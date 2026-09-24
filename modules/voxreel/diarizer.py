"""VoxReel Diarization Engine.

Implements FR-2 (Diarization) & §10 from VOX_engine_Plan.md:
- Voice Activity Detection (VAD) with min speech / silence gating
- Acoustic & speaker embedding extraction (192-d unit-normalized vectors)
- Agglomerative Hierarchical Clustering (AHC) with auto/fixed speaker count
- Overlap speech detection (overlap_flag)
- Minimum cluster utterance guard (clusters < 3 flagged low_confidence)
- Checkpoint generation (s2_diar.json)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("voxreel.diarizer")


@dataclass
class DiarizedSegment:
    start: float
    end: float
    speaker: str
    embedding: list[float] = field(default_factory=list)
    snr_db: float = 20.0
    overlap: bool = False
    low_confidence: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "speaker": self.speaker,
            "embedding": [round(float(x), 5) for x in self.embedding],
            "snr_db": round(self.snr_db, 1),
            "overlap": self.overlap,
            "low_confidence": self.low_confidence,
        }


class SpeakerEmbeddingExtractor:
    """Extracts 192-dimensional acoustic speaker embeddings from audio segments.

    Computes log-mel filterbank energies + statistical temporal pooling (mean + std),
    projected to a unit-normalized 192-d vector.
    """

    def __init__(self, embedding_dim: int = 192) -> None:
        self.embedding_dim = embedding_dim
        # Deterministic projection seed for reproducibility
        rng = np.random.default_rng(seed=42)
        # We project 80 mel bins * 2 (mean + std) = 160 features -> 192 dims
        self._proj = rng.standard_normal((160, self.embedding_dim)).astype(np.float32)
        # Normalize projection matrix columns
        self._proj /= np.linalg.norm(self._proj, axis=0, keepdims=True)

    def extract(self, audio: np.ndarray, sr: int = 16000) -> np.ndarray:
        """Extract a 192-d unit speaker embedding from raw audio samples."""
        arr = np.asarray(audio, dtype=np.float32).flatten()
        if arr.size < sr * 0.1:  # Pad if under 100ms
            arr = np.pad(arr, (0, int(sr * 0.1) - arr.size))

        # 1. Compute Short-Time Fourier Transform (STFT)
        n_fft = 512
        hop_length = int(sr * 0.01)  # 10ms
        win_length = int(sr * 0.025) # 25ms

        window = np.hanning(win_length)
        n_frames = 1 + (len(arr) - win_length) // hop_length
        if n_frames < 2:
            arr = np.tile(arr, 3)
            n_frames = 1 + (len(arr) - win_length) // hop_length

        frames = np.lib.stride_tricks.sliding_window_view(arr[:(n_frames - 1) * hop_length + win_length], win_length)[::hop_length]
        windowed = frames * window
        spectrum = np.abs(np.fft.rfft(windowed, n=n_fft))  # shape: (n_frames, 257)

        # 2. Simple 80-channel triangular Mel filterbank
        n_mels = 80
        low_freq = 80.0
        high_freq = sr / 2.0
        mel_low = 1127.0 * np.log(1.0 + low_freq / 700.0)
        mel_high = 1127.0 * np.log(1.0 + high_freq / 700.0)
        mel_points = np.linspace(mel_low, mel_high, n_mels + 2)
        hz_points = 700.0 * (np.exp(mel_points / 1127.0) - 1.0)
        bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

        fbank = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float32)
        for m in range(1, n_mels + 1):
            f_m_minus = bin_points[m - 1]
            f_m = bin_points[m]
            f_m_plus = bin_points[m + 1]

            for k in range(f_m_minus, f_m):
                if f_m != f_m_minus:
                    fbank[m - 1, k] = (k - f_m_minus) / (f_m - f_m_minus)
            for k in range(f_m, f_m_plus):
                if f_m_plus != f_m:
                    fbank[m - 1, k] = (f_m_plus - k) / (f_m_plus - f_m)

        mel_energies = np.dot(spectrum, fbank.T)
        log_mel = np.log(np.maximum(mel_energies, 1e-6))

        # 3. Statistical pooling over time (mean + std) -> 160 features
        mean_feat = np.mean(log_mel, axis=0)
        std_feat = np.std(log_mel, axis=0)
        feat_160 = np.concatenate([mean_feat, std_feat])

        # 4. Linear projection to 192 dimensions
        emb = feat_160 @ self._proj
        # 5. L2 unit normalization
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        return emb.astype(np.float32)


class Diarizer:
    """Performs VAD, acoustic segmentation, speaker embedding extraction, and clustering."""

    def __init__(
        self,
        min_speech_ms: int = 250,
        min_silence_ms: int = 150,
        min_cluster_utterances: int = 3,
    ) -> None:
        self.min_speech_ms = min_speech_ms
        self.min_silence_ms = min_silence_ms
        self.min_cluster_utterances = min_cluster_utterances
        self.embedder = SpeakerEmbeddingExtractor(embedding_dim=192)

    def detect_vad_segments(
        self,
        audio: np.ndarray,
        sr: int = 16000,
        energy_threshold: float = 0.015,
    ) -> list[tuple[float, float]]:
        """Detect speech regions using energy envelope with hysteresis and temporal smoothing."""
        frame_ms = 20
        frame_len = int(sr * (frame_ms / 1000.0))
        n_frames = len(audio) // frame_len
        if n_frames <= 0:
            return [(0.0, len(audio) / sr)]

        frames = audio[:n_frames * frame_len].reshape(n_frames, frame_len)
        rms = np.sqrt(np.mean(frames ** 2, axis=1))

        # Adaptive threshold based on noise floor
        noise_floor = np.percentile(rms, 15)
        speech_thresh = max(energy_threshold, noise_floor * 2.5)

        is_speech = rms > speech_thresh

        # Merge short silence gaps (< min_silence_ms)
        min_silence_frames = max(1, int(self.min_silence_ms / frame_ms))
        silence_run = 0
        for i in range(len(is_speech)):
            if not is_speech[i]:
                silence_run += 1
            else:
                if 0 < silence_run < min_silence_frames:
                    is_speech[i - silence_run:i] = True
                silence_run = 0

        # Remove short speech bursts (< min_speech_ms)
        min_speech_frames = max(1, int(self.min_speech_ms / frame_ms))
        speech_run = 0
        for i in range(len(is_speech)):
            if is_speech[i]:
                speech_run += 1
            else:
                if 0 < speech_run < min_speech_frames:
                    is_speech[i - speech_run:i] = False
                speech_run = 0

        # Convert boolean runs to time boundaries
        segments: list[tuple[float, float]] = []
        in_segment = False
        start_frame = 0

        for i, val in enumerate(is_speech):
            if val and not in_segment:
                in_segment = True
                start_frame = i
            elif not val and in_segment:
                in_segment = False
                start_sec = (start_frame * frame_len) / sr
                end_sec = (i * frame_len) / sr
                if end_sec - start_sec >= (self.min_speech_ms / 1000.0):
                    segments.append((start_sec, end_sec))

        if in_segment:
            start_sec = (start_frame * frame_len) / sr
            end_sec = len(audio) / sr
            if end_sec - start_sec >= (self.min_speech_ms / 1000.0):
                segments.append((start_sec, end_sec))

        if not segments:
            # Fallback to single segment covering the entire audio if speech detected anywhere
            segments.append((0.0, len(audio) / sr))

        return segments

    def cluster_embeddings(
        self,
        embeddings: np.ndarray,
        num_speakers: int | None = None,
        distance_threshold: float = 0.40,
    ) -> list[str]:
        """Perform Agglomerative Hierarchical Clustering on unit embeddings using cosine distance."""
        n = len(embeddings)
        if n == 0:
            return []
        if n == 1:
            return ["SPK_A"]

        # If num_speakers is specified (e.g. 1)
        if num_speakers == 1:
            return ["SPK_A"] * n

        # Cosine distance matrix: 1 - cosine_similarity
        # Since embeddings are unit normalized: dist = 1 - dot(A, B)
        sim_mat = embeddings @ embeddings.T
        dist_mat = np.maximum(0.0, 1.0 - sim_mat)
        np.fill_diagonal(dist_mat, 0.0)

        # Simple AHC with complete linkage
        # Start with each item in its own cluster
        clusters: list[list[int]] = [[i] for i in range(n)]

        target_k = num_speakers if num_speakers and num_speakers > 0 else None

        while len(clusters) > 1:
            if target_k and len(clusters) <= target_k:
                break

            # Find closest pair of clusters
            best_i, best_j = -1, -1
            min_dist = float("inf")

            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    # Complete linkage: max distance between any pair
                    d = max(dist_mat[p, q] for p in clusters[i] for q in clusters[j])
                    if d < min_dist:
                        min_dist = d
                        best_i, best_j = i, j

            # Stop if distance exceeds threshold (when auto-estimating k)
            if not target_k and min_dist > distance_threshold:
                break

            if best_i >= 0 and best_j >= 0:
                # Merge cluster best_j into best_i
                clusters[best_i].extend(clusters[best_j])
                clusters.pop(best_j)
            else:
                break

        # Map cluster indices to labels: SPK_A, SPK_B, ...
        labels = [""] * n
        for c_idx, cluster in enumerate(clusters):
            letter = chr(ord("A") + (c_idx % 26))
            spk_label = f"SPK_{letter}"
            for item in cluster:
                labels[item] = spk_label

        return labels

    def diarize(
        self,
        audio: np.ndarray,
        sr: int = 16000,
        num_speakers: int | None = None,
        output_checkpoint: str | Path | None = None,
    ) -> list[DiarizedSegment]:
        """Perform full diarization pipeline: VAD -> embedding extraction -> clustering."""
        from modules.voxreel.audio import AudioConditioner
        conditioner = AudioConditioner(target_sr=sr)

        # 1. VAD segmentation
        speech_intervals = self.detect_vad_segments(audio, sr=sr)

        # 2. Extract embeddings and compute SNR for each segment
        raw_segments: list[dict[str, Any]] = []
        valid_embeddings: list[np.ndarray] = []

        for start_sec, end_sec in speech_intervals:
            s_idx = int(start_sec * sr)
            e_idx = int(end_sec * sr)
            seg_audio = audio[s_idx:e_idx]

            emb = self.embedder.extract(seg_audio, sr=sr)
            snr = conditioner.calculate_snr(seg_audio, sr=sr)

            raw_segments.append({
                "start": start_sec,
                "end": end_sec,
                "embedding": emb,
                "snr_db": snr,
            })
            valid_embeddings.append(emb)

        # 3. Clustering
        emb_matrix = np.array(valid_embeddings, dtype=np.float32)
        speaker_labels = self.cluster_embeddings(emb_matrix, num_speakers=num_speakers)

        # 4. Count cluster utterances to apply FR-2.4 guard (< 3 utterances -> low_confidence)
        from collections import Counter
        cluster_counts = Counter(speaker_labels)

        # 5. Build final DiarizedSegment objects
        results: list[DiarizedSegment] = []
        for i, s in enumerate(raw_segments):
            spk = speaker_labels[i]
            is_low_conf = cluster_counts[spk] < self.min_cluster_utterances

            # Check overlap with previous segment
            overlap = False
            if i > 0 and s["start"] < raw_segments[i - 1]["end"]:
                overlap = True
                results[-1].overlap = True

            results.append(
                DiarizedSegment(
                    start=s["start"],
                    end=s["end"],
                    speaker=spk,
                    embedding=s["embedding"].tolist(),
                    snr_db=s["snr_db"],
                    overlap=overlap,
                    low_confidence=is_low_conf,
                )
            )

        # 6. Save s2_diar.json checkpoint
        if output_checkpoint:
            out_p = Path(output_checkpoint)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "num_speakers": len(cluster_counts),
                "segments": [r.to_dict() for r in results],
            }
            with open(out_p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        return results

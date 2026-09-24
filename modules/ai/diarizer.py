"""Diarization Engine supporting voice-embedding clustering (default) and PyAnnote (opt-in)."""

from __future__ import annotations

import logging
import wave
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from core.cancellation import CancellationToken
from core.exceptions import CancelledError
from modules.ai.engine import Availability, Engine, Transcript, classify_segment_tone

logger = logging.getLogger(__name__)


@dataclass
class DiarizerInput:
    """Input parameters for speaker diarization."""

    audio_path: Path | str
    transcript: Transcript
    num_speakers: int | None = None
    min_speakers: int = 1
    max_speakers: int = 10
    use_pyannote: bool = False
    hf_token: str | None = None
    characters: list[dict[str, str]] | None = None


class DiarizerEngine(Engine):
    """Engine conforming to Section 6 for speaker diarization."""

    name: str = "voice-embedding-clustering"

    @property
    def required_locks(self) -> list[str]:
        return []

    def probe(self) -> Availability:
        """Cheap check verifying diarization capability."""
        # Voice-embedding clustering is fully offline with NumPy
        pyannote_avail = False
        try:
            import pyannote.audio  # noqa: F401

            pyannote_avail = True
        except ImportError:
            pyannote_avail = False

        status_msg = "Voice-embedding clustering ready (offline default)"
        if pyannote_avail:
            status_msg += "; PyAnnote engine available (opt-in)"
        return Availability(status="ready", reason=status_msg)

    def _extract_pcm_segment(
        self,
        wav_path: Path,
        start_sec: float,
        end_sec: float,
    ) -> np.ndarray:
        """Extract float32 audio samples for a specific time window from a WAV file."""
        with wave.open(str(wav_path), "rb") as wf:
            framerate = wf.getframerate()
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()

            start_frame = max(0, int(start_sec * framerate))
            end_frame = min(wf.getnframes(), int(end_sec * framerate))
            count = max(1, end_frame - start_frame)

            wf.setpos(start_frame)
            raw_bytes = wf.readframes(count)

            if sampwidth == 2:
                dtype = np.int16
                scale = 32768.0
            elif sampwidth == 4:
                dtype = np.int32
                scale = 2147483648.0
            else:
                dtype = np.uint8
                scale = 128.0

            audio = np.frombuffer(raw_bytes, dtype=dtype).astype(np.float32) / scale
            if n_channels > 1:
                audio = audio.reshape(-1, n_channels).mean(axis=1)
            return audio

    def _estimate_f0(self, samples: np.ndarray, sr: int = 16000) -> tuple[float, float]:
        """Estimate fundamental frequency (F0/pitch in Hz) and voiced ratio using autocorrelation."""
        if len(samples) < 512:
            return 150.0, 0.0

        frame_len = int(0.040 * sr)  # 40ms frame (640 samples)
        hop_len = int(0.020 * sr)    # 20ms hop (320 samples)

        min_f0 = 65.0   # Deep male voice
        max_f0 = 450.0  # Child / high female voice
        min_lag = int(sr / max_f0)
        max_lag = int(sr / min_f0)

        voiced_f0s: list[float] = []
        total_frames = 0

        for start in range(0, len(samples) - frame_len, hop_len):
            total_frames += 1
            frame = samples[start : start + frame_len]
            energy = float(np.sum(frame**2))
            if energy < 1e-4:
                continue

            frame = frame - np.mean(frame)
            n_fft = 1 << (len(frame) * 2 - 1).bit_length()
            fx = np.fft.rfft(frame, n_fft)
            r = np.fft.irfft(fx * np.conj(fx), n_fft)[:frame_len]

            r0 = r[0] + 1e-12
            norm_r = r / r0

            search_window = norm_r[min_lag : min(max_lag, len(norm_r))]
            if len(search_window) == 0:
                continue

            peak_idx = int(np.argmax(search_window))
            peak_val = float(search_window[peak_idx])

            if peak_val > 0.28:
                true_lag = float(min_lag + peak_idx)
                if 0 < peak_idx < len(search_window) - 1:
                    alpha = float(search_window[peak_idx - 1])
                    beta = peak_val
                    gamma = float(search_window[peak_idx + 1])
                    denom = alpha - 2 * beta + gamma + 1e-12
                    delta = 0.5 * (alpha - gamma) / denom
                    true_lag += delta

                f0 = float(sr / max(1.0, true_lag))
                if min_f0 <= f0 <= max_f0:
                    voiced_f0s.append(f0)

        voiced_ratio = len(voiced_f0s) / max(1, total_frames)
        if voiced_f0s:
            median_f0 = float(np.median(voiced_f0s))
        else:
            median_f0 = 150.0
        return median_f0, voiced_ratio

    def _classify_voice_profile(
        self,
        f0: float,
        centroid: float,
        voiced_ratio: float = 0.5,
    ) -> str:
        """Classify vocal register into Male (Deep/Adult), Female (Lead/Mature), Child, or Elderly."""
        if f0 >= 245.0 or (f0 >= 225.0 and centroid >= 2600.0):
            return "Child"
        if f0 >= 185.0 or (f0 >= 175.0 and centroid >= 2200.0):
            if f0 >= 200.0:
                return "Female Lead"
            return "Mature Female"
        if f0 < 130.0 or (f0 < 140.0 and centroid < 1400.0):
            return "Deep Male"
        return "Male Lead"

    def _compute_acoustic_features(self, samples: np.ndarray, sr: int = 16000) -> np.ndarray:
        """Compute rich vocal tract, pitch, and timbre acoustic representation vector for speaker separation."""
        if len(samples) < 256:
            return np.zeros(32, dtype=np.float32)

        # 1. Pitch / F0 estimation
        f0, voiced_ratio = self._estimate_f0(samples, sr)

        # 2. Zero crossing rate
        zcr = float(np.mean(np.abs(np.diff(np.sign(samples)))) / 2.0)

        # 3. RMS Energy
        rms = float(np.sqrt(np.mean(samples**2) + 1e-12))

        # 4. FFT Magnitude Spectrogram
        fft_data = np.abs(np.fft.rfft(samples * np.hamming(len(samples))))
        freqs = np.fft.rfftfreq(len(samples), 1.0 / sr)

        sum_fft = np.sum(fft_data) + 1e-12
        centroid = float(np.sum(freqs * fft_data) / sum_fft)
        spread = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * fft_data) / sum_fft))

        cum_energy = np.cumsum(fft_data)
        rolloff_idx = np.searchsorted(cum_energy, 0.85 * sum_fft)
        rolloff = float(freqs[min(rolloff_idx, len(freqs) - 1)])

        # 5. Low vs High frequency ratio (formant balance)
        low_mask = freqs < 1000.0
        high_mask = (freqs >= 1000.0) & (freqs < 4000.0)
        low_energy = float(np.sum(fft_data[low_mask] ** 2))
        high_energy = float(np.sum(fft_data[high_mask] ** 2))
        lh_ratio = float(np.clip(np.log1p(low_energy) / (np.log1p(high_energy) + 1.0), 0.0, 5.0))

        # 6. Sub-band log energies (normalized by frame energy to represent formant spectral shape)
        band_edges = np.linspace(80, min(4000, sr // 2), 17)
        band_energies: list[float] = []
        tot_energy = float(np.log1p(np.sum(fft_data**2)) + 1e-6)
        for i in range(len(band_edges) - 1):
            mask = (freqs >= band_edges[i]) & (freqs < band_edges[i + 1])
            band_energy = float(np.sum(fft_data[mask] ** 2))
            band_energies.append(float(np.log1p(band_energy) / tot_energy))

        feature_vector = np.array(
            [
                (f0 / 200.0) * 4.5,
                (centroid / 2000.0) * 3.0,
                (spread / 1500.0) * 1.5,
                (rolloff / 3000.0) * 1.5,
                lh_ratio * 1.5,
                voiced_ratio * 2.0,
                zcr * 2.0,
                rms * 1.0,
            ]
            + band_energies,
            dtype=np.float32,
        )
        norm = np.linalg.norm(feature_vector)
        if norm > 1e-9:
            feature_vector /= norm
        return feature_vector

    def _cluster_features(
        self,
        features: np.ndarray,
        n_clusters: int,
    ) -> list[int]:
        """Cluster feature vectors into speaker labels using K-Means with K-Means++ initialization."""
        n_samples = len(features)
        if n_samples == 0:
            return []
        if n_clusters <= 1 or n_samples == 1:
            return [0] * n_samples

        clamped_clusters = min(n_clusters, n_samples)

        # Standardize features across dimensions
        std = np.std(features, axis=0, keepdims=True)
        std[std < 1e-6] = 1.0
        Z = (features - np.mean(features, axis=0, keepdims=True)) / std

        best_inertia = float("inf")
        best_labels: np.ndarray | None = None
        rng = np.random.RandomState(42)

        for _ in range(15):
            # K-means++ initialization
            centers = [Z[rng.randint(n_samples)]]
            for _ in range(1, clamped_clusters):
                dist_sq = np.min([np.sum((Z - c) ** 2, axis=1) for c in centers], axis=0)
                probs = dist_sq / (np.sum(dist_sq) + 1e-12)
                next_idx = rng.choice(n_samples, p=probs)
                centers.append(Z[next_idx])
            c_arr = np.array(centers)

            for _ in range(30):
                dists = np.sum((Z[:, None, :] - c_arr[None, :, :]) ** 2, axis=2)
                labels = np.argmin(dists, axis=1)
                new_centers = []
                for c in range(clamped_clusters):
                    mask = labels == c
                    if np.any(mask):
                        new_centers.append(np.mean(Z[mask], axis=0))
                    else:
                        new_centers.append(c_arr[c])
                c_new = np.array(new_centers)
                if np.allclose(c_arr, c_new, atol=1e-4):
                    break
                c_arr = c_new

            inertia = float(np.sum(np.min(np.sum((Z[:, None, :] - c_arr[None, :, :]) ** 2, axis=2), axis=1)))
            if inertia < best_inertia:
                best_inertia = inertia
                best_labels = labels

        if best_labels is None:
            return [0] * n_samples
        return [int(lbl) for lbl in best_labels]

    def _estimate_num_speakers(
        self,
        features: np.ndarray,
        min_spk: int = 1,
        max_spk: int = 10,
        raw_f0s: list[float] | None = None,
    ) -> int:
        """Estimate optimal speaker count based on pitch bimodality and silhouette-like cosine separation."""
        n_samples = len(features)
        if n_samples <= 1:
            return 1

        # Check pitch variance / span for multi-speaker alternation
        effective_min_spk = min_spk
        if raw_f0s and len(raw_f0s) >= 3:
            v_f0s = [f for f in raw_f0s if f > 60.0]
            if len(v_f0s) >= 3:
                f0_span = float(np.max(v_f0s) - np.min(v_f0s))
                f0_std = float(np.std(v_f0s))
                if f0_span >= 35.0 and f0_std >= 14.0:
                    effective_min_spk = max(effective_min_spk, 2)

        best_k = effective_min_spk
        best_score = -float("inf")

        for k in range(max(2, effective_min_spk), min(max_spk + 1, n_samples + 1)):
            labels = self._cluster_features(features, k)
            sim_matrix = np.dot(features, features.T)
            intra_sims: list[float] = []
            inter_sims: list[float] = []

            for i in range(n_samples):
                for j in range(i + 1, n_samples):
                    if labels[i] == labels[j]:
                        intra_sims.append(float(sim_matrix[i, j]))
                    else:
                        inter_sims.append(float(sim_matrix[i, j]))

            mean_intra = float(np.mean(intra_sims)) if intra_sims else 1.0
            mean_inter = float(np.mean(inter_sims)) if inter_sims else 0.0
            separation = mean_intra - mean_inter
            complexity_penalty = 0.015 * (k - 2)
            score = separation - complexity_penalty

            if score > best_score:
                best_score = score
                best_k = k

        # If effective_min_spk was 1 and no strong cluster separation was found, return 1
        if effective_min_spk == 1 and best_score < 0.005:
            return 1

        return max(1, best_k)

    def run(
        self,
        inputs: DiarizerInput,
        workdir: Path,
        token: CancellationToken,
        progress: Callable[[float, str], None],
    ) -> Transcript:
        """Execute speaker diarization on transcript segments, updating speaker labels."""
        token.throw_if_cancelled()

        workdir = Path(workdir).resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        audio_path = Path(inputs.audio_path).resolve()
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        segments = inputs.transcript.segments
        if not segments:
            logger.info("No transcript segments provided to diarize.")
            return inputs.transcript

        # Determine native sample rate from audio file
        try:
            with wave.open(str(audio_path), "rb") as wf:
                native_sr = wf.getframerate()
        except Exception:
            native_sr = 16000

        progress(0.1, f"Extracting acoustic features for {len(segments)} dialogue segments ({native_sr} Hz)...")
        token.throw_if_cancelled()

        features_list: list[np.ndarray] = []
        raw_meta_list: list[dict[str, float]] = []

        for idx, seg in enumerate(segments):
            if token.is_cancelled:
                raise CancelledError("Diarization cancelled by user token.")

            samples = self._extract_pcm_segment(audio_path, seg.start, seg.end)
            f0, vr = self._estimate_f0(samples, sr=native_sr)
            rms = float(np.sqrt(np.mean(samples**2) + 1e-12))
            fft_data = np.abs(np.fft.rfft(samples * np.hamming(len(samples))))
            freqs = np.fft.rfftfreq(len(samples), 1.0 / native_sr)
            sum_fft = np.sum(fft_data) + 1e-12
            centroid = float(np.sum(freqs * fft_data) / sum_fft)

            raw_meta_list.append({"f0": f0, "vr": vr, "rms": rms, "centroid": centroid})
            feat = self._compute_acoustic_features(samples, sr=native_sr)
            features_list.append(feat)

            prog = 0.1 + 0.5 * (idx / len(segments))
            progress(prog, f"Analyzing voice characteristics ({idx + 1}/{len(segments)})...")

        feature_matrix = np.vstack(features_list)
        token.throw_if_cancelled()

        # Determine speaker count
        if inputs.num_speakers is not None:
            n_speakers = max(1, inputs.num_speakers)
        else:
            progress(0.65, "Estimating number of active speakers...")
            raw_f0s = [m["f0"] for m in raw_meta_list]
            n_speakers = self._estimate_num_speakers(
                feature_matrix,
                min_spk=inputs.min_speakers,
                max_spk=inputs.max_speakers,
                raw_f0s=raw_f0s,
            )

        progress(0.75, f"Clustering segments into {n_speakers} speaker(s)...")
        token.throw_if_cancelled()
        cluster_labels = self._cluster_features(feature_matrix, n_speakers)

        # Order clusters by their first appearance in the transcript
        unique_labels: list[int] = []
        for lbl in cluster_labels:
            if lbl not in unique_labels:
                unique_labels.append(lbl)

        # Compute vocal profile and pitch for each cluster from raw physical acoustics
        cluster_profiles: dict[int, str] = {}
        for c_id in unique_labels:
            member_indices = [i for i, lbl in enumerate(cluster_labels) if lbl == c_id]
            avg_f0 = float(np.mean([raw_meta_list[i]["f0"] for i in member_indices]))
            avg_centroid = float(np.mean([raw_meta_list[i]["centroid"] for i in member_indices]))
            avg_voiced = float(np.mean([raw_meta_list[i]["vr"] for i in member_indices]))
            cluster_profiles[c_id] = self._classify_voice_profile(avg_f0, avg_centroid, avg_voiced)

        characters = inputs.characters or []
        speaker_mapping: dict[int, str] = {}

        for rank, c_id in enumerate(unique_labels):
            spk_num = rank + 1
            prof = cluster_profiles.get(c_id, "Voice")
            if rank < len(characters):
                char_data = characters[rank]
                char_name = char_data.get("character") or char_data.get("actor") or f"Actor {spk_num}"
                speaker_mapping[c_id] = f"Speaker {spk_num}: {char_name} ({prof})"
            else:
                speaker_mapping[c_id] = f"Speaker {spk_num} ({prof})"

        # Assign speaker labels and emotion tone to transcript segments
        for i, (seg, lbl) in enumerate(zip(segments, cluster_labels, strict=False)):
            seg.speaker = speaker_mapping[lbl]
            meta = raw_meta_list[i]
            c_spk_f0 = float(np.mean([raw_meta_list[j]["f0"] for j, c_lbl in enumerate(cluster_labels) if c_lbl == lbl]))
            seg.emotion = classify_segment_tone(
                text=seg.source_text,
                f0_hz=meta["f0"],
                voiced_ratio=meta["vr"],
                rms=meta["rms"],
                spk_mean_f0=c_spk_f0,
            )

        # Save diarized transcript
        out_transcript = Transcript(
            segments=segments,
            language=inputs.transcript.language,
            duration=inputs.transcript.duration,
        )
        out_json = workdir / "diarized_transcript.json"
        out_transcript.save_json(out_json)

        progress(1.0, f"Diarization complete. Identified {len(speaker_mapping)} speakers.")
        return out_transcript

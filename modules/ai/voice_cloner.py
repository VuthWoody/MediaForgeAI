"""Real Voice Cloning & Neural Speaker Embedding Engine using ONNX Runtime.

Implements zero-shot voice cloning from real video actor reference clips:
- Extracts 256-dimensional neural speaker voice fingerprints (tone_extract.onnx)
- Converts synthesized base speech into the exact vocal timbre of the real video actor (tone_color.onnx)
- Provides neural embeddings for high-accuracy speaker diarization clustering
"""

from __future__ import annotations

import logging
import subprocess
import time
import wave
from pathlib import Path

import numpy as np
import onnxruntime as ort

logger = logging.getLogger(__name__)

HF_REPO_ID = "Hinotsuba/OpenVoice-ONNX-v2"
EXTRACT_MODEL_FILENAME = "tone_extract.onnx"
COLOR_MODEL_FILENAME = "tone_color.onnx"
CONFIG_FILENAME = "tone_config.json"


class RealVoiceCloner:
    """Zero-shot voice cloner transferring real video actor timbre onto synthesized dialogue."""

    _instance: RealVoiceCloner | None = None

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = (
            Path(cache_dir).resolve()
            if cache_dir
            else Path.home() / "AppData" / "Local" / "MediaForgeAI" / "models" / "openvoice"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._extract_session: ort.InferenceSession | None = None
        self._color_session: ort.InferenceSession | None = None
        self._models_available: bool = False
        self._embedding_cache: dict[str, np.ndarray] = {}

        self._init_models()

    @classmethod
    def get_instance(cls) -> RealVoiceCloner:
        if cls._instance is None:
            cls._instance = RealVoiceCloner()
        return cls._instance

    def _init_models(self) -> None:
        """Locate or download ONNX voice cloning models."""
        try:
            from huggingface_hub import hf_hub_download

            extract_path = self.cache_dir / EXTRACT_MODEL_FILENAME
            color_path = self.cache_dir / COLOR_MODEL_FILENAME

            # Check if models exist in local cache dir; otherwise download from HF
            if not extract_path.exists() or extract_path.stat().st_size < 1000000:
                logger.info("Downloading voice cloning extract model from %s...", HF_REPO_ID)
                dl_path = hf_hub_download(repo_id=HF_REPO_ID, filename=EXTRACT_MODEL_FILENAME)
                extract_path = Path(dl_path)

            if not color_path.exists() or color_path.stat().st_size < 10000000:
                logger.info("Downloading voice cloning color model from %s...", HF_REPO_ID)
                dl_path = hf_hub_download(repo_id=HF_REPO_ID, filename=COLOR_MODEL_FILENAME)
                color_path = Path(dl_path)

            opts = ort.SessionOptions()
            opts.intra_op_num_threads = 4
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

            self._extract_session = ort.InferenceSession(
                str(extract_path), opts, providers=["CPUExecutionProvider"]
            )
            self._color_session = ort.InferenceSession(
                str(color_path), opts, providers=["CPUExecutionProvider"]
            )
            self._models_available = True
            logger.info("RealVoiceCloner initialized with ONNX models.")
        except Exception as e:
            logger.warning("Could not initialize RealVoiceCloner ONNX models: %s", e)
            self._models_available = False

    @property
    def is_available(self) -> bool:
        return self._models_available and (self._extract_session is not None) and (self._color_session is not None)

    @staticmethod
    def load_audio_22050(wav_path: Path | str) -> np.ndarray:
        """Load and resample audio to 22050 Hz mono float32."""
        p = Path(wav_path).resolve()
        if not p.exists():
            return np.zeros(2205, dtype=np.float32)

        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(p),
            "-ar",
            "22050",
            "-ac",
            "1",
            "-f",
            "s16le",
            "-",
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, check=True)
        return np.frombuffer(proc.stdout, dtype=np.int16).astype(np.float32) / 32768.0

    @staticmethod
    def compute_spectrogram(
        audio: np.ndarray,
        n_fft: int = 1024,
        hop_length: int = 256,
        win_length: int = 1024,
    ) -> np.ndarray:
        """Compute linear magnitude spectrogram with Hann window (shape: [frames, 513])."""
        pad_len = n_fft // 2
        padded = np.pad(audio, (pad_len, pad_len), mode="reflect")
        n_frames = 1 + (len(padded) - win_length) // hop_length
        if n_frames < 2:
            padded = np.tile(padded, 2)
            n_frames = 1 + (len(padded) - win_length) // hop_length

        frames = np.lib.stride_tricks.sliding_window_view(
            padded[: (n_frames - 1) * hop_length + win_length], win_length
        )[::hop_length]
        window = np.hanning(win_length).astype(np.float32)
        windowed = frames * window
        return np.abs(np.fft.rfft(windowed, n=n_fft)).astype(np.float32)

    def extract_speaker_embedding(self, audio_or_path: np.ndarray | Path | str, sr: int = 16000) -> np.ndarray:
        """Extract a 256-dimensional unit-normalized speaker voice fingerprint."""
        if not self.is_available or self._extract_session is None:
            return np.zeros(256, dtype=np.float32)

        if isinstance(audio_or_path, (Path, str)):
            p = Path(audio_or_path)
            cache_key = f"{p.resolve()}_{p.stat().st_mtime if p.exists() else 0}"
            if cache_key in self._embedding_cache:
                return self._embedding_cache[cache_key]
            audio_22k = self.load_audio_22050(p)
        else:
            samples = np.asarray(audio_or_path, dtype=np.float32).flatten()
            if sr != 22050:
                n_target = int(len(samples) * 22050 / sr)
                audio_22k = np.interp(
                    np.linspace(0, len(samples), n_target, endpoint=False),
                    np.arange(len(samples)),
                    samples,
                ).astype(np.float32)
            else:
                audio_22k = samples
            cache_key = None

        if len(audio_22k) < 512:
            return np.zeros(256, dtype=np.float32)

        spec = self.compute_spectrogram(audio_22k)
        spec_tensor = spec[np.newaxis, :, :]  # shape: [1, frames, 513]

        emb = self._extract_session.run(None, {"input": spec_tensor})[0][0]  # shape: [256]
        norm = float(np.linalg.norm(emb))
        if norm > 1e-12:
            emb = emb / norm

        if cache_key:
            self._embedding_cache[cache_key] = emb

        return emb

    def clone_voice(
        self,
        base_audio_path: Path | str,
        reference_audio_path: Path | str,
        output_path: Path | str,
        tau: float = 1.0,
    ) -> Path:
        """Convert synthesized base speech to match the real video actor's voice."""
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if not self.is_available or self._extract_session is None or self._color_session is None:
            # Fallback: copy base audio directly
            import shutil
            shutil.copy2(str(base_audio_path), str(out_p))
            return out_p

        base_p = Path(base_audio_path).resolve()
        ref_p = Path(reference_audio_path).resolve()

        if not base_p.exists():
            raise FileNotFoundError(f"Base audio not found: {base_p}")
        if not ref_p.exists():
            import shutil
            shutil.copy2(str(base_p), str(out_p))
            return out_p

        t_start = time.time()

        # 1. Extract target actor voice fingerprint (from real video audio)
        ref_audio = self.load_audio_22050(ref_p)
        ref_spec = self.compute_spectrogram(ref_audio)
        dest_tone = self._extract_session.run(None, {"input": ref_spec[np.newaxis, :, :]})[0]  # [1, 256]

        # 2. Extract base synthesized speech voice fingerprint
        base_audio = self.load_audio_22050(base_p)
        base_spec = self.compute_spectrogram(base_audio)
        src_tone = self._extract_session.run(None, {"input": base_spec[np.newaxis, :, :]})[0]   # [1, 256]

        # 3. Prepare inputs for Tone Color Converter
        audio_input = np.transpose(base_spec, (1, 0))[np.newaxis, :, :]  # [1, 513, frames]
        audio_length = np.array([audio_input.shape[2]], dtype=np.int64)
        src_tone_input = src_tone[:, :, np.newaxis].astype(np.float32)
        dest_tone_input = dest_tone[:, :, np.newaxis].astype(np.float32)
        tau_tensor = np.array([tau], dtype=np.float32)

        converted = self._color_session.run(
            None,
            {
                "audio": audio_input,
                "audio_length": audio_length,
                "src_tone": src_tone_input,
                "dest_tone": dest_tone_input,
                "tau": tau_tensor,
            },
        )[0]

        converted_samples = np.squeeze(converted).flatten()
        max_val = float(np.max(np.abs(converted_samples))) if len(converted_samples) > 0 else 0.0
        if max_val > 0.98:
            converted_samples = (converted_samples / max_val) * 0.95

        int_samples = (converted_samples * 32767.0).astype(np.int16)

        tmp_raw_22k = out_p.with_suffix(".tmp22k.wav")
        with wave.open(str(tmp_raw_22k), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(22050)
            wf.writeframes(int_samples.tobytes())

        # Standardize to 44.1kHz PCM s16le for clean mixing
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(tmp_raw_22k),
                "-ar",
                "44100",
                "-c:a",
                "pcm_s16le",
                str(out_p),
            ],
            check=True,
            capture_output=True,
        )
        tmp_raw_22k.unlink(missing_ok=True)

        logger.info(
            "Voice cloned successfully from %s in %.2fs -> %s",
            ref_p.name,
            time.time() - t_start,
            out_p.name,
        )
        return out_p

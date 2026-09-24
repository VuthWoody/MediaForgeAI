"""VoxReel Audio Conditioning & Ingestion Engine.

Implements FR-1 (Ingestion) & §10.1 from VOX_engine_Plan.md:
- Auto-detects audio streams and channel layouts
- Extracts center dialogue channel from 5.1/7.1 surround sound
- Converts to 16,000 Hz mono PCM WAV
- Normalizes loudness to EBU R128 (-23 LUFS target)
- Performs dialogue isolation / source separation pre-pass
- Computes Signal-to-Noise Ratio (SNR) for quality gating
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("voxreel.audio")


def _find_ffmpeg() -> str:
    """Find a usable ffmpeg executable."""
    cmd = shutil.which("ffmpeg")
    if cmd:
        return cmd
    try:
        import static_ffmpeg
        ffmpeg_bin, _ = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if ffmpeg_bin and Path(ffmpeg_bin).exists():
            return str(ffmpeg_bin)
    except Exception:
        pass
    return "ffmpeg"


def _find_ffprobe() -> str:
    """Find a usable ffprobe executable."""
    cmd = shutil.which("ffprobe")
    if cmd:
        return cmd
    try:
        import static_ffmpeg
        _, ffprobe_bin = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        if ffprobe_bin and Path(ffprobe_bin).exists():
            return str(ffprobe_bin)
    except Exception:
        pass
    return "ffprobe"


class AudioConditioner:
    """Engine responsible for probing, conditioning, center-channel extraction, and SNR evaluation."""

    def __init__(
        self,
        ffmpeg_bin: str | None = None,
        ffprobe_bin: str | None = None,
        target_sr: int = 16000,
        target_lufs: float = -23.0,
    ) -> None:
        self.ffmpeg_bin = ffmpeg_bin or _find_ffmpeg()
        self.ffprobe_bin = ffprobe_bin or _find_ffprobe()
        self.target_sr = target_sr
        self.target_lufs = target_lufs

    def probe(self, media_path: str | Path) -> dict[str, Any]:
        """Probe media file container, duration, and audio stream channel layouts."""
        p = Path(media_path)
        if not p.exists():
            raise FileNotFoundError(f"Media file not found: {media_path}")

        info: dict[str, Any] = {
            "name": p.name,
            "path": str(p.resolve()),
            "container": p.suffix.lower().lstrip("."),
            "duration_sec": 0.0,
            "streams": [],
            "best_dialogue_track": 0,
            "channels": 2,
            "layout": "stereo",
        }

        try:
            cmd = [
                self.ffprobe_bin,
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                "-select_streams", "a",
                str(p),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)

            format_info = data.get("format", {})
            info["duration_sec"] = float(format_info.get("duration", 0.0))

            streams = data.get("streams", [])
            for idx, s in enumerate(streams):
                channels = int(s.get("channels", 2))
                layout = str(s.get("channel_layout", "stereo"))
                tags = s.get("tags", {})
                lang = tags.get("language", "und")
                stream_dict = {
                    "index": idx,
                    "stream_id": s.get("index", idx),
                    "channels": channels,
                    "channel_layout": layout,
                    "language": lang,
                    "sample_rate": int(s.get("sample_rate", 44100)),
                }
                info["streams"].append(stream_dict)

                # Prioritize multi-channel stream with center channel
                if channels >= 6:
                    info["best_dialogue_track"] = idx
                    info["channels"] = channels
                    info["layout"] = layout

            if not streams:
                # Video file without separate probed stream or pure wave header
                info["channels"] = 2
                info["layout"] = "stereo"
            elif info["best_dialogue_track"] == 0 and streams:
                info["channels"] = streams[0].get("channels", 2)
                info["layout"] = streams[0].get("channel_layout", "mono" if info["channels"] == 1 else "stereo")

        except Exception as e:
            logger.warning("ffprobe probe failed, using fallback metrics: %s", e)
            # Basic fallback
            info["duration_sec"] = 0.0

        return info

    def condition_audio(
        self,
        input_path: str | Path,
        output_path: str | Path,
        force_center: bool = True,
        apply_loudnorm: bool = True,
        source_separation: bool = False,
    ) -> Path:
        """Process input media into a normalized 16k mono dialogue WAV.

        Args:
            input_path: Path to source media file (MKV, MP4, WAV, etc.)
            output_path: Destination path for conditioned 16kHz mono WAV (s1_audio.wav)
            force_center: If True and input has 5.1/7.1 channels, isolate center channel.
            apply_loudnorm: If True, normalize to EBU R128 (-23 LUFS).
            source_separation: If True, apply speech isolation pre-pass.
        """
        in_p = Path(input_path).resolve()
        out_p = Path(output_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if not in_p.exists():
            raise FileNotFoundError(f"Input file not found: {in_p}")

        # Probe layout
        media_info = self.probe(in_p)
        channels = media_info.get("channels", 2)

        # Build FFmpeg filter chain
        filters: list[str] = []

        # 1. Channel layout handling (FR-1.2)
        # 5.1 surround sound layout is FL, FR, FC, LFE, BL, BR. Center channel is c2.
        if force_center and channels >= 6:
            # Pan filter extracts center channel (c2) to mono (c0)
            filters.append("pan=mono|c0=c2")
        elif channels > 1:
            # Downmix stereo to mono
            filters.append("pan=mono|c0=0.5*c0+0.5*c1")

        # 2. Source separation / vocal bandpass conditioning
        if source_separation:
            # Vocal isolation frequency shaping: highpass 80Hz (rumble), lowpass 8000Hz (hiss)
            filters.append("highpass=f=80,lowpass=f=8000")

        # 3. EBU R128 loudness normalization (-23 LUFS target, FR-1.4)
        if apply_loudnorm:
            filters.append(f"loudnorm=I={self.target_lufs}:LRA=7:tp=-2")

        filter_arg = ",".join(filters) if filters else "anull"

        cmd = [
            self.ffmpeg_bin,
            "-y",
            "-i", str(in_p),
            "-vn",
            "-af", filter_arg,
            "-ar", str(self.target_sr),
            "-ac", "1",
            "-c:a", "pcm_s16le",
            str(out_p),
        ]

        logger.info("Conditioning audio: %s -> %s", in_p.name, out_p.name)
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.warning("FFmpeg filter failed, attempting basic mono conversion: %s", result.stderr)
            # Fallback simple command without loudnorm
            fallback_cmd = [
                self.ffmpeg_bin,
                "-y",
                "-i", str(in_p),
                "-vn",
                "-ar", str(self.target_sr),
                "-ac", "1",
                "-c:a", "pcm_s16le",
                str(out_p),
            ]
            subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)

        return out_p

    def load_audio_array(self, wav_path: str | Path) -> tuple[np.ndarray, int]:
        """Load mono audio file into normalized float32 numpy array in range [-1.0, 1.0]."""
        p = Path(wav_path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {p}")

        # Use av or soundfile or wave or pydub
        import wave
        with wave.open(str(p), "rb") as wf:
            sr = wf.getframerate()
            n_channels = wf.getnchannels()
            n_frames = wf.getnframes()
            data = wf.readframes(n_frames)

        arr = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
        if n_channels > 1:
            arr = arr.reshape(-1, n_channels).mean(axis=1)

        return arr, sr

    def save_audio_array(self, audio: np.ndarray, output_path: str | Path, sr: int = 16000) -> Path:
        """Save a float32 numpy array as a 16-bit PCM WAV."""
        import wave
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        clipped = np.clip(audio, -1.0, 1.0)
        int16_data = (clipped * 32767.0).astype(np.int16).tobytes()

        with wave.open(str(out_p), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(int16_data)

        return out_p

    def calculate_snr(self, audio: np.ndarray, sr: int = 16000) -> float:
        """Calculate estimated Signal-to-Noise Ratio (dB) of an audio segment.

        Uses energy percentile estimation:
        - Signal power: 95th percentile frame RMS power
        - Noise power: 10th percentile frame RMS power (silence/ambient floor)
        - SNR (dB) = 10 * log10(P_signal / P_noise)
        """
        arr = np.asarray(audio, dtype=np.float32).flatten()
        if arr.size < sr * 0.1:  # Less than 100ms
            return 0.0

        frame_len = int(sr * 0.02)  # 20ms frame
        hop_len = int(sr * 0.01)    # 10ms hop
        n_frames = (len(arr) - frame_len) // hop_len
        if n_frames <= 0:
            return 0.0

        frames = np.lib.stride_tricks.sliding_window_view(arr[:n_frames * hop_len + frame_len], frame_len)[::hop_len]
        powers = np.mean(frames ** 2, axis=1)

        signal_power = float(np.percentile(powers, 95))
        noise_power = float(np.percentile(powers, 10))

        if noise_power <= 1e-12:
            noise_power = 1e-12

        if signal_power <= noise_power:
            return 0.0

        snr_db = 10.0 * np.log10(signal_power / noise_power)
        return float(np.clip(snr_db, 0.0, 60.0))

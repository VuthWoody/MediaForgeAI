"""Audio waveform peak generator for timeline visualization with disk caching."""

from __future__ import annotations

import json
import logging
import struct
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class WaveformGenerator:
    """Extracts and caches normalized audio peak data (0.0 to 1.0) for timeline visualization."""

    SAMPLE_RATE: int = 8000
    PEAKS_PER_SECOND: int = 50

    @classmethod
    def get_peaks(
        cls,
        media_path: Path | str,
        cache_dir: Path | str | None = None,
        force_recompute: bool = False,
    ) -> list[float]:
        """Compute or load cached normalized audio peak points (0.0 to 1.0) for media file."""
        src_path = Path(media_path).resolve()
        if not src_path.exists():
            return []

        mtime = src_path.stat().st_mtime

        # Determine cache file location
        if cache_dir:
            c_dir = Path(cache_dir)
            c_dir.mkdir(parents=True, exist_ok=True)
            cache_file = c_dir / f"{src_path.stem}.peaks.json"
        else:
            cache_file = src_path.with_suffix(".peaks.json")

        # Check cache validity
        if not force_recompute and cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    data = json.load(f)
                if abs(float(data.get("mtime", 0.0)) - mtime) < 0.001:
                    peaks = data.get("peaks", [])
                    if peaks:
                        return [float(p) for p in peaks]
            except Exception as e:
                logger.debug("Failed to read waveform cache: %s", e)

        # Generate peaks via FFmpeg 8kHz mono 16-bit PCM stream
        cmd = [
            "ffmpeg",
            "-v",
            "quiet",
            "-i",
            str(src_path),
            "-vn",
            "-ar",
            str(cls.SAMPLE_RATE),
            "-ac",
            "1",
            "-f",
            "s16le",
            "-",
        ]

        try:
            res = subprocess.run(cmd, capture_output=True, check=True, timeout=60)
            raw_pcm = res.stdout
        except Exception as e:
            logger.warning("Failed to extract PCM audio for waveform: %s", e)
            return []

        if not raw_pcm:
            return []

        # 2 bytes per 16-bit signed sample
        num_samples = len(raw_pcm) // 2
        samples = struct.unpack(f"<{num_samples}h", raw_pcm[: num_samples * 2])

        chunk_size = max(1, cls.SAMPLE_RATE // cls.PEAKS_PER_SECOND)
        peaks: list[float] = []

        for i in range(0, num_samples, chunk_size):
            chunk = samples[i : i + chunk_size]
            if not chunk:
                continue
            peak = max(abs(min(chunk)), abs(max(chunk))) / 32768.0
            peaks.append(round(min(1.0, peak), 4))

        # Save to cache
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"mtime": mtime, "peaks": peaks}, f)
        except Exception as e:
            logger.debug("Failed to write waveform cache: %s", e)

        return peaks

"""Audio-visual alignment engine adjusting dubbed audio speed and padding to match original timestamps."""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from core.cancellation import CancellationToken
from core.utils import to_safe_path
from modules.media.inspector import MediaInspector

logger = logging.getLogger(__name__)


@dataclass
class AlignedClipResult:
    """Result of an alignment operation."""

    aligned_wav_path: Path
    original_duration: float
    actual_duration: float
    speed_factor: float
    overflow: bool = False


class AudioAligner:
    """Aligns TTS audio to target timeframes adhering to the 1.15x speed cap rule."""

    MAX_ATEMPO_CAP: float = 1.15  # Section 7 locked rule: atempo capped at 1.15x

    @classmethod
    def align_clip(
        cls,
        input_wav: Path | str,
        target_duration: float,
        output_wav: Path | str,
        token: CancellationToken | None = None,
    ) -> AlignedClipResult:
        """Align an individual TTS clip to target_duration."""
        if token:
            token.throw_if_cancelled()

        in_p = Path(input_wav).resolve()
        out_p = Path(output_wav).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        meta = MediaInspector.probe(in_p)
        actual_dur = meta.duration if meta.duration > 0 else 1.0
        dt_orig = max(0.2, target_duration)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        overflow = False
        speed_factor = 1.0

        if actual_dur > dt_orig:
            raw_ratio = actual_dur / dt_orig
            # Cap at 1.15x per locked specification
            speed_factor = min(cls.MAX_ATEMPO_CAP, raw_ratio)
            if raw_ratio > cls.MAX_ATEMPO_CAP:
                overflow = True

            # Use atempo filter in FFmpeg (or rubberband if supported)
            cmd = [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                to_safe_path(in_p),
                "-filter:a",
                f"atempo={speed_factor:.3f}",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "44100",
                to_safe_path(out_p),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg atempo alignment failed: {res.stderr}")
        else:
            # Pad with silence to match target_duration
            cmd = [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                to_safe_path(in_p),
                "-af",
                f"apad=whole_dur={dt_orig:.3f}",
                "-c:a",
                "pcm_s16le",
                "-ar",
                "44100",
                to_safe_path(out_p),
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode != 0:
                raise RuntimeError(f"FFmpeg apad alignment failed: {res.stderr}")

        meta_out = MediaInspector.probe(out_p)
        return AlignedClipResult(
            aligned_wav_path=out_p,
            original_duration=dt_orig,
            actual_duration=meta_out.duration,
            speed_factor=speed_factor,
            overflow=overflow,
        )

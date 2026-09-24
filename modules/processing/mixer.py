"""Audio Mixer module assembling dubbed dialogue and applying sidechain ducking to background music."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from core.cancellation import CancellationToken

logger = logging.getLogger(__name__)


class AudioMixer:
    """Combines speech dialogue clips at exact timestamps with sidechain-ducked background music."""

    @classmethod
    def assemble_dialogue_track(
        cls,
        clips: list[tuple[Path, float]],  # List of (clip_wav_path, start_seconds)
        total_duration: float,
        output_wav: Path | str,
        token: CancellationToken | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Place individual speech clips onto an empty timeline matching total_duration."""
        if token:
            token.throw_if_cancelled()
        if progress:
            progress(0.1, "Assembling dialogue track onto timeline...")

        out_p = Path(output_wav).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        if not clips:
            # Generate pure silence for total_duration
            cmd = [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=stereo",
                "-t",
                f"{total_duration:.3f}",
                "-c:a",
                "pcm_s16le",
                str(out_p),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            return out_p

        # Build FFmpeg command with adelay & amix
        cmd = ["ffmpeg", "-y", "-v", "error"]
        filter_inputs: list[str] = []

        for idx, (clip_path, start_s) in enumerate(clips):
            cmd.extend(["-i", str(clip_path)])
            delay_ms = int(round(start_s * 1000))
            filter_inputs.append(f"[{idx}:a]adelay={delay_ms}|{delay_ms}[a{idx}];")

        mix_inputs = "".join(f"[a{idx}]" for idx in range(len(clips)))
        filter_complex = "".join(filter_inputs) + f"{mix_inputs}amix=inputs={len(clips)}:dropout_transition=0:normalize=0[mixed]"

        cmd.extend([
            "-filter_complex",
            filter_complex,
            "-map",
            "[mixed]",
            "-t",
            f"{total_duration:.3f}",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            str(out_p),
        ])

        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        return out_p

    @classmethod
    def mix_master_audio(
        cls,
        dialogue_wav: Path | str,
        bgm_wav: Path | str,
        output_wav: Path | str,
        total_duration: float,
        ducking_threshold: float = 0.08,
        ducking_ratio: float = 4.0,
        token: CancellationToken | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Mix dialogue and background music using sidechaincompress ducking (Section 7 rule)."""
        if token:
            token.throw_if_cancelled()
        if progress:
            progress(0.4, "Applying sidechain compression ducking to BGM...")

        d_path = Path(dialogue_wav).resolve()
        b_path = Path(bgm_wav).resolve()
        out_p = Path(output_wav).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # [0:a] is BGM (main), [1:a] is Dialogue (sidechain key)
        # sidechaincompress ducks [0:a] when [1:a] is active
        filter_graph = (
            f"[0:a][1:a]sidechaincompress="
            f"threshold={ducking_threshold}:"
            f"ratio={ducking_ratio}:"
            f"attack=20:release=250[ducked_bgm];"
            f"[ducked_bgm][1:a]amix=inputs=2:dropout_transition=0:normalize=0[master]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(b_path),
            "-i",
            str(d_path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[master]",
            "-t",
            f"{total_duration:.3f}",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "44100",
            str(out_p),
        ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
        if progress:
            progress(1.0, "Master audio mix complete.")
        return out_p

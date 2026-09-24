"""Unit tests for SeparatorEngine stem separation."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError
from modules.ai.separator import SeparatorEngine, SeparatorInput


def _create_stereo_wav(path: Path, duration_sec: float = 2.0) -> None:
    """Helper to create a stereo 44.1kHz WAV with distinct center and sides."""
    sr = 44100
    t = np.linspace(0, duration_sec, int(duration_sec * sr), endpoint=False)
    # Center speech simulation (440Hz in both channels)
    center = 0.4 * np.sin(2 * np.pi * 440 * t)
    # Sides music simulation (1000Hz out of phase)
    side = 0.3 * np.sin(2 * np.pi * 1000 * t)

    left = center + side
    right = center - side

    stereo = np.column_stack((left, right))
    stereo_int = (np.clip(stereo, -1.0, 1.0) * 32767).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(stereo_int.tobytes())


def test_separator_probe_cpu_rule() -> None:
    """Verify SeparatorEngine probe adheres to Section 7 rule:
    htdemucs on CPU is disabled for performance; CPU uses MDX-Net ONNX.
    """
    engine = SeparatorEngine()
    avail = engine.probe()
    assert avail.is_usable
    # Ensure probe mentions CPU/MDX-Net
    assert "MDX-Net" in avail.reason or "FFmpeg" in avail.reason


def test_separator_run_generation(tmp_path: Path) -> None:
    """Verify SeparatorEngine outputs vocals.wav and no_vocals.wav stems."""
    audio_file = tmp_path / "mixed.wav"
    _create_stereo_wav(audio_file, duration_sec=1.5)

    engine = SeparatorEngine()
    token = CancellationToken()
    progress_calls: list[tuple[float, str]] = []

    inp = SeparatorInput(audio_path=audio_file, mode="auto")
    result = engine.run(
        inputs=inp,
        workdir=tmp_path,
        token=token,
        progress=lambda p, m: progress_calls.append((p, m)),
    )

    assert result.vocals_path.exists()
    assert result.no_vocals_path.exists()
    assert result.vocals_path.stat().st_size > 0
    assert result.no_vocals_path.stat().st_size > 0
    assert len(progress_calls) >= 2


def test_separator_cancellation(tmp_path: Path) -> None:
    """Verify SeparatorEngine halts when cancelled."""
    audio_file = tmp_path / "mixed.wav"
    _create_stereo_wav(audio_file, duration_sec=1.0)

    token = CancellationToken()
    token.cancel()

    engine = SeparatorEngine()
    inp = SeparatorInput(audio_path=audio_file)

    with pytest.raises(CancelledError):
        engine.run(
            inputs=inp,
            workdir=tmp_path,
            token=token,
            progress=lambda p, m: None,
        )

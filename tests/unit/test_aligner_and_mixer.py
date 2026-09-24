"""Unit tests for AudioAligner and AudioMixer."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

from modules.processing.aligner import AudioAligner
from modules.processing.mixer import AudioMixer


def _create_wav(path: Path, duration_s: float, freq: float = 440.0) -> None:
    sr = 44100
    t = np.linspace(0, duration_s, int(duration_s * sr), endpoint=False)
    sig = (0.5 * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(sig.tobytes())


def test_aligner_speed_cap_and_overflow(tmp_path: Path) -> None:
    """Verify atempo cap of 1.15x and overflow detection."""
    # Create 2.0s audio clip
    clip = tmp_path / "long_clip.wav"
    _create_wav(clip, 2.0)

    # Align to 1.0s target (needs 2.0x, but must be capped at 1.15x)
    out_wav = tmp_path / "aligned_capped.wav"
    res = AudioAligner.align_clip(clip, target_duration=1.0, output_wav=out_wav)

    assert res.overflow is True
    assert res.speed_factor == 1.15
    assert out_wav.exists()


def test_aligner_padding(tmp_path: Path) -> None:
    """Verify silence padding when clip is shorter than target."""
    clip = tmp_path / "short_clip.wav"
    _create_wav(clip, 0.5)

    out_wav = tmp_path / "aligned_padded.wav"
    res = AudioAligner.align_clip(clip, target_duration=1.5, output_wav=out_wav)

    assert res.overflow is False
    assert res.actual_duration >= 1.4  # Padded to ~1.5s


def test_mixer_dialogue_assembly(tmp_path: Path) -> None:
    """Verify timeline assembly of multiple clips."""
    c1 = tmp_path / "c1.wav"
    c2 = tmp_path / "c2.wav"
    _create_wav(c1, 0.5, 300.0)
    _create_wav(c2, 0.5, 600.0)

    clips = [(c1, 0.0), (c2, 1.0)]
    out_dialogue = tmp_path / "assembled.wav"

    AudioMixer.assemble_dialogue_track(clips, total_duration=2.0, output_wav=out_dialogue)
    assert out_dialogue.exists()
    assert out_dialogue.stat().st_size > 0

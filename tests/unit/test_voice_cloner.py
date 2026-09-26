"""Unit tests for RealVoiceCloner and neural speaker diarization."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from core.cancellation import CancellationToken
from modules.ai.diarizer import DiarizerEngine, DiarizerInput
from modules.ai.engine import Transcript, TranscriptSegment
from modules.ai.voice_cloner import RealVoiceCloner
from modules.ai.voice_generator import VoiceGenerator


def _make_test_sine_wav(path: Path, freq: float, duration: float = 1.0, sr: int = 16000) -> Path:
    """Generate simple synthetic wav file for testing."""
    p = Path(path).resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, duration, int(duration * sr), endpoint=False)
    samples = 0.5 * np.sin(2 * np.pi * freq * t)
    int_samples = (samples * 32767.0).astype(np.int16)
    with wave.open(str(p), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_samples.tobytes())
    return p


def test_real_voice_cloner_singleton_and_availability() -> None:
    """Verify RealVoiceCloner singleton returns available inference session."""
    cloner = RealVoiceCloner.get_instance()
    assert cloner is not None
    assert cloner.is_available is True


def test_extract_speaker_embedding_shape_and_norm(tmp_path: Path) -> None:
    """Verify speaker embedding extraction returns 256-dim unit vector."""
    cloner = RealVoiceCloner.get_instance()
    wav = _make_test_sine_wav(tmp_path / "test_tone.wav", freq=220.0, duration=1.0)
    emb = cloner.extract_speaker_embedding(wav)
    assert emb.shape == (256,)
    assert abs(np.linalg.norm(emb) - 1.0) < 1e-4


def test_clone_voice_execution(tmp_path: Path) -> None:
    """Verify clone_voice transforms base audio conditioned on reference audio."""
    cloner = RealVoiceCloner.get_instance()
    ref_wav = _make_test_sine_wav(tmp_path / "ref_actor.wav", freq=180.0, duration=1.5)
    base_wav = _make_test_sine_wav(tmp_path / "base_speech.wav", freq=220.0, duration=1.0)
    out_wav = tmp_path / "cloned_out.wav"

    res_path = cloner.clone_voice(base_wav, ref_wav, out_wav, tau=0.9)
    assert res_path.exists()
    assert res_path.stat().st_size > 1000

    with wave.open(str(res_path), "rb") as wf:
        assert wf.getframerate() == 44100
        assert wf.getnchannels() == 1
        assert wf.getnframes() > 1000


def test_diarizer_with_neural_cloner(tmp_path: Path) -> None:
    """Verify DiarizerEngine executes with neural embeddings active."""
    wav_path = tmp_path / "dialogue.wav"
    sr = 16000
    # Two alternating segments
    t1 = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
    s1 = (0.5 * np.sin(2 * np.pi * 180.0 * t1) * 32767.0).astype(np.int16)
    t2 = np.linspace(0, 1.5, int(1.5 * sr), endpoint=False)
    s2 = (0.5 * np.sin(2 * np.pi * 350.0 * t2) * 32767.0).astype(np.int16)
    full_audio = np.concatenate([s1, s2, s1, s2])

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(full_audio.tobytes())

    transcript = Transcript(
        segments=[
            TranscriptSegment(id=1, start=0.0, end=1.5, source_text="Line 1"),
            TranscriptSegment(id=2, start=1.5, end=3.0, source_text="Line 2"),
            TranscriptSegment(id=3, start=3.0, end=4.5, source_text="Line 3"),
            TranscriptSegment(id=4, start=4.5, end=6.0, source_text="Line 4"),
        ],
        duration=6.0,
    )

    engine = DiarizerEngine()
    result = engine.run(
        DiarizerInput(audio_path=wav_path, transcript=transcript, num_speakers=2),
        workdir=tmp_path / "work",
        token=CancellationToken(),
        progress=lambda p, m: None,
    )

    speakers = [s.speaker for s in result.segments]
    # Check that alternating segments are distinguished
    assert len(set(speakers)) == 2
    assert speakers[0] == speakers[2]
    assert speakers[1] == speakers[3]
    assert speakers[0] != speakers[1]

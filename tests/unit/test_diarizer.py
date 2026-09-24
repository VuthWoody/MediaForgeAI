"""Unit tests for DiarizerEngine verifying multi-speaker clustering."""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np
import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError
from modules.ai.diarizer import DiarizerEngine, DiarizerInput
from modules.ai.engine import Transcript, TranscriptSegment


def _create_synthetic_wav(path: Path, segments: list[tuple[float, float, float]]) -> None:
    """Helper to create a synthetic 16kHz mono WAV file with varying tones for testing."""
    sr = 16000
    total_duration = max(end for _, end, _ in segments)
    total_samples = int(total_duration * sr)
    audio = np.zeros(total_samples, dtype=np.float32)

    for start_s, end_s, freq in segments:
        s_idx = int(start_s * sr)
        e_idx = int(end_s * sr)
        t = np.linspace(0, end_s - start_s, e_idx - s_idx, endpoint=False)
        audio[s_idx:e_idx] = 0.5 * np.sin(2 * np.pi * freq * t)

    int_audio = (audio * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int_audio.tobytes())


def test_diarizer_probe() -> None:
    """Verify DiarizerEngine probe returns ready."""
    engine = DiarizerEngine()
    avail = engine.probe()
    assert avail.status == "ready"


def test_diarizer_two_speaker_clustering(tmp_path: Path) -> None:
    """Verify DiarizerEngine successfully distinguishes two alternating speakers."""
    wav_path = tmp_path / "two_speakers.wav"
    # Speaker 1: Low frequency 200Hz; Speaker 2: High frequency 1000Hz
    _create_synthetic_wav(
        wav_path,
        [
            (0.0, 1.5, 200.0),   # Speaker 1
            (1.6, 3.0, 1000.0),  # Speaker 2
            (3.1, 4.5, 200.0),   # Speaker 1
            (4.6, 6.0, 1000.0),  # Speaker 2
        ],
    )

    transcript = Transcript(
        segments=[
            TranscriptSegment(id=1, start=0.0, end=1.5, source_text="Speaker one line 1"),
            TranscriptSegment(id=2, start=1.6, end=3.0, source_text="Speaker two line 1"),
            TranscriptSegment(id=3, start=3.1, end=4.5, source_text="Speaker one line 2"),
            TranscriptSegment(id=4, start=4.6, end=6.0, source_text="Speaker two line 2"),
        ],
        duration=6.0,
    )

    engine = DiarizerEngine()
    token = CancellationToken()
    inp = DiarizerInput(
        audio_path=wav_path,
        transcript=transcript,
        num_speakers=2,
    )

    result = engine.run(
        inputs=inp,
        workdir=tmp_path,
        token=token,
        progress=lambda p, m: None,
    )

    assert len(result.segments) == 4
    # Segments 1 and 3 should share a speaker, segments 2 and 4 should share a different speaker
    spk_1 = result.segments[0].speaker
    spk_2 = result.segments[1].speaker
    spk_3 = result.segments[2].speaker
    spk_4 = result.segments[3].speaker

    assert spk_1 != spk_2
    assert spk_1 == spk_3
    assert spk_2 == spk_4
    assert (tmp_path / "diarized_transcript.json").exists()


def test_diarizer_cancellation(tmp_path: Path) -> None:
    """Verify DiarizerEngine respects cancellation tokens."""
    wav_path = tmp_path / "test.wav"
    _create_synthetic_wav(wav_path, [(0.0, 1.0, 440.0)])

    transcript = Transcript(
        segments=[TranscriptSegment(id=1, start=0.0, end=1.0, source_text="Hi")],
    )

    token = CancellationToken()
    token.cancel()

    engine = DiarizerEngine()
    inp = DiarizerInput(audio_path=wav_path, transcript=transcript)

    with pytest.raises(CancelledError):
        engine.run(
            inputs=inp,
            workdir=tmp_path,
            token=token,
            progress=lambda p, m: None,
        )


def test_diarizer_f0_pitch_estimation() -> None:
    """Verify DiarizerEngine autocorrelation correctly estimates pitch for male and female frequencies."""
    engine = DiarizerEngine()
    sr = 16000
    t = np.linspace(0, 0.5, int(0.5 * sr), endpoint=False)

    # 120 Hz tone (male register)
    male_wave = 0.5 * np.sin(2 * np.pi * 120.0 * t).astype(np.float32)
    f0_male, voiced_male = engine._estimate_f0(male_wave, sr)
    assert 110.0 <= f0_male <= 130.0
    assert voiced_male > 0.7

    # 220 Hz tone (female register)
    female_wave = 0.5 * np.sin(2 * np.pi * 220.0 * t).astype(np.float32)
    f0_female, voiced_female = engine._estimate_f0(female_wave, sr)
    assert 210.0 <= f0_female <= 230.0
    assert voiced_female > 0.7

    prof_male = engine._classify_voice_profile(f0_male, 1200.0)
    prof_female = engine._classify_voice_profile(f0_female, 2100.0)
    prof_child = engine._classify_voice_profile(300.0, 2800.0)
    assert "Male" in prof_male
    assert "Female" in prof_female
    assert prof_child == "Child"


def test_diarizer_power_multi_speaker_and_character_mapping(tmp_path: Path) -> None:
    """Verify Power Voice Separator separates 3 distinct voices (male, female, child) and maps characters."""
    wav_path = tmp_path / "three_speakers.wav"
    _create_synthetic_wav(
        wav_path,
        [
            (0.0, 1.2, 120.0),   # Male voice (120Hz)
            (1.3, 2.5, 220.0),   # Female voice (220Hz)
            (2.6, 3.8, 320.0),   # Child voice (320Hz)
            (3.9, 5.0, 120.0),   # Male voice again
        ],
    )

    transcript = Transcript(
        segments=[
            TranscriptSegment(id=1, start=0.0, end=1.2, source_text="Male line 1"),
            TranscriptSegment(id=2, start=1.3, end=2.5, source_text="Female line 1"),
            TranscriptSegment(id=3, start=2.6, end=3.8, source_text="Child line 1"),
            TranscriptSegment(id=4, start=3.9, end=5.0, source_text="Male line 2"),
        ],
        duration=5.0,
    )

    engine = DiarizerEngine()
    characters = [
        {"actor": "黄思宇", "character": "林清言"},
        {"actor": "李小风", "character": "赵明宇"},
        {"actor": "童童", "character": "小宝"},
    ]

    inp = DiarizerInput(
        audio_path=wav_path,
        transcript=transcript,
        num_speakers=3,
        characters=characters,
    )

    result = engine.run(
        inputs=inp,
        workdir=tmp_path,
        token=CancellationToken(),
        progress=lambda p, m: None,
    )

    assert len(result.segments) == 4
    spk_1 = result.segments[0].speaker
    spk_2 = result.segments[1].speaker
    spk_3 = result.segments[2].speaker
    spk_4 = result.segments[3].speaker

    # Segments 1 and 4 are the same speaker (male)
    assert spk_1 == spk_4
    # All 3 different speakers have distinct tags
    assert spk_1 != spk_2
    assert spk_2 != spk_3
    assert spk_1 != spk_3

    # Characters are mapped into speaker labels
    assert "林清言" in spk_1 or "赵明宇" in spk_1 or "小宝" in spk_1
    assert "Speaker 1" in spk_1
    assert "Speaker 2" in spk_2
    assert "Speaker 3" in spk_3

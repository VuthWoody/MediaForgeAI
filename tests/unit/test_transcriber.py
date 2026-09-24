"""Unit tests for TranscriberEngine conforming to the Section 7 schema and cancellation contract."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError
from modules.ai.engine import Transcript, TranscriptSegment
from modules.ai.transcriber import TranscriberEngine, TranscriberInput


def test_transcript_segment_schema_and_serialization() -> None:
    """Verify TranscriptSegment serializes to the exact Section 7 JSON schema."""
    seg = TranscriptSegment(
        id=1,
        start=1.250,
        end=3.800,
        speaker="Speaker 1",
        source_text="Test transcription line",
        target_text="Translated line",
        voice_id="v_01",
        audio_path="/path/to/stem.wav",
        confidence=0.9234,
    )
    d = seg.to_dict()

    assert d["id"] == 1
    assert d["start"] == 1.25
    assert d["end"] == 3.8
    assert d["speaker"] == "Speaker 1"
    assert d["source_text"] == "Test transcription line"
    assert d["target_text"] == "Translated line"
    assert d["confidence"] == 0.9234

    # Test roundtrip
    restored = TranscriptSegment.from_dict(d)
    assert restored.id == seg.id
    assert restored.start == seg.start
    assert restored.source_text == seg.source_text


def test_transcript_save_and_load(tmp_path: Path) -> None:
    """Verify Transcript saves and loads formatted JSON correctly."""
    segments = [
        TranscriptSegment(id=1, start=0.0, end=2.0, source_text="First line"),
        TranscriptSegment(id=2, start=2.1, end=4.5, source_text="Second line"),
    ]
    t = Transcript(segments=segments, language="zh", duration=4.5)
    out_file = tmp_path / "test_transcript.json"
    t.save_json(out_file)

    assert out_file.exists()
    loaded = Transcript.load_json(out_file)
    assert len(loaded.segments) == 2
    assert loaded.segments[0].source_text == "First line"
    assert loaded.segments[1].source_text == "Second line"


def test_transcriber_probe() -> None:
    """Verify TranscriberEngine probe returns usable status."""
    engine = TranscriberEngine()
    avail = engine.probe()
    assert avail.status in ("ready", "degraded", "unavailable")


def test_transcriber_run_mocked(tmp_path: Path) -> None:
    """Verify TranscriberEngine runs and outputs formatted Transcript."""
    engine = TranscriberEngine()

    dummy_audio = tmp_path / "test.wav"
    dummy_audio.write_bytes(b"dummy wav data")

    # Mock FFmpeg conversion and WhisperModel
    mock_seg = MagicMock()
    mock_seg.start = 1.0
    mock_seg.end = 2.5
    mock_seg.text = " Hello World "
    mock_seg.avg_logprob = -0.1

    mock_model = MagicMock()
    mock_model.transcribe.return_value = ([mock_seg], MagicMock(language="en"))

    with (
        patch.object(engine, "_prepare_16k_mono_audio", return_value=3.0),
        patch.object(engine, "_get_whisper_model", return_value=mock_model),
    ):
        inp = TranscriberInput(audio_path=dummy_audio, model_size="small")
        token = CancellationToken()
        progress_calls: list[tuple[float, str]] = []

        result = engine.run(
            inputs=inp,
            workdir=tmp_path,
            token=token,
            progress=lambda p, m: progress_calls.append((p, m)),
        )

        assert len(result.segments) == 1
        assert result.segments[0].source_text == "Hello World"
        assert result.segments[0].speaker == "Speaker 1"
        assert result.segments[0].confidence > 0.0
        assert (tmp_path / "transcript.json").exists()
        assert len(progress_calls) >= 2


def test_transcriber_cancellation(tmp_path: Path) -> None:
    """Verify TranscriberEngine halts immediately on cancellation."""
    engine = TranscriberEngine()
    dummy_audio = tmp_path / "test.wav"
    dummy_audio.write_bytes(b"dummy")

    token = CancellationToken()
    token.cancel()

    inp = TranscriberInput(audio_path=dummy_audio)
    with pytest.raises(CancelledError):
        engine.run(
            inputs=inp,
            workdir=tmp_path,
            token=token,
            progress=lambda p, m: None,
        )

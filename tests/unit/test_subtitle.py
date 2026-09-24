"""Unit tests for subtitle export, styling, and multiplexing."""

from __future__ import annotations

from pathlib import Path

from modules.ai.engine import Transcript, TranscriptSegment
from modules.processing.subtitle import SubtitleManager, SubtitleStyle


def test_srt_export(tmp_path: Path) -> None:
    """Verify SRT output syntax and timestamps."""
    segments = [
        TranscriptSegment(id=1, start=0.5, end=2.75, source_text="Hello world", speaker="Speaker 1"),
        TranscriptSegment(id=2, start=3.0, end=5.2, source_text="MediaForge AI", speaker="Speaker 2"),
    ]
    t = Transcript(segments=segments)
    out_srt = tmp_path / "test.srt"
    SubtitleManager.export_srt(t, out_srt, include_speaker=True)

    assert out_srt.exists()
    content = out_srt.read_text(encoding="utf-8")
    assert "00:00:00,500 --> 00:00:02,750" in content
    assert "[Speaker 1] Hello world" in content
    assert "00:00:03,000 --> 00:00:05,200" in content
    assert "[Speaker 2] MediaForge AI" in content


def test_vtt_export(tmp_path: Path) -> None:
    """Verify WebVTT output syntax."""
    segments = [
        TranscriptSegment(id=1, start=1.0, end=3.5, source_text="WebVTT line"),
    ]
    out_vtt = tmp_path / "test.vtt"
    SubtitleManager.export_vtt(segments, out_vtt)

    content = out_vtt.read_text(encoding="utf-8")
    assert content.startswith("WEBVTT")
    assert "00:00:01.000 --> 00:00:03.500" in content
    assert "WebVTT line" in content


def test_ass_export(tmp_path: Path) -> None:
    """Verify ASS export with custom styling headers."""
    segments = [
        TranscriptSegment(id=1, start=1.25, end=3.75, source_text="Multi\nline dialogue"),
    ]
    style = SubtitleStyle(font_name="Noto Sans Khmer", font_size=28, bold=True)
    out_ass = tmp_path / "test.ass"
    SubtitleManager.export_ass(segments, out_ass, style=style)

    content = out_ass.read_text(encoding="utf-8")
    assert "[Script Info]" in content
    assert "[V4+ Styles]" in content
    assert "Noto Sans Khmer,28" in content
    assert "Dialogue: 0,0:00:01.25,0:00:03.75,Default,,0,0,0,,Multi\\Nline dialogue" in content

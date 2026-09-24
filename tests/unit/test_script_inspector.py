"""Unit tests for ScriptInspectorWidget, Dialog, and tone classification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from modules.ai.engine import Transcript, TranscriptSegment, classify_segment_tone
from ui.views.script_inspector import ScriptInspectorDialog, ScriptInspectorWidget


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_classify_segment_tone_rules() -> None:
    """Verify classify_segment_tone detects correct emotions from text and acoustic cues."""
    # 1. Excited / Happy
    assert classify_segment_tone("Oh my god, Emma, I am good!") == "[excited]"
    assert classify_segment_tone("This is amazing!") == "[excited]"
    assert classify_segment_tone("Great. Take the seat. This seat is empty.") == "[happy]"
    assert classify_segment_tone("I am so glad to see you.") == "[happy]"

    # 2. Sad / Cry
    assert classify_segment_tone("I am so sorry, I miss you so much.") == "[sad]"
    assert classify_segment_tone("She was crying and sobbing in the corner.") == "[cry]"

    # 3. Angry / Whisper
    assert classify_segment_tone("Shut up! I hate this so much.") == "[angry]"
    assert classify_segment_tone("Please whisper, it's a secret.") == "[whisper]"

    # 4. Normal
    assert classify_segment_tone("English Conversation Between Two Friends") == "[normal]"
    assert classify_segment_tone("Hey James, how are you?") == "[normal]"


def test_script_inspector_load_and_filter(qapp: QApplication) -> None:
    """Verify ScriptInspectorWidget populates table rows and filters correctly."""
    widget = ScriptInspectorWidget()

    segments = [
        TranscriptSegment(
            id=1,
            start=9.92,
            end=12.62,
            speaker="Speaker 1: Narrator",
            source_text="English Conversation Between Two Friends",
            target_text="ការសន្ទនាភាសាអង់គ្លេសរវាងមិត្តពីរនាក់",
            emotion="normal",
        ),
        TranscriptSegment(
            id=2,
            start=15.14,
            end=17.42,
            speaker="Speaker 2: Emma (Female)",
            source_text="Hey James, how are you?",
            target_text="ហេ James សុខសប្បាយជាទេ?",
            emotion="normal",
        ),
        TranscriptSegment(
            id=3,
            start=18.28,
            end=21.96,
            speaker="Speaker 3: James (Male)",
            source_text="Oh my god, Emma, I am good. How are you?",
            target_text="ឱព្រះជាម្ចាស់អើយ អិមម៉ា ខ្ញុំសុខសប្បាយជាទេ។ ចុះអ្នកសុខសប្បាយជាទេ?",
            emotion="excited",
        ),
    ]
    tr = Transcript(segments=segments, language="km", duration=22.0)

    widget.load_transcript(tr)

    assert widget.table.rowCount() == 3
    # Verify columns
    assert widget.table.item(0, 0).text() == "1"
    assert "00:09.92" in widget.table.item(0, 1).text()
    assert "Narrator" in widget.table.item(0, 2).text()
    assert widget.table.item(0, 3).text() == "[normal]"
    assert widget.table.item(0, 4).text() == "English Conversation Between Two Friends"
    assert "ការសន្ទនា" in widget.table.item(0, 5).text()

    assert widget.table.item(2, 3).text() == "[excited]"

    # Test search filter
    widget.search_input.setText("Emma")
    visible_rows = [r for r in range(3) if not widget.table.isRowHidden(r)]
    # Rows 1 and 2 mention Emma (either speaker or text)
    assert 1 in visible_rows
    assert 2 in visible_rows
    assert 0 not in visible_rows

    # Reset search filter
    widget.search_input.setText("")
    assert all(not widget.table.isRowHidden(r) for r in range(3))

    # Test tone filter
    idx = widget.tone_filter.findData("[excited]")
    widget.tone_filter.setCurrentIndex(idx)
    assert not widget.table.isRowHidden(2)
    assert widget.table.isRowHidden(0)
    assert widget.table.isRowHidden(1)


def test_script_inspector_seek_signal(qapp: QApplication) -> None:
    """Verify clicking table item emits seek_requested signal."""
    widget = ScriptInspectorWidget()
    segments = [
        TranscriptSegment(id=1, start=10.5, end=15.0, source_text="Hello", target_text="Hi"),
    ]
    widget.load_transcript(Transcript(segments=segments))

    received_ms: list[int] = []
    widget.seek_requested.connect(lambda ms: received_ms.append(ms))

    item = widget.table.item(0, 1)
    assert item is not None
    widget._on_table_item_clicked(item)

    assert len(received_ms) == 1
    assert received_ms[0] == 10500


def test_script_inspector_save_edits(qapp: QApplication, tmp_path: Path) -> None:
    """Verify editing translation in table and saving writes back to JSON."""
    json_file = tmp_path / "translated_km.json"
    segments = [
        TranscriptSegment(id=1, start=0.0, end=2.0, source_text="Hello", target_text="Old translation"),
    ]
    tr = Transcript(segments=segments)
    tr.save_json(json_file)

    widget = ScriptInspectorWidget()
    widget.load_transcript(tr, json_file)

    # Edit translation item in table
    trans_item = widget.table.item(0, 5)
    assert trans_item is not None
    trans_item.setText("Updated translation text")

    updated_events: list[Transcript] = []
    widget.transcript_updated.connect(lambda t: updated_events.append(t))

    widget.save_edits(show_dialog=False)

    assert len(updated_events) == 1
    assert updated_events[0].segments[0].target_text == "Updated translation text"

    # Verify saved file on disk
    reloaded = Transcript.load_json(json_file)
    assert reloaded.segments[0].target_text == "Updated translation text"


def test_script_inspector_dialog(qapp: QApplication) -> None:
    """Verify ScriptInspectorDialog instantiates and houses the inspector widget."""
    dialog = ScriptInspectorDialog()
    assert dialog.inspector is not None
    assert dialog.windowTitle() == "MediaForge AI — Speech & Translation Inspector"
    dialog.close()


def test_script_inspector_replace_sentence_and_all(qapp: QApplication, tmp_path: Path) -> None:
    """Verify single sentence and replace-all in editor emit correct signals and invalidate clips."""
    json_file = tmp_path / "translated_km.json"
    tts_dir = tmp_path / "tts_clips"
    tts_dir.mkdir(parents=True)
    fake_clip_1 = tts_dir / "tts_0000_1.wav"
    fake_clip_2 = tts_dir / "tts_0001_2.wav"
    fake_clip_1.write_bytes(b"RIFF")
    fake_clip_2.write_bytes(b"RIFF")

    segments = [
        TranscriptSegment(id=1, start=0.0, end=2.0, source_text="Hello", target_text="Old 1"),
        TranscriptSegment(id=2, start=3.0, end=5.0, source_text="World", target_text="Old 2"),
    ]
    tr = Transcript(segments=segments)
    tr.save_json(json_file)

    widget = ScriptInspectorWidget()
    widget.load_transcript(tr, json_file)

    # 1. Edit row 0 translation & timestamp in table
    trans_item_0 = widget.table.item(0, 5)
    time_item_0 = widget.table.item(0, 1)
    assert trans_item_0 is not None
    assert time_item_0 is not None

    trans_item_0.setText("New Translation 1")
    time_item_0.setText("00:00.50 → 00:02.80 (2.3s)")

    replaced_segs: list[TranscriptSegment] = []
    widget.segment_replaced.connect(lambda s: replaced_segs.append(s))

    # Click Replace button in row 0
    replace_btn_0 = widget.table.cellWidget(0, 7)
    assert replace_btn_0 is not None
    widget._replace_sentence_in_editor(0, replace_btn_0)

    assert len(replaced_segs) == 1
    assert replaced_segs[0].id == 1
    assert replaced_segs[0].target_text == "New Translation 1"
    assert replaced_segs[0].start == 0.5
    assert replaced_segs[0].end == 2.8

    # Verify stale fake_clip_1 was deleted but fake_clip_2 remains
    assert not fake_clip_1.exists()
    assert fake_clip_2.exists()

    # 2. Test Replace All
    trans_item_1 = widget.table.item(1, 5)
    assert trans_item_1 is not None
    trans_item_1.setText("New Translation 2")

    all_replaced_events: list[Transcript] = []
    widget.replace_all_requested.connect(lambda t: all_replaced_events.append(t))

    widget.replace_all_in_editor()

    assert len(all_replaced_events) == 1
    assert all_replaced_events[0].segments[0].target_text == "New Translation 1"
    assert all_replaced_events[0].segments[1].target_text == "New Translation 2"
    assert not fake_clip_2.exists()


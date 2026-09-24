"""Unit tests for MultiTrackTimelineWidget (Phase 9)."""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ui.components.timeline import MultiTrackTimelineWidget


def test_timeline_initialization(qapp: QApplication) -> None:
    timeline = MultiTrackTimelineWidget()
    assert len(timeline.canvas.tracks) == 5
    track_ids = [t.id for t in timeline.canvas.tracks]
    assert track_ids == ["video", "orig_audio", "bgm", "dialogue", "subtitles"]
    assert timeline.canvas.duration_ms == 60000


def test_timeline_mute_and_solo(qapp: QApplication) -> None:
    from modules.media.player_controller import PlayerController
    ctrl = PlayerController()
    timeline = MultiTrackTimelineWidget(player_controller=ctrl)

    # 1. Canvas direct
    timeline.canvas.set_track_mute("video", True)
    assert timeline.canvas.tracks[0].muted is True

    timeline.canvas.set_track_solo("dialogue", True)
    assert timeline.canvas.tracks[3].solo is True

    # 2. Widget UI button interactions and controller propagation
    timeline._mute_buttons["orig_audio"].setChecked(True)
    assert ctrl.is_track_muted("orig_audio") is True
    assert timeline.canvas.tracks[1].muted is True

    timeline._solo_buttons["bgm"].setChecked(True)
    assert ctrl.is_track_soloed("bgm") is True
    assert timeline.canvas.tracks[2].solo is True

    # 3. Controller to Timeline UI sync
    ctrl.set_track_mute("video", False)
    assert not timeline._mute_buttons["video"].isChecked()
    assert timeline.canvas.tracks[0].muted is False


def test_timeline_load_transcript_clips(qapp: QApplication) -> None:
    timeline = MultiTrackTimelineWidget()
    sample_segments = [
        {"id": 1, "start": 0.5, "end": 2.5, "speaker": "Speaker 1", "source_text": "Hello world", "target_text": "ជំរាបសួរ"},
        {"id": 2, "start": 3.0, "end": 5.0, "speaker": "Speaker 2", "source_text": "Goodbye", "target_text": "លាហើយ"},
    ]
    timeline.load_transcript_clips(sample_segments)

    # Check Dialogue track
    dlg_track = next(t for t in timeline.canvas.tracks if t.id == "dialogue")
    assert len(dlg_track.clips) == 2
    assert dlg_track.clips[0].start_ms == 500
    assert dlg_track.clips[0].end_ms == 2500
    assert dlg_track.clips[0].label == "ជំរាបសួរ"

    # Check Subtitle track
    sub_track = next(t for t in timeline.canvas.tracks if t.id == "subtitles")
    assert len(sub_track.clips) == 2
    assert sub_track.clips[1].label == "លាហើយ"


def test_timeline_update_segment_clip(qapp: QApplication) -> None:
    """Verify update_segment_clip updates both dialogue and subtitle tracks."""
    timeline = MultiTrackTimelineWidget()
    sample_segments = [
        {"id": 1, "start": 1.0, "end": 3.0, "speaker": "Speaker 1", "source_text": "One", "target_text": "មួយ"},
    ]
    timeline.load_transcript_clips(sample_segments)

    # Update segment 1 to new translation and new timestamps
    timeline.update_segment_clip(
        seg_id=1,
        label="មួយ - កែប្រែ",
        start_ms=1500,
        end_ms=4500,
        speaker="Speaker 2",
    )

    dlg_track = next(t for t in timeline.canvas.tracks if t.id == "dialogue")
    sub_track = next(t for t in timeline.canvas.tracks if t.id == "subtitles")

    assert dlg_track.clips[0].label == "មួយ - កែប្រែ"
    assert dlg_track.clips[0].start_ms == 1500
    assert dlg_track.clips[0].end_ms == 4500
    assert dlg_track.clips[0].speaker == "Speaker 2"

    assert sub_track.clips[0].label == "មួយ - កែប្រែ"
    assert sub_track.clips[0].start_ms == 1500
    assert sub_track.clips[0].end_ms == 4500


def test_timeline_seek_and_zoom(qapp: QApplication) -> None:
    timeline = MultiTrackTimelineWidget()
    initial_zoom = timeline.canvas.pixels_per_second

    timeline._zoom_in()
    assert timeline.canvas.pixels_per_second > initial_zoom

    timeline._zoom_out()
    assert timeline.canvas.pixels_per_second == initial_zoom

    # Test seek
    seek_received: list[int] = []
    timeline.canvas.seek_requested.connect(seek_received.append)
    timeline.canvas.seek_requested.emit(5000)
    assert timeline.canvas.position_ms == 5000
    assert seek_received == [5000]

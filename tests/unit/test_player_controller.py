"""Unit tests for PlayerController, SRT parsing, frame stepping calculations, and subtitle tolerance."""

from __future__ import annotations

from pathlib import Path

from modules.media.inspector import MediaMetadata
from modules.media.player_controller import PlayerController, parse_srt_file
from ui.components.video_player import format_timecode


def test_parse_srt_file(tmp_path: Path) -> None:
    srt_content = """1
00:00:01,000 --> 00:00:03,500
Hello World!

2
00:00:04,200 --> 00:00:06,800
Second subtitle line
With multiple rows
"""
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(srt_content, encoding="utf-8")

    segments = parse_srt_file(srt_file)
    assert len(segments) == 2

    assert segments[0].index == 1
    assert segments[0].start_ms == 1000
    assert segments[0].end_ms == 3500
    assert segments[0].text == "Hello World!"

    assert segments[1].index == 2
    assert segments[1].start_ms == 4200
    assert segments[1].end_ms == 6800
    assert "With multiple rows" in segments[1].text


def test_subtitle_one_frame_tolerance(tmp_path: Path) -> None:
    """Verify Section 7 Phase 3 rule: 'SRT overlay tracks playback within +/- 1 frame.'"""
    controller = PlayerController()
    controller.metadata = MediaMetadata(
        file_path="test.mp4",
        file_size=1000,
        mtime=0.0,
        format_name="mp4",
        duration=10.0,
        bitrate=1000,
        width=1920,
        height=1080,
        fps=30.0,  # 1 frame = ~33.3ms
        total_frames=300,
        video_codec="h264",
        pix_fmt="yuv420p",
        aspect_ratio="16:9",
        has_audio=True,
        audio_codec="aac",
        sample_rate=44100,
        channels=2,
        audio_bitrate=128000,
    )

    srt_content = """1
00:00:01,000 --> 00:00:03,000
Target Subtitle
"""
    srt_file = tmp_path / "test.srt"
    srt_file.write_text(srt_content, encoding="utf-8")
    controller.load_subtitles(srt_file)

    frame_ms = int(1000.0 / 30.0)  # 33 ms

    # Within interval
    controller._update_subtitle(1500)
    assert controller._current_sub_text == "Target Subtitle"

    # Exactly 1 frame BEFORE start (1000 - 33 = 967ms): should still match within tolerance
    controller._update_subtitle(1000 - frame_ms)
    assert controller._current_sub_text == "Target Subtitle"

    # Beyond 1 frame before start (900ms): should be empty
    controller._update_subtitle(900)
    assert controller._current_sub_text == ""

    # Exactly 1 frame AFTER end (3000 + 33 = 3033ms): should still match within tolerance
    controller._update_subtitle(3000 + frame_ms)
    assert controller._current_sub_text == "Target Subtitle"

    # Beyond 1 frame after end (3100ms): should be empty
    controller._update_subtitle(3100)
    assert controller._current_sub_text == ""


def test_format_timecode() -> None:
    assert format_timecode(0, 30.0) == "00:00:00:00"
    # 1.5 seconds at 30 fps = 1 sec + 15 frames
    assert format_timecode(1500, 30.0) == "00:00:01:15"
    # 65.0 seconds at 25 fps = 1 min + 5 sec + 0 frames
    assert format_timecode(65000, 25.0) == "00:01:05:00"


def test_player_controller_mute_solo_and_stems(tmp_path: Path) -> None:
    ctrl = PlayerController()

    # Track default states
    assert not ctrl.is_track_muted("video")
    assert not ctrl.is_track_soloed("video")
    assert not ctrl.is_track_muted("orig_audio")

    # Mute video and check signal
    video_vis: list[bool] = []
    ctrl.video_visibility_changed.connect(video_vis.append)
    ctrl.set_track_mute("video", True)
    assert ctrl.is_track_muted("video")
    assert video_vis == [False]

    ctrl.set_track_mute("video", False)
    assert not ctrl.is_track_muted("video")
    assert video_vis == [False, True]

    # Create dummy wav files for stems
    stem1 = tmp_path / "orig.wav"
    stem2 = tmp_path / "bgm.wav"
    stem3 = tmp_path / "dlg.wav"
    stem1.write_bytes(b"RIFFdummyWAVEfmt ")
    stem2.write_bytes(b"RIFFdummyWAVEfmt ")
    stem3.write_bytes(b"RIFFdummyWAVEfmt ")

    ctrl.load_stems({"orig_audio": stem1, "bgm": stem2, "dialogue": stem3})
    assert len(ctrl._stems) == 3

    # Default: master volume 1.0, all unmuted -> all stems unmuted
    assert not ctrl._stems["orig_audio"][1].isMuted()
    assert not ctrl._stems["bgm"][1].isMuted()
    assert not ctrl._stems["dialogue"][1].isMuted()

    # Mute orig_audio -> orig_audio muted, others stay unmuted
    ctrl.set_track_mute("orig_audio", True)
    assert ctrl._stems["orig_audio"][1].isMuted()
    assert not ctrl._stems["bgm"][1].isMuted()
    assert not ctrl._stems["dialogue"][1].isMuted()

    # Solo dialogue -> dialogue unmuted, bgm & orig_audio muted
    ctrl.set_track_solo("dialogue", True)
    assert not ctrl._stems["dialogue"][1].isMuted()
    assert ctrl._stems["bgm"][1].isMuted()
    assert ctrl._stems["orig_audio"][1].isMuted()

    # Unsolo dialogue
    ctrl.set_track_solo("dialogue", False)
    assert not ctrl._stems["dialogue"][1].isMuted()
    assert not ctrl._stems["bgm"][1].isMuted()
    assert ctrl._stems["orig_audio"][1].isMuted()

    # Clear stems
    ctrl.clear_stems()
    assert len(ctrl._stems) == 0

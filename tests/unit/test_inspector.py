"""Unit tests for MediaInspector and MediaMetadata."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from modules.media.inspector import MediaInspector, MediaMetadata, parse_fps


def test_parse_fps() -> None:
    assert parse_fps("30/1") == 30.0
    assert abs(parse_fps("30000/1001") - 29.970029) < 0.001
    assert abs(parse_fps("24000/1001") - 23.976023) < 0.001
    assert parse_fps("60") == 60.0
    assert parse_fps("0/0") == 30.0
    assert parse_fps("invalid") == 30.0


def test_media_metadata_serialization() -> None:
    meta = MediaMetadata(
        file_path="C:/test/sample.mp4",
        file_size=1024000,
        mtime=1700000000.0,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
        duration=125.4,
        bitrate=2500000,
        width=1920,
        height=1080,
        fps=29.97,
        total_frames=3758,
        video_codec="h264",
        pix_fmt="yuv420p",
        aspect_ratio="16:9",
        has_audio=True,
        audio_codec="aac",
        sample_rate=48000,
        channels=2,
        audio_bitrate=192000,
    )

    d = meta.to_dict()
    assert d["width"] == 1920
    assert d["video_codec"] == "h264"

    rebuilt = MediaMetadata.from_dict(d)
    assert rebuilt.fps == 29.97
    assert rebuilt.has_audio is True
    assert rebuilt.total_frames == 3758


def test_inspector_probe_and_mtime_caching(tmp_path: Path) -> None:
    test_file = tmp_path / "video.mp4"
    test_file.write_bytes(b"dummy video data")

    mock_ffprobe_output = {
        "format": {
            "format_name": "mp4",
            "duration": "10.000000",
            "bit_rate": "1500000",
            "size": "50000",
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "r_frame_rate": "30/1",
                "avg_frame_rate": "30/1",
                "pix_fmt": "yuv420p",
                "display_aspect_ratio": "16:9",
                "nb_frames": "300",
            },
            {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "44100",
                "channels": 2,
                "bit_rate": "128000",
            },
        ],
    }

    MediaInspector.clear_cache()

    with patch("subprocess.run") as mock_run:
        mock_result = MagicMock()
        mock_result.stdout = json.dumps(mock_ffprobe_output)
        mock_run.return_value = mock_result

        # First probe - runs ffprobe
        meta1 = MediaInspector.probe(test_file)
        assert meta1.width == 1920
        assert meta1.height == 1080
        assert meta1.fps == 30.0
        assert meta1.video_codec == "h264"
        assert meta1.audio_codec == "aac"
        assert meta1.total_frames == 300
        assert mock_run.call_count == 1

        # Second probe on same file with unchanged mtime - served directly from cache
        meta2 = MediaInspector.probe(test_file)
        assert meta2 is meta1
        assert mock_run.call_count == 1  # No additional subprocess call!

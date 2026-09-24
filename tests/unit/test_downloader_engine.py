"""Unit tests for modules.downloader.engine."""

from pathlib import Path
from unittest.mock import patch

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError
from modules.downloader.engine import DownloaderEngine


def test_engine_probe() -> None:
    engine = DownloaderEngine()
    probe_info = engine.probe()
    assert probe_info["status"] == "ready"
    assert probe_info["version"] is not None


def test_engine_extract_info_mocked() -> None:
    engine = DownloaderEngine()

    mock_info = {
        "id": "vid123",
        "title": "Sample Documentary",
        "uploader": "Test Channel",
        "duration": 300.0,
        "thumbnail": "https://example.com/thumb.jpg",
        "extractor_key": "YouTube",
        "formats": [
            {
                "format_id": "137",
                "ext": "mp4",
                "width": 1920,
                "height": 1080,
                "vcodec": "avc1",
                "acodec": "none",
                "filesize": 10000000,
            },
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a",
                "filesize": 2000000,
            }
        ]
    }

    with patch("yt_dlp.YoutubeDL") as mock_ydl_cls:
        mock_instance = mock_ydl_cls.return_value.__enter__.return_value
        mock_instance.extract_info.return_value = mock_info
        extracted = engine.extract_info("https://youtube.com/watch?v=vid123")
        assert extracted["title"] == "Sample Documentary"
        assert extracted["creator"] == "Test Channel"
        assert len(extracted["formats"]) == 2


def test_engine_download_cancellation(tmp_path: Path) -> None:
    engine = DownloaderEngine()
    token = CancellationToken()
    token.cancel()

    with pytest.raises(CancelledError):
        engine.download("https://example.com/video.mp4", dest_dir=tmp_path, token=token)

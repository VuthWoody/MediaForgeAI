"""Unit tests for Hongguo Short Drama extractor, subtitle generator, and queue integration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.job_queue import JobQueue
from core.resource_lock import ResourceLock
from modules.downloader.hongguo import (
    HongguoDramaInfo,
    HongguoEpisodeStream,
    HongguoExtractor,
    format_srt_timestamp,
)
from modules.downloader.organizer import MediaOrganizer
from modules.downloader.queue_manager import DownloadQueueManager


def test_is_hongguo_url() -> None:
    assert HongguoExtractor.is_hongguo_url("https://hongguoduanju.com/player/7675288927619533886")
    assert HongguoExtractor.is_hongguo_url("https://hongguoduanju.com/detail?series_id=7675288927619533886")
    assert HongguoExtractor.is_hongguo_url("https://www.hongguoduanju.com/search/%E5%89%91%E5%AE%97")
    assert not HongguoExtractor.is_hongguo_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert not HongguoExtractor.is_hongguo_url("https://v.douyin.com/abcde/")
    assert not HongguoExtractor.is_hongguo_url("")


def test_parse_series_id() -> None:
    expected = "7675288927619533886"
    assert HongguoExtractor.parse_series_id("7675288927619533886") == expected
    assert HongguoExtractor.parse_series_id("https://hongguoduanju.com/player/7675288927619533886") == expected
    assert (
        HongguoExtractor.parse_series_id("https://hongguoduanju.com/player/7675288927619533886/7675294618430213144")
        == expected
    )
    assert (
        HongguoExtractor.parse_series_id("https://hongguoduanju.com/detail?series_id=7675288927619533886")
        == expected
    )
    assert HongguoExtractor.parse_series_id("invalid_input") is None


def test_parse_episode_range() -> None:
    # "all" or empty returns all up to max
    assert HongguoExtractor.parse_episode_range("all", 5) == [1, 2, 3, 4, 5]
    assert HongguoExtractor.parse_episode_range("*", 3) == [1, 2, 3]

    # Specific range
    assert HongguoExtractor.parse_episode_range("1-3", 10) == [1, 2, 3]
    assert HongguoExtractor.parse_episode_range("1, 3, 5", 10) == [1, 3, 5]
    assert HongguoExtractor.parse_episode_range("2-4, 7, 9-10", 10) == [2, 3, 4, 7, 9, 10]

    # Out of bounds and deduplication
    assert HongguoExtractor.parse_episode_range("1-5, 3, 12", 5) == [1, 2, 3, 4, 5]
    assert HongguoExtractor.parse_episode_range("invalid, -1, 0", 5) == []


def test_format_srt_timestamp() -> None:
    assert format_srt_timestamp(0.0) == "00:00:00,000"
    assert format_srt_timestamp(65.432) == "00:01:05,432"
    assert format_srt_timestamp(3661.050) == "01:01:01,050"
    assert format_srt_timestamp(-5.0) == "00:00:00,000"


def test_get_drama_info_mock() -> None:
    mock_router_data = {
        "loaderData": {
            "player_(series_id)/page": {
                "seriesDetail": {
                    "series_id": "7675288927619533886",
                    "series_name": "Test Drama Series",
                    "series_cover": "https://p3.example.com/cover.jpg",
                    "series_intro": "A great short drama synopsis.",
                    "episode_cnt": 10,
                    "accessible_episode_cnt": 3,
                    "vid_list": ["vid1", "vid2", "vid3", "vid4", "vid5"],
                }
            }
        }
    }
    mock_html = f"<html><script>window._ROUTER_DATA = {json.dumps(mock_router_data)};</script></html>"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_html.encode("utf-8")
        mock_urlopen.return_value = mock_resp

        info = HongguoExtractor.get_drama_info("https://hongguoduanju.com/player/7675288927619533886")

        assert isinstance(info, HongguoDramaInfo)
        assert info.series_id == "7675288927619533886"
        assert info.series_name == "Test Drama Series"
        assert info.episode_cnt == 10
        assert info.accessible_episode_cnt == 3
        assert len(info.episodes) == 10
        assert info.episodes[0].episode_num == 1
        assert info.episodes[0].accessible is True
        assert info.episodes[3].accessible is False  # Ep 4 is locked


def test_get_episode_stream_mock() -> None:
    mock_router_data = {
        "loaderData": {
            "player_(series_id)/page": {
                "seriesDetail": {"series_name": "Test Drama"},
                "video_player_info": {
                    "main_url": "https://v11.example.com/test.mp4",
                    "duration": 120.5,
                    "width": 1920,
                    "height": 1080,
                    "poster_url": "https://p11.example.com/poster.jpg",
                },
            }
        }
    }
    mock_html = f"<html><script>window._ROUTER_DATA = {json.dumps(mock_router_data)};</script></html>"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_html.encode("utf-8")
        mock_urlopen.return_value = mock_resp

        stream = HongguoExtractor.get_episode_stream(
            series_id="7675288927619533886",
            episode_num=1,
        )

        assert isinstance(stream, HongguoEpisodeStream)
        assert stream.stream_url == "https://v11.example.com/test.mp4"
        assert stream.duration == 120.5
        assert stream.width == 1920
        assert stream.height == 1080
        assert "Test Drama" in stream.title
        assert stream.headers["Referer"] == "https://hongguoduanju.com/"


def test_enqueue_hongguo_episode(tmp_path: Path) -> None:
    q_db = tmp_path / "queue.db"
    org_db = tmp_path / "lib.db"
    dl_dir = tmp_path / "downloads"

    jq = JobQueue(db_path=q_db)
    organizer = MediaOrganizer(base_dir=dl_dir, db_path=org_db)
    lock = ResourceLock()
    manager = DownloadQueueManager(job_queue=jq, organizer=organizer, resource_lock=lock)

    with patch.object(manager, "_spawn_worker"):
        job = manager.enqueue_hongguo_episode(
            series_id="7675288927619533886",
            episode_num=2,
            vid="7675294618430213144",
            title="Test Drama Ep 2",
            series_name="Test Drama",
            generate_srt=True,
        )

        assert job is not None
        assert job.payload["is_hongguo"] is True
        assert job.payload["series_id"] == "7675288927619533886"
        assert job.payload["episode_num"] == 2
        assert job.payload["generate_srt"] is True
    manager.shutdown()


def test_get_drama_info_celebrities_extraction() -> None:
    """Verify that HongguoExtractor parses cast celebrities into character profiles."""
    mock_router_data = {
        "loaderData": {
            "player_(series_id)/page": {
                "seriesDetail": {
                    "series_id": "7685350746975390744",
                    "series_name": "Test Drama with Cast",
                    "episode_cnt": 3,
                    "accessible_episode_cnt": 3,
                    "celebrities": [
                        {"nickname": "黄思宇", "sub_title": "饰 林清言"},
                        {"nickname": "周婷", "sub_title": "饰 周慧兰"},
                        {"nickname": "李小风", "sub_title": "饰 赵明宇"},
                    ],
                }
            }
        }
    }
    mock_html = f"<html><script>window._ROUTER_DATA = {json.dumps(mock_router_data)};</script></html>"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = mock_html.encode("utf-8")
        mock_urlopen.return_value = mock_resp

        info = HongguoExtractor.get_drama_info("https://hongguoduanju.com/player/7685350746975390744")
        assert len(info.characters) == 3
        assert info.characters[0]["character"] == "林清言"
        assert info.characters[0]["actor"] == "黄思宇"
        assert "林清言 (黄思宇)" in info.characters[0]["display"]

        assert info.characters[1]["character"] == "周慧兰"
        assert info.characters[2]["character"] == "赵明宇"

        chars_direct = HongguoExtractor.extract_characters_from_url(
            "https://hongguoduanju.com/player/7685350746975390744"
        )
        assert len(chars_direct) == 3
        assert chars_direct[0]["character"] == "林清言"

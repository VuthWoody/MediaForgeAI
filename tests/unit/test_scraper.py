"""Unit tests for modules.downloader.scraper."""

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError
from modules.downloader.scraper import PlaywrightScraper, _detect_platform


def test_detect_platform() -> None:
    assert _detect_platform("https://www.youtube.com/watch?v=123") == "YouTube"
    assert _detect_platform("https://youtu.be/123") == "YouTube"
    assert _detect_platform("https://v.douyin.com/iABCDE/") == "Douyin"
    assert _detect_platform("https://www.tiktok.com/@user/video/123") == "TikTok"
    assert _detect_platform("https://www.bilibili.com/video/BV123") == "Bilibili"
    assert _detect_platform("https://example.com/stream.m3u8") == "Generic"


def test_scraper_cancellation() -> None:
    token = CancellationToken()
    token.cancel()

    with pytest.raises(CancelledError):
        PlaywrightScraper.sniff_stream("https://example.com/test", token=token)

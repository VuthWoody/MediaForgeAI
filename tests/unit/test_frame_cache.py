"""Unit tests for FrameCache enforcing LRU eviction when > 60 frames buffered."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from modules.media.frame_cache import FrameCache


def create_dummy_frame(color: QColor) -> QImage:
    img = QImage(64, 64, QImage.Format.Format_RGB32)
    img.fill(color)
    return img


def test_frame_cache_evicts_when_over_60_frames(tmp_path: Path) -> None:
    """Verify Section 7 Phase 3 rule: 'FrameCache evicts LRU when > 60 frames buffered.'"""
    cache = FrameCache(capacity=60)
    video_path = tmp_path / "test.mp4"

    # Insert 70 frames (indices 0 to 69)
    for i in range(70):
        img = create_dummy_frame(QColor(i % 256, 0, 0))
        cache.put(video_path, i, img)

    # Size must be strictly capped at 60
    assert len(cache) == 60

    # Oldest 10 frames (0 to 9) must have been evicted
    for i in range(10):
        assert cache.get(video_path, i) is None

    # Newest 60 frames (10 to 69) must be present
    for i in range(10, 70):
        retrieved = cache.get(video_path, i)
        assert retrieved is not None
        assert not retrieved.isNull()


def test_frame_cache_recency_promotion(tmp_path: Path) -> None:
    cache = FrameCache(capacity=3)
    video_path = tmp_path / "sample.mp4"

    # Add frames 0, 1, 2
    cache.put(video_path, 0, create_dummy_frame(QColor(255, 0, 0)))
    cache.put(video_path, 1, create_dummy_frame(QColor(0, 255, 0)))
    cache.put(video_path, 2, create_dummy_frame(QColor(0, 0, 255)))
    assert len(cache) == 3

    # Access frame 0 (makes frame 0 most recent; frame 1 becomes oldest)
    accessed = cache.get(video_path, 0)
    assert accessed is not None

    # Add frame 3 (should evict frame 1, NOT frame 0)
    cache.put(video_path, 3, create_dummy_frame(QColor(255, 255, 0)))
    assert len(cache) == 3
    assert cache.get(video_path, 1) is None
    assert cache.get(video_path, 0) is not None
    assert cache.get(video_path, 2) is not None
    assert cache.get(video_path, 3) is not None


def test_frame_cache_clear(tmp_path: Path) -> None:
    cache = FrameCache()
    video_path = tmp_path / "sample.mp4"
    cache.put(video_path, 1, create_dummy_frame(QColor(255, 255, 255)))
    assert len(cache) == 1
    cache.clear()
    assert len(cache) == 0

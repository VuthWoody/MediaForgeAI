"""LRU frame cache holding +/- 30 frames around current playhead with exact FFmpeg decoding."""

from __future__ import annotations

import logging
import subprocess
import threading
from collections import OrderedDict
from pathlib import Path

from PySide6.QtGui import QImage

logger = logging.getLogger(__name__)


class FrameCache:
    """Thread-safe LRU cache storing decoded video frames with a maximum of 60 items."""

    MAX_FRAMES: int = 60  # Rule: +/- 30 frames around playhead; evict when > 60

    def __init__(self, capacity: int = MAX_FRAMES) -> None:
        self.capacity = max(1, capacity)
        self._cache: OrderedDict[tuple[str, int], QImage] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def get(self, video_path: Path | str, frame_idx: int) -> QImage | None:
        """Retrieve a frame from the cache and mark it as recently used."""
        key = (str(Path(video_path).resolve()), frame_idx)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
            return None

    def put(self, video_path: Path | str, frame_idx: int, image: QImage) -> None:
        """Insert a frame into the cache, evicting the least-recently-used when exceeding capacity."""
        if image.isNull():
            return

        key = (str(Path(video_path).resolve()), frame_idx)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                self._cache[key] = image
                return

            self._cache[key] = image
            while len(self._cache) > self.capacity:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached frames."""
        with self._lock:
            self._cache.clear()

    def extract_exact_frame(
        self,
        video_path: Path | str,
        frame_idx: int,
        fps: float,
    ) -> QImage:
        """Decode exactly one frame at frame_idx via FFmpeg subprocess and cache it.

        Conforms to Section 7 Phase 3 rule:
        'Frame stepping: step_forward()/step_back() decode EXACTLY ONE FRAME via FFmpeg subprocess.'
        """
        cached = self.get(video_path, frame_idx)
        if cached is not None:
            return cached

        path = Path(video_path).resolve()
        if not path.exists():
            return QImage()

        safe_fps = fps if fps > 0 else 30.0
        # Calculate timestamp in seconds
        timestamp_sec = max(0.0, frame_idx / safe_fps)

        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(path),
            "-ss",
            f"{timestamp_sec:.6f}",
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-c:v",
            "png",
            "-",
        ]

        try:
            res = subprocess.run(
                cmd,
                capture_output=True,
                check=True,
                timeout=10,
            )
            image = QImage.fromData(res.stdout)
            if not image.isNull():
                self.put(path, frame_idx, image)
                return image
            logger.warning("Decoded frame at index %d was null.", frame_idx)
            return QImage()
        except Exception as e:
            logger.error("FFmpeg frame extraction failed for frame %d: %s", frame_idx, e)
            return QImage()

    def prefetch(
        self,
        video_path: Path | str,
        center_frame: int,
        fps: float,
        radius: int = 15,
    ) -> None:
        """Asynchronously pre-fetch neighboring frames around center_frame."""
        start = max(0, center_frame - radius)
        end = center_frame + radius

        def worker() -> None:
            for idx in range(start, end + 1):
                if self.get(video_path, idx) is None:
                    self.extract_exact_frame(video_path, idx, fps)

        t = threading.Thread(target=worker, daemon=True, name="FramePrefetcher")
        t.start()

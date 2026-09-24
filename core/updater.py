"""Auto-updater for yt-dlp nightly and PyPI releases."""

from __future__ import annotations

import logging
import subprocess
import sys
import threading
from typing import Any

import requests
import yt_dlp

from core.event_bus import get_event_bus

logger = logging.getLogger(__name__)


class YtDlpUpdater:
    """Checks and updates yt-dlp with offline tolerance."""

    PYPI_URL = "https://pypi.org/pypi/yt-dlp/json"

    @classmethod
    def get_current_version(cls) -> str:
        """Get current installed yt-dlp version."""
        return str(yt_dlp.version.__version__)

    @classmethod
    def check_for_update(cls, timeout: float = 3.0) -> dict[str, Any]:
        """Check PyPI for newer yt-dlp version.

        Never raises; on network failure, falls back to cached version and emits warning.
        """
        curr = cls.get_current_version()
        res: dict[str, Any] = {
            "current": curr,
            "latest": None,
            "update_available": False,
            "error": None,
        }

        try:
            r = requests.get(cls.PYPI_URL, timeout=timeout)
            if r.status_code == 200:
                data = r.json()
                latest = str(data.get("info", {}).get("version", curr))
                res["latest"] = latest
                # Compare versions loosely or normalized
                curr_clean = curr.replace(".0", ".")
                latest_clean = latest.replace(".0", ".")
                if latest_clean > curr_clean:
                    res["update_available"] = True
                    try:
                        get_event_bus().toast.emit(
                            "info",
                            f"yt-dlp update available: {latest} (current: {curr})",
                        )
                    except Exception:
                        pass
                return res
        except Exception as e:
            logger.warning("yt-dlp update check failed (offline/timeout): %s", e)
            res["error"] = str(e)
            try:
                get_event_bus().toast.emit(
                    "warning",
                    f"yt-dlp offline check: Using cached version {curr}.",
                )
            except Exception:
                pass

        return res

    @classmethod
    def run_update(cls) -> bool:
        """Execute pip upgrade for yt-dlp."""
        try:
            cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            return result.returncode == 0
        except Exception as e:
            logger.error("Failed to upgrade yt-dlp: %s", e)
            return False

    @classmethod
    def check_async(cls, callback: Any | None = None) -> threading.Thread:
        """Run update check in background thread on launch without blocking UI."""
        def worker() -> None:
            info = cls.check_for_update()
            if callback:
                try:
                    callback(info)
                except Exception:
                    pass

        t = threading.Thread(target=worker, daemon=True, name="YtDlpUpdateChecker")
        t.start()
        return t

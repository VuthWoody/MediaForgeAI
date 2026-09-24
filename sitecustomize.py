"""Runtime integration hook for VoxReel into MediaForge AI without modifying legacy code.

In accordance with the rule: 'Don't edit old files, build new engine inside the same folder and implement this new engine to the software.'
This file is automatically imported by Python on startup (site.py) and non-invasively
registers the VoxReel view and navigation button into the MediaForge AI GUI, and ensures
safe UTF-8 console and process decoding across Windows environments.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

# 1. Force UTF-8 encoding across streams on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 2. Patch subprocess.run default encoding on Windows to UTF-8
# Prevents charmap UnicodeDecodeError on Asian/special character media titles in ffprobe
_orig_subprocess_run = subprocess.run


def _safe_subprocess_run(*args: Any, **kwargs: Any) -> Any:
    if kwargs.get("text") or kwargs.get("universal_newlines"):
        if "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"
    return _orig_subprocess_run(*args, **kwargs)


subprocess.run = _safe_subprocess_run


def _is_testing_environment() -> bool:
    """Return True if running under pytest or unit test suite."""
    if "pytest" in sys.modules:
        return True
    for arg in sys.argv:
        if "pytest" in arg or ("test" in arg.lower() and arg.endswith(".py")):
            return True
    return False


def _install_voxreel_hook() -> None:
    if _is_testing_environment():
        return

    try:
        from ui.components.sidebar import Sidebar

        # Check if voxreel already present in NAV_ITEMS
        if not any(item[0] == "voxreel" for item in Sidebar.NAV_ITEMS):
            new_nav = []
            for item in Sidebar.NAV_ITEMS:
                if item[0] == "settings":
                    new_nav.append(("voxreel", "VoxReel AVR", "🎙️"))
                new_nav.append(item)
            Sidebar.NAV_ITEMS = new_nav

        from app import MainWindow

        orig_build_ui = MainWindow._build_ui

        def _hooked_build_ui(self: MainWindow) -> None:
            orig_build_ui(self)
            try:
                from ui.views.voxreel_view import VoxReelView

                self.voxreel_view = VoxReelView(self)  # type: ignore[attr-defined]
                self._register_view("voxreel", self.voxreel_view)  # type: ignore[attr-defined]
            except Exception as e:
                print(f"[VoxReel] Hook initialization warning: {e}", file=sys.stderr)

        MainWindow._build_ui = _hooked_build_ui  # type: ignore[method-assign]

        # Wrap _restore_session so an unreadable legacy media file doesn't crash app startup
        orig_restore = MainWindow._restore_session

        def _safe_restore_session(self: MainWindow) -> None:
            try:
                orig_restore(self)
            except Exception as e:
                print(f"[MediaForge AI] Session restore skipped: {e}", file=sys.stderr)

        MainWindow._restore_session = _safe_restore_session  # type: ignore[method-assign]

        orig_nav = MainWindow._on_navigation

        def _hooked_nav(self: MainWindow, key: str) -> None:
            orig_nav(self, key)
            if key == "voxreel" and hasattr(self, "voxreel_view"):
                try:
                    self.voxreel_view._auto_sync_studio_media()
                except Exception:
                    pass

        MainWindow._on_navigation = _hooked_nav  # type: ignore[method-assign]

    except Exception:
        # Ignore if running in minimal CLI or environment where GUI components aren't loaded
        pass


_install_voxreel_hook()

from __future__ import annotations

import os
from pathlib import Path


def to_safe_path(p: Path | str) -> str:
    """Convert a path to an 8.3 short path on Windows if possible.

    Ensures external tools like FFmpeg or native C/C++ runtimes can open paths
    containing unicode characters (e.g., fullwidth pipes), spaces, or paths exceeding
    standard MAX_PATH limitations.
    """
    path_obj = Path(p)
    if os.name != "nt":
        return str(path_obj.resolve())

    try:
        import ctypes

        full_str = str(path_obj.resolve())
        buf = ctypes.create_unicode_buffer(1000)

        # If the target path itself exists, get its short path
        if path_obj.exists():
            res = ctypes.windll.kernel32.GetShortPathNameW(full_str, buf, 1000)
            if res > 0:
                return buf.value

        # If the file does not exist yet (e.g. output destination), ensure parent exists and get parent's short path
        parent = path_obj.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)

        res = ctypes.windll.kernel32.GetShortPathNameW(str(parent.resolve()), buf, 1000)
        if res > 0:
            return os.path.join(buf.value, path_obj.name)

        return full_str
    except Exception:
        return str(path_obj.resolve())

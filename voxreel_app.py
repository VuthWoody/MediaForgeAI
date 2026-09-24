"""Dedicated launcher for MediaForge AI with VoxReel Engine integrated."""

from __future__ import annotations

import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    import sitecustomize
    sitecustomize._install_voxreel_hook()
except Exception as e:
    print(f"[VoxReel] Launcher hook warning: {e}", file=sys.stderr)

from app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

"""MediaForge AI — main entry point proxy to app.py."""

from __future__ import annotations

import sys

# Initialize VoxReel AVR engine and environment hooks
try:
    import sitecustomize  # noqa: F401
except ImportError:
    pass

from app import main

if __name__ == "__main__":
    sys.exit(main())

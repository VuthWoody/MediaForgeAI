"""VoxReel — Speaker Diarization & Actor Voice Registry Engine.

Root proxy module to allow `import voxreel` and `python -m voxreel`.
"""

from __future__ import annotations

import sys

from modules.voxreel import (
    ActorVoiceRegistry,
    AudioConditioner,
    VoxReelConfig,
    VoxReelDB,
    VoxReelEngine,
    __version__,
)
from modules.voxreel.cli import main

__all__ = [
    "__version__",
    "VoxReelConfig",
    "VoxReelDB",
    "AudioConditioner",
    "ActorVoiceRegistry",
    "VoxReelEngine",
    "main",
]

if __name__ == "__main__":
    sys.exit(main())

"""VoxReel — Speaker Diarization & Actor Voice Registry Engine.

Package initialization and high-level exports.
"""

from __future__ import annotations

__version__ = "1.0.0"

from modules.voxreel.audio import AudioConditioner
from modules.voxreel.config import VoxReelConfig
from modules.voxreel.db import VoxReelDB
from modules.voxreel.engine import VoxReelEngine
from modules.voxreel.registry import ActorVoiceRegistry

__all__ = [
    "__version__",
    "VoxReelConfig",
    "VoxReelDB",
    "AudioConditioner",
    "ActorVoiceRegistry",
    "VoxReelEngine",
]

"""Constants for MediaForge AI."""

from typing import Final

APP_NAME: Final[str] = "MediaForge AI"
APP_VERSION: Final[str] = "1.0.0-dev"
SCHEMA_VERSION: Final[int] = 1
KEYRING_SERVICE: Final[str] = "mediaforge"

# Logging configuration
LOG_MAX_BYTES: Final[int] = 10 * 1024 * 1024  # 10 MB
LOG_BACKUP_COUNT: Final[int] = 5

# Named resource locks
LOCK_GPU_EXCLUSIVE: Final[str] = "GPU_EXCLUSIVE"
LOCK_CPU_HEAVY: Final[str] = "CPU_HEAVY"
LOCK_NETWORK_BULK: Final[str] = "NETWORK_BULK"
ALL_RESOURCE_LOCKS: Final[tuple[str, ...]] = (
    LOCK_GPU_EXCLUSIVE,
    LOCK_CPU_HEAVY,
    LOCK_NETWORK_BULK,
)

# Job Statuses
STATUS_QUEUED: Final[str] = "queued"
STATUS_RUNNING: Final[str] = "running"
STATUS_COMPLETED: Final[str] = "completed"
STATUS_FAILED: Final[str] = "failed"
STATUS_CANCELLED: Final[str] = "cancelled"

# Job Kinds
KIND_DOWNLOAD: Final[str] = "download"
KIND_TRANSCRIBE: Final[str] = "transcribe"
KIND_SEPARATE: Final[str] = "separate"
KIND_TRANSLATE: Final[str] = "translate"
KIND_TTS: Final[str] = "tts"
KIND_ALIGN: Final[str] = "align"
KIND_MIX: Final[str] = "mix"
KIND_RENDER: Final[str] = "render"

"""Central EventBus based on PySide6 Qt signals."""

from __future__ import annotations

import sys
import threading
from typing import ClassVar

from PySide6.QtCore import QObject, Signal


def _ensure_qapp() -> None:
    """Ensure a QApplication exists so Qt signals and widgets function in tests/CLI."""
    from PySide6.QtWidgets import QApplication

    if QApplication.instance() is None:
        argv = sys.argv if sys.argv else ["MediaForgeAI"]
        QApplication(argv)


class EventBus(QObject):
    """Singleton pub/sub event bus over PySide6 signals."""

    job_queued: ClassVar[Signal] = Signal(str)
    job_started: ClassVar[Signal] = Signal(str)
    job_progress: ClassVar[Signal] = Signal(str, float, str)
    job_completed: ClassVar[Signal] = Signal(str, dict)
    job_failed: ClassVar[Signal] = Signal(str, str)
    job_cancelled: ClassVar[Signal] = Signal(str)
    hardware_update: ClassVar[Signal] = Signal(dict)
    toast: ClassVar[Signal] = Signal(str, str)  # (level, message)

    _instance: ClassVar[EventBus | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, parent: QObject | None = None) -> None:
        _ensure_qapp()
        super().__init__(parent)

    @classmethod
    def instance(cls) -> EventBus:
        """Get or create the singleton EventBus instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    _ensure_qapp()
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for test isolation)."""
        with cls._lock:
            cls._instance = None


def get_event_bus() -> EventBus:
    """Helper to access the singleton EventBus."""
    return EventBus.instance()

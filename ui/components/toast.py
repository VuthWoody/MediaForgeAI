"""Floating toast notification overlay for user feedback."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QWidget,
)

from core.event_bus import get_event_bus


class Toast(QFrame):
    """Single floating toast message."""

    COLORS = {
        "info": ("#2563eb", "ℹ️"),
        "success": ("#10b981", "✅"),
        "warning": ("#f59e0b", "⚠️"),
        "error": ("#ef4444", "❌"),
    }

    def __init__(self, level: str, message: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.SubWindow | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)

        color, icon = self.COLORS.get(level.lower(), ("#6366f1", "ℹ️"))
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1e2230;
                border: 1px solid {color};
                border-left: 4px solid {color};
                border-radius: 6px;
                padding: 8px 14px;
            }}
            QLabel {{
                color: #f3f4f6;
                font-size: 13px;
                font-weight: 500;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 14px;")
        layout.addWidget(icon_lbl)

        msg_lbl = QLabel(message)
        layout.addWidget(msg_lbl)

        # Auto-dismiss timer (4 seconds)
        QTimer.singleShot(4000, self.deleteLater)


class ToastManager(QObject):
    """Listens to EventBus.toast and displays toasts on the parent window."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.parent_widget = parent
        get_event_bus().toast.connect(self.show_toast)

    def show_toast(self, level: str, message: str) -> None:
        """Create and position toast in bottom-right corner."""
        toast = Toast(level, message, parent=self.parent_widget)
        toast.adjustSize()

        # Position toast in bottom right of main window
        x = self.parent_widget.width() - toast.width() - 24
        y = self.parent_widget.height() - toast.height() - 56
        toast.move(max(10, x), max(10, y))
        toast.show()
        toast.raise_()

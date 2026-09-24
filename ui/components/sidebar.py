"""Collapsible navigation sidebar for MediaForge AI."""

from __future__ import annotations

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class Sidebar(QWidget):
    """Collapsible navigation sidebar emitting view_changed signals."""

    nav_changed = Signal(str)

    NAV_ITEMS = [
        ("dashboard", "Dashboard", "🎛️"),
        ("downloader", "Downloader", "📥"),
        ("library", "Media Library", "📁"),
        ("studio", "Studio", "🎬"),
        ("batch", "Batch Queue", "⚡"),
        ("settings", "Settings", "⚙️"),
    ]

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self._is_collapsed = False
        self._buttons: dict[str, QPushButton] = {}
        self._button_group = QButtonGroup(self)
        self._button_group.setExclusive(True)

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 12, 8, 12)
        layout.setSpacing(6)

        # App Brand Header & Collapse Toggle
        brand_layout = QHBoxLayout()
        brand_layout.setContentsMargins(6, 4, 6, 12)

        self._logo_label = QLabel("⚡")
        self._logo_label.setStyleSheet("font-size: 18px;")
        brand_layout.addWidget(self._logo_label)

        self._title_label = QLabel("MediaForge AI")
        self._title_label.setStyleSheet("font-weight: 700; font-size: 14px; color: #f3f4f6;")
        brand_layout.addWidget(self._title_label)
        brand_layout.addStretch()

        self._toggle_btn = QPushButton("◀")
        self._toggle_btn.setFixedSize(28, 28)
        self._toggle_btn.setToolTip("Collapse sidebar")
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #1a2234;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 4px;
                padding: 0px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2b354d;
                color: #ffffff;
                border-color: #6366f1;
            }
        """)
        self._toggle_btn.clicked.connect(self.toggle_collapse)
        brand_layout.addWidget(self._toggle_btn)

        layout.addLayout(brand_layout)

        # Navigation Buttons
        for key, label, icon in self.NAV_ITEMS:
            btn = QPushButton(f"{icon}  {label}")
            btn.setCheckable(True)
            btn.setIconSize(QSize(18, 18))
            btn.clicked.connect(lambda checked=False, k=key: self._on_item_clicked(k))
            self._button_group.addButton(btn)
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Version Footer
        self._version_label = QLabel("v1.0.0-dev")
        self._version_label.setStyleSheet("color: #6b7280; font-size: 11px; padding: 6px;")
        layout.addWidget(self._version_label)

        # Select Dashboard by default
        self.set_active("dashboard")
        self.setFixedWidth(200)

    def _on_item_clicked(self, key: str) -> None:
        self.nav_changed.emit(key)

    def set_active(self, key: str) -> None:
        """Set the active sidebar item."""
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    def toggle_collapse(self) -> None:
        """Toggle between expanded (200px) and collapsed (64px) sidebar."""
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.setFixedWidth(64)
            self._title_label.setVisible(False)
            self._version_label.setVisible(False)
            self._toggle_btn.setText("▶")
            self._toggle_btn.setToolTip("Expand sidebar")
            for key, _, icon in self.NAV_ITEMS:
                self._buttons[key].setText(icon)
                self._buttons[key].setToolTip(key.capitalize())
        else:
            self.setFixedWidth(200)
            self._title_label.setVisible(True)
            self._version_label.setVisible(True)
            self._toggle_btn.setText("◀")
            self._toggle_btn.setToolTip("Collapse sidebar")
            for key, label, icon in self.NAV_ITEMS:
                self._buttons[key].setText(f"{icon}  {label}")
                self._buttons[key].setToolTip("")

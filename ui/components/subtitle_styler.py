"""Subtitle styler component allowing custom font, size, colors, outline, and positioning."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from modules.processing.subtitle import SubtitleStyle


class SubtitleStylerWidget(QFrame):
    """Configuration panel for subtitle styling."""

    style_changed = Signal(SubtitleStyle)

    def __init__(self, current_style: SubtitleStyle | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style = current_style or SubtitleStyle()
        self._build_ui()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: #111827;
                border: 1px solid #1f2937;
                border-radius: 8px;
            }
            QLabel {
                color: #e5e7eb;
                font-size: 12px;
                font-weight: 600;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel("Subtitle Styler")
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(8)

        # 1. Font Family
        self.font_combo = QComboBox()
        self.font_combo.addItems(["Noto Sans", "Noto Sans Khmer", "Arial", "Segoe UI", "Microsoft YaHei"])
        self.font_combo.setCurrentText(self._style.font_name)
        self.font_combo.currentTextChanged.connect(self._on_changed)
        form.addRow("Font:", self.font_combo)

        # 2. Font Size
        self.size_spin = QSpinBox()
        self.size_spin.setRange(12, 96)
        self.size_spin.setValue(self._style.font_size)
        self.size_spin.valueChanged.connect(self._on_changed)
        form.addRow("Size:", self.size_spin)

        # 3. Alignment
        self.align_combo = QComboBox()
        self.align_combo.addItem("Bottom-Center", 2)
        self.align_combo.addItem("Bottom-Left", 1)
        self.align_combo.addItem("Bottom-Right", 3)
        self.align_combo.addItem("Top-Center", 6)
        self.align_combo.setCurrentIndex(0)
        self.align_combo.currentIndexChanged.connect(self._on_changed)
        form.addRow("Alignment:", self.align_combo)

        # 4. Bold / Italic
        check_row = QHBoxLayout()
        self.bold_check = QCheckBox("Bold")
        self.bold_check.setChecked(self._style.bold)
        self.bold_check.toggled.connect(self._on_changed)
        self.italic_check = QCheckBox("Italic")
        self.italic_check.setChecked(self._style.italic)
        self.italic_check.toggled.connect(self._on_changed)
        check_row.addWidget(self.bold_check)
        check_row.addWidget(self.italic_check)
        form.addRow("Style:", check_row)

        layout.addLayout(form)

    def get_style(self) -> SubtitleStyle:
        return SubtitleStyle(
            font_name=self.font_combo.currentText(),
            font_size=self.size_spin.value(),
            bold=self.bold_check.isChecked(),
            italic=self.italic_check.isChecked(),
            alignment=self.align_combo.currentData() or 2,
        )

    def _on_changed(self) -> None:
        self._style = self.get_style()
        self.style_changed.emit(self._style)

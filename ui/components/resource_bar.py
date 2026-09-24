"""System hardware resource bar displaying live CPU, RAM, GPU, and Disk meters."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QWidget,
)

from core.event_bus import get_event_bus


class ResourceBar(QFrame):
    """Bottom telemetry bar updating once per second from EventBus.hardware_update."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("resourceBar")
        self.setFixedHeight(36)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 2)
        layout.setSpacing(16)

        # 1. CPU Section
        cpu_box = QHBoxLayout()
        cpu_box.setSpacing(6)
        self._cpu_title = QLabel("CPU:")
        self._cpu_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        self._cpu_bar = QProgressBar()
        self._cpu_bar.setFixedSize(60, 10)
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setTextVisible(False)
        self._cpu_val = QLabel("0.0%")
        self._cpu_val.setStyleSheet("color: #e5e7eb; font-size: 11px; font-weight: 500;")
        cpu_box.addWidget(self._cpu_title)
        cpu_box.addWidget(self._cpu_bar)
        cpu_box.addWidget(self._cpu_val)
        layout.addLayout(cpu_box)

        # 2. RAM Section
        ram_box = QHBoxLayout()
        ram_box.setSpacing(6)
        self._ram_title = QLabel("RAM:")
        self._ram_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        self._ram_bar = QProgressBar()
        self._ram_bar.setFixedSize(60, 10)
        self._ram_bar.setRange(0, 100)
        self._ram_bar.setTextVisible(False)
        self._ram_val = QLabel("0.0 / 0.0 GB (0%)")
        self._ram_val.setStyleSheet("color: #e5e7eb; font-size: 11px; font-weight: 500;")
        ram_box.addWidget(self._ram_title)
        ram_box.addWidget(self._ram_bar)
        ram_box.addWidget(self._ram_val)
        layout.addLayout(ram_box)

        # 3. GPU Section
        gpu_box = QHBoxLayout()
        gpu_box.setSpacing(6)
        self._gpu_title = QLabel("GPU:")
        self._gpu_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        self._gpu_bar = QProgressBar()
        self._gpu_bar.setFixedSize(60, 10)
        self._gpu_bar.setRange(0, 100)
        self._gpu_bar.setTextVisible(False)
        self._gpu_val = QLabel("CPU Mode")
        self._gpu_val.setStyleSheet("color: #9ca3af; font-size: 11px;")
        gpu_box.addWidget(self._gpu_title)
        gpu_box.addWidget(self._gpu_bar)
        gpu_box.addWidget(self._gpu_val)
        layout.addLayout(gpu_box)

        layout.addStretch()

        # 4. Storage / Disk Section
        disk_box = QHBoxLayout()
        disk_box.setSpacing(6)
        self._disk_title = QLabel("Disk:")
        self._disk_title.setStyleSheet("color: #9ca3af; font-size: 11px; font-weight: 600;")
        self._disk_val = QLabel("--%")
        self._disk_val.setStyleSheet("color: #e5e7eb; font-size: 11px;")
        disk_box.addWidget(self._disk_title)
        disk_box.addWidget(self._disk_val)
        layout.addLayout(disk_box)

    def _connect_signals(self) -> None:
        get_event_bus().hardware_update.connect(self.update_metrics)

    def update_metrics(self, metrics: dict[str, Any]) -> None:
        """Update telemetry UI safely without blocking."""
        # CPU
        cpu = metrics.get("cpu_percent")
        if cpu is not None:
            self._cpu_bar.setValue(int(cpu))
            self._cpu_val.setText(f"{cpu:.1f}%")

        # RAM
        ram_pct = metrics.get("ram_percent")
        ram_used = metrics.get("ram_used_gb")
        ram_total = metrics.get("ram_total_gb")
        if ram_pct is not None and ram_used is not None and ram_total is not None:
            self._ram_bar.setValue(int(ram_pct))
            self._ram_val.setText(f"{ram_used:.1f}/{ram_total:.1f} GB ({int(ram_pct)}%)")

        # GPU
        gpu_pct = metrics.get("gpu_percent")
        gpu_name = metrics.get("gpu_name")
        if gpu_pct is not None and gpu_name:
            self._gpu_bar.setValue(int(gpu_pct))
            self._gpu_val.setText(f"{gpu_name} ({int(gpu_pct)}%)")
            self._gpu_val.setStyleSheet("color: #10b981; font-size: 11px;")
        else:
            self._gpu_bar.setValue(0)
            self._gpu_val.setText("CPU / Integrated")
            self._gpu_val.setStyleSheet("color: #9ca3af; font-size: 11px;")

        # Disk
        disk_pct = metrics.get("disk_percent")
        if disk_pct is not None:
            self._disk_val.setText(f"{int(disk_pct)}% Used")

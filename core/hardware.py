"""Hardware telemetry probe for CPU, RAM, Disk, and GPU metrics."""

from __future__ import annotations

import os
import warnings
from typing import Any

import psutil
from PySide6.QtCore import QObject, QTimer

from core.event_bus import get_event_bus

# Optional NVML support for NVIDIA GPUs
try:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        import pynvml
    _NVML_AVAILABLE = True
except Exception:
    _NVML_AVAILABLE = False


class HardwareProbe(QObject):
    """Monitors system resources (CPU, RAM, GPU, Disk).

    Runs via a 1 Hz QTimer on the MAIN THREAD (never a worker thread)
    and broadcasts updates over EventBus.hardware_update.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer: QTimer | None = None
        self._nvml_initialized = False
        self._init_nvml()

    def _init_nvml(self) -> None:
        """Attempt to initialize NVML safely."""
        if _NVML_AVAILABLE:
            try:
                pynvml.nvmlInit()
                self._nvml_initialized = True
            except Exception:
                self._nvml_initialized = False

    def probe(self) -> dict[str, Any]:
        """Collect current system metrics. Never raises; missing metrics return None."""
        metrics: dict[str, Any] = {
            "cpu_percent": None,
            "ram_percent": None,
            "ram_used_gb": None,
            "ram_total_gb": None,
            "disk_percent": None,
            "gpu_name": None,
            "gpu_percent": None,
            "gpu_mem_used_mb": None,
            "gpu_mem_total_mb": None,
        }

        # 1. CPU Telemetry
        try:
            metrics["cpu_percent"] = float(psutil.cpu_percent(interval=None))
        except Exception:
            metrics["cpu_percent"] = None

        # 2. RAM Telemetry
        try:
            mem = psutil.virtual_memory()
            metrics["ram_percent"] = float(mem.percent)
            metrics["ram_used_gb"] = round(float(mem.used) / (1024**3), 2)
            metrics["ram_total_gb"] = round(float(mem.total) / (1024**3), 2)
        except Exception:
            pass

        # 3. Disk Telemetry
        try:
            drive = os.path.splitdrive(os.getcwd())[0] or "C:"
            disk = psutil.disk_usage(drive + "\\")
            metrics["disk_percent"] = float(disk.percent)
        except Exception:
            pass

        # 4. GPU Telemetry (NVIDIA via NVML)
        if self._nvml_initialized:
            try:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                name = pynvml.nvmlDeviceGetName(handle)
                metrics["gpu_name"] = str(name) if isinstance(name, str) else name.decode("utf-8")

                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                metrics["gpu_percent"] = float(util.gpu)

                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                metrics["gpu_mem_used_mb"] = round(float(mem_info.used) / (1024**2), 1)
                metrics["gpu_mem_total_mb"] = round(float(mem_info.total) / (1024**2), 1)
            except Exception:
                pass

        return metrics

    def probe_and_emit(self) -> dict[str, Any]:
        """Collect metrics and emit them to the central EventBus."""
        metrics = self.probe()
        try:
            get_event_bus().hardware_update.emit(metrics)
        except Exception:
            pass
        return metrics

    def start(self, interval_ms: int = 1000) -> None:
        """Start the 1 Hz telemetry probe on the main thread."""
        if self._timer is None:
            self._timer = QTimer(self)
            self._timer.setInterval(interval_ms)
            self._timer.timeout.connect(self.probe_and_emit)
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """Stop the telemetry probe."""
        if self._timer is not None and self._timer.isActive():
            self._timer.stop()

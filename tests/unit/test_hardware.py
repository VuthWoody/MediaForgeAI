"""Unit tests for core.hardware."""

from core.event_bus import get_event_bus
from core.hardware import HardwareProbe


def test_hardware_probe_metrics() -> None:
    probe = HardwareProbe()
    metrics = probe.probe()

    assert isinstance(metrics, dict)
    for key in (
        "cpu_percent",
        "ram_percent",
        "ram_used_gb",
        "ram_total_gb",
        "disk_percent",
        "gpu_name",
        "gpu_percent",
        "gpu_mem_used_mb",
        "gpu_mem_total_mb",
    ):
        assert key in metrics

    # CPU, RAM, and Disk should be valid numeric values on Windows
    assert isinstance(metrics["cpu_percent"], float)
    assert isinstance(metrics["ram_percent"], float)
    assert isinstance(metrics["disk_percent"], float)


def test_hardware_probe_and_emit() -> None:
    probe = HardwareProbe()
    bus = get_event_bus()

    received: list[dict[str, object]] = []
    bus.hardware_update.connect(received.append)

    probe.probe_and_emit()
    assert len(received) == 1
    assert "cpu_percent" in received[0]

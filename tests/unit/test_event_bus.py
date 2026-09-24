"""Unit tests for core.event_bus."""

from core.event_bus import EventBus, get_event_bus


def test_event_bus_singleton() -> None:
    bus1 = EventBus.instance()
    bus2 = get_event_bus()
    assert bus1 is bus2


def test_event_bus_signals() -> None:
    bus = EventBus.instance()

    dispatched: dict[str, list[object]] = {
        "job_progress": [],
        "toast": [],
        "hardware_update": [],
    }

    bus.job_progress.connect(
        lambda jid, prog, msg: dispatched["job_progress"].append((jid, prog, msg))
    )
    bus.toast.connect(
        lambda level, msg: dispatched["toast"].append((level, msg))
    )
    bus.hardware_update.connect(
        lambda metrics: dispatched["hardware_update"].append(metrics)
    )

    bus.job_progress.emit("job-1", 0.75, "Encoding video")
    bus.toast.emit("info", "Download started")
    bus.hardware_update.emit({"cpu_percent": 24.5, "gpu_percent": 60.0})

    assert len(dispatched["job_progress"]) == 1
    assert dispatched["job_progress"][0] == ("job-1", 0.75, "Encoding video")

    assert len(dispatched["toast"]) == 1
    assert dispatched["toast"][0] == ("info", "Download started")

    assert len(dispatched["hardware_update"]) == 1
    assert dispatched["hardware_update"][0] == {"cpu_percent": 24.5, "gpu_percent": 60.0}

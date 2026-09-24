"""Unit tests for core.job_queue."""

import time
from pathlib import Path

from core.event_bus import get_event_bus
from core.job_queue import JobQueue


def test_job_queue_lifecycle(tmp_path: Path) -> None:
    db_file = tmp_path / "test_jobs.db"
    queue = JobQueue(db_file)

    events_received: list[tuple[str, str]] = []
    bus = get_event_bus()

    bus.job_queued.connect(lambda jid: events_received.append(("queued", jid)))
    bus.job_started.connect(lambda jid: events_received.append(("started", jid)))
    bus.job_completed.connect(lambda jid, res: events_received.append(("completed", jid)))

    # 1. Enqueue
    job = queue.enqueue("transcribe", {"model": "small", "file": "sample.mp4"})
    assert job.status == "queued"
    assert job.progress == 0.0

    job_dict = job.to_dict()
    assert job_dict["id"] == job.id
    assert job_dict["kind"] == "transcribe"

    retrieved = queue.get_job(job.id)
    assert retrieved is not None
    assert retrieved.kind == "transcribe"
    assert retrieved.payload["model"] == "small"

    # Non-existent job
    assert queue.get_job("non-existent-id") is None

    # 2. Start
    queue.start(job.id)
    job_started = queue.get_job(job.id)
    assert job_started is not None
    assert job_started.status == "running"

    # 3. Update Progress (check throttling)
    queue.update_progress(job.id, 0.25, "Extracting audio")
    queue.update_progress(job.id, 0.30, "Extracting audio fast")
    time.sleep(0.3)
    queue.update_progress(job.id, 0.50, "Transcribing")

    job_prog = queue.get_job(job.id)
    assert job_prog is not None
    assert job_prog.progress >= 0.25

    # 4. Complete
    queue.complete(job.id, {"segments": 42})
    job_done = queue.get_job(job.id)
    assert job_done is not None
    assert job_done.status == "completed"
    assert job_done.progress == 1.0

    queue.close()


def test_job_queue_failure_and_cancellation(tmp_path: Path) -> None:
    db_file = tmp_path / "test_fail_jobs.db"
    queue = JobQueue(db_file)

    # Test failure
    job1 = queue.enqueue("download", {"url": "https://example.com/bad"})
    queue.start(job1.id)
    queue.fail(job1.id, "HTTP 404 Not Found")

    j1 = queue.get_job(job1.id)
    assert j1 is not None
    assert j1.status == "failed"
    assert j1.error == "HTTP 404 Not Found"

    # Test cancellation
    job2 = queue.enqueue("render", {"format": "mp4"})
    queue.start(job2.id)
    queue.cancel(job2.id)

    j2 = queue.get_job(job2.id)
    assert j2 is not None
    assert j2.status == "cancelled"

    queue.close()


def test_job_queue_filtering(tmp_path: Path) -> None:
    db_file = tmp_path / "test_filter.db"
    queue = JobQueue(db_file)

    queue.enqueue("download", {"idx": 1})
    queue.enqueue("transcribe", {"idx": 2})
    j3 = queue.enqueue("translate", {"idx": 3})
    queue.start(j3.id)

    all_jobs = queue.list_jobs()
    assert len(all_jobs) == 3

    transcribe_jobs = queue.list_jobs(kind="transcribe")
    assert len(transcribe_jobs) == 1
    assert transcribe_jobs[0].kind == "transcribe"

    running_jobs = queue.list_jobs(status="running")
    assert len(running_jobs) == 1
    assert running_jobs[0].id == j3.id

    queue.close()


def test_job_queue_crash_recovery(tmp_path: Path) -> None:
    db_file = tmp_path / "test_crash.db"
    queue1 = JobQueue(db_file)

    job = queue1.enqueue("mix", {"track": 1})
    queue1.start(job.id)

    running_job = queue1.get_job(job.id)
    assert running_job is not None
    assert running_job.status == "running"

    # Simulate app crash by abruptly closing DB connection without completing
    queue1.close()

    # Relaunch app
    queue2 = JobQueue(db_file)
    recovered_job = queue2.get_job(job.id)
    assert recovered_job is not None
    # Must be marked failed due to crash survival rule
    assert recovered_job.status == "failed"
    assert "unexpected" in (recovered_job.error or "").lower()

    queue2.close()

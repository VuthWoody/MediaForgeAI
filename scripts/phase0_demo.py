"""Phase 0 Verification Demo.

Queues 3 dummy jobs, cancels the middle one, prints the SQLite trace, and exits 0.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

# Ensure repository root is on sys.path when invoked directly as a script
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.event_bus import get_event_bus  # noqa: E402
from core.job_queue import JobQueue  # noqa: E402


def run_phase0_demo() -> int:
    print("=" * 80)
    print("MEDIAFORGE AI — PHASE 0 FOUNDATIONS DEMO")
    print("=" * 80)

    # Use a temporary database for a clean demo trace
    temp_dir = tempfile.mkdtemp(prefix="mediaforge_phase0_")
    db_path = Path(temp_dir) / "demo_jobs.db"
    print(f"[1/5] Initializing SQLite JobQueue (WAL mode) at: {db_path}")
    queue = JobQueue(db_path)

    # Listen to EventBus signals
    bus = get_event_bus()
    bus.job_queued.connect(lambda jid: print(f"  [EventBus] Signal: job_queued -> {jid}"))
    bus.job_started.connect(lambda jid: print(f"  [EventBus] Signal: job_started -> {jid}"))
    bus.job_progress.connect(lambda jid, prog, msg: print(f"  [EventBus] Signal: job_progress -> {jid} ({prog * 100:.0f}%) {msg}"))
    bus.job_completed.connect(lambda jid, res: print(f"  [EventBus] Signal: job_completed -> {jid}"))
    bus.job_cancelled.connect(lambda jid: print(f"  [EventBus] Signal: job_cancelled -> {jid}"))

    # 1. Queue 3 dummy jobs
    print("\n[2/5] Enqueuing 3 dummy jobs...")
    job1 = queue.enqueue("download", {"url": "https://example.com/stream1.mp4", "quality": "1080p"}, job_id="job-001-download")
    job2 = queue.enqueue("transcribe", {"model": "whisper-small", "language": "en"}, job_id="job-002-transcribe")
    job3 = queue.enqueue("render", {"preset": "fast", "output": "final.mp4"}, job_id="job-003-render")

    # 2. Process Job 1
    print("\n[3/5] Processing Job 1 (Download)...")
    queue.start(job1.id)
    queue.update_progress(job1.id, 0.50, "Downloading chunks (50%)")
    queue.update_progress(job1.id, 1.00, "Download complete")
    queue.complete(job1.id, {"file_size_mb": 142.5})

    # 3. Process and cancel Job 2 (the middle one)
    print("\n[4/5] Starting and Cancelling Job 2 (Middle Job)...")
    queue.start(job2.id)
    queue.update_progress(job2.id, 0.20, "Extracting audio")
    queue.cancel(job2.id)

    # 4. Process Job 3
    print("\n[5/5] Processing Job 3 (Render)...")
    queue.start(job3.id)
    queue.update_progress(job3.id, 0.75, "Encoding H.264")
    queue.complete(job3.id, {"rendered_frames": 1800})

    # Print SQLite Trace
    print("\n" + "=" * 80)
    print("SQLITE JOBS TRACE TABLE (jobs.db)")
    print("=" * 80)
    header = f"{'JOB ID':<22} | {'KIND':<12} | {'STATUS':<10} | {'PROGRESS':<8} | {'UPDATED AT':<28}"
    print(header)
    print("-" * len(header))

    jobs = queue.list_jobs()
    # Sort chronologically by created_at for trace clarity
    jobs.sort(key=lambda j: j.created_at)

    for j in jobs:
        row = f"{j.id:<22} | {j.kind:<12} | {j.status:<10} | {j.progress * 100:>7.1f}% | {j.updated_at.isoformat():<28}"
        print(row)

    print("=" * 80)

    # Verify requirements
    assert len(jobs) == 3, "Expected exactly 3 jobs"
    assert jobs[0].status == "completed", "Job 1 should be completed"
    assert jobs[1].status == "cancelled", "Middle Job (Job 2) should be cancelled"
    assert jobs[2].status == "completed", "Job 3 should be completed"

    queue.close()
    print("Phase 0 Demo completed successfully with exit code 0.")
    return 0


if __name__ == "__main__":
    sys.exit(run_phase0_demo())

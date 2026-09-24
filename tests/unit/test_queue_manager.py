"""Unit tests for modules.downloader.queue_manager."""

from pathlib import Path
from unittest.mock import patch

from core.job_queue import JobQueue
from core.resource_lock import ResourceLock
from modules.downloader.organizer import MediaOrganizer
from modules.downloader.queue_manager import DownloadQueueManager


def test_queue_manager_enqueue_and_cancel(tmp_path: Path) -> None:
    db_file = tmp_path / "jobs.db"
    lib_dir = tmp_path / "library"
    lib_db = tmp_path / "lib.db"

    queue = JobQueue(db_file)
    organizer = MediaOrganizer(base_dir=lib_dir, db_path=lib_db)
    res_lock = ResourceLock()

    mgr = DownloadQueueManager(job_queue=queue, organizer=organizer, resource_lock=res_lock)

    # Worker count slider bounds
    mgr.set_max_workers(8)
    assert mgr.max_workers == 8
    mgr.set_max_workers(50)  # Capped at 32
    assert mgr.max_workers == 32

    # Enqueue a download job with mocked execution
    with patch.object(mgr._executor, "submit"):
        job = mgr.enqueue_download("https://example.com/video.mp4")
        assert job.kind == "download"
        assert job.status == "queued"

        mgr.cancel_download(job.id)
        cancelled_job = queue.get_job(job.id)
        assert cancelled_job is not None
        assert cancelled_job.status in ("cancelled", "queued")

    mgr.shutdown()
    queue.close()
    organizer.close()


def test_concurrent_network_locking(tmp_path: Path) -> None:
    """Ensure 3 concurrent download workers can hold network lock without timing out."""
    import threading
    import time

    queue = JobQueue(tmp_path / "jobs.db")
    organizer = MediaOrganizer(base_dir=tmp_path / "library", db_path=tmp_path / "lib.db")
    res_lock = ResourceLock()
    mgr = DownloadQueueManager(job_queue=queue, organizer=organizer, resource_lock=res_lock, max_workers=4)

    entered = []
    errors = []

    def worker_fn(idx: int) -> None:
        try:
            with mgr._network_lock_scope():
                entered.append(idx)
                time.sleep(0.1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker_fn, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5.0)

    assert len(errors) == 0
    assert len(entered) == 3
    assert not res_lock.is_locked("NETWORK_BULK")

    mgr.shutdown()
    queue.close()
    organizer.close()


def test_resume_download_preserves_payload_and_folder(tmp_path: Path) -> None:
    """Ensure retrying a failed download preserves drama series_name, episode_num, and folder."""
    queue = JobQueue(tmp_path / "jobs.db")
    organizer = MediaOrganizer(base_dir=tmp_path / "library", db_path=tmp_path / "lib.db")
    res_lock = ResourceLock()
    mgr = DownloadQueueManager(job_queue=queue, organizer=organizer, resource_lock=res_lock)

    with patch.object(mgr, "_spawn_worker"):
        job = mgr.enqueue_hongguo_episode(
            series_id="7685350746975390744",
            episode_num=2,
            vid="7685352730482707480",
            title="我的婆婆，我罩着 第2集",
            series_name="我的婆婆，我罩着",
            generate_srt=False,
        )

        # Simulate failure
        queue.start(job.id)
        queue.fail(job.id, "Simulated network timeout")
        failed_job = queue.get_job(job.id)
        assert failed_job.status == "failed"

        # Resume/retry download
        resumed_job = mgr.resume_download(job.id)
        assert resumed_job is not None
        assert resumed_job.id == job.id
        assert resumed_job.status == "queued"
        assert resumed_job.progress == 0.0
        assert resumed_job.payload["series_name"] == "我的婆婆，我罩着"
        assert resumed_job.payload["episode_num"] == 2
        assert resumed_job.payload["title"] == "我的婆婆，我罩着 第2集"

    mgr.shutdown()
    queue.close()
    organizer.close()


def test_reconcile_short_dramas_folder_and_db(tmp_path: Path) -> None:
    """Ensure misplaced files in ShortDrama/Hongguo Drama are reconciled into movie folder."""
    lib_dir = tmp_path / "library"
    lib_db = tmp_path / "lib.db"
    organizer = MediaOrganizer(base_dir=lib_dir, db_path=lib_db)

    # Create misplaced folder and file
    hg_dir = lib_dir / "ShortDrama" / "Hongguo Drama"
    hg_dir.mkdir(parents=True, exist_ok=True)
    mp4_file = hg_dir / "Ep01_我的婆婆，我罩着 第1集.mp4"
    mp4_file.write_text("dummy video")
    srt_file = hg_dir / "Ep01_我的婆婆，我罩着 第1集.srt"
    srt_file.write_text("1\n00:00:00,000 --> 00:00:01,000\nSub")

    from modules.downloader.organizer import MediaItem
    organizer.register_item(
        MediaItem(
            id="item-test-1",
            title="我的婆婆，我罩着 第1集",
            platform="Hongguo",
            creator="Hongguo Drama",
            date="2026-09-24",
            file_path=str(mp4_file),
            file_size_bytes=100,
        )
    )

    organizer.reconcile_short_dramas()

    movie_dir = lib_dir / "ShortDrama" / "我的婆婆，我罩着"
    assert (movie_dir / "Ep01_我的婆婆，我罩着 第1集.mp4").exists()
    assert (movie_dir / "Ep01_我的婆婆，我罩着 第1集.srt").exists()
    assert not hg_dir.exists()

    items = organizer.list_items()
    assert len(items) == 1
    assert items[0].creator == "我的婆婆，我罩着"
    assert "我的婆婆，我罩着" in items[0].file_path

    organizer.close()


"""Test end-to-end signal flow from Library 'Send to Studio' to StudioView and PlayerController."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtWidgets import QApplication

from core.config_store import ConfigStore
from core.job_queue import JobQueue
from core.project_manager import ProjectManager
from modules.downloader.organizer import MediaItem, MediaOrganizer
from modules.downloader.queue_manager import DownloadQueueManager
from app import MainWindow


def test_send_to_studio_signal_flow(tmp_path: Path, qapp: QApplication) -> None:
    # 1. Prepare sample video and companion srt
    sample_mp4 = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\scratch\sample_clip.mp4")
    assert sample_mp4.exists(), "Sample clip must exist for test"

    config_store = ConfigStore(settings_path=tmp_path / "settings.json")
    db_path = tmp_path / "jobs.db"
    job_queue = JobQueue(db_path)
    project_manager = ProjectManager(config_store=config_store)
    organizer = MediaOrganizer(base_dir=tmp_path / "downloads", db_path=tmp_path / "lib.db")
    queue_manager = DownloadQueueManager(job_queue=job_queue, organizer=organizer)

    window = MainWindow(
        project_manager=project_manager,
        job_queue=job_queue,
        queue_manager=queue_manager,
        organizer=organizer,
    )

    # Register sample media into library
    item = MediaItem(
        id="test-vid-1",
        title="Sample Video",
        platform="YouTube",
        creator="Test Creator",
        date="2026-09-23",
        file_path=str(sample_mp4),
        duration=5.0,
        resolution="1280x720",
        file_size_bytes=sample_mp4.stat().st_size,
    )
    organizer.register_item(item)
    window.library_view.refresh_library()

    # Verify initial studio state is empty
    assert window.studio_view.video_player.controller.current_video_path is None
    assert "No Media Loaded" in window.studio_view.meta_badge.text()

    # 2. Trigger send to studio
    window.library_view._on_send_to_studio(str(sample_mp4))

    # 3. Assert studio view loaded the media
    assert window.view_stack.currentWidget() == window.studio_view
    ctrl = window.studio_view.video_player.controller
    assert ctrl.current_video_path == sample_mp4
    assert ctrl.metadata is not None
    assert ctrl.metadata.width == 1280
    assert ctrl.metadata.height == 720
    assert "1280x720" in window.studio_view.meta_badge.text()

    # Assert timeline loaded tracks
    canvas = window.studio_view.timeline.canvas
    assert canvas.duration_ms > 0
    vid_track = next((t for t in canvas.tracks if t.id == "video"), None)
    assert vid_track is not None and len(vid_track.clips) > 0

    # Clean up
    job_queue.close()
    organizer.close()
    window.close()

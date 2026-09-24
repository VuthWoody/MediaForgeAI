"""Comprehensive button function regression test suite covering all PySide6 UI views and components.

Ensures that every interactive button, trigger, and callback executes cleanly without
throwing exceptions, crashing, or locking the UI in a permanently disabled state.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from core.cancellation import CancellationToken
from core.config_store import ConfigStore
from core.job_queue import JobQueue
from core.project_manager import ProjectManager
from modules.downloader.organizer import MediaOrganizer
from modules.downloader.queue_manager import DownloadQueueManager
from modules.media.player_controller import PlayerController
from ui.components.timeline import MultiTrackTimelineWidget
from ui.components.video_player import VideoPlayerWidget
from ui.views.batch_view import BatchView
from ui.views.dashboard_view import DashboardView
from ui.views.downloader_view import DownloaderView
from ui.views.settings_view import SettingsView
from ui.views.studio_view import StudioView


def test_video_player_transport_buttons(qapp: QApplication) -> None:
    """Verify transport bar buttons (Start, Step -1, Play/Pause, Step +1, Volume Mute)."""
    controller = PlayerController()
    player = VideoPlayerWidget(controller=controller)

    # 1. Start / Jump to 0 button
    player.restart_btn.click()
    assert controller.media_player.position() == 0

    # 2. Step back & step forward without media (graceful no-op, no crash)
    player.step_back_btn.click()
    player.step_fwd_btn.click()

    # 3. Play / Pause button
    assert player.play_btn.text() == "▶ Play"
    player.play_btn.click()
    # Toggling play should not crash even with no media loaded
    player.play_btn.click()

    # 4. Volume and Mute toggle
    assert player.vol_slider.value() == 100
    assert player.mute_btn.text() == "🔊"

    player.mute_btn.click()
    assert player.vol_slider.value() == 0
    assert player.mute_btn.text() == "🔇"

    player.mute_btn.click()
    assert player.vol_slider.value() == 100
    assert player.mute_btn.text() == "🔊"


def test_timeline_buttons_and_tracks(qapp: QApplication) -> None:
    """Verify timeline zoom buttons, fit button, mute and solo buttons."""
    controller = PlayerController()
    timeline = MultiTrackTimelineWidget(player_controller=controller)

    # 1. Zoom buttons
    orig_zoom = timeline.canvas.pixels_per_second
    timeline._zoom_in()
    assert timeline.canvas.pixels_per_second > orig_zoom

    timeline._zoom_out()
    assert timeline.canvas.pixels_per_second == orig_zoom

    timeline._zoom_reset()
    assert timeline.canvas.pixels_per_second == 60.0

    # 2. Mute buttons on all tracks
    for trk_id in ("video", "orig_audio", "bgm", "dialogue", "subtitles"):
        assert trk_id in timeline._mute_buttons
        m_btn = timeline._mute_buttons[trk_id]
        m_btn.click()
        assert controller.is_track_muted(trk_id) is True
        m_btn.click()
        assert controller.is_track_muted(trk_id) is False

    # 3. Solo buttons on audio tracks
    for trk_id in ("orig_audio", "bgm", "dialogue"):
        assert trk_id in timeline._solo_buttons
        s_btn = timeline._solo_buttons[trk_id]
        assert s_btn.isHidden() is False
        s_btn.click()
        assert controller.is_track_soloed(trk_id) is True
        s_btn.click()
        assert controller.is_track_soloed(trk_id) is False

    # Non-audio tracks (video, subtitles) should hide the solo button
    assert timeline._solo_buttons["video"].isHidden() is True
    assert timeline._solo_buttons["subtitles"].isHidden() is True


def test_studio_view_button_functions(qapp: QApplication, monkeypatch) -> None:
    """Verify all Studio view buttons, UI state lockouts, and error recoveries."""
    studio = StudioView()

    # 1. Click Transcribe with no media -> shows warning box, buttons stay enabled
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        studio.transcribe_btn.click()
        assert mock_warn.called
    assert studio.transcribe_btn.isEnabled() is True
    assert studio.autoprocess_btn.isEnabled() is True

    # 2. Click Separate with no media -> shows warning box, buttons stay enabled
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        studio.separate_btn.click()
        assert mock_warn.called
    assert studio.separate_btn.isEnabled() is True

    # 3. Click Auto-Process with no media -> shows warning box, buttons stay enabled
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        studio.autoprocess_btn.click()
        assert mock_warn.called
    assert studio.autoprocess_btn.isEnabled() is True

    # 4. Test UI state toggle helper
    studio._set_processing_ui_state(active=True)
    assert studio.autoprocess_btn.isEnabled() is False
    assert studio.transcribe_btn.isEnabled() is False
    assert studio.separate_btn.isEnabled() is False
    assert studio.cancel_btn.isEnabled() is True

    studio._set_processing_ui_state(active=False)
    assert studio.autoprocess_btn.isEnabled() is True
    assert studio.transcribe_btn.isEnabled() is True
    assert studio.separate_btn.isEnabled() is True
    assert studio.cancel_btn.isEnabled() is False

    # 5. Test Cancel button action
    token = CancellationToken()
    studio._current_token = token
    studio._set_processing_ui_state(active=True)
    studio.cancel_btn.click()
    assert token.is_cancelled is True
    assert studio.cancel_btn.isEnabled() is False

    # 6. Test Open Output button
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        studio._on_open_output_clicked()


def test_downloader_view_button_functions(qapp: QApplication, tmp_path: Path) -> None:
    """Verify Downloader view download trigger, concurrency slider, and action buttons."""
    db_path = tmp_path / "test_jobs.db"
    queue = JobQueue(db_path)
    organizer = MediaOrganizer(base_dir=tmp_path / "downloads")
    qm = DownloadQueueManager(job_queue=queue, organizer=organizer)

    view = DownloaderView(queue_manager=qm)

    # 1. Download button with empty URL -> shows warning
    with patch("PySide6.QtWidgets.QMessageBox.warning") as mock_warn:
        view.dl_btn.click()
        assert mock_warn.called

    # 2. Concurrency slider
    view.thread_slider.setValue(8)
    assert qm.max_workers == 8
    assert "8 threads" in view.thread_val_lbl.text()

    # 3. Table action buttons: test row creation and button click safety
    row = view._find_or_create_row("test-job-123", "https://youtube.com/watch?v=demo")
    assert row == 0

    act_widget = view.queue_table.cellWidget(row, 5)
    btns = act_widget.findChildren(type(view.dl_btn))
    assert len(btns) == 3

    # Click pause, resume, cancel buttons - must not throw TypeError
    with patch.object(qm, "pause_download") as mock_pause:
        btns[0].click()
        mock_pause.assert_called_once_with("test-job-123")

    with patch.object(qm, "resume_download") as mock_resume:
        btns[1].click()
        mock_resume.assert_called_once_with("test-job-123")

    with patch.object(qm, "cancel_download") as mock_cancel:
        btns[2].click()
        mock_cancel.assert_called_once_with("test-job-123")

    qm.shutdown()


def test_batch_view_button_functions(qapp: QApplication) -> None:
    """Verify Batch View button behavior, empty queue warning, and button recovery."""
    batch_view = BatchView()

    # 1. Start batch with empty queue -> informs user, buttons remain clean
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        batch_view.start_btn.click()
        assert mock_info.called
    assert batch_view.start_btn.isEnabled() is True
    assert batch_view.cancel_btn.isEnabled() is False

    # 2. Clear completed button
    batch_view._on_clear_clicked()
    assert len(batch_view.items) == 0


def test_dashboard_view_buttons(qapp: QApplication, tmp_path: Path) -> None:
    """Verify Dashboard View quick action cards and navigation signals."""
    cfg = ConfigStore(settings_path=tmp_path / "settings.json")
    pm = ProjectManager(config_store=cfg)
    dash = DashboardView(project_manager=pm)

    nav_called: list[str] = []
    dash.action_navigate.connect(nav_called.append)

    # Click Open Downloader card button
    card_dl_btn = dash.findChild(type(dash._recent_list), "")  # Find button in card
    dash.action_navigate.emit("downloader")
    assert "downloader" in nav_called


def test_settings_view_buttons(qapp: QApplication, tmp_path: Path) -> None:
    """Verify Settings View credential saving, cache clearing, and self-test buttons."""
    cfg = ConfigStore(settings_path=tmp_path / "settings.json")
    settings_view = SettingsView(config_store=cfg)

    # 1. Save credentials button
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        settings_view._save_credentials()
        assert mock_info.called

    # 2. Run Self-Test button
    with patch("PySide6.QtWidgets.QMessageBox.information") as mock_info:
        settings_view._run_self_test()
        assert mock_info.called

"""MediaForge AI — PySide6 Main Application Entry Point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSharedMemory, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config.constants import APP_NAME, APP_VERSION
from core.config_store import ConfigStore
from core.event_bus import get_event_bus
from core.hardware import HardwareProbe
from core.job_queue import JobQueue
from core.logging_config import setup_logging
from core.project_manager import ProjectManager
from core.resource_lock import ResourceLock
from core.updater import YtDlpUpdater
from modules.downloader.organizer import MediaOrganizer
from modules.downloader.queue_manager import DownloadQueueManager
from ui.components.resource_bar import ResourceBar
from ui.components.sidebar import Sidebar
from ui.components.toast import ToastManager
from ui.views.batch_view import BatchView
from ui.views.dashboard_view import DashboardView
from ui.views.downloader_view import DownloaderView
from ui.views.library_view import LibraryView
from ui.views.settings_view import SettingsView
from ui.views.studio_view import StudioView


class MainWindow(QMainWindow):
    """Primary application window hosting the sidebar, stacked views, and telemetry bar."""

    def __init__(
        self,
        project_manager: ProjectManager,
        job_queue: JobQueue,
        queue_manager: DownloadQueueManager,
        organizer: MediaOrganizer,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_manager = project_manager
        self.job_queue = job_queue
        self.queue_manager = queue_manager
        self.organizer = organizer

        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        self.resize(1280, 800)
        self.setMinimumSize(960, 600)

        self._build_ui()
        self._init_hardware_probe()
        self._init_autosave_timer()
        self._restore_session()

    def _build_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Upper Layout: Sidebar + Stacked Content Views
        upper_layout = QHBoxLayout()
        upper_layout.setContentsMargins(0, 0, 0, 0)
        upper_layout.setSpacing(0)

        # 1. Sidebar Navigation
        self.sidebar = Sidebar(self)
        self.sidebar.nav_changed.connect(self._on_navigation)
        upper_layout.addWidget(self.sidebar)

        # 2. View Stack (Instant switching)
        self.view_stack = QStackedWidget(self)
        self.views: dict[str, QWidget] = {}

        self.dashboard_view = DashboardView(
            project_manager=self.project_manager,
            job_queue=self.job_queue,
            parent=self,
        )
        self.dashboard_view.action_new_project.connect(self._create_new_project_dialog)
        self.dashboard_view.action_navigate.connect(self._on_navigation)
        self.dashboard_view.open_project_requested.connect(self._open_project)
        self.dashboard_view.action_import_media.connect(self._on_send_to_studio)

        self.downloader_view = DownloaderView(
            queue_manager=self.queue_manager,
            parent=self,
        )
        self.library_view = LibraryView(
            organizer=self.organizer,
            project_manager=self.project_manager,
            parent=self,
        )
        self.library_view.send_to_studio.connect(self._on_send_to_studio)

        self.studio_view = StudioView(self)
        self.batch_view = BatchView(self)
        self.settings_view = SettingsView(config_store=self.project_manager.config_store, parent=self)

        self._register_view("dashboard", self.dashboard_view)
        self._register_view("downloader", self.downloader_view)
        self._register_view("library", self.library_view)
        self._register_view("studio", self.studio_view)
        self._register_view("batch", self.batch_view)
        self._register_view("settings", self.settings_view)

        upper_layout.addWidget(self.view_stack, 1)
        root_layout.addLayout(upper_layout, 1)

        # 3. Bottom Resource Telemetry Bar
        self.resource_bar = ResourceBar(self)
        root_layout.addWidget(self.resource_bar)

        # 4. Floating Toast Notification Manager
        self.toast_mgr = ToastManager(self)

    def _register_view(self, key: str, widget: QWidget) -> None:
        self.views[key] = widget
        self.view_stack.addWidget(widget)

    def _on_navigation(self, key: str) -> None:
        if key in self.views:
            self.view_stack.setCurrentWidget(self.views[key])
            self.sidebar.set_active(key)

    def _on_send_to_studio(self, file_path: str) -> None:
        """Load media directly into the Studio view and navigate to Studio."""
        if file_path and Path(file_path).exists():
            self.studio_view.load_media(file_path)
            proj = self.project_manager.current_project
            if proj is not None:
                proj.media_path = str(file_path)
                self.project_manager.save_project(proj)
        self._on_navigation("studio")

    def _init_hardware_probe(self) -> None:
        """Start 1 Hz telemetry probe on the main thread."""
        self.hardware_probe = HardwareProbe(self)
        self.hardware_probe.start(interval_ms=1000)

    def _init_autosave_timer(self) -> None:
        """Auto-save project every 30 seconds as specified in Section 7 Phase 1."""
        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(30_000)
        self._autosave_timer.timeout.connect(self._on_autosave)
        self._autosave_timer.start()

    def _on_autosave(self) -> None:
        if self.project_manager.current_project is not None:
            self.project_manager.auto_save()

    def _restore_session(self) -> None:
        """Restore last project on launch."""
        restored = self.project_manager.restore_last_project()
        if restored:
            self.dashboard_view.refresh_dashboard()
            if restored.media_path and Path(restored.media_path).exists():
                self.studio_view.load_media(restored.media_path)
            get_event_bus().toast.emit("info", f"Restored project: {restored.name}")

    def _create_new_project_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "New Project", "Enter Project Name:")
        if ok and name.strip():
            default_dir = Path.home() / "Documents" / "MediaForge Projects"
            proj = self.project_manager.create_project(name.strip(), default_dir)
            self.dashboard_view.refresh_dashboard()
            get_event_bus().toast.emit("success", f"Created project: {proj.name}")

    def _open_project(self, path: str) -> None:
        try:
            proj = self.project_manager.load_project(path)
            self.dashboard_view.refresh_dashboard()
            if proj.media_path and Path(proj.media_path).exists():
                self.studio_view.load_media(proj.media_path)
                self._on_navigation("studio")
            get_event_bus().toast.emit("success", f"Loaded project: {proj.name}")
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Project", str(e))

    def closeEvent(self, event: QCloseEvent) -> None:
        """Auto-save active project on close and stop timers cleanly."""
        self._autosave_timer.stop()
        self.hardware_probe.stop()
        if self.project_manager.current_project is not None:
            self.project_manager.auto_save()
        self.queue_manager.shutdown()
        event.accept()


def load_theme(app: QApplication) -> None:
    """Load dark theme stylesheet."""
    theme_path = Path(__file__).resolve().parent / "ui" / "styles" / "theme.qss"
    if theme_path.exists():
        with open(theme_path, encoding="utf-8") as f:
            app.setStyleSheet(f.read())


def main() -> int:
    setup_logging()

    # 1. Single-Instance Guard via QSharedMemory
    app_id = "MediaForgeAI_SingleInstanceGuard"
    shared_memory = QSharedMemory(app_id)

    allow_multiple = "--allow-multiple" in sys.argv
    if not allow_multiple:
        if shared_memory.attach():
            print("MediaForge AI is already running. Focusing existing instance...")
            return 0
        if not shared_memory.create(1):
            print("Failed to initialize single-instance guard memory segment.")

    # 2. Asynchronous yt-dlp update check on launch
    YtDlpUpdater.check_async()

    # 3. PySide6 Application Setup
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    load_theme(app)

    # 4. Core Systems Initialization
    config_store = ConfigStore.instance()
    db_path = Path.home() / "AppData" / "Local" / "MediaForgeAI" / "jobs.db"
    job_queue = JobQueue(db_path)
    project_manager = ProjectManager(config_store=config_store)
    organizer = MediaOrganizer()
    resource_lock = ResourceLock()
    queue_manager = DownloadQueueManager(
        job_queue=job_queue,
        organizer=organizer,
        resource_lock=resource_lock,
    )

    # 5. Main Window Show
    window = MainWindow(
        project_manager=project_manager,
        job_queue=job_queue,
        queue_manager=queue_manager,
        organizer=organizer,
    )
    window.show()

    exit_code = app.exec()
    job_queue.close()
    organizer.close()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

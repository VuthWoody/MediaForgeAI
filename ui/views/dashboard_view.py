"""Modern professional studio dashboard view for MediaForge AI."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from core.event_bus import get_event_bus
from core.job_queue import JobQueue
from core.project_manager import ProjectManager


class DashboardView(QWidget):
    """Studio dashboard showcasing quick actions, recent projects, and active job status."""

    action_new_project = Signal()
    action_import_media = Signal(str)  # Emits chosen media file path
    action_navigate = Signal(str)  # target view key
    open_project_requested = Signal(str)  # project directory

    def __init__(
        self,
        project_manager: ProjectManager,
        job_queue: JobQueue | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_manager = project_manager
        self.job_queue = job_queue
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(24)

        # 1. Header Banner
        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Welcome to MediaForge AI")
        title.setProperty("class", "title")
        title.setStyleSheet("font-size: 22px; font-weight: 800; color: #ffffff;")
        subtitle = QLabel("AI video translation, expressive dubbing, and multi-platform media downloader.")
        subtitle.setStyleSheet("color: #9ca3af; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. Quick Action Cards (Grid)
        actions_grid = QGridLayout()
        actions_grid.setSpacing(16)

        # Card A: New Project
        card_new = QFrame()
        card_new.setProperty("class", "card")
        c1_layout = QVBoxLayout(card_new)
        c1_title = QLabel("⚡ New Project")
        c1_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        c1_desc = QLabel("Create an end-to-end studio translation & dubbing project.")
        c1_desc.setWordWrap(True)
        c1_desc.setStyleSheet("color: #9ca3af; font-size: 12px;")
        c1_btn = QPushButton("➕ Create Project")
        c1_btn.setProperty("class", "primary")
        c1_btn.setToolTip("Start a new video translation and dubbing workspace")
        c1_btn.clicked.connect(self.action_new_project.emit)
        c1_layout.addWidget(c1_title)
        c1_layout.addWidget(c1_desc)
        c1_layout.addStretch()
        c1_layout.addWidget(c1_btn)

        # Card B: Import Media
        card_import = QFrame()
        card_import.setProperty("class", "card")
        c2_layout = QVBoxLayout(card_import)
        c2_title = QLabel("🎬 Import Media")
        c2_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        c2_desc = QLabel("Load an existing video or audio file directly into the studio.")
        c2_desc.setWordWrap(True)
        c2_desc.setStyleSheet("color: #9ca3af; font-size: 12px;")
        c2_btn = QPushButton("📁 Browse File...")
        c2_btn.setToolTip("Open a video file from your computer")
        c2_btn.clicked.connect(self._on_import_clicked)
        c2_layout.addWidget(c2_title)
        c2_layout.addWidget(c2_desc)
        c2_layout.addStretch()
        c2_layout.addWidget(c2_btn)

        # Card C: Download Media
        card_dl = QFrame()
        card_dl.setProperty("class", "card")
        c3_layout = QVBoxLayout(card_dl)
        c3_title = QLabel("📥 Downloader")
        c3_title.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        c3_desc = QLabel("Grab videos from YouTube, TikTok, Douyin, or 20+ platforms.")
        c3_desc.setWordWrap(True)
        c3_desc.setStyleSheet("color: #9ca3af; font-size: 12px;")
        c3_btn = QPushButton("📥 Open Downloader")
        c3_btn.setToolTip("Navigate to the video downloader")
        c3_btn.clicked.connect(lambda: self.action_navigate.emit("downloader"))
        c3_layout.addWidget(c3_title)
        c3_layout.addWidget(c3_desc)
        c3_layout.addStretch()
        c3_layout.addWidget(c3_btn)

        actions_grid.addWidget(card_new, 0, 0)
        actions_grid.addWidget(card_import, 0, 1)
        actions_grid.addWidget(card_dl, 0, 2)
        layout.addLayout(actions_grid)

        # 3. Two Columns: Recent Projects (Left) vs Telemetry & Job Queue (Right)
        body_layout = QHBoxLayout()
        body_layout.setSpacing(20)

        # Left Column: Recent Projects
        left_box = QVBoxLayout()
        left_box.setSpacing(10)
        recent_hdr = QLabel("Recent Projects")
        recent_hdr.setStyleSheet("font-size: 16px; font-weight: 700; color: #ffffff;")
        left_box.addWidget(recent_hdr)

        self._recent_list = QListWidget()
        self._recent_list.setStyleSheet("""
            QListWidget {
                background-color: #161922;
                border: 1px solid #282e3f;
                border-radius: 8px;
                padding: 6px;
            }
            QListWidget::item {
                background-color: #1c202d;
                border-radius: 6px;
                padding: 10px 12px;
                margin-bottom: 6px;
                color: #e5e7eb;
            }
            QListWidget::item:hover {
                background-color: #242a3b;
            }
        """)
        self._recent_list.itemDoubleClicked.connect(self._on_recent_item_double_clicked)
        left_box.addWidget(self._recent_list)
        body_layout.addLayout(left_box, 60)

        # Right Column: System Telemetry + Active Jobs Card
        right_box = QVBoxLayout()
        right_box.setSpacing(16)

        # Card: Current Active Project
        self._active_proj_card = QFrame()
        self._active_proj_card.setProperty("class", "card")
        ap_layout = QVBoxLayout(self._active_proj_card)
        ap_layout.setSpacing(6)
        ap_lbl = QLabel("Current Project")
        ap_lbl.setStyleSheet("color: #818cf8; font-size: 11px; font-weight: 700; text-transform: uppercase;")
        self._active_proj_name = QLabel("No active project loaded")
        self._active_proj_name.setStyleSheet("font-size: 15px; font-weight: 700; color: #ffffff;")
        self._active_proj_info = QLabel("Create or open a project to begin.")
        self._active_proj_info.setStyleSheet("color: #9ca3af; font-size: 12px;")
        ap_layout.addWidget(ap_lbl)
        ap_layout.addWidget(self._active_proj_name)
        ap_layout.addWidget(self._active_proj_info)
        right_box.addWidget(self._active_proj_card)

        # Card: Active Pipeline Jobs
        self._jobs_card = QFrame()
        self._jobs_card.setProperty("class", "card")
        jc_layout = QVBoxLayout(self._jobs_card)
        jc_title = QLabel("Pipeline Queue Status")
        jc_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #ffffff;")
        self._jobs_summary = QLabel("No active or queued background jobs.")
        self._jobs_summary.setStyleSheet("color: #9ca3af; font-size: 12px;")
        jc_layout.addWidget(jc_title)
        jc_layout.addWidget(self._jobs_summary)
        right_box.addWidget(self._jobs_card)
        right_box.addStretch()

        body_layout.addLayout(right_box, 40)
        layout.addLayout(body_layout)

        scroll.setWidget(container)
        self._scroll = scroll
        self._container = container

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        self.refresh_dashboard()

    def _connect_signals(self) -> None:
        get_event_bus().job_queued.connect(lambda _: self._refresh_jobs_status())
        get_event_bus().job_completed.connect(lambda _, __: self._refresh_jobs_status())
        get_event_bus().job_failed.connect(lambda _, __: self._refresh_jobs_status())

    def refresh_dashboard(self) -> None:
        """Refresh current project status and recent list."""
        curr = self.project_manager.current_project
        if curr is not None:
            self._active_proj_name.setText(curr.name)
            self._active_proj_info.setText(f"Target: {curr.target_language.upper()} • Path: {curr.project_dir}")
        else:
            self._active_proj_name.setText("No active project loaded")
            self._active_proj_info.setText("Create or open a project to begin.")

        self._refresh_recent_projects()
        self._refresh_jobs_status()

    def _refresh_recent_projects(self) -> None:
        self._recent_list.clear()
        last_dir = self.project_manager.config_store.get("last_project_dir")
        if last_dir and Path(last_dir).exists():
            item = QListWidgetItem(f"📁 {Path(last_dir).name}  (Recent)\n{last_dir}")
            item.setData(Qt.ItemDataRole.UserRole, last_dir)
            self._recent_list.addItem(item)
        else:
            item = QListWidgetItem("No recent projects found. Click 'New Project' above.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recent_list.addItem(item)

    def _refresh_jobs_status(self) -> None:
        if self.job_queue is not None:
            running = self.job_queue.list_jobs(status="running")
            queued = self.job_queue.list_jobs(status="queued")
            completed = self.job_queue.list_jobs(status="completed")
            self._jobs_summary.setText(
                f"Running: {len(running)} | Queued: {len(queued)} | Completed: {len(completed)}"
            )

    def _on_import_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Media File",
            "",
            "Video & Audio Files (*.mp4 *.mkv *.mov *.avi *.webm *.mp3 *.wav *.m4a);;All Files (*.*)",
        )
        if file_path:
            self.action_import_media.emit(file_path)

    def _on_recent_item_double_clicked(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.open_project_requested.emit(str(path))

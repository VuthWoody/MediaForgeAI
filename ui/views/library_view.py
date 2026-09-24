"""Media library view organizing downloaded assets by platform, creator, and date with 'Send to Studio' action."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.event_bus import get_event_bus
from core.project_manager import ProjectManager
from modules.downloader.organizer import MediaOrganizer


class LibraryView(QWidget):
    """Media Library interface displaying organized media with 'Send to Studio' capability."""

    send_to_studio = Signal(str)  # Emits media file path to load into active project

    def __init__(
        self,
        organizer: MediaOrganizer,
        project_manager: ProjectManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.organizer = organizer
        self.project_manager = project_manager
        self._build_ui()
        self._connect_signals()
        self.refresh_library()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # 1. Header
        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Media Library")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        desc = QLabel("Assets automatically organized by Platform -> Creator -> Date.")
        desc.setStyleSheet("color: #9ca3af; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)

        # 2. Filter & Search Bar
        filter_row = QHBoxLayout()
        filter_row.setSpacing(12)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by video title or creator...")
        self.search_input.textChanged.connect(self.refresh_library)
        filter_row.addWidget(self.search_input, 1)

        self.platform_filter = QComboBox()
        self.platform_filter.addItems(["All Platforms", "YouTube", "TikTok", "Douyin", "Bilibili", "Hongguo", "Generic"])
        self.platform_filter.currentTextChanged.connect(self.refresh_library)
        filter_row.addWidget(self.platform_filter)

        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_library)
        filter_row.addWidget(refresh_btn)

        layout.addLayout(filter_row)

        # 3. Media Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Title", "Platform", "Creator", "Date", "Size", "Status", "Actions"
        ])

        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #161922;
                border: 1px solid #282e3f;
                border-radius: 8px;
                gridline-color: #222736;
            }
            QHeaderView::section {
                background-color: #1c202d;
                color: #9ca3af;
                font-weight: 600;
                font-size: 12px;
                padding: 6px;
                border: none;
                border-bottom: 1px solid #282e3f;
            }
        """)
        layout.addWidget(self.table)

    def _connect_signals(self) -> None:
        get_event_bus().job_completed.connect(lambda _, __: self.refresh_library())

    def refresh_library(self) -> None:
        """Query catalog with current search and platform filters."""
        self.organizer.reconcile_short_dramas()
        query = self.search_input.text().strip() or None
        plat_sel = self.platform_filter.currentText()
        platform = None if plat_sel == "All Platforms" else plat_sel

        items = self.organizer.list_items(platform=platform, search_query=query)

        self.table.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table.setItem(row, 0, QTableWidgetItem(f"🎬 {item.title}"))
            self.table.setItem(row, 1, QTableWidgetItem(item.platform))
            self.table.setItem(row, 2, QTableWidgetItem(item.creator))
            self.table.setItem(row, 3, QTableWidgetItem(item.date))

            mb = item.file_size_bytes / (1024 * 1024)
            self.table.setItem(row, 4, QTableWidgetItem(f"{mb:.1f} MB"))
            self.table.setItem(row, 5, QTableWidgetItem(item.processing_status))

            # Actions container
            action_widget = QWidget()
            a_layout = QHBoxLayout(action_widget)
            a_layout.setContentsMargins(4, 2, 4, 2)
            a_layout.setSpacing(6)

            # "Send to Studio" button
            send_btn = QPushButton("🚀 Send to Studio")
            send_btn.setProperty("class", "primary")
            send_btn.setToolTip("Open video in AI Studio for editing and processing")
            send_btn.clicked.connect(lambda checked=False, p=item.file_path: self._on_send_to_studio(p))

            # "Open Folder" button
            folder_btn = QPushButton("📁 Folder")
            folder_btn.setToolTip("Open containing folder in File Explorer")
            folder_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e2433;
                    color: #cbd5e1;
                    border: 1px solid #2d3748;
                    border-radius: 4px;
                    padding: 4px 10px;
                    font-size: 11px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #2e384d;
                    color: #ffffff;
                }
            """)
            folder_btn.clicked.connect(lambda checked=False, p=item.file_path: self._open_file_folder(p))

            a_layout.addWidget(send_btn)
            a_layout.addWidget(folder_btn)
            self.table.setCellWidget(row, 6, action_widget)

    def _on_send_to_studio(self, file_path: str) -> None:
        """Load selected media into active project and broadcast signal."""
        path = Path(file_path)
        if not path.exists():
            QMessageBox.warning(self, "File Not Found", f"Media file does not exist at:\n{file_path}")
            return

        # Assign to active project if present, or create default project
        if self.project_manager.current_project is None:
            default_dir = Path.home() / "Documents" / "MediaForge Projects"
            self.project_manager.create_project(path.stem, default_dir)

        proj = self.project_manager.current_project
        if proj is not None:
            proj.media_path = str(path)
            self.project_manager.save_project(proj)
            get_event_bus().toast.emit("success", f"Loaded '{path.name}' into Studio Project '{proj.name}'.")
            self.send_to_studio.emit(str(path))

    def _open_file_folder(self, file_path: str) -> None:
        p = Path(file_path)
        if p.exists():
            subprocess.run(["explorer", "/select,", str(p)], check=False)
        elif p.parent.exists():
            subprocess.run(["explorer", str(p.parent)], check=False)
        else:
            short_drama_base = self.organizer.base_dir / "ShortDrama"
            if short_drama_base.exists():
                matches = list(short_drama_base.rglob(p.name))
                if matches and matches[0].exists():
                    subprocess.run(["explorer", "/select,", str(matches[0])], check=False)
                    return
            QMessageBox.warning(self, "Folder Not Found", f"Media file or folder not found at:\n{file_path}")

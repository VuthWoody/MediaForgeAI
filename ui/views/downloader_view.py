"""Downloader view module with multi-platform URL detection, queue table, and thread controls."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.event_bus import get_event_bus
from modules.downloader.hongguo import HongguoDramaInfo, HongguoExtractor
from modules.downloader.queue_manager import DownloadQueueManager
from modules.downloader.scraper import _detect_platform


class CountdownShutdownDialog(QDialog):
    """60-second countdown dialog for auto-shutdown with NO pre-selected as per Section 7 Phase 2."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Auto-Shutdown Scheduled")
        self.setFixedSize(380, 160)
        self.remaining_seconds = 60

        layout = QVBoxLayout(self)
        self.info_lbl = QLabel(f"All downloads finished.\nComputer will shut down in {self.remaining_seconds} seconds.")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_lbl.setStyleSheet("font-size: 14px; color: #f3f4f6; font-weight: 600;")
        layout.addWidget(self.info_lbl)

        # Buttons with NO pre-selected
        btn_box = QDialogButtonBox()
        self.cancel_btn = btn_box.addButton("Cancel (No)", QDialogButtonBox.ButtonRole.RejectRole)
        self.confirm_btn = btn_box.addButton("Shutdown Now", QDialogButtonBox.ButtonRole.AcceptRole)

        # Pre-select NO
        self.cancel_btn.setDefault(True)
        self.cancel_btn.setFocus()

        btn_box.rejected.connect(self.reject)
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)

        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._on_tick)
        self.timer.start()

    def _on_tick(self) -> None:
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.timer.stop()
            self.accept()
        else:
            self.info_lbl.setText(
                f"All downloads finished.\nComputer will shut down in {self.remaining_seconds} seconds."
            )


class HongguoDramaDialog(QDialog):
    """Dialog for fetching a Hongguo drama, selecting all or specific episodes, and configuring SRT subtitle generation."""

    def __init__(
        self,
        queue_manager: DownloadQueueManager,
        initial_input: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.queue_manager = queue_manager
        self.drama_info: HongguoDramaInfo | None = None
        self.setWindowTitle("Hongguo Short Drama (红果短剧) Batch Downloader")
        self.setMinimumSize(580, 520)
        self.resize(620, 560)
        self._build_ui()
        if initial_input:
            self.input_field.setText(initial_input)
            self._fetch_drama()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header
        h_layout = QVBoxLayout()
        h_layout.setSpacing(4)
        t_lbl = QLabel("Hongguo Short Drama Downloader")
        t_lbl.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        sub_lbl = QLabel("Download complete dramas or selected episodes with .srt subtitles (hongguoduanju.com)")
        sub_lbl.setStyleSheet("color: #9ca3af; font-size: 12px;")
        h_layout.addWidget(t_lbl)
        h_layout.addWidget(sub_lbl)
        layout.addLayout(h_layout)

        # Search / URL input row
        input_row = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Enter drama URL or drama name (e.g. 咱家剑宗团宠小师妹)...")
        self.input_field.returnPressed.connect(self._fetch_drama)
        self.fetch_btn = QPushButton("🔍 Fetch Drama")
        self.fetch_btn.setProperty("class", "primary")
        self.fetch_btn.setToolTip("Search drama title or parse Hongguo URL")
        self.fetch_btn.clicked.connect(self._fetch_drama)
        input_row.addWidget(self.input_field, 1)
        input_row.addWidget(self.fetch_btn)
        layout.addLayout(input_row)

        # Status / Fetching progress label
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #818cf8; font-size: 12px; font-style: italic;")
        layout.addWidget(self.status_lbl)

        # Drama Info Card (Frame)
        self.info_card = QFrame()
        self.info_card.setProperty("class", "card")
        self.info_card.setStyleSheet("""
            QFrame.card {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 14px;
            }
            QLabel {
                background: transparent;
            }
        """)
        c_layout = QVBoxLayout(self.info_card)
        c_layout.setSpacing(8)

        self.drama_title_lbl = QLabel("No drama loaded yet")
        self.drama_title_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #f3f4f6; background: transparent;")
        self.ep_stats_lbl = QLabel("")
        self.ep_stats_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #34d399; background: transparent;")
        self.drama_intro_lbl = QLabel("")
        self.drama_intro_lbl.setWordWrap(True)
        self.drama_intro_lbl.setStyleSheet("color: #9ca3af; font-size: 12px; background: transparent;")

        c_layout.addWidget(self.drama_title_lbl)
        c_layout.addWidget(self.ep_stats_lbl)
        c_layout.addWidget(self.drama_intro_lbl)
        self.info_card.setVisible(False)
        layout.addWidget(self.info_card)

        # Episode Selection Group
        self.selection_card = QFrame()
        self.selection_card.setProperty("class", "card")
        self.selection_card.setStyleSheet("""
            QFrame.card {
                background-color: #161b22;
                border: 1px solid #30363d;
                border-radius: 8px;
                padding: 14px;
            }
            QLabel, QRadioButton, QCheckBox {
                background: transparent;
            }
        """)
        s_layout = QVBoxLayout(self.selection_card)
        s_layout.setSpacing(10)

        sel_title = QLabel("Episode Selection:")
        sel_title.setStyleSheet("font-size: 13px; font-weight: 700; color: #e5e7eb;")
        s_layout.addWidget(sel_title)

        self.radio_all = QRadioButton("Download All Available Web Episodes")
        self.radio_all.setChecked(True)
        self.radio_all.toggled.connect(self._on_radio_toggled)
        s_layout.addWidget(self.radio_all)

        range_row = QHBoxLayout()
        self.radio_range = QRadioButton("Specific Episode Range:")
        self.radio_range.toggled.connect(self._on_radio_toggled)
        self.range_input = QLineEdit("1-3")
        self.range_input.setPlaceholderText("e.g. 1-3, 1, 3, 5")
        self.range_input.setEnabled(False)
        range_row.addWidget(self.radio_range)
        range_row.addWidget(self.range_input, 1)
        s_layout.addLayout(range_row)

        hint_lbl = QLabel("Hint: Hongguo web provides direct streaming for first 3 episodes (e.g. 1-3).")
        hint_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")
        s_layout.addWidget(hint_lbl)

        # Subtitle Option
        self.srt_chk = QCheckBox("Generate .srt Subtitles (faster-whisper AI, zero API cost)")
        self.srt_chk.setChecked(True)
        self.srt_chk.setStyleSheet("color: #f3f4f6; font-size: 12px; font-weight: 600;")
        s_layout.addWidget(self.srt_chk)

        self.selection_card.setVisible(False)
        layout.addWidget(self.selection_card)

        layout.addStretch()

        # Action Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(cancel_btn)

        self.enqueue_btn = QPushButton("📥 Enqueue Episodes")
        self.enqueue_btn.setProperty("class", "primary")
        self.enqueue_btn.setToolTip("Add selected episodes to download queue")
        self.enqueue_btn.setStyleSheet("""
            background-color: #e11d48;
            color: #ffffff;
            font-weight: 700;
            padding: 8px 18px;
            border-radius: 6px;
        """)
        self.enqueue_btn.setEnabled(False)
        self.enqueue_btn.clicked.connect(self._enqueue_episodes)
        btn_box.addWidget(self.enqueue_btn)

        layout.addLayout(btn_box)

    def _on_radio_toggled(self) -> None:
        self.range_input.setEnabled(self.radio_range.isChecked())

    def _fetch_drama(self) -> None:
        query = self.input_field.text().strip()
        if not query:
            QMessageBox.warning(self, "Input Required", "Please enter a drama name or URL.")
            return

        self.status_lbl.setText("Fetching drama information from Hongguo...")
        self.fetch_btn.setEnabled(False)

        try:
            info = HongguoExtractor.get_drama_info(query)
            self.drama_info = info
            self.drama_title_lbl.setText(f"🎬 {info.series_name}")
            cast_info = ""
            if info.characters:
                cast_names = ", ".join(c.get("display", "") for c in info.characters[:6])
                cast_info = f"\n🎭 Cast: {cast_names}" + ("..." if len(info.characters) > 6 else "")

            self.ep_stats_lbl.setText(
                f"Total Episodes: {info.episode_cnt} | Directly Accessible on Web: {info.accessible_episode_cnt}{cast_info}"
            )
            intro = info.series_intro[:200] + ("..." if len(info.series_intro) > 200 else "")
            self.drama_intro_lbl.setText(intro or "No synopsis available.")

            self.info_card.setVisible(True)
            self.selection_card.setVisible(True)
            self.enqueue_btn.setEnabled(True)
            self.status_lbl.setText("Drama details loaded successfully.")

            # Default range to accessible episodes
            if info.accessible_episode_cnt > 1:
                self.range_input.setText(f"1-{info.accessible_episode_cnt}")
            else:
                self.range_input.setText("1")

            self.enqueue_btn.setText(f"Enqueue All ({info.accessible_episode_cnt} Episodes)")

        except Exception as e:
            self.status_lbl.setText(f"Failed to fetch drama: {e}")
            QMessageBox.critical(self, "Fetch Failed", f"Could not load drama:\n{e}")
        finally:
            self.fetch_btn.setEnabled(True)

    def _enqueue_episodes(self) -> None:
        if not self.drama_info:
            return

        if self.radio_all.isChecked():
            ep_nums = list(range(1, self.drama_info.accessible_episode_cnt + 1))
        else:
            ep_nums = HongguoExtractor.parse_episode_range(
                self.range_input.text(), self.drama_info.episode_cnt
            )

        if not ep_nums:
            QMessageBox.warning(self, "Invalid Selection", "No valid episodes selected.")
            return

        gen_srt = self.srt_chk.isChecked()
        characters = getattr(self.drama_info, "characters", []) or []
        count = 0

        for num in ep_nums:
            vid = ""
            title = f"{self.drama_info.series_name} 第{num}集"
            for ep in self.drama_info.episodes:
                if ep.episode_num == num:
                    vid = ep.vid
                    title = ep.title
                    break

            self.queue_manager.enqueue_hongguo_episode(
                series_id=self.drama_info.series_id,
                episode_num=num,
                vid=vid,
                title=title,
                series_name=self.drama_info.series_name,
                generate_srt=gen_srt,
                characters=characters,
            )
            count += 1

        get_event_bus().toast.emit("success", f"Enqueued {count} Hongguo episode(s) with subtitles={gen_srt}.")
        self.accept()


class DownloaderView(QWidget):
    """Full-featured multi-platform downloader with queue management, format selection, and thread controls."""

    def __init__(
        self,
        queue_manager: DownloadQueueManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.queue_manager = queue_manager
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(18)

        # 1. Header
        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("Multi-Platform Media Downloader")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #ffffff;")
        desc = QLabel("Supports YouTube, TikTok, Douyin, Bilibili, and 20+ platforms with automatic platform detection.")
        desc.setStyleSheet("color: #9ca3af; font-size: 13px;")
        header.addWidget(title)
        header.addWidget(desc)
        layout.addLayout(header)

        # 2. URL Input Card
        card = QFrame()
        card.setProperty("class", "card")
        c_layout = QVBoxLayout(card)
        c_layout.setSpacing(12)

        # URL + Platform Detection row
        input_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("Paste video URL (YouTube, TikTok, Douyin mobile-share link, etc.)...")
        self.url_input.textChanged.connect(self._on_url_changed)

        self.platform_badge = QLabel("Generic")
        self.platform_badge.setStyleSheet("""
            background-color: #23283b;
            color: #818cf8;
            font-weight: 700;
            font-size: 11px;
            padding: 4px 10px;
            border-radius: 4px;
        """)

        self.dl_btn = QPushButton("📥 Download Media")
        self.dl_btn.setProperty("class", "primary")
        self.dl_btn.setToolTip("Start downloading video or audio stream")
        self.dl_btn.clicked.connect(self._start_download)

        input_row.addWidget(self.url_input, 1)
        input_row.addWidget(self.platform_badge)
        input_row.addWidget(self.dl_btn)
        c_layout.addLayout(input_row)

        # Options Row: Quality, Stream Sniffer, Subtitles, Thumbnails
        opts_row = QHBoxLayout()
        opts_row.setSpacing(16)

        # Quality selector
        lbl_q = QLabel("Quality:")
        lbl_q.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems([
            "Best Video + Audio Merged (1080p+)",
            "High Quality (720p)",
            "Audio Only (Best Quality)",
        ])
        opts_row.addWidget(lbl_q)
        opts_row.addWidget(self.quality_combo)

        # Checkboxes
        self.sniffer_chk = QCheckBox("Mobile Stream Sniffer (Playwright)")
        self.sniffer_chk.setToolTip("Recommended for Douyin, Hongguo, or mobile short links")
        self.subs_chk = QCheckBox("Subtitles")
        self.subs_chk.setChecked(True)
        self.thumb_chk = QCheckBox("Thumbnail")
        self.thumb_chk.setChecked(True)

        opts_row.addWidget(self.sniffer_chk)
        opts_row.addWidget(self.subs_chk)
        opts_row.addWidget(self.thumb_chk)
        opts_row.addStretch()

        # Bulk Import Button
        bulk_btn = QPushButton("📋 Bulk URLs...")
        bulk_btn.setToolTip("Paste and download multiple video URLs at once")
        bulk_btn.clicked.connect(self._open_bulk_dialog)
        opts_row.addWidget(bulk_btn)

        # Hongguo Short Drama Batch Button
        hg_btn = QPushButton("🎭 Hongguo Drama...")
        hg_btn.setStyleSheet("""
            background-color: #be123c;
            color: #ffffff;
            font-weight: 600;
            font-size: 12px;
            padding: 4px 12px;
            border-radius: 4px;
        """)
        hg_btn.setToolTip("Batch download complete dramas or episodes with .srt subtitles from hongguoduanju.com")
        hg_btn.clicked.connect(lambda: self._open_hongguo_dialog())
        opts_row.addWidget(hg_btn)

        c_layout.addLayout(opts_row)
        layout.addWidget(card)

        # 3. Controls & Concurrency Slider Row
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(16)

        lbl_threads = QLabel("Download Workers:")
        lbl_threads.setStyleSheet("color: #9ca3af; font-size: 12px; font-weight: 600;")
        self.thread_slider = QSlider(Qt.Orientation.Horizontal)
        self.thread_slider.setRange(1, 16)
        self.thread_slider.setValue(self.queue_manager.max_workers)
        self.thread_slider.setFixedWidth(140)
        self.thread_val_lbl = QLabel(f"{self.queue_manager.max_workers} threads")
        self.thread_val_lbl.setStyleSheet("color: #e5e7eb; font-size: 12px;")
        self.thread_slider.valueChanged.connect(self._on_thread_slider_changed)

        ctrl_row.addWidget(lbl_threads)
        ctrl_row.addWidget(self.thread_slider)
        ctrl_row.addWidget(self.thread_val_lbl)

        ctrl_row.addStretch()

        # Auto-shutdown checkbox
        self.auto_shutdown_chk = QCheckBox("Auto-shutdown when finished")
        self.auto_shutdown_chk.setStyleSheet("color: #9ca3af; font-size: 12px;")
        ctrl_row.addWidget(self.auto_shutdown_chk)

        # Output Folder Display
        lbl_out = QLabel("Output Folder:")
        lbl_out.setStyleSheet("color: #9ca3af; font-size: 12px;")
        self.folder_lbl = QLabel(str(self.queue_manager.organizer.base_dir))
        self.folder_lbl.setStyleSheet("color: #818cf8; font-size: 12px;")
        browse_btn = QPushButton("📁 Browse...")
        browse_btn.setToolTip("Select destination download directory")
        browse_btn.clicked.connect(self._change_output_dir)
        ctrl_row.addWidget(lbl_out)
        ctrl_row.addWidget(self.folder_lbl)
        ctrl_row.addWidget(browse_btn)

        layout.addLayout(ctrl_row)

        # 4. Downloads Queue Table
        self.queue_table = QTableWidget()
        self.queue_table.setColumnCount(6)
        self.queue_table.setHorizontalHeaderLabels([
            "Job ID", "Target URL / Title", "Platform", "Progress", "Status", "Actions"
        ])
        header_view = self.queue_table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.queue_table.setColumnWidth(3, 160)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.queue_table.setStyleSheet("""
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
        layout.addWidget(self.queue_table)

    def _connect_signals(self) -> None:
        bus = get_event_bus()
        bus.job_queued.connect(self._on_job_queued)
        bus.job_progress.connect(self._on_job_progress)
        bus.job_completed.connect(self._on_job_completed)
        bus.job_failed.connect(self._on_job_failed)
        bus.job_cancelled.connect(self._on_job_cancelled)

    def _on_url_changed(self, text: str) -> None:
        platform = _detect_platform(text)
        self.platform_badge.setText(platform)
        if platform in ("Douyin", "Hongguo"):
            self.sniffer_chk.setChecked(True)

    def _on_thread_slider_changed(self, val: int) -> None:
        self.thread_val_lbl.setText(f"{val} threads")
        self.queue_manager.set_max_workers(val)

    def _start_download(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Invalid URL", "Please enter a media URL to download.")
            return

        if HongguoExtractor.is_hongguo_url(url):
            self.url_input.clear()
            self._open_hongguo_dialog(initial_url=url)
            return

        fmt = "bestvideo+bestaudio/best"
        q_idx = self.quality_combo.currentIndex()
        if q_idx == 1:
            fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif q_idx == 2:
            fmt = "bestaudio/best"

        self.queue_manager.enqueue_download(
            url=url,
            format_spec=fmt,
            use_sniffer=self.sniffer_chk.isChecked(),
        )
        self.url_input.clear()
        get_event_bus().toast.emit("info", "Media download task enqueued.")

    def _open_hongguo_dialog(self, initial_url: str = "") -> None:
        dialog = HongguoDramaDialog(self.queue_manager, initial_input=initial_url, parent=self)
        dialog.exec()

    def _open_bulk_dialog(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Bulk URL Import")
        dialog.setFixedSize(500, 360)
        d_layout = QVBoxLayout(dialog)
        d_layout.addWidget(QLabel("Paste multiple video URLs (one per line):"))

        text_edit = QTextEdit()
        text_edit.setPlaceholderText("https://youtube.com/watch?v=...\nhttps://v.douyin.com/...")
        d_layout.addWidget(text_edit)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        d_layout.addWidget(btns)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            lines = [line.strip() for line in text_edit.toPlainText().splitlines() if line.strip()]
            for u in lines:
                self.queue_manager.enqueue_download(url=u, use_sniffer=self.sniffer_chk.isChecked())
            get_event_bus().toast.emit("success", f"Enqueued {len(lines)} bulk downloads.")

    def _change_output_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Download Directory", str(self.queue_manager.organizer.base_dir))
        if folder:
            self.queue_manager.organizer.base_dir = Path(folder)
            self.folder_lbl.setText(folder)

    # Table Sync Helpers
    def _find_or_create_row(self, job_id: str, default_url: str = "") -> int:
        for row in range(self.queue_table.rowCount()):
            item = self.queue_table.item(row, 0)
            if item and item.text() == job_id:
                return row

        row = self.queue_table.rowCount()
        self.queue_table.insertRow(row)

        self.queue_table.setItem(row, 0, QTableWidgetItem(job_id))
        self.queue_table.setItem(row, 1, QTableWidgetItem(default_url))
        self.queue_table.setItem(row, 2, QTableWidgetItem(_detect_platform(default_url)))

        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(0)
        self.queue_table.setCellWidget(row, 3, pbar)

        self.queue_table.setItem(row, 4, QTableWidgetItem("queued"))

        # Action Buttons Container
        actions_widget = QWidget()
        a_layout = QHBoxLayout(actions_widget)
        a_layout.setContentsMargins(4, 2, 4, 2)
        a_layout.setSpacing(6)

        btn_style = """
            QPushButton {
                background-color: #1e293b;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 0px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """

        pause_btn = QPushButton("⏸")
        pause_btn.setFixedSize(26, 24)
        pause_btn.setToolTip("Pause Download")
        pause_btn.setStyleSheet(btn_style)
        pause_btn.clicked.connect(lambda checked=False, jid=job_id: self.queue_manager.pause_download(jid))

        resume_btn = QPushButton("▶")
        resume_btn.setFixedSize(26, 24)
        resume_btn.setToolTip("Resume Download")
        resume_btn.setStyleSheet(btn_style)
        resume_btn.clicked.connect(lambda checked=False, jid=job_id: self.queue_manager.resume_download(jid))

        cancel_btn = QPushButton("✖")
        cancel_btn.setFixedSize(26, 24)
        cancel_btn.setToolTip("Cancel Download")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #f87171;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 0px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #dc2626;
                color: #ffffff;
            }
        """)
        cancel_btn.clicked.connect(lambda checked=False, jid=job_id: self.queue_manager.cancel_download(jid))

        a_layout.addWidget(pause_btn)
        a_layout.addWidget(resume_btn)
        a_layout.addWidget(cancel_btn)
        self.queue_table.setCellWidget(row, 5, actions_widget)

        return row

    def _enable_action_buttons(self, row: int) -> None:
        act_widget = self.queue_table.cellWidget(row, 5)
        if act_widget:
            for btn in act_widget.findChildren(QPushButton):
                btn.setEnabled(True)

    def _disable_action_buttons(self, row: int, pause: bool = True, cancel: bool = True) -> None:
        act_widget = self.queue_table.cellWidget(row, 5)
        if act_widget:
            btns = act_widget.findChildren(QPushButton)
            if len(btns) >= 3:
                if pause:
                    btns[0].setEnabled(False)
                if cancel:
                    btns[2].setEnabled(False)

    def _on_job_queued(self, job_id: str) -> None:
        job = self.queue_manager.job_queue.get_job(job_id)
        if job and job.kind == "download":
            display_title = str(job.payload.get("title") or job.payload.get("url", ""))
            row = self._find_or_create_row(job_id, display_title)
            target_item = self.queue_table.item(row, 1)
            if target_item and display_title:
                target_item.setText(display_title)
            pbar = self.queue_table.cellWidget(row, 3)
            if isinstance(pbar, QProgressBar):
                pbar.setValue(int(job.progress * 100))
            status_item = self.queue_table.item(row, 4)
            if status_item:
                status_item.setText("queued")
                status_item.setForeground(QColor("#94a3b8"))
                status_item.setToolTip("")
            self._enable_action_buttons(row)

    def _on_job_progress(self, job_id: str, progress: float, msg: str) -> None:
        row = self._find_or_create_row(job_id)
        pbar = self.queue_table.cellWidget(row, 3)
        if isinstance(pbar, QProgressBar):
            pbar.setValue(int(progress * 100))
        status_item = self.queue_table.item(row, 4)
        if status_item:
            status_text = "downloading"
            if progress >= 0.98:
                status_text = "merging"
            elif any(k in msg.lower() for k in ("subtitle", "whisper", "srt")):
                status_text = "subtitling"
            status_item.setText(status_text)
            status_item.setForeground(QColor("#60a5fa"))
            status_item.setToolTip(msg)

    def _on_job_completed(self, job_id: str, result: dict) -> None:
        row = self._find_or_create_row(job_id)
        title = result.get("title")
        if title:
            target_item = self.queue_table.item(row, 1)
            if target_item:
                target_item.setText(title)
        pbar = self.queue_table.cellWidget(row, 3)
        if isinstance(pbar, QProgressBar):
            pbar.setValue(100)
        status_item = self.queue_table.item(row, 4)
        if status_item:
            status_item.setText("completed")
            status_item.setForeground(Qt.GlobalColor.green)
        self._disable_action_buttons(row, pause=True, cancel=True)

        # Check auto-shutdown trigger
        if self.auto_shutdown_chk.isChecked():
            running = self.queue_manager.job_queue.list_jobs(status="running", kind="download")
            queued = self.queue_manager.job_queue.list_jobs(status="queued", kind="download")
            if not running and not queued:
                dlg = CountdownShutdownDialog(self)
                dlg.exec()

    def _on_job_failed(self, job_id: str, error: str) -> None:
        row = self._find_or_create_row(job_id)
        status_item = self.queue_table.item(row, 4)
        if status_item:
            status_item.setText("failed")
            status_item.setForeground(Qt.GlobalColor.red)
            status_item.setToolTip(error)
        self._disable_action_buttons(row, pause=True, cancel=True)

    def _on_job_cancelled(self, job_id: str) -> None:
        row = self._find_or_create_row(job_id)
        status_item = self.queue_table.item(row, 4)
        if status_item:
            status_item.setText("cancelled")
            status_item.setForeground(Qt.GlobalColor.yellow)
        self._disable_action_buttons(row, pause=True, cancel=True)

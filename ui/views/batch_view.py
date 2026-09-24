"""Batch processing and hardware accelerated video rendering view (Phase 11)."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.cancellation import CancellationToken
from modules.batch.batch_runner import BatchItem, BatchItemStatus, BatchRunner, BatchSummary


class ShutdownCountdownDialog(QDialog):
    """60-second countdown confirmation dialog with NO pre-selected (Section 7 rule)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("System Power Management")
        self.setFixedSize(380, 180)
        self.remaining_sec = 60

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        self.label = QLabel("Batch complete! Shutting down in 60 seconds...")
        self.label.setStyleSheet("font-weight: 700; font-size: 13px; color: #f87171;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label)

        btn_box = QHBoxLayout()
        btn_box.setSpacing(12)

        # Cancel button (Default focus!)
        self.cancel_btn = QPushButton("Cancel Shutdown")
        self.cancel_btn.setDefault(True)
        self.cancel_btn.setFocus()
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #3b82f6;
                color: #ffffff;
                font-weight: 700;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self.cancel_btn)

        self.shutdown_now_btn = QPushButton("Shutdown Now")
        self.shutdown_now_btn.setStyleSheet("""
            QPushButton {
                background-color: #ef4444;
                color: #ffffff;
                font-weight: 700;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        self.shutdown_now_btn.clicked.connect(self.accept)
        btn_box.addWidget(self.shutdown_now_btn)

        layout.addLayout(btn_box)

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)
        self._timer.start()

    def _on_tick(self) -> None:
        self.remaining_sec -= 1
        if self.remaining_sec <= 0:
            self._timer.stop()
            self.accept()
        else:
            self.label.setText(f"Batch complete! Shutting down in {self.remaining_sec} seconds...")


class BatchView(QWidget):
    """High-throughput batch rendering with hardware encoding and GPU ResourceLock protection."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.runner = BatchRunner()
        self.items: list[BatchItem] = []
        self._current_token: CancellationToken | None = None
        self._build_ui()
        self._detect_encoder()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        # 1. Header
        top_bar = QHBoxLayout()
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Batch Processing & HW Acceleration")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        desc = QLabel("Sequential multi-episode rendering guarded by GPU Exclusive ResourceLock.")
        desc.setStyleSheet("color: #9ca3af; font-size: 11px;")
        header.addWidget(title)
        header.addWidget(desc)
        top_bar.addLayout(header)

        top_bar.addStretch()

        self.encoder_badge = QLabel("Probing Encoders...")
        self.encoder_badge.setStyleSheet("""
            background-color: #1e2433;
            color: #38bdf8;
            font-size: 11px;
            font-weight: 700;
            padding: 5px 12px;
            border-radius: 6px;
            border: 1px solid #0284c7;
        """)
        top_bar.addWidget(self.encoder_badge)

        layout.addLayout(top_bar)

        # 2. Control Toolbar
        toolbar = QFrame()
        toolbar.setStyleSheet("""
            QFrame {
                background-color: #131b2e;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(12, 8, 12, 8)
        tb_layout.setSpacing(10)

        add_files_btn = QPushButton("➕ Add Video Files...")
        add_files_btn.setToolTip("Select one or more video files to enqueue")
        add_files_btn.clicked.connect(self._on_add_files_clicked)
        tb_layout.addWidget(add_files_btn)

        add_folder_btn = QPushButton("📁 Add Folder...")
        add_folder_btn.setToolTip("Select a folder containing video episodes")
        add_folder_btn.clicked.connect(self._on_add_folder_clicked)
        tb_layout.addWidget(add_folder_btn)

        tb_layout.addSpacing(10)

        # Target language
        tb_layout.addWidget(QLabel("Target:"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Khmer (km)", "km")
        self.lang_combo.addItem("English (en)", "en")
        self.lang_combo.addItem("Chinese (zh)", "zh")
        self.lang_combo.addItem("Japanese (ja)", "ja")
        self.lang_combo.addItem("Korean (ko)", "ko")
        self.lang_combo.setFixedWidth(110)
        tb_layout.addWidget(self.lang_combo)

        # Encoder selection
        tb_layout.addWidget(QLabel("Encoder:"))
        self.encoder_combo = QComboBox()
        self.encoder_combo.addItem("Auto Detect (Hardware)", "auto")
        self.encoder_combo.addItem("NVIDIA NVENC (h264_nvenc)", "h264_nvenc")
        self.encoder_combo.addItem("AMD AMF (h264_amf)", "h264_amf")
        self.encoder_combo.addItem("Intel QSV (h264_qsv)", "h264_qsv")
        self.encoder_combo.addItem("CPU Software (libx264)", "libx264")
        self.encoder_combo.setFixedWidth(170)
        tb_layout.addWidget(self.encoder_combo)

        tb_layout.addStretch()

        # Start Batch Button
        self.start_btn = QPushButton("🚀 Start Batch")
        self.start_btn.setToolTip("Begin batch rendering with GPU ResourceLock protection")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: 700;
                padding: 6px 16px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #047857; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.start_btn.clicked.connect(self._on_start_batch_clicked)
        tb_layout.addWidget(self.start_btn)

        # Cancel Batch Button
        self.cancel_btn = QPushButton("⏹️ Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Cancel ongoing batch processing")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: 700;
                padding: 6px 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #b91c1c; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_batch_clicked)
        tb_layout.addWidget(self.cancel_btn)

        # Clear Completed Button
        clear_btn = QPushButton("🧹 Clear")
        clear_btn.clicked.connect(self._on_clear_clicked)
        tb_layout.addWidget(clear_btn)

        layout.addWidget(toolbar)

        # 3. Overall Progress & Status
        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setValue(0)
        self.overall_bar.setFixedHeight(12)
        self.overall_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background-color: #38bdf8;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.overall_bar)

        self.status_lbl = QLabel("Queue is ready.")
        self.status_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        layout.addWidget(self.status_lbl)

        # 4. Batch Items Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Source Media",
            "Target",
            "Status",
            "Progress",
            "Elapsed",
            "Output",
        ])
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        header_view.resizeSection(3, 100)
        header_view.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0b0f17;
                border: 1px solid #1e2536;
                border-radius: 6px;
                gridline-color: #1e2536;
                color: #e2e8f0;
            }
            QHeaderView::section {
                background-color: #161d2b;
                color: #94a3b8;
                font-weight: 700;
                padding: 4px;
                border: 1px solid #1e2536;
            }
        """)
        layout.addWidget(self.table, 1)

        # 5. Footer: Auto-Shutdown Option
        footer = QHBoxLayout()
        self.shutdown_check = QCheckBox("Shutdown PC after batch completes (with 60-second cancel window)")
        self.shutdown_check.setStyleSheet("color: #94a3b8; font-size: 11px;")
        footer.addWidget(self.shutdown_check)

        footer.addStretch()

        self.mem_lbl = QLabel("Peak Memory: 0 MB")
        self.mem_lbl.setStyleSheet("color: #64748b; font-size: 11px;")
        footer.addWidget(self.mem_lbl)

        layout.addLayout(footer)

    def _detect_encoder(self) -> None:
        def worker() -> None:
            enc = self.runner.detect_best_encoder()

            def on_ready() -> None:
                if "nvenc" in enc:
                    text = f"⚡ NVIDIA NVENC ({enc})"
                elif "amf" in enc:
                    text = f"⚡ AMD AMF ({enc})"
                elif "qsv" in enc:
                    text = f"⚡ Intel QuickSync ({enc})"
                else:
                    text = f"🖥️ CPU ({enc})"
                self.encoder_badge.setText(text)

            QTimer.singleShot(0, on_ready)

        threading.Thread(target=worker, daemon=True).start()

    def _on_add_files_clicked(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Video Files for Batch",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.webm *.avi);;All Files (*)",
        )
        for f in files:
            p = Path(f)
            item = BatchItem(
                id=f"item_{len(self.items) + 1}",
                video_path=p,
                target_lang=self.lang_combo.currentData(),
            )
            self.items.append(item)
        self._refresh_table()

    def _on_add_folder_clicked(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder Containing Videos")
        if folder:
            p_folder = Path(folder)
            valid_exts = {".mp4", ".mkv", ".mov", ".webm", ".avi"}
            for p in sorted(p_folder.glob("*")):
                if p.suffix.lower() in valid_exts and p.is_file():
                    item = BatchItem(
                        id=f"item_{len(self.items) + 1}",
                        video_path=p,
                        target_lang=self.lang_combo.currentData(),
                    )
                    self.items.append(item)
            self._refresh_table()

    def _refresh_table(self) -> None:
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            self.table.setItem(row, 0, QTableWidgetItem(item.video_path.name))
            self.table.setItem(row, 1, QTableWidgetItem(item.target_lang.upper()))

            status_item = QTableWidgetItem(item.status.value.upper())
            if item.status == BatchItemStatus.COMPLETED:
                status_item.setForeground(Qt.GlobalColor.green)
            elif item.status == BatchItemStatus.PROCESSING:
                status_item.setForeground(Qt.GlobalColor.cyan)
            elif item.status == BatchItemStatus.FAILED:
                status_item.setForeground(Qt.GlobalColor.red)
            self.table.setItem(row, 2, status_item)

            pct_str = f"{int(item.progress * 100)}%"
            self.table.setItem(row, 3, QTableWidgetItem(pct_str))

            el_str = f"{item.elapsed_sec:.1f}s" if item.elapsed_sec > 0 else "-"
            self.table.setItem(row, 4, QTableWidgetItem(el_str))

            out_text = item.output_path.name if item.output_path else "-"
            self.table.setItem(row, 5, QTableWidgetItem(out_text))

    def _on_start_batch_clicked(self) -> None:
        if not self.items:
            QMessageBox.information(self, "Empty Queue", "Please add video files to the batch queue first.")
            return

        token = CancellationToken()
        self._current_token = token

        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        chosen_encoder = self.encoder_combo.currentData()

        def worker() -> None:
            def on_item_update(item: BatchItem) -> None:
                QTimer.singleShot(0, self._refresh_table)

            def on_total_progress(prog: float, msg: str) -> None:
                def update_ui() -> None:
                    self.overall_bar.setValue(int(prog * 100))
                    self.status_lbl.setText(msg)

                QTimer.singleShot(0, update_ui)

            try:
                summary: BatchSummary = self.runner.run_batch(
                    items=self.items,
                    encoder=chosen_encoder,
                    token=token,
                    item_callback=on_item_update,
                    total_progress=on_total_progress,
                )

                def on_batch_finished() -> None:
                    self.mem_lbl.setText(f"Peak Memory: {summary.peak_memory_mb} MB")
                    self.status_lbl.setText(
                        f"Batch finished! Succeeded: {summary.completed_items}, Failed: {summary.failed_items} ({summary.total_elapsed_sec:.1f}s)"
                    )

                    if self.shutdown_check.isChecked():
                        dlg = ShutdownCountdownDialog(self)
                        if dlg.exec() == QDialog.DialogCode.Accepted:
                            # User confirmed shutdown
                            subprocess.run(["shutdown", "/s", "/t", "0"])

                QTimer.singleShot(0, on_batch_finished)

            except Exception as e:
                def on_batch_error(err_str: str) -> None:
                    if "cancel" in err_str.lower():
                        self.status_lbl.setText("⏹️ Batch processing cancelled by user.")
                    else:
                        self.status_lbl.setText(f"❌ Batch error: {err_str}")
                        QMessageBox.critical(self, "Batch Error", f"Batch processing failed:\n\n{err_str}")

                QTimer.singleShot(0, lambda err=str(e): on_batch_error(err))

            finally:
                def restore_buttons() -> None:
                    self.start_btn.setEnabled(True)
                    self.cancel_btn.setEnabled(False)

                QTimer.singleShot(0, restore_buttons)

        threading.Thread(target=worker, daemon=True, name="BatchRunnerWorker").start()

    def _on_cancel_batch_clicked(self) -> None:
        if self._current_token:
            self._current_token.cancel()
            self.status_lbl.setText("Cancelling batch runner...")
            self.cancel_btn.setEnabled(False)

    def _on_clear_clicked(self) -> None:
        self.items = [i for i in self.items if i.status not in (BatchItemStatus.COMPLETED, BatchItemStatus.FAILED)]
        self._refresh_table()

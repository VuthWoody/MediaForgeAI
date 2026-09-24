"""VoxReel Desktop GUI View.

PySide6 view providing full UI access to:
- Actor Voice Registry (AVR) Management (Register, Enroll, Merge, Delete)
- 5-Stage Checkpointed Diarization & Matching Studio
- Segment review, inline corrections, and cluster promotion
- Multi-format exports (JSON, SRT, VTT, ELAN, TXT)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.voxreel.config import VoxReelConfig
from modules.voxreel.db import VoxReelDB
from modules.voxreel.engine import MasterSessionResult, VoxReelEngine
from modules.voxreel.registry import ActorVoiceRegistry

logger = logging.getLogger("mediaforge.voxreel")


class PipelineWorker(QThread):
    """Worker thread running the 5-stage VoxReel pipeline off the GUI thread."""

    progress_signal = Signal(str, float, str)
    completed_signal = Signal(object)
    failed_signal = Signal(str)

    def __init__(
        self,
        engine: VoxReelEngine,
        media_path: str,
        language: str = "en",
        num_speakers: int | None = None,
        model_size: str | None = None,
        resume: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.media_path = media_path
        self.language = language
        self.num_speakers = num_speakers
        self.model_size = model_size
        self.resume = resume

    def run(self) -> None:
        try:
            res = self.engine.process(
                media_path=self.media_path,
                language=self.language,
                num_speakers=self.num_speakers,
                model_size=self.model_size,
                resume=self.resume,
                progress_cb=lambda s, p, m: self.progress_signal.emit(s, p, m),
            )
            self.completed_signal.emit(res)
        except Exception as e:
            self.failed_signal.emit(str(e))


class VoxReelView(QWidget):
    """Integrated VoxReel Actor Voice Registry & Diarization Studio View."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = VoxReelDB()
        self.config = VoxReelConfig()
        self.registry = ActorVoiceRegistry(db=self.db, config=self.config.registry)
        self.engine = VoxReelEngine(config=self.config, db=self.db)

        self.current_media_path: str | None = None
        self.current_session_result: MasterSessionResult | None = None
        self._worker: PipelineWorker | None = None

        self._build_ui()
        self.refresh_actors()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # ---------------------------------------------------------------------
        # LEFT PANE: Actor Voice Registry (AVR) Manager
        # ---------------------------------------------------------------------
        left_widget = QWidget(self)
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        avr_header = QLabel("🎙️ Actor Voice Registry (AVR)")
        avr_header.setStyleSheet("font-size: 15px; font-weight: bold; color: #6366f1;")
        left_layout.addWidget(avr_header)

        # Search Bar
        self.search_input = QLineEdit(self)
        self.search_input.setPlaceholderText("🔍 Search registered actors...")
        self.search_input.textChanged.connect(self._on_search_changed)
        left_layout.addWidget(self.search_input)

        # Actor List
        self.actor_list = QListWidget(self)
        self.actor_list.setStyleSheet("""
            QListWidget {
                background-color: #111827;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-radius: 4px;
                color: #e5e7eb;
            }
            QListWidget::item:selected {
                background-color: #312e81;
                color: #ffffff;
            }
        """)
        self.actor_list.itemClicked.connect(self._on_actor_selected)
        left_layout.addWidget(self.actor_list, 1)

        # Actor Action Buttons
        act_btn_layout = QHBoxLayout()
        self.btn_new_actor = QPushButton("➕ New Actor")
        self.btn_new_actor.clicked.connect(self._create_actor_dialog)
        self.btn_enroll = QPushButton("🎙️ Enroll Clip")
        self.btn_enroll.clicked.connect(self._enroll_clip_dialog)
        self.btn_enroll.setEnabled(False)
        act_btn_layout.addWidget(self.btn_new_actor)
        act_btn_layout.addWidget(self.btn_enroll)
        left_layout.addLayout(act_btn_layout)

        sec_btn_layout = QHBoxLayout()
        self.btn_merge = QPushButton("🔀 Merge")
        self.btn_merge.clicked.connect(self._merge_actor_dialog)
        self.btn_merge.setEnabled(False)
        self.btn_delete = QPushButton("🗑️ Delete")
        self.btn_delete.setStyleSheet("background-color: #7f1d1d; color: #fecaca;")
        self.btn_delete.clicked.connect(self._delete_actor_dialog)
        self.btn_delete.setEnabled(False)
        sec_btn_layout.addWidget(self.btn_merge)
        sec_btn_layout.addWidget(self.btn_delete)
        left_layout.addLayout(sec_btn_layout)

        # Actor Details Box
        self.actor_details_box = QLabel("Select an actor to view profile details.")
        self.actor_details_box.setStyleSheet("color: #9ca3af; font-size: 11px; padding: 6px; background-color: #1f2937; border-radius: 4px;")
        self.actor_details_box.setWordWrap(True)
        left_layout.addWidget(self.actor_details_box)

        left_widget.setMinimumWidth(280)
        splitter.addWidget(left_widget)

        # ---------------------------------------------------------------------
        # RIGHT PANE: Diarization & Voice Matching Studio
        # ---------------------------------------------------------------------
        right_widget = QWidget(self)
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # Media Selection Bar
        media_group = QGroupBox("Media File & Studio Audio Ingestion")
        media_layout = QHBoxLayout(media_group)

        self.media_path_input = QLineEdit(self)
        self.media_path_input.setPlaceholderText("Auto-detected from Studio, or select video/audio...")
        self.btn_use_studio = QPushButton("🎬 Use Active Studio Media")
        self.btn_use_studio.setToolTip("Automatically load the video currently open in the Studio tab")
        self.btn_use_studio.setStyleSheet("""
            QPushButton {
                background-color: #0f766e;
                color: #ffffff;
                font-weight: 600;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #14b8a6;
            }
        """)
        self.btn_use_studio.clicked.connect(self._use_studio_media)

        self.btn_browse = QPushButton("Browse...")
        self.btn_browse.clicked.connect(self._browse_media)

        media_layout.addWidget(self.media_path_input, 1)
        media_layout.addWidget(self.btn_use_studio)
        media_layout.addWidget(self.btn_browse)
        right_layout.addWidget(media_group)

        # Pipeline Controls Bar
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(QLabel("Whisper:"))
        self.model_combo = QComboBox(self)
        self.model_combo.addItem("small (Fast & Accurate)", "small")
        self.model_combo.addItem("base (Very Fast)", "base")
        self.model_combo.addItem("tiny (Ultra Fast)", "tiny")
        self.model_combo.addItem("large-v3 (Slow - 3GB Download)", "large-v3")
        self.model_combo.setToolTip("Speech recognition model. 'small' is pre-cached and avoids download hangs.")
        ctrl_layout.addWidget(self.model_combo)

        ctrl_layout.addWidget(QLabel("Language:"))
        self.lang_combo = QComboBox(self)
        self.lang_combo.addItems(["auto", "zh", "en", "ja", "ko", "es", "fr", "de"])
        ctrl_layout.addWidget(self.lang_combo)

        ctrl_layout.addWidget(QLabel("Speakers:"))
        self.speakers_combo = QComboBox(self)
        self.speakers_combo.addItems(["Auto", "1", "2", "3", "4", "5", "6", "8", "10"])
        ctrl_layout.addWidget(self.speakers_combo)

        self.chk_separation = QCheckBox("Source Separation (Demucs)", self)
        self.chk_separation.setChecked(True)
        ctrl_layout.addWidget(self.chk_separation)

        self.chk_resume = QCheckBox("Resume Checkpoints", self)
        self.chk_resume.setChecked(True)
        ctrl_layout.addWidget(self.chk_resume)

        ctrl_layout.addStretch()

        self.btn_run = QPushButton("⚡ Run Full Pipeline (Studio Audio)")
        self.btn_run.setToolTip("Take audio from active Studio video, diarize, transcribe, and match actor voices")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #6366f1;
            }
            QPushButton:disabled {
                background-color: #374151;
                color: #9ca3af;
            }
        """)
        self.btn_run.clicked.connect(self._run_pipeline)
        ctrl_layout.addWidget(self.btn_run)
        right_layout.addLayout(ctrl_layout)

        # Stage Progress Bar & Telemetry Status
        progress_layout = QVBoxLayout()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(14)
        progress_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("Ready to process.")
        self.status_label.setStyleSheet("color: #9ca3af; font-size: 11px;")
        progress_layout.addWidget(self.status_label)
        right_layout.addLayout(progress_layout)

        # Attributed Segment Results Table
        table_header = QLabel("Transcript & Speaker Attribution")
        table_header.setStyleSheet("font-size: 13px; font-weight: bold; color: #e5e7eb;")
        right_layout.addWidget(table_header)

        self.segment_table = QTableWidget(self)
        self.segment_table.setColumnCount(7)
        self.segment_table.setHorizontalHeaderLabels([
            "Start (s)", "End (s)", "Cluster", "Matched Actor", "Score", "Status", "Text"
        ])
        header = self.segment_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.segment_table.setStyleSheet("""
            QTableWidget {
                background-color: #111827;
                border: 1px solid #374151;
                border-radius: 6px;
                gridline-color: #1f2937;
            }
            QHeaderView::section {
                background-color: #1f2937;
                color: #e5e7eb;
                padding: 6px;
                border: 1px solid #374151;
            }
        """)
        right_layout.addWidget(self.segment_table, 1)

        # Human Feedback & Export Actions
        action_bar = QHBoxLayout()
        self.btn_confirm_match = QPushButton("⭐ Confirm Match")
        self.btn_confirm_match.clicked.connect(self._confirm_selected_segment)
        self.btn_promote = QPushButton("🚀 Promote to Actor...")
        self.btn_promote.clicked.connect(self._promote_selected_cluster)

        self.btn_sync_studio = QPushButton("🎬 Sync to Studio Timeline")
        self.btn_sync_studio.setToolTip("Send multi-speaker voice segments directly into Studio timeline")
        self.btn_sync_studio.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: 600;
                padding: 6px 12px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #10b981;
            }
        """)
        self.btn_sync_studio.clicked.connect(self._manual_sync_to_studio)

        action_bar.addWidget(self.btn_confirm_match)
        action_bar.addWidget(self.btn_promote)
        action_bar.addWidget(self.btn_sync_studio)
        action_bar.addStretch()

        self.btn_export_srt = QPushButton("📥 SRT")
        self.btn_export_srt.clicked.connect(lambda: self._export_format("srt"))
        self.btn_export_vtt = QPushButton("📥 VTT")
        self.btn_export_vtt.clicked.connect(lambda: self._export_format("vtt"))
        self.btn_export_json = QPushButton("📥 JSON")
        self.btn_export_json.clicked.connect(lambda: self._export_format("json"))
        self.btn_export_eaf = QPushButton("📥 ELAN (.eaf)")
        self.btn_export_eaf.clicked.connect(lambda: self._export_format("eaf"))
        self.btn_open_folder = QPushButton("📁 Output Folder")
        self.btn_open_folder.clicked.connect(self._open_output_folder)

        action_bar.addWidget(self.btn_export_srt)
        action_bar.addWidget(self.btn_export_vtt)
        action_bar.addWidget(self.btn_export_json)
        action_bar.addWidget(self.btn_export_eaf)
        action_bar.addWidget(self.btn_open_folder)

        right_layout.addLayout(action_bar)

        splitter.addWidget(right_widget)
        splitter.setSizes([320, 800])
        main_layout.addWidget(splitter)

    # -------------------------------------------------------------------------
    # Actor Registry UI Logic
    # -------------------------------------------------------------------------

    def refresh_actors(self, search_text: str = "") -> None:
        self.actor_list.clear()
        actors = self.registry.search_actors(search_text) if search_text else self.registry.list_actors()

        for a in actors:
            alias_txt = f" ({', '.join(a.aliases)})" if a.aliases else ""
            item = QListWidgetItem(f"🎭 {a.display_name}{alias_txt}")
            item.setData(Qt.ItemDataRole.UserRole, a.id)
            self.actor_list.addItem(item)

        self.btn_enroll.setEnabled(False)
        self.btn_merge.setEnabled(False)
        self.btn_delete.setEnabled(False)
        self.actor_details_box.setText(f"{len(actors)} actor(s) registered.")

    def _on_search_changed(self, text: str) -> None:
        self.refresh_actors(text.strip())

    def _on_actor_selected(self, item: QListWidgetItem) -> None:
        actor_id = item.data(Qt.ItemDataRole.UserRole)
        actor = self.registry.get_actor(actor_id)
        if not actor:
            return

        self.btn_enroll.setEnabled(True)
        self.btn_merge.setEnabled(True)
        self.btn_delete.setEnabled(True)

        prof = self.db.get_or_create_profile(actor.id)
        refs = self.db.get_reference_embeddings(prof.id)

        details = (
            f"<b>Name:</b> {actor.display_name}<br>"
            f"<b>ID:</b> {actor.id[:8]}...<br>"
            f"<b>Aliases:</b> {', '.join(actor.aliases) if actor.aliases else 'None'}<br>"
            f"<b>Voice Profile:</b> {len(refs)} reference embeddings (max 50)<br>"
            f"<b>Centroid Status:</b> {'Calibrated' if prof.centroid is not None else 'Uncalibrated'}<br>"
            f"<b>Consent Flag:</b> {'Yes' if actor.consent_flag else 'No'}"
        )
        self.actor_details_box.setText(details)

    def _create_actor_dialog(self) -> None:
        name, ok = QInputDialog.getText(self, "New Actor", "Enter Actor Display Name:")
        if ok and name.strip():
            aliases_txt, ok2 = QInputDialog.getText(
                self, "Aliases", "Enter comma-separated aliases or character names:"
            )
            aliases = [a.strip() for a in aliases_txt.split(",") if a.strip()] if ok2 else []
            self.registry.create_actor(display_name=name.strip(), aliases=aliases, consent_flag=True)
            self.refresh_actors()
            QMessageBox.information(self, "Actor Created", f"Successfully registered actor: {name.strip()}")

    def _enroll_clip_dialog(self) -> None:
        cur_item = self.actor_list.currentItem()
        if not cur_item:
            return
        actor_id = cur_item.data(Qt.ItemDataRole.UserRole)
        actor = self.registry.get_actor(actor_id)
        if not actor:
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Enroll Reference Audio Clip for {actor.display_name}",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.m4a *.aac *.ogg)",
        )
        if file_path:
            success, msg, count = self.registry.enroll_clip(actor_id, file_path)
            if success:
                QMessageBox.information(self, "Enrollment Success", msg)
                self._on_actor_selected(cur_item)
            else:
                QMessageBox.warning(self, "Enrollment Gating Rejected", msg)

    def _merge_actor_dialog(self) -> None:
        cur_item = self.actor_list.currentItem()
        if not cur_item:
            return
        actor_id = cur_item.data(Qt.ItemDataRole.UserRole)
        actor = self.registry.get_actor(actor_id)
        if not actor:
            return

        all_actors = [a for a in self.registry.list_actors() if a.id != actor_id]
        if not all_actors:
            QMessageBox.information(self, "Merge", "No other actors available to merge.")
            return

        names = [f"{a.display_name} ({a.id[:8]})" for a in all_actors]
        choice, ok = QInputDialog.getItem(
            self, "Merge Actor", f"Select actor to merge into '{actor.display_name}':", names, 0, False
        )
        if ok and choice:
            idx = names.index(choice)
            source_actor = all_actors[idx]
            confirm = QMessageBox.question(
                self,
                "Confirm Merge",
                f"Are you sure you want to merge '{source_actor.display_name}' into '{actor.display_name}'?\n"
                f"This will combine reference embeddings and delete '{source_actor.display_name}'.",
            )
            if confirm == QMessageBox.StandardButton.Yes:
                self.registry.merge_actors(target_id=actor.id, source_id=source_actor.id)
                self.refresh_actors()
                QMessageBox.information(self, "Merged", f"Successfully merged into {actor.display_name}.")

    def _delete_actor_dialog(self) -> None:
        cur_item = self.actor_list.currentItem()
        if not cur_item:
            return
        actor_id = cur_item.data(Qt.ItemDataRole.UserRole)
        actor = self.registry.get_actor(actor_id)
        if not actor:
            return

        confirm = QMessageBox.question(
            self,
            "GDPR Erasure Confirmation",
            f"Are you sure you want to delete '{actor.display_name}'?\n"
            f"All associated biometric voice vectors and profiles will be permanently erased.",
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.registry.delete_actor(actor.id)
            self.refresh_actors()
            QMessageBox.information(self, "Deleted", f"Actor '{actor.display_name}' erased.")

    # -------------------------------------------------------------------------
    # Studio Media Discovery & Pipeline Processing Logic
    # -------------------------------------------------------------------------

    def get_active_studio_media(self) -> Path | None:
        """Find the video/audio path currently open in the Studio view or active project."""
        main_win = self.window()
        if not hasattr(main_win, "studio_view") and hasattr(self.parent(), "studio_view"):
            main_win = self.parent()

        # 1. Check StudioView
        if hasattr(main_win, "studio_view") and main_win.studio_view:
            sv = main_win.studio_view
            if getattr(sv, "_original_source_video_path", None):
                p = Path(sv._original_source_video_path).resolve()
                if p.exists():
                    return p
            if hasattr(sv, "video_player") and hasattr(sv.video_player, "controller"):
                ctrl = sv.video_player.controller
                if getattr(ctrl, "current_video_path", None):
                    p = Path(ctrl.current_video_path).resolve()
                    if p.exists():
                        return p
        # 2. Check ProjectManager
        if hasattr(main_win, "project_manager") and main_win.project_manager:
            proj = main_win.project_manager.current_project
            if proj and getattr(proj, "media_path", None):
                p = Path(proj.media_path).resolve()
                if p.exists():
                    return p
        return None

    def _auto_sync_studio_media(self) -> None:
        """Sync media path from active Studio video if currently empty or outdated."""
        p = self.get_active_studio_media()
        if p and p.exists():
            cur = self.media_path_input.text().strip()
            if not cur or not Path(cur).exists() or cur != str(p):
                self.media_path_input.setText(str(p))
                self.current_media_path = str(p)
                self.status_label.setText(f"Active Studio video: {p.name}")

    def _use_studio_media(self) -> None:
        """Explicitly load the media currently active in Studio into VoxReel."""
        p = self.get_active_studio_media()
        if p and p.exists():
            self.media_path_input.setText(str(p))
            self.current_media_path = str(p)
            self.status_label.setText(f"Loaded media from Studio: {p.name}")
        else:
            QMessageBox.information(
                self,
                "Studio Media",
                "No active video is currently open in the Studio tab.\nPlease open a video in Studio first, or click 'Browse...' to select a file.",
            )

    def showEvent(self, event: Any) -> None:
        """Auto-populate with active studio media if input is currently blank."""
        super().showEvent(event)
        self._auto_sync_studio_media()

    def _browse_media(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Media File for Diarization", "", "Media Files (*.mp4 *.mkv *.mov *.wav *.mp3 *.flac *.avi)"
        )
        if file_path:
            self.media_path_input.setText(file_path)
            self.current_media_path = file_path

    def _run_pipeline(self) -> None:
        path = self.media_path_input.text().strip()
        if not path or not Path(path).exists():
            # Try to auto-grab from active Studio video
            studio_p = self.get_active_studio_media()
            if studio_p and studio_p.exists():
                path = str(studio_p)
                self.media_path_input.setText(path)
                self.current_media_path = path
            else:
                QMessageBox.warning(
                    self,
                    "No Media File",
                    "No video or audio file is selected.\n\nPlease open a video in the Studio tab or click 'Browse...' to select a file.",
                )
                return

        model_size = self.model_combo.currentData() or "small"
        speakers_val = self.speakers_combo.currentText()
        num_speakers = int(speakers_val) if speakers_val.isdigit() else None
        lang = self.lang_combo.currentText()
        resume = self.chk_resume.isChecked()

        self.btn_run.setEnabled(False)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Starting pipeline on {Path(path).name} (Whisper: {model_size})...")

        self._worker = PipelineWorker(
            engine=self.engine,
            media_path=path,
            language=lang,
            num_speakers=num_speakers,
            model_size=model_size,
            resume=resume,
            parent=self,
        )
        self._worker.progress_signal.connect(self._on_pipeline_progress)
        self._worker.completed_signal.connect(self._on_pipeline_completed)
        self._worker.failed_signal.connect(self._on_pipeline_failed)
        self._worker.start()

    def _on_pipeline_progress(self, stage: str, pct: float, msg: str) -> None:
        self.progress_bar.setValue(int(pct * 100))
        self.status_label.setText(f"[{stage}] {msg}")

    def _on_pipeline_completed(self, result: MasterSessionResult) -> None:
        self.current_session_result = result
        self.btn_run.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText(f"Session {result.session_id[:8]} completed successfully.")
        self._populate_segment_table(result.segments)
        # Automatically sync attributed speaker clips into Studio timeline
        self._sync_to_studio_timeline(result)

    def _on_pipeline_failed(self, error_msg: str) -> None:
        self.btn_run.setEnabled(True)
        self.status_label.setText(f"Failed: {error_msg}")
        QMessageBox.critical(self, "Pipeline Error", error_msg)

    def _sync_to_studio_timeline(self, result: MasterSessionResult | None = None) -> None:
        """Convert attributed segments into TranscriptSegments and send to Studio timeline."""
        target_res = result or self.current_session_result
        if not target_res or not target_res.segments:
            return

        try:
            main_win = self.window()
            if hasattr(main_win, "studio_view") and main_win.studio_view:
                sv = main_win.studio_view
                if hasattr(sv, "timeline"):
                    from modules.ai.engine import TranscriptSegment

                    segments: list[TranscriptSegment] = []
                    for idx, s in enumerate(target_res.segments, start=1):
                        spk_label = s.get("actor") or s.get("speaker") or "Speaker 1"
                        text_val = s.get("text", "")
                        score_val = float(s.get("match_score", 0.95) or 0.95)
                        segments.append(
                            TranscriptSegment(
                                id=idx,
                                start=float(s.get("start", 0.0)),
                                end=float(s.get("end", 0.0)),
                                speaker=spk_label,
                                source_text=text_val,
                                target_text="",
                                confidence=score_val,
                            )
                        )
                    sv.timeline.load_transcript_clips(segments)
                    if hasattr(sv, "script_inspector") and sv.script_inspector:
                        sv.script_inspector.load_transcript(segments)
                    logger.info("Successfully synced %d VoxReel segments to Studio timeline and script inspector", len(segments))
        except Exception as e:
            logger.warning("Could not sync VoxReel segments to Studio timeline: %s", e)

    def _manual_sync_to_studio(self) -> None:
        if not self.current_session_result:
            QMessageBox.warning(self, "Sync", "No processed session results available to sync.")
            return
        self._sync_to_studio_timeline(self.current_session_result)
        main_win = self.window()
        if hasattr(main_win, "_on_navigation"):
            main_win._on_navigation("studio")

    def _populate_segment_table(self, segments: list[dict[str, Any]]) -> None:
        self.segment_table.setRowCount(len(segments))

        for row, s in enumerate(segments):
            start_item = QTableWidgetItem(f"{float(s.get('start', 0.0)):.2f}")
            end_item = QTableWidgetItem(f"{float(s.get('end', 0.0)):.2f}")
            spk_item = QTableWidgetItem(s.get("speaker", "SPK_0"))

            actor_name = s.get("actor") or "Unknown"
            actor_item = QTableWidgetItem(actor_name)

            score = s.get("match_score")
            score_item = QTableWidgetItem(f"{score:.2f}" if score is not None else "—")

            status = s.get("match_status", "new")
            status_item = QTableWidgetItem(status.upper())
            # Color code status
            if status == "auto":
                status_item.setForeground(Qt.GlobalColor.green)
            elif status == "review":
                status_item.setForeground(Qt.GlobalColor.yellow)
            else:
                status_item.setForeground(Qt.GlobalColor.cyan)

            text_item = QTableWidgetItem(s.get("text", ""))

            self.segment_table.setItem(row, 0, start_item)
            self.segment_table.setItem(row, 1, end_item)
            self.segment_table.setItem(row, 2, spk_item)
            self.segment_table.setItem(row, 3, actor_item)
            self.segment_table.setItem(row, 4, score_item)
            self.segment_table.setItem(row, 5, status_item)
            self.segment_table.setItem(row, 6, text_item)

    def _confirm_selected_segment(self) -> None:
        cur_row = self.segment_table.currentRow()
        if cur_row < 0 or not self.current_session_result:
            return

        seg = self.current_session_result.segments[cur_row]
        seg_id = seg.get("id")
        if seg_id:
            self.registry.apply_corrections(
                self.current_session_result.session_id,
                [{"action": "confirm_match", "segment_id": seg_id}],
            )
            item = self.segment_table.item(cur_row, 5)
            if item:
                item.setText("CONFIRMED")
                item.setForeground(Qt.GlobalColor.green)

    def _promote_selected_cluster(self) -> None:
        cur_row = self.segment_table.currentRow()
        if cur_row < 0 or not self.current_session_result:
            return

        seg = self.current_session_result.segments[cur_row]
        cluster = seg.get("speaker", "SPK_A")

        name, ok = QInputDialog.getText(
            self, "Promote to Actor", f"Assign actor name to all occurrences of {cluster}:"
        )
        if ok and name.strip():
            actor = self.registry.promote_cluster_to_actor(
                session_id=self.current_session_result.session_id,
                cluster_label=cluster,
                actor_name=name.strip(),
            )
            # Update table rows with this cluster
            for r in range(self.segment_table.rowCount()):
                c_item = self.segment_table.item(r, 2)
                if c_item and c_item.text() == cluster:
                    name_item = self.segment_table.item(r, 3)
                    if name_item:
                        name_item.setText(actor.display_name)
                    st_item = self.segment_table.item(r, 5)
                    if st_item:
                        st_item.setText("CONFIRMED")
                        st_item.setForeground(Qt.GlobalColor.green)

            self.refresh_actors()
            QMessageBox.information(
                self,
                "Promoted",
                f"Cluster {cluster} promoted to registered actor: {actor.display_name}",
            )

    def _export_format(self, fmt: str) -> None:
        if not self.current_session_result:
            QMessageBox.warning(self, "Export", "No processed session available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {fmt.upper()} Export",
            f"{self.current_session_result.session_id[:8]}.{fmt}",
            f"{fmt.upper()} Files (*.{fmt})",
        )
        if file_path:
            master = self.current_session_result.to_master_json()
            if fmt == "srt":
                self.engine.exporter.export_srt(master, file_path)
            elif fmt == "vtt":
                self.engine.exporter.export_vtt(master, file_path)
            elif fmt == "json":
                self.engine.exporter.export_json(master, file_path)
            elif fmt in ("eaf", "elan"):
                self.engine.exporter.export_elan(master, file_path)
            QMessageBox.information(self, "Export Complete", f"Exported {fmt.upper()} to:\n{file_path}")

    def _open_output_folder(self) -> None:
        if self.current_session_result and self.current_session_result.checkpoint_dir:
            folder = Path(self.current_session_result.checkpoint_dir).parent
            if folder.exists():
                os.startfile(str(folder))

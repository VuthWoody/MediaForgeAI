"""Script & Translation Inspector Widget for MediaForge AI Studio.

Displays:
1. Timestamps (start -> end, duration)
2. Speaker identification (Speaker A, Speaker B, Female Lead, Male Lead, Actor name)
3. Emotional tone classification ([happy], [excited], [normal], [sad], [cry], [angry], [whisper])
4. Whisper Speech-to-Text output (original recognized speech)
5. Full untruncated translation (target text, editable in place)
6. Action controls: seek/audition player, live filter, save edits, sync to timeline, pop-out window.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
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

from modules.ai.engine import Transcript, TranscriptSegment, classify_segment_tone
from modules.ai.khmer_localizer import KhmerDialogueLocalizer

logger = logging.getLogger(__name__)


def _format_time(sec: float) -> str:
    """Format seconds into MM:SS.cc string."""
    m = int(sec // 60)
    s = sec % 60
    return f"{m:02d}:{s:05.2f}"


def _parse_time_token(token: str) -> float | None:
    """Parse time string like '01:23.45', '12.3', or '01:02:03' into seconds."""
    token = token.strip()
    if not token:
        return None
    if ":" in token:
        parts = token.split(":")
        try:
            if len(parts) == 2:
                return float(parts[0]) * 60.0 + float(parts[1])
            elif len(parts) == 3:
                return float(parts[0]) * 3600.0 + float(parts[1]) * 60.0 + float(parts[2])
        except ValueError:
            return None
    else:
        try:
            return float(token)
        except ValueError:
            return None
    return None


def _parse_timestamp_range(text: str, default_start: float, default_end: float) -> tuple[float, float]:
    """Parse user edited timestamp strings like '00:05.20 → 00:08.50 (3.3s)' into (start, end)."""
    clean_text = text.split("(")[0].strip()
    for sep in ["→", "->", "-->", "–", "—", " to "]:
        if sep in clean_text:
            parts = clean_text.split(sep, 1)
            t0 = _parse_time_token(parts[0])
            t1 = _parse_time_token(parts[1])
            if t0 is not None and t1 is not None and t1 > t0:
                return round(t0, 3), round(t1, 3)
    return default_start, default_end


class ScriptInspectorWidget(QWidget):
    """Full-featured Speech & Translation Inspector table with live search and tone badges."""

    transcript_updated = Signal(object)  # Emits Transcript when user saves edits
    seek_requested = Signal(int)         # Emits millisecond timestamp to seek player
    segment_replaced = Signal(object)    # Emits TranscriptSegment when user clicks "Replace" in editor
    replace_all_requested = Signal(object)  # Emits Transcript when user clicks "Replace All in Editor"


    def __init__(self, player_controller: Any | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.player_controller = player_controller
        self.current_transcript: Transcript | None = None
        self.current_json_path: Path | None = None
        self._all_segments: list[TranscriptSegment] = []
        self._is_popped_out = False
        self._popout_dialog: QDialog | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # 1. Top Controls Bar
        bar = QHBoxLayout()
        bar.setSpacing(8)

        # Title & Info Pill
        title_box = QHBoxLayout()
        title_box.setSpacing(6)
        icon_lbl = QLabel("📜")
        icon_lbl.setStyleSheet("font-size: 16px;")
        title_box.addWidget(icon_lbl)

        self.title_lbl = QLabel("Speech & Translation Inspector")
        self.title_lbl.setStyleSheet("color: #38bdf8; font-weight: 700; font-size: 12px;")
        title_box.addWidget(self.title_lbl)

        self.stats_badge = QLabel("No Transcript Loaded")
        self.stats_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #334155;
        """)
        title_box.addWidget(self.stats_badge)
        bar.addLayout(title_box)

        bar.addStretch()

        # Search Filter
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter dialogue, speaker, or tone...")
        self.search_input.setFixedWidth(220)
        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: #0f172a;
                border: 1px solid #334155;
                color: #ffffff;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 11px;
            }
            QLineEdit:focus { border: 1px solid #38bdf8; }
        """)
        self.search_input.textChanged.connect(self._apply_filters)
        bar.addWidget(self.search_input)

        # Speaker Filter
        self.speaker_filter = QComboBox()
        self.speaker_filter.addItem("All Speakers", None)
        self.speaker_filter.setFixedWidth(130)
        self.speaker_filter.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #334155;
            color: #cbd5e1;
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 11px;
        """)
        self.speaker_filter.currentIndexChanged.connect(self._apply_filters)
        bar.addWidget(self.speaker_filter)

        # Tone Filter
        self.tone_filter = QComboBox()
        self.tone_filter.addItem("All Tones", None)
        self.tone_filter.addItem("[happy]", "[happy]")
        self.tone_filter.addItem("[excited]", "[excited]")
        self.tone_filter.addItem("[normal]", "[normal]")
        self.tone_filter.addItem("[sad]", "[sad]")
        self.tone_filter.addItem("[cry]", "[cry]")
        self.tone_filter.addItem("[angry]", "[angry]")
        self.tone_filter.addItem("[whisper]", "[whisper]")
        self.tone_filter.setFixedWidth(110)
        self.tone_filter.setStyleSheet("""
            background-color: #0f172a;
            border: 1px solid #334155;
            color: #cbd5e1;
            padding: 3px 6px;
            border-radius: 4px;
            font-size: 11px;
        """)
        self.tone_filter.currentIndexChanged.connect(self._apply_filters)
        bar.addWidget(self.tone_filter)

        # Save Edits Button
        self.save_btn = QPushButton("💾 Save Edits")
        self.save_btn.setToolTip("Save modifications to transcript and update timeline")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #047857; }
        """)
        self.save_btn.clicked.connect(self.save_edits)
        bar.addWidget(self.save_btn)

        # Naturalize Khmer Button
        self.naturalize_btn = QPushButton("✨ Naturalize Khmer")
        self.naturalize_btn.setToolTip("Transform literal/dictionary Khmer translations into fluent, natural spoken dialogue with gender concordance")
        self.naturalize_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: #ffffff;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 4px;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #6d28d9; }
        """)
        self.naturalize_btn.clicked.connect(self.naturalize_all_khmer)
        bar.addWidget(self.naturalize_btn)

        # Replace All in Editor Button
        self.replace_all_btn = QPushButton("📥 Replace All in Editor")
        self.replace_all_btn.setToolTip("Insert/replace all translations and timestamps into Video Editor timeline and subtitles at once")
        self.replace_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 4px;
                border: none;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.replace_all_btn.clicked.connect(self.replace_all_in_editor)
        bar.addWidget(self.replace_all_btn)

        # Export Button
        self.export_btn = QPushButton("📤 Export...")
        self.export_btn.setToolTip("Export dialogue transcript to SRT, VTT, JSON, or CSV")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #cbd5e1;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid #334155;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #334155; color: #ffffff; }
        """)
        self.export_btn.clicked.connect(self._on_export_clicked)
        bar.addWidget(self.export_btn)

        # Pop out / In Button
        self.popout_btn = QPushButton("🗖 Pop Out")
        self.popout_btn.setToolTip("Open in separate floating window for multi-monitor workflow")
        self.popout_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: 600;
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid #38bdf8;
                font-size: 11px;
            }
            QPushButton:hover { background-color: #0284c7; color: #ffffff; }
        """)
        self.popout_btn.clicked.connect(self._toggle_popout)
        bar.addWidget(self.popout_btn)

        layout.addLayout(bar)

        # 2. Main Dialogue Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "#",
            "⏱️ Timestamp",
            "🗣️ Speaker",
            "🎭 Tone",
            "🎙️ Whisper STT (Speech-to-Text)",
            "🌐 Translation (Target Text - Editable)",
            "▶️ Seek",
            "📥 Editor",
        ])

        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #090d16;
                color: #f1f5f9;
                gridline-color: #1e293b;
                border: 1px solid #1e293b;
                border-radius: 6px;
                selection-background-color: #1e3a5f;
                selection-color: #ffffff;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #131b2e;
                color: #94a3b8;
                font-weight: 700;
                font-size: 11px;
                padding: 6px;
                border: none;
                border-right: 1px solid #1e293b;
                border-bottom: 1px solid #1e293b;
            }
            QTableWidget::item {
                padding: 4px 6px;
                border-bottom: 1px solid #131b2e;
            }
            QTableWidget::item:focus {
                background-color: #1e293b;
            }
        """)

        # Set column widths & resize modes
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 36)

        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(1, 145)

        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(2, 150)

        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(3, 90)

        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)

        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(6, 50)

        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(7, 95)

        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemClicked.connect(self._on_table_item_clicked)
        self.table.itemDoubleClicked.connect(self._on_table_item_double_clicked)

        layout.addWidget(self.table, 1)


    def load_transcript(self, transcript: Transcript | list[TranscriptSegment] | list[dict[str, Any]] | Path | str, json_path: Path | str | None = None) -> None:
        """Load transcript segments into the inspector table."""
        if isinstance(transcript, (str, Path)):
            p = Path(transcript).resolve()
            self.current_json_path = p
            if p.exists():
                try:
                    self.current_transcript = Transcript.load_json(p)
                except Exception as e:
                    logger.warning("Failed to load transcript from %s: %s", p, e)
                    return
            else:
                return
        elif isinstance(transcript, Transcript):
            self.current_transcript = transcript
            if json_path:
                self.current_json_path = Path(json_path).resolve()
        elif isinstance(transcript, list):
            if transcript and isinstance(transcript[0], dict):
                self.current_transcript = Transcript.from_dict(transcript)
            else:
                self.current_transcript = Transcript(segments=transcript)
            if json_path:
                self.current_json_path = Path(json_path).resolve()

        if not self.current_transcript:
            return

        self._all_segments = list(self.current_transcript.segments)

        # Update speaker filter list
        speakers = sorted(list(dict.fromkeys(s.speaker for s in self._all_segments if s.speaker)))
        self.speaker_filter.blockSignals(True)
        self.speaker_filter.clear()
        self.speaker_filter.addItem("All Speakers", None)
        for spk in speakers:
            self.speaker_filter.addItem(spk, spk)
        self.speaker_filter.blockSignals(False)

        # Populate table
        self._populate_table(self._all_segments)

        # Update status pill
        total = len(self._all_segments)
        lang = self.current_transcript.language or "auto"
        self.stats_badge.setText(f"{total} lines • {len(speakers)} speakers • Lang: {lang.upper()}")
        self.stats_badge.setStyleSheet("""
            background-color: #14532d;
            color: #4ade80;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #16a34a;
        """)

    def _populate_table(self, segments: list[TranscriptSegment]) -> None:
        """Render dialogue segments into table rows."""
        self.table.setRowCount(len(segments))

        for row, seg in enumerate(segments):
            # 0. Index
            idx_item = QTableWidgetItem(str(seg.id))
            idx_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            idx_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            idx_item.setForeground(QColor(148, 163, 184))
            self.table.setItem(row, 0, idx_item)

            # 1. Timestamp (start -> end, duration) - Editable
            t_str = f"{_format_time(seg.start)} → {_format_time(seg.end)} ({seg.end - seg.start:.1f}s)"
            time_item = QTableWidgetItem(t_str)
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            time_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            time_item.setForeground(QColor(56, 189, 248))  # Cyan/Sky
            time_item.setData(Qt.ItemDataRole.UserRole, (seg.start, seg.end))
            self.table.setItem(row, 1, time_item)

            # 2. Speaker Badge
            spk_text = seg.speaker or "Speaker 1"
            spk_item = QTableWidgetItem(spk_text)
            spk_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)

            # Speaker color coding
            spk_lower = spk_text.lower()
            if "female" in spk_lower or "emma" in spk_lower or ("2" in spk_lower and "1" not in spk_lower):
                spk_item.setForeground(QColor(244, 114, 182))  # Pink
            elif "child" in spk_lower or "kid" in spk_lower or "boy" in spk_lower or "girl" in spk_lower:
                spk_item.setForeground(QColor(251, 191, 36))   # Amber
            elif "male" in spk_lower or "james" in spk_lower:
                spk_item.setForeground(QColor(129, 140, 248))  # Indigo / Soft Blue
            else:
                spk_item.setForeground(QColor(167, 139, 250))  # Violet
            self.table.setItem(row, 2, spk_item)

            # 3. Tone / Emotion Badge
            tone_val = getattr(seg, "emotion", None)
            if not tone_val or tone_val == "normal":
                tone_val = classify_segment_tone(seg.source_text)
            if not tone_val.startswith("["):
                tone_val = f"[{tone_val}]"

            tone_item = QTableWidgetItem(tone_val)
            tone_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            tone_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            # Emotion color coding
            t_lower = tone_val.lower()
            if "[excited]" in t_lower or "[happy]" in t_lower:
                tone_item.setForeground(QColor(52, 211, 153))  # Emerald Green
            elif "[sad]" in t_lower or "[grief]" in t_lower:
                tone_item.setForeground(QColor(96, 165, 250))  # Blue
            elif "[cry]" in t_lower or "[sob]" in t_lower:
                tone_item.setForeground(QColor(148, 163, 184))  # Slate Gray
            elif "[angry]" in t_lower or "[shout]" in t_lower:
                tone_item.setForeground(QColor(248, 113, 113))  # Coral Red
            elif "[whisper]" in t_lower:
                tone_item.setForeground(QColor(45, 212, 191))   # Teal
            else:
                tone_item.setForeground(QColor(165, 180, 252))  # Soft Periwinkle (Normal)

            font = tone_item.font()
            font.setBold(True)
            tone_item.setFont(font)
            self.table.setItem(row, 3, tone_item)

            # 4. Whisper STT (Speech-to-Text)
            stt_item = QTableWidgetItem(seg.source_text)
            stt_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            stt_item.setForeground(QColor(241, 245, 249))
            self.table.setItem(row, 4, stt_item)

            # 5. Translation (Target Text - Editable)
            trans_item = QTableWidgetItem(seg.target_text)
            trans_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable)
            trans_item.setForeground(QColor(254, 240, 138))  # Warm Soft Gold
            self.table.setItem(row, 5, trans_item)

            # 6. Seek Button
            play_btn = QPushButton("▶")
            play_btn.setToolTip(f"Jump player to {_format_time(seg.start)}")
            play_btn.setFixedWidth(36)
            play_btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #38bdf8;
                    border: 1px solid #334155;
                    border-radius: 4px;
                    font-size: 11px;
                    padding: 2px;
                }
                QPushButton:hover {
                    background-color: #0284c7;
                    color: #ffffff;
                }
            """)
            start_ms = int(seg.start * 1000)
            play_btn.clicked.connect(lambda _, ms=start_ms: self._seek_player(ms))
            self.table.setCellWidget(row, 6, play_btn)

            # 7. Replace in Video Editor Button
            replace_btn = QPushButton("📥 Replace")
            replace_btn.setToolTip(f"Insert/replace sentence #{seg.id} translation & timestamp into Video Editor")
            replace_btn.setFixedWidth(80)
            replace_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0d9488;
                    color: #ffffff;
                    border: 1px solid #14b8a6;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 600;
                    padding: 2px 4px;
                }
                QPushButton:hover {
                    background-color: #0f766e;
                }
            """)
            replace_btn.clicked.connect(lambda _, r=row, b=replace_btn: self._replace_sentence_in_editor(r, b))
            self.table.setCellWidget(row, 7, replace_btn)

    def _on_table_item_clicked(self, item: QTableWidgetItem) -> None:
        """Single click seeks video player to the start of this segment."""
        row = item.row()
        time_item = self.table.item(row, 1)
        if time_item:
            data = time_item.data(Qt.ItemDataRole.UserRole)
            if data and len(data) >= 1:
                start_sec = data[0]
                self._seek_player(int(start_sec * 1000))

    def _on_table_item_double_clicked(self, item: QTableWidgetItem) -> None:
        """Double click on non-editable columns seeks player."""
        if item.column() not in (1, 2, 5):
            self._on_table_item_clicked(item)

    def _seek_player(self, ms: int) -> None:
        """Seek video player controller to timestamp in milliseconds."""
        self.seek_requested.emit(ms)
        if self.player_controller:
            try:
                self.player_controller.seek_to(ms)
            except Exception as e:
                logger.debug("Failed to seek player: %s", e)

    def _replace_sentence_in_editor(self, row: int, btn: QPushButton | None = None) -> None:
        """Insert or replace the edited translation and timestamp of a single sentence into the video editor."""
        idx_item = self.table.item(row, 0)
        if not idx_item:
            return
        try:
            seg_id = int(idx_item.text())
        except ValueError:
            return

        seg = next((s for s in self._all_segments if s.id == seg_id), None)
        if not seg:
            return

        time_item = self.table.item(row, 1)
        if time_item:
            new_start, new_end = _parse_timestamp_range(time_item.text(), seg.start, seg.end)
            seg.start = new_start
            seg.end = new_end
            time_item.setData(Qt.ItemDataRole.UserRole, (seg.start, seg.end))

        spk_item = self.table.item(row, 2)
        if spk_item:
            seg.speaker = spk_item.text().strip()

        trans_item = self.table.item(row, 5)
        if trans_item:
            seg.target_text = trans_item.text().strip()

        # Invalidate cached TTS clip if workdir exists so next dubbing synthesizes fresh speech
        self._invalidate_tts_clip(seg.id)

        # Save to companion JSON if available
        if self.current_json_path and self.current_json_path.exists():
            try:
                self.current_transcript.save_json(self.current_json_path)
            except Exception as e:
                logger.debug("Could not auto-save JSON: %s", e)

        # Emit signals to update Timeline, PlayerController, and Studio
        self.segment_replaced.emit(seg)
        self.transcript_updated.emit(self.current_transcript)

        # Visual feedback on the button
        if btn:
            orig_text = btn.text()
            orig_style = btn.styleSheet()
            btn.setText("✅ Replaced!")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #15803d;
                    color: #ffffff;
                    border: 1px solid #22c55e;
                    border-radius: 4px;
                    font-size: 11px;
                    font-weight: 700;
                    padding: 2px 4px;
                }
            """)
            QTimer.singleShot(1500, lambda: self._reset_btn(btn, orig_text, orig_style))

    def _reset_btn(self, btn: QPushButton, text: str, style: str) -> None:
        try:
            btn.setText(text)
            btn.setStyleSheet(style)
        except RuntimeError:
            pass

    def _invalidate_tts_clip(self, seg_id: int) -> None:
        """Remove stale synthesized TTS clip so next pipeline run regenerates audio."""
        if not self.current_json_path:
            return
        workdir = self.current_json_path.parent
        tts_dir = workdir / "tts_clips"
        if tts_dir.exists():
            for p in tts_dir.glob(f"tts_*_{seg_id}.wav"):
                try:
                    p.unlink(missing_ok=True)
                    logger.info("Invalidated stale TTS clip for sentence #%d: %s", seg_id, p.name)
                except Exception:
                    pass

    def replace_all_in_editor(self) -> None:
        """Insert/replace all inspected sentences, translations, and timestamps into the Video Editor."""
        if not self.current_transcript or not self._all_segments:
            return

        for row in range(self.table.rowCount()):
            idx_item = self.table.item(row, 0)
            if not idx_item:
                continue
            try:
                seg_id = int(idx_item.text())
            except ValueError:
                continue

            seg = next((s for s in self._all_segments if s.id == seg_id), None)
            if not seg:
                continue

            time_item = self.table.item(row, 1)
            if time_item:
                new_start, new_end = _parse_timestamp_range(time_item.text(), seg.start, seg.end)
                seg.start = new_start
                seg.end = new_end
                time_item.setData(Qt.ItemDataRole.UserRole, (seg.start, seg.end))

            spk_item = self.table.item(row, 2)
            if spk_item:
                seg.speaker = spk_item.text().strip()

            trans_item = self.table.item(row, 5)
            if trans_item:
                seg.target_text = trans_item.text().strip()

            self._invalidate_tts_clip(seg.id)

        # Save to companion JSON
        if self.current_json_path and self.current_json_path.exists():
            try:
                self.current_transcript.save_json(self.current_json_path)
            except Exception as e:
                logger.debug("Could not auto-save JSON on replace all: %s", e)

        # Emit batch update signals
        self.replace_all_requested.emit(self.current_transcript)
        self.transcript_updated.emit(self.current_transcript)

        # Visual feedback on Replace All button
        orig_text = self.replace_all_btn.text()
        orig_style = self.replace_all_btn.styleSheet()
        self.replace_all_btn.setText("✅ All Replaced!")
        self.replace_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #15803d;
                color: #ffffff;
                font-weight: 700;
                padding: 4px 12px;
                border-radius: 4px;
                border: 1px solid #22c55e;
                font-size: 11px;
            }
        """)
        QTimer.singleShot(2000, lambda: self._reset_btn(self.replace_all_btn, orig_text, orig_style))

        self.stats_badge.setText(f"✅ Synced {len(self._all_segments)} lines to Video Editor")
        self.stats_badge.setStyleSheet("""
            background-color: #14532d;
            color: #4ade80;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #16a34a;
        """)

    def naturalize_all_khmer(self) -> None:
        """Upgrade all segment translations in the table to natural spoken conversational Khmer."""
        if not self.current_transcript or not self._all_segments:
            return

        modified_count = 0
        for row in range(self.table.rowCount()):
            idx_item = self.table.item(row, 0)
            if not idx_item:
                continue
            try:
                seg_id = int(idx_item.text())
            except ValueError:
                continue

            seg = next((s for s in self._all_segments if s.id == seg_id), None)
            if not seg:
                continue

            spk_item = self.table.item(row, 2)
            speaker_name = spk_item.text().strip() if spk_item else seg.speaker

            trans_item = self.table.item(row, 5)
            curr_text = trans_item.text().strip() if trans_item else seg.target_text

            if curr_text:
                natural_text = KhmerDialogueLocalizer.naturalize(
                    curr_text,
                    speaker_name=speaker_name,
                )
                if natural_text != curr_text:
                    modified_count += 1
                    seg.target_text = natural_text
                    if trans_item:
                        trans_item.setText(natural_text)
                    self._invalidate_tts_clip(seg.id)

        # Save to companion JSON if available
        if self.current_json_path and self.current_json_path.exists():
            try:
                self.current_transcript.save_json(self.current_json_path)
            except Exception as e:
                logger.debug("Could not auto-save JSON on naturalize: %s", e)

        self.transcript_updated.emit(self.current_transcript)

        # Visual feedback on button
        orig_text = self.naturalize_btn.text()
        orig_style = self.naturalize_btn.styleSheet()
        self.naturalize_btn.setText("✅ Naturalized!")
        self.naturalize_btn.setStyleSheet("""
            QPushButton {
                background-color: #15803d;
                color: #ffffff;
                font-weight: 700;
                padding: 4px 10px;
                border-radius: 4px;
                border: 1px solid #22c55e;
                font-size: 11px;
            }
        """)
        QTimer.singleShot(2000, lambda: self._reset_btn(self.naturalize_btn, orig_text, orig_style))

        self.stats_badge.setText(f"✨ Naturalized {modified_count} lines into Natural Khmer")
        self.stats_badge.setStyleSheet("""
            background-color: #4c1d95;
            color: #c4b5fd;
            font-size: 11px;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 4px;
            border: 1px solid #8b5cf6;
        """)

    def _apply_filters(self) -> None:
        """Filter table rows based on search text, selected speaker, and tone."""
        query = self.search_input.text().strip().lower()
        sel_spk = self.speaker_filter.currentData()
        sel_tone = self.tone_filter.currentData()

        for row in range(self.table.rowCount()):
            spk_item = self.table.item(row, 2)
            tone_item = self.table.item(row, 3)
            stt_item = self.table.item(row, 4)
            trans_item = self.table.item(row, 5)

            spk_text = spk_item.text().lower() if spk_item else ""
            tone_text = tone_item.text().lower() if tone_item else ""
            stt_text = stt_item.text().lower() if stt_item else ""
            trans_text = trans_item.text().lower() if trans_item else ""

            match_query = True
            if query:
                match_query = (
                    query in spk_text
                    or query in tone_text
                    or query in stt_text
                    or query in trans_text
                )

            match_spk = True
            if sel_spk:
                match_spk = sel_spk.lower() in spk_text

            match_tone = True
            if sel_tone:
                match_tone = sel_tone.lower() in tone_text

            self.table.setRowHidden(row, not (match_query and match_spk and match_tone))

    def save_edits(self, show_dialog: bool = True) -> None:
        """Save user edits back to the transcript and json file."""
        if not self.current_transcript or not self._all_segments:
            return

        # Harvest modified fields from table
        for row in range(self.table.rowCount()):
            idx_item = self.table.item(row, 0)
            if not idx_item:
                continue
            seg_id = int(idx_item.text())

            # Find matching segment
            seg = next((s for s in self._all_segments if s.id == seg_id), None)
            if not seg:
                continue

            time_item = self.table.item(row, 1)
            if time_item:
                new_start, new_end = _parse_timestamp_range(time_item.text(), seg.start, seg.end)
                seg.start = new_start
                seg.end = new_end
                time_item.setData(Qt.ItemDataRole.UserRole, (seg.start, seg.end))

            spk_item = self.table.item(row, 2)
            if spk_item:
                seg.speaker = spk_item.text().strip()

            trans_item = self.table.item(row, 5)
            if trans_item:
                seg.target_text = trans_item.text().strip()

            self._invalidate_tts_clip(seg.id)

        # Save to companion JSON if available
        if self.current_json_path and self.current_json_path.exists():
            try:
                self.current_transcript.save_json(self.current_json_path)
                logger.info("Saved edited transcript to %s", self.current_json_path)
            except Exception as e:
                logger.warning("Failed to save transcript to %s: %s", self.current_json_path, e)

        self.transcript_updated.emit(self.current_transcript)
        if show_dialog:
            QMessageBox.information(
                self,
                "Edits Saved",
                "Transcript modifications saved successfully and synced to timeline!",
            )


    def _on_export_clicked(self) -> None:
        """Export current script to SRT, VTT, JSON, or CSV."""
        if not self._all_segments:
            QMessageBox.warning(self, "No Transcript", "No transcript loaded to export.")
            return

        out_path, sel_filter = QFileDialog.getSaveFileName(
            self,
            "Export Dialogue Script",
            "dialogue_script.srt",
            "SubRip Subtitle (*.srt);;WebVTT (*.vtt);;JSON Transcript (*.json);;CSV Spreadsheet (*.csv);;Plain Text (*.txt)",
        )
        if not out_path:
            return

        p = Path(out_path)
        try:
            if p.suffix.lower() == ".srt":
                lines = []
                for i, s in enumerate(self._all_segments, start=1):
                    start_str = _format_srt_time(s.start)
                    end_str = _format_srt_time(s.end)
                    text = s.target_text or s.source_text
                    lines.append(f"{i}\n{start_str} --> {end_str}\n{s.speaker}: {text}\n")
                p.write_text("\n".join(lines), encoding="utf-8")

            elif p.suffix.lower() == ".vtt":
                lines = ["WEBVTT\n"]
                for s in self._all_segments:
                    start_str = _format_vtt_time(s.start)
                    end_str = _format_vtt_time(s.end)
                    text = s.target_text or s.source_text
                    lines.append(f"{start_str} --> {end_str}\n<v {s.speaker}>{text}\n")
                p.write_text("\n".join(lines), encoding="utf-8")

            elif p.suffix.lower() == ".json":
                self.current_transcript.save_json(p)

            elif p.suffix.lower() == ".csv":
                import csv
                with open(p, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(["ID", "Start_Sec", "End_Sec", "Speaker", "Tone", "Whisper_STT", "Translation"])
                    for s in self._all_segments:
                        tone = getattr(s, "emotion", "") or classify_segment_tone(s.source_text)
                        writer.writerow([s.id, f"{s.start:.3f}", f"{s.end:.3f}", s.speaker, tone, s.source_text, s.target_text])

            else:
                lines = []
                for s in self._all_segments:
                    tone = getattr(s, "emotion", "") or classify_segment_tone(s.source_text)
                    lines.append(f"[{_format_time(s.start)} - {_format_time(s.end)}] {s.speaker} {tone}:\nSTT: {s.source_text}\nTR : {s.target_text}\n")
                p.write_text("\n".join(lines), encoding="utf-8")

            QMessageBox.information(self, "Export Complete", f"Exported successfully to:\n{p.name}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export script:\n\n{e}")

    def _toggle_popout(self) -> None:
        """Pop out the widget into a floating dialog window, or dock back into Studio."""
        if not self._is_popped_out:
            self._popout_dialog = ScriptInspectorDialog(self.player_controller, parent=self.window())
            if self.current_transcript:
                self._popout_dialog.inspector.load_transcript(self.current_transcript, self.current_json_path)

            self.popout_btn.setText("📥 Dock in Studio")
            self._is_popped_out = True
            self._popout_dialog.finished.connect(self._on_popout_closed)
            self._popout_dialog.show()
        else:
            if self._popout_dialog:
                self._popout_dialog.close()
                self._popout_dialog = None
            self.popout_btn.setText("🗖 Pop Out")
            self._is_popped_out = False

    def _on_popout_closed(self) -> None:
        self._is_popped_out = False
        self.popout_btn.setText("🗖 Pop Out")


class ScriptInspectorDialog(QDialog):
    """Floating window housing the Script & Translation Inspector for multi-monitor setups."""

    def __init__(self, player_controller: Any | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("MediaForge AI — Speech & Translation Inspector")
        self.resize(1100, 650)
        self.setStyleSheet("background-color: #0b0f17; color: #ffffff;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self.inspector = ScriptInspectorWidget(player_controller=player_controller, parent=self)
        self.inspector.popout_btn.setVisible(False)  # Hidden inside floating dialog
        layout.addWidget(self.inspector)


def _format_srt_time(sec: float) -> str:
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    msec = int(round((sec - int(sec)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msec:03d}"


def _format_vtt_time(sec: float) -> str:
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    msec = int(round((sec - int(sec)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{msec:03d}"

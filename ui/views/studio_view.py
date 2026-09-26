"""Studio view module with video player, frame stepping, subtitle overlay, timeline, and unified Auto-Process pipeline."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.cancellation import CancellationToken
from modules.ai.diarizer import DiarizerEngine, DiarizerInput
from modules.ai.engine import Transcript
from modules.ai.separator import SeparatorEngine, SeparatorInput
from modules.ai.transcriber import TranscriberEngine, TranscriberInput
from modules.media.inspector import MediaMetadata
from modules.processing.pipeline import PipelineConfig, PipelineEngine, PipelineResult
from ui.components.timeline import MultiTrackTimelineWidget, TimelineClip
from ui.components.video_player import VideoPlayerWidget
from ui.views.script_inspector import ScriptInspectorWidget

logger = logging.getLogger("mediaforge.studio")


class PowerVoiceSeparatorDialog(QDialog):
    """Configuration dialog for Power Voice Separator, extracting actor/character names and speaker counts."""

    def __init__(self, video_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🎙️ Power Voice Separator")
        self.setMinimumWidth(520)
        self.video_path = Path(video_path).resolve()
        self.characters: list[dict[str, str]] = []
        self._load_existing_characters()
        self._build_ui()

    def _load_existing_characters(self) -> None:
        meta_path = self.video_path.with_suffix(".meta.json")
        if meta_path.exists():
            try:
                with open(meta_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.characters = data.get("characters") or []
                    self.saved_url = data.get("url") or ""
            except Exception:
                self.saved_url = ""
        else:
            self.saved_url = ""

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title & Explanation
        title = QLabel("🎙️ Power Voice Separator")
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #a78bfa;")
        layout.addWidget(title)

        desc = QLabel(
            "Distinguish and separate every actor's voice (Male, Female, Child, Elderly).\n"
            "Paste a movie URL to auto-extract character and actor names."
        )
        desc.setStyleSheet("color: #94a3b8; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # URL Input Row
        url_box = QFrame()
        url_box.setStyleSheet(
            "background-color: #1e1e2e; border: 1px solid #313244; border-radius: 8px; padding: 10px;"
        )
        u_layout = QVBoxLayout(url_box)
        u_layout.setSpacing(6)

        url_lbl = QLabel("Movie / Drama URL (Optional - For Character Extraction):")
        url_lbl.setStyleSheet("color: #cdd6f4; font-weight: 600; font-size: 11px;")
        u_layout.addWidget(url_lbl)

        row = QHBoxLayout()
        self.url_input = QLineEdit(getattr(self, "saved_url", ""))
        self.url_input.setPlaceholderText("e.g. https://hongguoduanju.com/player/7685350746975390744")
        self.url_input.setStyleSheet(
            "background-color: #11111b; border: 1px solid #45475a; color: #ffffff; padding: 6px; border-radius: 4px;"
        )
        row.addWidget(self.url_input, 1)

        self.fetch_chars_btn = QPushButton("🔍 Extract Actors")
        self.fetch_chars_btn.setStyleSheet(
            "background-color: #4f46e5; color: #ffffff; font-weight: 600; padding: 6px 12px; border-radius: 4px;"
        )
        self.fetch_chars_btn.clicked.connect(self._on_fetch_characters)
        row.addWidget(self.fetch_chars_btn)
        u_layout.addLayout(row)

        self.chars_status_lbl = QLabel()
        self._update_chars_status_label()
        u_layout.addWidget(self.chars_status_lbl)
        layout.addWidget(url_box)

        # Speaker count selection
        spk_box = QFrame()
        spk_box.setStyleSheet(
            "background-color: #1e1e2e; border: 1px solid #313244; border-radius: 8px; padding: 10px;"
        )
        s_layout = QVBoxLayout(spk_box)
        s_layout.setSpacing(8)

        spk_title = QLabel("Speaker Separation Mode:")
        spk_title.setStyleSheet("color: #cdd6f4; font-weight: 600; font-size: 11px;")
        s_layout.addWidget(spk_title)

        self.spk_combo = QComboBox()
        self.spk_combo.addItem("Auto-Detect (Separate all voices: Male, Female, Child, Elderly)", None)
        self.spk_combo.addItem("2 Speakers (Male Lead + Female Lead)", 2)
        self.spk_combo.addItem("3 Speakers (Male, Female, Child/Elderly)", 3)
        self.spk_combo.addItem("4 Speakers (4 distinct actor voices)", 4)
        self.spk_combo.addItem("5 Speakers (5 distinct actor voices)", 5)
        self.spk_combo.addItem("6 Speakers (6 distinct actor voices)", 6)
        self.spk_combo.addItem("8 Speakers (Multi-cast ensemble)", 8)
        self.spk_combo.addItem("10 Speakers (Maximum full cast)", 10)
        self.spk_combo.setStyleSheet(
            "background-color: #11111b; border: 1px solid #45475a; color: #ffffff; padding: 6px; border-radius: 4px;"
        )
        s_layout.addWidget(self.spk_combo)
        layout.addWidget(spk_box)

        # Action Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        run_btn = QPushButton("🎙️ Start Power Separation")
        run_btn.setStyleSheet(
            "background-color: #7c3aed; color: #ffffff; font-weight: 700; padding: 8px 18px; border-radius: 6px;"
        )
        run_btn.clicked.connect(self.accept)
        btn_row.addWidget(run_btn)

        layout.addLayout(btn_row)

    def _update_chars_status_label(self) -> None:
        if self.characters:
            names = ", ".join(c.get("display", "") for c in self.characters[:6])
            suffix = "..." if len(self.characters) > 6 else ""
            self.chars_status_lbl.setText(f"✅ Found {len(self.characters)} actors/characters: {names}{suffix}")
            self.chars_status_lbl.setStyleSheet("color: #10b981; font-size: 11px; font-weight: 600;")
        else:
            self.chars_status_lbl.setText(
                "No movie characters linked yet. Paste URL above or run with auto-detected vocal profiles."
            )
            self.chars_status_lbl.setStyleSheet("color: #6b7280; font-size: 11px;")

    def _on_fetch_characters(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "URL Required", "Please enter a drama or movie URL.")
            return

        from modules.downloader.hongguo import HongguoExtractor

        self.fetch_chars_btn.setEnabled(False)
        self.chars_status_lbl.setText("Fetching drama cast from URL...")
        try:
            chars = HongguoExtractor.extract_characters_from_url(url)
            if chars:
                self.characters = chars
                self._update_chars_status_label()
                meta_path = self.video_path.with_suffix(".meta.json")
                try:
                    with open(meta_path, "w", encoding="utf-8") as mf:
                        json.dump({"url": url, "characters": chars}, mf, indent=2, ensure_ascii=False)
                except Exception:
                    pass
            else:
                self.chars_status_lbl.setText("No celebrities/characters found at this URL.")
                self.chars_status_lbl.setStyleSheet("color: #f59e0b; font-size: 11px;")
        except Exception as e:
            self.chars_status_lbl.setText(f"Fetch failed: {e}")
            self.chars_status_lbl.setStyleSheet("color: #ef4444; font-size: 11px;")
        finally:
            self.fetch_chars_btn.setEnabled(True)

    def get_selection(self) -> tuple[int | None, list[dict[str, str]]]:
        num_spk = self.spk_combo.currentData()
        return num_spk, self.characters


class StudioTaskSignals(QObject):
    """Bridge for background worker threads to safely dispatch updates to the Qt GUI thread."""

    progress = Signal(int, str)
    completed = Signal(object)
    error = Signal(str)


class StudioView(QWidget):
    """Integrated studio view hosting the video player, multi-track timeline, and auto-process DAG pipeline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_token: CancellationToken | None = None
        self._last_result: PipelineResult | None = None
        self._active_task_signals: StudioTaskSignals | None = None
        self._original_source_video_path: Path | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 14)
        layout.setSpacing(10)

        # 1. Header & Actions Bar
        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("AI Studio")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #ffffff;")
        desc = QLabel("Frame-accurate player, multi-track timeline, and unified 1-click Auto-Process pipeline.")
        desc.setStyleSheet("color: #9ca3af; font-size: 11px;")
        header.addWidget(title)
        header.addWidget(desc)
        top_bar.addLayout(header)

        top_bar.addStretch()

        # Metadata Badge Pill
        self.meta_badge = QLabel("No Media Loaded")
        self.meta_badge.setStyleSheet("""
            background-color: #1e2433;
            color: #94a3b8;
            font-size: 11px;
            font-weight: 600;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #2d3748;
        """)
        top_bar.addWidget(self.meta_badge)

        # Open Media Button
        open_btn = QPushButton("📁 Open Media...")
        open_btn.setToolTip("Open a video file (.mp4, .mkv, .mov, .webm) in AI Studio")
        open_btn.clicked.connect(self._on_open_media_clicked)
        top_bar.addWidget(open_btn)

        # Load Subtitles Button
        load_sub_btn = QPushButton("💬 Load Subtitles...")
        load_sub_btn.setToolTip("Load external subtitle file (.srt, .vtt) for overlay and sync")
        load_sub_btn.clicked.connect(self._on_load_subtitles_clicked)
        top_bar.addWidget(load_sub_btn)

        # Power Voice Separator Button
        self.transcribe_btn = QPushButton("🎙️ Power Voice Separator")
        self.transcribe_btn.setToolTip("Separate male, female, child, elderly voices & link movie cast actors")
        self.transcribe_btn.setStyleSheet("""
            QPushButton {
                background-color: #7c3aed;
                color: #ffffff;
                font-weight: 700;
                padding: 5px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #6d28d9; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.transcribe_btn.clicked.connect(self._on_transcribe_clicked)
        top_bar.addWidget(self.transcribe_btn)

        # Separate Stems Button
        self.separate_btn = QPushButton("🎵 Separate Stems")
        self.separate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4f46e5;
                color: #ffffff;
                font-weight: 600;
                padding: 5px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #4338ca; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.separate_btn.setToolTip("MDX-Net ONNX stem separation (vocals & BGM).")
        self.separate_btn.clicked.connect(self._on_separate_clicked)
        top_bar.addWidget(self.separate_btn)

        # Script & Translation Inspector Button
        self.open_inspector_btn = QPushButton("📜 Inspector")
        self.open_inspector_btn.setToolTip("Switch to Speech-to-Text & Translation Inspector table or pop out window")
        self.open_inspector_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                font-weight: 600;
                padding: 5px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #0369a1; }
        """)
        self.open_inspector_btn.clicked.connect(self._on_open_inspector_clicked)
        top_bar.addWidget(self.open_inspector_btn)

        layout.addLayout(top_bar)

        # 2. Unified Auto-Process Pipeline Control Strip
        pipeline_strip = QFrame()
        pipeline_strip.setStyleSheet("""
            QFrame {
                background-color: #131b2e;
                border: 1px solid #1e293b;
                border-radius: 8px;
            }
        """)
        ps_layout = QHBoxLayout(pipeline_strip)
        ps_layout.setContentsMargins(12, 6, 12, 6)
        ps_layout.setSpacing(10)

        ps_lbl = QLabel("⚡ Auto-Process Pipeline:")
        ps_lbl.setStyleSheet("font-weight: 700; color: #38bdf8; font-size: 12px;")
        ps_layout.addWidget(ps_lbl)

        # Target Language Dropdown
        lang_lbl = QLabel("Target:")
        lang_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ps_layout.addWidget(lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.addItem("Khmer (km)", "km")
        self.lang_combo.addItem("English (en)", "en")
        self.lang_combo.addItem("Chinese (zh)", "zh")
        self.lang_combo.addItem("Japanese (ja)", "ja")
        self.lang_combo.addItem("Korean (ko)", "ko")
        self.lang_combo.setFixedWidth(120)
        ps_layout.addWidget(self.lang_combo)

        # Translation Provider Dropdown
        prov_lbl = QLabel("Engine:")
        prov_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ps_layout.addWidget(prov_lbl)

        self.prov_combo = QComboBox()
        self.prov_combo.addItem("Natural Khmer AI (Free)", "libre")
        self.prov_combo.addItem("Gemini 2.0 Flash", "gemini")
        self.prov_combo.addItem("DeepSeek V3", "deepseek")
        self.prov_combo.addItem("Qwen Turbo", "qwen")
        self.prov_combo.setFixedWidth(160)
        ps_layout.addWidget(self.prov_combo)

        # Voices / Speaker Count Mode Dropdown
        spk_lbl = QLabel("Voices:")
        spk_lbl.setStyleSheet("color: #94a3b8; font-size: 11px;")
        ps_layout.addWidget(spk_lbl)

        self.spk_mode_combo = QComboBox()
        self.spk_mode_combo.addItem("Auto (All Voices)", None)
        self.spk_mode_combo.addItem("2 Voices (Male + Female)", 2)
        self.spk_mode_combo.addItem("3 Voices (Male, Female, Child)", 3)
        self.spk_mode_combo.addItem("4 Voices (Multi-Cast)", 4)
        self.spk_mode_combo.addItem("5+ Voices (Full Ensemble)", 5)
        self.spk_mode_combo.setFixedWidth(155)
        ps_layout.addWidget(self.spk_mode_combo)

        # Run Auto-Process Button
        self.autoprocess_btn = QPushButton("⚡ Run Full Auto-Process")
        self.autoprocess_btn.setToolTip("Run 1-Click Automated Processing (Inspect, Transcribe, Stems, Translate, TTS, Mix, Mux)")
        self.autoprocess_btn.setStyleSheet("""
            QPushButton {
                background-color: #059669;
                color: #ffffff;
                font-weight: 700;
                font-size: 12px;
                padding: 6px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #047857; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.autoprocess_btn.clicked.connect(self._on_autoprocess_clicked)
        ps_layout.addWidget(self.autoprocess_btn)

        # Fresh Dubbing Checkbox (Start from 0%)
        self.chk_fresh = QCheckBox("🔄 Fresh Dubbing (0%)")
        self.chk_fresh.setToolTip(
            "Force re-transcribe, re-translate, and re-synthesize all speech from 0% instead of reusing existing cache"
        )
        self.chk_fresh.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")
        ps_layout.addWidget(self.chk_fresh)


        # Cancel Button
        self.cancel_btn = QPushButton("⏹️ Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setToolTip("Cancel active pipeline execution")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc2626;
                color: #ffffff;
                font-weight: 600;
                padding: 6px 12px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #b91c1c; }
            QPushButton:disabled { background-color: #374151; color: #9ca3af; }
        """)
        self.cancel_btn.clicked.connect(self._on_cancel_clicked)
        ps_layout.addWidget(self.cancel_btn)

        ps_layout.addStretch()

        # Open Output Folder Button
        self.open_output_btn = QPushButton("📂 Open Output")
        self.open_output_btn.setEnabled(True)
        self.open_output_btn.setToolTip("Open destination output folder in File Explorer")
        self.open_output_btn.clicked.connect(self._on_open_output_clicked)
        ps_layout.addWidget(self.open_output_btn)

        layout.addWidget(pipeline_strip)

        # 3. Master Progress Bar & Stage Status
        self.progress_container = QWidget()
        self.progress_container.setVisible(False)
        p_layout = QVBoxLayout(self.progress_container)
        p_layout.setContentsMargins(0, 0, 0, 0)
        p_layout.setSpacing(4)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(14)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border: none;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                font-weight: 700;
            }
            QProgressBar::chunk {
                background-color: #10b981;
                border-radius: 4px;
            }
        """)
        p_layout.addWidget(self.progress_bar)

        self.status_bar = QLabel("")
        self.status_bar.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
        p_layout.addWidget(self.status_bar)

        layout.addWidget(self.progress_container)

        # 4. Video Player Frame
        player_frame = QFrame()
        player_frame.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 1px solid #1e2536;
                border-radius: 8px;
            }
        """)
        pf_layout = QVBoxLayout(player_frame)
        pf_layout.setContentsMargins(0, 0, 0, 0)

        self.video_player = VideoPlayerWidget(parent=self)
        self.video_player.controller.metadata_ready.connect(self._on_metadata_loaded)
        pf_layout.addWidget(self.video_player)

        layout.addWidget(player_frame, 2)

        # 5. Bottom Tabs: Multi-Track Timeline & Speech/Translation Inspector
        self.bottom_tabs = QTabWidget(parent=self)
        self.bottom_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #1e293b;
                background-color: #0b0f17;
                border-radius: 8px;
            }
            QTabBar::tab {
                background-color: #131b2e;
                color: #94a3b8;
                font-weight: 600;
                font-size: 11px;
                padding: 6px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                border: 1px solid #1e293b;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #1e293b;
                color: #38bdf8;
                font-weight: 700;
            }
            QTabBar::tab:hover:!selected {
                background-color: #1a2234;
                color: #e2e8f0;
            }
        """)

        # Tab 1: Timeline
        self.timeline = MultiTrackTimelineWidget(
            player_controller=self.video_player.controller,
            parent=self,
        )
        self.bottom_tabs.addTab(self.timeline, "⏱️ Multi-Track Timeline")

        # Tab 2: Speech & Translation Inspector
        self.script_inspector = ScriptInspectorWidget(
            player_controller=self.video_player.controller,
            parent=self,
        )
        self.script_inspector.transcript_updated.connect(self._on_script_inspector_updated)
        self.script_inspector.segment_replaced.connect(self._on_segment_replaced_in_editor)
        self.script_inspector.replace_all_requested.connect(self._on_replace_all_in_editor)
        self.bottom_tabs.addTab(self.script_inspector, "📜 Speech & Translation Inspector")


        layout.addWidget(self.bottom_tabs, 1)

    def load_media(self, video_path: Path | str, srt_path: Path | str | None = None) -> None:
        """Load video media and optional subtitle file into the Studio player and timeline."""
        p = Path(video_path).resolve()
        if "_dubbed_" not in p.stem.lower():
            self._original_source_video_path = p
        self.video_player.load_media(p, srt_path)
        self.open_output_btn.setEnabled(True)

        # Check if companion stems exist for multi-track audition
        stems = self._discover_companion_stems(p)
        if stems:
            self.video_player.controller.load_stems(stems)
            # If opening an already dubbed video, default orig_audio to muted
            if "_dubbed_" in p.stem.lower():
                self.video_player.controller.set_track_mute("orig_audio", True)
                self.timeline.set_track_mute("orig_audio", True)

            # Check for companion transcript
            workdir = next(iter(stems.values())).parent
            translated_files = list(workdir.glob("translated_*.json"))
            if translated_files and translated_files[0].exists():
                try:
                    tr = Transcript.load_json(translated_files[0])
                    self.timeline.load_transcript_clips(tr.segments)
                    self.script_inspector.load_transcript(tr, translated_files[0])
                except Exception:
                    pass
            elif (workdir / "transcript.json").exists():
                try:
                    tr = Transcript.load_json(workdir / "transcript.json")
                    self.timeline.load_transcript_clips(tr.segments)
                    self.script_inspector.load_transcript(tr, workdir / "transcript.json")
                except Exception:
                    pass

    def _resolve_output_dir(self, video_path: Path, subfolder: str = "forge_output") -> Path:
        """Resolve a guaranteed writable output directory with multi-tier fallback."""
        # 1. If video is already inside the target subfolder, use it
        if video_path.parent.name == subfolder:
            return video_path.parent

        # 2. Check user configured directory in Settings
        try:
            from core.config_store import ConfigStore
            cfg_dir = ConfigStore.instance().get("output_dir")
            if cfg_dir:
                p = Path(cfg_dir)
                p.mkdir(parents=True, exist_ok=True)
                test_f = p / ".test_mf_write"
                test_f.touch()
                test_f.unlink()
                return p
        except Exception:
            pass

        # 3. Try next to the video file
        try:
            cand = video_path.parent / subfolder
            cand.mkdir(parents=True, exist_ok=True)
            test_f = cand / ".test_mf_write"
            test_f.touch()
            test_f.unlink()
            return cand
        except Exception:
            pass

        # 4. Fallback to Documents/MediaForge Projects/forge_output
        for fallback in [
            Path.home() / "Documents" / "MediaForge Projects" / subfolder,
            Path.home() / "AppData" / "Local" / "MediaForgeAI" / subfolder,
            Path.cwd() / subfolder,
        ]:
            try:
                fallback.mkdir(parents=True, exist_ok=True)
                test_f = fallback / ".test_mf_write"
                test_f.touch()
                test_f.unlink()
                return fallback
            except Exception:
                pass

        fallback = Path.home() / ".mediaforge" / subfolder
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

    def _discover_companion_stems(self, video_path: Path) -> dict[str, Path]:
        """Auto-discover companion stems from workdir if opening a media or dubbed file."""
        stems: dict[str, Path] = {}
        parent_dir = video_path.parent

        stem_base = video_path.stem
        if "_dubbed_" in stem_base:
            stem_base = stem_base.split("_dubbed_")[0]

        candidate_dirs = [
            parent_dir,
            parent_dir / "forge_output",
            Path.home() / "Documents" / "MediaForge Projects" / "forge_output",
            Path.home() / "AppData" / "Local" / "MediaForgeAI" / "forge_output",
        ]

        for cdir in candidate_dirs:
            if not cdir.exists():
                continue
            for wdir in cdir.glob(f"work_{stem_base}*"):
                if not wdir.is_dir():
                    continue
                audio_16k = wdir / "audio_16k.wav"
                bgm = wdir / "no_vocals.wav"
                dlg = wdir / "dubbed_dialogue.wav"

                if audio_16k.exists():
                    stems["orig_audio"] = audio_16k
                if bgm.exists():
                    stems["bgm"] = bgm
                if dlg.exists():
                    stems["dialogue"] = dlg

                if stems:
                    return stems
        return stems

    def _on_metadata_loaded(self, meta: MediaMetadata) -> None:
        audio_str = f" • {meta.audio_codec.upper()}" if meta.has_audio else ""
        text = f"{meta.width}x{meta.height} • {meta.fps:.2f} fps • {meta.video_codec.upper()}{audio_str} • {meta.duration:.1f}s"
        self.meta_badge.setText(text)
        self.meta_badge.setStyleSheet("""
            background-color: #1a2234;
            color: #38bdf8;
            font-size: 11px;
            font-weight: 700;
            padding: 4px 10px;
            border-radius: 6px;
            border: 1px solid #0284c7;
        """)
        # Update timeline duration and tracks
        self.timeline.load_media_clips(meta, self.video_player.controller.subtitles)

    def _on_open_media_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video Media",
            "",
            "Video Files (*.mp4 *.mkv *.mov *.webm *.avi);;All Files (*)",
        )
        if file_path:
            self.load_media(file_path)

    def _on_load_subtitles_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Subtitles",
            "",
            "Subtitle Files (*.srt *.vtt *.ass);;All Files (*)",
        )
        if file_path:
            self.video_player.controller.load_subtitles(file_path)
            if self.video_player.controller.metadata:
                self.timeline.load_media_clips(
                    self.video_player.controller.metadata,
                    self.video_player.controller.subtitles,
                )

    def _on_cancel_clicked(self) -> None:
        if self._current_token:
            self._current_token.cancel()
            self.status_bar.setText("Cancelling pipeline...")
            self.cancel_btn.setEnabled(False)

    def _on_open_output_clicked(self) -> None:
        target_file: Path | None = None
        target_folder: Path | None = None

        # 1. Check if we have an in-memory result from a pipeline run in this session
        if self._last_result and self._last_result.output_video_path:
            p = self._last_result.output_video_path
            if p.exists():
                target_file = p
                target_folder = p.parent
            elif p.parent.exists():
                target_folder = p.parent

        # 2. Check if a video is currently loaded in the Studio player
        if not target_folder or not target_folder.exists():
            ctrl = self.video_player.controller
            current_vid = ctrl.current_video_path
            if current_vid:
                vid_path = Path(current_vid).resolve()
                stem_base = vid_path.stem.split("_dubbed_")[0]

                # If current video itself is an exported dubbed video, use it directly
                if "_dubbed_" in vid_path.stem.lower() and vid_path.exists():
                    target_file = vid_path
                    target_folder = vid_path.parent
                else:
                    candidate_dirs = [
                        self._resolve_output_dir(vid_path, "forge_output"),
                        Path.home() / "Documents" / "MediaForge Projects" / "forge_output",
                        vid_path.parent / "forge_output",
                        Path.home() / "AppData" / "Local" / "MediaForgeAI" / "forge_output",
                        vid_path.parent,
                    ]

                    # Check for an existing rendered dubbed video matching this source
                    for cdir in candidate_dirs:
                        if not cdir.exists():
                            continue
                        dubbed_matches = list(cdir.glob(f"{stem_base}_dubbed_*.mp4"))
                        if dubbed_matches and dubbed_matches[0].exists():
                            target_file = dubbed_matches[0]
                            target_folder = cdir
                            break

                        # Check for companion workdir
                        work_dirs = list(cdir.glob(f"work_{stem_base}*"))
                        if work_dirs and work_dirs[0].exists():
                            target_folder = cdir
                            break

                    if not target_folder or not target_folder.exists():
                        target_folder = self._resolve_output_dir(vid_path, "forge_output")

        # 3. Global fallback: User Documents or Config output_dir
        if not target_folder or not target_folder.exists():
            try:
                from core.config_store import ConfigStore
                cfg_out = ConfigStore.instance().get("output_dir")
                if cfg_out and Path(cfg_out).exists():
                    target_folder = Path(cfg_out)
            except Exception:
                pass

        if not target_folder or not target_folder.exists():
            target_folder = Path.home() / "Documents" / "MediaForge Projects" / "forge_output"
            target_folder.mkdir(parents=True, exist_ok=True)

        # 4. Open in Explorer / File Manager with multiple reliable strategies
        opened = False

        # Strategy A: Windows Explorer with file selected or folder opened
        try:
            if target_file and target_file.exists():
                subprocess.Popen(["explorer.exe", f"/select,{str(target_file.resolve())}"])
                opened = True
            elif target_folder and target_folder.exists():
                subprocess.Popen(["explorer.exe", str(target_folder.resolve())])
                opened = True
        except Exception as ex_proc:
            logger.warning("subprocess explorer launch failed: %s", ex_proc)

        # Strategy B: os.startfile
        if not opened and target_folder and target_folder.exists():
            try:
                os.startfile(str(target_folder.resolve()))
                opened = True
            except Exception as ex_os:
                logger.warning("os.startfile failed: %s", ex_os)

        # Strategy C: Qt QDesktopServices
        if not opened and target_folder and target_folder.exists():
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(target_folder.resolve())))
                opened = True
            except Exception as ex_qt:
                logger.warning("QDesktopServices failed: %s", ex_qt)

        if not opened:
            QMessageBox.warning(
                self,
                "Output Directory",
                f"Output destination directory:\n{target_folder}\n\nPlease open this folder in your file browser.",
            )

    def _on_autoprocess_clicked(self) -> None:
        try:
            ctrl = self.video_player.controller
            if not ctrl.current_video_path:
                QMessageBox.warning(self, "No Media", "Please open a video file first.")
                return

            video_path = ctrl.current_video_path

            # If user is re-running on an already-dubbed video, find and use the original clean source
            actual_video_path = video_path
            if "_dubbed_" in video_path.stem.lower():
                if self._original_source_video_path and self._original_source_video_path.exists():
                    actual_video_path = self._original_source_video_path
                else:
                    stem_base = video_path.stem.split("_dubbed_")[0]
                    for candidate in [
                        video_path.parent / f"{stem_base}{video_path.suffix}",
                        video_path.parent.parent / f"{stem_base}{video_path.suffix}",
                    ]:
                        if candidate.exists():
                            actual_video_path = candidate
                            break

            target_lang = self.lang_combo.currentData()
            translation_prov = self.prov_combo.currentData()
            num_spk = self.spk_mode_combo.currentData()

            # Auto-check companion .meta.json for movie characters
            movie_characters = None
            meta_path = actual_video_path.with_suffix(".meta.json")
            if meta_path.exists():
                try:
                    with open(meta_path, encoding="utf-8") as mf:
                        movie_characters = json.load(mf).get("characters")
                except Exception:
                    pass

            out_dir = self._resolve_output_dir(actual_video_path, "forge_output")

            token = CancellationToken()
            self._current_token = token

            self._set_processing_ui_state(active=True)
            self.progress_container.setVisible(True)
            self.progress_bar.setValue(2)
            self.status_bar.setText("Starting Unified Auto-Process Pipeline...")

            config = PipelineConfig(
                video_path=actual_video_path,
                output_dir=out_dir,
                target_lang=target_lang,
                translation_provider=translation_prov,
                characters=movie_characters,
                num_speakers=num_spk,
                force_recompute=self.chk_fresh.isChecked(),
            )


            signals = StudioTaskSignals(self)
            self._active_task_signals = signals  # Protect from PySide6 GC
            signals.progress.connect(self._update_progress)
            signals.completed.connect(self._on_autoprocess_done)
            signals.error.connect(lambda err: self._on_task_error("Auto-Process error", err))

            def worker() -> None:
                try:
                    engine = PipelineEngine()
                    def progress_cb(prog: float, msg: str) -> None:
                        signals.progress.emit(int(prog * 100), msg)

                    result = engine.run(config, token=token, progress=progress_cb)
                    signals.completed.emit(result)
                except Exception as e:
                    logger.exception("Pipeline worker execution failed: %s", e)
                    signals.error.emit(str(e))

            threading.Thread(target=worker, daemon=True, name="AutoProcessWorker").start()

        except Exception as e:
            logger.exception("Failed to start Auto-Process pipeline: %s", e)
            self._set_processing_ui_state(active=False)
            self.status_bar.setText(f"❌ Failed to start pipeline: {e}")
            QMessageBox.critical(self, "Pipeline Error", f"Failed to start pipeline:\n\n{e}")

    def _on_autoprocess_done(self, result: PipelineResult) -> None:
        try:
            self._last_result = result
            self._set_processing_ui_state(active=False)
            self.open_output_btn.setEnabled(True)
            self.status_bar.setText(f"✅ Auto-Process Complete: {result.output_video_path.name}")
            ctrl = self.video_player.controller

            # 1. Load the generated dubbed video and its srt subtitles
            ctrl.load_media(result.output_video_path, result.srt_path)

            # 2. Gather audio stems for multi-track audition
            stems: dict[str, Path] = {}
            workdir = result.srt_path.parent
            audio_16k = workdir / "audio_16k.wav"
            if audio_16k.exists():
                stems["orig_audio"] = audio_16k
            elif result.vocals_path and result.vocals_path.exists():
                stems["orig_audio"] = result.vocals_path
            elif result.video_path.exists():
                stems["orig_audio"] = result.video_path

            if result.no_vocals_path and result.no_vocals_path.exists():
                stems["bgm"] = result.no_vocals_path

            dlg_wav = workdir / "dubbed_dialogue.wav"
            if dlg_wav.exists():
                stems["dialogue"] = dlg_wav
            elif result.dubbed_dialogue_path and result.dubbed_dialogue_path.exists():
                stems["dialogue"] = result.dubbed_dialogue_path

            ctrl.load_stems(stems)

            # 3. In the studio player, default orig_audio to MUTED so dubbed dialogue + BGM play
            ctrl.set_track_mute("orig_audio", True)
            self.timeline.set_track_mute("orig_audio", True)

            # 4. Populate timeline tracks and script inspector
            self.timeline.load_transcript_clips(result.translated_transcript.segments)
            trans_file = workdir / f"translated_{result.translated_transcript.language}.json"
            self.script_inspector.load_transcript(result.translated_transcript, trans_file if trans_file.exists() else None)

            dur_ms = int(result.duration_sec * 1000)
            if "bgm" in stems:
                self.timeline.canvas.set_track_clips(
                    "bgm",
                    [
                        TimelineClip(
                            id="bgm_stem",
                            start_ms=0,
                            end_ms=dur_ms,
                            label="BGM / SFX Stem (Demucs)",
                            color=QColor(139, 92, 246, 220),
                        )
                    ],
                )

            QMessageBox.information(
                self,
                "Auto-Process Complete",
                f"Video dubbed and subtitled successfully!\n\nSaved to: {result.output_video_path.name}",
            )
        except Exception as e:
            logger.exception("Error loading Auto-Process preview in Studio: %s", e)
            self._set_processing_ui_state(active=False)
            self.status_bar.setText(f"❌ Error displaying auto-process preview: {e}")
            QMessageBox.critical(self, "Preview Error", f"Auto-Process completed, but failed to load preview:\n\n{e}")

    def _on_open_inspector_clicked(self) -> None:
        """Switch Studio bottom tab to Speech & Translation Inspector."""
        self.bottom_tabs.setCurrentWidget(self.script_inspector)

    def _on_script_inspector_updated(self, updated_tr: Transcript) -> None:
        """Called when user edits text or speakers in the script inspector, keeping timeline in sync."""
        if updated_tr and updated_tr.segments:
            self.timeline.load_transcript_clips(updated_tr.segments)

    def _on_segment_replaced_in_editor(self, seg: Any) -> None:
        """Update single sentence translation and timestamp in Video Editor timeline and subtitle overlay."""
        start_ms = int(seg.start * 1000)
        end_ms = int(seg.end * 1000)
        text = seg.target_text or seg.source_text

        # 1. Update timeline tracks (dialogue + subtitle clips)
        self.timeline.update_segment_clip(seg.id, text, start_ms, end_ms, getattr(seg, "speaker", ""))

        # 2. Update player controller active subtitles
        from modules.media.player_controller import SubtitleSegment

        ctrl = self.video_player.controller
        updated = False
        for sub in ctrl.subtitles:
            if sub.index == seg.id:
                sub.text = text
                sub.start_ms = start_ms
                sub.end_ms = end_ms
                updated = True
                break
        if not updated:
            ctrl.subtitles.append(
                SubtitleSegment(index=seg.id, start_ms=start_ms, end_ms=end_ms, text=text)
            )
            ctrl.subtitles.sort(key=lambda s: s.start_ms)

        # 3. Seek to segment start and trigger subtitle update
        ctrl.seek(start_ms)
        self.status_bar.setText(f"📥 Replaced line #{seg.id} in Video Editor: {text[:45]}...")

    def _on_replace_all_in_editor(self, transcript: Any) -> None:
        """Replace all translations and timestamps in Video Editor timeline and subtitle overlay."""
        if not transcript or not getattr(transcript, "segments", None):
            return

        # 1. Update all timeline clips
        self.timeline.load_transcript_clips(transcript.segments)

        # 2. Rebuild player controller subtitles
        from modules.media.player_controller import SubtitleSegment

        new_subs: list[SubtitleSegment] = []
        for s in transcript.segments:
            s_text = s.target_text or s.source_text
            new_subs.append(
                SubtitleSegment(
                    index=s.id,
                    start_ms=int(s.start * 1000),
                    end_ms=int(s.end * 1000),
                    text=s_text,
                )
            )
        ctrl = self.video_player.controller
        ctrl.subtitles = new_subs
        if ctrl.subtitles:
            ctrl._update_subtitle(ctrl.media_player.position())

        self.status_bar.setText(f"📥 Replaced all {len(transcript.segments)} sentences in Video Editor!")


    def _on_task_error(self, prefix: str, err_msg: str) -> None:
        self._set_processing_ui_state(active=False)
        if "cancel" in err_msg.lower():
            self.status_bar.setText("⏹️ Auto-Process pipeline cancelled by user.")
        else:
            self.status_bar.setText(f"❌ {prefix}: {err_msg}")
            QMessageBox.critical(self, "Process Error", f"{prefix}:\n\n{err_msg}")

    def _update_progress(self, pct: int, msg: str) -> None:
        self.progress_bar.setValue(pct)
        self.status_bar.setText(f"[{pct}%] {msg}")

    def _set_processing_ui_state(self, active: bool) -> None:
        self.autoprocess_btn.setEnabled(not active)
        self.transcribe_btn.setEnabled(not active)
        self.separate_btn.setEnabled(not active)
        self.cancel_btn.setEnabled(active)

    def _on_transcribe_clicked(self) -> None:
        try:
            ctrl = self.video_player.controller
            if not ctrl.current_video_path:
                QMessageBox.warning(self, "No Media", "Please open a video file first.")
                return

            video_path = ctrl.current_video_path
            dlg = PowerVoiceSeparatorDialog(video_path=video_path, parent=self)
            if dlg.exec() != QDialog.Accepted:
                return

            num_speakers, characters = dlg.get_selection()

            self._set_processing_ui_state(active=True)
            self.progress_container.setVisible(True)
            self.status_bar.setText("Starting Power Voice Separation (faster-whisper + pitch clustering)...")

            token = CancellationToken()
            self._current_token = token
            out_dir = self._resolve_output_dir(video_path, "ai_output")
            srt_path = out_dir / f"{video_path.stem}.srt"

            signals = StudioTaskSignals(self)
            self._active_task_signals = signals
            signals.progress.connect(self._update_progress)
            signals.completed.connect(lambda diarized: self._on_transcribe_done(diarized, srt_path))
            signals.error.connect(lambda err: self._on_task_error("Transcription failed", err))

            def worker() -> None:
                def progress_cb(prog: float, msg: str) -> None:
                    signals.progress.emit(int(prog * 100), msg)

                try:
                    # 1. Transcribe
                    transcriber = TranscriberEngine()
                    transcript = transcriber.run(
                        TranscriberInput(audio_path=video_path, model_size="small"),
                        workdir=out_dir,
                        token=token,
                        progress=progress_cb,
                    )

                    # 2. Power Diarize
                    diarizer = DiarizerEngine()
                    diarized = diarizer.run(
                        DiarizerInput(
                            audio_path=video_path,
                            transcript=transcript,
                            num_speakers=num_speakers,
                            characters=characters,
                        ),
                        workdir=out_dir,
                        token=token,
                        progress=progress_cb,
                    )

                    # 3. Export companion .srt
                    self._export_transcript_to_srt(diarized, srt_path)
                    signals.completed.emit(diarized)
                except Exception as e:
                    logger.exception("Transcribe worker error: %s", e)
                    signals.error.emit(str(e))

            threading.Thread(target=worker, daemon=True, name="AITranscribeWorker").start()
        except Exception as e:
            logger.exception("Failed to start transcription: %s", e)
            self._set_processing_ui_state(active=False)
            QMessageBox.critical(self, "Transcription Error", str(e))

    def _on_transcribe_done(self, diarized: object, srt_path: Path) -> None:
        self._set_processing_ui_state(active=False)
        segments = getattr(diarized, "segments", [])
        speakers = sorted(list(set(getattr(s, "speaker", "") for s in segments if getattr(s, "speaker", ""))))
        spk_str = f" across {len(speakers)} distinct voices" if speakers else ""
        self.status_bar.setText(f"✅ Power Voice Separation Complete: {len(segments)} segments{spk_str}.")
        ctrl = self.video_player.controller
        ctrl.load_subtitles(srt_path)
        self.timeline.load_transcript_clips(segments)
        self.script_inspector.load_transcript(diarized)

    def _on_separate_clicked(self) -> None:
        try:
            ctrl = self.video_player.controller
            if not ctrl.current_video_path:
                QMessageBox.warning(self, "No Media", "Please open a video file first.")
                return

            self._set_processing_ui_state(active=True)
            self.progress_container.setVisible(True)
            self.status_bar.setText("Starting stem separation (vocals & background)...")

            video_path = ctrl.current_video_path
            token = CancellationToken()
            self._current_token = token
            out_dir = self._resolve_output_dir(video_path, "ai_stems")

            signals = StudioTaskSignals(self)
            self._active_task_signals = signals
            signals.progress.connect(self._update_progress)
            signals.completed.connect(self._on_separate_done)
            signals.error.connect(lambda err: self._on_task_error("Separation failed", err))

            def worker() -> None:
                def progress_cb(prog: float, msg: str) -> None:
                    signals.progress.emit(int(prog * 100), msg)

                try:
                    separator = SeparatorEngine()
                    result = separator.run(
                        SeparatorInput(audio_path=video_path, mode="auto"),
                        workdir=out_dir,
                        token=token,
                        progress=progress_cb,
                    )
                    signals.completed.emit(result)
                except Exception as e:
                    logger.exception("Separate worker error: %s", e)
                    signals.error.emit(str(e))

            threading.Thread(target=worker, daemon=True, name="AISeparateWorker").start()
        except Exception as e:
            logger.exception("Failed to start stem separation: %s", e)
            self._set_processing_ui_state(active=False)
            QMessageBox.critical(self, "Separation Error", str(e))

    def _on_separate_done(self, result: object) -> None:
        self._set_processing_ui_state(active=False)
        voc_path = getattr(result, "vocals_path", None)
        bgm_path = getattr(result, "no_vocals_path", None)
        voc_name = getattr(voc_path, "name", "vocals.wav") if voc_path else "vocals.wav"
        bgm_name = getattr(bgm_path, "name", "no_vocals.wav") if bgm_path else "no_vocals.wav"
        self.status_bar.setText(f"✅ Stem Separation Complete: {voc_name}, {bgm_name}")

        try:
            ctrl = self.video_player.controller
            stems: dict[str, Path] = {}
            if voc_path and Path(voc_path).exists():
                stems["orig_audio"] = Path(voc_path)
            if bgm_path and Path(bgm_path).exists():
                stems["bgm"] = Path(bgm_path)

            if stems:
                ctrl.load_stems(stems)
                meta = ctrl.metadata
                dur_ms = int(meta.duration * 1000) if meta and meta.duration > 0 else 60000
                if "bgm" in stems:
                    self.timeline.canvas.set_track_clips(
                        "bgm",
                        [
                            TimelineClip(
                                id="bgm_stem",
                                start_ms=0,
                                end_ms=dur_ms,
                                label=f"BGM / SFX Stem ({bgm_name})",
                                color=QColor(139, 92, 246, 220),
                            )
                        ],
                    )
                if "orig_audio" in stems:
                    self.timeline.canvas.set_track_clips(
                        "orig_audio",
                        [
                            TimelineClip(
                                id="vocals_stem",
                                start_ms=0,
                                end_ms=dur_ms,
                                label=f"Vocals Stem ({voc_name})",
                                color=QColor(16, 185, 129, 220),
                            )
                        ],
                    )
        except Exception as e:
            logger.warning("Could not automatically populate stems after separation: %s", e)

    @staticmethod
    def _export_transcript_to_srt(transcript: Transcript, srt_path: Path) -> None:
        def fmt_time(seconds: float) -> str:
            ms = int((seconds % 1.0) * 1000)
            total_sec = int(seconds)
            s = total_sec % 60
            total_min = total_sec // 60
            m = total_min % 60
            h = total_min // 60
            return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

        with open(srt_path, "w", encoding="utf-8") as f:
            for seg in transcript.segments:
                f.write(f"{seg.id}\n")
                f.write(f"{fmt_time(seg.start)} --> {fmt_time(seg.end)}\n")
                speaker_tag = f"[{seg.speaker}] " if seg.speaker else ""
                f.write(f"{speaker_tag}{seg.source_text}\n\n")

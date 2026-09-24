"""Multi-track visual composite timeline widget (Phase 9).

Provides a read-only visual representation of 5 timeline tracks:
1. Video
2. Original Audio
3. BGM / SFX
4. Dubbed Dialogue
5. Subtitles

Includes per-track Mute/Solo controls, frame-accurate playhead tracking,
time ruler, and click-to-seek synchronization with the media player.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from modules.media.player_controller import PlayerController


@dataclass
class TimelineClip:
    """Represents a clip or segment block on a timeline track."""

    id: int | str
    start_ms: int
    end_ms: int
    label: str
    color: QColor = field(default_factory=lambda: QColor(59, 130, 246, 200))
    speaker: str = ""


@dataclass
class TrackInfo:
    """Track metadata including mute and solo status."""

    id: str
    name: str
    icon: str
    default_color: QColor
    muted: bool = False
    solo: bool = False
    clips: list[TimelineClip] = field(default_factory=list)


class TimelineCanvas(QWidget):
    """Custom-painted canvas rendering the ruler, track lanes, clips, and playhead."""

    seek_requested = Signal(int)  # Emits target position in milliseconds
    clip_clicked = Signal(str, object)  # Emits (track_id, TimelineClip)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.duration_ms: int = 60000  # Default 60 seconds
        self.position_ms: int = 0
        self.pixels_per_second: float = 60.0  # Zoom level
        self.ruler_height: int = 26
        self.track_height: int = 34
        self.track_gap: int = 6

        self.tracks: list[TrackInfo] = [
            TrackInfo("video", "Video", "🎬", QColor(37, 99, 235)),
            TrackInfo("orig_audio", "Original Audio", "🔊", QColor(16, 185, 129)),
            TrackInfo("bgm", "BGM / SFX", "🎵", QColor(139, 92, 246)),
            TrackInfo("dialogue", "Dubbed Dialogue", "🎙️", QColor(245, 158, 11)),
            TrackInfo("subtitles", "Subtitles", "💬", QColor(236, 72, 153)),
        ]

        self._dragging_playhead: bool = False
        self._update_geometry()

    def _update_geometry(self) -> None:
        total_tracks_height = len(self.tracks) * (self.track_height + self.track_gap)
        total_h = self.ruler_height + total_tracks_height + 20
        total_w = max(800, int((self.duration_ms / 1000.0) * self.pixels_per_second) + 100)
        self.setFixedHeight(total_h)
        self.setMinimumWidth(total_w)
        self.updateGeometry()

    def set_duration(self, duration_ms: int) -> None:
        self.duration_ms = max(1000, duration_ms)
        self._update_geometry()
        self.update()

    def set_position(self, position_ms: int) -> None:
        if self.position_ms != position_ms:
            self.position_ms = max(0, min(position_ms, self.duration_ms))
            self.update()

    def set_track_clips(self, track_id: str, clips: list[TimelineClip]) -> None:
        for trk in self.tracks:
            if trk.id == track_id:
                trk.clips = clips
                break
        self.update()

    def update_segment_clip(
        self,
        seg_id: int | str,
        label: str,
        start_ms: int,
        end_ms: int,
        speaker: str | None = None,
    ) -> None:
        """Update or insert an individual segment clip in dialogue and subtitle tracks."""
        for trk in self.tracks:
            if trk.id in ("dialogue", "subtitles"):
                prefix = "dlg_" if trk.id == "dialogue" else "sub_"
                target_id = f"{prefix}{seg_id}"
                clip = next((c for c in trk.clips if str(c.id) == target_id), None)
                if clip:
                    clip.label = label
                    clip.start_ms = start_ms
                    clip.end_ms = end_ms
                    if speaker:
                        clip.speaker = speaker
                else:
                    color = QColor(245, 158, 11, 210) if trk.id == "dialogue" else QColor(236, 72, 153, 200)
                    trk.clips.append(
                        TimelineClip(
                            id=target_id,
                            start_ms=start_ms,
                            end_ms=end_ms,
                            label=label,
                            color=color,
                            speaker=speaker or "",
                        )
                    )
                trk.clips.sort(key=lambda c: c.start_ms)

        if end_ms > self.duration_ms:
            self.set_duration(end_ms + 2000)
        else:
            self.update()


    def set_track_mute(self, track_id: str, muted: bool) -> None:
        for trk in self.tracks:
            if trk.id == track_id:
                trk.muted = muted
                break
        self.update()

    def set_track_solo(self, track_id: str, solo: bool) -> None:
        for trk in self.tracks:
            if trk.id == track_id:
                trk.solo = solo
                break
        self.update()

    def _ms_to_x(self, ms: int) -> float:
        return (ms / 1000.0) * self.pixels_per_second

    def _x_to_ms(self, x: float) -> int:
        seconds = max(0.0, x / self.pixels_per_second)
        return int(seconds * 1000)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # 1. Background
        painter.fillRect(0, 0, w, h, QBrush(QColor(13, 17, 23)))

        # 2. Time Ruler
        painter.fillRect(0, 0, w, self.ruler_height, QBrush(QColor(22, 27, 34)))
        painter.setPen(QPen(QColor(48, 54, 61), 1))
        painter.drawLine(0, self.ruler_height, w, self.ruler_height)

        ruler_font = QFont("Consolas", 8)
        painter.setFont(ruler_font)
        painter.setPen(QPen(QColor(139, 148, 158), 1))

        # Ruler ticks every second, text every 5 seconds
        step_sec = 1
        total_sec = int(self.duration_ms / 1000.0) + 1
        for sec in range(0, total_sec + 1, step_sec):
            x = int(self._ms_to_x(sec * 1000))
            if sec % 5 == 0:
                painter.drawLine(x, self.ruler_height - 10, x, self.ruler_height)
                minutes = sec // 60
                rem_sec = sec % 60
                time_str = f"{minutes:02d}:{rem_sec:02d}"
                painter.drawText(x + 3, self.ruler_height - 4, time_str)
            else:
                painter.drawLine(x, self.ruler_height - 5, x, self.ruler_height)

        # 3. Tracks & Clips
        audio_ids = {"orig_audio", "bgm", "dialogue"}
        any_audio_solo = any(t.solo for t in self.tracks if t.id in audio_ids)
        y = self.ruler_height + 6

        clip_font = QFont("Segoe UI", 8)
        painter.setFont(clip_font)

        for trk in self.tracks:
            track_rect = QRectF(0, y, w, self.track_height)

            # Check if active based on domain isolation
            if trk.id in audio_ids:
                if any_audio_solo:
                    is_active = trk.solo and not trk.muted
                else:
                    is_active = not trk.muted
            elif trk.id == "video":
                is_active = not trk.muted
            elif trk.id == "subtitles":
                is_active = not trk.muted
            else:
                is_active = not trk.muted

            # Track lane background
            lane_color = QColor(24, 30, 42) if is_active else QColor(18, 22, 28)
            painter.fillRect(track_rect, QBrush(lane_color))
            painter.setPen(QPen(QColor(36, 44, 58), 1))
            painter.drawRect(track_rect)

            # Draw Clips
            for clip in trk.clips:
                clip_x = self._ms_to_x(clip.start_ms)
                clip_w = max(4.0, self._ms_to_x(clip.end_ms) - clip_x)
                clip_rect = QRectF(clip_x, y + 2, clip_w, self.track_height - 4)

                c_color = QColor(clip.color)
                if not is_active:
                    c_color.setAlpha(60)

                painter.fillRect(clip_rect, QBrush(c_color))
                painter.setPen(QPen(c_color.lighter(130), 1))
                painter.drawRoundedRect(clip_rect, 3, 3)

                # Clip Text Label
                if clip_w > 20:
                    painter.setPen(QPen(QColor(255, 255, 255, 230 if is_active else 100), 1))
                    text_to_draw = clip.label
                    if clip.speaker:
                        text_to_draw = f"[{clip.speaker}] {text_to_draw}"
                    painter.drawText(
                        clip_rect.adjusted(4, 2, -4, -2),
                        Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                        text_to_draw,
                    )

            y += self.track_height + self.track_gap

        # 4. Playhead Vertical Cursor
        playhead_x = self._ms_to_x(self.position_ms)
        pen_playhead = QPen(QColor(239, 68, 68), 2)
        painter.setPen(pen_playhead)
        painter.drawLine(int(playhead_x), 0, int(playhead_x), h)

        # Playhead top marker triangle/pill
        painter.setBrush(QBrush(QColor(239, 68, 68)))
        painter.setPen(Qt.PenStyle.NoPen)
        marker_w = 8
        painter.drawRect(int(playhead_x - marker_w / 2), 0, marker_w, self.ruler_height)

        painter.end()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            x = event.position().x()
            y = event.position().y()
            target_ms = self._x_to_ms(x)

            # Check if clicked inside a clip
            clicked_clip: TimelineClip | None = None
            clicked_track_id: str = ""

            track_y = self.ruler_height + 6
            for trk in self.tracks:
                if track_y <= y <= track_y + self.track_height:
                    for clip in trk.clips:
                        clip_x = self._ms_to_x(clip.start_ms)
                        clip_w = max(4.0, self._ms_to_x(clip.end_ms) - clip_x)
                        if clip_x <= x <= clip_x + clip_w:
                            clicked_clip = clip
                            clicked_track_id = trk.id
                            break
                    break
                track_y += self.track_height + self.track_gap

            if clicked_clip:
                self.clip_clicked.emit(clicked_track_id, clicked_clip)
                self.seek_requested.emit(clicked_clip.start_ms)
            else:
                self._dragging_playhead = True
                self.seek_requested.emit(target_ms)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging_playhead:
            target_ms = self._x_to_ms(event.position().x())
            self.seek_requested.emit(target_ms)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging_playhead = False


class MultiTrackTimelineWidget(QFrame):
    """Integrated multi-track timeline component with track headers and canvas."""

    track_mute_changed = Signal(str, bool)  # track_id, is_muted
    track_solo_changed = Signal(str, bool)  # track_id, is_soloed

    def __init__(
        self,
        player_controller: PlayerController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = player_controller
        self._mute_buttons: dict[str, QPushButton] = {}
        self._solo_buttons: dict[str, QPushButton] = {}
        self._build_ui()
        if self.controller:
            self._connect_controller()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QFrame {
                background-color: #0b0f17;
                border: 1px solid #1e2536;
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # Header Bar
        header_bar = QHBoxLayout()
        header_bar.setSpacing(8)
        title = QLabel("Multi-Track Timeline")
        title.setStyleSheet("font-weight: 700; color: #e2e8f0; font-size: 12px;")
        header_bar.addWidget(title)

        header_bar.addStretch()

        zoom_btn_style = """
            QPushButton {
                background-color: #1e2433;
                color: #e2e8f0;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 12px;
                font-weight: 700;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2e384d;
                border-color: #6366f1;
                color: #ffffff;
            }
        """

        zoom_out_btn = QPushButton("➖")
        zoom_out_btn.setToolTip("Zoom Out Timeline (-)")
        zoom_out_btn.setFixedSize(28, 24)
        zoom_out_btn.setStyleSheet(zoom_btn_style)
        zoom_out_btn.clicked.connect(self._zoom_out)
        header_bar.addWidget(zoom_out_btn)

        self.zoom_lbl = QLabel("Zoom: 100%")
        self.zoom_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: 600;")
        header_bar.addWidget(self.zoom_lbl)

        zoom_in_btn = QPushButton("➕")
        zoom_in_btn.setToolTip("Zoom In Timeline (+)")
        zoom_in_btn.setFixedSize(28, 24)
        zoom_in_btn.setStyleSheet(zoom_btn_style)
        zoom_in_btn.clicked.connect(self._zoom_in)
        header_bar.addWidget(zoom_in_btn)

        zoom_fit_btn = QPushButton("Fit 100%")
        zoom_fit_btn.setFixedHeight(24)
        zoom_fit_btn.setToolTip("Reset Zoom to 100%")
        zoom_fit_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e2433;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                font-size: 11px;
                font-weight: 600;
                padding: 0 8px;
            }
            QPushButton:hover {
                background-color: #2e384d;
                border-color: #6366f1;
                color: #ffffff;
            }
        """)
        zoom_fit_btn.clicked.connect(self._zoom_reset)
        header_bar.addWidget(zoom_fit_btn)

        layout.addLayout(header_bar)

        # Body: Left Track Headers + Right Scrollable Canvas
        body = QHBoxLayout()
        body.setSpacing(0)
        body.setContentsMargins(0, 0, 0, 0)

        # Track Headers Column
        self.headers_col = QVBoxLayout()
        self.headers_col.setSpacing(6)
        self.headers_col.setContentsMargins(0, 32, 8, 20)  # align with canvas ruler

        self.canvas = TimelineCanvas(self)

        for trk in self.canvas.tracks:
            header_widget = self._create_track_header(trk)
            self.headers_col.addWidget(header_widget)

        self.headers_col.addStretch()
        body.addLayout(self.headers_col)

        # Scroll Area for Canvas
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setWidget(self.canvas)
        body.addWidget(scroll_area, 1)

        layout.addLayout(body)

        # Connect internal canvas signals
        self.canvas.seek_requested.connect(self._on_seek_requested)

    def _create_track_header(self, track: TrackInfo) -> QWidget:
        panel = QFrame()
        panel.setFixedHeight(34)
        panel.setFixedWidth(190)
        panel.setStyleSheet("""
            QFrame {
                background-color: #161d2b;
                border: 1px solid #283347;
                border-radius: 4px;
            }
        """)
        h_layout = QHBoxLayout(panel)
        h_layout.setContentsMargins(8, 2, 8, 2)
        h_layout.setSpacing(6)

        lbl = QLabel(f"{track.icon} {track.name}")
        lbl.setStyleSheet("color: #cbd5e1; font-size: 11px; font-weight: 600;")
        h_layout.addWidget(lbl, 1)

        # Mute button
        m_btn = QPushButton("M")
        m_btn.setCheckable(True)
        m_btn.setFixedSize(24, 22)
        m_btn.setToolTip(f"Mute Track '{track.name}' (M)")
        m_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #334155;
                border-radius: 3px;
                padding: 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
                border-color: #64748b;
            }
            QPushButton:checked {
                background-color: #ef4444;
                color: #ffffff;
                border-color: #dc2626;
            }
        """)
        m_btn.toggled.connect(lambda checked, tid=track.id: self._on_mute_clicked(tid, checked))
        self._mute_buttons[track.id] = m_btn
        h_layout.addWidget(m_btn)

        # Solo button
        s_btn = QPushButton("S")
        s_btn.setCheckable(True)
        s_btn.setFixedSize(24, 22)
        s_btn.setToolTip(f"Solo Track '{track.name}' (S)")
        s_btn.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                font-weight: 800;
                font-size: 11px;
                border: 1px solid #334155;
                border-radius: 3px;
                padding: 0px;
                text-align: center;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
                border-color: #64748b;
            }
            QPushButton:checked {
                background-color: #eab308;
                color: #0f172a;
                border-color: #ca8a04;
            }
        """)
        s_btn.toggled.connect(lambda checked, tid=track.id: self._on_solo_clicked(tid, checked))
        if track.id not in ("orig_audio", "bgm", "dialogue"):
            s_btn.setVisible(False)
        self._solo_buttons[track.id] = s_btn
        h_layout.addWidget(s_btn)

        return panel

    def _on_mute_clicked(self, track_id: str, checked: bool) -> None:
        self.canvas.set_track_mute(track_id, checked)
        self.track_mute_changed.emit(track_id, checked)
        if self.controller:
            self.controller.set_track_mute(track_id, checked)

    def _on_solo_clicked(self, track_id: str, checked: bool) -> None:
        self.canvas.set_track_solo(track_id, checked)
        self.track_solo_changed.emit(track_id, checked)
        if self.controller:
            self.controller.set_track_solo(track_id, checked)

    def set_track_mute(self, track_id: str, muted: bool) -> None:
        """Programmatically set track mute state without recursive signals."""
        if track_id in self._mute_buttons:
            btn = self._mute_buttons[track_id]
            btn.blockSignals(True)
            btn.setChecked(muted)
            btn.blockSignals(False)
        self.canvas.set_track_mute(track_id, muted)

    def set_track_solo(self, track_id: str, solo: bool) -> None:
        """Programmatically set track solo state without recursive signals."""
        if track_id in self._solo_buttons:
            btn = self._solo_buttons[track_id]
            btn.blockSignals(True)
            btn.setChecked(solo)
            btn.blockSignals(False)
        self.canvas.set_track_solo(track_id, solo)

    def _connect_controller(self) -> None:
        if not self.controller:
            return
        self.controller.duration_changed.connect(self.canvas.set_duration)
        self.controller.position_changed.connect(self.canvas.set_position)
        self.controller.track_mute_changed.connect(self.set_track_mute)
        self.controller.track_solo_changed.connect(self.set_track_solo)

    def _on_seek_requested(self, ms: int) -> None:
        if self.controller:
            self.controller.seek(ms)
        self.canvas.set_position(ms)

    def _zoom_in(self) -> None:
        self.canvas.pixels_per_second = min(200.0, self.canvas.pixels_per_second * 1.25)
        self.zoom_lbl.setText(f"Zoom: {int((self.canvas.pixels_per_second / 60.0) * 100)}%")
        self.canvas._update_geometry()
        self.canvas.adjustSize()
        self.canvas.update()

    def _zoom_out(self) -> None:
        self.canvas.pixels_per_second = max(15.0, self.canvas.pixels_per_second / 1.25)
        self.zoom_lbl.setText(f"Zoom: {int((self.canvas.pixels_per_second / 60.0) * 100)}%")
        self.canvas._update_geometry()
        self.canvas.adjustSize()
        self.canvas.update()

    def _zoom_reset(self) -> None:
        self.canvas.pixels_per_second = 60.0
        self.zoom_lbl.setText("Zoom: 100%")
        self.canvas._update_geometry()
        self.canvas.adjustSize()
        self.canvas.update()

    def load_media_clips(self, meta: object, subtitles: list[object] | None = None) -> None:
        """Populate initial video and audio tracks with media spans and optional subtitles."""
        duration_sec = getattr(meta, "duration", 0.0)
        dur_ms = max(1000, int(duration_sec * 1000))
        self.canvas.set_duration(dur_ms)

        width = getattr(meta, "width", 0)
        height = getattr(meta, "height", 0)
        vcodec = getattr(meta, "video_codec", "").upper()
        res_str = f" {width}x{height}" if width and height else ""
        codec_str = f" ({vcodec})" if vcodec else ""

        self.canvas.set_track_clips(
            "video",
            [
                TimelineClip(
                    id="vid-main",
                    start_ms=0,
                    end_ms=dur_ms,
                    label=f"Video{res_str}{codec_str}",
                    color=QColor(37, 99, 235, 220),
                )
            ],
        )

        has_audio = getattr(meta, "has_audio", False)
        if has_audio:
            acodec = getattr(meta, "audio_codec", "").upper()
            self.canvas.set_track_clips(
                "orig_audio",
                [
                    TimelineClip(
                        id="audio-main",
                        start_ms=0,
                        end_ms=dur_ms,
                        label=f"Audio: {acodec or 'Stereo'}",
                        color=QColor(16, 185, 129, 220),
                    )
                ],
            )
        else:
            self.canvas.set_track_clips("orig_audio", [])

        if subtitles:
            sub_clips: list[TimelineClip] = []
            for s in subtitles:
                s_idx = getattr(s, "index", len(sub_clips) + 1)
                s_start = getattr(s, "start_ms", 0)
                s_end = getattr(s, "end_ms", 0)
                s_text = getattr(s, "text", "")
                sub_clips.append(
                    TimelineClip(
                        id=f"sub_{s_idx}",
                        start_ms=s_start,
                        end_ms=s_end,
                        label=s_text.replace("\n", " "),
                        color=QColor(236, 72, 153, 200),
                    )
                )
            self.canvas.set_track_clips("subtitles", sub_clips)

    def load_transcript_clips(self, transcript_segments: list[object]) -> None:
        """Populate Dubbed Dialogue and Subtitle tracks from transcript segments."""
        dialogue_clips: list[TimelineClip] = []
        subtitle_clips: list[TimelineClip] = []

        # Vibrant 10-speaker color palette for multi-speaker visual separation
        speaker_colors = [
            QColor(59, 130, 246, 210),   # 1. Electric Blue (Male Lead)
            QColor(236, 72, 153, 210),   # 2. Hot Pink (Female Lead)
            QColor(16, 185, 129, 210),   # 3. Emerald Green (Deep Male)
            QColor(168, 85, 247, 210),   # 4. Purple (Mature Female)
            QColor(245, 158, 11, 210),   # 5. Amber (Young Male)
            QColor(14, 165, 233, 210),   # 6. Sky Blue (Young Female)
            QColor(249, 115, 22, 210),   # 7. Bright Orange (Child)
            QColor(132, 204, 22, 210),   # 8. Lime Green (Elderly Male)
            QColor(217, 70, 239, 210),   # 9. Fuchsia (Elderly Female)
            QColor(20, 184, 166, 210),   # 10. Teal (Narrator)
        ]

        speakers: dict[str, QColor] = {}

        for seg in transcript_segments:
            # Handle Segment object or dict
            start_sec = getattr(seg, "start", None) or (seg.get("start") if isinstance(seg, dict) else 0.0)
            end_sec = getattr(seg, "end", None) or (seg.get("end") if isinstance(seg, dict) else 0.0)
            speaker = getattr(seg, "speaker", None) or (seg.get("speaker") if isinstance(seg, dict) else "Speaker 1")
            text = getattr(seg, "source_text", None) or (seg.get("source_text") if isinstance(seg, dict) else "")
            target_text = getattr(seg, "target_text", "") or (seg.get("target_text", "") if isinstance(seg, dict) else "")
            seg_id = getattr(seg, "id", 0) or (seg.get("id", 0) if isinstance(seg, dict) else 0)

            if speaker not in speakers:
                color_idx = len(speakers) % len(speaker_colors)
                speakers[speaker] = speaker_colors[color_idx]

            color = speakers[speaker]
            start_ms = int(float(start_sec) * 1000)
            end_ms = int(float(end_sec) * 1000)

            dialogue_clips.append(
                TimelineClip(
                    id=f"dlg_{seg_id}",
                    start_ms=start_ms,
                    end_ms=end_ms,
                    label=target_text or text,
                    color=color,
                    speaker=speaker,
                )
            )

            subtitle_clips.append(
                TimelineClip(
                    id=f"sub_{seg_id}",
                    start_ms=start_ms,
                    end_ms=end_ms,
                    label=target_text or text,
                    color=QColor(219, 39, 119, 180),
                    speaker=speaker,
                )
            )

        self.canvas.set_track_clips("dialogue", dialogue_clips)
        self.canvas.set_track_clips("subtitles", subtitle_clips)

    def update_segment_clip(
        self,
        seg_id: int | str,
        label: str,
        start_ms: int,
        end_ms: int,
        speaker: str | None = None,
    ) -> None:
        """Update or insert an individual segment clip in the visual timeline."""
        self.canvas.update_segment_clip(seg_id, label, start_ms, end_ms, speaker)


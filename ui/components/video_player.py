"""Video player widget with hardware-accelerated viewport, custom QPainter subtitle overlay, and frame-stepping controls."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QImage, QPainter, QPainterPath, QPen
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)

from modules.media.inspector import MediaMetadata
from modules.media.player_controller import PlayerController


def format_timecode(ms: int, fps: float = 30.0) -> str:
    """Format milliseconds into HH:MM:SS:FF timecode."""
    total_seconds = max(0, ms) / 1000.0
    safe_fps = fps if fps > 0 else 30.0

    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    frames = int((total_seconds - int(total_seconds)) * safe_fps)

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"


class SubtitleOverlayWidget(QWidget):
    """Custom-painted QWidget for frame-accurate subtitle overlay without QLabel overhead.

    Rule: Subtitle overlay is a QWidget painted on top of the video widget, NOT a QLabel.
    Scales dynamically with viewport resize and renders clean black outlines for legibility.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.subtitle_text: str = ""

    def set_subtitle_text(self, text: str) -> None:
        """Update displayed subtitle text and trigger repaint."""
        cleaned = text.strip()
        if cleaned != self.subtitle_text:
            self.subtitle_text = cleaned
            self.update()

    def paintEvent(self, event: object) -> None:
        """Render high-contrast outlined subtitle text on top of the video canvas."""
        if not self.subtitle_text:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        # Scale font size dynamically based on viewport height (approx 4.5% of height)
        base_size = max(13, int(self.height() * 0.045))
        font = QFont("Segoe UI", base_size)
        font.setBold(True)
        painter.setFont(font)

        lines = [line.strip() for line in self.subtitle_text.splitlines() if line.strip()]
        if not lines:
            return

        metrics = painter.fontMetrics()
        line_height = metrics.height()
        total_text_height = len(lines) * line_height

        # Position 35px from bottom margin
        bottom_margin = max(24, int(self.height() * 0.06))
        start_y = self.height() - bottom_margin - total_text_height

        outline_width = max(2.5, base_size / 6.5)
        outline_pen = QPen(QColor(10, 10, 10, 240), outline_width)
        fill_brush = QBrush(QColor(255, 255, 255, 255))

        for i, line in enumerate(lines):
            text_width = metrics.horizontalAdvance(line)
            x = (self.width() - text_width) / 2.0
            y = start_y + (i * line_height) + metrics.ascent()

            path = QPainterPath()
            path.addText(QPointF(x, y), font, line)

            # Draw outer glow / shadow outline
            painter.strokePath(path, outline_pen)
            # Fill white text
            painter.fillPath(path, fill_brush)

        painter.end()


class SteppedFrameCanvas(QWidget):
    """Renders exact QImage frames decoded during paused frame stepping."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self._image: QImage | None = None

    def set_frame_image(self, image: QImage) -> None:
        self._image = image
        self.update()

    def clear(self) -> None:
        self._image = None
        self.update()

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 12, 16))

        if self._image is not None and not self._image.isNull():
            scaled = self._image.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawImage(x, y, scaled)

        painter.end()


class VideoMuteOverlay(QWidget):
    """Visual overlay displayed when the Video track is muted on the timeline."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setVisible(False)

    def paintEvent(self, event: object) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(10, 12, 16))
        painter.setPen(QPen(QColor(148, 163, 184), 1))
        font = QFont("Segoe UI", 12)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "🎬 Video Track Muted",
        )
        painter.end()


class VideoPlayerWidget(QWidget):
    """Unified video player with QMediaPlayer, exact frame canvas, subtitle overlay, and transport controls."""

    def __init__(
        self,
        controller: PlayerController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.controller = controller or PlayerController(parent=self)
        self._user_is_scrubbing: bool = False
        self._fps: float = 30.0
        self._duration_ms: int = 0

        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Video Canvas Container
        self.video_container = QWidget()
        self.video_container.setStyleSheet("background-color: #0b0f17;")
        self.video_container_layout = QStackedLayout(self.video_container)
        self.video_container_layout.setStackingMode(QStackedLayout.StackingMode.StackAll)

        # Base playback viewport
        self.video_widget = QVideoWidget()
        self.controller.media_player.setVideoOutput(self.video_widget)
        self.video_container_layout.addWidget(self.video_widget)

        # Frame stepping canvas (active when stepping exact single frames)
        self.stepped_canvas = SteppedFrameCanvas()
        self.stepped_canvas.setVisible(False)
        self.video_container_layout.addWidget(self.stepped_canvas)

        # Video mute blackout overlay
        self.video_mute_overlay = VideoMuteOverlay(self.video_container)
        self.video_container_layout.addWidget(self.video_mute_overlay)

        # Subtitle overlay on top of all
        self.subtitle_overlay = SubtitleOverlayWidget(self.video_container)
        self.video_container_layout.addWidget(self.subtitle_overlay)

        root_layout.addWidget(self.video_container, 1)

        # 2. Transport & Scrubber Bar
        transport_card = QFrame()
        transport_card.setStyleSheet("""
            QFrame {
                background-color: #121722;
                border-top: 1px solid #1e2536;
                padding: 6px 14px;
            }
        """)
        t_layout = QVBoxLayout(transport_card)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(6)

        # Scrubber Slider Row
        self.scrub_slider = QSlider(Qt.Orientation.Horizontal)
        self.scrub_slider.setRange(0, 1000)
        self.scrub_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 5px;
                background: #232a3d;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #6366f1;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #818cf8;
                width: 13px;
                height: 13px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::handle:horizontal:hover {
                background: #a5b4fc;
            }
        """)
        self.scrub_slider.sliderPressed.connect(self._on_scrub_pressed)
        self.scrub_slider.sliderMoved.connect(self._on_scrub_moved)
        self.scrub_slider.sliderReleased.connect(self._on_scrub_released)
        t_layout.addWidget(self.scrub_slider)

        # Buttons + Timecode Row
        controls_row = QHBoxLayout()
        controls_row.setSpacing(8)

        btn_style = """
            QPushButton {
                background-color: #1a2234;
                color: #e2e8f0;
                border: 1px solid #2d3748;
                border-radius: 5px;
                padding: 4px 10px;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #2b354d;
                border-color: #6366f1;
                color: #ffffff;
            }
            QPushButton:pressed {
                background-color: #151b28;
            }
        """

        # Restart / Start Button
        self.restart_btn = QPushButton("⏮ Start")
        self.restart_btn.setToolTip("Jump to Beginning (00:00:00)")
        self.restart_btn.setStyleSheet(btn_style)
        self.restart_btn.clicked.connect(self._on_restart_clicked)
        controls_row.addWidget(self.restart_btn)

        # Step Back Button (-1 Frame)
        self.step_back_btn = QPushButton("◀ -1 Frame")
        self.step_back_btn.setToolTip("Step Backward 1 Frame (Left Arrow)")
        self.step_back_btn.setStyleSheet(btn_style)
        self.step_back_btn.clicked.connect(lambda: self.controller.step_back(1))
        controls_row.addWidget(self.step_back_btn)

        # Play / Pause Toggle
        self.play_btn = QPushButton("▶ Play")
        self.play_btn.setFixedWidth(84)
        self.play_btn.setProperty("class", "primary")
        self.play_btn.setToolTip("Play / Pause Video (Spacebar)")
        self.play_btn.clicked.connect(self._toggle_play)
        controls_row.addWidget(self.play_btn)

        # Step Forward Button (+1 Frame)
        self.step_fwd_btn = QPushButton("+1 Frame ▶")
        self.step_fwd_btn.setToolTip("Step Forward 1 Frame (Right Arrow)")
        self.step_fwd_btn.setStyleSheet(btn_style)
        self.step_fwd_btn.clicked.connect(lambda: self.controller.step_forward(1))
        controls_row.addWidget(self.step_fwd_btn)

        # Timecode Display: HH:MM:SS:FF / HH:MM:SS:FF
        self.timecode_lbl = QLabel("00:00:00:00 / 00:00:00:00")
        self.timecode_lbl.setStyleSheet("""
            font-family: 'Consolas', monospace;
            font-size: 12px;
            color: #cbd5e1;
            font-weight: 600;
            background-color: #0c1017;
            border: 1px solid #1e293b;
            border-radius: 4px;
            padding: 4px 10px;
        """)
        controls_row.addWidget(self.timecode_lbl)

        controls_row.addStretch()

        # Volume control
        self.mute_btn = QPushButton("🔊")
        self.mute_btn.setFixedSize(28, 28)
        self.mute_btn.setToolTip("Mute / Unmute Audio (M)")
        self.mute_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 14px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #1e2433;
                border-radius: 4px;
            }
        """)
        self.mute_btn.clicked.connect(self._toggle_mute)
        controls_row.addWidget(self.mute_btn)

        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_slider.setValue(100)
        self.vol_slider.setFixedWidth(80)
        self.vol_slider.setToolTip("Volume: 100%")
        self.vol_slider.valueChanged.connect(self._on_volume_changed)
        controls_row.addWidget(self.vol_slider)

        self.vol_pct_lbl = QLabel("100%")
        self.vol_pct_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; min-width: 34px;")
        controls_row.addWidget(self.vol_pct_lbl)

        t_layout.addLayout(controls_row)
        root_layout.addWidget(transport_card)

    def _connect_signals(self) -> None:
        self.controller.position_changed.connect(self._on_position_changed)
        self.controller.duration_changed.connect(self._on_duration_changed)
        self.controller.state_changed.connect(self._on_state_changed)
        self.controller.metadata_ready.connect(self._on_metadata_ready)
        self.controller.frame_image_ready.connect(self._on_frame_image_ready)
        self.controller.subtitle_changed.connect(self.subtitle_overlay.set_subtitle_text)
        self.controller.video_visibility_changed.connect(self._on_video_visibility_changed)
        self.controller.subtitles_visibility_changed.connect(self._on_subtitles_visibility_changed)

    def _on_video_visibility_changed(self, visible: bool) -> None:
        self.video_mute_overlay.setVisible(not visible)
        if not visible:
            self.stepped_canvas.setVisible(False)
        else:
            if self.controller.current_video_path is not None and self.controller._is_paused:
                self.stepped_canvas.setVisible(True)

    def _on_subtitles_visibility_changed(self, visible: bool) -> None:
        self.subtitle_overlay.setVisible(visible)

    def load_media(self, video_path: Path | str, srt_path: Path | str | None = None) -> None:
        """Load media file into the player and controller."""
        self.controller.load_media(video_path, srt_path)

    def _on_restart_clicked(self) -> None:
        self.stepped_canvas.setVisible(False)
        self.controller.seek(0)

    def _toggle_play(self) -> None:
        # If switching from paused frame-step mode to play, hide stepped canvas
        self.stepped_canvas.setVisible(False)
        self.controller.toggle_play_pause()

    def _on_state_changed(self, is_playing: bool) -> None:
        if is_playing:
            self.play_btn.setText("⏸ Pause")
            self.stepped_canvas.setVisible(False)
        else:
            self.play_btn.setText("▶ Play")

    def _on_metadata_ready(self, metadata: MediaMetadata) -> None:
        self._fps = metadata.fps if metadata.fps > 0 else 30.0
        self._duration_ms = int(metadata.duration * 1000)
        self.scrub_slider.setRange(0, max(1, self._duration_ms))
        self._update_timecode(0)

    def _on_duration_changed(self, duration_ms: int) -> None:
        self._duration_ms = duration_ms
        self.scrub_slider.setRange(0, max(1, duration_ms))
        self._update_timecode(int(self.controller.media_player.position()))

    def _on_position_changed(self, pos_ms: int) -> None:
        if not self._user_is_scrubbing:
            self.scrub_slider.setValue(pos_ms)
        self._update_timecode(pos_ms)

    def _update_timecode(self, current_ms: int) -> None:
        cur_str = format_timecode(current_ms, self._fps)
        dur_str = format_timecode(self._duration_ms, self._fps)
        self.timecode_lbl.setText(f"{cur_str} / {dur_str}")

    def _on_frame_image_ready(self, img: QImage) -> None:
        """Show exact frame image on stepping canvas."""
        self.stepped_canvas.set_frame_image(img)
        self.stepped_canvas.setVisible(True)

    def _on_scrub_pressed(self) -> None:
        self._user_is_scrubbing = True
        self.stepped_canvas.setVisible(False)

    def _on_scrub_moved(self, val: int) -> None:
        self._update_timecode(val)
        # Responsive scrubbing within 50ms
        self.controller.seek_ms(val)

    def _on_scrub_released(self) -> None:
        self._user_is_scrubbing = False
        self.controller.seek_ms(self.scrub_slider.value())

    def _on_volume_changed(self, val: int) -> None:
        self.controller.set_volume(val / 100.0)
        self.vol_pct_lbl.setText(f"{val}%")
        self.vol_slider.setToolTip(f"Volume: {val}%")
        if val == 0:
            self.mute_btn.setText("🔇")
            self.mute_btn.setToolTip("Unmute Audio")
        else:
            self.mute_btn.setText("🔊")
            self.mute_btn.setToolTip("Mute Audio (M)")

    def _toggle_mute(self) -> None:
        if self.vol_slider.value() > 0:
            self._saved_vol = self.vol_slider.value()
            self.vol_slider.setValue(0)
        else:
            restore_vol = getattr(self, "_saved_vol", 100) or 100
            self.vol_slider.setValue(restore_vol)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        # Ensure overlays match exact viewport bounds on resize
        self.subtitle_overlay.setGeometry(self.video_container.rect())
        self.video_mute_overlay.setGeometry(self.video_container.rect())

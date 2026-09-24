"""Hybrid player controller combining QMediaPlayer with FrameCache for exact frame stepping."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QImage
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

from modules.media.frame_cache import FrameCache
from modules.media.inspector import MediaInspector, MediaMetadata

logger = logging.getLogger(__name__)


@dataclass
class SubtitleSegment:
    """Represents a timed subtitle line."""

    index: int
    start_ms: int
    end_ms: int
    text: str


def parse_srt_file(srt_path: Path | str) -> list[SubtitleSegment]:
    """Parse a standard .srt subtitle file into timed segments."""
    path = Path(srt_path)
    if not path.exists():
        return []

    try:
        content = path.read_text(encoding="utf-8-sig")
    except Exception:
        try:
            content = path.read_text(encoding="gb18030", errors="replace")
        except Exception:
            return []

    segments: list[SubtitleSegment] = []
    # Match standard SRT blocks: index, timestamp --> timestamp, text
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) < 2:
            continue

        # Extract timestamp line
        time_line_idx = -1
        for idx, line in enumerate(lines):
            if "-->" in line:
                time_line_idx = idx
                break

        if time_line_idx == -1:
            continue

        time_line = lines[time_line_idx]
        parts = time_line.split("-->")
        if len(parts) != 2:
            continue

        def to_ms(ts: str) -> int:
            ts = ts.strip().replace(",", ".")
            h, m, s = ts.split(":")
            return int((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)

        try:
            start_ms = to_ms(parts[0])
            end_ms = to_ms(parts[1])
        except Exception:
            continue

        sub_index = int(lines[0]) if lines[0].isdigit() else len(segments) + 1
        text = "\n".join(lines[time_line_idx + 1 :])

        segments.append(
            SubtitleSegment(
                index=sub_index,
                start_ms=start_ms,
                end_ms=end_ms,
                text=text,
            )
        )

    return sorted(segments, key=lambda s: s.start_ms)


class PlayerController(QObject):
    """Coordinates QMediaPlayer continuous playback with FrameCache single-frame stepping."""

    position_changed = Signal(int)  # milliseconds
    frame_changed = Signal(int)  # frame index
    duration_changed = Signal(int)  # total duration ms
    state_changed = Signal(bool)  # True = playing, False = paused
    frame_image_ready = Signal(QImage)  # exact decoded frame image
    metadata_ready = Signal(object)  # MediaMetadata
    subtitle_changed = Signal(str)  # current active subtitle string
    track_mute_changed = Signal(str, bool)  # track_id, is_muted
    track_solo_changed = Signal(str, bool)  # track_id, is_soloed
    video_visibility_changed = Signal(bool)  # True = visible, False = muted/hidden
    subtitles_visibility_changed = Signal(bool)  # True = visible, False = muted/hidden

    def __init__(
        self,
        frame_cache: FrameCache | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.frame_cache = frame_cache if frame_cache is not None else FrameCache()

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self._master_volume: float = 1.0
        self._stems: dict[str, tuple[QMediaPlayer, QAudioOutput]] = {}
        self._track_states: dict[str, dict[str, bool]] = {
            "video": {"muted": False, "solo": False},
            "orig_audio": {"muted": False, "solo": False},
            "bgm": {"muted": False, "solo": False},
            "dialogue": {"muted": False, "solo": False},
            "subtitles": {"muted": False, "solo": False},
        }

        self.current_video_path: Path | None = None
        self.metadata: MediaMetadata | None = None
        self.subtitles: list[SubtitleSegment] = []
        self._current_sub_text: str = ""
        self._current_frame: int = 0
        self._is_paused: bool = True

        self._connect_signals()

    def _connect_signals(self) -> None:
        self.media_player.positionChanged.connect(self._on_player_position_changed)
        self.media_player.durationChanged.connect(self._on_player_duration_changed)
        self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
        self.media_player.mediaStatusChanged.connect(self._on_media_status_changed)

    def _on_media_status_changed(self, status: QMediaPlayer.MediaStatus) -> None:
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.pause()
            self.seek_ms(0)
            self.state_changed.emit(False)

    def load_stems(self, stems: dict[str, Path | str]) -> None:
        """Load external audio stems for multi-track audition (e.g. orig_audio, bgm, dialogue)."""
        self.clear_stems()
        for track_id, p in stems.items():
            path = Path(p).resolve()
            if not path.exists():
                logger.warning("Stem file not found for track %s: %s", track_id, path)
                continue
            player = QMediaPlayer(self)
            out = QAudioOutput(self)
            player.setAudioOutput(out)
            player.setSource(QUrl.fromLocalFile(str(path)))
            self._stems[track_id] = (player, out)
            logger.info("Loaded stem for track '%s': %s", track_id, path.name)

        pos = self.media_player.position()
        for p, _ in self._stems.values():
            p.setPosition(pos)

        self._update_audio_routing()

    def clear_stems(self) -> None:
        """Clear and release all loaded stem players."""
        for p, a in self._stems.values():
            p.stop()
            p.setSource(QUrl())
            p.deleteLater()
            a.deleteLater()
        self._stems.clear()
        self._update_audio_routing()

    def set_track_mute(self, track_id: str, muted: bool) -> None:
        """Set mute state for a track ('video', 'orig_audio', 'bgm', 'dialogue', 'subtitles')."""
        if track_id not in self._track_states:
            self._track_states[track_id] = {"muted": False, "solo": False}
        self._track_states[track_id]["muted"] = muted

        if track_id == "video":
            self.video_visibility_changed.emit(not muted)
        elif track_id == "subtitles":
            self.subtitles_visibility_changed.emit(not muted)

        self._update_audio_routing()
        self.track_mute_changed.emit(track_id, muted)

    def set_track_solo(self, track_id: str, solo: bool) -> None:
        """Set solo state for a track."""
        if track_id not in self._track_states:
            self._track_states[track_id] = {"muted": False, "solo": False}
        self._track_states[track_id]["solo"] = solo

        if track_id == "video":
            if solo:
                self.video_visibility_changed.emit(True)
        elif track_id == "subtitles":
            if solo:
                self.subtitles_visibility_changed.emit(True)

        self._update_audio_routing()
        self.track_solo_changed.emit(track_id, solo)

    def is_track_muted(self, track_id: str) -> bool:
        return self._track_states.get(track_id, {}).get("muted", False)

    def is_track_soloed(self, track_id: str) -> bool:
        return self._track_states.get(track_id, {}).get("solo", False)

    def _update_audio_routing(self) -> None:
        """Calculate effective audible volume per audio track and master output."""
        audio_track_ids = ("orig_audio", "bgm", "dialogue")
        any_audio_solo = any(self._track_states.get(t, {}).get("solo", False) for t in audio_track_ids)

        if self._stems:
            # Stems are active: silence the master video's embedded audio to avoid doubling
            self.audio_output.setVolume(0.0)
            self.audio_output.setMuted(True)

            for t in audio_track_ids:
                if t in self._stems:
                    p, a = self._stems[t]
                    t_state = self._track_states.get(t, {"muted": False, "solo": False})
                    if any_audio_solo:
                        is_audible = t_state.get("solo", False) and not t_state.get("muted", False)
                    else:
                        is_audible = not t_state.get("muted", False)

                    if is_audible:
                        a.setMuted(False)
                        a.setVolume(self._master_volume)
                    else:
                        a.setMuted(True)
                        a.setVolume(0.0)
        else:
            # Standalone media playback without stems: orig_audio controls master player's audio
            orig_state = self._track_states.get("orig_audio", {"muted": False, "solo": False})
            if any_audio_solo:
                is_audible = orig_state.get("solo", False) and not orig_state.get("muted", False)
            else:
                is_audible = not orig_state.get("muted", False)

            if is_audible:
                self.audio_output.setMuted(False)
                self.audio_output.setVolume(self._master_volume)
            else:
                self.audio_output.setMuted(True)
                self.audio_output.setVolume(0.0)

    def load_media(
        self,
        video_path: Path | str,
        srt_path: Path | str | None = None,
    ) -> None:
        """Load a video file, inspect its metadata, and optionally load accompanying subtitles."""
        path = Path(video_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {path}")

        # Reset stems and track states on new media load
        self.clear_stems()
        self._track_states = {
            "video": {"muted": False, "solo": False},
            "orig_audio": {"muted": False, "solo": False},
            "bgm": {"muted": False, "solo": False},
            "dialogue": {"muted": False, "solo": False},
            "subtitles": {"muted": False, "solo": False},
        }
        self.video_visibility_changed.emit(True)
        self.subtitles_visibility_changed.emit(True)

        self.current_video_path = path

        # Probe metadata
        self.metadata = MediaInspector.probe(path)
        self.metadata_ready.emit(self.metadata)

        # Load subtitles
        if srt_path is not None:
            self.load_subtitles(srt_path)
        else:
            # Auto-detect companion .srt next to video file
            candidate_srt = path.with_suffix(".srt")
            if candidate_srt.exists():
                self.load_subtitles(candidate_srt)
            else:
                self.subtitles.clear()
                self._update_subtitle(0)

        # Set media source
        self.media_player.setSource(QUrl.fromLocalFile(str(path)))
        self.pause()
        self.seek_ms(0)

        # Decode and render frame 0 for immediate visual preview on load
        fps = self.metadata.fps if self.metadata and self.metadata.fps > 0 else 30.0
        frame_0 = self.frame_cache.extract_exact_frame(path, 0, fps)
        if not frame_0.isNull():
            self.frame_image_ready.emit(frame_0)

    def load_subtitles(self, srt_path: Path | str) -> None:
        """Load and parse an SRT subtitle file."""
        self.subtitles = parse_srt_file(srt_path)
        logger.info("Loaded %d subtitle segments from %s", len(self.subtitles), srt_path)
        self._update_subtitle(int(self.media_player.position()))

    def play(self) -> None:
        """Start or resume continuous video playback and synchronize active stems."""
        pos = self.media_player.position()
        for p, _ in self._stems.values():
            p.setPosition(pos)
            p.play()
        self.media_player.play()

    def pause(self) -> None:
        """Pause continuous video playback and all active stems."""
        self.media_player.pause()
        for p, _ in self._stems.values():
            p.pause()

    def toggle_play_pause(self) -> None:
        """Toggle between play and pause."""
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def seek_ms(self, pos_ms: int) -> None:
        """Seek player to millisecond position."""
        target_ms = max(0, pos_ms)
        self.media_player.setPosition(target_ms)
        for p, _ in self._stems.values():
            p.setPosition(target_ms)
        self._on_player_position_changed(target_ms)

    def seek(self, pos_ms: int) -> None:
        """Alias for seek_ms."""
        self.seek_ms(pos_ms)

    def step_forward(self, frames: int = 1) -> None:
        """Step forward exactly `frames` frames using FFmpeg decoding.

        Rule: step_forward()/step_back() decode EXACTLY ONE FRAME via FFmpeg subprocess.
        """
        if not self.current_video_path or not self.metadata:
            return

        self.pause()
        fps = self.metadata.fps if self.metadata.fps > 0 else 30.0
        total_f = (
            self.metadata.total_frames
            if self.metadata.total_frames > 0
            else int(self.metadata.duration * fps)
        )

        target_frame = min(total_f - 1, self._current_frame + frames)
        self._apply_frame_step(target_frame, fps)

    def step_back(self, frames: int = 1) -> None:
        """Step backward exactly `frames` frames using FFmpeg decoding."""
        if not self.current_video_path or not self.metadata:
            return

        self.pause()
        fps = self.metadata.fps if self.metadata.fps > 0 else 30.0
        target_frame = max(0, self._current_frame - frames)
        self._apply_frame_step(target_frame, fps)

    def _apply_frame_step(self, target_frame: int, fps: float) -> None:
        if not self.current_video_path:
            return

        self._current_frame = target_frame
        target_ms = int((target_frame / fps) * 1000)

        # Seek media player and stems
        self.media_player.setPosition(target_ms)
        for p, _ in self._stems.values():
            p.setPosition(target_ms)

        # Exact frame decoding via FrameCache
        frame_img = self.frame_cache.extract_exact_frame(
            self.current_video_path,
            target_frame,
            fps,
        )

        if not frame_img.isNull():
            self.frame_image_ready.emit(frame_img)

        self.frame_changed.emit(target_frame)
        self.position_changed.emit(target_ms)
        self._update_subtitle(target_ms)

        # Prefetch neighborhood
        self.frame_cache.prefetch(self.current_video_path, target_frame, fps, radius=10)

    def set_volume(self, volume: float) -> None:
        """Set playback volume between 0.0 and 1.0."""
        self._master_volume = max(0.0, min(1.0, volume))
        self._update_audio_routing()

    def _on_player_position_changed(self, pos_ms: int) -> None:
        fps = self.metadata.fps if self.metadata and self.metadata.fps > 0 else 30.0
        frame_idx = int((pos_ms / 1000.0) * fps)
        self._current_frame = frame_idx

        # Synchronize stems if playback drifts beyond 150ms
        for p, _ in self._stems.values():
            if abs(p.position() - pos_ms) > 150:
                p.setPosition(pos_ms)

        self.position_changed.emit(pos_ms)
        self.frame_changed.emit(frame_idx)
        self._update_subtitle(pos_ms)

    def _on_player_duration_changed(self, duration_ms: int) -> None:
        self.duration_changed.emit(duration_ms)

    def _on_playback_state_changed(self, state: QMediaPlayer.PlaybackState) -> None:
        is_playing = state == QMediaPlayer.PlaybackState.PlayingState
        self._is_paused = not is_playing
        if is_playing:
            pos = self.media_player.position()
            for p, _ in self._stems.values():
                if p.playbackState() != QMediaPlayer.PlaybackState.PlayingState:
                    p.setPosition(pos)
                    p.play()
        else:
            for p, _ in self._stems.values():
                if p.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                    p.pause()
        self.state_changed.emit(is_playing)

    def _update_subtitle(self, pos_ms: int) -> None:
        """Match and emit active subtitle text within +/- 1 frame tolerance."""
        fps = self.metadata.fps if self.metadata and self.metadata.fps > 0 else 30.0
        frame_ms = int(1000.0 / fps)

        active_text = ""
        for seg in self.subtitles:
            # +/- 1 frame tolerance window as per Section 7 Phase 3 rule
            if (seg.start_ms - frame_ms) <= pos_ms <= (seg.end_ms + frame_ms):
                active_text = seg.text
                break

        if active_text != self._current_sub_text:
            self._current_sub_text = active_text
            self.subtitle_changed.emit(active_text)

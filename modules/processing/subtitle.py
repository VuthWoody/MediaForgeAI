"""Subtitle processing module supporting SRT, VTT, and ASS export, styling, and FFmpeg burn-in."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.cancellation import CancellationToken
from modules.ai.engine import Transcript, TranscriptSegment

logger = logging.getLogger(__name__)


@dataclass
class SubtitleStyle:
    """Styling specification for ASS subtitles and FFmpeg burn-in."""

    font_name: str = "Noto Sans"
    font_size: int = 24
    primary_color: str = "&H00FFFFFF"  # White in ASS &HAABBGGRR / &HBBGGRR
    outline_color: str = "&H00000000"  # Black
    back_color: str = "&H80000000"     # Semi-transparent shadow
    bold: bool = True
    italic: bool = False
    outline_width: float = 2.0
    shadow_offset: float = 1.0
    alignment: int = 2  # 2 = Bottom-Center in ASS
    margin_v: int = 30

    def to_ass_force_style(self) -> str:
        """Format style as an FFmpeg force_style string."""
        bold_val = -1 if self.bold else 0
        italic_val = -1 if self.italic else 0
        return (
            f"FontName={self.font_name},"
            f"FontSize={self.font_size},"
            f"PrimaryColour={self.primary_color},"
            f"OutlineColour={self.outline_color},"
            f"BackColour={self.back_color},"
            f"Bold={bold_val},"
            f"Italic={italic_val},"
            f"Outline={self.outline_width},"
            f"Shadow={self.shadow_offset},"
            f"Alignment={self.alignment},"
            f"MarginV={self.margin_v}"
        )


class SubtitleManager:
    """Manages subtitle export (SRT, VTT, ASS), soft-muxing, and video burn-in."""

    @staticmethod
    def format_srt_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS,mmm for SRT."""
        total_ms = int(round(seconds * 1000))
        h = total_ms // 3600000
        total_ms %= 3600000
        m = total_ms // 60000
        total_ms %= 60000
        s = total_ms // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def format_vtt_time(seconds: float) -> str:
        """Format seconds as HH:MM:SS.mmm for WebVTT."""
        total_ms = int(round(seconds * 1000))
        h = total_ms // 3600000
        total_ms %= 3600000
        m = total_ms // 60000
        total_ms %= 60000
        s = total_ms // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    @staticmethod
    def format_ass_time(seconds: float) -> str:
        """Format seconds as H:MM:SS.cc for ASS."""
        total_cs = int(round(seconds * 100))
        h = total_cs // 360000
        total_cs %= 360000
        m = total_cs // 6000
        total_cs %= 6000
        s = total_cs // 100
        cs = total_cs % 100
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    @classmethod
    def export_srt(
        cls,
        transcript: Transcript | list[TranscriptSegment],
        output_path: Path | str,
        include_speaker: bool = False,
    ) -> Path:
        """Export transcript to standard .srt format."""
        segments = transcript.segments if isinstance(transcript, Transcript) else transcript
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = []
        for seg in segments:
            text = seg.target_text if seg.target_text else seg.source_text
            if not text.strip():
                continue
            lines.append(str(seg.id))
            lines.append(f"{cls.format_srt_time(seg.start)} --> {cls.format_srt_time(seg.end)}")
            speaker_prefix = f"[{seg.speaker}] " if include_speaker and seg.speaker else ""
            lines.append(f"{speaker_prefix}{text.strip()}")
            lines.append("")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    @classmethod
    def export_vtt(
        cls,
        transcript: Transcript | list[TranscriptSegment],
        output_path: Path | str,
        include_speaker: bool = False,
    ) -> Path:
        """Export transcript to standard .vtt (WebVTT) format."""
        segments = transcript.segments if isinstance(transcript, Transcript) else transcript
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        lines: list[str] = ["WEBVTT", ""]
        for seg in segments:
            text = seg.target_text if seg.target_text else seg.source_text
            if not text.strip():
                continue
            lines.append(str(seg.id))
            lines.append(f"{cls.format_vtt_time(seg.start)} --> {cls.format_vtt_time(seg.end)}")
            speaker_prefix = f"[{seg.speaker}] " if include_speaker and seg.speaker else ""
            lines.append(f"{speaker_prefix}{text.strip()}")
            lines.append("")

        out.write_text("\n".join(lines), encoding="utf-8")
        return out

    @classmethod
    def export_ass(
        cls,
        transcript: Transcript | list[TranscriptSegment],
        output_path: Path | str,
        style: SubtitleStyle | None = None,
        include_speaker: bool = False,
    ) -> Path:
        """Export transcript to Advanced SubStation Alpha (.ass) format."""
        segments = transcript.segments if isinstance(transcript, Transcript) else transcript
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        st = style or SubtitleStyle()

        header = f"""[Script Info]
Title: MediaForge AI Subtitle
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{st.font_name},{st.font_size},{st.primary_color},&H000000FF,{st.outline_color},{st.back_color},{-1 if st.bold else 0},{-1 if st.italic else 0},0,0,100,100,0,0,1,{st.outline_width},{st.shadow_offset},{st.alignment},20,20,{st.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events: list[str] = []
        for seg in segments:
            text = seg.target_text if seg.target_text else seg.source_text
            if not text.strip():
                continue
            # Replace newlines with ASS \N
            clean_text = text.strip().replace("\n", "\\N")
            start_s = cls.format_ass_time(seg.start)
            end_s = cls.format_ass_time(seg.end)
            spk_name = seg.speaker if include_speaker else ""
            events.append(f"Dialogue: 0,{start_s},{end_s},Default,{spk_name},0,0,0,,{clean_text}")

        content = header + "\n".join(events) + "\n"
        out.write_text(content, encoding="utf-8")
        return out

    @classmethod
    def soft_mux(
        cls,
        video_path: Path | str,
        subtitle_path: Path | str,
        output_path: Path | str,
        audio_path: Path | str | None = None,
        token: CancellationToken | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Soft-mux subtitles into MP4/MKV container without transcoding video (Section 7 default)."""
        if token:
            token.throw_if_cancelled()
        if progress:
            progress(0.1, "Soft-muxing subtitles into video container...")

        v_in = Path(video_path).resolve()
        sub_in = Path(subtitle_path).resolve()
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)

        is_mkv = out.suffix.lower() == ".mkv"
        sub_codec = "ass" if is_mkv else "mov_text"
        has_sub = sub_in.exists() and sub_in.stat().st_size > 0

        if audio_path:
            a_in = Path(audio_path).resolve()
            if has_sub:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-i",
                    str(a_in),
                    "-i",
                    str(sub_in),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-map",
                    "2:s:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-c:s",
                    sub_codec,
                    "-metadata:s:s:0",
                    "title=Subtitles",
                    "-shortest",
                    str(out),
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-i",
                    str(a_in),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(out),
                ]
        else:
            if has_sub:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-i",
                    str(sub_in),
                    "-map",
                    "0:v",
                    "-map",
                    "0:a?",
                    "-map",
                    "1:s",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    "-c:s",
                    sub_codec,
                    "-metadata:s:s:0",
                    "title=Subtitles",
                    str(out),
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-map",
                    "0:v",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    str(out),
                ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=180)
        if progress:
            progress(1.0, "Soft-muxing complete.")
        return out

    @classmethod
    def burn_in(
        cls,
        video_path: Path | str,
        subtitle_path: Path | str,
        output_path: Path | str,
        audio_path: Path | str | None = None,
        style: SubtitleStyle | None = None,
        token: CancellationToken | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> Path:
        """Burn subtitles directly into video frames using FFmpeg -vf subtitles (Section 7 opt-in)."""
        if token:
            token.throw_if_cancelled()
        if progress:
            progress(0.1, "Preparing FFmpeg burn-in filter...")

        v_in = Path(video_path).resolve()
        sub_in = Path(subtitle_path).resolve()
        out = Path(output_path).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        st = style or SubtitleStyle()
        has_sub = sub_in.exists() and sub_in.stat().st_size > 0

        if has_sub:
            escaped_sub = str(sub_in).replace("\\", "/").replace(":", "\\:")
            force_style = st.to_ass_force_style()
            vf_arg = f"subtitles='{escaped_sub}':force_style='{force_style}'"

            if progress:
                progress(0.3, "Rendering hardcoded subtitles via FFmpeg...")

            if audio_path:
                a_in = Path(audio_path).resolve()
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-i",
                    str(a_in),
                    "-vf",
                    vf_arg,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(out),
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-vf",
                    vf_arg,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-c:a",
                    "copy",
                    str(out),
                ]
        else:
            if audio_path:
                a_in = Path(audio_path).resolve()
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-i",
                    str(a_in),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "192k",
                    "-shortest",
                    str(out),
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-i",
                    str(v_in),
                    "-map",
                    "0:v",
                    "-map",
                    "0:a?",
                    "-c:v",
                    "copy",
                    "-c:a",
                    "copy",
                    str(out),
                ]

        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
        if progress:
            progress(1.0, "Subtitle burn-in complete.")
        return out

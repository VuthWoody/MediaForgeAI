"""Media inspector wrapping FFprobe with mtime-based caching."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.exceptions import NetworkError, ValidationError

logger = logging.getLogger(__name__)


def parse_fps(fps_str: str) -> float:
    """Parse FFprobe fractional frame rate string (e.g. '30/1' or '30000/1001') to float."""
    if not fps_str or fps_str == "0/0":
        return 30.0
    if "/" in fps_str:
        num, den = fps_str.split("/", 1)
        try:
            den_val = float(den)
            if den_val == 0:
                return 30.0
            return float(num) / den_val
        except (ValueError, ZeroDivisionError):
            return 30.0
    try:
        return float(fps_str)
    except ValueError:
        return 30.0


@dataclass
class MediaMetadata:
    """Typed metadata describing a container, video stream, and audio stream."""

    file_path: str
    file_size: int
    mtime: float
    format_name: str
    duration: float
    bitrate: int
    width: int
    height: int
    fps: float
    total_frames: int
    video_codec: str
    pix_fmt: str
    aspect_ratio: str
    has_audio: bool
    audio_codec: str
    sample_rate: int
    channels: int
    audio_bitrate: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MediaMetadata:
        return cls(
            file_path=str(data.get("file_path", "")),
            file_size=int(data.get("file_size", 0)),
            mtime=float(data.get("mtime", 0.0)),
            format_name=str(data.get("format_name", "")),
            duration=float(data.get("duration", 0.0)),
            bitrate=int(data.get("bitrate", 0)),
            width=int(data.get("width", 0)),
            height=int(data.get("height", 0)),
            fps=float(data.get("fps", 30.0)),
            total_frames=int(data.get("total_frames", 0)),
            video_codec=str(data.get("video_codec", "")),
            pix_fmt=str(data.get("pix_fmt", "")),
            aspect_ratio=str(data.get("aspect_ratio", "")),
            has_audio=bool(data.get("has_audio", False)),
            audio_codec=str(data.get("audio_codec", "")),
            sample_rate=int(data.get("sample_rate", 0)),
            channels=int(data.get("channels", 0)),
            audio_bitrate=int(data.get("audio_bitrate", 0)),
        )


class MediaInspector:
    """FFprobe wrapper with file modification-time (mtime) caching."""

    _cache: dict[str, MediaMetadata] = {}

    @classmethod
    def probe(
        cls,
        file_path: Path | str,
        project_cache: dict[str, Any] | None = None,
    ) -> MediaMetadata:
        """Probe media file metadata using FFprobe with caching."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Media file not found: {path}")

        current_mtime = path.stat().st_mtime
        path_str = str(path)

        # 1. Check in-memory cache
        if path_str in cls._cache:
            cached = cls._cache[path_str]
            if abs(cached.mtime - current_mtime) < 0.001:
                return cached

        # 2. Check project cache dict if supplied
        if project_cache is not None and path_str in project_cache:
            try:
                candidate = MediaMetadata.from_dict(project_cache[path_str])
                if abs(candidate.mtime - current_mtime) < 0.001:
                    cls._cache[path_str] = candidate
                    return candidate
            except Exception as e:
                logger.debug("Project cache deserialization error: %s", e)

        # 3. Execute FFprobe
        cmd = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
                timeout=20,
            )
            raw = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            raise ValidationError(f"FFprobe failed to inspect {path}: {e.stderr}") from e
        except json.JSONDecodeError as e:
            raise ValidationError(f"FFprobe returned invalid JSON: {e}") from e
        except Exception as e:
            raise NetworkError(f"Error inspecting media: {e}") from e

        format_data = raw.get("format", {})
        streams = raw.get("streams", [])

        # Parse container format
        format_name = format_data.get("format_name", "unknown")
        duration = float(format_data.get("duration") or 0.0)
        bitrate = int(format_data.get("bit_rate") or 0)
        file_size = int(format_data.get("size") or path.stat().st_size)

        # Video stream
        v_stream: dict[str, Any] | None = None
        a_stream: dict[str, Any] | None = None

        for s in streams:
            ctype = s.get("codec_type")
            if ctype == "video" and v_stream is None:
                v_stream = s
            elif ctype == "audio" and a_stream is None:
                a_stream = s

        width = 0
        height = 0
        fps = 30.0
        total_frames = 0
        video_codec = ""
        pix_fmt = ""
        aspect_ratio = ""

        if v_stream is not None:
            width = int(v_stream.get("width") or 0)
            height = int(v_stream.get("height") or 0)
            fps_str = v_stream.get("avg_frame_rate") or v_stream.get("r_frame_rate") or "30/1"
            fps = parse_fps(fps_str)
            video_codec = v_stream.get("codec_name") or ""
            pix_fmt = v_stream.get("pix_fmt") or ""
            aspect_ratio = (
                v_stream.get("display_aspect_ratio")
                or (f"{width}:{height}" if width and height else "")
            )

            # Extract or compute frame count
            nb_frames = v_stream.get("nb_frames")
            if nb_frames and str(nb_frames).isdigit():
                total_frames = int(nb_frames)
            elif duration > 0 and fps > 0:
                total_frames = int(round(duration * fps))

        # Audio stream
        has_audio = a_stream is not None
        audio_codec = ""
        sample_rate = 0
        channels = 0
        audio_bitrate = 0

        if a_stream is not None:
            audio_codec = a_stream.get("codec_name") or ""
            sample_rate = int(a_stream.get("sample_rate") or 0)
            channels = int(a_stream.get("channels") or 0)
            audio_bitrate = int(a_stream.get("bit_rate") or 0)

        metadata = MediaMetadata(
            file_path=path_str,
            file_size=file_size,
            mtime=current_mtime,
            format_name=format_name,
            duration=duration,
            bitrate=bitrate,
            width=width,
            height=height,
            fps=fps,
            total_frames=total_frames,
            video_codec=video_codec,
            pix_fmt=pix_fmt,
            aspect_ratio=aspect_ratio,
            has_audio=has_audio,
            audio_codec=audio_codec,
            sample_rate=sample_rate,
            channels=channels,
            audio_bitrate=audio_bitrate,
        )

        cls._cache[path_str] = metadata
        if project_cache is not None:
            project_cache[path_str] = metadata.to_dict()

        return metadata

    @classmethod
    def clear_cache(cls) -> None:
        """Clear in-memory inspection cache."""
        cls._cache.clear()

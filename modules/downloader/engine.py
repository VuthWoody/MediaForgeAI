"""Multi-platform media downloader engine wrapping yt-dlp."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yt_dlp

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, NetworkError

logger = logging.getLogger(__name__)


class DownloaderEngine:
    """High-performance downloader engine wrapping yt-dlp with cancellation support."""

    name: str = "yt-dlp"
    required_locks: list[str] = ["NETWORK_BULK"]

    def probe(self) -> dict[str, Any]:
        """Check availability and version of yt-dlp."""
        try:
            ver = str(yt_dlp.version.__version__)
            return {"status": "ready", "version": ver, "error": None}
        except Exception as e:
            return {"status": "unavailable", "version": None, "error": str(e)}

    def extract_info(
        self,
        url: str,
        token: CancellationToken | None = None,
    ) -> dict[str, Any]:
        """Extract metadata (title, formats, thumbnail, creator, duration) without downloading."""
        if token is not None:
            token.throw_if_cancelled()

        ydl_opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise NetworkError(f"Could not extract information from {url}")
                return {
                    "id": info.get("id"),
                    "title": info.get("title", "Untitled Video"),
                    "creator": info.get("uploader") or info.get("creator") or info.get("channel") or "Unknown",
                    "duration": float(info.get("duration") or 0.0),
                    "thumbnail": info.get("thumbnail"),
                    "platform": info.get("extractor_key") or "Generic",
                    "formats": [
                        {
                            "format_id": f.get("format_id"),
                            "ext": f.get("ext"),
                            "resolution": f.get("resolution") or f"{f.get('width', '?')}x{f.get('height', '?')}",
                            "vcodec": f.get("vcodec"),
                            "acodec": f.get("acodec"),
                            "filesize": f.get("filesize") or f.get("filesize_approx"),
                        }
                        for f in info.get("formats", [])
                        if f.get("vcodec") != "none" or f.get("acodec") != "none"
                    ],
                }
        except yt_dlp.utils.DownloadError as e:
            raise NetworkError(f"Extraction error: {e}") from e

    def download(
        self,
        url: str,
        dest_dir: Path | str,
        format_spec: str = "bestvideo+bestaudio/best",
        download_subs: bool = True,
        download_thumbnail: bool = True,
        progress_cb: Callable[[float, str], None] | None = None,
        token: CancellationToken | None = None,
    ) -> Path:
        """Download media with best video and best audio merged into mp4."""
        if token is not None:
            token.throw_if_cancelled()

        target_dir = Path(dest_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        downloaded_file: Path | None = None

        def progress_hook(d: dict[str, Any]) -> None:
            nonlocal downloaded_file
            if token is not None and token.is_cancelled:
                raise CancelledError("Download cancelled by user.")

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                pct = (downloaded / total) if total > 0 else 0.0
                speed = d.get("speed")
                speed_str = f"{speed / (1024 * 1024):.1f} MB/s" if speed else "calculating"
                msg = f"Downloading: {speed_str}"
                if progress_cb is not None:
                    progress_cb(min(0.95, pct), msg)

            elif status == "finished":
                filename = d.get("filename")
                if filename:
                    downloaded_file = Path(filename)
                if progress_cb is not None:
                    progress_cb(0.98, "Merging audio/video streams...")

        out_template = str(target_dir / "%(title).100s.%(ext)s")

        ydl_opts: dict[str, Any] = {
            "format": format_spec,
            "outtmpl": out_template,
            "merge_output_format": "mp4",
            "progress_hooks": [progress_hook],
            "quiet": True,
            "no_warnings": True,
            "writethumbnail": download_thumbnail,
            "writesubtitles": download_subs,
            "allsubtitles": False,
            "subtitleslangs": ["en", "km", "zh"],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if downloaded_file and downloaded_file.exists():
                    final_path = downloaded_file
                else:
                    # In case format was merged to .mp4
                    merged_filename = ydl.prepare_filename(info)
                    candidate = Path(merged_filename)
                    if candidate.with_suffix(".mp4").exists():
                        final_path = candidate.with_suffix(".mp4")
                    else:
                        final_path = candidate

                if progress_cb is not None:
                    progress_cb(1.0, "Download and stream merge complete.")

                return final_path

        except yt_dlp.utils.DownloadError as e:
            if "cancelled" in str(e).lower():
                raise CancelledError("Download was cancelled.") from e
            raise NetworkError(f"Download error: {e}") from e

"""Download queue manager adapting download tasks to the unified SQLite JobQueue."""

from __future__ import annotations

import json
import logging
import threading
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.cancellation import CancellationToken
from core.event_bus import get_event_bus
from core.exceptions import CancelledError
from core.job_queue import Job, JobQueue
from core.resource_lock import ResourceLock
from modules.downloader.engine import DownloaderEngine
from modules.downloader.hongguo import HongguoExtractor
from modules.downloader.organizer import MediaItem, MediaOrganizer, sanitize_filename
from modules.downloader.scraper import PlaywrightScraper

logger = logging.getLogger(__name__)


class DownloadQueueManager:
    """Manages download job scheduling over core.JobQueue and ResourceLock('NETWORK_BULK')."""

    def __init__(
        self,
        job_queue: JobQueue,
        organizer: MediaOrganizer,
        resource_lock: ResourceLock | None = None,
        max_workers: int = 4,
    ) -> None:
        self.job_queue = job_queue
        self.organizer = organizer
        self.resource_lock = resource_lock or ResourceLock()
        self.engine = DownloaderEngine()
        self.max_workers = max(1, min(32, max_workers))

        self._tokens: dict[str, CancellationToken] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="DLWorker")
        self._paused_jobs: set[str] = set()
        self._active_network_count = 0

    def _acquire_network_lock(self, token: CancellationToken | None = None) -> None:
        """Acquire network bulk lock at manager level so multiple download threads can run concurrently."""
        with self._lock:
            if self._active_network_count == 0:
                acquired = self.resource_lock.acquire("NETWORK_BULK", timeout=60.0, token=token)
                if not acquired:
                    raise TimeoutError("Failed to acquire network lock within timeout of 60.0s")
            self._active_network_count += 1

    def _release_network_lock(self) -> None:
        """Release network bulk lock when no download workers are active."""
        with self._lock:
            if self._active_network_count > 0:
                self._active_network_count -= 1
                if self._active_network_count == 0:
                    self.resource_lock.release("NETWORK_BULK")

    @contextmanager
    def _network_lock_scope(self, token: CancellationToken | None = None) -> Generator[None, None, None]:
        """Reference-counted network lock context ensuring concurrent download workers run concurrently."""
        self._acquire_network_lock(token)
        try:
            yield
        finally:
            self._release_network_lock()

    def set_max_workers(self, count: int) -> None:
        """Update concurrency slider bounded between 1 and 32 threads."""
        new_count = max(1, min(32, count))
        if new_count != self.max_workers:
            self.max_workers = new_count
            self._executor.shutdown(wait=False)
            self._executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="DLWorker")

    def enqueue_download(
        self,
        url: str,
        target_dir: Path | str | None = None,
        format_spec: str = "bestvideo+bestaudio/best",
        use_sniffer: bool = False,
    ) -> Job:
        """Enqueue a new media download job on the unified SQLite job queue."""
        payload: dict[str, Any] = {
            "url": url,
            "target_dir": str(target_dir) if target_dir else str(self.organizer.base_dir),
            "format_spec": format_spec,
            "use_sniffer": use_sniffer,
        }

        job = self.job_queue.enqueue(kind="download", payload=payload)
        self._spawn_worker(job.id, payload)
        return job

    def enqueue_hongguo_episode(
        self,
        series_id: str,
        episode_num: int,
        vid: str = "",
        title: str = "",
        series_name: str = "",
        generate_srt: bool = True,
        target_dir: Path | str | None = None,
        characters: list[dict[str, str]] | None = None,
    ) -> Job:
        """Enqueue a Hongguo short drama episode download job with companion .srt generation and character metadata."""
        ep_title = title or f"{series_name} 第{episode_num}集"
        payload: dict[str, Any] = {
            "is_hongguo": True,
            "series_id": series_id,
            "episode_num": episode_num,
            "vid": vid,
            "title": ep_title,
            "series_name": series_name or "Hongguo Drama",
            "generate_srt": generate_srt,
            "characters": characters or [],
            "url": f"https://hongguoduanju.com/player/{series_id}/{vid}" if vid else f"https://hongguoduanju.com/player/{series_id}",
            "target_dir": str(target_dir) if target_dir else str(self.organizer.base_dir),
        }
        job = self.job_queue.enqueue(kind="download", payload=payload)
        self._spawn_worker(job.id, payload)
        return job

    def cancel_download(self, job_id: str) -> None:
        """Cancel a running or queued download job."""
        with self._lock:
            token = self._tokens.get(job_id)
            if token is not None:
                token.cancel()
        self.job_queue.cancel(job_id)

    def pause_download(self, job_id: str) -> None:
        """Pause a download by cancelling the active worker while preserving restart state."""
        with self._lock:
            self._paused_jobs.add(job_id)
            token = self._tokens.get(job_id)
            if token is not None:
                token.cancel()
        self.job_queue.cancel(job_id)

    def resume_download(self, job_id: str) -> Job | None:
        """Resume or retry a paused/failed download preserving all original metadata and destination folder."""
        job = self.job_queue.get_job(job_id)
        if job is None:
            return None

        with self._lock:
            self._paused_jobs.discard(job_id)

        # Preserve the entire payload intact (series_name, series_id, episode_num, etc.)
        payload = dict(job.payload)

        # Reset status in SQLite so UI row directly transitions from failed/paused -> queued -> downloading
        now_iso = datetime.now(UTC).isoformat()
        with self.job_queue._lock:
            self.job_queue._conn.execute(
                """
                UPDATE jobs
                SET status = 'queued', progress = 0.0, error = NULL, updated_at = ?
                WHERE id = ?;
                """,
                (now_iso, job_id),
            )
        try:
            get_event_bus().job_queued.emit(job_id)
            get_event_bus().job_progress.emit(job_id, 0.0, "Restarting download...")
        except Exception:
            pass

        self._spawn_worker(job_id, payload)
        return self.job_queue.get_job(job_id)

    def _spawn_worker(self, job_id: str, payload: dict[str, Any]) -> None:
        token = CancellationToken()
        with self._lock:
            self._tokens[job_id] = token

        self._executor.submit(self._execute_download_job, job_id, payload, token)

    def _execute_download_job(
        self,
        job_id: str,
        payload: dict[str, Any],
        token: CancellationToken,
    ) -> None:
        url = str(payload.get("url"))
        use_sniffer = bool(payload.get("use_sniffer", False))
        format_spec = str(payload.get("format_spec", "bestvideo+bestaudio/best"))
        base_target_dir = Path(payload.get("target_dir", self.organizer.base_dir))

        try:
            self.job_queue.start(job_id)
            self.job_queue.update_progress(job_id, 0.05, "Preparing media download...")

            is_hongguo = bool(payload.get("is_hongguo") or HongguoExtractor.is_hongguo_url(url))

            if is_hongguo:
                series_id = str(payload.get("series_id") or HongguoExtractor.parse_series_id(url) or "")
                vid = str(payload.get("vid") or "")
                if not vid and url:
                    _, parsed_vid = HongguoExtractor.parse_url(url)
                    if parsed_vid:
                        vid = parsed_vid

                episode_num = int(payload.get("episode_num") or 1)
                series_name = str(payload.get("series_name") or "")

                # Auto-resolve series_name or episode_num if missing or generic
                if not series_name or series_name == "Hongguo Drama" or (vid and episode_num == 1):
                    try:
                        drama_info = HongguoExtractor.get_drama_info(series_id or url)
                        if drama_info.series_name and (not series_name or series_name == "Hongguo Drama"):
                            series_name = drama_info.series_name
                        if vid and episode_num == 1:
                            for ep in drama_info.episodes:
                                if ep.vid == vid:
                                    episode_num = ep.episode_num
                                    break
                    except Exception as e:
                        logger.warning("Could not auto-resolve drama metadata for %s: %s", series_id, e)

                if not series_name:
                    series_name = "Hongguo Drama"

                generate_srt = bool(payload.get("generate_srt", True))

                # Acquire network lock only during stream extraction and file download
                with self._network_lock_scope(token):
                    self.job_queue.update_progress(job_id, 0.15, f"Resolving Hongguo stream for Ep {episode_num}...")
                    stream_info = HongguoExtractor.get_episode_stream(
                        series_id=series_id,
                        vid=vid if vid else None,
                        episode_num=episode_num,
                    )
                    if stream_info.series_name and (not series_name or series_name == "Hongguo Drama"):
                        series_name = stream_info.series_name

                    title = payload.get("title")
                    if not title or title.startswith("Hongguo Drama") or ("第1集" in title and episode_num > 1):
                        title = f"{series_name} 第{episode_num}集"

                    platform = "Hongguo"
                    creator = series_name

                    dest_dir = base_target_dir / "ShortDrama" / sanitize_filename(series_name)
                    dest_dir.mkdir(parents=True, exist_ok=True)
                    target_file = dest_dir / f"Ep{episode_num:02d}_{sanitize_filename(title)}.mp4"

                    def on_hg_progress(p: float, msg: str) -> None:
                        scaled = 0.15 + (p * 0.60)
                        self.job_queue.update_progress(job_id, scaled, msg)

                    final_file = HongguoExtractor.download_episode(
                        stream_info=stream_info,
                        dest_path=target_file,
                        progress_cb=on_hg_progress,
                        token=token,
                    )

                # Subtitle generation outside network lock so other downloads are never blocked
                srt_path: Path | None = None
                if generate_srt:
                    def on_srt_progress(p: float, msg: str) -> None:
                        scaled = 0.75 + (p * 0.20)
                        self.job_queue.update_progress(job_id, scaled, msg)

                    try:
                        srt_path = HongguoExtractor.generate_srt(
                            video_path=final_file,
                            language="zh",
                            progress_cb=on_srt_progress,
                            token=token,
                        )
                    except Exception as srt_err:
                        logger.warning("Subtitle generation failed for %s: %s", final_file, srt_err)

                # Save companion .meta.json for actor & character voice separation in AI Studio
                chars_data = payload.get("characters") or getattr(stream_info, "characters", []) or []
                meta_json_path = final_file.with_suffix(".meta.json")
                try:
                    with open(meta_json_path, "w", encoding="utf-8") as mf:
                        json.dump(
                            {
                                "title": title,
                                "series_name": series_name,
                                "series_id": series_id,
                                "episode_num": episode_num,
                                "url": url,
                                "characters": chars_data,
                            },
                            mf,
                            indent=2,
                            ensure_ascii=False,
                        )
                except Exception as meta_err:
                    logger.warning("Could not write companion meta.json for %s: %s", final_file, meta_err)

                today_str = datetime.now(UTC).strftime("%Y-%m-%d")
                file_size = final_file.stat().st_size if final_file.exists() else 0
                media_item = MediaItem(
                    id=f"media-{job_id}",
                    title=title,
                    platform=platform,
                    creator=creator,
                    date=today_str,
                    file_path=str(final_file),
                    file_size_bytes=file_size,
                    source_url=url,
                    processing_status="downloaded",
                )
                self.organizer.register_item(media_item)

                self.job_queue.complete(
                    job_id,
                    {
                        "file_path": str(final_file),
                        "srt_path": str(srt_path) if srt_path else None,
                        "title": title,
                        "platform": platform,
                        "file_size": file_size,
                    },
                )
                return

            target_url = url
            title = "Untitled Video"
            platform = "Generic"
            creator = "Unknown"

            # Check if sniffer is needed or requested (e.g. Douyin / TikTok)
            if use_sniffer or any(k in url.lower() for k in ("douyin", "iesdouyin")):
                self.job_queue.update_progress(job_id, 0.10, "Sniffing stream with Playwright subprocess...")
                sniffed = PlaywrightScraper.sniff_stream(url, timeout_sec=25, token=token)
                if sniffed.get("status") == "success" and sniffed.get("stream_url"):
                    target_url = str(sniffed["stream_url"])
                    title = str(sniffed.get("title", title))
                    platform = str(sniffed.get("platform", platform))

            # Extract info from stream
            try:
                info = self.engine.extract_info(target_url, token=token)
                title = info.get("title", title)
                creator = info.get("creator", creator)
                platform = info.get("platform", platform)
            except Exception:
                pass

            # Organize destination folder: Platform / Creator / Date
            today_str = datetime.now(UTC).strftime("%Y-%m-%d")
            if base_target_dir != self.organizer.base_dir:
                dest_dir = base_target_dir / platform / creator / today_str
                dest_dir.mkdir(parents=True, exist_ok=True)
            else:
                dest_dir = self.organizer.get_destination_dir(platform, creator, today_str)

            def on_progress(p: float, msg: str) -> None:
                # Scale progress between 10% and 95%
                scaled = 0.10 + (p * 0.85)
                self.job_queue.update_progress(job_id, scaled, msg)

            # Execute download with best video + best audio merged within network lock
            with self._network_lock_scope(token):
                final_file = self.engine.download(
                    url=target_url,
                    dest_dir=dest_dir,
                    format_spec=format_spec,
                    progress_cb=on_progress,
                    token=token,
                )

            # Register in Library catalog
            file_size = final_file.stat().st_size if final_file.exists() else 0
            media_item = MediaItem(
                id=f"media-{job_id}",
                title=title,
                platform=platform,
                creator=creator,
                date=today_str,
                file_path=str(final_file),
                file_size_bytes=file_size,
                source_url=url,
                processing_status="downloaded",
            )
            self.organizer.register_item(media_item)

            # Complete job
            self.job_queue.complete(
                job_id,
                {
                    "file_path": str(final_file),
                    "title": title,
                    "platform": platform,
                    "file_size": file_size,
                },
            )

        except CancelledError:
            logger.info("Download job %s was cancelled.", job_id)
            self.job_queue.cancel(job_id)
        except Exception as e:
            logger.error("Download job %s failed: %s", job_id, e)
            self.job_queue.fail(job_id, str(e))
        finally:
            with self._lock:
                self._tokens.pop(job_id, None)

    def shutdown(self) -> None:
        """Shutdown thread pool executor."""
        with self._lock:
            for token in self._tokens.values():
                token.cancel()
        self._executor.shutdown(wait=True, cancel_futures=True)

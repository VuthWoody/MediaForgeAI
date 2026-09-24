"""Hongguo Short Drama (hongguoduanju.com) extractor and subtitle generator."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import tempfile
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, NetworkError

logger = logging.getLogger(__name__)

HONGGUO_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    "Referer": "https://hongguoduanju.com/",
}


@dataclass
class HongguoEpisodeItem:
    """Metadata for an episode in a Hongguo drama."""

    episode_num: int
    vid: str
    url: str
    title: str
    accessible: bool = True


@dataclass
class HongguoDramaInfo:
    """Metadata for a complete Hongguo drama series."""

    series_id: str
    series_name: str
    series_cover: str
    series_intro: str
    episode_cnt: int
    accessible_episode_cnt: int
    episodes: list[HongguoEpisodeItem] = field(default_factory=list)
    characters: list[dict[str, str]] = field(default_factory=list)


@dataclass
class HongguoEpisodeStream:
    """Direct video stream details for a Hongguo episode."""

    episode_num: int
    title: str
    stream_url: str
    duration: float
    width: int
    height: int
    series_name: str = ""
    poster_url: str = ""
    headers: dict[str, str] = field(default_factory=lambda: dict(HONGGUO_HEADERS))
    characters: list[dict[str, str]] = field(default_factory=list)


def format_srt_timestamp(seconds: float) -> str:
    """Convert float seconds to SRT timestamp format: HH:MM:SS,mmm."""
    if seconds < 0:
        seconds = 0.0
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        seconds += 1
        millis = 0
    total_secs = int(seconds)
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


class HongguoExtractor:
    """Extractor for Hongguo Duanju (https://hongguoduanju.com/) short dramas."""

    BASE_URL: str = "https://hongguoduanju.com"

    @classmethod
    def is_hongguo_url(cls, url: str) -> bool:
        """Check if a URL belongs to hongguoduanju.com."""
        if not url:
            return False
        return "hongguoduanju.com" in url.lower()

    @classmethod
    def parse_series_id(cls, url_or_id: str) -> str | None:
        """Extract series_id from a URL or raw ID string."""
        raw = url_or_id.strip()
        if raw.isdigit() and len(raw) >= 15:
            return raw

        # Query param ?series_id=...
        m_query = re.search(r"series_id=(\d+)", raw)
        if m_query:
            return m_query.group(1)

        # /player/{series_id}
        m_player = re.search(r"/player/(\d+)", raw)
        if m_player:
            return m_player.group(1)

        # /detail/(\d+)
        m_detail = re.search(r"/detail/(\d+)", raw)
        if m_detail:
            return m_detail.group(1)

        return None

    @classmethod
    def parse_url(cls, url: str) -> tuple[str | None, str | None]:
        """Extract (series_id, vid) from a Hongguo URL if present."""
        if not url:
            return None, None
        series_id = cls.parse_series_id(url)
        m_vid = re.search(r"/player/\d+/(\d+)", url)
        vid = m_vid.group(1) if m_vid else None
        return series_id, vid

    @classmethod
    def parse_episode_range(cls, range_str: str, max_episodes: int) -> list[int]:
        """Parse episode selection string (e.g. 'all', '1-5', '1, 3, 5-8', '2') into sorted unique list.

        Args:
            range_str: User input range specifier.
            max_episodes: Maximum episode number available.

        Returns:
            Sorted list of 1-based episode numbers.
        """
        raw = range_str.strip().lower()
        if not raw or raw in ("all", "*"):
            return list(range(1, max_episodes + 1))

        episodes: set[int] = set()
        parts = [p.strip() for p in raw.split(",") if p.strip()]

        for part in parts:
            if "-" in part:
                sub_parts = part.split("-", 1)
                try:
                    start = int(sub_parts[0].strip())
                    end = int(sub_parts[1].strip())
                    if start <= end:
                        for ep in range(start, end + 1):
                            if 1 <= ep <= max_episodes:
                                episodes.add(ep)
                except ValueError:
                    continue
            else:
                try:
                    ep = int(part)
                    if 1 <= ep <= max_episodes:
                        episodes.add(ep)
                except ValueError:
                    continue

        return sorted(episodes)

    @classmethod
    def search_dramas(cls, keyword: str) -> list[dict[str, Any]]:
        """Search dramas by keyword on hongguoduanju.com."""
        encoded = urllib.parse.quote(keyword.strip())
        search_url = f"{cls.BASE_URL}/search/{encoded}"

        try:
            req = urllib.request.Request(search_url, headers=HONGGUO_HEADERS)
            html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        except Exception as e:
            raise NetworkError(f"Failed to connect to Hongguo search: {e}") from e

        m = re.search(r"_ROUTER_DATA\s*=\s*(\{.*?\});", html)
        if not m:
            return []

        try:
            data = json.loads(m.group(1))
            loader = data.get("loaderData", {})
            page_data = loader.get("search_(keyword)/page") or loader.get("search_page") or {}
            search_list = page_data.get("searchList", [])
        except Exception as e:
            logger.warning("Error parsing Hongguo search JSON: %s", e)
            return []

        results: list[dict[str, Any]] = []
        for item in search_list:
            series_id = str(item.get("keyword") or item.get("series_id") or "")
            name = str(item.get("name") or item.get("series_name") or "")
            if series_id and name:
                results.append(
                    {
                        "series_id": series_id,
                        "title": name,
                        "url": f"{cls.BASE_URL}/player/{series_id}",
                        "cover": item.get("cover_url", ""),
                    }
                )
        return results

    @classmethod
    def get_drama_info(cls, url_or_id: str) -> HongguoDramaInfo:
        """Fetch full drama metadata, total episode count, and episode listing."""
        series_id = cls.parse_series_id(url_or_id)
        if not series_id:
            # If not a URL/ID, treat as search query and pick first result
            search_res = cls.search_dramas(url_or_id)
            if not search_res:
                raise NetworkError(f"Could not find drama matching: {url_or_id}")
            series_id = search_res[0]["series_id"]

        player_url = f"{cls.BASE_URL}/player/{series_id}"
        try:
            req = urllib.request.Request(player_url, headers=HONGGUO_HEADERS)
            html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        except Exception as e:
            raise NetworkError(f"Failed to fetch Hongguo drama page: {e}") from e

        m = re.search(r"_ROUTER_DATA\s*=\s*(\{.*?\});", html)
        if not m:
            raise NetworkError("Could not extract router data from Hongguo player page.")

        try:
            data = json.loads(m.group(1))
            loader = data.get("loaderData", {})
            page_data = loader.get("player_(series_id)/page", {})
            series_detail = page_data.get("seriesDetail", {})
        except Exception as e:
            raise NetworkError(f"Failed to parse Hongguo drama metadata: {e}") from e

        series_name = series_detail.get("series_name") or f"Hongguo_Series_{series_id}"
        series_cover = series_detail.get("series_cover") or ""
        series_intro = series_detail.get("series_intro") or ""
        episode_cnt = int(series_detail.get("episode_cnt") or 0)
        accessible_cnt = int(series_detail.get("accessible_episode_cnt") or 3)
        vid_list: list[str] = series_detail.get("vid_list") or []

        if not episode_cnt:
            episode_cnt = len(vid_list) if vid_list else accessible_cnt

        episodes: list[HongguoEpisodeItem] = []
        for i in range(episode_cnt):
            ep_num = i + 1
            vid = vid_list[i] if i < len(vid_list) else ""
            if ep_num == 1:
                ep_url = f"{cls.BASE_URL}/player/{series_id}"
            else:
                ep_url = f"{cls.BASE_URL}/player/{series_id}/{vid}" if vid else f"{cls.BASE_URL}/player/{series_id}"

            is_accessible = ep_num <= accessible_cnt
            episodes.append(
                HongguoEpisodeItem(
                    episode_num=ep_num,
                    vid=vid,
                    url=ep_url,
                    title=f"{series_name} 第{ep_num}集",
                    accessible=is_accessible,
                )
            )

        raw_celeb = series_detail.get("celebrities") or page_data.get("celebrities")
        celebrities = raw_celeb if isinstance(raw_celeb, list) else []
        characters: list[dict[str, str]] = []
        for c in celebrities:
            if isinstance(c, dict):
                actor = str(c.get("nickname") or c.get("name") or "").strip()
                sub = str(c.get("sub_title") or c.get("role_name") or "").strip()
                char = re.sub(r"^[饰\:\s]+", "", sub).strip()
                if not char:
                    char = actor
                if actor or char:
                    characters.append(
                        {
                            "actor": actor,
                            "character": char,
                            "display": f"{char} ({actor})" if actor and char != actor else (char or actor),
                            "sub_title": sub,
                        }
                    )

        return HongguoDramaInfo(
            series_id=series_id,
            series_name=series_name,
            series_cover=series_cover,
            series_intro=series_intro,
            episode_cnt=episode_cnt,
            accessible_episode_cnt=accessible_cnt,
            episodes=episodes,
            characters=characters,
        )

    @classmethod
    def extract_characters_from_url(cls, url_or_id: str) -> list[dict[str, str]]:
        """Extract actor and character name list directly from a movie/drama URL or series ID."""
        try:
            info = cls.get_drama_info(url_or_id)
            return info.characters
        except Exception as e:
            logger.warning("Could not extract characters from %s: %s", url_or_id, e)
            return []

    @classmethod
    def get_episode_stream(
        cls,
        series_id: str,
        vid: str | None = None,
        episode_num: int = 1,
    ) -> HongguoEpisodeStream:
        """Obtain direct high-speed MP4 download URL for an episode."""
        if episode_num == 1 or not vid:
            ep_url = f"{cls.BASE_URL}/player/{series_id}"
        else:
            ep_url = f"{cls.BASE_URL}/player/{series_id}/{vid}"

        try:
            req = urllib.request.Request(ep_url, headers=HONGGUO_HEADERS)
            html = urllib.request.urlopen(req, timeout=15).read().decode("utf-8")
        except Exception as e:
            raise NetworkError(f"Failed to fetch episode {episode_num} page: {e}") from e

        # Extract main_url from _ROUTER_DATA
        m = re.search(r"_ROUTER_DATA\s*=\s*(\{.*?\});", html)
        stream_url = ""
        duration = 0.0
        width = 1280
        height = 720
        poster_url = ""
        title = f"Episode {episode_num}"
        series_name = ""

        if m:
            try:
                data = json.loads(m.group(1))
                loader = data.get("loaderData", {})
                page_data = (
                    loader.get("player_(series_id)/(vid)/page")
                    or loader.get("player_(series_id)/page")
                    or {}
                )
                vinfo = page_data.get("video_player_info") or {}
                stream_url = vinfo.get("main_url") or ""
                duration = float(vinfo.get("duration") or 0.0)
                width = int(vinfo.get("width") or 1280)
                height = int(vinfo.get("height") or 720)
                poster_url = vinfo.get("poster_url") or ""
                sdetail = page_data.get("seriesDetail") or {}
                sname = sdetail.get("series_name")
                if sname:
                    series_name = str(sname).strip()
                    title = f"{series_name} 第{episode_num}集"
            except Exception as e:
                logger.warning("Error parsing router data for stream: %s", e)

        # Fallback to application/ld+json VideoObject
        if not stream_url:
            for ld in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
                try:
                    obj = json.loads(ld.group(1))
                    if obj.get("@type") == "VideoObject" and obj.get("contentUrl"):
                        stream_url = obj["contentUrl"]
                        title = obj.get("name") or title
                        poster_url = obj.get("image") or poster_url
                        break
                except Exception:
                    pass

        if not stream_url:
            raise NetworkError(
                f"Episode {episode_num} stream not available on web (requires app access or is unavailable)."
            )

        raw_celeb = (
            (sdetail.get("celebrities") if "sdetail" in locals() and sdetail else None)
            or (page_data.get("celebrities") if "page_data" in locals() and page_data else None)
        )
        celebrities = raw_celeb if isinstance(raw_celeb, list) else []
        characters: list[dict[str, str]] = []
        for c in celebrities:
            if isinstance(c, dict):
                actor = str(c.get("nickname") or c.get("name") or "").strip()
                sub = str(c.get("sub_title") or c.get("role_name") or "").strip()
                char = re.sub(r"^[饰\:\s]+", "", sub).strip()
                if not char:
                    char = actor
                if actor or char:
                    characters.append(
                        {
                            "actor": actor,
                            "character": char,
                            "display": f"{char} ({actor})" if actor and char != actor else (char or actor),
                            "sub_title": sub,
                        }
                    )

        return HongguoEpisodeStream(
            episode_num=episode_num,
            title=title,
            stream_url=stream_url,
            duration=duration,
            width=width,
            height=height,
            series_name=series_name,
            poster_url=poster_url,
            headers=dict(HONGGUO_HEADERS),
            characters=characters,
        )

    @classmethod
    def download_episode(
        cls,
        stream_info: HongguoEpisodeStream,
        dest_path: Path | str,
        progress_cb: Callable[[float, str], None] | None = None,
        token: CancellationToken | None = None,
    ) -> Path:
        """Download episode MP4 stream directly to destination path."""
        if token is not None:
            token.throw_if_cancelled()

        target = Path(dest_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        req = urllib.request.Request(stream_info.stream_url, headers=stream_info.headers)

        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get("content-length") or 0)
                downloaded = 0
                chunk_size = 1024 * 128  # 128 KB chunks

                with open(target, "wb") as f:
                    while True:
                        if token is not None and token.is_cancelled:
                            raise CancelledError("Download cancelled by user.")

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded += len(chunk)

                        if progress_cb is not None:
                            pct = (downloaded / total_size) if total_size > 0 else 0.5
                            speed_mb = downloaded / (1024 * 1024)
                            progress_cb(min(0.95, pct), f"Downloading {speed_mb:.1f} MB...")

            if progress_cb is not None:
                progress_cb(1.0, "Video download complete.")

            return target

        except Exception as e:
            if isinstance(e, CancelledError):
                if target.exists():
                    target.unlink(missing_ok=True)
                raise
            raise NetworkError(f"Failed to download episode video stream: {e}") from e

    @classmethod
    def generate_srt(
        cls,
        video_path: Path | str,
        output_srt_path: Path | str | None = None,
        language: str = "zh",
        progress_cb: Callable[[float, str], None] | None = None,
        token: CancellationToken | None = None,
    ) -> Path:
        """Generate timestamped .srt subtitles from a video file using faster-whisper.

        Args:
            video_path: Path to the downloaded video file.
            output_srt_path: Optional path for the .srt file (defaults to video_path with .srt extension).
            language: Spoken language code ('zh' for Chinese).
            progress_cb: Progress callback.
            token: Cancellation token.

        Returns:
            Path to the written .srt subtitle file.
        """
        if token is not None:
            token.throw_if_cancelled()

        v_path = Path(video_path)
        if not v_path.exists():
            raise FileNotFoundError(f"Video file not found: {v_path}")

        srt_out = Path(output_srt_path) if output_srt_path else v_path.with_suffix(".srt")
        srt_out.parent.mkdir(parents=True, exist_ok=True)

        if progress_cb is not None:
            progress_cb(0.1, "Extracting audio for subtitle generation...")

        # Extract 16kHz mono audio to temporary wav file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_audio:
            tmp_audio_path = Path(tmp_audio.name)

        try:
            extract_cmd = [
                "ffmpeg",
                "-y",
                "-i",
                str(v_path),
                "-vn",
                "-ar",
                "16000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                str(tmp_audio_path),
            ]
            subprocess.run(extract_cmd, check=True, capture_output=True)

            if token is not None:
                token.throw_if_cancelled()

            if progress_cb is not None:
                progress_cb(0.3, "Transcribing dialogue with faster-whisper...")

            # Transcribe with faster-whisper
            try:
                from faster_whisper import WhisperModel
            except ImportError as err:
                raise RuntimeError(
                    "faster-whisper is not installed. Install via `pip install faster-whisper`"
                ) from err

            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _info = model.transcribe(
                str(tmp_audio_path),
                language=language,
                beam_size=5,
            )

            srt_blocks: list[str] = []
            for i, segment in enumerate(segments, start=1):
                if token is not None and token.is_cancelled:
                    raise CancelledError("Subtitle generation cancelled.")

                start_str = format_srt_timestamp(segment.start)
                end_str = format_srt_timestamp(segment.end)
                text = segment.text.strip()
                srt_blocks.append(f"{i}\n{start_str} --> {end_str}\n{text}\n")

            with open(srt_out, "w", encoding="utf-8") as f:
                f.write("\n".join(srt_blocks))

            if progress_cb is not None:
                progress_cb(1.0, f"Subtitles generated successfully ({len(srt_blocks)} entries).")

            return srt_out

        finally:
            if tmp_audio_path.exists():
                try:
                    tmp_audio_path.unlink()
                except Exception:
                    pass

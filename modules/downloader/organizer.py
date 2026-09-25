"""Media organizer for structured asset storage by platform, creator, and date."""

from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Sanitize string for Windows filesystem safety."""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name).strip()
    return cleaned[:120] if cleaned else "Untitled"


@dataclass
class MediaItem:
    """Represents a downloaded or imported media asset in the Media Library."""

    id: str
    title: str
    platform: str
    creator: str
    date: str
    file_path: str
    thumbnail_path: str | None = None
    duration: float = 0.0
    resolution: str = "1080p"
    file_size_bytes: int = 0
    source_url: str = ""
    processing_status: str = "downloaded"
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class MediaOrganizer:
    """Organizes media assets into structured directories and maintains the catalog database."""

    def __init__(self, base_dir: str | Path | None = None, db_path: str | Path | None = None) -> None:
        if base_dir:
            self.base_dir = Path(base_dir)
            self.base_dir.mkdir(parents=True, exist_ok=True)
        else:
            default_videos = Path.home() / "Videos" / "MediaForge Downloads"
            try:
                default_videos.mkdir(parents=True, exist_ok=True)
                self.base_dir = default_videos
            except OSError:
                self.base_dir = Path.home() / "AppData" / "Local" / "MediaForgeAI" / "downloads"
                self.base_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = (
            Path(db_path)
            if db_path
            else Path.home() / "AppData" / "Local" / "MediaForgeAI" / "library.db"
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._connect_and_init()

    def _connect_and_init(self) -> None:
        with self._lock:
            try:
                self._conn = sqlite3.connect(
                    str(self.db_path),
                    check_same_thread=False,
                    isolation_level=None,
                )
                self._init_db_locked()
            except sqlite3.DatabaseError as e:
                logger.warning("Corrupted SQLite database detected at %s (%s). Recreating clean database.", self.db_path, e)
                self._recover_db_locked()
        self.reconcile_short_dramas()

    def _recover_db_locked(self) -> None:
        try:
            if hasattr(self, "_conn") and self._conn:
                self._conn.close()
        except Exception:
            pass

        timestamp = int(time.time())
        bak_file = self.db_path.with_name(f"{self.db_path.stem}.corrupted_{timestamp}.bak")
        try:
            if self.db_path.exists():
                self.db_path.rename(bak_file)
            for aux in [
                self.db_path.with_name(self.db_path.name + "-wal"),
                self.db_path.with_name(self.db_path.name + "-shm"),
            ]:
                if aux.exists():
                    aux.unlink()
        except Exception as ren_err:
            logger.error("Failed to backup corrupted database file: %s", ren_err)

        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._init_db_locked()

    def _init_db_locked(self) -> None:
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS library (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                platform TEXT NOT NULL,
                creator TEXT NOT NULL,
                date TEXT NOT NULL,
                file_path TEXT NOT NULL,
                thumbnail_path TEXT,
                duration REAL NOT NULL,
                resolution TEXT NOT NULL,
                file_size_bytes INTEGER NOT NULL,
                source_url TEXT,
                processing_status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_lib_platform ON library(platform);")
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_lib_creator ON library(creator);")

    def reconcile_short_dramas(self) -> None:
        """Reconcile short dramas stored in generic folders into movie-specific folders and sync library catalog."""
        with self._lock:
            try:
                short_drama_base = self.base_dir / "ShortDrama"
                if short_drama_base.exists():
                    hongguo_drama_dir = short_drama_base / "Hongguo Drama"
                    if hongguo_drama_dir.exists():
                        for item in list(hongguo_drama_dir.glob("*")):
                            if not item.is_file():
                                continue
                            # Filename pattern: Ep01_我的婆婆，我罩着 第1集.mp4 or .srt
                            m = re.match(r"^Ep\d+_(.+?)(?:\s*第\d+集)?\.(mp4|srt)$", item.name)
                            drama_name = None
                            if m:
                                drama_name = m.group(1).strip()
                            elif "_" in item.stem:
                                drama_name = item.stem.split("_", 1)[1].strip()

                            if drama_name and drama_name != "Hongguo Drama":
                                dest_dir = short_drama_base / sanitize_filename(drama_name)
                                dest_dir.mkdir(parents=True, exist_ok=True)
                                dest_file = dest_dir / item.name
                                if not dest_file.exists():
                                    try:
                                        item.rename(dest_file)
                                    except Exception as move_err:
                                        logger.warning("Could not move %s to %s: %s", item, dest_file, move_err)
                                else:
                                    try:
                                        if item.stat().st_size <= dest_file.stat().st_size:
                                            item.unlink()
                                    except Exception:
                                        pass

                        try:
                            if not any(hongguo_drama_dir.iterdir()):
                                hongguo_drama_dir.rmdir()
                        except Exception:
                            pass

                # Update database records:
                rows = self._conn.execute(
                    "SELECT id, title, creator, file_path FROM library WHERE creator = 'Hongguo Drama' OR file_path LIKE '%Hongguo Drama%';"
                ).fetchall()

                for row_id, title, _creator, file_path in rows:
                    p = Path(file_path)
                    drama_name = re.sub(r"\s*第\d+集$", "", title).strip()
                    if not drama_name or drama_name == "Hongguo Drama":
                        m = re.match(r"^Ep\d+_(.+?)(?:\s*第\d+集)?\.(mp4|srt)$", p.name)
                        if m:
                            drama_name = m.group(1).strip()
                    if not drama_name:
                        drama_name = "Hongguo Drama"

                    new_path = self.base_dir / "ShortDrama" / sanitize_filename(drama_name) / p.name
                    target_path_str = str(new_path) if new_path.exists() else str(p)

                    self._conn.execute(
                        """
                        UPDATE library
                        SET creator = ?, file_path = ?
                        WHERE id = ?;
                        """,
                        (drama_name, target_path_str, row_id),
                    )

                # Deduplicate identical items in library
                self._conn.execute(
                    """
                    DELETE FROM library
                    WHERE rowid NOT IN (
                        SELECT MIN(rowid)
                        FROM library
                        GROUP BY file_path
                    );
                    """
                )
            except Exception as e:
                logger.warning("Error during short drama reconciliation: %s", e)

    def get_destination_dir(self, platform: str, creator: str, date_str: str | None = None) -> Path:
        """Construct directory path: Base -> Platform -> Creator -> Date."""
        clean_platform = sanitize_filename(platform or "Generic")
        clean_creator = sanitize_filename(creator or "Unknown Creator")
        date_folder = date_str or datetime.now(UTC).strftime("%Y-%m-%d")

        dest = self.base_dir / clean_platform / clean_creator / date_folder
        dest.mkdir(parents=True, exist_ok=True)
        return dest

    def get_target_filepath(
        self,
        platform: str,
        creator: str,
        title: str,
        ext: str = "mp4",
        date_str: str | None = None,
    ) -> Path:
        """Generate full organized destination file path."""
        target_dir = self.get_destination_dir(platform, creator, date_str)
        clean_title = sanitize_filename(title)
        extension = ext.lstrip(".")
        return target_dir / f"{clean_title}.{extension}"

    def register_item(self, item: MediaItem) -> None:
        """Register or update a media item in the library catalog."""
        now = item.created_at or datetime.now(UTC).isoformat()
        sql = """
            INSERT OR REPLACE INTO library (
                id, title, platform, creator, date, file_path, thumbnail_path,
                duration, resolution, file_size_bytes, source_url,
                processing_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """
        vals = (
            item.id,
            item.title,
            item.platform,
            item.creator,
            item.date,
            str(item.file_path),
            item.thumbnail_path,
            item.duration,
            item.resolution,
            item.file_size_bytes,
            item.source_url,
            item.processing_status,
            now,
        )
        with self._lock:
            try:
                self._conn.execute(sql, vals)
            except sqlite3.DatabaseError as e:
                logger.warning("Database error in register_item: %s. Attempting self-healing recovery.", e)
                self._recover_db_locked()
                try:
                    self._conn.execute(sql, vals)
                except Exception as retry_err:
                    logger.error("Failed to register item after recovery: %s", retry_err)

    def organize_and_catalog(
        self,
        src_file: Path | str,
        platform: str,
        creator: str,
        title: str,
        video_date: str | None = None,
        source_url: str = "",
        duration: float = 0.0,
        resolution: str = "1080p",
    ) -> MediaItem:
        """Move or copy source file into organized hierarchy and record in catalog."""
        src = Path(src_file)
        dest_file = self.get_target_filepath(
            platform=platform,
            creator=creator,
            title=title,
            ext=src.suffix.lstrip(".") or "mp4",
            date_str=video_date,
        )
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        if src.exists() and src.resolve() != dest_file.resolve():
            import shutil
            shutil.copy2(src, dest_file)

        size_bytes = dest_file.stat().st_size if dest_file.exists() else 0
        import uuid
        item = MediaItem(
            id=f"media-{uuid.uuid4().hex[:12]}",
            title=title,
            platform=platform,
            creator=creator,
            date=video_date or datetime.now(UTC).strftime("%Y-%m-%d"),
            file_path=str(dest_file),
            duration=duration,
            resolution=resolution,
            file_size_bytes=size_bytes,
            source_url=source_url,
            processing_status="downloaded",
        )
        self.register_item(item)
        return item

    def list_media(
        self,
        platform: str | None = None,
        search_query: str | None = None,
        limit: int = 200,
    ) -> list[MediaItem]:
        """Convenience alias for list_items."""
        return self.list_items(platform=platform, search_query=search_query, limit=limit)

    def list_items(
        self,
        platform: str | None = None,
        search_query: str | None = None,
        limit: int = 200,
    ) -> list[MediaItem]:
        """List library items sorted by Platform -> Creator -> Date DESC."""
        self.reconcile_short_dramas()
        query = "SELECT id, title, platform, creator, date, file_path, thumbnail_path, duration, resolution, file_size_bytes, source_url, processing_status, created_at FROM library"
        clauses: list[str] = []
        params: list[Any] = []

        if platform:
            clauses.append("platform = ?")
            params.append(platform)

        if search_query:
            clauses.append("(title LIKE ? OR creator LIKE ?)")
            params.append(f"%{search_query}%")
            params.append(f"%{search_query}%")

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY platform ASC, creator ASC, date DESC, created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            try:
                cursor = self._conn.cursor()
                cursor.execute(query, tuple(params))
                rows = cursor.fetchall()
                return [self._row_to_item(r) for r in rows]
            except sqlite3.DatabaseError as e:
                logger.warning("Database error in list_items: %s. Attempting self-healing recovery.", e)
                self._recover_db_locked()
                return []

    def _row_to_item(self, row: tuple[Any, ...]) -> MediaItem:
        return MediaItem(
            id=str(row[0]),
            title=str(row[1]),
            platform=str(row[2]),
            creator=str(row[3]),
            date=str(row[4]),
            file_path=str(row[5]),
            thumbnail_path=row[6],
            duration=float(row[7]),
            resolution=str(row[8]),
            file_size_bytes=int(row[9]),
            source_url=str(row[10] or ""),
            processing_status=str(row[11]),
            created_at=str(row[12]),
        )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

"""SQLite-backed persistent job queue with WAL mode and progress throttling."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from core.event_bus import get_event_bus

JobKind = Literal[
    "download",
    "transcribe",
    "separate",
    "translate",
    "tts",
    "align",
    "mix",
    "render",
]

JobStatus = Literal[
    "queued",
    "running",
    "completed",
    "failed",
    "cancelled",
]


@dataclass
class Job:
    """Represents a discrete unit of pipeline or media processing work."""

    id: str
    kind: JobKind
    payload: dict[str, Any]
    status: JobStatus
    progress: float
    created_at: datetime
    updated_at: datetime
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert job representation to dict."""
        return {
            "id": self.id,
            "kind": self.kind,
            "payload": self.payload,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
        }


class JobQueue:
    """Persistent job queue backed by SQLite in WAL mode."""

    CURRENT_SCHEMA_VERSION = 1
    MIN_PROGRESS_INTERVAL_SEC = 0.25  # Throttled at <= 4 Hz

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._last_progress_write: dict[str, float] = {}

        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode
        )
        self._init_db()

    def _init_db(self) -> None:
        with self._lock:
            cursor = self._conn.cursor()
            if self.db_path != ":memory:":
                cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA synchronous=NORMAL;")

            # Migrations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                );
            """)

            # Check applied migrations
            cursor.execute("SELECT MAX(version) FROM schema_migrations;")
            row = cursor.fetchone()
            current_version = row[0] if (row and row[0] is not None) else 0

            if current_version < 1:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        payload TEXT NOT NULL,
                        status TEXT NOT NULL,
                        progress REAL NOT NULL DEFAULT 0.0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        error TEXT
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_kind ON jobs(kind);")
                now_iso = datetime.now(UTC).isoformat()
                cursor.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                    (1, now_iso),
                )

            # Crash survival: Mark orphaned "running" jobs as "failed" on launch
            cursor.execute(
                """
                UPDATE jobs
                SET status = 'failed',
                    error = 'Job failed: Unexpected application termination/crash while running',
                    updated_at = ?
                WHERE status = 'running';
                """,
                (datetime.now(UTC).isoformat(),),
            )

    def close(self) -> None:
        """Close database connection."""
        with self._lock:
            self._conn.close()

    def enqueue(
        self,
        kind: JobKind,
        payload: dict[str, Any],
        job_id: str | None = None,
    ) -> Job:
        """Enqueue a new job and emit job_queued signal."""
        jid = job_id or f"job-{uuid.uuid4().hex[:12]}"
        now = datetime.now(UTC)
        now_str = now.isoformat()
        payload_str = json.dumps(payload)

        with self._lock:
            self._conn.execute(
                """
                INSERT INTO jobs (id, kind, payload, status, progress, created_at, updated_at, error)
                VALUES (?, ?, ?, 'queued', 0.0, ?, ?, NULL);
                """,
                (jid, kind, payload_str, now_str, now_str),
            )

        job = Job(
            id=jid,
            kind=kind,
            payload=payload,
            status="queued",
            progress=0.0,
            created_at=now,
            updated_at=now,
            error=None,
        )

        try:
            get_event_bus().job_queued.emit(jid)
        except Exception:
            pass

        return job

    def start(self, job_id: str) -> None:
        """Mark job as running and emit job_started signal."""
        now = datetime.now(UTC).isoformat()
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET status = 'running', updated_at = ?
                WHERE id = ?;
                """,
                (now, job_id),
            )

        try:
            get_event_bus().job_started.emit(job_id)
        except Exception:
            pass

    def update_progress(self, job_id: str, progress: float, message: str = "") -> None:
        """Update job progress throttled at <= 4 Hz, emitting job_progress signal."""
        now_ts = time.monotonic()
        last_write = self._last_progress_write.get(job_id, 0.0)
        should_write_db = (
            (now_ts - last_write >= self.MIN_PROGRESS_INTERVAL_SEC)
            or progress >= 1.0
            or progress <= 0.0
        )

        if should_write_db:
            now_iso = datetime.now(UTC).isoformat()
            with self._lock:
                self._conn.execute(
                    """
                    UPDATE jobs
                    SET progress = ?, updated_at = ?
                    WHERE id = ?;
                    """,
                    (progress, now_iso, job_id),
                )
            self._last_progress_write[job_id] = now_ts

        try:
            get_event_bus().job_progress.emit(job_id, progress, message)
        except Exception:
            pass

    def complete(self, job_id: str, result: dict[str, Any] | None = None) -> None:
        """Mark job completed and emit job_completed signal."""
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET status = 'completed', progress = 1.0, updated_at = ?
                WHERE id = ?;
                """,
                (now_iso, job_id),
            )
        self._last_progress_write.pop(job_id, None)

        try:
            get_event_bus().job_completed.emit(job_id, result or {})
        except Exception:
            pass

    def fail(self, job_id: str, error: str) -> None:
        """Mark job failed and emit job_failed signal."""
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET status = 'failed', error = ?, updated_at = ?
                WHERE id = ?;
                """,
                (error, now_iso, job_id),
            )
        self._last_progress_write.pop(job_id, None)

        try:
            get_event_bus().job_failed.emit(job_id, error)
        except Exception:
            pass

    def cancel(self, job_id: str) -> None:
        """Mark job cancelled and emit job_cancelled signal."""
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            self._conn.execute(
                """
                UPDATE jobs
                SET status = 'cancelled', updated_at = ?
                WHERE id = ?;
                """,
                (now_iso, job_id),
            )
        self._last_progress_write.pop(job_id, None)

        try:
            get_event_bus().job_cancelled.emit(job_id)
        except Exception:
            pass

    def get_job(self, job_id: str) -> Job | None:
        """Fetch a job by ID."""
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT id, kind, payload, status, progress, created_at, updated_at, error
                FROM jobs
                WHERE id = ?;
                """,
                (job_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_job(row)

    def list_jobs(
        self,
        status: JobStatus | None = None,
        kind: JobKind | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """List jobs optionally filtered by status and kind."""
        query = "SELECT id, kind, payload, status, progress, created_at, updated_at, error FROM jobs"
        clauses: list[str] = []
        params: list[Any] = []

        if status:
            clauses.append("status = ?")
            params.append(status)
        if kind:
            clauses.append("kind = ?")
            params.append(kind)

        if clauses:
            query += " WHERE " + " AND ".join(clauses)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self._row_to_job(r) for r in rows]

    def _row_to_job(self, row: tuple[Any, ...]) -> Job:
        jid, kind, payload_str, status, progress, created_str, updated_str, error = row
        return Job(
            id=str(jid),
            kind=kind,
            payload=json.loads(payload_str),
            status=status,
            progress=float(progress),
            created_at=datetime.fromisoformat(created_str),
            updated_at=datetime.fromisoformat(updated_str),
            error=error,
        )

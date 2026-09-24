"""VoxReel SQLite & Vector Storage Layer.

Implements data model & schema matching §9.2 of VOX_engine_Plan.md.
Provides vector storage, centroid computation, cosine similarity math,
and full transactional CRUD for actors, voice profiles, sessions, and audit logs.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np


def vector_to_blob(v: np.ndarray) -> bytes:
    """Convert a numpy 1D float array into raw bytes."""
    arr = np.asarray(v, dtype=np.float32)
    return arr.tobytes()


def blob_to_vector(b: bytes) -> np.ndarray:
    """Convert raw bytes back into a numpy 1D float32 array."""
    if not b:
        return np.zeros(0, dtype=np.float32)
    return np.frombuffer(b, dtype=np.float32).copy()


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two 1D vectors."""
    va = np.asarray(a, dtype=np.float32).flatten()
    vb = np.asarray(b, dtype=np.float32).flatten()
    if va.size == 0 or vb.size == 0 or va.size != vb.size:
        return 0.0
    norm_a = float(np.linalg.norm(va))
    norm_b = float(np.linalg.norm(vb))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def batch_cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Compute cosine similarities between a 1D query vector and a 2D matrix of vectors."""
    q = np.asarray(query, dtype=np.float32).flatten()
    m = np.asarray(matrix, dtype=np.float32)
    if m.ndim == 1:
        m = m.reshape(1, -1)
    if q.size == 0 or m.size == 0:
        return np.zeros(0, dtype=np.float32)
    norm_q = np.linalg.norm(q)
    if norm_q == 0.0:
        return np.zeros(len(m), dtype=np.float32)
    norms_m = np.linalg.norm(m, axis=1)
    norms_m[norms_m == 0.0] = 1e-12
    return (m @ q) / (norms_m * norm_q)


@dataclass
class Actor:
    id: str
    display_name: str
    aliases: list[str] = field(default_factory=list)
    notes: str | None = None
    consent_flag: bool = False
    deleted_at: str | None = None


@dataclass
class VoiceProfile:
    id: str
    actor_id: str
    language: str = "en"
    embedding_model: str = "ecapa-tdnn-voxceleb-v2"
    centroid: np.ndarray | None = None
    ref_count: int = 0
    created_at: str = ""


@dataclass
class ReferenceEmbedding:
    id: str
    voice_profile_id: str
    vector: np.ndarray
    source: str = "enroll_clip"
    session_id: str | None = None
    snr_db: float = 0.0
    duration_sec: float = 0.0
    model_version: str = "ecapa-tdnn-voxceleb-v2"
    created_at: str = ""


@dataclass
class Session:
    id: str
    media_file_id: str | None = None
    language: str = "en"
    num_speakers: int | None = None
    pipeline_ver: str = "1.0.0"
    embedding_model: str = "ecapa-tdnn-voxceleb-v2"
    status: str = "queued"
    created_at: str = ""


class VoxReelDB:
    """SQLite-backed database for VoxReel Actor Voice Registry and processing sessions."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None or str(db_path).strip() == "":
            app_dir = Path.home() / "AppData" / "Local" / "MediaForgeAI"
            app_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = app_dir / "voxreel.db"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_schema()

    def get_connection(self) -> sqlite3.Connection:
        """Create a configured SQLite connection with foreign keys enabled."""
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_schema(self) -> None:
        """Initialize all tables defined in §9.2 SQL Schema."""
        with self.get_connection() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS media_file (
                id              TEXT PRIMARY KEY,
                original_name   TEXT NOT NULL,
                stored_path     TEXT NOT NULL,
                container       TEXT,
                duration_sec    REAL,
                audio_tracks    TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS session (
                id              TEXT PRIMARY KEY,
                media_file_id   TEXT REFERENCES media_file(id),
                language        TEXT,
                num_speakers    INTEGER,
                pipeline_ver    TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                status          TEXT CHECK (status IN ('queued','running','done','failed','needs_review')),
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS actor (
                id              TEXT PRIMARY KEY,
                display_name    TEXT NOT NULL,
                aliases         TEXT DEFAULT '[]',
                notes           TEXT,
                consent_flag    INTEGER NOT NULL DEFAULT 0,
                deleted_at      TEXT
            );

            CREATE TABLE IF NOT EXISTS voice_profile (
                id              TEXT PRIMARY KEY,
                actor_id        TEXT REFERENCES actor(id) ON DELETE CASCADE,
                language        TEXT NOT NULL DEFAULT 'en',
                embedding_model TEXT NOT NULL,
                centroid        BLOB,
                ref_count       INTEGER DEFAULT 0,
                created_at      TEXT DEFAULT (datetime('now')),
                UNIQUE (actor_id, language, embedding_model)
            );

            CREATE TABLE IF NOT EXISTS reference_embedding (
                id              TEXT PRIMARY KEY,
                voice_profile_id TEXT REFERENCES voice_profile(id) ON DELETE CASCADE,
                vector          BLOB NOT NULL,
                source          TEXT CHECK (source IN ('enroll_clip','confirmed_segment')),
                session_id      TEXT REFERENCES session(id),
                snr_db          REAL,
                duration_sec    REAL,
                model_version   TEXT NOT NULL,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS segment (
                id              TEXT PRIMARY KEY,
                session_id      TEXT REFERENCES session(id) ON DELETE CASCADE,
                start_sec       REAL NOT NULL,
                end_sec         REAL NOT NULL,
                cluster_label   TEXT NOT NULL,
                actor_id        TEXT REFERENCES actor(id) ON DELETE SET NULL,
                match_score     REAL,
                match_status    TEXT CHECK (match_status IN ('auto','review','new','manual','rejected')),
                text            TEXT,
                asr_conf        REAL,
                overlap_flag    INTEGER DEFAULT 0,
                corrected_by    TEXT,
                UNIQUE (session_id, start_sec, cluster_label)
            );

            CREATE TABLE IF NOT EXISTS word (
                id              TEXT PRIMARY KEY,
                segment_id      TEXT REFERENCES segment(id) ON DELETE CASCADE,
                start_sec       REAL NOT NULL,
                end_sec         REAL NOT NULL,
                token           TEXT NOT NULL,
                conf            REAL
            );

            CREATE TABLE IF NOT EXISTS cluster_match (
                id              TEXT PRIMARY KEY,
                session_id      TEXT REFERENCES session(id) ON DELETE CASCADE,
                cluster_label   TEXT NOT NULL,
                actor_id        TEXT REFERENCES actor(id) ON DELETE SET NULL,
                score           REAL,
                status          TEXT NOT NULL,
                decided_by      TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                entity      TEXT NOT NULL,
                entity_id   TEXT NOT NULL,
                action      TEXT NOT NULL,
                payload     TEXT,
                user_id     TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_actor_name ON actor(display_name);
            CREATE INDEX IF NOT EXISTS idx_segment_session ON segment(session_id);
            CREATE INDEX IF NOT EXISTS idx_ref_emb_profile ON reference_embedding(voice_profile_id);
            """)

    # -------------------------------------------------------------------------
    # Actor Operations
    # -------------------------------------------------------------------------

    def create_actor(
        self,
        display_name: str,
        aliases: list[str] | None = None,
        notes: str | None = None,
        consent_flag: bool = False,
    ) -> Actor:
        """Create a new registered actor."""
        actor_id = str(uuid.uuid4())
        aliases_list = [a.strip() for a in (aliases or []) if a.strip()]
        aliases_json = json.dumps(aliases_list, ensure_ascii=False)
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO actor (id, display_name, aliases, notes, consent_flag)
                VALUES (?, ?, ?, ?, ?)
                """,
                (actor_id, display_name.strip(), aliases_json, notes, int(consent_flag)),
            )
            self._log_audit(
                conn,
                "actor",
                actor_id,
                "create",
                {"display_name": display_name, "aliases": aliases_list, "consent": consent_flag},
            )
            conn.commit()

        return Actor(
            id=actor_id,
            display_name=display_name.strip(),
            aliases=aliases_list,
            notes=notes,
            consent_flag=consent_flag,
        )

    def get_actor(self, actor_id: str) -> Actor | None:
        """Fetch actor by ID (excluding soft-deleted)."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM actor WHERE id = ? AND deleted_at IS NULL",
                (actor_id,),
            ).fetchone()
            if not row:
                return None
            return Actor(
                id=row["id"],
                display_name=row["display_name"],
                aliases=json.loads(row["aliases"] or "[]"),
                notes=row["notes"],
                consent_flag=bool(row["consent_flag"]),
                deleted_at=row["deleted_at"],
            )

    def get_actor_by_name(self, name: str) -> Actor | None:
        """Fetch actor by exact display name (case-insensitive) or alias."""
        clean_name = name.strip().lower()
        actors = self.list_actors()
        for act in actors:
            if act.display_name.lower() == clean_name:
                return act
            for alias in act.aliases:
                if alias.lower() == clean_name:
                    return act
        return None

    def list_actors(self, include_deleted: bool = False) -> list[Actor]:
        """List all actors."""
        query = "SELECT * FROM actor"
        if not include_deleted:
            query += " WHERE deleted_at IS NULL"
        query += " ORDER BY display_name ASC"

        with self.get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [
                Actor(
                    id=r["id"],
                    display_name=r["display_name"],
                    aliases=json.loads(r["aliases"] or "[]"),
                    notes=r["notes"],
                    consent_flag=bool(r["consent_flag"]),
                    deleted_at=r["deleted_at"],
                )
                for r in rows
            ]

    def search_actors(self, query: str) -> list[Actor]:
        """Search actors by name or alias substring."""
        q = query.strip().lower()
        if not q:
            return self.list_actors()
        all_actors = self.list_actors()
        results: list[Actor] = []
        for a in all_actors:
            if q in a.display_name.lower():
                results.append(a)
                continue
            if any(q in alias.lower() for alias in a.aliases):
                results.append(a)
        return results

    def update_actor(
        self,
        actor_id: str,
        display_name: str | None = None,
        aliases: list[str] | None = None,
        notes: str | None = None,
        consent_flag: bool | None = None,
    ) -> Actor | None:
        """Update actor metadata."""
        act = self.get_actor(actor_id)
        if not act:
            return None

        new_name = display_name.strip() if display_name is not None else act.display_name
        new_aliases = aliases if aliases is not None else act.aliases
        new_notes = notes if notes is not None else act.notes
        new_consent = consent_flag if consent_flag is not None else act.consent_flag

        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE actor
                SET display_name = ?, aliases = ?, notes = ?, consent_flag = ?
                WHERE id = ?
                """,
                (
                    new_name,
                    json.dumps(new_aliases, ensure_ascii=False),
                    new_notes,
                    int(new_consent),
                    actor_id,
                ),
            )
            self._log_audit(
                conn,
                "actor",
                actor_id,
                "update",
                {"display_name": new_name, "aliases": new_aliases, "consent": new_consent},
            )
            conn.commit()

        act.display_name = new_name
        act.aliases = new_aliases
        act.notes = new_notes
        act.consent_flag = new_consent
        return act

    def delete_actor(self, actor_id: str, hard_delete: bool = True) -> bool:
        """Erase actor and all associated biometric vector profiles (GDPR Art. 9)."""
        act = self.get_actor(actor_id)
        if not act:
            return False

        with self.get_connection() as conn:
            if hard_delete:
                # Nullify foreign references in segments and cluster matches
                conn.execute("UPDATE segment SET actor_id = NULL WHERE actor_id = ?", (actor_id,))
                conn.execute("UPDATE cluster_match SET actor_id = NULL WHERE actor_id = ?", (actor_id,))
                # Cascades will delete voice_profile and reference_embedding
                conn.execute("DELETE FROM actor WHERE id = ?", (actor_id,))
            else:
                now_str = datetime.now(UTC).isoformat()
                conn.execute("UPDATE actor SET deleted_at = ? WHERE id = ?", (now_str, actor_id,))

            self._log_audit(
                conn,
                "actor",
                actor_id,
                "delete" if hard_delete else "soft_delete",
                {"hard": hard_delete, "name": act.display_name},
            )
            conn.commit()
        return True

    def merge_actors(self, target_id: str, source_id: str) -> Actor | None:
        """Merge source_id actor into target_id actor.

        Transfers all reference embeddings to target profiles, recalculates centroids,
        repoints session segments/matches to target_id, and purges the source actor.
        """
        target = self.get_actor(target_id)
        source = self.get_actor(source_id)
        if not target or not source or target_id == source_id:
            return None

        # Combine aliases
        combined_aliases = list(dict.fromkeys(target.aliases + [source.display_name] + source.aliases))

        with self.get_connection() as conn:
            # Transfer reference embeddings to target voice profiles
            source_profiles = conn.execute(
                "SELECT * FROM voice_profile WHERE actor_id = ?",
                (source_id,),
            ).fetchall()

            for sp in source_profiles:
                lang = sp["language"]
                model = sp["embedding_model"]
                tp = conn.execute(
                    "SELECT id FROM voice_profile WHERE actor_id = ? AND language = ? AND embedding_model = ?",
                    (target_id, lang, model),
                ).fetchone()

                if not tp:
                    target_profile_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO voice_profile (id, actor_id, language, embedding_model, centroid, ref_count)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (target_profile_id, target_id, lang, model, None, 0),
                    )
                else:
                    target_profile_id = tp["id"]

                # Repoint reference embeddings
                conn.execute(
                    "UPDATE reference_embedding SET voice_profile_id = ? WHERE voice_profile_id = ?",
                    (target_profile_id, sp["id"]),
                )

            # Repoint segments and cluster matches
            conn.execute("UPDATE segment SET actor_id = ? WHERE actor_id = ?", (target_id, source_id))
            conn.execute("UPDATE cluster_match SET actor_id = ? WHERE actor_id = ?", (target_id, source_id))

            # Update target aliases
            conn.execute(
                "UPDATE actor SET aliases = ? WHERE id = ?",
                (json.dumps(combined_aliases, ensure_ascii=False), target_id),
            )

            # Delete source actor (cascades remove source profiles)
            conn.execute("DELETE FROM actor WHERE id = ?", (source_id,))

            self._log_audit(
                conn,
                "actor",
                target_id,
                "merge",
                {"source_id": source_id, "source_name": source.display_name},
            )
            conn.commit()

        # Recalculate centroids for target actor profiles
        with self.get_connection() as conn:
            t_profs = conn.execute(
                "SELECT id FROM voice_profile WHERE actor_id = ?",
                (target_id,),
            ).fetchall()
        for p in t_profs:
            self.update_profile_centroid(p["id"])

        target.aliases = combined_aliases
        return target

    # -------------------------------------------------------------------------
    # Voice Profile & Vector Operations
    # -------------------------------------------------------------------------

    def get_or_create_profile(
        self,
        actor_id: str,
        language: str = "en",
        embedding_model: str = "ecapa-tdnn-voxceleb-v2",
    ) -> VoiceProfile:
        """Get existing voice profile for actor/lang/model or create one."""
        with self.get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM voice_profile
                WHERE actor_id = ? AND language = ? AND embedding_model = ?
                """,
                (actor_id, language, embedding_model),
            ).fetchone()

            if row:
                centroid = blob_to_vector(row["centroid"]) if row["centroid"] else None
                return VoiceProfile(
                    id=row["id"],
                    actor_id=row["actor_id"],
                    language=row["language"],
                    embedding_model=row["embedding_model"],
                    centroid=centroid,
                    ref_count=row["ref_count"],
                    created_at=row["created_at"],
                )

            prof_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO voice_profile (id, actor_id, language, embedding_model, centroid, ref_count)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (prof_id, actor_id, language, embedding_model, None),
            )
            conn.commit()

            return VoiceProfile(
                id=prof_id,
                actor_id=actor_id,
                language=language,
                embedding_model=embedding_model,
                centroid=None,
                ref_count=0,
            )

    def add_reference_embedding(
        self,
        profile_id: str,
        vector: np.ndarray,
        source: str = "enroll_clip",
        session_id: str | None = None,
        snr_db: float = 0.0,
        duration_sec: float = 0.0,
        model_version: str = "ecapa-tdnn-voxceleb-v2",
    ) -> ReferenceEmbedding:
        """Insert reference embedding vector and update centroid."""
        emb_id = str(uuid.uuid4())
        vec = np.asarray(vector, dtype=np.float32).flatten()
        blob = vector_to_blob(vec)

        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO reference_embedding (
                    id, voice_profile_id, vector, source, session_id,
                    snr_db, duration_sec, model_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    emb_id,
                    profile_id,
                    blob,
                    source,
                    session_id,
                    snr_db,
                    duration_sec,
                    model_version,
                ),
            )
            conn.commit()

        self.update_profile_centroid(profile_id)

        return ReferenceEmbedding(
            id=emb_id,
            voice_profile_id=profile_id,
            vector=vec,
            source=source,
            session_id=session_id,
            snr_db=snr_db,
            duration_sec=duration_sec,
            model_version=model_version,
        )

    def get_reference_embeddings(self, profile_id: str) -> list[ReferenceEmbedding]:
        """Fetch all reference embeddings belonging to a voice profile."""
        with self.get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM reference_embedding WHERE voice_profile_id = ? ORDER BY created_at ASC",
                (profile_id,),
            ).fetchall()

            return [
                ReferenceEmbedding(
                    id=r["id"],
                    voice_profile_id=r["voice_profile_id"],
                    vector=blob_to_vector(r["vector"]),
                    source=r["source"],
                    session_id=r["session_id"],
                    snr_db=float(r["snr_db"] or 0.0),
                    duration_sec=float(r["duration_sec"] or 0.0),
                    model_version=r["model_version"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]

    def update_profile_centroid(self, profile_id: str) -> np.ndarray | None:
        """Recalculate L2-normalized mean centroid of all reference embeddings in profile."""
        refs = self.get_reference_embeddings(profile_id)
        if not refs:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE voice_profile SET centroid = NULL, ref_count = 0 WHERE id = ?",
                    (profile_id,),
                )
                conn.commit()
            return None

        vectors = [r.vector for r in refs if r.vector.size > 0]
        if not vectors:
            return None

        mat = np.vstack(vectors)
        centroid = np.mean(mat, axis=0)
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm

        blob = vector_to_blob(centroid)
        ref_count = len(vectors)

        with self.get_connection() as conn:
            conn.execute(
                "UPDATE voice_profile SET centroid = ?, ref_count = ? WHERE id = ?",
                (blob, ref_count, profile_id),
            )
            conn.commit()

        return centroid

    def get_all_active_profiles(
        self,
        embedding_model: str = "ecapa-tdnn-voxceleb-v2",
        language: str | None = None,
    ) -> list[tuple[Actor, VoiceProfile, list[ReferenceEmbedding]]]:
        """Load all active actor profiles with centroids and reference embeddings for matching."""
        actors = self.list_actors(include_deleted=False)
        actor_map = {a.id: a for a in actors}
        if not actor_map:
            return []

        results: list[tuple[Actor, VoiceProfile, list[ReferenceEmbedding]]] = []
        with self.get_connection() as conn:
            query = "SELECT * FROM voice_profile WHERE embedding_model = ?"
            params: list[Any] = [embedding_model]
            if language:
                query += " AND language = ?"
                params.append(language)

            p_rows = conn.execute(query, params).fetchall()
            for pr in p_rows:
                act = actor_map.get(pr["actor_id"])
                if not act:
                    continue

                centroid = blob_to_vector(pr["centroid"]) if pr["centroid"] else None
                prof = VoiceProfile(
                    id=pr["id"],
                    actor_id=pr["actor_id"],
                    language=pr["language"],
                    embedding_model=pr["embedding_model"],
                    centroid=centroid,
                    ref_count=pr["ref_count"],
                    created_at=pr["created_at"],
                )

                e_rows = conn.execute(
                    "SELECT * FROM reference_embedding WHERE voice_profile_id = ?",
                    (prof.id,),
                ).fetchall()

                refs = [
                    ReferenceEmbedding(
                        id=er["id"],
                        voice_profile_id=er["voice_profile_id"],
                        vector=blob_to_vector(er["vector"]),
                        source=er["source"],
                        session_id=er["session_id"],
                        snr_db=float(er["snr_db"] or 0.0),
                        duration_sec=float(er["duration_sec"] or 0.0),
                        model_version=er["model_version"],
                        created_at=er["created_at"],
                    )
                    for er in e_rows
                ]

                results.append((act, prof, refs))

        return results

    # -------------------------------------------------------------------------
    # Session Operations
    # -------------------------------------------------------------------------

    def create_session(
        self,
        media_file_id: str | None = None,
        language: str = "en",
        num_speakers: int | None = None,
        pipeline_ver: str = "1.0.0",
        embedding_model: str = "ecapa-tdnn-voxceleb-v2",
    ) -> Session:
        """Create a new processing session."""
        session_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO session (
                    id, media_file_id, language, num_speakers,
                    pipeline_ver, embedding_model, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    session_id,
                    media_file_id,
                    language,
                    num_speakers,
                    pipeline_ver,
                    embedding_model,
                ),
            )
            conn.commit()

        return Session(
            id=session_id,
            media_file_id=media_file_id,
            language=language,
            num_speakers=num_speakers,
            pipeline_ver=pipeline_ver,
            embedding_model=embedding_model,
            status="running",
        )

    def get_session(self, session_id: str) -> Session | None:
        """Fetch session by ID."""
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM session WHERE id = ?", (session_id,)).fetchone()
            if not row:
                return None
            return Session(
                id=row["id"],
                media_file_id=row["media_file_id"],
                language=row["language"],
                num_speakers=row["num_speakers"],
                pipeline_ver=row["pipeline_ver"],
                embedding_model=row["embedding_model"],
                status=row["status"],
                created_at=row["created_at"],
            )

    def update_session_status(self, session_id: str, status: str) -> None:
        """Update session state ('queued','running','done','failed','needs_review')."""
        with self.get_connection() as conn:
            conn.execute("UPDATE session SET status = ? WHERE id = ?", (status, session_id))
            conn.commit()

    def save_segments(self, session_id: str, segments: list[dict[str, Any]]) -> None:
        """Save segments and their nested word timestamps into the database."""
        with self.get_connection() as conn:
            # Ensure session exists to satisfy foreign key constraint
            conn.execute(
                "INSERT OR IGNORE INTO session (id, pipeline_ver, embedding_model, status) VALUES (?, '1.0.0', 'ecapa-tdnn-voxceleb-v2', 'running')",
                (session_id,),
            )
            # Clear previous segments for this session
            conn.execute("DELETE FROM segment WHERE session_id = ?", (session_id,))

            for s in segments:
                seg_id = s.get("id") or str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO segment (
                        id, session_id, start_sec, end_sec, cluster_label,
                        actor_id, match_score, match_status, text, asr_conf,
                        overlap_flag, corrected_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        seg_id,
                        session_id,
                        float(s["start"]),
                        float(s["end"]),
                        s.get("speaker") or s.get("cluster_label", "SPK_0"),
                        s.get("actor_id"),
                        s.get("match_score"),
                        s.get("match_status", "new"),
                        s.get("text", ""),
                        s.get("asr_conf", 1.0),
                        1 if s.get("overlap", False) else 0,
                        s.get("corrected_by"),
                    ),
                )

                words = s.get("words", [])
                for w in words:
                    word_id = str(uuid.uuid4())
                    conn.execute(
                        """
                        INSERT INTO word (id, segment_id, start_sec, end_sec, token, conf)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            word_id,
                            seg_id,
                            float(w.get("s", w.get("start", 0.0))),
                            float(w.get("e", w.get("end", 0.0))),
                            w.get("w", w.get("token", "")),
                            float(w.get("c", w.get("conf", 1.0))),
                        ),
                    )
            conn.commit()

    def get_segments(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve all segments for a session with word-level detail."""
        with self.get_connection() as conn:
            s_rows = conn.execute(
                """
                SELECT s.*, a.display_name as actor_name
                FROM segment s
                LEFT JOIN actor a ON s.actor_id = a.id
                WHERE s.session_id = ?
                ORDER BY s.start_sec ASC
                """,
                (session_id,),
            ).fetchall()

            segments: list[dict[str, Any]] = []
            for sr in s_rows:
                seg_id = sr["id"]
                w_rows = conn.execute(
                    "SELECT * FROM word WHERE segment_id = ? ORDER BY start_sec ASC",
                    (seg_id,),
                ).fetchall()

                words = [
                    {
                        "w": wr["token"],
                        "s": round(float(wr["start_sec"]), 3),
                        "e": round(float(wr["end_sec"]), 3),
                        "c": round(float(wr["conf"]), 3),
                    }
                    for wr in w_rows
                ]

                segments.append({
                    "id": seg_id,
                    "start": round(float(sr["start_sec"]), 3),
                    "end": round(float(sr["end_sec"]), 3),
                    "speaker": sr["cluster_label"],
                    "actor_id": sr["actor_id"],
                    "actor": sr["actor_name"] if sr["actor_name"] else None,
                    "match_score": round(float(sr["match_score"]), 3) if sr["match_score"] is not None else None,
                    "match_status": sr["match_status"],
                    "text": sr["text"] or "",
                    "asr_conf": round(float(sr["asr_conf"]), 3) if sr["asr_conf"] is not None else 1.0,
                    "overlap": bool(sr["overlap_flag"]),
                    "words": words,
                })

            return segments

    def save_cluster_matches(self, session_id: str, matches: list[dict[str, Any]]) -> None:
        """Save cluster to actor mappings for session."""
        with self.get_connection() as conn:
            # Ensure session exists to satisfy foreign key constraint
            conn.execute(
                "INSERT OR IGNORE INTO session (id, pipeline_ver, embedding_model, status) VALUES (?, '1.0.0', 'ecapa-tdnn-voxceleb-v2', 'running')",
                (session_id,),
            )
            conn.execute("DELETE FROM cluster_match WHERE session_id = ?", (session_id,))
            for m in matches:
                conn.execute(
                    """
                    INSERT INTO cluster_match (id, session_id, cluster_label, actor_id, score, status, decided_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        session_id,
                        m["cluster_label"],
                        m.get("actor_id"),
                        m.get("score"),
                        m.get("status", "new"),
                        m.get("decided_by"),
                    ),
                )
            conn.commit()

    def get_cluster_matches(self, session_id: str) -> list[dict[str, Any]]:
        """Retrieve cluster matches for a session."""
        with self.get_connection() as conn:
            rows = conn.execute(
                """
                SELECT cm.*, a.display_name as actor_name
                FROM cluster_match cm
                LEFT JOIN actor a ON cm.actor_id = a.id
                WHERE cm.session_id = ?
                ORDER BY cm.cluster_label ASC
                """,
                (session_id,),
            ).fetchall()

            return [
                {
                    "cluster": r["cluster_label"],
                    "actor": {"id": r["actor_id"], "name": r["actor_name"]} if r["actor_id"] else None,
                    "match_score": round(float(r["score"]), 3) if r["score"] is not None else 0.0,
                    "match_status": r["status"],
                }
                for r in rows
            ]

    # -------------------------------------------------------------------------
    # Audit Log Helper
    # -------------------------------------------------------------------------

    def _log_audit(
        self,
        conn: sqlite3.Connection,
        entity: str,
        entity_id: str,
        action: str,
        payload: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> None:
        payload_str = json.dumps(payload or {}, ensure_ascii=False)
        conn.execute(
            """
            INSERT INTO audit_log (entity, entity_id, action, payload, user_id)
            VALUES (?, ?, ?, ?, ?)
            """,
            (entity, entity_id, action, payload_str, user_id),
        )

    def get_audit_logs(self, entity_id: str | None = None) -> list[dict[str, Any]]:
        """Fetch audit log entries."""
        with self.get_connection() as conn:
            if entity_id:
                rows = conn.execute(
                    "SELECT * FROM audit_log WHERE entity_id = ? ORDER BY created_at DESC",
                    (entity_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 200"
                ).fetchall()

            return [
                {
                    "id": r["id"],
                    "entity": r["entity"],
                    "entity_id": r["entity_id"],
                    "action": r["action"],
                    "payload": json.loads(r["payload"] or "{}"),
                    "user_id": r["user_id"],
                    "created_at": r["created_at"],
                }
                for r in rows
            ]

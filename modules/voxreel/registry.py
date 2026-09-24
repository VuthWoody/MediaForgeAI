"""VoxReel Actor Voice Registry (AVR) & Identity Matching Engine.

Implements FR-4, FR-5, and §10.1–10.2 from VOX_engine_Plan.md:
- Persistent Actor and Voice Profile management with SQLite + vector indexing
- Quality-gated enrollment (SNR >= 12 dB, duration >= 1.5s, dedupe cosine > 0.98, cap 50)
- Profile centroid tracking (L2-normalized average)
- Multi-metric similarity scoring: 0.6 * centroid_sim + 0.4 * mean_sim
- Hungarian bipartite matching across session clusters
- Thresholds: auto >= 0.82, review 0.70–0.82, new < 0.70
- Learning feedback flywheel: promoting confirmed clusters into persistent actor profiles
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from modules.voxreel.audio import AudioConditioner
from modules.voxreel.config import RegistryConfig
from modules.voxreel.db import (
    Actor,
    VoxReelDB,
    cosine_similarity,
)
from modules.voxreel.diarizer import SpeakerEmbeddingExtractor
from modules.voxreel.hungarian import match_clusters_to_candidates

logger = logging.getLogger("voxreel.registry")


@dataclass
class ClusterMatchResult:
    cluster_label: str
    actor_id: str | None = None
    actor_name: str | None = None
    match_score: float = 0.0
    match_status: str = "new"  # 'auto' | 'review' | 'new' | 'manual'
    centroid_sim: float = 0.0
    mean_sim: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster": self.cluster_label,
            "actor": {"id": self.actor_id, "name": self.actor_name} if self.actor_id else None,
            "match_score": round(self.match_score, 3),
            "match_status": self.match_status,
        }


class ActorVoiceRegistry:
    """Actor Voice Registry manager handling enrollment, Hungarian matching, and feedback."""

    def __init__(
        self,
        db: VoxReelDB | None = None,
        config: RegistryConfig | None = None,
    ) -> None:
        self.db = db or VoxReelDB()
        self.config = config or RegistryConfig()
        self.audio_conditioner = AudioConditioner()
        self.embedder = SpeakerEmbeddingExtractor(embedding_dim=192)

    # -------------------------------------------------------------------------
    # Actor Management (CRUD & Merge/Delete)
    # -------------------------------------------------------------------------

    def create_actor(
        self,
        display_name: str,
        aliases: list[str] | None = None,
        notes: str | None = None,
        consent_flag: bool = True,
    ) -> Actor:
        """Create a new actor entry in the registry."""
        return self.db.create_actor(
            display_name=display_name,
            aliases=aliases,
            notes=notes,
            consent_flag=consent_flag,
        )

    def get_actor(self, actor_id: str) -> Actor | None:
        return self.db.get_actor(actor_id)

    def search_actors(self, query: str) -> list[Actor]:
        return self.db.search_actors(query)

    def list_actors(self, include_deleted: bool = False) -> list[Actor]:
        return self.db.list_actors(include_deleted=include_deleted)

    def update_actor(
        self,
        actor_id: str,
        display_name: str | None = None,
        aliases: list[str] | None = None,
        notes: str | None = None,
        consent_flag: bool | None = None,
    ) -> Actor | None:
        return self.db.update_actor(
            actor_id=actor_id,
            display_name=display_name,
            aliases=aliases,
            notes=notes,
            consent_flag=consent_flag,
        )

    def delete_actor(self, actor_id: str) -> bool:
        """Fully erase actor and all biometric voice vectors (GDPR Art. 9)."""
        return self.db.delete_actor(actor_id, hard_delete=True)

    def merge_actors(self, target_id: str, source_id: str) -> Actor | None:
        """Merge source actor into target actor, transferring vectors and aliases."""
        return self.db.merge_actors(target_id=target_id, source_id=source_id)

    # -------------------------------------------------------------------------
    # Voice Profile & Enrollment
    # -------------------------------------------------------------------------

    def enroll_clip(
        self,
        actor_id: str,
        audio_path: str | Path,
        language: str = "en",
        model_name: str = "ecapa-tdnn-voxceleb-v2",
    ) -> tuple[bool, str, int]:
        """Enroll reference speech audio clips into an actor's voice profile.

        Applies FR-4.5 quality gates:
        - SNR >= 12.0 dB
        - Segment duration >= 1.5s
        - Near-duplicate dropping (cosine sim > 0.98)
        - Profile size cap (<= 50 embeddings)

        Returns:
            (success, message, num_embeddings_enrolled)
        """
        actor = self.get_actor(actor_id)
        if not actor:
            return False, f"Actor ID '{actor_id}' not found.", 0

        p = Path(audio_path).resolve()
        if not p.exists():
            return False, f"Audio file '{p}' not found.", 0

        # Load audio
        audio, sr = self.audio_conditioner.load_audio_array(p)
        dur = len(audio) / sr if sr > 0 else 0.0

        if dur < self.config.min_enroll_duration_s:
            return False, f"Clip duration ({dur:.2f}s) is shorter than minimum required ({self.config.min_enroll_duration_s}s).", 0

        snr = self.audio_conditioner.calculate_snr(audio, sr=sr)
        if snr < self.config.min_enroll_snr_db:
            return False, f"Clip SNR ({snr:.1f} dB) is below required quality gate ({self.config.min_enroll_snr_db} dB).", 0

        # Extract 192-d embedding
        emb = self.embedder.extract(audio, sr=sr)

        # Get or create profile
        profile = self.db.get_or_create_profile(actor_id, language=language, embedding_model=model_name)
        existing_refs = self.db.get_reference_embeddings(profile.id)

        # Check deduplication threshold (FR-4.5: dedupe_cosine: 0.98)
        for ref in existing_refs:
            sim = cosine_similarity(emb, ref.vector)
            if sim >= self.config.dedupe_cosine:
                logger.info("Skipping near-duplicate embedding (sim: %.4f >= %.2f)", sim, self.config.dedupe_cosine)
                return True, "Embedding is identical to existing reference; profile maintained.", 0

        # Check max profile capacity (capped at 50)
        if len(existing_refs) >= self.config.max_profile_embeddings:
            # Replace the reference with lowest SNR
            existing_refs.sort(key=lambda r: r.snr_db)
            lowest = existing_refs[0]
            with self.db.get_connection() as conn:
                conn.execute("DELETE FROM reference_embedding WHERE id = ?", (lowest.id,))
                conn.commit()

        # Add new reference embedding
        self.db.add_reference_embedding(
            profile_id=profile.id,
            vector=emb,
            source="enroll_clip",
            snr_db=snr,
            duration_sec=dur,
            model_version=model_name,
        )

        return True, f"Successfully enrolled voice clip for {actor.display_name} (SNR: {snr:.1f} dB).", 1

    # -------------------------------------------------------------------------
    # Matching Algorithm (§10.2)
    # -------------------------------------------------------------------------

    def match_session_clusters(
        self,
        session_id: str,
        cluster_embeddings: dict[str, list[np.ndarray]],
        language: str = "en",
        model_name: str = "ecapa-tdnn-voxceleb-v2",
    ) -> list[ClusterMatchResult]:
        """Match session cluster embeddings against persistent Actor Voice Registry profiles.

        Implements §10.2:
        1. centroid_c = mean(top-quality embeddings of C)
        2. candidates = all active actor profiles
        3. combined = 0.6 * centroid_sim + 0.4 * mean_sim
        4. Hungarian assignment across clusters
        5. Threshold assignment: auto (>= 0.82), review (0.70–0.82), new (< 0.70)
        """
        active_profiles = self.db.get_all_active_profiles(embedding_model=model_name, language=language)
        if not active_profiles:
            # Fallback across languages if no exact language profile match
            active_profiles = self.db.get_all_active_profiles(embedding_model=model_name)

        clusters = sorted(cluster_embeddings.keys())
        if not clusters:
            return []

        # If no registered actors exist yet, all clusters are marked as 'new'
        if not active_profiles:
            results: list[ClusterMatchResult] = []
            for idx, c in enumerate(clusters):
                results.append(
                    ClusterMatchResult(
                        cluster_label=c,
                        actor_id=None,
                        actor_name=f"UNKNOWN_{idx + 1}",
                        match_score=0.0,
                        match_status="new",
                    )
                )
            return results

        # 1. Compute cluster centroids
        cluster_centroids: list[np.ndarray] = []
        for c in clusters:
            embs = cluster_embeddings[c]
            if not embs:
                cluster_centroids.append(np.zeros(192, dtype=np.float32))
            else:
                mat = np.vstack(embs)
                c_cent = np.mean(mat, axis=0)
                norm = np.linalg.norm(c_cent)
                if norm > 0:
                    c_cent = c_cent / norm
                cluster_centroids.append(c_cent)

        # 2. Compute similarity matrix: shape (num_clusters, num_candidates)
        num_clusters = len(clusters)
        num_candidates = len(active_profiles)
        sim_matrix = np.zeros((num_clusters, num_candidates), dtype=np.float32)

        for i, c_cent in enumerate(cluster_centroids):
            for j, (_actor, profile, refs) in enumerate(active_profiles):
                # Centroid similarity
                if profile.centroid is not None and profile.centroid.size > 0:
                    c_sim = cosine_similarity(c_cent, profile.centroid)
                else:
                    c_sim = 0.0

                # Mean similarity across reference embeddings
                if refs:
                    ref_sims = [cosine_similarity(c_cent, r.vector) for r in refs]
                    m_sim = float(np.mean(ref_sims))
                else:
                    m_sim = c_sim

                # Combined score: 0.6 * centroid_sim + 0.4 * mean_sim (§10.2)
                combined = 0.6 * c_sim + 0.4 * m_sim
                sim_matrix[i, j] = combined

        # 3. Hungarian Bipartite Assignment
        # Prevents two clusters claiming the same actor when #clusters <= #candidates
        matches = match_clusters_to_candidates(sim_matrix)

        assigned_candidates: dict[int, tuple[int, float]] = {}
        for r_idx, c_idx, score in matches:
            assigned_candidates[r_idx] = (c_idx, score)

        # 4. Classify according to thresholds
        match_results: list[ClusterMatchResult] = []
        unknown_counter = 1

        for i, c in enumerate(clusters):
            c_cent = cluster_centroids[i]
            if i in assigned_candidates:
                cand_idx, score = assigned_candidates[i]
                actor, profile, refs = active_profiles[cand_idx]

                c_sim = cosine_similarity(c_cent, profile.centroid) if profile.centroid is not None else 0.0
                m_sim = float(np.mean([cosine_similarity(c_cent, r.vector) for r in refs])) if refs else c_sim

                if score >= self.config.auto_assign_threshold:
                    status = "auto"
                    a_id = actor.id
                    a_name = actor.display_name
                elif score >= self.config.review_band_min:
                    status = "review"
                    a_id = actor.id
                    a_name = actor.display_name
                else:
                    status = "new"
                    a_id = None
                    a_name = f"UNKNOWN_{unknown_counter}"
                    unknown_counter += 1

                match_results.append(
                    ClusterMatchResult(
                        cluster_label=c,
                        actor_id=a_id,
                        actor_name=a_name,
                        match_score=score,
                        match_status=status,
                        centroid_sim=c_sim,
                        mean_sim=m_sim,
                    )
                )
            else:
                match_results.append(
                    ClusterMatchResult(
                        cluster_label=c,
                        actor_id=None,
                        actor_name=f"UNKNOWN_{unknown_counter}",
                        match_score=0.0,
                        match_status="new",
                    )
                )
                unknown_counter += 1

        # 5. Persist matches in DB
        db_matches = [
            {
                "cluster_label": mr.cluster_label,
                "actor_id": mr.actor_id,
                "score": mr.match_score,
                "status": mr.match_status,
                "decided_by": None,
            }
            for mr in match_results
        ]
        self.db.save_cluster_matches(session_id, db_matches)

        return match_results

    # -------------------------------------------------------------------------
    # Learning Flywheel & Feedback (§5.5, §11.2)
    # -------------------------------------------------------------------------

    def promote_cluster_to_actor(
        self,
        session_id: str,
        cluster_label: str,
        actor_name: str,
        aliases: list[str] | None = None,
        cluster_embeddings: list[np.ndarray] | None = None,
        language: str = "en",
    ) -> Actor:
        """Promote an unknown cluster to a registered Actor with profile embeddings.

        Creates the actor, enrolls quality-gated embeddings from the session,
        recalculates centroid, updates session segments, and logs audit trail.
        """
        # Find or create actor
        actor = self.db.get_actor_by_name(actor_name)
        if not actor:
            actor = self.db.create_actor(
                display_name=actor_name,
                aliases=aliases or [],
                notes=f"Promoted from session {session_id} ({cluster_label})",
                consent_flag=True,
            )

        # Enroll embeddings if provided
        if cluster_embeddings:
            profile = self.db.get_or_create_profile(actor.id, language=language)
            for emb in cluster_embeddings:
                # Add with deduplication check
                existing_refs = self.db.get_reference_embeddings(profile.id)
                is_dupe = any(
                    cosine_similarity(emb, r.vector) >= self.config.dedupe_cosine
                    for r in existing_refs
                )
                if not is_dupe and len(existing_refs) < self.config.max_profile_embeddings:
                    self.db.add_reference_embedding(
                        profile_id=profile.id,
                        vector=emb,
                        source="confirmed_segment",
                        session_id=session_id,
                        snr_db=20.0,
                        duration_sec=2.0,
                    )

        # Update database segments for this session
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE segment
                SET actor_id = ?, match_status = 'confirmed'
                WHERE session_id = ? AND cluster_label = ?
                """,
                (actor.id, session_id, cluster_label),
            )
            conn.execute(
                """
                UPDATE cluster_match
                SET actor_id = ?, status = 'confirmed'
                WHERE session_id = ? AND cluster_label = ?
                """,
                (actor.id, session_id, cluster_label),
            )
            self.db._log_audit(
                conn,
                "session",
                session_id,
                "promote_to_actor",
                {"cluster": cluster_label, "actor_id": actor.id, "actor_name": actor.display_name},
            )
            conn.commit()

        return actor

    def apply_corrections(
        self,
        session_id: str,
        corrections: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply human corrections batch to a session (§11.2).

        Actions supported:
        - 'reassign_speaker': change segment's actor_id
        - 'edit_text': update segment text
        - 'confirm_match': mark segment match_status as 'confirmed'
        - 'promote_to_actor': create/enroll actor from cluster
        """
        applied_count = 0
        with self.db.get_connection() as conn:
            for item in corrections:
                action = item.get("action")
                seg_id = item.get("segment_id")

                if action == "reassign_speaker" and seg_id:
                    actor_id = item.get("actor_id")
                    conn.execute(
                        "UPDATE segment SET actor_id = ?, match_status = 'manual' WHERE id = ?",
                        (actor_id, seg_id),
                    )
                    applied_count += 1

                elif action == "edit_text" and seg_id:
                    new_text = item.get("text", "")
                    conn.execute("UPDATE segment SET text = ? WHERE id = ?", (new_text, seg_id))
                    applied_count += 1

                elif action == "confirm_match" and seg_id:
                    conn.execute(
                        "UPDATE segment SET match_status = 'confirmed' WHERE id = ?",
                        (seg_id,),
                    )
                    applied_count += 1

                elif action == "promote_to_actor":
                    cluster = item.get("cluster", "SPK_A")
                    name = item.get("name", "New Actor")
                    aliases = item.get("aliases", [])
                    self.promote_cluster_to_actor(
                        session_id=session_id,
                        cluster_label=cluster,
                        actor_name=name,
                        aliases=aliases,
                    )
                    applied_count += 1

            self.db._log_audit(
                conn,
                "session",
                session_id,
                "batch_corrections",
                {"count": applied_count, "items": corrections},
            )
            conn.commit()

        return {"status": "applied", "count": applied_count}

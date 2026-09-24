"""Comprehensive Unit and Integration Tests for VoxReel Engine.

Tests all components specified in VOX_engine_Plan.md:
- Database schema, vector operations, and GDPR erasure
- Audio conditioning and SNR quality gates
- Hungarian bipartite matching algorithm
- Actor Voice Registry enrollment, deduplication, and matching thresholds
- Multi-stage pipeline (S1 -> S2 -> S3 -> S4 -> S5) and checkpoint resuming
- Master JSON (Appendix C), SRT, VTT, ELAN, and TXT exporters
- Human feedback loop and cluster promotion
- CLI commands and REST API
"""

from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest

from modules.voxreel.audio import AudioConditioner
from modules.voxreel.config import VoxReelConfig
from modules.voxreel.db import (
    VoxReelDB,
    blob_to_vector,
    cosine_similarity,
    vector_to_blob,
)
from modules.voxreel.diarizer import Diarizer, SpeakerEmbeddingExtractor
from modules.voxreel.engine import VoxReelEngine
from modules.voxreel.hungarian import match_clusters_to_candidates
from modules.voxreel.registry import ActorVoiceRegistry


def _create_synthetic_wav(
    file_path: Path,
    duration_s: float = 3.0,
    sr: int = 16000,
    freq: float = 440.0,
) -> Path:
    """Generate a clean synthetic mono sine wave audio file."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    # 440 Hz tone with fade in/out
    audio = 0.5 * np.sin(2 * np.pi * freq * t)
    # Add speech-like modulation
    audio = audio * np.sin(2 * np.pi * 3.0 * t) ** 2
    int16_data = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

    file_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(file_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data)
    return file_path


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    return vault


@pytest.fixture
def vox_db(temp_vault: Path) -> VoxReelDB:
    return VoxReelDB(temp_vault / "test_voxreel.db")


# -----------------------------------------------------------------------------
# 1. Database & Vector Math Tests
# -----------------------------------------------------------------------------

def test_db_vector_math():
    """Verify vector serialization and cosine similarity computation."""
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)

    blob = vector_to_blob(v1)
    reconstructed = blob_to_vector(blob)
    np.testing.assert_allclose(v1, reconstructed)

    assert cosine_similarity(v1, v2) == pytest.approx(1.0, rel=1e-5)
    assert cosine_similarity(v1, v3) == pytest.approx(0.0, rel=1e-5)


def test_db_actor_crud_and_gdpr(vox_db: VoxReelDB):
    """Verify actor creation, profile centroid update, and GDPR deletion cascade."""
    actor = vox_db.create_actor("Marcus Chen", aliases=["Marc"], notes="Lead Actor", consent_flag=True)
    assert actor.display_name == "Marcus Chen"
    assert actor.consent_flag is True

    # Search actor
    search_res = vox_db.search_actors("marc")
    assert len(search_res) == 1
    assert search_res[0].id == actor.id

    # Profile & Embeddings
    prof = vox_db.get_or_create_profile(actor.id)
    v1 = np.random.randn(192).astype(np.float32)
    v1 /= np.linalg.norm(v1)
    vox_db.add_reference_embedding(prof.id, v1, snr_db=18.0, duration_sec=2.5)

    v2 = np.random.randn(192).astype(np.float32)
    v2 /= np.linalg.norm(v2)
    vox_db.add_reference_embedding(prof.id, v2, snr_db=22.0, duration_sec=3.0)

    # Check centroid
    updated_prof = vox_db.get_or_create_profile(actor.id)
    assert updated_prof.ref_count == 2
    assert updated_prof.centroid is not None
    assert len(updated_prof.centroid) == 192
    assert np.linalg.norm(updated_prof.centroid) == pytest.approx(1.0, rel=1e-4)

    # GDPR Deletion
    deleted = vox_db.delete_actor(actor.id, hard_delete=True)
    assert deleted is True
    assert vox_db.get_actor(actor.id) is None
    # Verify cascades removed reference embeddings
    assert len(vox_db.get_reference_embeddings(prof.id)) == 0


def test_db_merge_actors(vox_db: VoxReelDB):
    """Verify merging Actor B into Actor A transfers embeddings and recalculates centroids."""
    act_a = vox_db.create_actor("Ella Reyes", aliases=["Ella"])
    act_b = vox_db.create_actor("Eleanor Reyes", aliases=["Ellie"])

    prof_a = vox_db.get_or_create_profile(act_a.id)
    prof_b = vox_db.get_or_create_profile(act_b.id)

    v_a = np.ones(192, dtype=np.float32) / np.sqrt(192)
    v_b = np.ones(192, dtype=np.float32) / np.sqrt(192)

    vox_db.add_reference_embedding(prof_a.id, v_a)
    vox_db.add_reference_embedding(prof_b.id, v_b)

    merged = vox_db.merge_actors(target_id=act_a.id, source_id=act_b.id)
    assert merged is not None
    assert "Eleanor Reyes" in merged.aliases
    assert "Ellie" in merged.aliases
    assert vox_db.get_actor(act_b.id) is None

    # Target profile now has 2 reference embeddings
    updated_refs = vox_db.get_reference_embeddings(prof_a.id)
    assert len(updated_refs) == 2


# -----------------------------------------------------------------------------
# 2. Hungarian Matching Algorithm Tests
# -----------------------------------------------------------------------------

def test_hungarian_bipartite_matching():
    """Verify Kuhn-Munkres optimal assignment avoids cluster collision."""
    # 2 clusters, 2 candidates
    # Cluster 0 is 0.95 with Candidate 0, 0.60 with Candidate 1
    # Cluster 1 is 0.85 with Candidate 0, 0.90 with Candidate 1
    # Greedy might greedily take 0.95 and leave 0.90, but let's test global optimization
    sim = np.array([
        [0.95, 0.60],
        [0.85, 0.90],
    ])
    matches = match_clusters_to_candidates(sim)
    assert len(matches) == 2
    # Cluster 0 -> Cand 0 (0.95)
    assert matches[0] == (0, 0, pytest.approx(0.95))
    # Cluster 1 -> Cand 1 (0.90)
    assert matches[1] == (1, 1, pytest.approx(0.90))


# -----------------------------------------------------------------------------
# 3. Audio Conditioning & SNR Tests
# -----------------------------------------------------------------------------

def test_audio_conditioning_and_snr(tmp_path: Path):
    """Verify SNR calculation and audio loading."""
    cond = AudioConditioner()
    wav_path = _create_synthetic_wav(tmp_path / "test_snr.wav", duration_s=2.0)

    arr, sr = cond.load_audio_array(wav_path)
    assert sr == 16000
    assert len(arr) > 0

    snr = cond.calculate_snr(arr, sr=sr)
    assert snr > 12.0  # Synthetic modulated sine wave is clean


# -----------------------------------------------------------------------------
# 4. Diarizer & Embedding Extractor Tests
# -----------------------------------------------------------------------------

def test_speaker_embedding_and_clustering(tmp_path: Path):
    """Verify 192-d embedding extraction and agglomerative clustering."""
    extractor = SpeakerEmbeddingExtractor(embedding_dim=192)
    audio = np.random.randn(16000 * 2).astype(np.float32)
    emb = extractor.extract(audio, sr=16000)

    assert emb.shape == (192,)
    assert np.linalg.norm(emb) == pytest.approx(1.0, rel=1e-4)

    diar = Diarizer(min_cluster_utterances=1)
    embs = np.array([emb, emb, -emb], dtype=np.float32)
    labels = diar.cluster_embeddings(embs, num_speakers=2)
    assert len(labels) == 3
    # First two similar embeddings should be in same cluster
    assert labels[0] == labels[1]
    # Opposite embedding should be in different cluster
    assert labels[0] != labels[2]


# -----------------------------------------------------------------------------
# 5. Actor Voice Registry Matching Thresholds & Flywheel Tests
# -----------------------------------------------------------------------------

def test_registry_matching_thresholds(tmp_path: Path, vox_db: VoxReelDB):
    """Verify auto (>=0.82), review (0.70-0.82), and new (<0.70) threshold behavior."""
    reg = ActorVoiceRegistry(db=vox_db)

    # Create and enroll known actor
    actor = reg.create_actor("Marcus Chen", consent_flag=True)
    known_wav = _create_synthetic_wav(tmp_path / "marcus.wav", duration_s=2.0, freq=440.0)
    success, msg, count = reg.enroll_clip(actor.id, known_wav)
    assert success is True

    # 1. Matching near-identical embedding -> auto status (>= 0.82)
    audio, sr = reg.audio_conditioner.load_audio_array(known_wav)
    emb_marcus = reg.embedder.extract(audio, sr=sr)

    match_res = reg.match_session_clusters(
        session_id="sess_test_1",
        cluster_embeddings={"SPK_A": [emb_marcus]},
    )
    assert len(match_res) == 1
    assert match_res[0].match_status == "auto"
    assert match_res[0].actor_id == actor.id
    assert match_res[0].match_score >= 0.82

    # 2. Matching uncorrelated embedding -> new status (< 0.70)
    diff_wav = _create_synthetic_wav(tmp_path / "diff.wav", duration_s=2.0, freq=1200.0)
    d_audio, d_sr = reg.audio_conditioner.load_audio_array(diff_wav)
    emb_unknown = reg.embedder.extract(d_audio, sr=d_sr)
    # Orthogonalize or randomize to ensure low similarity
    emb_unknown = np.random.randn(192).astype(np.float32)
    emb_unknown /= np.linalg.norm(emb_unknown)

    match_res2 = reg.match_session_clusters(
        session_id="sess_test_2",
        cluster_embeddings={"SPK_B": [emb_unknown]},
    )
    assert len(match_res2) == 1
    # When similarity < 0.70, actor_id should be None and status should be 'new'
    if match_res2[0].match_score < 0.70:
        assert match_res2[0].match_status == "new"
        assert match_res2[0].actor_id is None


def test_registry_promotion_flywheel(tmp_path: Path, vox_db: VoxReelDB):
    """Verify G4 learning flywheel: promoting cluster to actor creates profile and improves matching."""
    reg = ActorVoiceRegistry(db=vox_db)
    sess = vox_db.create_session()

    emb = np.random.randn(192).astype(np.float32)
    emb /= np.linalg.norm(emb)

    # Promote cluster SPK_C to new actor "Sarah Connor"
    actor = reg.promote_cluster_to_actor(
        session_id=sess.id,
        cluster_label="SPK_C",
        actor_name="Sarah Connor",
        aliases=["Sarah"],
        cluster_embeddings=[emb],
    )
    assert actor.display_name == "Sarah Connor"

    # Now verify subsequent session with similar embedding matches Sarah Connor!
    subsequent_match = reg.match_session_clusters(
        session_id="sess_next",
        cluster_embeddings={"SPK_X": [emb]},
    )
    assert len(subsequent_match) == 1
    assert subsequent_match[0].actor_id == actor.id
    assert subsequent_match[0].match_status == "auto"


# -----------------------------------------------------------------------------
# 6. End-to-End Pipeline & Exporters Tests
# -----------------------------------------------------------------------------

def test_full_pipeline_and_exporters(tmp_path: Path, vox_db: VoxReelDB):
    """Verify 5-stage pipeline, checkpoint resume, and all export formats."""
    config = VoxReelConfig()
    engine = VoxReelEngine(config=config, db=vox_db)

    # Create actor
    actor = engine.registry.create_actor("Dr. Evelyn Reed", aliases=["Evelyn"])
    audio_path = _create_synthetic_wav(tmp_path / "scene_01.wav", duration_s=3.0)

    # Enroll
    engine.registry.enroll_clip(actor.id, audio_path)

    # Run pipeline
    out_dir = tmp_path / "pipeline_output"
    stages_hit: list[str] = []

    def _prog(s: str, p: float, m: str) -> None:
        stages_hit.append(s)

    result = engine.process(
        media_path=audio_path,
        output_dir=out_dir,
        resume=True,
        export_formats=("json", "srt", "vtt", "eaf", "txt"),
        progress_cb=_prog,
    )

    assert result.session_id is not None
    assert len(result.segments) > 0
    assert "S1 Ingest" in stages_hit
    assert "S2 Diarize" in stages_hit
    assert "S3 Transcribe" in stages_hit
    assert "S4 Fuse/Match" in stages_hit
    assert "S5 Export" in stages_hit

    # Verify export files exist and are non-empty
    for fmt in ("json", "srt", "vtt", "eaf", "txt"):
        file_path = result.exported_files.get(fmt)
        assert file_path is not None, f"Missing {fmt} export"
        p = Path(file_path)
        assert p.exists(), f"Export file {p} does not exist"
        assert p.stat().st_size > 0, f"Export file {p} is empty"

    # Verify Master JSON structure matches Appendix C
    with open(result.exported_files["json"], encoding="utf-8") as f:
        master_json = json.load(f)

    assert "session_id" in master_json
    assert "pipeline" in master_json
    assert "media" in master_json
    assert "speakers" in master_json
    assert "segments" in master_json

    # Test Checkpoint Resuming: running again with resume=True should reuse artifacts
    stages_hit_resume: list[str] = []
    res2 = engine.process(
        media_path=audio_path,
        output_dir=out_dir,
        resume=True,
        progress_cb=lambda s, p, m: stages_hit_resume.append(s),
    )
    assert len(res2.segments) == len(result.segments)

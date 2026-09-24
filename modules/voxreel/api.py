"""VoxReel REST API Specification.

Implements §11 from VOX_engine_Plan.md:
- POST   /api/v1/ingest
- POST   /api/v1/sessions
- GET    /api/v1/sessions/{id}
- GET    /api/v1/sessions/{id}/export
- POST   /api/v1/registry/actors
- GET    /api/v1/registry/actors
- PATCH  /api/v1/registry/actors/{id}
- DELETE /api/v1/registry/actors/{id}
- POST   /api/v1/registry/actors/{id}/enroll
- POST   /api/v1/registry/actors/{id}/merge
- POST   /api/v1/sessions/{id}/corrections
- POST   /api/v1/sessions/{id}/label
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from modules.voxreel.db import VoxReelDB
from modules.voxreel.engine import VoxReelEngine
from modules.voxreel.exporters import VoxReelExporter
from modules.voxreel.registry import ActorVoiceRegistry

app = FastAPI(
    title="VoxReel API",
    version="1.0.0",
    description="Stateful Speaker Diarization & Actor Voice Registry API",
)

db = VoxReelDB()
registry = ActorVoiceRegistry(db=db)
engine = VoxReelEngine(db=db)


# -----------------------------------------------------------------------------
# Request & Response Models
# -----------------------------------------------------------------------------

class CreateActorRequest(BaseModel):
    display_name: str
    aliases: list[str] = Field(default_factory=list)
    notes: str | None = None
    consent_flag: bool = True


class UpdateActorRequest(BaseModel):
    display_name: str | None = None
    aliases: list[str] | None = None
    notes: str | None = None
    consent_flag: bool | None = None


class MergeActorsRequest(BaseModel):
    source_actor_id: str


class StartSessionRequest(BaseModel):
    media_path: str
    language: str = "en"
    num_speakers: int | None = None


class BatchCorrectionsRequest(BaseModel):
    corrections: list[dict[str, Any]]


class LabelClusterRequest(BaseModel):
    cluster: str
    actor_name: str
    promote: bool = True
    aliases: list[str] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# API Endpoints (§11.1)
# -----------------------------------------------------------------------------

@app.post("/api/v1/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_media(file: UploadFile = File(...)) -> dict[str, Any]:  # noqa: B008
    """Upload media file and start background processing."""
    tmp_dir = Path(tempfile.gettempdir()) / "voxreel_uploads"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    fname = file.filename or "upload.wav"
    stored_path = tmp_dir / fname

    with open(stored_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    res = engine.process(stored_path)
    return {"job_id": res.session_id, "session_id": res.session_id, "status": "completed"}


@app.post("/api/v1/sessions", status_code=status.HTTP_202_ACCEPTED)
def start_session(req: StartSessionRequest) -> dict[str, Any]:
    """Start job from server-side file path."""
    p = Path(req.media_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Media file not found.")
    res = engine.process(p, language=req.language, num_speakers=req.num_speakers)
    return {"session_id": res.session_id, "status": "done"}


@app.get("/api/v1/sessions/{session_id}")
def get_session_transcript(session_id: str) -> dict[str, Any]:
    """Retrieve full attributed transcript for a session (Master JSON)."""
    sess = db.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found.")

    segments = db.get_segments(session_id)
    speakers = db.get_cluster_matches(session_id)

    return {
        "session_id": session_id,
        "pipeline": {"voxreel": "1.0.0", "embedding_model": sess.embedding_model},
        "media": {"name": f"session_{session_id}", "duration_sec": 0.0},
        "language": sess.language,
        "speakers": speakers,
        "segments": segments,
    }


@app.get("/api/v1/sessions/{session_id}/export")
def export_session(
    session_id: str,
    format: str = Query("srt", pattern="^(srt|vtt|json|eaf|txt)$"),
) -> FileResponse:
    """Download export in requested format."""
    data = get_session_transcript(session_id)
    tmp_out = Path(tempfile.gettempdir()) / f"voxreel_export_{session_id}.{format}"

    if format == "json":
        VoxReelExporter.export_json(data, tmp_out)
        media_type = "application/json"
    elif format == "srt":
        VoxReelExporter.export_srt(data, tmp_out)
        media_type = "text/plain"
    elif format == "vtt":
        VoxReelExporter.export_vtt(data, tmp_out)
        media_type = "text/vtt"
    elif format == "txt":
        VoxReelExporter.export_txt(data, tmp_out)
        media_type = "text/plain"
    elif format in ("eaf", "elan"):
        VoxReelExporter.export_elan(data, tmp_out)
        media_type = "application/xml"
    else:
        media_type = "text/plain"

    return FileResponse(tmp_out, media_type=media_type, filename=tmp_out.name)


@app.post("/api/v1/registry/actors", status_code=status.HTTP_201_CREATED)
def create_actor(req: CreateActorRequest) -> Any:
    """Create a new actor record in the registry."""
    act = registry.create_actor(
        display_name=req.display_name,
        aliases=req.aliases,
        notes=req.notes,
        consent_flag=req.consent_flag,
    )
    return act


@app.get("/api/v1/registry/actors")
def search_actors(q: str = Query("", description="Search term")) -> Any:
    """Search actors in registry."""
    return registry.search_actors(q)


@app.patch("/api/v1/registry/actors/{actor_id}")
def update_actor(actor_id: str, req: UpdateActorRequest) -> Any:
    """Update actor metadata."""
    act = registry.update_actor(
        actor_id=actor_id,
        display_name=req.display_name,
        aliases=req.aliases,
        notes=req.notes,
        consent_flag=req.consent_flag,
    )
    if not act:
        raise HTTPException(status_code=404, detail="Actor not found.")
    return act


@app.delete("/api/v1/registry/actors/{actor_id}")
def delete_actor(actor_id: str) -> dict[str, str]:
    """Erase actor and all associated biometric voice vectors (GDPR Art. 9)."""
    ok = registry.delete_actor(actor_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Actor not found.")
    return {"status": "deleted", "id": actor_id}


@app.post("/api/v1/registry/actors/{actor_id}/enroll")
async def enroll_actor_clip(actor_id: str, file: UploadFile = File(...), lang: str = "en") -> dict[str, Any]:  # noqa: B008
    """Enroll a voice clip for an actor."""
    fname = file.filename or "clip.wav"
    tmp_path = Path(tempfile.gettempdir()) / fname
    with open(tmp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    success, msg, count = registry.enroll_clip(actor_id, tmp_path, language=lang)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"status": "enrolled", "message": msg, "enrolled_count": count}


@app.post("/api/v1/registry/actors/{actor_id}/merge")
def merge_actors(actor_id: str, req: MergeActorsRequest) -> Any:
    """Merge another actor into this one."""
    res = registry.merge_actors(target_id=actor_id, source_id=req.source_actor_id)
    if not res:
        raise HTTPException(status_code=400, detail="Merge failed. Verify both actor IDs exist.")
    return res


@app.post("/api/v1/sessions/{session_id}/corrections", status_code=status.HTTP_202_ACCEPTED)
def batch_corrections(session_id: str, req: BatchCorrectionsRequest) -> dict[str, Any]:
    """Submit human corrections batch (§11.2)."""
    return registry.apply_corrections(session_id, req.corrections)


@app.post("/api/v1/sessions/{session_id}/label")
def label_cluster(session_id: str, req: LabelClusterRequest) -> dict[str, Any]:
    """Map cluster to actor and optionally promote to voice profile."""
    if req.promote:
        act = registry.promote_cluster_to_actor(
            session_id=session_id,
            cluster_label=req.cluster,
            actor_name=req.actor_name,
            aliases=req.aliases,
        )
        return {"status": "promoted", "actor": act}
    else:
        found = db.get_actor_by_name(req.actor_name)
        assigned_actor = found if found is not None else db.create_actor(display_name=req.actor_name, aliases=req.aliases)
        registry.apply_corrections(
            session_id,
            [{"action": "reassign_speaker", "actor_id": assigned_actor.id, "cluster": req.cluster}],
        )
        return {"status": "labeled", "actor": assigned_actor}

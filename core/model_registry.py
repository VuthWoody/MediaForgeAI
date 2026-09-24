"""Declarative registry and specification for on-demand downloadable AI models."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from core.cancellation import CancellationToken
from core.exceptions import ValidationError


@dataclass(frozen=True)
class ModelSpec:
    """Specification of an on-demand AI model asset."""

    id: str
    name: str
    url: str
    sha256: str
    size_mb: int
    dest: str
    description: str = ""


# Locked model registry as per Section 5.8
MODELS: dict[str, ModelSpec] = {
    "whisper-small": ModelSpec(
        id="whisper-small",
        name="Whisper Small",
        url="https://huggingface.co/Systran/faster-whisper-small/resolve/main/model.bin",
        sha256="e927c3a4ec0e7e1efcae5ef56b9c9f0b12c8b746813e3ecb2a4df65a7e937d59",
        size_mb=460,
        dest="models/whisper/small",
        description="CPU-friendly multi-lingual faster-whisper small model",
    ),
    "whisper-large-v3-turbo": ModelSpec(
        id="whisper-large-v3-turbo",
        name="Whisper Large v3 Turbo",
        url="https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2/resolve/main/model.bin",
        sha256="5d6e27ab6f675f0a7e02e0df2944b207576f3f01c87e4162e08819e917d84d7a",
        size_mb=1600,
        dest="models/whisper/large-v3-turbo",
        description="Opt-in high-accuracy whisper large-v3-turbo model",
    ),
    "mdx-inst-hq3": ModelSpec(
        id="mdx-inst-hq3",
        name="UVR MDX-Net Inst HQ 3",
        url="https://github.com/TRvlvr/model_repo/releases/download/all_public_uvr_models/UVR-MDX-NET-Inst_HQ_3.onnx",
        sha256="15df20c571765c5c0c9769db00569a93dd41a9956efb9bb4787a4ffae1a30f36",
        size_mb=120,
        dest="models/mdx/UVR-MDX-NET-Inst_HQ_3.onnx",
        description="MDX-Net ONNX stem separation model for vocals/instrumental isolation on CPU/GPU",
    ),
    "demucs-htdemucs-ft": ModelSpec(
        id="demucs-htdemucs-ft",
        name="HTDemucs Fine-Tuned",
        url="https://dl.fbaipublicfiles.com/demucs/hybrid_transformer/f7e0c4bc-ba3fe64a.th",
        sha256="f7e0c4bce968c9ff096fcfb036579c2980fa2a9404bb152ce8a30eb8a5d3f234",
        size_mb=320,
        dest="models/demucs/htdemucs_ft",
        description="Demucs 4-stem separation model (strict GPU-exclusive mode)",
    ),
    "embedding-clustering": ModelSpec(
        id="embedding-clustering",
        name="Voice Embedding Clustering",
        url="https://huggingface.co/pyannote/embedding/resolve/main/pytorch_model.bin",
        sha256="a28b030b42fbb1b93f1faec1cb53a5477bcf4d1a499d63c457f9ea3f56eb72f1",
        size_mb=90,
        dest="models/embedding/clustering",
        description="Speaker diarization voice-embedding clustering model",
    ),
}


class ModelRegistry:
    """Manages AI model metadata, verification, and on-demand pull coordination."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Path(__file__).resolve().parent.parent

    def get_spec(self, model_id: str) -> ModelSpec:
        """Fetch specification for a model identifier."""
        if model_id not in MODELS:
            raise ValidationError(f"Unknown model identifier '{model_id}'. Available: {list(MODELS.keys())}")
        return MODELS[model_id]

    def get_path(self, model_id: str) -> Path:
        """Get absolute destination path for a given model."""
        spec = self.get_spec(model_id)
        return self.base_dir / spec.dest

    def is_available(self, model_id: str) -> bool:
        """Check whether the model file or directory exists locally."""
        path = self.get_path(model_id)
        return path.exists()

    def verify_checksum(self, file_path: Path, expected_sha256: str) -> bool:
        """Verify SHA256 checksum of a file."""
        if not file_path.is_file():
            return False
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest().lower() == expected_sha256.lower()

    def ensure(
        self,
        model_id: str,
        progress_cb: Callable[[float, str], None] | None = None,
        token: CancellationToken | None = None,
    ) -> Path:
        """Idempotent model check. In Phase 0, checks local presence only (downloads activate in Phase 4)."""
        spec = self.get_spec(model_id)
        path = self.get_path(model_id)
        if token is not None:
            token.throw_if_cancelled()
        if progress_cb is not None:
            progress_cb(1.0 if path.exists() else 0.0, f"Model {spec.name} status checked")
        return path

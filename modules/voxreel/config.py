"""VoxReel Configuration Module.

Defines all configuration dataclasses matching §10.1 of VOX_engine_Plan.md.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]


@dataclass
class AudioConfig:
    target_sr: int = 16000
    channels: str = "center_or_mono"  # center channel preferred on 5.1+
    loudness_target_lufs: float = -23.0
    separation_enabled_for_video: bool = True
    separation_model: str = "htdemucs"
    stems_to_keep: list[str] = field(default_factory=lambda: ["vocals"])


@dataclass
class VadConfig:
    model: str = "silero-vad-v5"
    min_speech_ms: int = 250
    min_silence_ms: int = 150


@dataclass
class DiarizationConfig:
    segmentation: str = "pyannote/segmentation-3.0"
    embedding: str = "ecapa-tdnn-voxceleb-v2"  # 192-d or 512-d
    clustering: str = "agglomerative"
    distance_threshold: str = "auto"
    overlap_detection: bool = True
    min_cluster_utterances: int = 3


@dataclass
class AsrConfig:
    model: str = "small"  # small (fast, cached), base, tiny, large-v3
    compute_type: str = "int8"  # int8 on CPU
    beam_size: int = 5
    word_timestamps: bool = True
    vad_filter: bool = True


@dataclass
class RegistryConfig:
    auto_assign_threshold: float = 0.82  # cosine similarity >= 0.82
    review_band_min: float = 0.70       # 0.70 <= score < 0.82
    review_band_max: float = 0.82
    new_speaker_threshold: float = 0.70 # < 0.70 -> new speaker
    min_enroll_snr_db: float = 12.0
    min_enroll_duration_s: float = 1.5
    max_profile_embeddings: int = 50
    dedupe_cosine: float = 0.98          # near-identical embeddings dropped


@dataclass
class VoxReelConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    diarization: DiarizationConfig = field(default_factory=DiarizationConfig)
    asr: AsrConfig = field(default_factory=AsrConfig)
    registry: RegistryConfig = field(default_factory=RegistryConfig)
    vault_dir: str = ""  # Default empty, resolved to user data or local directory

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> VoxReelConfig:
        cfg = cls()
        if "audio" in data and isinstance(data["audio"], dict):
            for k, v in data["audio"].items():
                if hasattr(cfg.audio, k):
                    setattr(cfg.audio, k, v)
        if "vad" in data and isinstance(data["vad"], dict):
            for k, v in data["vad"].items():
                if hasattr(cfg.vad, k):
                    setattr(cfg.vad, k, v)
        if "diarization" in data and isinstance(data["diarization"], dict):
            for k, v in data["diarization"].items():
                if hasattr(cfg.diarization, k):
                    setattr(cfg.diarization, k, v)
        if "asr" in data and isinstance(data["asr"], dict):
            for k, v in data["asr"].items():
                if hasattr(cfg.asr, k):
                    setattr(cfg.asr, k, v)
        if "registry" in data and isinstance(data["registry"], dict):
            for k, v in data["registry"].items():
                if hasattr(cfg.registry, k):
                    setattr(cfg.registry, k, v)
        if "vault_dir" in data:
            cfg.vault_dir = str(data["vault_dir"])
        return cfg

    @classmethod
    def from_yaml(cls, path: str | Path) -> VoxReelConfig:
        p = Path(path)
        if not p.exists():
            return cls()
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)

    def to_yaml(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=False)

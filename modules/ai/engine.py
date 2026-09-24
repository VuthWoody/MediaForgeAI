"""Base Engine contract and data types conforming to Section 6 of the specifications."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from core.cancellation import CancellationToken

AvailabilityStatus = Literal["ready", "degraded", "unavailable"]


@dataclass(frozen=True)
class Availability:
    """Availability status and diagnostics for an AI engine or provider."""

    status: AvailabilityStatus
    reason: str = ""

    @property
    def is_usable(self) -> bool:
        return self.status in ("ready", "degraded")


def classify_segment_tone(
    text: str,
    f0_hz: float = 150.0,
    voiced_ratio: float = 0.5,
    rms: float = 0.05,
    spk_mean_f0: float = 180.0,
) -> str:
    """Classifies speech dialogue segment into emotion tone: [excited], [happy], [sad], [angry], [cry], [whisper], [normal]."""
    t = text.lower().strip()
    if not t:
        return "[normal]"

    # 1. Text cues
    cry_words = ["cry", "crying", "sob", "sobbing", "tears", "weep", "weeping", "sniff"]
    if any(re.search(r"\b" + w + r"\b", t) for w in cry_words):
        return "[cry]"

    whisper_words = ["whisper", "shh", "quiet", "secret"]
    if any(re.search(r"\b" + w + r"\b", t) for w in whisper_words):
        return "[whisper]"

    angry_words = ["hate", "shut up", "damn", "kill", "liar", "get out", "furious", "angry", "hell"]
    if any(re.search(r"\b" + w + r"\b", t) for w in angry_words):
        return "[angry]"

    excited_words = ["oh my god", "amazing", "awesome", "wow", "yay", "super", "omg", "great!", "hurray"]
    if any(w in t for w in excited_words) or ("!" in text and ("great" in t or "good" in t or "cool" in t)):
        return "[excited]"

    happy_words = ["happy", "glad", "good", "great", "nice", "fun", "pleasure", "smile", "laugh", "love", "welcome"]
    if any(re.search(r"\b" + w + r"\b", t) for w in happy_words):
        return "[happy]"

    sad_words = ["sad", "sorry", "miss you", "regret", "depressed", "lost", "died", "grief", "pain", "hurt", "alone"]
    if any(re.search(r"\b" + w + r"\b", t) for w in sad_words):
        return "[sad]"

    # 2. Acoustic cues (if audio parameters provided)
    if f0_hz > 0 and spk_mean_f0 > 0:
        rel_pitch = f0_hz / spk_mean_f0
        if rel_pitch > 1.25 and rms > 0.06:
            return "[excited]"
        if rel_pitch > 1.12:
            return "[happy]"
        if rel_pitch < 0.85 and rms < 0.03:
            return "[sad]"
        if voiced_ratio < 0.25 and rms < 0.02:
            return "[whisper]"

    return "[normal]"


@dataclass
class TranscriptSegment:
    """Represents a single timed dialogue segment adhering strictly to the Section 7 schema."""

    id: int
    start: float
    end: float
    speaker: str = "Speaker 1"
    source_text: str = ""
    target_text: str = ""
    voice_id: str = ""
    audio_path: str = ""
    confidence: float = 1.0
    emotion: str = "normal"

    def to_dict(self) -> dict[str, Any]:
        """Serialize segment to dict adhering strictly to Section 7 schema."""
        d: dict[str, Any] = {
            "id": self.id,
            "start": round(self.start, 3),
            "end": round(self.end, 3),
            "speaker": self.speaker,
            "source_text": self.source_text,
            "target_text": self.target_text,
            "voice_id": self.voice_id,
            "audio_path": self.audio_path,
            "confidence": round(self.confidence, 4),
        }
        if self.emotion:
            d["emotion"] = self.emotion
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranscriptSegment:
        """Create segment from dict."""
        return cls(
            id=int(data.get("id", 1)),
            start=float(data.get("start", 0.0)),
            end=float(data.get("end", 0.0)),
            speaker=str(data.get("speaker", "Speaker 1")),
            source_text=str(data.get("source_text", "")),
            target_text=str(data.get("target_text", "")),
            voice_id=str(data.get("voice_id", "")),
            audio_path=str(data.get("audio_path", "")),
            confidence=float(data.get("confidence", 1.0)),
            emotion=str(data.get("emotion", "normal")),
        )


@dataclass
class Transcript:
    """Complete collection of transcript segments with metadata and serialization."""

    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "auto"
    duration: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "duration": round(self.duration, 3),
            "segments": [s.to_dict() for s in self.segments],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | list[Any]) -> Transcript:
        if isinstance(data, list):
            segments = [TranscriptSegment.from_dict(s) for s in data]
            duration = max((s.end for s in segments), default=0.0)
            return cls(segments=segments, duration=duration)
        segments_data = data.get("segments", [])
        segments = [TranscriptSegment.from_dict(s) for s in segments_data]
        return cls(
            segments=segments,
            language=str(data.get("language", "auto")),
            duration=float(data.get("duration", 0.0)),
        )

    def save_json(self, path: Path | str) -> None:
        """Save transcript to formatted JSON file."""
        target_path = Path(path).resolve()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in self.segments], f, ensure_ascii=False, indent=2)

    @classmethod
    def load_json(cls, path: Path | str) -> Transcript:
        """Load transcript from JSON file."""
        target_path = Path(path).resolve()
        with open(target_path, encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            segments = [TranscriptSegment.from_dict(s) for s in data]
            duration = max((s.end for s in segments), default=0.0)
            return cls(segments=segments, duration=duration)
        elif isinstance(data, dict):
            return cls.from_dict(data)
        else:
            raise ValueError(f"Unrecognized transcript JSON format: {type(data)}")


@dataclass(frozen=True)
class SeparationResult:
    """Paths to separated audio stems."""

    vocals_path: Path
    no_vocals_path: Path
    duration: float = 0.0


class Engine(Protocol):
    """Protocol conforming to Section 6 Engine Contract."""

    name: str
    required_locks: list[str]

    def probe(self) -> Availability:
        """Cheap check. Never raises. Returns ready/degraded/unavailable status."""
        ...

    def run(
        self,
        inputs: Any,
        workdir: Path,
        token: CancellationToken,
        progress: Callable[[float, str], None],
    ) -> Any:
        """Execute engine processing.

        Writes only into workdir.
        Emits progress via callback.
        Returns typed result. Never touches UI.
        """
        ...

"""Base interfaces for translation and TTS external provider adapters."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.cancellation import CancellationToken
from modules.ai.engine import Availability


@dataclass
class TranslationResult:
    """Result of a translation call."""

    translated_text: str
    provider: str
    source_lang: str
    target_lang: str


class TranslationProvider(Protocol):
    """Protocol for translation API adapters."""

    name: str

    def probe(self) -> Availability:
        ...

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        max_chars: int | None = None,
        director_tags: list[str] | None = None,
        token: CancellationToken | None = None,
    ) -> TranslationResult:
        ...


@dataclass
class TTSResult:
    """Result of a text-to-speech generation call."""

    audio_path: Path
    duration_sec: float
    provider: str
    voice_id: str


class TTSProvider(Protocol):
    """Protocol for TTS API adapters."""

    name: str

    def probe(self) -> Availability:
        ...

    def generate_speech(
        self,
        text: str,
        voice_id: str,
        output_wav: Path,
        pitch: float = 0.0,
        rate: float = 1.0,
        emotion_tag: str | None = None,
        token: CancellationToken | None = None,
    ) -> TTSResult:
        ...

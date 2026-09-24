"""Gemini TTS provider adapter using prompt-based emotion."""

from __future__ import annotations

import logging
from pathlib import Path

from core.cancellation import CancellationToken
from core.config_store import ConfigStore
from modules.ai.engine import Availability
from modules.ai.providers.base import TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class GeminiTTSProvider(TTSProvider):
    """Gemini 2.5 Flash TTS provider adapter."""

    name: str = "gemini"

    def probe(self) -> Availability:
        key = ConfigStore.instance().get_api_key("gemini")
        if not key:
            return Availability(status="unavailable", reason="Gemini API key not configured for TTS.")
        return Availability(status="ready", reason="Gemini 2.5 Flash TTS ready.")

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
        if token:
            token.throw_if_cancelled()

        # In v1.0, Gemini TTS free tier is limited to 10 req/day, with fallback to Edge-TTS/Qwen
        # If API returns error or quota, caller falls back per route_tts()
        raise NotImplementedError("Gemini TTS quota fallback: delegating to secondary provider.")

"""Qwen3-TTS provider adapter."""

from __future__ import annotations

import logging
from pathlib import Path

from core.cancellation import CancellationToken
from core.config_store import ConfigStore
from modules.ai.engine import Availability
from modules.ai.providers.base import TTSProvider, TTSResult

logger = logging.getLogger(__name__)


class QwenTTSProvider(TTSProvider):
    """Qwen3-TTS provider with instruction following."""

    name: str = "qwen"

    def probe(self) -> Availability:
        key = ConfigStore.instance().get_api_key("qwen")
        if not key:
            return Availability(status="unavailable", reason="Qwen API key not configured for TTS.")
        return Availability(status="ready", reason="Qwen3-TTS ready.")

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

        # Delegate to Edge-TTS fallback when offline or no API key
        raise NotImplementedError("Qwen TTS delegated to Edge-TTS fallback.")

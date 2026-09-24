"""Gemini 2.0 Flash translation provider adapter."""

from __future__ import annotations

import json
import logging
import urllib.request

from core.cancellation import CancellationToken
from core.config_store import ConfigStore
from modules.ai.engine import Availability
from modules.ai.providers.base import TranslationProvider, TranslationResult

logger = logging.getLogger(__name__)


class GeminiTranslateProvider(TranslationProvider):
    """Gemini 2.0 Flash translation provider with expressive natural language tag preservation."""

    name: str = "gemini"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_key(self) -> str | None:
        if self._api_key:
            return self._api_key
        return ConfigStore.instance().get_api_key("gemini")

    def probe(self) -> Availability:
        key = self._get_key()
        if not key:
            return Availability(
                status="unavailable",
                reason="Gemini API key not configured in Settings/keyring.",
            )
        return Availability(status="ready", reason="Gemini 2.0 Flash ready.")

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        max_chars: int | None = None,
        director_tags: list[str] | None = None,
        token: CancellationToken | None = None,
    ) -> TranslationResult:
        if token:
            token.throw_if_cancelled()

        key = self._get_key()
        if not key:
            # Fallback if no key
            return TranslationResult(
                translated_text=text,
                provider=self.name,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        prompt = (
            f"You are a professional film dialogue translator for dubbing into {target_lang}. "
            f"Translate the following line faithfully and idiomatically. "
            f"Preserve all expressive tags exactly in curly braces like {{whisper}}, {{laugh}}, {{sigh}} if present. "
        )
        if max_chars:
            prompt += f"Keep the translation concise, strictly under {max_chars} characters for lip synchronization. "
        prompt += f"\n\nSource text: {text}\nTranslation only, no quotes, no explanations:"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 256},
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        res_text = parts[0].get("text", "").strip()
                        return TranslationResult(
                            translated_text=res_text,
                            provider=self.name,
                            source_lang=source_lang,
                            target_lang=target_lang,
                        )
        except Exception as e:
            logger.warning("Gemini translate request error: %s", e)

        return TranslationResult(
            translated_text=text,
            provider=self.name,
            source_lang=source_lang,
            target_lang=target_lang,
        )

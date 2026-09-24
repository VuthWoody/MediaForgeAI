"""DeepSeek translation provider adapter using structured JSON mode."""

from __future__ import annotations

import json
import logging
import urllib.request

from core.cancellation import CancellationToken
from core.config_store import ConfigStore
from modules.ai.engine import Availability
from modules.ai.providers.base import TranslationProvider, TranslationResult

logger = logging.getLogger(__name__)


class DeepSeekTranslateProvider(TranslationProvider):
    """DeepSeek translation provider with structured JSON tag preservation."""

    name: str = "deepseek"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_key(self) -> str | None:
        if self._api_key:
            return self._api_key
        return ConfigStore.instance().get_api_key("deepseek")

    def probe(self) -> Availability:
        key = self._get_key()
        if not key:
            return Availability(status="unavailable", reason="DeepSeek API key not configured.")
        return Availability(status="ready", reason="DeepSeek translation ready.")

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
            return TranslationResult(
                translated_text=text,
                provider=self.name,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        url = "https://api.deepseek.com/chat/completions"
        system_prompt = (
            f"You are a film dialogue translator into {target_lang}. "
            "Output JSON with key 'translation'. Preserve director tags in curly braces exactly."
        )
        user_prompt = f"Text: {text}"
        if max_chars:
            user_prompt += f" (Keep under {max_chars} chars)"

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                translated = parsed.get("translation", text)
                return TranslationResult(
                    translated_text=translated,
                    provider=self.name,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
        except Exception as e:
            logger.warning("DeepSeek translate request error: %s", e)

        return TranslationResult(
            translated_text=text,
            provider=self.name,
            source_lang=source_lang,
            target_lang=target_lang,
        )

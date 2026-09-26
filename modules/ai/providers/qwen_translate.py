"""Qwen translation provider adapter."""

from __future__ import annotations

import json
import logging
import urllib.request

from core.cancellation import CancellationToken
from core.config_store import ConfigStore
from modules.ai.engine import Availability
from modules.ai.providers.base import TranslationProvider, TranslationResult

logger = logging.getLogger(__name__)


class QwenTranslateProvider(TranslationProvider):
    """Qwen translation provider."""

    name: str = "qwen"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key

    def _get_key(self) -> str | None:
        if self._api_key:
            return self._api_key
        return ConfigStore.instance().get_api_key("qwen")

    def probe(self) -> Availability:
        key = self._get_key()
        if not key:
            return Availability(status="unavailable", reason="Qwen API key not configured.")
        return Availability(status="ready", reason="Qwen translation ready.")

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

        key = ConfigStore.instance().get_api_key("qwen")
        if not key:
            return TranslationResult(
                translated_text=text,
                provider=self.name,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        if target_lang.lower() in ("km", "khmer"):
            system_msg = (
                "You are an expert Cambodian movie dubbing director specializing in Natural Spoken Khmer (ភាសានិយាយភាពយន្តបែបធម្មជាតិ). "
                "Translate into natural, conversational, fluent cinema Khmer. Avoid literal dictionary phrasing. "
                "Use conversational pronouns ('ខ្ញុំ / ឯង / ពួកយើង / ឈ្មោះ') and spoken particles (ណ៎, ហ្នឹង, ណា៎, តើ, អត់, ហ្អ៎, ម៉េស, ទេ). "
                "Preserve director tags in curly braces like {whisper}, {laugh} exactly."
            )
            user_msg = f"Dialogue: {text}"
            if max_chars:
                user_msg += f" (Keep strictly under {max_chars} chars for lip-sync)"
        else:
            system_msg = f"你是一名专业的影视配音翻译专家，请将台词翻译成{target_lang}。保留大括号中的表情/导演标签如{{whisper}}、{{laugh}}。"
            user_msg = f"台词：{text}"
            if max_chars:
                user_msg += f"（严格限制在{max_chars}字以内）"

        payload = {
            "model": "qwen-turbo",
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
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
                translated = data["choices"][0]["message"]["content"].strip()
                return TranslationResult(
                    translated_text=translated,
                    provider=self.name,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
        except Exception as e:
            logger.warning("Qwen translate request error: %s", e)

        return TranslationResult(
            translated_text=text,
            provider=self.name,
            source_lang=source_lang,
            target_lang=target_lang,
        )

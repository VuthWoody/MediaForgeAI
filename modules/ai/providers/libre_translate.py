"""LibreTranslate free provider adapter for offline/fallback translation."""

from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request

from core.cancellation import CancellationToken
from modules.ai.engine import Availability
from modules.ai.providers.base import TranslationProvider, TranslationResult

logger = logging.getLogger(__name__)


class LibreTranslateProvider(TranslationProvider):
    """Fallback translation provider stripping tags and returning clean translated text."""

    name: str = "libre"

    def __init__(self, endpoint_url: str = "https://translate.argosopentech.com/translate") -> None:
        self.endpoint_url = endpoint_url

    def probe(self) -> Availability:
        return Availability(status="ready", reason="LibreTranslate free endpoint available.")

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

        # Rule: LibreTranslate strips tags and logs
        clean_text = re.sub(r"\{[a-zA-Z0-9_:]+\}", "", text).strip()
        if not clean_text:
            return TranslationResult(
                translated_text="",
                provider=self.name,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        # Map common codes
        s_code = source_lang[:2].lower() if source_lang != "auto" else "auto"
        t_code = target_lang[:2].lower()

        # Try LibreTranslate endpoint first with a responsive timeout
        try:
            req_data = json.dumps({
                "q": clean_text,
                "source": s_code,
                "target": t_code,
                "format": "text",
            }).encode("utf-8")

            req = urllib.request.Request(
                self.endpoint_url,
                data=req_data,
                headers={"Content-Type": "application/json", "User-Agent": "MediaForgeAI/1.0"},
            )

            with urllib.request.urlopen(req, timeout=4) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                translated = data.get("translatedText", clean_text)
                return TranslationResult(
                    translated_text=translated,
                    provider=self.name,
                    source_lang=source_lang,
                    target_lang=target_lang,
                )
        except Exception as e:
            logger.debug("LibreTranslate endpoint unreachable (%s); attempting Google GTX fallback.", e)

        # Fast free fallback: Google Translate GTX web endpoint
        try:
            q_enc = urllib.parse.quote(clean_text)
            gtx_url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={s_code}&tl={t_code}&dt=t&q={q_enc}"
            req_gtx = urllib.request.Request(gtx_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_gtx, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                chunks = [seg[0] for seg in data[0] if seg and seg[0]]
                translated = "".join(chunks)
                if translated:
                    return TranslationResult(
                        translated_text=translated,
                        provider="libre_fallback",
                        source_lang=source_lang,
                        target_lang=target_lang,
                    )
        except Exception as e2:
            logger.warning("Free translation fallback failed: %s; returning original.", e2)

        return TranslationResult(
            translated_text=clean_text,
            provider=self.name,
            source_lang=source_lang,
            target_lang=target_lang,
        )

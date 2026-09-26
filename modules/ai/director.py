"""Director module handling tag DSL parsing, timing calculation, and multi-provider translation."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable

from core.cancellation import CancellationToken
from modules.ai.engine import Transcript, TranscriptSegment
from modules.ai.khmer_localizer import KhmerDialogueLocalizer
from modules.ai.providers.base import TranslationProvider, TranslationResult
from modules.ai.providers.deepseek_translate import DeepSeekTranslateProvider
from modules.ai.providers.gemini_translate import GeminiTranslateProvider
from modules.ai.providers.libre_translate import LibreTranslateProvider
from modules.ai.providers.qwen_translate import QwenTranslateProvider

logger = logging.getLogger(__name__)

# Locked Director Tag DSL: {whisper} {laugh} {sob} {shout:angry} {sigh} {gasp} {cry}
VALID_TAGS: set[str] = {
    "whisper",
    "laugh",
    "sob",
    "shout:angry",
    "sigh",
    "gasp",
    "cry",
}

CHARS_PER_SEC: dict[str, float] = {
    "en": 15.0,
    "km": 10.0,
    "zh": 4.0,
    "ja": 5.0,
    "ko": 6.0,
}


def route_translate() -> list[str]:
    """Locked translation routing table as per Section 3.2."""
    return ["gemini", "deepseek", "qwen", "libre"]


class DirectorManager:
    """Manages expressive director tags and translation orchestration."""

    def __init__(self) -> None:
        self.providers: dict[str, TranslationProvider] = {
            "gemini": GeminiTranslateProvider(),
            "deepseek": DeepSeekTranslateProvider(),
            "qwen": QwenTranslateProvider(),
            "libre": LibreTranslateProvider(),
        }

    @staticmethod
    def extract_tags(text: str) -> list[str]:
        """Extract all valid expressive director tags from text."""
        matches = re.findall(r"\{([a-zA-Z0-9_:]+)\}", text)
        return [m for m in matches if m in VALID_TAGS or m.startswith("shout:")]

    @staticmethod
    def strip_tags(text: str) -> str:
        """Strip all curly bracket director tags from text."""
        return re.sub(r"\{[a-zA-Z0-9_:]+\}", "", text).strip()

    @staticmethod
    def calculate_max_chars(duration: float, target_lang: str) -> int:
        """Calculate max character constraint for lip-sync timing."""
        rate = CHARS_PER_SEC.get(target_lang.lower(), 12.0)
        return max(4, int(duration * rate))

    def translate_line(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
        max_chars: int | None = None,
        token: CancellationToken | None = None,
        preferred_provider: str | None = None,
        speaker_gender: str = "auto",
        speaker_name: str | None = None,
    ) -> TranslationResult:
        """Translate a single line trying providers according to the locked routing table."""
        tags = self.extract_tags(text)

        providers_order = route_translate()
        if preferred_provider and preferred_provider in self.providers:
            providers_order = [preferred_provider] + [p for p in providers_order if p != preferred_provider]

        result: TranslationResult | None = None

        for provider_name in providers_order:
            provider = self.providers.get(provider_name)
            if not provider:
                continue

            try:
                avail = provider.probe()
                if not avail.is_usable:
                    continue
            except Exception as e:
                logger.debug("Provider %s probe failed: %s; trying next.", provider_name, e)
                continue

            try:
                res = provider.translate(
                    text=text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    max_chars=max_chars,
                    director_tags=tags,
                    token=token,
                )
                if res.translated_text and res.translated_text != text:
                    result = res
                    break
            except Exception as e:
                logger.warning("Provider %s failed translation: %s; trying next.", provider_name, e)

        if not result:
            result = TranslationResult(
                translated_text=text,
                provider="fallback",
                source_lang=source_lang,
                target_lang=target_lang,
            )

        # Automatic Natural Conversational Khmer Post-Processing
        if target_lang.lower() in ("km", "khmer") and result.translated_text:
            result.translated_text = KhmerDialogueLocalizer.naturalize(
                result.translated_text,
                speaker_gender=speaker_gender,
                speaker_name=speaker_name,
            )

        return result

    def translate_transcript(
        self,
        transcript: Transcript,
        target_lang: str,
        token: CancellationToken | None = None,
        progress: Callable[[float, str], None] | None = None,
        preferred_provider: str | None = None,
        provider_name: str | None = None,
    ) -> Transcript:
        """Translate all segments in a transcript, preserving timestamps and updating target_text."""
        effective_provider = preferred_provider or provider_name
        segments = transcript.segments
        total = len(segments)
        if total == 0:
            return transcript

        source_lang = transcript.language or "auto"
        translated_segments: list[TranscriptSegment] = []

        for idx, seg in enumerate(segments):
            if token:
                token.throw_if_cancelled()

            dt_orig = max(0.5, seg.end - seg.start)
            max_chars = self.calculate_max_chars(dt_orig, target_lang)
            spk = getattr(seg, "speaker", None)
            gender = KhmerDialogueLocalizer.detect_gender(spk)

            res = self.translate_line(
                text=seg.source_text,
                source_lang=source_lang,
                target_lang=target_lang,
                max_chars=max_chars,
                token=token,
                preferred_provider=effective_provider,
                speaker_gender=gender,
                speaker_name=spk,
            )

            seg.target_text = res.translated_text
            translated_segments.append(seg)

            if progress:
                prog = (idx + 1) / total
                progress(prog, f"Translated line {idx + 1}/{total} -> {target_lang}")

        return Transcript(
            segments=translated_segments,
            language=target_lang,
            duration=transcript.duration,
        )

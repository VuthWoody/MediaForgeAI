"""Voice Generator module managing TTS routing, speaker assignment, and audio segment caching."""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from typing import Any

from core.cancellation import CancellationToken
from modules.ai.providers.base import TTSProvider, TTSResult
from modules.ai.providers.edge_tts import EdgeTTSProvider
from modules.ai.providers.gemini_tts import GeminiTTSProvider
from modules.ai.providers.qwen_tts import QwenTTSProvider
from modules.ai.providers.voxcpm_tts import VoxCPMProvider
from modules.media.inspector import MediaInspector

logger = logging.getLogger(__name__)


def route_tts(target_lang: str) -> list[str]:
    """Locked TTS routing table per Section 3 specification."""
    lang = target_lang.lower()
    if lang in ("km", "khmer"):
        return ["edge", "qwen"]
    if lang in ("zh", "chinese"):
        return ["qwen", "edge", "gemini"]
    return ["gemini", "qwen", "edge"]


# Comprehensive multi-speaker voice configuration presets with acoustic personalization
SPEAKER_VOICE_PROFILES: dict[str, dict[str, dict[str, Any]]] = {
    "km": {
        "Speaker 1": {"voice": "km-KH-PisethNeural", "pitch": 0.0, "rate": 1.00, "role": "Male Lead"},
        "Speaker 2": {"voice": "km-KH-SreymomNeural", "pitch": 0.0, "rate": 1.00, "role": "Female Lead"},
        "Speaker 3": {"voice": "km-KH-PisethNeural", "pitch": -1.2, "rate": 0.94, "role": "Deep Male / Antagonist"},
        "Speaker 4": {"voice": "km-KH-SreymomNeural", "pitch": -0.8, "rate": 0.96, "role": "Mature Female / Mother"},
        "Speaker 5": {"voice": "km-KH-PisethNeural", "pitch": 1.2, "rate": 1.04, "role": "Young Male / Youth"},
        "Speaker 6": {"voice": "km-KH-SreymomNeural", "pitch": 1.0, "rate": 1.04, "role": "Young Female / Maiden"},
        "Speaker 7": {"voice": "km-KH-SreymomNeural", "pitch": 2.8, "rate": 1.10, "role": "Child / Kid"},
        "Speaker 8": {"voice": "km-KH-PisethNeural", "pitch": -1.6, "rate": 0.88, "role": "Elderly Male / Grandfather"},
        "Speaker 9": {"voice": "km-KH-SreymomNeural", "pitch": -1.4, "rate": 0.88, "role": "Elderly Female / Grandmother"},
        "Speaker 10": {"voice": "km-KH-PisethNeural", "pitch": -0.4, "rate": 0.92, "role": "Narrator / Announcer"},
        "default": {"voice": "km-KH-PisethNeural", "pitch": 0.0, "rate": 1.00, "role": "Default"},
    },
    "zh": {
        "Speaker 1": {"voice": "zh-CN-YunjianNeural", "pitch": 0.0, "rate": 1.00, "role": "Male Lead (Actor)"},
        "Speaker 2": {"voice": "zh-CN-XiaoxiaoNeural", "pitch": 0.0, "rate": 1.00, "role": "Female Lead (Warm)"},
        "Speaker 3": {"voice": "zh-CN-YunxiNeural", "pitch": 0.0, "rate": 1.03, "role": "Young Male (Lively)"},
        "Speaker 4": {"voice": "zh-CN-XiaoyiNeural", "pitch": 0.0, "rate": 1.03, "role": "Young Female (Bright)"},
        "Speaker 5": {"voice": "zh-CN-YunfengNeural", "pitch": -0.6, "rate": 0.95, "role": "Mature Male (Father)"},
        "Speaker 6": {"voice": "zh-CN-YunjiaNeural", "pitch": -0.5, "rate": 0.96, "role": "Mature Female (Mother)"},
        "Speaker 7": {"voice": "zh-CN-XiaoshuangNeural", "pitch": 1.0, "rate": 1.08, "role": "Child (Authentic Girl/Boy)"},
        "Speaker 8": {"voice": "zh-CN-YunyangNeural", "pitch": -1.2, "rate": 0.90, "role": "Elderly Male (Grandpa)"},
        "Speaker 9": {"voice": "zh-CN-XiaohanNeural", "pitch": -1.0, "rate": 0.90, "role": "Elderly Female (Grandma)"},
        "Speaker 10": {"voice": "zh-CN-YunyangNeural", "pitch": 0.0, "rate": 0.95, "role": "Narrator (News Anchor)"},
        "default": {"voice": "zh-CN-XiaoxiaoNeural", "pitch": 0.0, "rate": 1.00, "role": "Default"},
    },
    "en": {
        "Speaker 1": {"voice": "en-US-GuyNeural", "pitch": 0.0, "rate": 1.00, "role": "Male Lead"},
        "Speaker 2": {"voice": "en-US-JennyNeural", "pitch": 0.0, "rate": 1.00, "role": "Female Lead"},
        "Speaker 3": {"voice": "en-US-JasonNeural", "pitch": 0.0, "rate": 1.04, "role": "Young Male"},
        "Speaker 4": {"voice": "en-US-AriaNeural", "pitch": 0.0, "rate": 1.02, "role": "Young Female"},
        "Speaker 5": {"voice": "en-US-DavisNeural", "pitch": -0.6, "rate": 0.95, "role": "Mature Male"},
        "Speaker 6": {"voice": "en-US-SaraNeural", "pitch": -0.5, "rate": 0.96, "role": "Mature Female"},
        "Speaker 7": {"voice": "en-US-AnaNeural", "pitch": 1.0, "rate": 1.08, "role": "Child Voice"},
        "Speaker 8": {"voice": "en-US-TonyNeural", "pitch": -1.2, "rate": 0.90, "role": "Elderly / Authoritative Male"},
        "Speaker 9": {"voice": "en-US-NancyNeural", "pitch": -1.0, "rate": 0.90, "role": "Elderly Female"},
        "Speaker 10": {"voice": "en-US-ChristopherNeural", "pitch": 0.0, "rate": 0.95, "role": "Narrator"},
        "default": {"voice": "en-US-JennyNeural", "pitch": 0.0, "rate": 1.00, "role": "Default"},
    },
}

SPEAKER_VOICE_PRESETS: dict[str, dict[str, str]] = {
    lang: {spk: cfg["voice"] for spk, cfg in spk_dict.items()}
    for lang, spk_dict in SPEAKER_VOICE_PROFILES.items()
}


class VoiceGenerator:
    """Dispatches TTS requests across providers with hash-based caching."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = (
            Path(cache_dir).resolve()
            if cache_dir
            else Path.home() / "AppData" / "Local" / "MediaForgeAI" / "tts_cache"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.providers: dict[str, TTSProvider] = {
            "voxcpm": VoxCPMProvider(),
            "edge": EdgeTTSProvider(),
            "gemini": GeminiTTSProvider(),
            "qwen": QwenTTSProvider(),
        }

    def _get_cache_key(
        self,
        text: str,
        voice_id: str,
        provider: str,
        pitch: float,
        rate: float,
        ref_audio: Path | str | None = None,
    ) -> str:
        ref_tag = "noref"
        if ref_audio and Path(ref_audio).exists():
            try:
                st = Path(ref_audio).stat()
                ref_tag = f"{st.st_size}_{int(st.st_mtime)}"
            except Exception:
                ref_tag = str(ref_audio)
        raw = f"{text}_{voice_id}_{provider}_{pitch:.2f}_{rate:.2f}_{ref_tag}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def resolve_speaker_voice_settings(
        self, speaker: str, target_lang: str
    ) -> tuple[str, float, float]:
        """Resolve tailored (voice_id, pitch, rate) for any speaker string or character role."""
        lang = target_lang[:2].lower()
        profiles = SPEAKER_VOICE_PROFILES.get(lang, SPEAKER_VOICE_PROFILES["en"])

        raw_speaker = (speaker or "").strip()
        lower_spk = raw_speaker.lower()

        # 1. Child voice check (keyword in English, Chinese, Khmer)
        if any(w in lower_spk for w in ("child", "kid", "toddler", "boy", "girl", "小孩", "儿童", "孩子", "小女孩", "小男孩")):
            if "Speaker 7" in profiles:
                p = profiles["Speaker 7"]
                return p["voice"], p["pitch"], p["rate"]

        # 2. Elderly voice check
        if any(w in lower_spk for w in ("elderly", "grandmother", "grandma", "grandpa", "grandfather", "old", "老太太", "奶奶", "姥姥", "太婆")):
            if "Speaker 9" in profiles:
                p = profiles["Speaker 9"]
                return p["voice"], p["pitch"], p["rate"]
        if any(w in lower_spk for w in ("elderly male", "grandpa", "grandfather", "老头", "爷爷", "姥爷", "老汉", "太爷")):
            if "Speaker 8" in profiles:
                p = profiles["Speaker 8"]
                return p["voice"], p["pitch"], p["rate"]

        # 3. Explicit Gender / Persona classification (MUST check before raw 'Speaker N' index)
        if any(w in lower_spk for w in ("female", "woman", "mother", "lady", "mature female", "female lead", "女主", "女士", "妈妈", "夫人", "闺女")):
            if "mature" in lower_spk and "Speaker 4" in profiles:
                p = profiles["Speaker 4"]
            else:
                p = profiles.get("Speaker 2", profiles.get("default", profiles["Speaker 1"]))
            return p["voice"], p["pitch"], p["rate"]

        if any(w in lower_spk for w in ("deep male", "antagonist", "villain", "deep")):
            if "Speaker 3" in profiles:
                p = profiles["Speaker 3"]
                return p["voice"], p["pitch"], p["rate"]

        if any(w in lower_spk for w in ("male", "man", "father", "guy", "male lead", "男主", "先生", "爸爸", "少爷", "大人")):
            p = profiles.get("Speaker 1", profiles.get("default", profiles["Speaker 2"]))
            return p["voice"], p["pitch"], p["rate"]

        # 4. Fallback to explicit "Speaker N" tag if no explicit persona/gender was detected
        m = re.search(r"Speaker\s*(\d+)", raw_speaker, re.IGNORECASE)
        if m:
            spk_idx = int(m.group(1))
            mapped_key = f"Speaker {((spk_idx - 1) % 10) + 1}"
            if mapped_key in profiles:
                p = profiles[mapped_key]
                return p["voice"], p["pitch"], p["rate"]

        # 5. Fallback directly from profiles dict
        if raw_speaker in profiles:
            p = profiles[raw_speaker]
            return p["voice"], p["pitch"], p["rate"]

        default_prof = profiles.get("default", profiles["Speaker 1"])
        return default_prof["voice"], default_prof["pitch"], default_prof["rate"]

    def get_voice_for_speaker(self, speaker: str, target_lang: str) -> str:
        """Resolve preset voice ID for a given speaker and language."""
        voice_id, _, _ = self.resolve_speaker_voice_settings(speaker, target_lang)
        return voice_id

    def generate_speech(
        self,
        text: str,
        target_lang: str,
        speaker: str = "Speaker 1",
        output_wav: Path | None = None,
        voice_id: str | None = None,
        pitch: float | None = None,
        rate: float | None = None,
        emotion_tag: str | None = None,
        reference_audio: Path | str | None = None,
        actor_id: str | None = None,
        preferred_provider: str | None = None,
        token: CancellationToken | None = None,
    ) -> TTSResult:
        """Synthesize speech using VoxCPM2 zero-shot actor cloning or neural routing table with caching."""
        clean_text = text.strip()
        if not clean_text:
            raise ValueError("Cannot synthesize speech from empty text.")

        resolved_voice, resolved_pitch, resolved_rate = self.resolve_speaker_voice_settings(
            speaker, target_lang
        )
        selected_voice = voice_id or resolved_voice
        selected_pitch = pitch if pitch is not None else resolved_pitch
        selected_rate = rate if rate is not None else resolved_rate

        routing = route_tts(target_lang)
        if preferred_provider and preferred_provider in self.providers:
            routing = [preferred_provider] + [p for p in routing if p != preferred_provider]
        elif reference_audio is not None and "voxcpm" in self.providers:
            routing = ["voxcpm"] + [p for p in routing if p != "voxcpm"]

        # Check hash cache
        cache_key = self._get_cache_key(
            clean_text, selected_voice, routing[0], selected_pitch, selected_rate, ref_audio=reference_audio
        )
        cached_file = self.cache_dir / f"{cache_key}.wav"

        if cached_file.exists() and cached_file.stat().st_size > 0:
            meta = MediaInspector.probe(cached_file)
            logger.info("TTS Cache hit: %s", cached_file.name)
            if output_wav:
                output_wav.parent.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy2(cached_file, output_wav)
                return TTSResult(
                    audio_path=output_wav,
                    duration_sec=meta.duration,
                    provider="cache",
                    voice_id=selected_voice,
                )
            return TTSResult(
                audio_path=cached_file,
                duration_sec=meta.duration,
                provider="cache",
                voice_id=selected_voice,
            )

        target_out = output_wav or cached_file
        target_out.parent.mkdir(parents=True, exist_ok=True)

        # Try providers in order
        for p_name in routing:
            provider = self.providers.get(p_name)
            if not provider:
                continue

            avail = provider.probe()
            if not avail.is_usable:
                continue

            try:
                # If provider is VoxCPM, pass reference audio and actor info for cloning
                if p_name == "voxcpm" and hasattr(provider, "generate_speech"):
                    res = provider.generate_speech(  # type: ignore
                        text=clean_text,
                        voice_id=selected_voice,
                        output_wav=target_out,
                        pitch=selected_pitch,
                        rate=selected_rate,
                        emotion_tag=emotion_tag,
                        reference_audio=reference_audio,
                        target_lang=target_lang,
                        actor_id=actor_id,
                        token=token,
                    )
                else:
                    res = provider.generate_speech(
                        text=clean_text,
                        voice_id=selected_voice,
                        output_wav=target_out,
                        pitch=selected_pitch,
                        rate=selected_rate,
                        emotion_tag=emotion_tag,
                        token=token,
                    )

                # Copy to cache if output_wav was provided separately
                if output_wav and not cached_file.exists():
                    import shutil
                    shutil.copy2(target_out, cached_file)

                return res
            except Exception as e:
                logger.warning("TTS Provider '%s' failed: %s; falling back...", p_name, e)

        raise RuntimeError(f"All TTS providers failed for language '{target_lang}'.")

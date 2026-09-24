"""Edge-TTS provider adapter for free neural text-to-speech in Khmer, Chinese, English, etc."""

from __future__ import annotations

import asyncio
import logging
import subprocess
from pathlib import Path

from core.cancellation import CancellationToken
from modules.ai.engine import Availability
from modules.ai.providers.base import TTSProvider, TTSResult
from modules.media.inspector import MediaInspector

logger = logging.getLogger(__name__)

# Default high quality neural voices
DEFAULT_VOICES: dict[str, str] = {
    "km": "km-KH-PisethNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-JennyNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
}


class EdgeTTSProvider(TTSProvider):
    """Microsoft Edge Neural TTS provider supporting Khmer, Chinese, English, and more."""

    name: str = "edge"

    def probe(self) -> Availability:
        try:
            import edge_tts  # noqa: F401

            return Availability(status="ready", reason="Edge-TTS neural voices available.")
        except ImportError:
            return Availability(status="unavailable", reason="edge-tts package is not installed.")

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

        import edge_tts

        out_path = Path(output_wav).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_mp3 = out_path.with_suffix(".tmp.mp3")

        # Format pitch string e.g. "+5Hz" or "-5Hz"
        pitch_int = int(round(pitch * 20))
        pitch_str = f"{pitch_int:+d}Hz" if pitch_int != 0 else "+0Hz"

        # Format rate string e.g. "+10%" or "-10%"
        rate_pct = int(round((rate - 1.0) * 100))
        rate_str = f"{rate_pct:+d}%" if rate_pct != 0 else "+0%"

        async def _synth() -> None:
            communicate = edge_tts.Communicate(
                text=text,
                voice=voice_id,
                pitch=pitch_str,
                rate=rate_str,
            )
            await communicate.save(str(tmp_mp3))

        try:
            asyncio.run(_synth())
            if token:
                token.throw_if_cancelled()

            # Convert mp3 to standard 44.1kHz stereo PCM WAV via FFmpeg
            cmd = [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-i",
                str(tmp_mp3),
                "-c:a",
                "pcm_s16le",
                "-ar",
                "44100",
                str(out_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True, timeout=60)
            tmp_mp3.unlink(missing_ok=True)

            meta = MediaInspector.probe(out_path)
            duration = meta.duration if meta.duration > 0 else 1.0

            return TTSResult(
                audio_path=out_path,
                duration_sec=duration,
                provider=self.name,
                voice_id=voice_id,
            )
        except Exception as e:
            tmp_mp3.unlink(missing_ok=True)
            logger.error("Edge-TTS speech synthesis failed: %s", e)
            raise

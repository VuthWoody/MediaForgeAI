"""Transcriber Engine wrapping faster-whisper conforming to the Section 6 Engine contract."""

from __future__ import annotations

import logging
import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, EngineUnavailableError
from modules.ai.engine import Availability, Engine, Transcript, TranscriptSegment
from modules.media.inspector import MediaInspector

logger = logging.getLogger(__name__)


@dataclass
class TranscriberInput:
    """Input parameters for the transcription engine."""

    audio_path: Path | str
    model_size: str = "small"
    language: str | None = None
    beam_size: int = 5
    word_timestamps: bool = True
    device: str = "auto"  # "auto", "cpu", "cuda"
    compute_type: str = "default"  # "int8", "float16", "float32", "default"


class TranscriberEngine(Engine):
    """Engine conforming to Section 6 wrapping faster-whisper."""

    name: str = "faster-whisper"

    def __init__(self) -> None:
        self._model_cache: dict[str, Any] = {}

    @property
    def required_locks(self) -> list[str]:
        return []

    def probe(self) -> Availability:
        """Cheap check verifying faster-whisper availability."""
        try:
            import faster_whisper  # noqa: F401

            return Availability(status="ready", reason="faster-whisper engine is available")
        except ImportError:
            return Availability(
                status="unavailable",
                reason="faster-whisper package is not installed",
            )
        except Exception as e:
            return Availability(status="degraded", reason=f"faster-whisper probe warning: {e}")

    def _prepare_16k_mono_audio(self, source_path: Path, output_wav: Path) -> float:
        """Convert input audio/video to 16kHz mono WAV for optimal Whisper ingestion.

        Returns audio duration in seconds.
        """
        output_wav.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(source_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "wav",
            str(output_wav),
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)

        meta = MediaInspector.probe(output_wav)
        return meta.duration if meta.duration > 0 else 1.0

    def _get_whisper_model(
        self,
        model_size: str,
        device: str,
        compute_type: str,
    ) -> Any:
        from faster_whisper import WhisperModel

        target_device = "cpu"
        if device == "cuda":
            target_device = "cuda"
        elif device == "auto":
            try:
                import torch

                target_device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                target_device = "cpu"

        # Determine compute type
        ct = compute_type
        if ct == "default":
            ct = "float16" if target_device == "cuda" else "int8"

        cache_key = f"{model_size}_{target_device}_{ct}"
        if cache_key in self._model_cache:
            return self._model_cache[cache_key]

        logger.info(
            "Loading faster-whisper model '%s' on %s (%s)...",
            model_size,
            target_device,
            ct,
        )
        model = WhisperModel(model_size, device=target_device, compute_type=ct)
        self._model_cache[cache_key] = model
        return model

    def run(
        self,
        inputs: TranscriberInput,
        workdir: Path,
        token: CancellationToken,
        progress: Callable[[float, str], None],
    ) -> Transcript:
        """Execute faster-whisper transcription on mixed audio, writing transcript.json into workdir."""
        token.throw_if_cancelled()

        availability = self.probe()
        if not availability.is_usable:
            raise EngineUnavailableError(f"Transcriber engine unavailable: {availability.reason}")

        workdir = Path(workdir).resolve()
        workdir.mkdir(parents=True, exist_ok=True)
        source_path = Path(inputs.audio_path).resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Input audio file not found: {source_path}")

        progress(0.05, "Extracting audio stream (16kHz mono)...")
        token.throw_if_cancelled()

        prepared_wav = workdir / "whisper_input_16k.wav"
        total_duration = self._prepare_16k_mono_audio(source_path, prepared_wav)
        token.throw_if_cancelled()

        progress(0.15, f"Loading Whisper model ({inputs.model_size})...")
        model = self._get_whisper_model(
            model_size=inputs.model_size,
            device=inputs.device,
            compute_type=inputs.compute_type,
        )
        token.throw_if_cancelled()

        progress(0.25, "Running transcription on mixed audio...")
        segments_gen, info = model.transcribe(
            str(prepared_wav),
            beam_size=inputs.beam_size,
            language=inputs.language,
            word_timestamps=inputs.word_timestamps,
        )

        detected_lang = getattr(info, "language", inputs.language or "unknown")
        segments: list[TranscriptSegment] = []
        seg_idx = 1

        for segment in segments_gen:
            if token.is_cancelled:
                raise CancelledError("Transcription cancelled by user token.")

            # Calculate confidence from avg_logprob
            confidence = 1.0
            if hasattr(segment, "avg_logprob") and segment.avg_logprob is not None:
                try:
                    confidence = max(0.0, min(1.0, math.exp(segment.avg_logprob)))
                except OverflowError:
                    confidence = 1.0
            elif hasattr(segment, "no_speech_prob") and segment.no_speech_prob is not None:
                confidence = max(0.0, min(1.0, 1.0 - float(segment.no_speech_prob)))

            raw_text = segment.text.strip()
            if not raw_text:
                continue

            seg = TranscriptSegment(
                id=seg_idx,
                start=round(float(segment.start), 3),
                end=round(float(segment.end), 3),
                speaker="Speaker 1",
                source_text=raw_text,
                target_text="",
                voice_id="",
                audio_path="",
                confidence=round(confidence, 4),
            )
            segments.append(seg)
            seg_idx += 1

            # Progress tracking
            if total_duration > 0:
                cur_ratio = min(0.95, 0.25 + 0.70 * (seg.end / total_duration))
                progress(
                    cur_ratio,
                    f"Transcribing ({seg.end:.1f}s / {total_duration:.1f}s, {len(segments)} segments)...",
                )

        transcript = Transcript(
            segments=segments,
            language=detected_lang,
            duration=total_duration,
        )

        out_json = workdir / "transcript.json"
        transcript.save_json(out_json)
        progress(1.0, f"Transcription completed. {len(segments)} segments generated.")
        return transcript

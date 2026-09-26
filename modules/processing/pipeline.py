"""Unified Auto-Process DAG Pipeline (Phase 10).

Executes the full automated translation, dubbing, and subtitling workflow:
1. Probe & Validate Media
2. Extract 16kHz Audio
3. Whisper Transcription (faster-whisper)
4. Speaker Diarization (Hierarchical Clustering)
5. Stem Separation (MDX-Net / Demucs) -> Vocals + BGM/SFX
6. Translation & Director Tagging (Gemini / DeepSeek / Qwen / LibreTranslate)
7. Expressive TTS Dubbing (Edge-TTS / Gemini / Qwen)
8. Audio Alignment (1.15x speed cap + silence padding)
9. Audio Mixing (sidechain ducking BGM under speech)
10. Subtitle Generation (.srt, .vtt, .ass)
11. Final MP4 Mux / Render with HW acceleration (NVENC / AMF / QSV / x264)

Features content-addressed artifact reuse and graceful CancellationToken support.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.cancellation import CancellationToken
from core.exceptions import EngineError
from core.utils import to_safe_path
from modules.ai.diarizer import DiarizerEngine, DiarizerInput
from modules.ai.director import DirectorManager
from modules.ai.engine import Transcript
from modules.ai.separator import SeparatorEngine, SeparatorInput
from modules.ai.transcriber import TranscriberEngine, TranscriberInput
from modules.ai.voice_generator import VoiceGenerator
from modules.media.inspector import MediaInspector
from modules.processing.aligner import AudioAligner
from modules.processing.mixer import AudioMixer
from modules.processing.subtitle import SubtitleManager, SubtitleStyle

logger = logging.getLogger("mediaforge.pipeline")


@dataclass
class PipelineConfig:
    """Configuration options for an automated pipeline execution."""

    video_path: Path
    output_dir: Path
    target_lang: str = "km"  # Default: Khmer ("km") or English ("en")
    source_lang: str | None = None  # None for auto-detect (e.g. Chinese "zh")
    translation_provider: str = "libre"  # "libre", "gemini", "deepseek", "qwen"
    tts_provider: str | None = None  # None for auto router ("edge" for Khmer, etc.)
    whisper_model: str = "small"
    separate_stems: bool = True
    burn_subtitles: bool = False
    encoder: str = "auto"  # "auto", "h264_nvenc", "h264_amf", "h264_qsv", "libx264"
    force_recompute: bool = False
    characters: list[dict[str, str]] | None = None
    num_speakers: int | None = None


@dataclass
class PipelineResult:
    """Artifacts produced by the automated pipeline execution."""

    video_path: Path
    output_video_path: Path
    transcript: Transcript
    translated_transcript: Transcript
    srt_path: Path
    vtt_path: Path
    ass_path: Path
    mixed_audio_path: Path
    vocals_path: Path | None = None
    no_vocals_path: Path | None = None
    dubbed_dialogue_path: Path | None = None
    duration_sec: float = 0.0
    stages_completed: list[str] = field(default_factory=list)


class PipelineEngine:
    """Orchestrates the entire end-to-end processing pipeline as a DAG."""

    def __init__(self) -> None:
        self.inspector = MediaInspector()
        self.transcriber = TranscriberEngine()
        self.diarizer = DiarizerEngine()
        self.separator = SeparatorEngine()
        self.director = DirectorManager()
        self.voice_gen = VoiceGenerator()
        self.aligner = AudioAligner()
        self.mixer = AudioMixer()
        self.sub_mgr = SubtitleManager()

    def run(
        self,
        config: PipelineConfig,
        token: CancellationToken | None = None,
        progress: Callable[[float, str], None] | None = None,
    ) -> PipelineResult:
        """Execute the DAG pipeline from end to end."""
        token = token or CancellationToken()

        def emit_progress(p: float, msg: str) -> None:
            if progress:
                progress(p, msg)
            logger.info(f"Pipeline [{int(p * 100)}%]: {msg}")

        emit_progress(0.02, "Initializing pipeline & verifying workdir...")
        token.throw_if_cancelled()

        # Content-addressed cache directory
        video_stat = config.video_path.stat()
        cache_seed = f"{config.video_path.name}_{video_stat.st_size}_{video_stat.st_mtime}_{config.target_lang}_{config.translation_provider}"
        cache_hash = hashlib.sha256(cache_seed.encode("utf-8")).hexdigest()[:12]

        # Sanitize video stem for workdir so FFmpeg never fails on unicode characters like '\uff5c' (|)
        safe_stem = "".join(c if (c.isalnum() or c in (" ", "-", "_")) else "_" for c in config.video_path.stem)
        safe_stem = re.sub(r"\s+", " ", safe_stem).strip()
        workdir = config.output_dir / f"work_{safe_stem}_{cache_hash}"

        # If a legacy workdir with unescaped characters exists, migrate its cached files
        legacy_dir = config.output_dir / f"work_{config.video_path.stem}_{cache_hash}"
        if legacy_dir.exists() and not workdir.exists():
            import shutil
            try:
                shutil.copytree(legacy_dir, workdir)
            except Exception as e:
                logger.debug("Failed migrating legacy workdir: %s", e)

        workdir.mkdir(parents=True, exist_ok=True)

        stages_completed: list[str] = []

        # ---------------------------------------------------------------------
        # Stage 1: Inspect Media
        # ---------------------------------------------------------------------
        emit_progress(0.05, "Inspecting media streams & metadata...")
        meta = self.inspector.probe(config.video_path)
        if not meta.has_audio:
            raise EngineError(f"Video {config.video_path.name} contains no audio stream for transcription.")
        stages_completed.append("inspect")

        # ---------------------------------------------------------------------
        # Stage 2: Extract 16kHz Audio
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.10, "Extracting audio for Whisper transcription...")
        extracted_audio_path = workdir / "audio_16k.wav"
        if not extracted_audio_path.exists() or config.force_recompute:
            cmd_extract = [
                "ffmpeg",
                "-y",
                "-i",
                to_safe_path(config.video_path),
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "16000",
                "-ac",
                "1",
                to_safe_path(extracted_audio_path),
            ]
            res = subprocess.run(cmd_extract, capture_output=True, text=True)
            if res.returncode != 0:
                raise EngineError(f"FFmpeg audio extraction failed: {res.stderr}")
        stages_completed.append("extract_audio")

        # ---------------------------------------------------------------------
        # Stage 3: Whisper Transcription
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.18, f"Transcribing audio with faster-whisper ({config.whisper_model})...")
        trans_json = workdir / "transcript.json"

        if trans_json.exists() and not config.force_recompute:
            emit_progress(0.25, "Reusing cached transcription...")
            transcript = Transcript.load_json(trans_json)
        else:
            companion_srt = config.video_path.with_suffix(".srt")
            if companion_srt.exists() and not config.force_recompute:
                try:
                    emit_progress(0.22, f"Importing companion subtitles from {companion_srt.name}...")
                    from modules.ai.engine import TranscriptSegment
                    from modules.media.player_controller import parse_srt_file

                    sub_segs = parse_srt_file(companion_srt)
                    if sub_segs:
                        segs = [
                            TranscriptSegment(
                                id=i + 1,
                                start=round(s.start_ms / 1000.0, 3),
                                end=round(s.end_ms / 1000.0, 3),
                                source_text=s.text,
                            )
                            for i, s in enumerate(sub_segs)
                        ]
                        duration = max((s.end for s in segs), default=0.0)
                        transcript = Transcript(
                            segments=segs,
                            language=config.source_lang,
                            duration=duration,
                        )
                        transcript.save_json(trans_json)
                    else:
                        raise ValueError("Empty subtitle file")
                except Exception as srt_err:
                    logger.warning("Could not import companion srt (%s), falling back to faster-whisper", srt_err)
                    def sub_prog_t(p: float, m: str) -> None:
                        emit_progress(0.15 + (p * 0.15), f"Whisper: {m}")

                    transcript = self.transcriber.run(
                        TranscriberInput(
                            audio_path=extracted_audio_path,
                            model_size=config.whisper_model,
                            language=config.source_lang,
                        ),
                        workdir=workdir,
                        token=token,
                        progress=sub_prog_t,
                    )
            else:
                def sub_prog_t(p: float, m: str) -> None:
                    emit_progress(0.15 + (p * 0.15), f"Whisper: {m}")

                transcript = self.transcriber.run(
                    TranscriberInput(
                        audio_path=extracted_audio_path,
                        model_size=config.whisper_model,
                        language=config.source_lang,
                    ),
                    workdir=workdir,
                    token=token,
                    progress=sub_prog_t,
                )
        stages_completed.append("transcribe")

        # ---------------------------------------------------------------------
        # Stage 4: Diarization (Power Voice Separator)
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.32, "Separating voices & characters (Power Voice Separator)...")
        diar_json = workdir / "diarized_transcript.json"

        should_recompute_diar = config.force_recompute or not diar_json.exists()
        diarized_transcript: Transcript | None = None
        if not should_recompute_diar:
            try:
                cached_d = Transcript.load_json(diar_json)
                unique_spks = {s.speaker for s in cached_d.segments}
                spk_counts = [sum(1 for s in cached_d.segments if s.speaker == spk) for spk in unique_spks]
                if len(cached_d.segments) >= 4 and (
                    len(unique_spks) <= 1
                    or (len(cached_d.segments) >= 10 and min(spk_counts) <= 1)
                ):
                    logger.info("Cached diarization contains only 1 dominant speaker; recomputing...")
                    should_recompute_diar = True
                else:
                    diarized_transcript = cached_d
                    emit_progress(0.38, f"Reusing cached diarization ({len(unique_spks)} speaker(s))...")
            except Exception:
                should_recompute_diar = True

        if should_recompute_diar or diarized_transcript is None:
            # Check for drama characters metadata from config or companion .meta.json
            active_characters = config.characters
            if not active_characters:
                meta_candidate = config.video_path.with_suffix(".meta.json")
                if meta_candidate.exists():
                    try:
                        with open(meta_candidate, encoding="utf-8") as mf:
                            mdata = json.load(mf)
                            active_characters = mdata.get("characters")
                    except Exception as ex_m:
                        logger.debug("Could not read companion meta.json: %s", ex_m)

            def sub_prog_d(p: float, m: str) -> None:
                emit_progress(0.30 + (p * 0.08), f"Power Voice Separator: {m}")

            diarized_transcript = self.diarizer.run(
                DiarizerInput(
                    audio_path=extracted_audio_path,
                    transcript=transcript,
                    num_speakers=config.num_speakers,
                    characters=active_characters,
                ),
                workdir=workdir,
                token=token,
                progress=sub_prog_d,
            )
        stages_completed.append("diarize")

        # ---------------------------------------------------------------------
        # Stage 5: Stem Separation (Vocals vs BGM/SFX)
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        vocals_path: Path | None = None
        no_vocals_path: Path | None = None

        if config.separate_stems:
            emit_progress(0.40, "Separating vocals and BGM stems...")
            cached_vocals = workdir / "vocals.wav"
            cached_no_vocals = workdir / "no_vocals.wav"

            if cached_vocals.exists() and cached_no_vocals.exists() and not config.force_recompute:
                emit_progress(0.48, "Reusing cached audio stems...")
                vocals_path = cached_vocals
                no_vocals_path = cached_no_vocals
            else:
                def sub_prog_s(p: float, m: str) -> None:
                    emit_progress(0.40 + (p * 0.10), f"Stem Separator: {m}")

                stem_res = self.separator.run(
                    SeparatorInput(audio_path=config.video_path, mode="auto"),
                    workdir=workdir,
                    token=token,
                    progress=sub_prog_s,
                )
                vocals_path = stem_res.vocals_path
                no_vocals_path = stem_res.no_vocals_path
            stages_completed.append("separate_stems")
        else:
            # Fallback: without separation, no_vocals is extracted stereo audio
            no_vocals_path = workdir / "original_audio.wav"
            if not no_vocals_path.exists():
                subprocess.run(
                    ["ffmpeg", "-y", "-i", to_safe_path(config.video_path), "-vn", "-c:a", "pcm_s16le", to_safe_path(no_vocals_path)],
                    capture_output=True,
                )

        # ---------------------------------------------------------------------
        # Stage 6: Translation & Director Tagging
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.52, f"Translating transcript to {config.target_lang.upper()} ({config.translation_provider})...")
        trans_out_json = workdir / f"translated_{config.target_lang}.json"

        if trans_out_json.exists() and not config.force_recompute:
            emit_progress(0.60, "Reusing cached translation...")
            translated_transcript = Transcript.load_json(trans_out_json)
            # Sync speakers and emotions from diarized_transcript if cached translation had outdated speaker tags
            if len(translated_transcript.segments) == len(diarized_transcript.segments):
                for t_seg, d_seg in zip(translated_transcript.segments, diarized_transcript.segments, strict=False):
                    if t_seg.speaker != d_seg.speaker:
                        t_seg.speaker = d_seg.speaker
                    if hasattr(d_seg, "emotion") and d_seg.emotion:
                        t_seg.emotion = d_seg.emotion
                with open(trans_out_json, "w", encoding="utf-8") as f:
                    json.dump(translated_transcript.to_dict(), f, indent=2, ensure_ascii=False)
        else:
            def sub_prog_tr(p: float, m: str) -> None:
                emit_progress(0.52 + (p * 0.10), f"Director: {m}")

            translated_transcript = self.director.translate_transcript(
                transcript=diarized_transcript,
                target_lang=config.target_lang,
                token=token,
                progress=sub_prog_tr,
                preferred_provider=config.translation_provider,
            )
            with open(trans_out_json, "w", encoding="utf-8") as f:
                json.dump(translated_transcript.to_dict(), f, indent=2, ensure_ascii=False)
        stages_completed.append("translate")

        # ---------------------------------------------------------------------
        # Stage 7: Expressive TTS Dubbing (with VoxCPM2 Actor Voice Cloning)
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.62, "Synthesizing multi-actor dubbed dialogue (VoxCPM2 / Neural TTS)...")
        tts_dir = workdir / "tts_clips"
        tts_dir.mkdir(parents=True, exist_ok=True)

        # Invalidate cached TTS clips if speaker assignments changed from previous run
        speakers_manifest_file = tts_dir / ".speakers_manifest.json"
        current_speaker_map = {str(seg.id): seg.speaker for seg in translated_transcript.segments}
        if speakers_manifest_file.exists():
            try:
                with open(speakers_manifest_file, encoding="utf-8") as smf:
                    cached_speaker_map = json.load(smf)
                if cached_speaker_map != current_speaker_map or config.force_recompute:
                    logger.info("Speaker assignments changed or force recompute; purging stale TTS clips...")
                    for old_clip in tts_dir.glob("tts_*.wav"):
                        old_clip.unlink(missing_ok=True)
            except Exception as e:
                logger.debug("Failed checking speaker manifest: %s", e)

        with open(speakers_manifest_file, "w", encoding="utf-8") as smf:
            json.dump(current_speaker_map, smf, indent=2, ensure_ascii=False)

        # Track text manifest so any edited translation in Inspector mode is automatically re-synthesized
        clips_manifest_file = tts_dir / ".clips_text_manifest.json"
        cached_clip_manifest: dict[str, dict[str, Any]] = {}
        if clips_manifest_file.exists() and not config.force_recompute:
            try:
                with open(clips_manifest_file, encoding="utf-8") as cmf:
                    cached_clip_manifest = json.load(cmf)
            except Exception as e:
                logger.debug("Failed checking clips manifest: %s", e)

        current_clip_manifest: dict[str, dict[str, Any]] = {}

        # Extract reference audio samples per unique actor for VoxCPM2 voice cloning
        clones_dir = workdir / "actor_clones"
        clones_dir.mkdir(parents=True, exist_ok=True)
        speaker_reference_audios: dict[str, Path] = {}
        source_vocal_audio = vocals_path or extracted_audio_path

        if source_vocal_audio and Path(source_vocal_audio).exists():
            import wave
            try:
                with wave.open(str(source_vocal_audio), "rb") as wf:
                    v_sr = wf.getframerate()
                    v_ch = wf.getnchannels()
                    v_sw = wf.getsampwidth()

                    # Group candidate speech segments per speaker
                    speaker_candidates: dict[str, list[Any]] = {}
                    for seg in translated_transcript.segments:
                        spk = seg.speaker
                        if spk not in speaker_candidates:
                            speaker_candidates[spk] = []
                        dur = seg.end - seg.start
                        if dur >= 1.5:
                            speaker_candidates[spk].append(seg)

                    for spk, seg_list in speaker_candidates.items():
                        if not seg_list:
                            continue
                        # Select segment with ideal duration (closest to 3.5 - 5.0s for rich acoustic profile)
                        seg_list.sort(key=lambda s: abs((s.end - s.start) - 4.0))
                        best_seg = seg_list[0]
                        dur = best_seg.end - best_seg.start
                        safe_name = "".join(c if c.isalnum() else "_" for c in spk)[:32]
                        ref_path = clones_dir / f"ref_{safe_name}.wav"
                        start_fr = max(0, int(best_seg.start * v_sr))
                        cnt = min(wf.getnframes() - start_fr, int(dur * v_sr))
                        if cnt > 0:
                            wf.setpos(start_fr)
                            chunk_bytes = wf.readframes(cnt)
                            with wave.open(str(ref_path), "wb") as out_rf:
                                out_rf.setnchannels(v_ch)
                                out_rf.setsampwidth(v_sw)
                                out_rf.setframerate(v_sr)
                                out_rf.writeframes(chunk_bytes)
                            speaker_reference_audios[spk] = ref_path
                            logger.info("Extracted actor reference clip for '%s': %s (%.2fs)", spk, ref_path.name, dur)
            except Exception as ex_clone:
                logger.debug("Notice extracting actor clone reference clips: %s", ex_clone)

        raw_tts_items: list[tuple[float, float, Path]] = []
        total_segs = len(translated_transcript.segments)

        for i, seg in enumerate(translated_transcript.segments):
            token.throw_if_cancelled()
            text_to_speak = seg.target_text or seg.source_text
            if not text_to_speak.strip():
                continue

            out_clip = tts_dir / f"tts_{i:04d}_{seg.id}.wav"
            ref_audio = speaker_reference_audios.get(seg.speaker)
            cached_meta = cached_clip_manifest.get(str(seg.id), {})
            text_changed = (
                cached_meta.get("text") != text_to_speak
                or cached_meta.get("speaker") != seg.speaker
                or cached_meta.get("emotion") != getattr(seg, "emotion", None)
                or cached_meta.get("provider") != (config.tts_provider or "voxcpm")
                or cached_meta.get("cloned") != bool(ref_audio)
            )

            if not out_clip.exists() or text_changed or config.force_recompute:
                if text_changed and out_clip.exists():
                    out_clip.unlink(missing_ok=True)
                self.voice_gen.generate_speech(
                    text=text_to_speak,
                    target_lang=config.target_lang,
                    speaker=seg.speaker,
                    output_wav=out_clip,
                    emotion_tag=getattr(seg, "emotion", None),
                    reference_audio=ref_audio,
                    preferred_provider=config.tts_provider or "voxcpm",
                    token=token,
                )

            current_clip_manifest[str(seg.id)] = {
                "text": text_to_speak,
                "speaker": seg.speaker,
                "emotion": getattr(seg, "emotion", None),
                "provider": config.tts_provider or "voxcpm",
                "cloned": bool(ref_audio),
            }
            raw_tts_items.append((seg.start, seg.end, out_clip))

            if total_segs > 0:
                prog = (i + 1) / total_segs
                emit_progress(0.62 + (prog * 0.12), f"TTS generated line {i + 1}/{total_segs} ({seg.speaker})")

        with open(clips_manifest_file, "w", encoding="utf-8") as cmf:
            json.dump(current_clip_manifest, cmf, indent=2, ensure_ascii=False)

        stages_completed.append("tts_generate")


        # ---------------------------------------------------------------------
        # Stage 8: Audio Alignment (1.15x speed cap + silence padding)
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.76, "Aligning dubbed speech to visual timing (1.15x cap)...")
        aligned_dir = workdir / "aligned_clips"
        aligned_dir.mkdir(parents=True, exist_ok=True)

        aligned_for_mix: list[tuple[Path, float]] = []
        for i, (start_s, end_s, raw_clip_path) in enumerate(raw_tts_items):
            token.throw_if_cancelled()
            target_dur = max(0.2, end_s - start_s)
            out_clip_path = aligned_dir / f"aligned_{i:04d}.wav"
            res = self.aligner.align_clip(
                input_wav=raw_clip_path,
                target_duration=target_dur,
                output_wav=out_clip_path,
                token=token,
            )
            aligned_for_mix.append((res.aligned_wav_path, start_s))
        stages_completed.append("align_dialogue")

        # ---------------------------------------------------------------------
        # Stage 9: Audio Mixing & Sidechain Ducking
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.82, "Mixing dialogue and sidechain ducking BGM...")
        dialogue_track_wav = workdir / "dubbed_dialogue.wav"
        mixed_audio_path = workdir / "dubbed_mix.wav"

        # 1. Assemble aligned dialogue track
        self.mixer.assemble_dialogue_track(
            clips=aligned_for_mix,
            total_duration=meta.duration,
            output_wav=dialogue_track_wav,
            token=token,
        )

        # 2. Sidechain ducking BGM
        bgm_path = no_vocals_path if (no_vocals_path and no_vocals_path.exists()) else extracted_audio_path
        self.mixer.mix_master_audio(
            dialogue_wav=dialogue_track_wav,
            bgm_wav=bgm_path,
            output_wav=mixed_audio_path,
            total_duration=meta.duration,
            token=token,
        )
        stages_completed.append("mix_audio")

        # ---------------------------------------------------------------------
        # Stage 10: Subtitle Generation (.srt, .vtt, .ass)
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.88, "Exporting multilingual subtitles (.srt, .vtt, .ass)...")
        srt_path = workdir / f"{config.video_path.stem}_{config.target_lang}.srt"
        vtt_path = workdir / f"{config.video_path.stem}_{config.target_lang}.vtt"
        ass_path = workdir / f"{config.video_path.stem}_{config.target_lang}.ass"

        sub_style = SubtitleStyle()
        self.sub_mgr.export_srt(translated_transcript, srt_path)
        self.sub_mgr.export_vtt(translated_transcript, vtt_path)
        self.sub_mgr.export_ass(translated_transcript, ass_path, style=sub_style)
        stages_completed.append("subtitle_process")

        # ---------------------------------------------------------------------
        # Stage 11: Final Export Mux / Render
        # ---------------------------------------------------------------------
        token.throw_if_cancelled()
        emit_progress(0.92, "Rendering final dubbed & subtitled video...")
        output_filename = f"{config.video_path.stem}_dubbed_{config.target_lang}.mp4"
        final_video_path = config.output_dir / output_filename

        # Detect encoder
        chosen_encoder = self._resolve_encoder(config.encoder)
        emit_progress(0.94, f"Encoding with {chosen_encoder}...")

        if config.burn_subtitles:
            # Burn-in subtitles
            self.sub_mgr.burn_in(
                video_path=config.video_path,
                subtitle_path=ass_path,
                output_path=final_video_path,
                audio_path=mixed_audio_path,
            )
        else:
            # Soft-mux subtitles + new mixed audio
            self.sub_mgr.soft_mux(
                video_path=config.video_path,
                subtitle_path=srt_path,
                output_path=final_video_path,
                audio_path=mixed_audio_path,
            )
        stages_completed.append("export_video")

        emit_progress(1.0, f"Auto-Process complete! Saved to {final_video_path.name}")

        return PipelineResult(
            video_path=config.video_path,
            output_video_path=final_video_path,
            transcript=diarized_transcript,
            translated_transcript=translated_transcript,
            srt_path=srt_path,
            vtt_path=vtt_path,
            ass_path=ass_path,
            mixed_audio_path=mixed_audio_path,
            vocals_path=vocals_path,
            no_vocals_path=no_vocals_path,
            dubbed_dialogue_path=dialogue_track_wav,
            duration_sec=meta.duration,
            stages_completed=stages_completed,
        )

    @staticmethod
    def _resolve_encoder(requested: str) -> str:
        if requested != "auto":
            return requested

        # Trial probe common hardware encoders
        candidates = ["h264_nvenc", "h264_amf", "h264_qsv", "libx264"]
        for enc in candidates:
            if enc == "libx264":
                return "libx264"
            cmd = [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "nullsrc=s=128x128:d=0.1",
                "-c:v",
                enc,
                "-f",
                "null",
                "-",
            ]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0:
                logger.info(f"Hardware encoder detected and verified: {enc}")
                return enc

        return "libx264"

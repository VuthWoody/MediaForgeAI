"""VoxReel Checkpointed Pipeline Engine.

Implements §7.2 (Checkpointed Pipeline Stages) from VOX_engine_Plan.md:
- S1 Ingest: media file -> conditioned WAV (16k mono, EBU R128) -> s1_audio.wav
- S2 Diarize: WAV -> segments + embeddings + clusters -> s2_diar.json
- S3 Transcribe: WAV -> words + timestamps -> s3_asr.json
- S4 Fuse/Match: S2 + S3 -> attributed transcript + registry scores -> s4_final.json
- S5 Export: final JSON -> SRT, VTT, ELAN, TXT, JSON
- Resumable pipeline (--resume flag skips already completed stage artifacts)
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from modules.voxreel.asr import Transcriber
from modules.voxreel.audio import AudioConditioner
from modules.voxreel.config import VoxReelConfig
from modules.voxreel.db import VoxReelDB
from modules.voxreel.diarizer import Diarizer
from modules.voxreel.exporters import VoxReelExporter
from modules.voxreel.registry import ActorVoiceRegistry, ClusterMatchResult

logger = logging.getLogger("voxreel.engine")


@dataclass
class MasterSessionResult:
    session_id: str
    media_name: str
    duration_sec: float
    language: str
    speakers: list[dict[str, Any]] = field(default_factory=list)
    segments: list[dict[str, Any]] = field(default_factory=list)
    exported_files: dict[str, str] = field(default_factory=dict)
    checkpoint_dir: str = ""

    def to_master_json(self) -> dict[str, Any]:
        """Convert to Appendix C Master JSON schema."""
        return {
            "session_id": self.session_id,
            "pipeline": {
                "voxreel": "1.0.0",
                "embedding_model": "ecapa-tdnn-voxceleb-v2",
            },
            "media": {
                "name": self.media_name,
                "duration_sec": round(self.duration_sec, 2),
            },
            "language": self.language,
            "speakers": self.speakers,
            "segments": self.segments,
        }


class VoxReelEngine:
    """End-to-end multi-stage diarization and actor identity matching engine."""

    def __init__(
        self,
        config: VoxReelConfig | None = None,
        db: VoxReelDB | None = None,
    ) -> None:
        self.config = config or VoxReelConfig()
        self.db = db or VoxReelDB(self.config.vault_dir if self.config.vault_dir else None)
        self.audio_conditioner = AudioConditioner(
            target_sr=self.config.audio.target_sr,
            target_lufs=self.config.audio.loudness_target_lufs,
        )
        self.diarizer = Diarizer(
            min_speech_ms=self.config.vad.min_speech_ms,
            min_silence_ms=self.config.vad.min_silence_ms,
            min_cluster_utterances=self.config.diarization.min_cluster_utterances,
        )
        self.transcriber = Transcriber(
            model_size=self.config.asr.model,
            compute_type=self.config.asr.compute_type,
            beam_size=self.config.asr.beam_size,
        )
        self.registry = ActorVoiceRegistry(db=self.db, config=self.config.registry)
        self.exporter = VoxReelExporter()

    def process(
        self,
        media_path: str | Path,
        output_dir: str | Path | None = None,
        language: str = "en",
        num_speakers: int | None = None,
        model_size: str | None = None,
        resume: bool = True,
        export_formats: tuple[str, ...] = ("json", "srt", "vtt", "eaf", "txt"),
        progress_cb: Callable[[str, float, str], None] | None = None,
    ) -> MasterSessionResult:
        """Execute the 5-stage VoxReel pipeline on a media file.

        Args:
            media_path: Input media file.
            output_dir: Directory for session checkpoints and exports.
            language: Speech language.
            num_speakers: Optional forced speaker count override.
            model_size: Optional Whisper model size override (e.g. 'small', 'base', 'tiny').
            resume: If True, resume from last completed stage checkpoint.
            export_formats: Formats to export in Stage 5.
            progress_cb: Callback (stage_name, pct, message).
        """
        in_p = Path(media_path).resolve()
        if not in_p.exists():
            raise FileNotFoundError(f"Media file not found: {in_p}")

        if model_size and model_size != self.transcriber.model_size:
            self.transcriber.model_size = model_size
            self.transcriber._model = None

        # Setup session in DB
        probe_info = self.audio_conditioner.probe(in_p)
        session = self.db.create_session(
            language=language,
            num_speakers=num_speakers,
            pipeline_ver="1.0.0",
            embedding_model=self.config.diarization.embedding,
        )
        session_id = session.id

        # Setup checkpoint directory
        base_out = Path(output_dir).resolve() if output_dir else in_p.parent / "voxreel_output"
        session_dir = base_out / session_id
        ckpt_dir = session_dir / "checkpoints"
        ckpt_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Starting VoxReel session %s for %s", session_id, in_p.name)

        def _notify(stage: str, pct: float, msg: str) -> None:
            if progress_cb:
                progress_cb(stage, pct, msg)

        # ---------------------------------------------------------------------
        # Stage 1: Ingest & Audio Conditioning (s1_audio.wav)
        # ---------------------------------------------------------------------
        _notify("S1 Ingest", 0.1, "Conditioning audio (16k mono, EBU R128)...")
        s1_wav = ckpt_dir / "s1_audio.wav"

        if resume and s1_wav.exists() and s1_wav.stat().st_size > 1000:
            logger.info("Stage 1 checkpoint found: %s", s1_wav)
        else:
            # Check if a companion clean 16k audio or vocal track exists from Studio
            companion_audio: Path | None = None
            for parent_dir in [in_p.parent, in_p.parent / "forge_output"]:
                for candidate in parent_dir.glob(f"work_{in_p.stem}*"):
                    if candidate.is_dir():
                        for name in ["vocals.wav", "audio_16k.wav", "no_vocals.wav"]:
                            cp = candidate / name
                            if cp.exists() and cp.stat().st_size > 1000:
                                companion_audio = cp
                                break
                    if companion_audio:
                        break
                if companion_audio:
                    break

            source_to_condition = companion_audio if companion_audio else in_p
            if companion_audio:
                logger.info("Using companion studio audio: %s", companion_audio)

            self.audio_conditioner.condition_audio(
                input_path=source_to_condition,
                output_path=s1_wav,
                force_center=True,
                apply_loudnorm=True,
                source_separation=self.config.audio.separation_enabled_for_video and companion_audio is None,
            )

        audio_arr, sr = self.audio_conditioner.load_audio_array(s1_wav)
        dur_sec = len(audio_arr) / sr if sr > 0 else probe_info.get("duration_sec", 0.0)

        # ---------------------------------------------------------------------
        # Stage 2: Diarize & Cluster (s2_diar.json)
        # ---------------------------------------------------------------------
        _notify("S2 Diarize", 0.3, "Detecting voice activity & clustering speakers...")
        s2_json = ckpt_dir / "s2_diar.json"

        diar_segments_raw: list[dict[str, Any]] = []
        if resume and s2_json.exists() and s2_json.stat().st_size > 10:
            logger.info("Stage 2 checkpoint found: %s", s2_json)
            with open(s2_json, encoding="utf-8") as f:
                diar_data = json.load(f)
                diar_segments_raw = diar_data.get("segments", [])
        else:
            diar_results = self.diarizer.diarize(
                audio=audio_arr,
                sr=sr,
                num_speakers=num_speakers,
                output_checkpoint=s2_json,
            )
            diar_segments_raw = [d.to_dict() for d in diar_results]

        # ---------------------------------------------------------------------
        # Stage 3: Transcribe Speech to Words (s3_asr.json)
        # ---------------------------------------------------------------------
        s3_json = ckpt_dir / "s3_asr.json"

        asr_segments_raw: list[dict[str, Any]] = []
        if resume and s3_json.exists() and s3_json.stat().st_size > 10:
            logger.info("Stage 3 checkpoint found: %s", s3_json)
            _notify("S3 Transcribe", 0.78, "Loaded cached speech transcript checkpoint.")
            with open(s3_json, encoding="utf-8") as f:
                asr_data = json.load(f)
                asr_segments_raw = asr_data.get("segments", [])
        else:
            _notify("S3 Transcribe", 0.55, f"Initializing speech recognition ({self.transcriber.model_size})...")
            # Inject known actor names into prompt
            known_actors = self.db.list_actors()
            actor_names = [a.display_name for a in known_actors]
            aliases = [alias for a in known_actors for alias in a.aliases]
            prompt_list = list(dict.fromkeys(actor_names + aliases))

            def _asr_progress(sub_pct: float, msg: str) -> None:
                # Stage 3 spans from 0.55 to 0.78
                stage_pct = 0.55 + 0.23 * max(0.0, min(1.0, sub_pct))
                _notify("S3 Transcribe", stage_pct, msg)

            asr_results = self.transcriber.transcribe(
                audio_path=s1_wav,
                language=language,
                prompt_aliases=prompt_list[:20],
                output_checkpoint=s3_json,
                progress_cb=_asr_progress,
            )
            asr_segments_raw = [s.to_dict() for s in asr_results]

        # ---------------------------------------------------------------------
        # Stage 4: Temporal Alignment & Registry Matching (s4_final.json)
        # ---------------------------------------------------------------------
        _notify("S4 Fuse/Match", 0.8, "Fusing transcript with Actor Voice Registry...")
        s4_json = ckpt_dir / "s4_final.json"

        # Group diarized embeddings by cluster
        cluster_embeddings: dict[str, list[np.ndarray]] = {}
        for d in diar_segments_raw:
            spk = d["speaker"]
            emb_list = d.get("embedding", [])
            if emb_list:
                cluster_embeddings.setdefault(spk, []).append(np.array(emb_list, dtype=np.float32))

        # Perform Hungarian bipartite matching against registered actor profiles
        match_results = self.registry.match_session_clusters(
            session_id=session_id,
            cluster_embeddings=cluster_embeddings,
            language=language,
            model_name=self.config.diarization.embedding,
        )

        speaker_meta_map: dict[str, ClusterMatchResult] = {m.cluster_label: m for m in match_results}

        # Temporal fusion: Assign words and text from ASR into speaker segments
        # by maximum time overlap
        fused_segments: list[dict[str, Any]] = []

        # If ASR segments exist, align words to diarization intervals
        all_words: list[dict[str, Any]] = []
        for asr_seg in asr_segments_raw:
            all_words.extend(asr_seg.get("words", []))

        for d_seg in diar_segments_raw:
            d_start = float(d_seg["start"])
            d_end = float(d_seg["end"])
            spk = d_seg["speaker"]
            spk_meta = speaker_meta_map.get(spk)

            # Find words that fall into [d_start, d_end]
            matching_words: list[dict[str, Any]] = []
            for w in all_words:
                w_mid = (float(w["s"]) + float(w["e"])) / 2.0
                if d_start <= w_mid <= d_end:
                    matching_words.append(w)

            # Build text from words or fallback
            if matching_words:
                seg_text = " ".join(w["w"] for w in matching_words)
            else:
                # Find overlapping ASR segment
                overlaps = [
                    a for a in asr_segments_raw
                    if max(0.0, min(d_end, float(a["end"])) - max(d_start, float(a["start"]))) > 0
                ]
                seg_text = overlaps[0]["text"] if overlaps else ""

            actor_id = spk_meta.actor_id if spk_meta else None
            actor_name = spk_meta.actor_name if spk_meta else None
            match_score = spk_meta.match_score if spk_meta else 0.0
            match_status = spk_meta.match_status if spk_meta else "new"

            fused_segments.append({
                "start": round(d_start, 3),
                "end": round(d_end, 3),
                "speaker": spk,
                "actor_id": actor_id,
                "actor": actor_name,
                "match_score": round(match_score, 3),
                "match_status": match_status,
                "text": seg_text,
                "asr_conf": 0.95,
                "overlap": d_seg.get("overlap", False),
                "words": matching_words,
            })

        # Save segments into database
        self.db.save_segments(session_id, fused_segments)
        self.db.update_session_status(session_id, "done")

        # Prepare speakers list for Master JSON
        speakers_summary = [m.to_dict() for m in match_results]

        master_result = MasterSessionResult(
            session_id=session_id,
            media_name=in_p.name,
            duration_sec=dur_sec,
            language=language,
            speakers=speakers_summary,
            segments=fused_segments,
            checkpoint_dir=str(ckpt_dir),
        )

        with open(s4_json, "w", encoding="utf-8") as f:
            json.dump(master_result.to_master_json(), f, indent=2, ensure_ascii=False)

        # ---------------------------------------------------------------------
        # Stage 5: Export to Requested Formats (JSON, SRT, VTT, ELAN, TXT)
        # ---------------------------------------------------------------------
        _notify("S5 Export", 0.95, "Exporting subtitle, annotation, and transcript files...")
        exported: dict[str, str] = {}
        master_dict = master_result.to_master_json()

        export_dir = session_dir / "exports"
        export_dir.mkdir(parents=True, exist_ok=True)
        stem = in_p.stem

        if "json" in export_formats:
            json_file = export_dir / f"{stem}.voxreel.json"
            self.exporter.export_json(master_dict, json_file)
            exported["json"] = str(json_file)

        if "srt" in export_formats:
            srt_file = export_dir / f"{stem}.srt"
            self.exporter.export_srt(master_dict, srt_file)
            exported["srt"] = str(srt_file)

        if "vtt" in export_formats:
            vtt_file = export_dir / f"{stem}.vtt"
            self.exporter.export_vtt(master_dict, vtt_file)
            exported["vtt"] = str(vtt_file)

        if "txt" in export_formats:
            txt_file = export_dir / f"{stem}.txt"
            self.exporter.export_txt(master_dict, txt_file)
            exported["txt"] = str(txt_file)

        if "eaf" in export_formats or "elan" in export_formats:
            elan_file = export_dir / f"{stem}.eaf"
            self.exporter.export_elan(master_dict, elan_file)
            exported["eaf"] = str(elan_file)

        master_result.exported_files = exported
        _notify("Done", 1.0, f"Processing complete. {len(exported)} formats exported.")

        return master_result

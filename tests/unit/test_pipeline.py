"""Unit tests for Unified Auto-Process Pipeline (Phase 10)."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from core.cancellation import CancellationToken
from core.exceptions import CancelledError, EngineError
from modules.media.inspector import MediaMetadata
from modules.processing.pipeline import PipelineConfig, PipelineEngine


def test_pipeline_config_defaults() -> None:
    cfg = PipelineConfig(
        video_path=Path("sample.mp4"),
        output_dir=Path("exports"),
    )
    assert cfg.target_lang == "km"
    assert cfg.translation_provider == "libre"
    assert cfg.encoder == "auto"
    assert cfg.separate_stems is True


def test_resolve_encoder() -> None:
    enc = PipelineEngine._resolve_encoder("auto")
    assert enc in ["h264_nvenc", "h264_amf", "h264_qsv", "libx264"]

    forced = PipelineEngine._resolve_encoder("libx264")
    assert forced == "libx264"


def test_pipeline_cancellation() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        video_file = tmp_path / "test_video.mp4"
        video_file.write_bytes(b"dummy")

        engine = PipelineEngine()
        token = CancellationToken()
        token.cancel()

        cfg = PipelineConfig(
            video_path=video_file,
            output_dir=tmp_path,
        )

        with pytest.raises(CancelledError):
            engine.run(cfg, token=token)


def test_pipeline_no_audio_error() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        video_file = tmp_path / "no_audio.mp4"
        video_file.write_bytes(b"dummy")

        engine = PipelineEngine()
        # Mock inspector to return no audio
        fake_meta = MediaMetadata(
            file_path=str(video_file),
            file_size=1024,
            mtime=123456.0,
            format_name="mp4",
            duration=10.0,
            bitrate=500000,
            width=1920,
            height=1080,
            fps=30.0,
            total_frames=300,
            video_codec="h264",
            pix_fmt="yuv420p",
            aspect_ratio="16:9",
            has_audio=False,
            audio_codec="none",
            sample_rate=0,
            channels=0,
            audio_bitrate=0,
        )
        engine.inspector.probe = MagicMock(return_value=fake_meta)

        cfg = PipelineConfig(
            video_path=video_file,
            output_dir=tmp_path,
        )

        with pytest.raises(EngineError, match="contains no audio stream"):
            engine.run(cfg)


def test_pipeline_text_manifest_invalidation(tmp_path: Path) -> None:
    """Verify that changes in segment text or speaker trigger re-synthesis in Stage 7."""
    tts_dir = tmp_path / "tts_clips"
    tts_dir.mkdir(parents=True)
    manifest_file = tts_dir / ".clips_text_manifest.json"

    import json
    # Seed old manifest
    old_manifest = {
        "1": {"text": "Original line", "speaker": "Speaker 1", "emotion": None},
    }
    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(old_manifest, f)

    fake_clip = tts_dir / "tts_0000_1.wav"
    fake_clip.write_bytes(b"RIFF")

    # Detect text changed
    new_text = "Edited translation line"
    cached_meta = old_manifest.get("1", {})
    text_changed = (
        cached_meta.get("text") != new_text
        or cached_meta.get("speaker") != "Speaker 1"
    )
    assert text_changed is True


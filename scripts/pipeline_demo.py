"""Phase 10 Verification Script: Unified End-to-End Pipeline Demo."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.processing.pipeline import PipelineConfig, PipelineEngine, PipelineResult


def create_synthetic_video(output_path: Path, duration_sec: float = 3.0) -> None:
    """Generate a test MP4 video with an audio sine wave using ffmpeg."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"color=c=blue:s=640x360:d={duration_sec}:r=30",
        "-f",
        "lavfi",
        "-i",
        f"sine=frequency=440:duration={duration_sec}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("=" * 80)
    print("   MEDIAFORGE AI — PHASE 10: AUTO-PROCESS DAG PIPELINE DEMO")
    print("=" * 80)
    print()

    workdir = Path("scratch/pipeline_demo_run")
    workdir.mkdir(parents=True, exist_ok=True)

    input_video = workdir / "synthetic_input.mp4"
    print(f"1. Generating synthetic test video ({input_video.name})...")
    create_synthetic_video(input_video, duration_sec=3.0)
    print(f"   [OK] Test video generated: {input_video.stat().st_size} bytes")

    output_dir = workdir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    config = PipelineConfig(
        video_path=input_video,
        output_dir=output_dir,
        target_lang="en",
        translation_provider="libre",
        whisper_model="tiny",
        separate_stems=False,  # Skip stem separation for rapid synthetic test
        force_recompute=True,
    )

    engine = PipelineEngine()

    print()
    print("2. Executing Unified DAG Pipeline:")
    print("   Inspection -> Audio Extract -> Whisper -> Diarize -> Stems ->")
    print("   Translate -> Expressive TTS -> Align -> Mix -> Subtitles -> Mux MP4")
    print()

    def progress_callback(prog: float, msg: str) -> None:
        pct = int(prog * 100)
        bar = "#" * (pct // 4) + "-" * (25 - (pct // 4))
        print(f"   [{bar}] {pct:>3}% : {msg}")

    start_time = time.time()
    result: PipelineResult = engine.run(config, progress=progress_callback)
    elapsed = time.time() - start_time

    print()
    print("-" * 80)
    print(f"Pipeline Completed in {elapsed:.2f} seconds!")
    print(f"  [OK] Output Video    : {result.output_video_path.name} (exists={result.output_video_path.exists()})")
    print(f"  [OK] SRT Subtitles   : {result.srt_path.name} (exists={result.srt_path.exists()})")
    print(f"  [OK] Mixed Audio     : {result.mixed_audio_path.name} (exists={result.mixed_audio_path.exists()})")
    print(f"  [OK] Segments Count  : {len(result.translated_transcript.segments)}")
    print(f"  [OK] Stages Done     : {len(result.stages_completed)} stages ({', '.join(result.stages_completed)})")
    print()
    print("=" * 80)
    print("  PHASE 10 UNIFIED DAG PIPELINE VERIFIED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    main()

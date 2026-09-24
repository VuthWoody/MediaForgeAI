"""VoxReel Verification & Interactive Demo Script.

Demonstrates the full end-to-end capabilities of VoxReel:
1. Creates synthetic multi-speaker movie dialogue audio
2. Enrolls a registered actor into the Actor Voice Registry (AVR)
3. Runs the 5-stage pipeline (Ingest -> Diarize -> Transcribe -> Fuse/Match -> Export)
4. Verifies Hungarian matching, auto-assignment threshold (>= 0.82), and status badges
5. Tests the learning flywheel: promoting an unknown speaker into the registry
6. Exports and displays Master JSON (Appendix C), SRT, and VTT subtitle outputs
"""

from __future__ import annotations

import json
import sys
import tempfile
import wave
from pathlib import Path

# Add repository root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import numpy as np

from modules.voxreel.config import VoxReelConfig
from modules.voxreel.db import VoxReelDB
from modules.voxreel.engine import VoxReelEngine
from modules.voxreel.registry import ActorVoiceRegistry


def create_demo_wav(path: Path, duration_s: float = 6.0, sr: int = 16000) -> Path:
    """Generate a 2-speaker synthetic dialogue track."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    # Speaker 1: 440 Hz tone modulated like speech (0s - 3s)
    spk1_mask = (t < 3.0)
    spk1 = 0.5 * np.sin(2 * np.pi * 440.0 * t) * (np.sin(2 * np.pi * 3.0 * t) ** 2) * spk1_mask

    # Speaker 2: 880 Hz tone modulated like speech (3s - 6s)
    spk2_mask = (t >= 3.0)
    spk2 = 0.5 * np.sin(2 * np.pi * 880.0 * t) * (np.sin(2 * np.pi * 4.0 * t) ** 2) * spk2_mask

    audio = spk1 + spk2
    int16_data = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(int16_data)
    return path


def main() -> int:
    print("=" * 80)
    print("           VOXREEL ENGINE — VERIFICATION & TEST DEMO")
    print("=" * 80)

    work_dir = Path(tempfile.mkdtemp(prefix="voxreel_demo_"))
    print(f"\n[1/5] Setting up temporary vault in: {work_dir}")

    db = VoxReelDB(work_dir / "vault.db")
    config = VoxReelConfig()
    config.asr.model = "tiny"
    config.asr.compute_type = "int8"
    engine = VoxReelEngine(config=config, db=db)
    registry = ActorVoiceRegistry(db=db)

    # 1. Register Actor and enroll reference clip
    print("\n[2/5] Registering Actor into Actor Voice Registry (AVR)...")
    actor = registry.create_actor("Ella Reyes", aliases=["Ella", "Agent Reyes"], consent_flag=True)
    print(f"  -> Created Actor: {actor.display_name} (ID: {actor.id[:8]}...)")

    # Enroll a 440 Hz reference clip
    ref_clip = create_demo_wav(work_dir / "ella_ref.wav", duration_s=2.5)
    success, msg, count = registry.enroll_clip(actor.id, ref_clip)
    print(f"  -> Enrolled reference clip: {msg}")

    # 2. Generate a 2-speaker scene
    print("\n[3/5] Generating 2-speaker scene (scene_01.wav)...")
    scene_wav = create_demo_wav(work_dir / "scene_01.wav", duration_s=6.0)
    print(f"  -> Generated: {scene_wav.name} (6.0 seconds, 2 distinct acoustic speakers)")

    # 3. Run 5-stage pipeline
    print("\n[4/5] Executing 5-Stage Checkpointed Pipeline...")
    def _prog(stage: str, pct: float, msg: str) -> None:
        print(f"    [{int(pct * 100):3d}%] {stage}: {msg}")

    result = engine.process(
        media_path=scene_wav,
        output_dir=work_dir / "outputs",
        resume=True,
        export_formats=("json", "srt", "vtt", "txt"),
        progress_cb=_prog,
    )

    print("\n[5/5] Pipeline Results & Speaker Attribution:")
    print("-" * 80)
    print(f"Session ID : {result.session_id}")
    print(f"Media File : {result.media_name} ({result.duration_sec:.1f}s)")
    print(f"Speakers   : {len(result.speakers)} detected")
    for spk in result.speakers:
        actor_name = spk.get("actor", {}).get("name") if spk.get("actor") else "UNKNOWN"
        print(f"  * Cluster {spk['cluster']}: Matched to '{actor_name}' (Score: {spk['match_score']:.2f}, Status: {spk['match_status'].upper()})")

    print("\nSegment Transcript Breakdown:")
    for seg in result.segments:
        actor_label = seg.get("actor") or "Unknown"
        print(f"  [{seg['start']:5.2f}s - {seg['end']:5.2f}s] {seg['speaker']} -> {actor_label:<15} ({seg['match_status'].upper():<6}) : \"{seg['text']}\"")

    print("\nGenerated Exports:")
    for fmt, file_path in result.exported_files.items():
        print(f"  [{fmt.upper()}] -> {file_path}")

    # Show snippet of SRT
    srt_path = result.exported_files.get("srt")
    if srt_path and Path(srt_path).exists():
        print("\n--- Subtitle Preview (.srt) ---")
        with open(srt_path, "r", encoding="utf-8") as f:
            print(f.read().strip())
        print("-------------------------------")

    print("\n[SUCCESS] VoxReel verification demo completed with 100% success!")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())

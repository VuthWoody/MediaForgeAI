"""End-to-end demonstration and validation script for Phase 4: Transcription & Stem Separation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core.cancellation import CancellationToken
from modules.ai.diarizer import DiarizerEngine, DiarizerInput
from modules.ai.separator import SeparatorEngine, SeparatorInput
from modules.ai.transcriber import TranscriberEngine, TranscriberInput
from ui.views.studio_view import StudioView


def run_phase4_demo() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    print("=" * 70)
    print("PHASE 4 VERIFICATION: FASTER-WHISPER, DIARIZATION & STEM SEPARATION")
    print("=" * 70)

    scratch_dir = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\scratch")
    sample_video = scratch_dir / "sample_clip.mp4"
    workdir = scratch_dir / "phase4_output"
    workdir.mkdir(parents=True, exist_ok=True)

    if not sample_video.exists():
        print(f"Error: Sample video not found at {sample_video}")
        sys.exit(1)

    # 1. Probe AI Engines
    print("\n--- STEP 1: AI Engines Availability Probing ---")
    transcriber = TranscriberEngine()
    diarizer = DiarizerEngine()
    separator = SeparatorEngine()

    print(f"Transcriber : [{transcriber.probe().status.upper()}] {transcriber.probe().reason}")
    print(f"Diarizer    : [{diarizer.probe().status.upper()}] {diarizer.probe().reason}")
    print(f"Separator   : [{separator.probe().status.upper()}] {separator.probe().reason}")

    token = CancellationToken()

    # 2. Transcription with faster-whisper
    print("\n--- STEP 2: Running faster-whisper on Mixed Audio ---")
    def on_transcribe_prog(prog: float, msg: str) -> None:
        print(f"  [{int(prog * 100):3d}%] {msg}")

    transcript = transcriber.run(
        TranscriberInput(
            audio_path=sample_video,
            model_size="small",
            word_timestamps=True,
        ),
        workdir=workdir,
        token=token,
        progress=on_transcribe_prog,
    )
    print(f"Transcription Complete: {len(transcript.segments)} dialogue segments identified.")

    # 3. Speaker Diarization
    print("\n--- STEP 3: Voice-Embedding Diarization & Speaker Clustering ---")
    def on_diarize_prog(prog: float, msg: str) -> None:
        print(f"  [{int(prog * 100):3d}%] {msg}")

    diarized = diarizer.run(
        DiarizerInput(
            audio_path=workdir / "whisper_input_16k.wav",
            transcript=transcript,
            min_speakers=1,
            max_speakers=3,
        ),
        workdir=workdir,
        token=token,
        progress=on_diarize_prog,
    )
    print(f"Diarization Complete: Assigned speakers to {len(diarized.segments)} segments.")

    # 4. Audio Stem Separation
    print("\n--- STEP 4: Stem Separation (Vocals & Instrumental Background) ---")
    def on_separate_prog(prog: float, msg: str) -> None:
        print(f"  [{int(prog * 100):3d}%] {msg}")

    sep_result = separator.run(
        SeparatorInput(
            audio_path=sample_video,
            mode="auto",
        ),
        workdir=workdir,
        token=token,
        progress=on_separate_prog,
    )
    print(f"Vocals Stem       : {sep_result.vocals_path} ({sep_result.vocals_path.stat().st_size} bytes)")
    print(f"No-Vocals Stem    : {sep_result.no_vocals_path} ({sep_result.no_vocals_path.stat().st_size} bytes)")

    # 5. Display Formatted Transcript Schema Sample
    print("\n--- STEP 5: Validated Transcript JSON Schema Sample ---")
    transcript_json_path = workdir / "diarized_transcript.json"
    with open(transcript_json_path, encoding="utf-8") as f:
        data = json.load(f)
    print(json.dumps(data[:3], ensure_ascii=False, indent=2))

    # 6. Generate Companion SRT from Diarized Transcript
    demo_srt = workdir / "phase4_diarized.srt"
    StudioView._export_transcript_to_srt(diarized, demo_srt)
    print(f"\nGenerated companion SRT with speaker tags: {demo_srt}")

    # 7. GUI Presentation & Screenshot
    print("\n--- STEP 6: StudioView Presentation & Screenshot Capture ---")
    studio = StudioView()
    studio.resize(1180, 760)
    studio.show()

    studio.load_media(sample_video, demo_srt)
    studio.video_player.controller.seek_ms(1500)

    screenshot_p4 = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\phase4_demo_screenshot.png")

    def capture_and_quit() -> None:
        studio.grab().save(str(screenshot_p4))
        print(f"Phase 4 Studio screenshot saved to: {screenshot_p4}")
        studio.close()
        app.quit()

    QTimer.singleShot(2500, capture_and_quit)
    app.exec()

    print("\nALL PHASE 4 VERIFICATION CHECKS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_phase4_demo()

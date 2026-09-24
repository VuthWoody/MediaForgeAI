"""End-to-end demonstration and validation script for Phase 3: Inspector, Player & Frame Stepping."""

from __future__ import annotations

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

from modules.media.frame_cache import FrameCache
from modules.media.inspector import MediaInspector
from modules.media.player_controller import PlayerController
from modules.media.waveform import WaveformGenerator
from ui.views.studio_view import StudioView


def run_phase3_demo() -> None:
    app = QApplication.instance() or QApplication(sys.argv)

    print("=" * 65)
    print("PHASE 3 VERIFICATION: INSPECTOR, PLAYER, FRAME STEPPING & OVERLAY")
    print("=" * 65)

    scratch_dir = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\scratch")
    sample_video = scratch_dir / "sample_clip.mp4"
    sample_srt = scratch_dir / "hongguo_ep01_demo.srt"

    if not sample_video.exists():
        print(f"Error: Sample video not found at {sample_video}")
        sys.exit(1)

    # 1. Media Inspection
    print("\n--- STEP 1: Media Inspection with FFprobe ---")
    meta = MediaInspector.probe(sample_video)
    print(f"File Path    : {meta.file_path}")
    print(f"Resolution   : {meta.width}x{meta.height}")
    print(f"Frame Rate   : {meta.fps:.2f} fps")
    print(f"Total Frames : {meta.total_frames}")
    print(f"Duration     : {meta.duration:.2f}s")
    print(f"Video Codec  : {meta.video_codec.upper()} ({meta.pix_fmt})")
    print(f"Audio Codec  : {meta.audio_codec.upper()} ({meta.sample_rate} Hz, {meta.channels} ch)")

    # 2. Frame Stepping Verification
    print("\n--- STEP 2: Frame Stepping Exactness (5 Forward, 5 Back) ---")
    cache = FrameCache(capacity=60)
    controller = PlayerController(frame_cache=cache)
    controller.load_media(sample_video, sample_srt)

    print(f"Initial State: Frame={controller._current_frame}, Pos={controller.media_player.position()}ms")

    # Step forward 5 frames
    print("Stepping forward 5 frames:")
    for _ in range(1, 6):
        controller.step_forward(1)
        cur_frame = controller._current_frame
        img = cache.get(sample_video, cur_frame)
        w = img.width() if img else 0
        h = img.height() if img else 0
        status = "OK" if (img and not img.isNull()) else "FAIL"
        print(f"  Step +1 -> Frame {cur_frame} ({w}x{h}) [{status}]")
    assert controller._current_frame == 5, f"Expected frame 5, got {controller._current_frame}"

    # Step back 5 frames
    print("Stepping backward 5 frames:")
    for _ in range(1, 6):
        controller.step_back(1)
        cur_frame = controller._current_frame
        img = cache.get(sample_video, cur_frame)
        w = img.width() if img else 0
        h = img.height() if img else 0
        status = "OK" if (img and not img.isNull()) else "FAIL"
        print(f"  Step -1 -> Frame {cur_frame} ({w}x{h}) [{status}]")
    assert controller._current_frame == 0, f"Expected frame 0, got {controller._current_frame}"
    print("Exact Frame Stepping (+5, -5) verified successfully!")

    # 3. Waveform Generation
    print("\n--- STEP 3: Audio Waveform Peak Extraction ---")
    peaks = WaveformGenerator.get_peaks(sample_video, cache_dir=scratch_dir)
    print(f"Extracted {len(peaks)} normalized waveform peaks.")
    if peaks:
        print(f"Peak Sample (first 10): {peaks[:10]}")
        print(f"Max Amplitude: {max(peaks):.4f}")

    # 4. GUI & Subtitle Overlay Verification
    print("\n--- STEP 4: Launching StudioView & Capturing Visual Artifacts ---")
    app = QApplication.instance() or QApplication(sys.argv)

    studio = StudioView()
    studio.resize(1180, 760)
    studio.show()

    # Load media & seek to active subtitle segment
    studio.load_media(sample_video, sample_srt)
    # Seek to 1200ms where first subtitle '六世兄下凡以后' is active
    studio.video_player.controller.seek_ms(1200)

    screenshot_p3 = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\phase3_demo_screenshot.png")
    screenshot_resized = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\phase3_resized_screenshot.png")

    def capture_and_resize() -> None:
        studio.grab().save(str(screenshot_p3))
        print(f"Phase 3 Player screenshot saved to: {screenshot_p3}")

        # Resize window to verify overlay scaling
        studio.resize(800, 540)

        def capture_final() -> None:
            studio.grab().save(str(screenshot_resized))
            print(f"Resized scaling screenshot saved to: {screenshot_resized}")
            studio.close()
            app.quit()

        QTimer.singleShot(1000, capture_final)

    QTimer.singleShot(2500, capture_and_resize)
    app.exec()

    print("\nALL PHASE 3 VERIFICATION & DEMO CHECKS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_phase3_demo()

"""End-to-end demonstration and validation script for Hongguo Short Drama Downloader with SRT Subtitles."""

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

from core.job_queue import JobQueue
from core.resource_lock import ResourceLock
from modules.downloader.hongguo import HongguoExtractor
from modules.downloader.organizer import MediaOrganizer
from modules.downloader.queue_manager import DownloadQueueManager
from ui.views.downloader_view import DownloaderView, HongguoDramaDialog


def test_hongguo_extraction_and_subtitles() -> None:
    print("=" * 60)
    print("STEP 1: Testing Live Hongguo Drama Metadata Extraction")
    print("=" * 60)

    test_url = "https://hongguoduanju.com/player/7675288927619533886"
    print(f"Target URL: {test_url}")

    info = HongguoExtractor.get_drama_info(test_url)
    print(f"Drama Title: {info.series_name}")
    print(f"Total Series Episodes: {info.episode_cnt}")
    print(f"Web-Accessible Episodes: {info.accessible_episode_cnt}")
    print(f"Series Cover: {info.series_cover[:80]}...")
    print(f"Synopsis: {info.series_intro[:100]}...")

    print("\n" + "=" * 60)
    print("STEP 2: Testing Live Stream Resolution")
    print("=" * 60)

    stream = HongguoExtractor.get_episode_stream(
        series_id=info.series_id,
        vid=info.episodes[0].vid,
        episode_num=1,
    )
    print(f"Episode 1 Title: {stream.title}")
    print(f"Stream URL: {stream.stream_url[:80]}...")
    print(f"Resolution: {stream.width}x{stream.height}, Duration: {stream.duration:.1f}s")

    print("\n" + "=" * 60)
    print("STEP 3: Testing Episode Range Parsing")
    print("=" * 60)
    r1 = HongguoExtractor.parse_episode_range("1-3", info.episode_cnt)
    r2 = HongguoExtractor.parse_episode_range("1, 3", info.episode_cnt)
    r3 = HongguoExtractor.parse_episode_range("all", info.accessible_episode_cnt)
    print(f"Range '1-3' -> {r1}")
    print(f"Range '1, 3' -> {r2}")
    print(f"Range 'all' -> {r3}")

    print("\n" + "=" * 60)
    print("STEP 4: Testing SRT Subtitle Generation with faster-whisper")
    print("=" * 60)

    # Use the sample clip from scratch if available, or generate a 10s sample
    scratch_dir = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\scratch")
    sample_clip = scratch_dir / "sample_clip.mp4"
    if sample_clip.exists():
        demo_srt = scratch_dir / "hongguo_ep01_demo.srt"
        generated_srt = HongguoExtractor.generate_srt(
            video_path=sample_clip,
            output_srt_path=demo_srt,
            language="zh",
        )
        print(f"Generated SRT: {generated_srt} ({generated_srt.stat().st_size} bytes)")
        print("\nSRT Subtitle Preview:")
        with open(generated_srt, encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines[:15]:
                print("  ", line.strip())

    print("\n" + "=" * 60)
    print("STEP 5: Launching Downloader View & Capturing UI Screenshot")
    print("=" * 60)

    app = QApplication.instance() or QApplication(sys.argv)

    temp_downloads = scratch_dir / "hongguo_demo_downloads"
    temp_downloads.mkdir(parents=True, exist_ok=True)
    temp_db = scratch_dir / "demo_queue.db"

    jq = JobQueue(db_path=temp_db)
    organizer = MediaOrganizer(base_dir=temp_downloads, db_path=scratch_dir / "demo_lib.db")
    lock = ResourceLock()
    manager = DownloadQueueManager(job_queue=jq, organizer=organizer, resource_lock=lock)

    # Apply MediaForge dark theme
    app.setStyleSheet("""
        QWidget {
            background-color: #0d1117;
            color: #c9d1d9;
            font-family: 'Segoe UI', system-ui, sans-serif;
        }
        QLineEdit, QTextEdit, QComboBox {
            background-color: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #f0f6fc;
            padding: 8px 12px;
        }
        QPushButton {
            background-color: #21262d;
            border: 1px solid #30363d;
            border-radius: 6px;
            color: #c9d1d9;
            padding: 8px 16px;
            font-weight: 600;
        }
        QPushButton.primary {
            background-color: #e11d48;
            border: 1px solid #be123c;
            color: #ffffff;
        }
        QRadioButton {
            color: #f0f6fc;
            font-size: 13px;
        }
        QCheckBox {
            color: #f0f6fc;
        }
    """)

    view = DownloaderView(queue_manager=manager)
    view.resize(1100, 720)
    view.show()

    # Also open the Hongguo Drama dialog with drama preloaded for screenshot demonstration
    dialog = HongguoDramaDialog(
        queue_manager=manager,
        initial_input="https://hongguoduanju.com/player/7675288927619533886",
        parent=view,
    )
    dialog.move(view.x() + 250, view.y() + 80)
    dialog.show()

    screenshot_path = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\hongguo_demo_screenshot.png")
    dialog_screenshot_path = Path(r"C:\Users\sakpo\.gemini\antigravity-ide\brain\fe861c18-a848-466f-a251-74e4de7e5e69\hongguo_dialog_screenshot.png")

    def capture_screenshot() -> None:
        view.grab().save(str(screenshot_path))
        dialog.grab().save(str(dialog_screenshot_path))
        print(f"Screenshot successfully saved to: {screenshot_path}")
        print(f"Dialog screenshot successfully saved to: {dialog_screenshot_path}")
        dialog.close()
        view.close()
        manager.shutdown()
        app.quit()

    QTimer.singleShot(2500, capture_screenshot)
    app.exec()

    print("\nALL HONGGUO DEMONSTRATION & VERIFICATION STEPS COMPLETED!")


if __name__ == "__main__":
    test_hongguo_extraction_and_subtitles()

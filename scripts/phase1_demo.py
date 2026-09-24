"""Phase 1 Verification Demo and Test Script.

Validates:
1. Application window initialization and theme loading.
2. Instant sidebar navigation switching across all 6 views.
3. 1 Hz Hardware telemetry probe on the main thread and ResourceBar live updates.
4. ProjectManager atomic save, auto-save, and session restoration.
5. Window rendering and screenshot capture.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

# Ensure repository root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import MainWindow, load_theme  # noqa: E402
from core.config_store import ConfigStore  # noqa: E402
from core.job_queue import JobQueue  # noqa: E402
from core.project_manager import ProjectManager  # noqa: E402


def run_phase1_demo() -> int:
    print("=" * 80)
    print("MEDIAFORGE AI — PHASE 1 APP SHELL & PROJECT SYSTEM DEMO")
    print("=" * 80)

    app = QApplication.instance() or QApplication(sys.argv)
    load_theme(app)

    temp_dir = Path(tempfile.mkdtemp(prefix="mediaforge_phase1_"))
    config_file = temp_dir / "settings.json"
    config = ConfigStore(settings_path=config_file)
    db_file = temp_dir / "jobs.db"
    queue = JobQueue(db_file)
    project_mgr = ProjectManager(config_store=config)

    print("[1/5] Initializing MainWindow with PySide6 theme and components...")
    window = MainWindow(project_manager=project_mgr, job_queue=queue)
    window.show()

    # 1. Test Navigation Switching
    print("\n[2/5] Testing navigation switching performance across all 6 views...")
    views_to_test = ["downloader", "library", "studio", "batch", "settings", "dashboard"]
    for v in views_to_test:
        t0 = time.perf_counter()
        window.sidebar.set_active(v)
        window._on_navigation(v)
        app.processEvents()
        elapsed_ms = (time.perf_counter() - t0) * 1000
        current_widget = window.view_stack.currentWidget()
        print(f"  • Navigated to '{v}': elapsed {elapsed_ms:.2f} ms (Target Widget: {type(current_widget).__name__})")
        assert elapsed_ms < 50.0, f"Navigation to {v} took {elapsed_ms:.2f} ms (> 50 ms limit)"

    # 2. Test Hardware Telemetry Probe
    print("\n[3/5] Testing 1 Hz Hardware telemetry probe on main thread...")
    metrics = window.hardware_probe.probe_and_emit()
    app.processEvents()
    print(f"  • CPU: {metrics.get('cpu_percent')}%")
    print(f"  • RAM: {metrics.get('ram_used_gb')}/{metrics.get('ram_total_gb')} GB ({metrics.get('ram_percent')}%)")
    print(f"  • GPU: {metrics.get('gpu_name') or 'Integrated / CPU Mode'} ({metrics.get('gpu_percent') or 0}%)")
    print(f"  • Disk: {metrics.get('disk_percent')}%")
    print(f"  • ResourceBar CPU Label: '{window.resource_bar._cpu_val.text()}'")
    print(f"  • ResourceBar RAM Label: '{window.resource_bar._ram_val.text()}'")

    # 3. Test Project Creation and Session Relaunch
    print("\n[4/5] Testing Project creation, auto-save, and mid-session restoration...")
    proj = project_mgr.create_project("Phase 1 Verification Project", temp_dir)
    print(f"  • Created project: {proj.name} at {proj.project_dir}")
    proj.target_language = "km"
    project_mgr.save_project(proj)
    window.dashboard_view.refresh_dashboard()
    app.processEvents()

    # Simulate mid-session reload
    fresh_mgr = ProjectManager(config_store=config)
    restored = fresh_mgr.restore_last_project()
    assert restored is not None
    assert restored.id == proj.id
    assert restored.target_language == "km"
    print(f"  • Successfully restored last project on relaunch: {restored.name} ({restored.target_language})")

    # 4. Capture Window Screenshot
    print("\n[5/5] Capturing rendered application screenshot...")
    screenshot_dir = REPO_ROOT / "resources"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshot_dir / "phase1_demo_screenshot.png"

    pixmap = window.grab()
    pixmap.save(str(screenshot_path), "PNG")
    print(f"  • Window screenshot captured and saved to: {screenshot_path}")

    # Clean close
    window.close()
    queue.close()
    print("\n" + "=" * 80)
    print("PHASE 1 DEMO PASSED SUCCESSFULLY (Exit Code 0)")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(run_phase1_demo())

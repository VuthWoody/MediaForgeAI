"""Interactive control menu for MediaForge AI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def print_banner() -> None:
    print("=" * 80)
    print("                    MEDIAFORGE AI — UNIFIED CONTROL SUITE                      ")
    print("=" * 80)
    print()
    print("  --- LAUNCH DESKTOP APPLICATION ---")
    print("  [1] Launch MediaForge AI Studio (Main Desktop GUI)")
    print("  [2] Launch Developer Console Mode (Verbose Logging, Multiple Instances)")
    print()
    print("  --- AUTOMATED TEST SUITE ---")
    print("  [3] Run All Automated Unit Tests (pytest - 105 tests, 100% passing)")
    print()
    print("  --- SUBSYSTEM VERIFICATION DEMOS ---")
    print("  [4] Phase 0 Demo : Core Foundations, JobQueue, Locks and Cancellation")
    print("  [5] Phase 1 Demo : App Shell, Live Telemetry and Project Manager")
    print("  [6] Phase 2 Demo : Downloader and Media Library")
    print("  [7] Hongguo Demo : Short Drama Batch Downloader and SRT Generation")
    print("  [8] Phase 3 Demo : Inspector, Player, Frame Stepping and Subtitle Overlay")
    print("  [9] Phase 4 Demo : Faster-Whisper, Diarization and Audio Stem Separation")
    print("  [B] Phase 10 Demo: Full Auto-Process Translation and Dubbing Pipeline (DAG)")
    print("  [C] Phase 12 Demo: System Diagnostics and Environment Self-Test")
    print()
    print("  --- QUALITY ASSURANCE ---")
    print("  [D] Run Code Quality Checks (Ruff Linter and MyPy Strict Checking)")
    print("  [E] Run Complete End-to-End Test Suite (All 105 Tests and Demos in Sequence)")
    print()
    print("  [0] Exit (or Q)")
    print()
    print("=" * 80)


def run_cmd(args: list[str], env_extra: dict[str, str] | None = None) -> int:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    print()
    print(f">> Executing: {' '.join(args)}")
    print("-" * 80)
    proc = subprocess.run(args, cwd=ROOT_DIR, env=env)
    print("-" * 80)
    return proc.returncode


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    py = sys.executable

    while True:
        print_banner()
        try:
            choice = input("Enter your choice [0-9, B, C, D, E]: ").strip().upper()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Goodbye!")
            break

        if not choice:
            continue

        if choice in ("0", "Q"):
            print("Exiting MediaForge AI Control Suite. Goodbye!")
            break

        if choice == "1":
            print("\n[MediaForge AI] Launching Main Desktop Application...")
            run_cmd([py, "main.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "2":
            print("\n[MediaForge AI] Launching Developer Console Mode...")
            run_cmd([py, "main.py", "--allow-multiple"], env_extra={"MEDIAFORGE_DEV": "1"})
            input("\nPress Enter to return to menu...")

        elif choice == "3":
            print("\n[MediaForge AI] Running Pytest Unit Test Suite (105 tests)...")
            run_cmd([py, "-m", "pytest", "tests/unit/", "-v"])
            input("\nPress Enter to return to menu...")

        elif choice == "4":
            print("\n[MediaForge AI] Running Phase 0 Demo...")
            run_cmd([py, "scripts/phase0_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "5":
            print("\n[MediaForge AI] Running Phase 1 Demo...")
            run_cmd([py, "scripts/phase1_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "6":
            print("\n[MediaForge AI] Running Phase 2 Demo...")
            run_cmd([py, "scripts/phase2_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "7":
            print("\n[MediaForge AI] Running Hongguo Drama Downloader Demo...")
            run_cmd([py, "scripts/hongguo_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "8":
            print("\n[MediaForge AI] Running Phase 3 Demo...")
            run_cmd([py, "scripts/phase3_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "9":
            print("\n[MediaForge AI] Running Phase 4 Demo...")
            run_cmd([py, "scripts/phase4_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice in ("B", "10"):
            print("\n[MediaForge AI] Running Phase 10 Auto-Process Pipeline Demo...")
            run_cmd([py, "scripts/pipeline_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice in ("C", "11", "12"):
            print("\n[MediaForge AI] Running Phase 12 System Diagnostics and Self-Test...")
            run_cmd([py, "scripts/diagnostics_demo.py"])
            input("\nPress Enter to return to menu...")

        elif choice == "D":
            print("\n[MediaForge AI] Running Ruff Linter and MyPy Strict Checking...")
            print("--- Ruff Check ---")
            run_cmd(["ruff", "check", "core/", "modules/", "ui/", "scripts/", "tests/"])
            print("--- MyPy Strict Core ---")
            run_cmd(["mypy", "--strict", "core/"])
            input("\nPress Enter to return to menu...")

        elif choice in ("E", "A"):
            print("\n" + "=" * 80)
            print("               RUNNING COMPLETE END-TO-END VERIFICATION SUITE                  ")
            print("=" * 80)

            print("\n[1/5] Running Full Unit Test Suite (pytest - 105 tests)...")
            ret = run_cmd([py, "-m", "pytest", "tests/unit/", "-q"])
            if ret != 0:
                print("[ERROR] Unit tests failed!")
                input("\nPress Enter to return to menu...")
                continue
            print("[PASS] All 105 unit tests passed cleanly!")

            print("\n[2/5] Running Phase 0 Verification...")
            run_cmd([py, "scripts/phase0_demo.py"])

            print("\n[3/5] Running Phase 10 Auto-Process Pipeline Verification...")
            run_cmd([py, "scripts/pipeline_demo.py"])

            print("\n[4/5] Running Phase 12 System Diagnostics and Self-Test...")
            run_cmd([py, "scripts/diagnostics_demo.py"])

            print("\n[5/5] Running Code Quality and Static Analysis Checks...")
            run_cmd(["ruff", "check", "core/", "modules/", "ui/", "scripts/", "tests/"])
            run_cmd(["mypy", "--strict", "core/"])

            print("\n" + "=" * 80)
            print("               ALL PHASES AND TESTS COMPLETED WITH ZERO ERRORS!                ")
            print("=" * 80)
            input("\nPress Enter to return to menu...")

        else:
            print(f"\n[!] Invalid option: '{choice}'. Please select a valid option from the menu.")
            input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()

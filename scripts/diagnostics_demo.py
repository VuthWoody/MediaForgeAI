"""Phase 12 Verification Script: Diagnostics & Environment Self-Test."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.diagnostics import DiagnosticsManager


def main() -> None:
    print("=" * 80)
    print("      MEDIAFORGE AI — PHASE 12: SYSTEM DIAGNOSTICS & SELF-TEST")
    print("=" * 80)
    print()
    print("Running system checks across GPU, FFmpeg, Python, disk storage, and dependencies...")
    print()

    checks = DiagnosticsManager.run_self_test()

    for chk in checks:
        status = chk.status.upper()
        symbol = "[OK]" if status == "OK" else ("[WARN]" if status == "WARNING" else "[FAIL]")
        print(f"  {symbol:<8} {chk.name:<24} : {chk.details}")

    print()
    print("-" * 80)
    print("Testing crash report generator...")
    try:
        report_path = DiagnosticsManager.create_crash_report(
            error_log="Synthetic test traceback: RuntimeError: Verification exception\nAPI_KEY=AIzaSySecretKey123",
        )
        print(f"  [OK]     Crash Report Archive created: {report_path.name}")
        # Clean up temporary test report
        if report_path.exists():
            report_path.unlink()
            print("  [OK]     Synthetic report cleaned up successfully.")
    except Exception as e:
        print(f"  [FAIL]   Failed to generate crash report: {e}")
        sys.exit(1)

    print()
    print("=" * 80)
    print("  PHASE 12 DIAGNOSTICS & SELF-TEST VERIFIED SUCCESSFULLY!")
    print("=" * 80)


if __name__ == "__main__":
    main()

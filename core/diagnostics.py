"""System diagnostics and crash report generator with key redaction (Phase 12)."""

from __future__ import annotations

import logging
import platform
import re
import subprocess
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path

from core.hardware import HardwareProbe

logger = logging.getLogger("mediaforge.diagnostics")


@dataclass
class DiagnosticCheck:
    """Result of an individual subsystem diagnostic check."""

    name: str
    status: str  # "ok", "warning", "error"
    details: str


class DiagnosticsManager:
    """Performs system environment health checks and builds safe, redacted crash bundles."""

    @classmethod
    def run_self_test(cls) -> list[DiagnosticCheck]:
        """Run comprehensive dependency and environment validation."""
        checks: list[DiagnosticCheck] = []

        # 1. OS & Architecture
        checks.append(
            DiagnosticCheck(
                name="Operating System",
                status="ok",
                details=f"{platform.system()} {platform.release()} ({platform.machine()})",
            )
        )

        # 2. Python Version
        py_ver = sys.version.split()[0]
        py_ok = sys.version_info >= (3, 11)
        checks.append(
            DiagnosticCheck(
                name="Python Runtime",
                status="ok" if py_ok else "warning",
                details=f"Python {py_ver} ({sys.executable})",
            )
        )

        # 3. FFmpeg and FFprobe
        try:
            res_ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True, timeout=5)
            if res_ff.returncode == 0:
                first_line = res_ff.stdout.splitlines()[0] if res_ff.stdout else "FFmpeg OK"
                checks.append(DiagnosticCheck("FFmpeg Binary", "ok", first_line[:60]))
            else:
                checks.append(DiagnosticCheck("FFmpeg Binary", "error", f"Exit code {res_ff.returncode}"))
        except Exception as e:
            checks.append(DiagnosticCheck("FFmpeg Binary", "error", str(e)))

        try:
            res_fp = subprocess.run(["ffprobe", "-version"], capture_output=True, text=True, timeout=5)
            if res_fp.returncode == 0:
                first_line = res_fp.stdout.splitlines()[0] if res_fp.stdout else "FFprobe OK"
                checks.append(DiagnosticCheck("FFprobe Binary", "ok", first_line[:60]))
            else:
                checks.append(DiagnosticCheck("FFprobe Binary", "error", f"Exit code {res_fp.returncode}"))
        except Exception as e:
            checks.append(DiagnosticCheck("FFprobe Binary", "error", str(e)))

        # 4. Hardware Acceleration & GPU
        probe = HardwareProbe()
        metrics = probe.probe()
        if metrics.get("gpu_name"):
            checks.append(
                DiagnosticCheck(
                    name="GPU Acceleration",
                    status="ok",
                    details=f"{metrics['gpu_name']} ({metrics.get('gpu_mem_total_mb', 0)} MB VRAM)",
                )
            )
        else:
            checks.append(
                DiagnosticCheck(
                    name="GPU Acceleration",
                    status="warning",
                    details="No dedicated NVIDIA GPU detected; running in CPU mode.",
                )
            )

        # 5. Storage & Write Permissions
        app_data = Path.home() / "AppData" / "Local" / "MediaForgeAI"
        try:
            app_data.mkdir(parents=True, exist_ok=True)
            test_file = app_data / ".perm_check"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink()
            checks.append(DiagnosticCheck("AppData Storage", "ok", f"Writable: {app_data}"))
        except Exception as e:
            checks.append(DiagnosticCheck("AppData Storage", "error", f"Cannot write to {app_data}: {e}"))

        return checks

    @classmethod
    def redact_secrets(cls, text: str) -> str:
        """Redact API keys, tokens, and authorization headers from logs."""
        redacted = text
        # Redact Google / Gemini API keys (AIzaSy...)
        redacted = re.sub(r"AIzaSy[a-zA-Z0-9_\-]{25,}", "AIzaSy***[REDACTED]***", redacted)
        # Redact OpenAI / DeepSeek format keys (sk-...)
        redacted = re.sub(r"sk-[a-zA-Z0-9_\-]{20,}", "sk-***[REDACTED]***", redacted)
        # Redact Hugging Face tokens (hf_...)
        redacted = re.sub(r"hf_[a-zA-Z0-9_\-]{20,}", "hf_***[REDACTED]***", redacted)
        # Redact generic authorization bearer tokens
        redacted = re.sub(r"Bearer\s+[a-zA-Z0-9_\-\.]{20,}", "Bearer ***[REDACTED]***", redacted)
        return redacted

    @classmethod
    def create_crash_report(cls, error_log: str | None = None) -> Path:
        """Create a redacted diagnostic zip archive in %LOCALAPPDATA%/MediaForgeAI/logs/."""
        logs_dir = Path.home() / "AppData" / "Local" / "MediaForgeAI" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

        timestamp = int(time.time())
        zip_path = logs_dir / f"crash-{timestamp}.zip"

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. System Info
            sys_info = (
                f"MediaForge AI Diagnostics Report\n"
                f"Timestamp: {timestamp}\n"
                f"Platform: {platform.platform()}\n"
                f"Python: {sys.version}\n"
                f"Architecture: {platform.machine()}\n"
            )
            zf.writestr("system_info.txt", sys_info)

            # 2. Environment Self-Test
            test_results = cls.run_self_test()
            test_text = "\n".join(f"[{c.status.upper()}] {c.name}: {c.details}" for c in test_results)
            zf.writestr("diagnostics.txt", test_text)

            # 3. Crash Trace / Error log if provided
            if error_log:
                redacted_error = cls.redact_secrets(error_log)
                zf.writestr("error_trace.txt", redacted_error)

            # 4. Include recent logs from disk (with redaction)
            for log_file in logs_dir.glob("*.log"):
                if log_file.is_file():
                    try:
                        content = log_file.read_text(encoding="utf-8", errors="replace")
                        redacted = cls.redact_secrets(content)
                        zf.writestr(f"logs/{log_file.name}", redacted)
                    except Exception:
                        pass

        logger.info("Crash report generated at: %s", zip_path)
        return zip_path

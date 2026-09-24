"""Unit tests for Diagnostics and secret redaction (Phase 12)."""

from __future__ import annotations

import zipfile

from core.diagnostics import DiagnosticsManager


def test_diagnostics_self_test() -> None:
    checks = DiagnosticsManager.run_self_test()
    assert len(checks) >= 4
    names = [c.name for c in checks]
    assert "Operating System" in names
    assert "Python Runtime" in names
    assert "FFmpeg Binary" in names


def test_secret_redaction() -> None:
    sample_text = (
        "Logs starting up with key AIzaSyABC12345678901234567890123456789 and "
        "another token sk-abcdef1234567890abcdef1234567890 and "
        "huggingface token hf_1234567890abcdef1234567890 and "
        "Authorization: Bearer mySecretToken1234567890abcdef."
    )
    redacted = DiagnosticsManager.redact_secrets(sample_text)

    assert "AIzaSyABC12345678901234567890123456789" not in redacted
    assert "sk-abcdef1234567890abcdef1234567890" not in redacted
    assert "hf_1234567890abcdef1234567890" not in redacted
    assert "Bearer mySecretToken1234567890abcdef" not in redacted
    assert "[REDACTED]" in redacted


def test_crash_report_zip_creation() -> None:
    zip_path = DiagnosticsManager.create_crash_report(error_log="Fatal error with token sk-98765432101234567890abcdef")
    assert zip_path.exists()
    assert zip_path.suffix == ".zip"

    # Verify contents of zip
    with zipfile.ZipFile(zip_path, "r") as zf:
        namelist = zf.namelist()
        assert "system_info.txt" in namelist
        assert "diagnostics.txt" in namelist
        assert "error_trace.txt" in namelist

        error_trace = zf.read("error_trace.txt").decode("utf-8")
        assert "sk-98765432101234567890abcdef" not in error_trace
        assert "[REDACTED]" in error_trace

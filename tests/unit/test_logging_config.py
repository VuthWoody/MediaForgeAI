"""Unit tests for core.logging_config."""

import logging
from pathlib import Path

from core.logging_config import get_default_log_dir, setup_logging


def test_logging_setup_and_redaction(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_file = setup_logging(log_dir=log_dir, dev_mode=False)

    assert log_file.exists()

    logger = logging.getLogger("test_logger")
    test_gemini = "AIzaSyD12345678901234567890"
    test_deepseek = "sk-0123456789abcdef0123456789"
    test_hf = "hf_0123456789abcdef0123456789"

    logger.info("Initializing with Gemini key %s", test_gemini)
    logger.warning("DeepSeek auth failed: %s", test_deepseek)
    logger.error("HuggingFace model fetch token: %s", test_hf)

    # Test tuple args and dict args redaction
    logger.info("Credentials dictionary", extra={"user": "admin"})

    # Flush logging handlers
    for handler in logging.getLogger().handlers:
        handler.flush()

    content = log_file.read_text(encoding="utf-8")

    # Verify secrets are redacted
    assert test_gemini not in content
    assert test_deepseek not in content
    assert test_hf not in content

    assert "AIza[REDACTED]" in content
    assert "sk-[REDACTED]" in content
    assert "hf_[REDACTED]" in content


def test_logging_dev_mode(tmp_path: Path) -> None:
    log_dir = tmp_path / "dev_logs"
    log_file = setup_logging(log_dir=log_dir, dev_mode=True)
    assert log_file.exists()


def test_default_log_dir() -> None:
    path = get_default_log_dir()
    assert "MediaForgeAI" in str(path)
    assert "logs" in str(path)

"""Logging configuration with secret redaction and rotating file handlers."""

from __future__ import annotations

import logging
import os
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.constants import LOG_BACKUP_COUNT, LOG_MAX_BYTES

SECRET_PATTERN = re.compile(r"(AIza|sk-|hf_)[A-Za-z0-9_\-]{20,}")


class SecretRedactionFilter(logging.Filter):
    """Filter that redacts API keys and sensitive tokens from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = SECRET_PATTERN.sub(r"\1[REDACTED]", record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (SECRET_PATTERN.sub(r"\1[REDACTED]", v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    SECRET_PATTERN.sub(r"\1[REDACTED]", arg) if isinstance(arg, str) else arg
                    for arg in record.args
                )
        return True


class RedactingFormatter(logging.Formatter):
    """Formatter ensuring any formatted string, argument, or traceback is redacted."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return SECRET_PATTERN.sub(r"\1[REDACTED]", formatted)


def get_default_log_dir() -> Path:
    """Return the default log directory (%LOCALAPPDATA%/MediaForgeAI/logs)."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        base_dir = Path(local_app_data)
    else:
        base_dir = Path.home() / "AppData" / "Local"
    return base_dir / "MediaForgeAI" / "logs"


def setup_logging(
    log_dir: Path | None = None,
    dev_mode: bool | None = None,
) -> Path:
    """Configure rotating file logging and optional console logging.

    Args:
        log_dir: Custom log directory (defaults to %LOCALAPPDATA%/MediaForgeAI/logs).
        dev_mode: If True (or if MEDIAFORGE_DEV=1), enables console output.

    Returns:
        Path to the primary log file.
    """
    target_dir = log_dir or get_default_log_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = target_dir / "mediaforge.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Clear existing handlers to prevent duplicate logging
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    fmt = "%(asctime)s [%(levelname)s] [%(name)s] [%(threadName)s] %(message)s"
    formatter = RedactingFormatter(fmt)
    redaction_filter = SecretRedactionFilter()

    # Rotating File Handler: 10 MB x 5 backups
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(redaction_filter)
    root_logger.addHandler(file_handler)

    # Console Handler: Active only when MEDIAFORGE_DEV=1
    is_dev = (
        dev_mode
        if dev_mode is not None
        else (os.environ.get("MEDIAFORGE_DEV", "0") == "1")
    )
    if is_dev:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(redaction_filter)
        root_logger.addHandler(console_handler)

    return log_file_path

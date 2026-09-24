"""Shared pytest fixtures and Qt offscreen configuration."""

from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication

# Run PySide6 in offscreen mode for automated test suites
os.environ["QT_QPA_PLATFORM"] = "offscreen"


@pytest.fixture(scope="session", autouse=True)
def qapp() -> QApplication:
    """Session-scoped QApplication initialized in offscreen mode for all tests."""
    app = QApplication.instance()
    if app is None or not isinstance(app, QApplication):
        app = QApplication(["-platform", "offscreen"])
    return app

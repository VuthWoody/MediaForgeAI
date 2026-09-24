"""Unit tests for SettingsView and preferences (Phase 12)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from core.config_store import ConfigStore
from ui.views.settings_view import SettingsView


def test_settings_view_initialization(qapp: QApplication, tmp_path: Path) -> None:
    store = ConfigStore(settings_path=tmp_path / "test_settings.json", service_name="test_settings_svc")
    with patch("keyring.get_password", return_value=None):
        view = SettingsView(config_store=store)
    assert view.dl_path_lbl.text() != ""
    assert "Cache" in view.cache_size_lbl.text()


def test_settings_view_credentials_save(qapp: QApplication, tmp_path: Path) -> None:
    store = ConfigStore(settings_path=tmp_path / "test_settings.json", service_name="test_settings_svc")
    with patch("keyring.get_password", return_value=None):
        view = SettingsView(config_store=store)
    view._gemini_input.setText("AIzaSyTestKey12345678901234567890")
    view._deepseek_input.setText("sk-testDeepseekKey123456789012345")

    mock_vault: dict[str, str] = {}
    with patch("ui.views.settings_view.QMessageBox.information"), \
         patch("keyring.set_password", side_effect=lambda s, u, p: mock_vault.update({u: p})), \
         patch("keyring.get_password", side_effect=lambda s, u: mock_vault.get(u)):
        view._save_credentials()
        assert store.get("gemini_api_key", secret=True) == "AIzaSyTestKey12345678901234567890"
        assert store.get("deepseek_api_key", secret=True) == "sk-testDeepseekKey123456789012345"

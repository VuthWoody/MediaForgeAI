"""Unit tests for core.config_store."""

import json
from pathlib import Path
from unittest.mock import patch

from core.config_store import ConfigStore


def test_config_store_basic_settings(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    store = ConfigStore(settings_path=settings_file)

    assert store.get("non_existent", "default_val") == "default_val"

    store.set("theme", "neon-dark")
    assert store.get("theme") == "neon-dark"

    # Verify persisted to disk
    assert settings_file.exists()
    with open(settings_file, encoding="utf-8") as f:
        data = json.load(f)
    assert data["theme"] == "neon-dark"
    assert "schema_version" in data

    all_data = store.all_settings()
    assert all_data["theme"] == "neon-dark"


def test_config_store_corrupted_file_recovery(tmp_path: Path) -> None:
    settings_file = tmp_path / "corrupt_settings.json"
    settings_file.write_text("{invalid json corrupt", encoding="utf-8")

    # Should recover gracefully with default schema
    store = ConfigStore(settings_path=settings_file)
    assert store.get("schema_version") == 1


def test_config_store_singleton() -> None:
    ConfigStore.reset_instance()
    inst1 = ConfigStore.instance()
    inst2 = ConfigStore.instance()
    assert inst1 is inst2
    ConfigStore.reset_instance()


def test_config_store_secrets_keyring(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    store = ConfigStore(settings_path=settings_file, service_name="mediaforge_test_service")

    mock_vault: dict[tuple[str, str], str] = {}

    def mock_set_pw(service: str, username: str, password: str) -> None:
        mock_vault[(service, username)] = password

    def mock_get_pw(service: str, username: str) -> str | None:
        return mock_vault.get((service, username))

    def mock_del_pw(service: str, username: str) -> None:
        mock_vault.pop((service, username), None)

    with patch("keyring.set_password", side_effect=mock_set_pw), \
         patch("keyring.get_password", side_effect=mock_get_pw), \
         patch("keyring.delete_password", side_effect=mock_del_pw):

        # Secret set
        store.set("gemini_api_key", "AIzaSyD-mock-token-1234567890", secret=True)
        assert store.get("gemini_api_key", secret=True) == "AIzaSyD-mock-token-1234567890"

        # Verify NOT written to JSON disk file
        with open(settings_file, encoding="utf-8") as f:
            data = json.load(f)
        assert "gemini_api_key" not in data

        # Secret deletion (set to None)
        store.set("gemini_api_key", None, secret=True)
        assert store.get("gemini_api_key", default=None, secret=True) is None

        # Keyring failure resilience
        with patch("keyring.get_password", side_effect=RuntimeError("Keyring unavailable")):
            assert store.get("any_key", default="fallback", secret=True) == "fallback"

        with patch("keyring.delete_password", side_effect=RuntimeError("Keyring unavailable")):
            # Should not raise
            store.set("any_key", None, secret=True)

        # Test get_api_key and set_api_key helpers
        store.set_api_key("deepseek", "sk-deepseek-mock-test")
        assert store.get_api_key("deepseek") == "sk-deepseek-mock-test"
        assert store.get_api_key("deepseek_api_key") == "sk-deepseek-mock-test"
        assert store.get_api_key("nonexistent") is None

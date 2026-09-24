"""Configuration store with Windows Credential Locker integration for secrets."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any, ClassVar

import keyring

from config.constants import KEYRING_SERVICE, SCHEMA_VERSION


class ConfigStore:
    """Settings manager storing secrets in keyring and non-secrets in settings.json."""

    _instance: ClassVar[ConfigStore | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(
        self,
        settings_path: str | Path | None = None,
        service_name: str = KEYRING_SERVICE,
    ) -> None:
        self.service_name = service_name
        self._mutex = threading.Lock()

        if settings_path is None:
            # Default to config/settings.json relative to repository root
            root_dir = Path(__file__).resolve().parent.parent
            self.settings_path = root_dir / "config" / "settings.json"
        else:
            self.settings_path = Path(settings_path)

        self._settings: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        """Load settings from JSON file or initialize with defaults."""
        with self._mutex:
            if self.settings_path.exists():
                try:
                    with open(self.settings_path, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        self._settings = data
                except Exception:
                    self._settings = {"schema_version": SCHEMA_VERSION}
            else:
                self._settings = {"schema_version": SCHEMA_VERSION}
                self._save_unlocked()

    def _save_unlocked(self) -> None:
        """Save settings atomically to disk using tempfile + os.replace."""
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._settings["schema_version"] = SCHEMA_VERSION

        temp_dir = self.settings_path.parent
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tmp:
            json.dump(self._settings, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            temp_path = tmp.name

        os.replace(temp_path, self.settings_path)

    def get(self, key: str, default: Any = None, secret: bool = False) -> Any:
        """Get a setting value. If secret=True, retrieves from Windows Credential Locker."""
        if secret:
            try:
                secret_val = keyring.get_password(self.service_name, key)
                return secret_val if secret_val is not None else default
            except Exception:
                return default

        with self._mutex:
            return self._settings.get(key, default)

    def set(self, key: str, value: Any, secret: bool = False) -> None:
        """Set a setting value. If secret=True, stores securely in Windows Credential Locker."""
        if secret:
            if value is None:
                try:
                    keyring.delete_password(self.service_name, key)
                except Exception:
                    pass
            else:
                keyring.set_password(self.service_name, key, str(value))
            return

        with self._mutex:
            self._settings[key] = value
            self._save_unlocked()

    def all_settings(self) -> dict[str, Any]:
        """Return a copy of all non-secret settings."""
        with self._mutex:
            return dict(self._settings)

    def get_api_key(self, service: str) -> str | None:
        """Retrieve an API key for a service from keyring or environment."""
        key = service if service.endswith("_api_key") or service == "hf_token" else f"{service}_api_key"
        val = self.get(key, secret=True)
        if val:
            return str(val)
        val = self.get(service, secret=True)
        if val:
            return str(val)
        env_map = {
            "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "qwen": "DASHSCOPE_API_KEY",
            "hf": "HF_TOKEN",
        }
        env_var = env_map.get(service.lower())
        if env_var and os.environ.get(env_var):
            return os.environ[env_var]
        return None

    def set_api_key(self, service: str, key_val: str | None) -> None:
        """Store an API key for a service securely in keyring."""
        key = service if service.endswith("_api_key") or service == "hf_token" else f"{service}_api_key"
        self.set(key, key_val, secret=True)

    @classmethod
    def instance(cls) -> ConfigStore:
        """Get or initialize singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (useful for tests)."""
        with cls._lock:
            cls._instance = None

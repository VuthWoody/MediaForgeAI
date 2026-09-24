"""Unit tests for core.project_manager."""

import json
from pathlib import Path

import pytest

from core.config_store import ConfigStore
from core.exceptions import ValidationError
from core.project_manager import ProjectManager


def test_create_and_save_project(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    config = ConfigStore(settings_path=settings_file)
    manager = ProjectManager(config_store=config)

    proj = manager.create_project("Test Episode 1", tmp_path)
    assert proj.name == "Test Episode 1"
    assert proj.file_path.exists()

    # Check directory structure
    proj_dir = Path(proj.project_dir)
    for sub in ("audio", "stems", "subtitles", "exports", "cache"):
        assert (proj_dir / sub).is_dir()

    # Verify atomic update
    proj.transcript.append({"id": 1, "text": "Hello world", "start": 0.0, "end": 2.0})
    saved_path = manager.save_project(proj)
    assert saved_path == proj.file_path

    # Reload from disk
    loaded = manager.load_project(proj_dir)
    assert loaded.id == proj.id
    assert len(loaded.transcript) == 1
    assert loaded.transcript[0]["text"] == "Hello world"


def test_backup_rotation(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    config = ConfigStore(settings_path=settings_file)
    manager = ProjectManager(config_store=config)

    proj = manager.create_project("Rotation Test", tmp_path)
    proj_file = proj.file_path

    # Perform multiple saves to trigger backup rotation
    for i in range(5):
        proj.duration = float(i * 10)
        manager.save_project(proj)

    # Check that backups exist up to MAX_BACKUPS (3) and no more
    assert proj_file.with_name(f"{proj_file.name}.bak.1").exists()
    assert proj_file.with_name(f"{proj_file.name}.bak.2").exists()
    assert proj_file.with_name(f"{proj_file.name}.bak.3").exists()
    assert not proj_file.with_name(f"{proj_file.name}.bak.4").exists()


def test_corrupt_file_recovery(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    config = ConfigStore(settings_path=settings_file)
    manager = ProjectManager(config_store=config)

    # 1. Create and save a valid project with custom language twice so backup has it
    proj = manager.create_project("Corruption Test", tmp_path)
    proj.target_language = "km"
    manager.save_project(proj)
    manager.save_project(proj)

    # Backup 1 now contains valid data with target_language = "km"
    # 2. Corrupt the main index.mfproj file with garbage bytes
    with open(proj.file_path, "w", encoding="utf-8") as f:
        f.write("{broken json payload truncated...")

    # 3. Loading should automatically detect corruption and recover from backup
    recovered = manager.load_project(proj.project_dir)
    assert recovered.name == "Corruption Test"
    assert recovered.target_language == "km"

    # Main index.mfproj should now be repaired
    with open(proj.file_path, encoding="utf-8") as f:
        data = json.load(f)
    assert data["target_language"] == "km"


def test_restore_last_project_mid_session_relaunch(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    config = ConfigStore(settings_path=settings_file)
    manager1 = ProjectManager(config_store=config)

    # Session 1: Create project
    proj = manager1.create_project("Session Restored Project", tmp_path)
    proj_dir = proj.project_dir

    # Session 2: Fresh instance (simulating app restart)
    manager2 = ProjectManager(config_store=config)
    restored = manager2.restore_last_project()

    assert restored is not None
    assert restored.id == proj.id
    assert restored.project_dir == proj_dir


def test_save_without_active_project(tmp_path: Path) -> None:
    settings_file = tmp_path / "settings.json"
    config = ConfigStore(settings_path=settings_file)
    manager = ProjectManager(config_store=config)

    with pytest.raises(ValidationError):
        manager.save_project()

"""Project file management (.mfproj), atomic writes, backup rotation, and crash recovery."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.config_store import ConfigStore
from core.exceptions import ValidationError

CURRENT_SCHEMA_VERSION = 1
MAX_BACKUPS = 3


@dataclass
class Project:
    """Represents a MediaForge AI project."""

    id: str
    name: str
    project_dir: str
    schema_version: int = CURRENT_SCHEMA_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    media_path: str | None = None
    duration: float = 0.0
    source_language: str = "auto"
    target_language: str = "en"
    transcript: list[dict[str, Any]] = field(default_factory=list)
    subtitles: list[dict[str, Any]] = field(default_factory=list)
    voices: dict[str, Any] = field(default_factory=dict)
    timeline: dict[str, Any] = field(default_factory=dict)
    export_history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def file_path(self) -> Path:
        """Path to the index.mfproj file."""
        return Path(self.project_dir) / "index.mfproj"

    def to_dict(self) -> dict[str, Any]:
        """Convert project to serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any], project_dir: str) -> Project:
        """Construct Project from dictionary."""
        data_copy = dict(data)
        data_copy["project_dir"] = project_dir
        return cls(**data_copy)


class ProjectManager:
    """Manages project lifecycle, atomic writes, backup rotation, and recovery."""

    def __init__(self, config_store: ConfigStore | None = None) -> None:
        self.config_store = config_store or ConfigStore.instance()
        self.current_project: Project | None = None

    def create_project(self, name: str, parent_dir: str | Path) -> Project:
        """Create a new project directory layout and initialize index.mfproj."""
        clean_name = name.strip() or "Untitled Project"
        proj_dir = Path(parent_dir) / clean_name
        proj_dir.mkdir(parents=True, exist_ok=True)

        # Standard subdirectories as specified in Section 7 Phase 1
        for sub in ("audio", "stems", "subtitles", "exports", "cache"):
            (proj_dir / sub).mkdir(parents=True, exist_ok=True)

        project = Project(
            id=f"proj-{uuid.uuid4().hex[:8]}",
            name=clean_name,
            project_dir=str(proj_dir),
            schema_version=CURRENT_SCHEMA_VERSION,
        )

        self.save_project(project)
        self.current_project = project
        self.config_store.set("last_project_dir", str(proj_dir))
        return project

    def save_project(self, project: Project | None = None) -> Path:
        """Save project atomically using tmpfile -> fsync -> os.replace with backup rotation."""
        target = project or self.current_project
        if target is None:
            raise ValidationError("No active project to save.")

        target.updated_at = datetime.now(UTC).isoformat()
        index_file = target.file_path
        proj_dir = Path(target.project_dir)
        proj_dir.mkdir(parents=True, exist_ok=True)

        # 1. Rotate backups before overwriting existing project file
        if index_file.exists():
            self._rotate_backups(index_file)

        # 2. Atomic write to temporary file on same filesystem
        data = target.to_dict()
        with tempfile.NamedTemporaryFile("w", dir=proj_dir, delete=False, encoding="utf-8") as tmp:
            json.dump(data, tmp, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmp_path = Path(tmp.name)

        # 3. Atomic replace
        os.replace(tmp_path, index_file)
        self.config_store.set("last_project_dir", str(proj_dir))
        return index_file

    def _rotate_backups(self, file_path: Path) -> None:
        """Rotate up to MAX_BACKUPS (.bak.1, .bak.2, .bak.3)."""
        # Delete oldest backup if it exists
        oldest = file_path.with_name(f"{file_path.name}.bak.{MAX_BACKUPS}")
        if oldest.exists():
            oldest.unlink()

        # Shift existing backups down (e.g. 2 -> 3, 1 -> 2)
        for i in range(MAX_BACKUPS - 1, 0, -1):
            src = file_path.with_name(f"{file_path.name}.bak.{i}")
            dest = file_path.with_name(f"{file_path.name}.bak.{i + 1}")
            if src.exists():
                src.rename(dest)

        # Copy current file to .bak.1
        first_bak = file_path.with_name(f"{file_path.name}.bak.1")
        shutil.copy2(file_path, first_bak)

    def load_project(self, path: str | Path) -> Project:
        """Load project from index.mfproj or directory, with corrupt-file recovery."""
        target_path = Path(path)
        if target_path.is_dir():
            index_file = target_path / "index.mfproj"
            proj_dir = target_path
        else:
            index_file = target_path
            proj_dir = target_path.parent

        if not index_file.exists():
            # Check if any backup exists in the directory
            recovered = self._attempt_backup_recovery(index_file)
            if not recovered:
                raise FileNotFoundError(f"Project file not found: {index_file}")

        data: dict[str, Any] | None = None
        try:
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            # Corrupted main file -> attempt backup recovery
            recovered = self._attempt_backup_recovery(index_file)
            if not recovered:
                raise ValidationError(f"Project file {index_file} is corrupt and no valid backups were found.") from None
            with open(index_file, encoding="utf-8") as f:
                data = json.load(f)

        if not isinstance(data, dict):
            raise ValidationError(f"Invalid project schema in {index_file}")

        # Run schema migrations if schema_version < CURRENT_SCHEMA_VERSION
        data = self._apply_migrations(data)

        project = Project.from_dict(data, project_dir=str(proj_dir))
        self.current_project = project
        self.config_store.set("last_project_dir", str(proj_dir))
        return project

    def _attempt_backup_recovery(self, file_path: Path) -> bool:
        """Search available .bak files in order of recency and restore the newest valid one."""
        for i in range(1, MAX_BACKUPS + 1):
            bak = file_path.with_name(f"{file_path.name}.bak.{i}")
            if bak.exists():
                try:
                    with open(bak, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and "id" in data:
                        shutil.copy2(bak, file_path)
                        return True
                except Exception:
                    continue
        return False

    def _apply_migrations(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply necessary schema migrations."""
        version = int(data.get("schema_version", 1))
        # Migration hooks can be added sequentially here as schema grows
        data["schema_version"] = max(version, CURRENT_SCHEMA_VERSION)
        return data

    def restore_last_project(self) -> Project | None:
        """Restore the most recently opened project across application launches."""
        last_dir = self.config_store.get("last_project_dir")
        if last_dir and Path(last_dir).exists():
            try:
                return self.load_project(last_dir)
            except Exception:
                return None
        return None

    def auto_save(self) -> Path | None:
        """Periodic auto-save handler (runs every 30 s)."""
        if self.current_project is not None:
            return self.save_project(self.current_project)
        return None

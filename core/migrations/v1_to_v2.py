"""Schema migration stub from version 1 to version 2."""

from __future__ import annotations

from typing import Any


def migrate(data: dict[str, Any]) -> dict[str, Any]:
    """Migrate project data dictionary from schema v1 to v2."""
    migrated = dict(data)
    migrated["schema_version"] = 2
    # Stub for future fields/transformations
    return migrated

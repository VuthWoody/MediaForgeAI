"""Unit test for schema migrations."""

from core.migrations.v1_to_v2 import migrate


def test_v1_to_v2_migration() -> None:
    v1_data = {
        "id": "proj-1234",
        "name": "Old Project",
        "schema_version": 1,
        "media_path": "video.mp4",
    }
    migrated = migrate(v1_data)
    assert migrated["schema_version"] == 2
    assert migrated["name"] == "Old Project"

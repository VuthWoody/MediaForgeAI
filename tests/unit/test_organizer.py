"""Unit tests for modules.downloader.organizer."""

from pathlib import Path

from modules.downloader.organizer import MediaItem, MediaOrganizer, sanitize_filename


def test_sanitize_filename() -> None:
    assert sanitize_filename("A/B\\C:D?E*F\"G<H>I|J") == "ABCDEFGHIJ"
    assert sanitize_filename("   Clean Title   ") == "Clean Title"
    assert sanitize_filename("") == "Untitled"


def test_organizer_paths_and_catalog(tmp_path: Path) -> None:
    lib_dir = tmp_path / "downloads"
    db_file = tmp_path / "test_library.db"
    organizer = MediaOrganizer(base_dir=lib_dir, db_path=db_file)

    dest_dir = organizer.get_destination_dir("YouTube", "BBC Earth", "2026-09-23")
    assert dest_dir == lib_dir / "YouTube" / "BBC Earth" / "2026-09-23"
    assert dest_dir.is_dir()

    target_file = organizer.get_target_filepath("YouTube", "BBC Earth", "Episode 1: Ocean", ext="mp4", date_str="2026-09-23")
    assert target_file == dest_dir / "Episode 1 Ocean.mp4"

    # Register items
    item1 = MediaItem(
        id="item-1",
        title="Episode 1 Ocean",
        platform="YouTube",
        creator="BBC Earth",
        date="2026-09-23",
        file_path=str(target_file),
        duration=120.0,
        resolution="1080p",
        file_size_bytes=1024 * 1024 * 50,
    )
    item2 = MediaItem(
        id="item-2",
        title="Dance Clip",
        platform="Douyin",
        creator="User123",
        date="2026-09-22",
        file_path=str(tmp_path / "clip.mp4"),
        duration=15.0,
        resolution="720p",
        file_size_bytes=1024 * 1024 * 10,
    )

    organizer.register_item(item1)
    organizer.register_item(item2)

    # Test auto-sorting and listing
    items = organizer.list_items()
    assert len(items) == 2
    # Douyin before YouTube alphabetically by platform
    assert items[0].platform == "Douyin"
    assert items[1].platform == "YouTube"

    # Test platform filter
    yt_items = organizer.list_items(platform="YouTube")
    assert len(yt_items) == 1
    assert yt_items[0].creator == "BBC Earth"

    # Test search filter
    search_res = organizer.list_items(search_query="Ocean")
    assert len(search_res) == 1
    assert search_res[0].id == "item-1"

    organizer.close()

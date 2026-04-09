from pathlib import Path


_PRODUCTION_ROOTS = ("app", "ui", "services", "system", "plugins")
_FORBIDDEN_PATTERNS = (
    "._db.get_track(",
    "._db.get_track_by_path(",
    "._db.get_track_by_cloud_file_id(",
    "._db.add_track(",
    "._db.add_tracks_bulk(",
    "._db.update_track(",
    "._db.update_track_cover_path(",
    "._db.update_track_path(",
    "._db.add_track_to_playlist(",
    "._db.get_cloud_account(",
    "._db.update_cloud_account_playing_state(",
    "._db.get_cloud_file_by_file_id(",
    ".db.get_track(",
    ".db.get_track_by_path(",
    ".db.get_track_by_cloud_file_id(",
    ".db.add_track(",
    ".db.add_tracks_bulk(",
    ".db.update_track(",
    ".db.update_track_cover_path(",
    ".db.update_track_path(",
    ".db.add_track_to_playlist(",
    ".db.get_cloud_account(",
    ".db.update_cloud_account_playing_state(",
    ".db.get_cloud_file_by_file_id(",
)


def test_production_code_does_not_call_database_manager_crud_directly():
    """Business code should go through services/repositories, not DatabaseManager CRUD helpers."""
    violations: list[str] = []

    for root in _PRODUCTION_ROOTS:
        for path in Path(root).rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            for pattern in _FORBIDDEN_PATTERNS:
                if pattern in source:
                    violations.append(f"{path}: {pattern}")

    assert violations == []

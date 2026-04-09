from pathlib import Path
import inspect

from infrastructure.database.sqlite_manager import DatabaseManager
from services.library.file_organization_service import FileOrganizationService


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


def test_database_manager_no_longer_exposes_track_or_playlist_crud_api():
    """Business CRUD should live in repositories/services, not DatabaseManager."""
    forbidden_api = (
        "add_track",
        "add_track_async",
        "get_track",
        "get_tracks_by_ids",
        "get_track_by_path",
        "get_track_by_cloud_file_id",
        "get_tracks_by_cloud_file_ids",
        "get_track_index_for_paths",
        "add_tracks_bulk",
        "get_all_tracks",
        "search_tracks",
        "delete_track",
        "delete_track_async",
        "update_track",
        "update_track_async",
        "update_track_cover_path",
        "update_track_path",
        "create_playlist",
        "get_playlist",
        "get_all_playlists",
        "get_playlist_tracks",
        "add_track_to_playlist",
        "remove_track_from_playlist",
        "delete_playlist",
        "add_favorite",
        "remove_favorite",
        "get_all_favorite_track_ids",
        "get_favorites",
        "get_cloud_account",
        "update_cloud_account_playing_state",
        "update_cloud_file_local_path",
        "get_cloud_file_by_file_id",
    )

    for name in forbidden_api:
        assert not hasattr(DatabaseManager, name), name


def test_file_organization_service_no_longer_accepts_db_manager():
    """Library-adjacent services should not keep deprecated db_manager constructor args."""
    assert "db_manager" not in inspect.signature(FileOrganizationService.__init__).parameters

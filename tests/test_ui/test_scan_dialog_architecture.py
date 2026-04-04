"""Architecture tests for scan dialog data-access boundaries."""

import inspect
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from domain.track import Track
from ui.windows.components.scan_dialog import ScanController, ScanDialog, ScanWorker, ScanStats


def test_scan_components_do_not_require_db_manager():
    """Scan dialog stack should depend on LibraryService, not DatabaseManager."""
    worker_params = inspect.signature(ScanWorker.__init__).parameters
    controller_params = inspect.signature(ScanController.__init__).parameters
    api_params = inspect.signature(ScanDialog.scan_folder).parameters

    assert "db_manager" not in worker_params
    assert "db_manager" not in controller_params
    assert "db_manager" not in api_params


def test_scan_worker_loads_existing_index_via_library_service():
    """Incremental scan index should come from LibraryService abstraction."""
    library_service = SimpleNamespace(
        get_track_index_for_paths=MagicMock(return_value={"/tmp/a.mp3": {"size": 10, "mtime": 2.0}}),
        get_track_by_path=MagicMock(return_value=None),
        add_tracks_bulk=MagicMock(return_value=(0, 0)),
        add_track=MagicMock(),
    )
    worker = ScanWorker(
        folder_path="/tmp",
        library_service=library_service,
        cover_service=None,
    )

    result = worker._load_existing_index(["/tmp/a.mp3"])

    library_service.get_track_index_for_paths.assert_called_once_with(["/tmp/a.mp3"])
    assert result == {"/tmp/a.mp3": {"size": 10, "mtime": 2.0}}


def test_scan_worker_flush_batch_uses_library_service_bulk_insert():
    """Batch insert should go through LibraryService bulk API."""
    library_service = SimpleNamespace(
        get_track_index_for_paths=MagicMock(return_value={}),
        get_track_by_path=MagicMock(return_value=None),
        add_tracks_bulk=MagicMock(return_value=(2, 1)),
        add_track=MagicMock(),
    )
    worker = ScanWorker(
        folder_path="/tmp",
        library_service=library_service,
        cover_service=None,
    )
    stats = ScanStats()
    tracks = [
        Track(path="/tmp/a.mp3", title="A", created_at=datetime.now()),
        Track(path="/tmp/b.mp3", title="B", created_at=datetime.now()),
        Track(path="/tmp/c.mp3", title="C", created_at=datetime.now()),
    ]

    worker._flush_batch(tracks, stats)

    library_service.add_tracks_bulk.assert_called_once()
    assert stats.added == 2
    assert stats.skipped == 1

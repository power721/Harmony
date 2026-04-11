"""OnlineTrackHandler worker cleanup behavior tests."""

import inspect
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import services.playback.handlers as handlers_module
from domain.track import TrackSource
from services.playback.handlers import CloudTrackHandler, LocalTrackHandler, OnlineTrackHandler


def test_stop_download_worker_uses_cooperative_shutdown(monkeypatch):
    """Download worker stop should avoid force terminate."""
    fake_worker = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        deleteLater=MagicMock(),
        terminate=MagicMock(),
    )
    handler = SimpleNamespace()
    monkeypatch.setattr(handlers_module, "isValid", lambda _obj: True)

    OnlineTrackHandler._stop_download_worker(handler, fake_worker, "song-mid", wait_ms=250)

    fake_worker.requestInterruption.assert_called_once()
    fake_worker.quit.assert_called_once()
    fake_worker.wait.assert_called_once_with(250)
    fake_worker.deleteLater.assert_called_once()
    fake_worker.terminate.assert_not_called()


def test_handlers_do_not_require_database_manager_dependency():
    """Playback handlers should depend on repositories, not DatabaseManager."""
    local_params = inspect.signature(LocalTrackHandler.__init__).parameters
    cloud_params = inspect.signature(CloudTrackHandler.__init__).parameters
    online_params = inspect.signature(OnlineTrackHandler.__init__).parameters

    assert "db_manager" not in local_params
    assert "db_manager" not in cloud_params
    assert "db_manager" not in online_params


def test_process_metadata_async_tracks_background_threads(monkeypatch):
    """Cloud metadata worker thread should be tracked and released after completion."""

    class FakeThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon
            self.started = False

        def start(self):
            self.started = True

    monkeypatch.setattr(handlers_module.threading, "Thread", FakeThread)

    fake_handler = SimpleNamespace(
        _save_to_library=MagicMock(),
        _metadata_threads=set(),
        _metadata_threads_lock=threading.Lock(),
    )

    CloudTrackHandler._process_metadata_async(
        fake_handler, [("file-id", "/tmp/a.mp3", "quark")]
    )

    assert len(fake_handler._metadata_threads) == 1
    thread = next(iter(fake_handler._metadata_threads))
    thread.target()
    fake_handler._save_to_library.assert_called_once_with("file-id", "/tmp/a.mp3", "quark")
    assert len(fake_handler._metadata_threads) == 0


def test_cloud_handler_cleanup_joins_and_clears_metadata_threads():
    """CloudTrackHandler cleanup should wait briefly for metadata threads and clear tracking."""

    class FakeThread:
        def __init__(self):
            self.join_calls = []
            self._alive = True

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            self.join_calls.append(timeout)
            self._alive = False

    thread = FakeThread()
    fake_handler = SimpleNamespace(
        _metadata_threads={thread},
        _metadata_threads_lock=threading.Lock(),
    )

    CloudTrackHandler.cleanup(fake_handler, join_timeout=1.5)

    assert thread.join_calls == [1.5]
    assert len(fake_handler._metadata_threads) == 0


def test_cloud_handler_save_to_library_uses_provider_aware_lookup_for_online_source(monkeypatch):
    """Online-source fallback inside cloud save path should keep provider context."""
    from services.metadata import metadata_service

    monkeypatch.setattr(
        metadata_service.MetadataService,
        "extract_metadata",
        staticmethod(lambda _path: {"title": "Song", "artist": "Artist", "album": "", "duration": 1}),
    )

    fake_track_repo = SimpleNamespace(
        get_by_cloud_file_id=MagicMock(
            return_value=SimpleNamespace(
                id=1,
                path="/tmp/song.mp3",
                title="Song",
                artist="Artist",
                cover_path="",
            )
        ),
        update_path=MagicMock(),
    )
    fake_handler = SimpleNamespace(
        _cloud_account=None,
        _engine=SimpleNamespace(
            current_playlist_item=SimpleNamespace(
                cloud_file_id="song-1",
                source=TrackSource.ONLINE,
                is_online=True,
                online_provider_id="qqmusic",
            )
        ),
        _track_repo=fake_track_repo,
        _update_track_fields=MagicMock(),
        _cover_service=None,
    )

    CloudTrackHandler._save_to_library(
        fake_handler,
        "song-1",
        "/tmp/song.mp3",
        source=TrackSource.ONLINE,
    )

    fake_track_repo.get_by_cloud_file_id.assert_called_once_with(
        "song-1",
        provider_id="qqmusic",
    )

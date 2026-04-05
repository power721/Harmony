"""OnlineTrackHandler worker cleanup behavior tests."""

import inspect
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import services.playback.handlers as handlers_module
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

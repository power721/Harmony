"""DownloadManager cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import app.bootstrap as bootstrap_module
import services.download.download_manager as download_manager_module
from services.download.download_manager import DownloadManager


class _FakeSignal:
    def __init__(self):
        self.connect_calls = []
        self.disconnect_calls = []

    def connect(self, callback):
        self.connect_calls.append(callback)

    def disconnect(self, callback=None):
        self.disconnect_calls.append(callback)


class _FakeWorker:
    def __init__(self, *_args, **_kwargs):
        self.download_finished = _FakeSignal()
        self.finished = _FakeSignal()
        self._running = False
        self.started = False
        self.deleted = False

    def isRunning(self):
        return self._running

    def start(self):
        self.started = True

    def deleteLater(self):
        self.deleted = True


def test_stop_worker_uses_cooperative_shutdown(monkeypatch):
    """Stopping worker should not force-terminate QThread."""
    fake_worker = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    manager = SimpleNamespace()
    monkeypatch.setattr(download_manager_module, "isValid", lambda _obj: True)

    DownloadManager._stop_worker(manager, fake_worker, "song-mid", wait_ms=250)

    fake_worker.requestInterruption.assert_called_once()
    fake_worker.quit.assert_called_once()
    fake_worker.wait.assert_called_once_with(250)
    fake_worker.terminate.assert_not_called()


def test_redownload_replaces_stale_worker_and_disconnects_old_signals(monkeypatch):
    """Replacing stale worker should disconnect old signals before deleteLater."""
    manager = DownloadManager()
    monkeypatch.setattr(download_manager_module, "isValid", lambda _obj: True)
    monkeypatch.setattr(DownloadManager, "_OnlineDownloadWorker", _FakeWorker)
    monkeypatch.setattr(
        bootstrap_module.Bootstrap,
        "instance",
        classmethod(lambda cls: SimpleNamespace(online_download_service=object())),
    )

    assert manager.redownload_online_track("song-mid", "Song A")
    first_worker = manager._download_workers["song-mid"]

    # Simulate stale worker that is no longer running.
    first_worker._running = False

    assert manager.redownload_online_track("song-mid", "Song A")
    second_worker = manager._download_workers["song-mid"]

    assert second_worker is not first_worker
    assert first_worker.deleted is True
    assert first_worker.download_finished.disconnect_calls
    assert first_worker.finished.disconnect_calls
    assert len(second_worker.download_finished.connect_calls) == 1
    assert len(second_worker.finished.connect_calls) == 1


def test_on_online_download_finished_skips_disconnect_for_invalid_worker(monkeypatch):
    """Invalid worker objects should not be disconnected to avoid runtime crash."""
    manager = DownloadManager()
    invalid_worker = SimpleNamespace(
        download_finished=SimpleNamespace(disconnect=MagicMock())
    )
    manager._download_workers["song-mid"] = invalid_worker
    monkeypatch.setattr(download_manager_module, "isValid", lambda _obj: False)

    failed = []
    manager.download_failed.connect(lambda song_mid: failed.append(song_mid))

    manager._on_online_download_finished("song-mid", "")

    invalid_worker.download_finished.disconnect.assert_not_called()
    assert failed == ["song-mid"]


def test_download_manager_uses_lock_for_worker_registry():
    """Worker registry should be protected by a lock to avoid data races."""
    manager = DownloadManager()
    assert hasattr(manager, "_download_lock")

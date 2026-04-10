"""
Tests for CloudDownloadService cache path handling.
"""

import threading
import time
from pathlib import Path
from types import SimpleNamespace

from PySide6.QtCore import QThread
from unittest.mock import Mock

from domain.cloud import CloudAccount, CloudFile
from services.cloud.download_service import CloudDownloadService, CloudDownloadWorker


class _BlockingWorker(QThread):
    def __init__(self):
        super().__init__()
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True
        self.requestInterruption()

    def run(self):
        while not self.isInterruptionRequested():
            self.msleep(10)


def test_get_cached_path_does_not_reuse_same_name_cache_for_different_file_ids(tmp_path):
    """Different cloud file IDs with the same display name must not share a cache hit."""
    service = CloudDownloadService()
    service.set_download_dir(str(tmp_path))

    first_file = CloudFile(file_id="fid-1", name="song.mp3", size=4)
    second_file = CloudFile(file_id="fid-2", name="song.mp3", size=4)

    legacy_shared_path = tmp_path / "song.mp3"
    legacy_shared_path.write_bytes(b"demo")

    assert service.get_cached_path(first_file.file_id, first_file) is None
    assert service.get_cached_path(second_file.file_id, second_file) is None


def test_get_cached_path_returns_none_when_download_dir_missing(tmp_path):
    """Missing download directories should be treated as a cache miss."""
    service = CloudDownloadService()
    service.set_download_dir(str(tmp_path / "missing"))

    cloud_file = CloudFile(file_id="fid-1", name="song.mp3", size=4)

    assert service.get_cached_path(cloud_file.file_id, cloud_file) is None


def test_cleanup_stops_active_download_workers():
    """Cleanup must stop outstanding worker threads before the service is destroyed."""
    service = CloudDownloadService()
    worker = _BlockingWorker()
    service._active_downloads["file-1"] = worker
    worker.start()
    time.sleep(0.05)

    service.cleanup()

    assert worker.cancel_called is True
    assert worker.isRunning() is False
    assert service._active_downloads == {}


def test_cloud_download_service_instance_is_thread_safe(monkeypatch):
    CloudDownloadService._instance = None
    init_calls = []
    original_init = CloudDownloadService.__init__

    def fake_init(self, parent=None):
        init_calls.append("init")
        time.sleep(0.05)
        self._active_downloads = {}
        self._downloads_lock = threading.Lock()
        self._cached_paths = {}
        self._download_dir = "data/cloud_downloads"

    monkeypatch.setattr(CloudDownloadService, "__init__", fake_init)

    try:
        results = []

        def get_instance():
            results.append(CloudDownloadService.instance())

        first = threading.Thread(target=get_instance)
        second = threading.Thread(target=get_instance)
        first.start()
        second.start()
        first.join()
        second.join()

        assert len(init_calls) == 1
        assert len(results) == 2
        assert results[0] is results[1]
    finally:
        monkeypatch.setattr(CloudDownloadService, "__init__", original_init)
        CloudDownloadService._instance = None


def test_cancel_download_uses_cooperative_stop_for_unresponsive_worker():
    """Cancelling a stuck worker should not force-terminate the thread."""
    service = CloudDownloadService()
    worker = Mock()
    worker.cancel = Mock()
    worker.isRunning.return_value = True
    worker.wait.return_value = False
    worker.requestInterruption = Mock()
    worker.quit = Mock()
    worker.terminate = Mock()
    service._active_downloads["file-1"] = worker

    service.cancel_download("file-1")

    worker.cancel.assert_called_once()
    worker.requestInterruption.assert_called_once()
    worker.quit.assert_called_once()
    worker.wait.assert_called_once_with(1000)
    worker.terminate.assert_not_called()
    assert service._active_downloads == {}


def test_cloud_download_worker_retries_transient_download_url_failure(monkeypatch, tmp_path):
    """Transient URL lookup failures should be retried before surfacing an error."""
    import services.cloud.download_service as cloud_download_module
    import services.cloud.quark_service as quark_service_module

    cloud_file = CloudFile(file_id="file-1", name="song.mp3", size=2)
    account = CloudAccount(provider="quark", access_token="cookie")
    worker = CloudDownloadWorker(cloud_file, account, str(tmp_path))

    attempts = {"count": 0}
    completed = []
    errors = []
    sleep_calls = []

    def fake_get_download_url(access_token, file_id):
        assert access_token == "cookie"
        assert file_id == "file-1"
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise RuntimeError("temporary network error")
        return "https://example.com/song.mp3"

    def fake_download_file(url, dest_path, access_token):
        assert url == "https://example.com/song.mp3"
        assert access_token == "cookie"
        Path(dest_path).write_bytes(b"ok")
        return True

    monkeypatch.setattr(quark_service_module.QuarkDriveService, "get_download_url", fake_get_download_url)
    monkeypatch.setattr(quark_service_module.QuarkDriveService, "download_file", fake_download_file)
    monkeypatch.setattr(
        cloud_download_module,
        "time",
        SimpleNamespace(sleep=lambda delay: sleep_calls.append(delay)),
        raising=False,
    )

    worker.download_completed.connect(lambda file_id, local_path: completed.append((file_id, local_path)))
    worker.download_error.connect(lambda file_id, message: errors.append((file_id, message)))

    worker.run()

    assert attempts["count"] == 2
    assert len(sleep_calls) == 1
    assert completed == [("file-1", str(tmp_path / "song__file-1.mp3"))]
    assert errors == []


def test_cloud_download_worker_retries_service_download_failures(monkeypatch, tmp_path):
    """Service-level download failures should be retried before giving up."""
    import services.cloud.download_service as cloud_download_module
    cloud_file = CloudFile(file_id="file-2", name="song.mp3", size=None)
    account = CloudAccount(provider="quark", access_token="cookie")
    worker = CloudDownloadWorker(cloud_file, account, str(tmp_path))

    attempts = {"count": 0}
    sleep_calls = []

    class _RetryingService:
        @staticmethod
        def download_file(url, dest_path, access_token):
            assert url == "https://example.com/song.mp3"
            assert access_token == "cookie"
            attempts["count"] += 1
            if attempts["count"] == 1:
                return False
            Path(dest_path).write_bytes(b"ok")
            return True

    monkeypatch.setattr(
        cloud_download_module,
        "time",
        SimpleNamespace(sleep=lambda delay: sleep_calls.append(delay)),
        raising=False,
    )

    ok = worker._download_file("https://example.com/song.mp3", str(tmp_path / "song.mp3"), _RetryingService)

    assert ok is True
    assert attempts["count"] == 2
    assert len(sleep_calls) == 1

"""
Tests for CloudDownloadService cache path handling.
"""

import time

from PySide6.QtCore import QThread

from domain.cloud import CloudFile
from services.cloud.download_service import CloudDownloadService


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


class _StubbornWorker(QThread):
    def __init__(self):
        super().__init__()
        self.cancel_called = False

    def cancel(self):
        self.cancel_called = True

    def run(self):
        while True:
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


def test_cancel_download_terminates_unresponsive_worker():
    """Cancelling a stuck worker must not leave a running QThread behind."""
    service = CloudDownloadService()
    worker = _StubbornWorker()
    service._active_downloads["file-1"] = worker
    worker.start()
    time.sleep(0.05)

    service.cancel_download("file-1")

    assert worker.cancel_called is True
    assert worker.isRunning() is False

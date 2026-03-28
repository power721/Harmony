"""
Test for QThread lifecycle management in download workers.

This test reproduces the crash: "QThread: Destroyed while thread is still running"
"""
import pytest
import time
from PySide6.QtCore import QThread, Signal, QEventLoop
from PySide6.QtWidgets import QApplication


def test_qthread_deletion_while_running(qtbot):
    """Test that reproduces the QThread deletion crash."""

    class DownloadWorker(QThread):
        download_finished = Signal(str, str)

        def __init__(self, song_mid):
            super().__init__()
            self._song_mid = song_mid

        def run(self):
            # Simulate download work
            time.sleep(0.1)
            self.download_finished.emit(self._song_mid, "/path/to/file.mp3")

    worker = DownloadWorker("test_song_mid")
    workers = {"test_song_mid": worker}

    def on_finished(mid, path):
        # This is what the current code does - it's WRONG
        worker_obj = workers.pop(mid)
        worker_obj.deleteLater()  # ⚠️ Thread is still running here!

    worker.download_finished.connect(on_finished)
    worker.start()

    # Wait a bit for the crash to occur
    with qtbot.wait_signal(worker.download_finished, timeout=1000):
        pass

    # Process events to trigger deletion
    QApplication.processEvents()

    # This will cause: "QThread: Destroyed while thread is still running"


def test_qthread_proper_cleanup(qtbot):
    """Test the correct way to clean up QThread."""

    class DownloadWorker(QThread):
        download_finished = Signal(str, str)

        def __init__(self, song_mid):
            super().__init__()
            self._song_mid = song_mid

        def run(self):
            # Simulate download work
            time.sleep(0.1)
            self.download_finished.emit(self._song_mid, "/path/to/file.mp3")

    worker = DownloadWorker("test_song_mid")
    workers = {"test_song_mid": worker}
    finished_called = []

    def on_download_finished(mid, path):
        # Don't delete here - just record the result
        finished_called.append((mid, path))

    def on_thread_finished():
        # Delete ONLY after thread has fully stopped
        worker_obj = workers.pop("test_song_mid")
        worker_obj.deleteLater()

    worker.download_finished.connect(on_download_finished)
    worker.finished.connect(on_thread_finished)  # ✓ Correct cleanup
    worker.start()

    # Wait for thread to complete
    with qtbot.wait_signal(worker.finished, timeout=1000):
        pass

    # Process events to allow deletion
    QApplication.processEvents()

    # Thread was properly cleaned up
    assert len(finished_called) == 1
    assert "test_song_mid" not in workers

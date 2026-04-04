"""DownloadManager cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import services.download.download_manager as download_manager_module
from services.download.download_manager import DownloadManager


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

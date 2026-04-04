"""OnlineTrackHandler worker cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import services.playback.handlers as handlers_module
from services.playback.handlers import OnlineTrackHandler


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

"""ArtistsView thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.views.artists_view as artists_view_module
from ui.views.artists_view import ArtistsView


def test_stop_load_worker_uses_cooperative_shutdown(monkeypatch):
    """Stopping load worker should avoid force terminate."""
    fake_worker = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        deleteLater=MagicMock(),
        terminate=MagicMock(),
    )
    view = SimpleNamespace(_load_worker=fake_worker)
    monkeypatch.setattr(artists_view_module, "isValid", lambda _obj: True)

    ArtistsView._stop_load_worker(view, wait_ms=250, clear_ref=True)

    fake_worker.requestInterruption.assert_called_once()
    fake_worker.quit.assert_called_once()
    fake_worker.wait.assert_called_once_with(250)
    fake_worker.deleteLater.assert_called_once()
    fake_worker.terminate.assert_not_called()
    assert view._load_worker is None

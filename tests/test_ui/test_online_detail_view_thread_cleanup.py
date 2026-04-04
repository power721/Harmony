"""OnlineDetailView thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.views.online_detail_view as detail_module
from ui.views.online_detail_view import OnlineDetailView


def test_stop_full_cover_loader_uses_cooperative_shutdown(monkeypatch):
    """Stopping full cover loader should avoid force terminate."""
    fake_loader = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    view = SimpleNamespace(_full_cover_loader=fake_loader)
    monkeypatch.setattr(detail_module, "isValid", lambda _obj: True)

    OnlineDetailView._stop_full_cover_loader(view)

    fake_loader.requestInterruption.assert_called_once()
    fake_loader.quit.assert_called_once()
    fake_loader.wait.assert_called_once_with(1000)
    fake_loader.terminate.assert_not_called()

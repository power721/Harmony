"""Recommend card cover loader thread cleanup tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.widgets.recommend_card as recommend_card_module
from ui.widgets.recommend_card import CoverLoader


def test_cover_loader_stop_thread_uses_cooperative_shutdown(monkeypatch):
    """Stopping cover loader should avoid force terminate."""
    fake_loader = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    monkeypatch.setattr(recommend_card_module, "isValid", lambda _obj: True)

    CoverLoader._stop_thread(fake_loader, wait_ms=250)

    fake_loader.requestInterruption.assert_called_once()
    fake_loader.quit.assert_called_once()
    fake_loader.wait.assert_called_once_with(250)
    fake_loader.terminate.assert_not_called()

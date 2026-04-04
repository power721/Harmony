"""BaseCoverDownloadDialog thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.dialogs.base_cover_download_dialog as dialog_module
from ui.dialogs.base_cover_download_dialog import BaseCoverDownloadDialog


def test_stop_thread_uses_cooperative_shutdown(monkeypatch):
    """Stopping dialog worker should avoid force terminate."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    dialog = SimpleNamespace()
    monkeypatch.setattr(dialog_module, "isValid", lambda _obj: True)

    BaseCoverDownloadDialog._stop_thread(dialog, fake_thread, wait_ms=250)

    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(250)
    fake_thread.terminate.assert_not_called()

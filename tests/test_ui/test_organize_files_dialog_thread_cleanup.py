"""OrganizeFilesDialog thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.dialogs.organize_files_dialog as organize_dialog_module
from ui.dialogs.organize_files_dialog import OrganizeFilesDialog


def test_stop_organize_thread_uses_cooperative_shutdown(monkeypatch):
    """Stopping organize thread should avoid force terminate."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    dialog = SimpleNamespace(organize_thread=fake_thread)
    monkeypatch.setattr(organize_dialog_module, "isValid", lambda _obj: True)

    OrganizeFilesDialog._stop_organize_thread(dialog, wait_ms=250)

    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(250)
    fake_thread.terminate.assert_not_called()

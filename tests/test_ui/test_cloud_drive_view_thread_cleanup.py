"""CloudDriveView thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.views.cloud.cloud_drive_view import CloudDriveView


def test_stop_current_download_thread_uses_cooperative_shutdown():
    """Stopping current download thread should avoid force terminate."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    view = SimpleNamespace(_current_download_thread=fake_thread)

    CloudDriveView._stop_current_download_thread(view, wait_ms=250)

    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(250)
    fake_thread.terminate.assert_not_called()
    assert view._current_download_thread is None

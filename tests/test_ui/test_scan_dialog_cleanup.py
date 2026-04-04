"""ScanController cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from ui.windows.components.scan_dialog import ScanController


def test_on_finished_ignores_disconnect_runtime_error():
    """Finishing scan should continue cleanup when disconnect raises RuntimeError."""
    fake_dialog = SimpleNamespace(
        rejected=SimpleNamespace(disconnect=MagicMock(side_effect=RuntimeError("already disconnected"))),
        set_progress=MagicMock(),
        close=MagicMock(),
    )
    controller = SimpleNamespace(
        dialog=fake_dialog,
        _on_cancel=MagicMock(),
        _cleanup_thread=MagicMock(),
        on_complete=MagicMock(),
        completed=SimpleNamespace(emit=MagicMock()),
        deleteLater=MagicMock(),
    )

    ScanController._on_finished(controller, {"ok": True})

    fake_dialog.set_progress.assert_called_once_with(100)
    fake_dialog.close.assert_called_once()
    controller._cleanup_thread.assert_called_once()
    controller.on_complete.assert_called_once_with({"ok": True})
    controller.completed.emit.assert_called_once_with({"ok": True})
    controller.deleteLater.assert_called_once()

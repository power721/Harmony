from types import SimpleNamespace
from unittest.mock import Mock

from app.application import Application


def test_quit_calls_hotkeys_cleanup(monkeypatch):
    app = Application.__new__(Application)
    cache_cleaner = SimpleNamespace(stop=Mock())
    app._bootstrap = SimpleNamespace(
        stop_mpris=Mock(),
        cache_cleaner_service=cache_cleaner,
        shutdown_database=Mock(),
    )
    app._qt_app = SimpleNamespace(quit=Mock())
    cleanup = Mock()

    monkeypatch.setattr("system.hotkeys.cleanup", cleanup)

    Application.quit(app)

    cleanup.assert_called_once_with()
    app._bootstrap.shutdown_database.assert_called_once_with()

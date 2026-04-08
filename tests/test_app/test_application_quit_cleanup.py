from types import SimpleNamespace
from unittest.mock import Mock

from app.application import Application


def test_quit_calls_hotkeys_cleanup(monkeypatch):
    app = Application.__new__(Application)
    cache_cleaner = SimpleNamespace(stop=Mock())
    write_worker = SimpleNamespace(wait_idle=Mock(), stop=Mock())
    app._bootstrap = SimpleNamespace(
        stop_mpris=Mock(),
        cache_cleaner_service=cache_cleaner,
        db=SimpleNamespace(_write_worker=write_worker),
    )
    app._qt_app = SimpleNamespace(quit=Mock())
    cleanup = Mock()

    monkeypatch.setattr("system.hotkeys.cleanup", cleanup)

    Application.quit(app)

    cleanup.assert_called_once_with()

from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from app.application import Application


def test_dispatch_to_ui_invokes_callback_with_bound_instance(monkeypatch):
    qt_app = QApplication.instance() or QApplication([])
    bootstrap = SimpleNamespace()

    monkeypatch.setattr("app.application.Bootstrap.instance", lambda db_path="Harmony.db": bootstrap)

    app = Application(qt_app)
    received: list[str] = []

    monkeypatch.setattr(
        "app.application.QTimer.singleShot",
        lambda _delay, callback: callback(),
    )

    app._dispatch_to_ui(received.append, "ok")

    assert received == ["ok"]


def test_application_no_longer_exposes_database_manager_property(monkeypatch):
    qt_app = QApplication.instance() or QApplication([])
    bootstrap = SimpleNamespace()

    monkeypatch.setattr("app.application.Bootstrap.instance", lambda db_path="Harmony.db": bootstrap)

    app = Application(qt_app)

    assert not hasattr(type(app), "db")


def test_run_logs_startup_failures_and_still_enters_event_loop(monkeypatch, caplog):
    qt_app = QApplication.instance() or QApplication([])
    cache_cleaner = SimpleNamespace(start=lambda: (_ for _ in ()).throw(RuntimeError("cache cleaner failed")))
    bootstrap = SimpleNamespace(
        cache_cleaner_service=cache_cleaner,
        start_mpris=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mpris failed")),
    )

    monkeypatch.setattr("app.application.Bootstrap.instance", lambda db_path="Harmony.db": bootstrap)
    monkeypatch.setattr(
        "infrastructure.cache.ImageCache.cleanup",
        lambda days=7: (_ for _ in ()).throw(RuntimeError("cleanup failed")),
    )

    app = Application(qt_app)
    app._main_window = object()
    monkeypatch.setattr(app._qt_app, "exec", lambda: 123)

    result = app.run()

    assert result == 123
    assert "Image cache cleanup failed" in caplog.text
    assert "Cache cleaner start failed" in caplog.text
    assert "MPRIS startup failed" in caplog.text

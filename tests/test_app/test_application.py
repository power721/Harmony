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

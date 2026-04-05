"""AlbumsView thread cleanup behavior tests."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

import ui.views.albums_view as albums_view_module
from system.event_bus import EventBus
from system.theme import ThemeManager
from ui.views.albums_view import AlbumsView

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_theme_config():
    config = Mock()
    config.get.return_value = "dark"
    return config


def test_stop_load_worker_uses_cooperative_shutdown(monkeypatch):
    """Stopping load worker should avoid force terminate."""
    fake_worker = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        deleteLater=MagicMock(),
        terminate=MagicMock(),
    )
    view = SimpleNamespace(_load_worker=fake_worker)
    monkeypatch.setattr(albums_view_module, "isValid", lambda _obj: True)

    AlbumsView._stop_load_worker(view, wait_ms=250, clear_ref=True)

    fake_worker.requestInterruption.assert_called_once()
    fake_worker.quit.assert_called_once()
    fake_worker.wait.assert_called_once_with(250)
    fake_worker.deleteLater.assert_called_once()
    fake_worker.terminate.assert_not_called()
    assert view._load_worker is None


class _FakeSignal:
    def __init__(self):
        self.connected = []

    def connect(self, slot):
        self.connected.append(slot)

    def disconnect(self, slot):
        self.connected.remove(slot)


def test_close_event_disconnects_event_bus(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)

    fake_bus = SimpleNamespace(
        tracks_added=_FakeSignal(),
        cover_updated=_FakeSignal(),
    )
    monkeypatch.setattr(EventBus, "instance", classmethod(lambda cls: fake_bus))

    view = AlbumsView(library_service=Mock())

    assert view._on_tracks_added in fake_bus.tracks_added.connected
    assert view._on_cover_updated in fake_bus.cover_updated.connected

    view.closeEvent(QCloseEvent())

    assert view._on_tracks_added not in fake_bus.tracks_added.connected
    assert view._on_cover_updated not in fake_bus.cover_updated.connected

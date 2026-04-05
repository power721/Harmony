"""PlayerControls shutdown cleanup tests."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager
from ui.widgets.player_controls import PlayerControls

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


class _FakeSignal:
    def connect(self, _slot):
        return None

    def disconnect(self, _slot=None):
        return None


def test_close_event_calls_cleanup(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)

    monkeypatch.setattr(PlayerControls, "_setup_sleep_timer_connections", lambda self: None)
    monkeypatch.setattr(PlayerControls, "_refresh_equalizer_availability", lambda self: None)
    monkeypatch.setattr(PlayerControls, "_initialize_favorite_button", lambda self: None)
    monkeypatch.setattr(PlayerControls, "refresh_theme", lambda self: None)
    monkeypatch.setattr(PlayerControls, "_sync_button_states", lambda self: None)

    engine = SimpleNamespace(
        play_previous=lambda: None,
        play_next=lambda: None,
        play=lambda: None,
        pause=lambda: None,
        seek=lambda _position: None,
        set_volume=lambda _volume: None,
        set_play_mode=lambda _mode: None,
        state_changed=_FakeSignal(),
        position_changed=_FakeSignal(),
        duration_changed=_FakeSignal(),
        current_track_changed=_FakeSignal(),
        current_track_pending=_FakeSignal(),
        play_mode_changed=_FakeSignal(),
        volume_changed=_FakeSignal(),
        current_track=None,
        play_mode=None,
        state=None,
        duration=lambda: 0,
        backend=SimpleNamespace(),
    )
    player = SimpleNamespace(engine=engine)

    controls = PlayerControls(player=player)
    cleanup_calls = []
    controls.cleanup = lambda: cleanup_calls.append("cleanup")

    controls.closeEvent(QCloseEvent())

    assert cleanup_calls == ["cleanup"]

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton

from domain.track import Track
from services import LyricsService
from services.metadata import CoverService
from system.theme import ThemeManager
from ui.controllers.cover_controller import CoverController
from ui.dialogs.base_cover_download_dialog import BaseCoverDownloadDialog
from ui.dialogs.cloud_login_dialog import CloudLoginDialog
from ui.dialogs.lyrics_edit_dialog import LyricsEditDialog
from ui.dialogs.redownload_dialog import RedownloadDialog
from ui.dialogs.sleep_timer_dialog import SleepTimerDialog
from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
from ui.strategies.track_search_strategy import TrackSearchStrategy


class _FakeSleepTimerService(QObject):
    timer_started = Signal()
    timer_stopped = Signal()
    timer_triggered = Signal()

    def __init__(self):
        super().__init__()
        self.is_active = False

    def start(self, _config):
        self.is_active = True
        self.timer_started.emit()

    def cancel(self):
        self.is_active = False
        self.timer_stopped.emit()


@pytest.fixture(autouse=True)
def _init_theme():
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    ThemeManager.instance(config)
    yield
    ThemeManager._instance = None


def _buttons_by_role(dialog):
    buttons = dialog.findChildren(QPushButton)
    return {
        "primary": [button for button in buttons if button.property("role") == "primary"],
        "cancel": [button for button in buttons if button.property("role") == "cancel"],
    }


def test_lyrics_edit_dialog_uses_foundation_action_button_roles(qtbot, monkeypatch):
    monkeypatch.setattr(LyricsService, "get_lyrics", lambda *_args, **_kwargs: "")

    dialog = LyricsEditDialog("/tmp/song.mp3", "Song", "Artist")
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert "QPushButton {" not in LyricsEditDialog._STYLE_TEMPLATE
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1


def test_redownload_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = RedownloadDialog("Song", current_quality="320")
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert "QPushButton {" not in RedownloadDialog._STYLE_TEMPLATE
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1


def test_cloud_login_dialog_uses_foundation_cancel_button_role(qtbot, monkeypatch):
    monkeypatch.setattr(CloudLoginDialog, "_start_login_flow", lambda self: None)

    dialog = CloudLoginDialog("quark")
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert "QPushButton {" not in CloudLoginDialog._STYLE_TEMPLATE
    assert len(roles["cancel"]) == 1


def test_sleep_timer_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = SleepTimerDialog(_FakeSleepTimerService())
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 2


def test_cover_download_dialog_uses_foundation_action_button_roles(qtbot):
    track = Track(
        id=1,
        path="/tmp/song.mp3",
        title="Song",
        artist="Artist",
        album="Album",
    )
    strategy = TrackSearchStrategy([track], Mock(), Mock())
    cover_service = Mock(spec=CoverService)

    with patch.object(CoverController, "search", return_value=None):
        dialog = UniversalCoverDownloadDialog(strategy, cover_service)

    qtbot.addWidget(dialog)
    roles = _buttons_by_role(dialog)

    assert "QPushButton {" not in BaseCoverDownloadDialog._STYLE_TEMPLATE
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1

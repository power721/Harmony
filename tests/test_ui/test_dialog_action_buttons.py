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
from ui.dialogs.help_dialog import HelpDialog
from ui.dialogs.input_dialog import InputDialog
from ui.dialogs.lyrics_edit_dialog import LyricsEditDialog
from ui.dialogs.message_dialog import MessageDialog, Ok, Cancel
from ui.dialogs.add_to_playlist_dialog import AddToPlaylistDialog
from ui.dialogs.organize_files_dialog import OrganizeFilesDialog
from ui.dialogs.progress_dialog import ProgressDialog
from ui.dialogs.provider_select_dialog import ProviderSelectDialog
from ui.dialogs.redownload_dialog import RedownloadDialog
from ui.dialogs.sleep_timer_dialog import SleepTimerDialog
from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
from ui.dialogs.welcome_dialog import WelcomeDialog
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
    assert len(roles["cancel"]) == 0


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


def test_organize_files_dialog_uses_foundation_action_button_roles(qtbot):
    track = Track(
        id=1,
        path="/tmp/song.mp3",
        title="Song",
        artist="Artist",
        album="Album",
    )
    file_org_service = Mock()
    config_manager = Mock()
    config_manager.get.return_value = ""

    dialog = OrganizeFilesDialog(
        tracks=[track],
        file_org_service=file_org_service,
        config_manager=config_manager,
    )
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert dialog.styleSheet() == ""
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1


def test_organize_files_dialog_uses_global_panel_table_variant(qtbot):
    track = Track(
        id=1,
        path="/tmp/song.mp3",
        title="Song",
        artist="Artist",
        album="Album",
    )
    file_org_service = Mock()
    config_manager = Mock()
    config_manager.get.return_value = ""

    dialog = OrganizeFilesDialog(
        tracks=[track],
        file_org_service=file_org_service,
        config_manager=config_manager,
    )
    qtbot.addWidget(dialog)

    assert dialog.preview_table.property("variant") == "panel"
    assert dialog.preview_table.styleSheet() == ""


def test_provider_select_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = ProviderSelectDialog()
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert dialog.styleSheet() == ""
    assert len(roles["primary"]) == 2
    assert len(roles["cancel"]) == 1


def test_help_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = HelpDialog()
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert len(roles["primary"]) == 1


def test_progress_dialog_uses_foundation_cancel_button_role(qtbot):
    dialog = ProgressDialog("Title", "Loading", "Cancel", 0, 100)
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert dialog.styleSheet() == ""
    assert len(roles["cancel"]) == 1


def test_welcome_dialog_keeps_custom_onboarding_actions(qtbot):
    dialog = WelcomeDialog(library_service=Mock())
    qtbot.addWidget(dialog)

    buttons = {button.objectName() for button in dialog.findChildren(QPushButton)}

    assert "QPushButton#addFolderBtn" in WelcomeDialog._STYLE_TEMPLATE
    assert "QPushButton#skipBtn" in WelcomeDialog._STYLE_TEMPLATE
    assert "addFolderBtn" in buttons
    assert "skipBtn" in buttons


def test_input_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = InputDialog("Title", "Prompt", "value")
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert dialog.styleSheet() == ""
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1


def test_add_to_playlist_dialog_uses_foundation_action_button_roles(qtbot):
    library_service = Mock()
    library_service.get_all_playlists.return_value = []

    dialog = AddToPlaylistDialog(library_service)
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert "QPushButton#cancelBtn" not in AddToPlaylistDialog._STYLE_TEMPLATE
    assert "QPushButton#okBtn" not in AddToPlaylistDialog._STYLE_TEMPLATE
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1


def test_message_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = MessageDialog(None, "information")
    dialog._add_button("OK", Ok, is_primary=True)
    dialog._add_button("Cancel", Cancel, is_primary=False)
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert "QPushButton#msgPrimaryBtn" not in MessageDialog._STYLE_TEMPLATE
    assert "QPushButton#msgBtn" not in MessageDialog._STYLE_TEMPLATE
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1

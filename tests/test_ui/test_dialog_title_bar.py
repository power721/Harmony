from unittest.mock import Mock

from PySide6.QtWidgets import QDialog, QMainWindow, QVBoxLayout

from domain.track import TrackSource
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from ui.widgets.context_menus import LocalTrackContextMenu


def _init_theme():
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    return ThemeManager.instance(config)


def test_dialog_title_bar_uses_global_theme_selectors(qtbot):
    _init_theme()
    dialog = QDialog()
    qtbot.addWidget(dialog)
    container = QVBoxLayout(dialog)

    _, controller = setup_equalizer_title_layout(dialog, container, "Title")

    assert controller.title_bar.objectName() == "dialogTitleBar"
    assert controller.title_label.objectName() == "dialogTitle"
    assert controller.close_btn.objectName() == "dialogCloseBtn"
    assert controller.title_bar.styleSheet() == ""
    assert controller.title_label.styleSheet() == ""
    assert controller.close_btn.styleSheet() == ""


def test_title_bar_relies_on_object_names_instead_of_local_qss(qtbot):
    _init_theme()
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    assert bar.objectName() == "titleBar"
    assert bar._btn_min.objectName() == "winBtn"
    assert bar._btn_close.objectName() == "closeBtn"
    assert bar.styleSheet() == ""


def test_local_track_context_menu_uses_global_qmenu_styling(qtbot):
    _init_theme()
    menu_builder = LocalTrackContextMenu()
    track = Mock()
    track.id = 1
    track.path = "/tmp/song.mp3"
    track.source = TrackSource.LOCAL

    menu = menu_builder.build_menu([track], set(), None)
    qtbot.addWidget(menu)

    assert menu is not None
    assert menu.styleSheet() == ""


def test_local_track_context_menu_exposes_organize_files_action(qtbot):
    _init_theme()
    menu_builder = LocalTrackContextMenu()
    track = Mock()
    track.id = 1
    track.path = "/tmp/song.mp3"
    track.source = TrackSource.LOCAL
    emitted = []

    menu_builder.organize_files.connect(lambda tracks: emitted.append(tracks))

    menu = menu_builder.build_menu([track], set(), None)
    qtbot.addWidget(menu)

    organize_action = next(
        action for action in menu.actions() if action.text() == t("organize_files")
    )
    organize_action.trigger()

    assert emitted == [[track]]

from unittest.mock import Mock

from system.theme import ThemeManager
from ui.dialogs.edit_media_info_dialog import EditMediaInfoDialog
from ui.dialogs.input_dialog import InputDialog
from ui.dialogs.organize_files_dialog import OrganizeFilesDialog
from ui.dialogs.progress_dialog import ProgressDialog
from ui.dialogs.provider_select_dialog import ProviderSelectDialog
from ui.views.albums_view import AlbumsView


def _init_theme():
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager._instance = None
    return ThemeManager.instance(config)


def test_input_dialog_marks_shell_and_uses_unstyled_foundation_children(qtbot):
    _init_theme()

    dialog = InputDialog("Title", "Prompt", "value")
    qtbot.addWidget(dialog)

    assert dialog.property("shell") is True
    assert dialog._input.styleSheet() == ""


def test_albums_view_search_input_uses_theme_variant_instead_of_local_qss(qtbot):
    _init_theme()

    view = AlbumsView(library_service=Mock())
    qtbot.addWidget(view)

    assert view._search_input.property("variant") == "search"
    assert view._search_input.styleSheet() == ""


def test_dialog_shells_use_global_foundation_container_styles(qtbot):
    _init_theme()

    library_service = Mock()
    first_track = Mock()
    first_track.title = "Song"
    first_track.artist = "Artist"
    first_track.album = "Album"
    first_track.genre = "Genre"
    first_track.path = "/tmp/song.mp3"
    library_service.get_track.return_value = first_track

    dialogs = [
        EditMediaInfoDialog([1], library_service),
        OrganizeFilesDialog(
            [first_track],
            Mock(),
            Mock(get=Mock(return_value="")),
        ),
        ProviderSelectDialog(),
        ProgressDialog("Title", "Label", "Cancel", 0, 100),
    ]

    for dialog in dialogs:
        qtbot.addWidget(dialog)
        assert dialog.property("shell") is True
        assert dialog.styleSheet() == ""

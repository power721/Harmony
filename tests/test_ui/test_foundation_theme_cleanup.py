from unittest.mock import Mock

from system.theme import ThemeManager
from ui.dialogs.input_dialog import InputDialog
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

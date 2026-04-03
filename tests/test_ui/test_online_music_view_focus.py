"""Focus behavior tests for OnlineMusicView search input."""

from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from ui.views.online_music_view import OnlineMusicView


def test_click_outside_search_input_clears_focus(qtbot):
    """Clicking outside search input should clear its focus."""
    theme_manager = MagicMock()
    theme_manager.get_qss.side_effect = lambda qss: qss
    theme_manager.register_widget = MagicMock()
    theme_manager.current_theme = MagicMock(highlight="#1db954")

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        view = OnlineMusicView(config_manager=None, db_manager=None, qqmusic_service=None)
        view._top_lists_loaded = True  # Avoid loading top list workers in this test.
        qtbot.addWidget(view)
        view.show()

        view._search_input.setFocus()
        qtbot.waitUntil(lambda: view._search_input.hasFocus())

        qtbot.mouseClick(view._stack, Qt.LeftButton)

        qtbot.waitUntil(lambda: not view._search_input.hasFocus())

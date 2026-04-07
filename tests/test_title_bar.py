"""Tests for TitleBar widget."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock, PropertyMock

import pytest
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor


@pytest.fixture
def theme_mock():
    """Create a mock ThemeManager with preset theme defaults."""
    mock = MagicMock()
    theme = MagicMock()
    theme.background = "#121212"
    theme.background_alt = "#282828"
    theme.background_hover = "#2a2a2a"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.highlight_hover = "#1ed760"
    theme.selection = "rgba(40,40,40,0.8)"
    theme.border = "#3a3a3a"
    type(mock).current_theme = PropertyMock(return_value=theme)
    mock.get_qss = lambda tpl: tpl  # passthrough (no token replacement)
    mock.register_widget = MagicMock()
    return mock


@pytest.fixture
def patch_theme(theme_mock):
    """Patch ThemeManager.instance() to return theme_mock."""
    with patch("ui.widgets.title_bar.ThemeManager.instance", return_value=theme_mock):
        yield theme_mock


def test_title_bar_creation(qtbot, patch_theme):
    """TitleBar should create with all child widgets."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    assert bar.height() == 44
    assert bar._title_label is not None
    assert bar._btn_min is not None
    assert bar._btn_max is not None
    assert bar._btn_close is not None
    assert bar._btn_close.objectName() == "closeBtn"


def test_toggle_maximize(qtbot, patch_theme):
    """Double-clicking should toggle maximize."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    window.resize(400, 300)
    qtbot.addWidget(window)
    bar = TitleBar(window)

    assert not window.isMaximized()

    mock_event = MagicMock()
    mock_event.button.return_value = Qt.MouseButton.LeftButton
    bar.mouseDoubleClickEvent(mock_event)
    assert window.isMaximized()

    mock_event2 = MagicMock()
    mock_event2.button.return_value = Qt.MouseButton.LeftButton
    bar.mouseDoubleClickEvent(mock_event2)
    assert not window.isMaximized()


def test_close_button(qtbot, patch_theme):
    """Close button should trigger window.close()."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    with patch.object(window, 'close') as mock_close:
        bar._btn_close.click()
        mock_close.assert_called_once()


def test_minimize_button(qtbot, patch_theme):
    """Minimize button should trigger showMinimized."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    with patch.object(window, 'showMinimized') as mock_min:
        bar._btn_min.click()
        mock_min.assert_called_once()


def test_set_track_title(qtbot, patch_theme):
    """set_track_title should update the title label."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    bar.set_track_title("Bohemian Rhapsody", "Queen")
    assert "Bohemian Rhapsody" in bar._title_label.text()
    assert "Queen" in bar._title_label.text()


def test_clear_track_title(qtbot, patch_theme):
    """clear_track_title should restore default title."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    bar.set_track_title("Song", "Artist")
    bar.clear_track_title()
    assert bar._title_label.text() == "Harmony"


def test_set_accent_color(qtbot, patch_theme):
    """set_accent_color should update the background."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    bar.set_accent_color(QColor(100, 200, 50))
    assert bar._accent_color is not None
    assert bar._accent_color.red() == 100


def test_clear_accent_color(qtbot, patch_theme):
    """clear_accent_color should reset to theme bg."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    bar.set_accent_color(QColor(100, 200, 50))
    bar.clear_accent_color()
    assert bar._accent_color is None


def test_set_track_title_artist_only(qtbot, patch_theme):
    """set_track_title with empty artist should show title only."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    bar.set_track_title("Song Title", "")
    assert bar._title_label.text() == "Song Title"


def test_refresh_theme(qtbot, patch_theme):
    """refresh_theme should re-apply stylesheet and trigger update."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    qtbot.addWidget(window)
    bar = TitleBar(window)

    # Should not raise
    bar.refresh_theme()
    assert bar.styleSheet() == ""


def test_drag_to_move(qtbot, patch_theme):
    """Dragging should move the parent window."""
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    window.resize(400, 300)
    qtbot.addWidget(window)
    bar = TitleBar(window)

    initial_pos = window.pos()

    # Simulate press
    press_event = MagicMock()
    press_event.button.return_value = Qt.MouseButton.LeftButton
    press_event.globalPosition.return_value = QPointF(initial_pos.x() + 20, initial_pos.y() + 10)
    bar.mousePressEvent(press_event)

    # Simulate move
    move_event = MagicMock()
    move_event.buttons.return_value = Qt.MouseButton.LeftButton
    move_event.globalPosition.return_value = QPointF(initial_pos.x() + 30, initial_pos.y() + 20)
    bar.mouseMoveEvent(move_event)

    # Window should have moved by delta
    new_pos = window.pos()
    assert new_pos.x() == initial_pos.x() + 10
    assert new_pos.y() == initial_pos.y() + 10

    # Release
    bar.mouseReleaseEvent(MagicMock())
    assert bar._drag_pos is None

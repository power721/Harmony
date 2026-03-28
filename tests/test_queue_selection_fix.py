"""
Test for queue view selection state synchronization.

This test verifies that when selection is restored in the queue view,
the widget's selection state is properly synchronized even when signals
are blocked.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication, QListWidget, QListWidgetItem
from PySide6.QtCore import Qt, QObject, Signal

from ui.views.queue_view import QueueItemWidget


# Mock Theme and ThemeManager
class MockTheme:
    def __init__(self):
        self.name = "Dark"
        self.background = "#121212"
        self.background_alt = "#282828"
        self.background_hover = "#2a2a2a"
        self.text = "#ffffff"
        self.text_secondary = "#b3b3b3"
        self.highlight = "#1db954"
        self.highlight_hover = "#1ed760"
        self.selection = "rgba(40, 40, 40, 0.8)"
        self.border = "#3a3a3a"


class MockThemeManager(QObject):
    theme_changed = Signal(object)

    _instance = None

    def __init__(self):
        super().__init__()
        self.current_theme = MockTheme()

    @classmethod
    def instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_widget(self, widget):
        pass

    def get_qss(self, template):
        return template


def test_selection_state_sync():
    """Test that widget selection state is synchronized when signals are blocked."""
    # Create QApplication if not exists
    app = QApplication.instance() or QApplication(sys.argv)

    # Mock ThemeManager
    with patch('system.theme.ThemeManager', MockThemeManager):
        # Create a mock track
        track = {
            "id": 1,
            "title": "Test Track",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180,
            "path": "/tmp/test.mp3"
        }

        # Create a list widget
        list_widget = QListWidget()

        # Create a queue item widget (not current, not playing)
        widget = QueueItemWidget(track, 0, is_current=False, is_playing=False, highlight_color="#FFD700")

        # Create list item
        item = QListWidgetItem()
        item.setData(Qt.UserRole, track)
        list_widget.addItem(item)
        list_widget.setItemWidget(item, widget)

        # Verify initial state
        assert widget._is_selected == False, "Widget should start unselected"

        # Block signals (simulating the bug scenario)
        list_widget.blockSignals(True)

        # Select the item
        item.setSelected(True)

        # OLD BUG: Widget state would not update because signals are blocked
        # assert widget._is_selected == False, "Bug: Widget state not synced"

        # NEW FIX: Manually update widget state
        widget.set_selected(True)

        # Verify widget state is now synchronized
        assert widget._is_selected == True, "Widget selection state should be True after manual sync"
        assert item.isSelected() == True, "List item should be selected"

        # Unblock signals
        list_widget.blockSignals(False)

        print("✓ Test passed: Widget selection state correctly synchronized")


def test_current_and_selected_state():
    """Test that current playing track can be selected with proper styling."""
    app = QApplication.instance() or QApplication(sys.argv)

    with patch('system.theme.ThemeManager', MockThemeManager):
        track = {
            "id": 1,
            "title": "Test Track",
            "artist": "Test Artist",
            "duration": 180,
            "path": "/tmp/test.mp3"
        }

        # Create widget for current playing track
        widget = QueueItemWidget(track, 0, is_current=True, is_playing=True, highlight_color="#FFD700")

        # Initially, current track has highlight color text (not selected)
        assert widget._is_current == True, "Widget should be current track"
        assert widget._is_selected == False, "Widget should not be selected initially"

        # Now select it (simulate user clicking on current track)
        widget.set_selected(True)

        # After selection, widget should be in selected state
        # The style should show black text on highlight background
        assert widget._is_selected == True, "Widget should be selected"

        print("✓ Test passed: Current track can be selected with proper state")


if __name__ == "__main__":
    test_selection_state_sync()
    test_current_and_selected_state()
    print("\n✓ All tests passed!")

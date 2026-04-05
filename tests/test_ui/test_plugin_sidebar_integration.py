from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QStackedWidget

from system.theme import ThemeManager
from ui.windows.components.sidebar import Sidebar
from ui.windows.main_window import MainWindow


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
def mock_config():
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    return config


def test_sidebar_can_add_plugin_entry(qapp, mock_config):
    ThemeManager.instance(mock_config)
    sidebar = Sidebar(config_manager=mock_config)

    sidebar.add_plugin_entry(page_index=200, title="QQ Music", icon_name="GLOBE")

    assert any(index == 200 for index, _button in sidebar._nav_buttons)


def test_main_window_mounts_plugin_pages(qapp, mock_config):
    ThemeManager.instance(mock_config)
    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window._stacked_widget = QStackedWidget()
    window._sidebar = Sidebar(config_manager=mock_config)

    bootstrap = Mock()
    bootstrap.plugin_manager.registry.sidebar_entries.return_value = [
        type(
            "Spec",
            (),
            {
                "plugin_id": "qqmusic",
                "entry_id": "qqmusic.sidebar",
                "title": "QQ Music",
                "order": 80,
                "icon_name": "GLOBE",
                "page_factory": staticmethod(
                    lambda _context, _parent: QLabel("QQ Music View")
                ),
            },
        )()
    ]

    with patch("ui.windows.main_window.Bootstrap.instance", return_value=bootstrap):
        window._mount_plugin_pages()

    assert "qqmusic" in window._plugin_page_keys.values()
    assert window._stacked_widget.count() == 1

"""Tests for OnlineDetailView action button visibility based on page count."""

import os
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager
from ui.views.online_detail_view import OnlineDetailView


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _init_theme_manager():
    ThemeManager._instance = None
    config = MagicMock()
    config.get.return_value = "dark"
    ThemeManager.instance(config)


def test_all_actions_hidden_when_only_one_page():
    """All-pages action buttons should be hidden when there is only one page."""
    _app()
    _init_theme_manager()
    view = OnlineDetailView()

    view._total_pages = 1
    view._update_pagination()

    assert view._play_all_btn.isHidden()
    assert view._insert_all_queue_btn.isHidden()
    assert view._add_all_queue_btn.isHidden()


def test_all_actions_visible_when_multiple_pages():
    """All-pages action buttons should be visible when there are multiple pages."""
    _app()
    _init_theme_manager()
    view = OnlineDetailView()

    view._total_pages = 1
    view._update_pagination()
    view._total_pages = 2
    view._update_pagination()

    assert not view._play_all_btn.isHidden()
    assert not view._insert_all_queue_btn.isHidden()
    assert not view._add_all_queue_btn.isHidden()

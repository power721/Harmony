from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication, QWidget

from ui.dialogs.settings_dialog import GeneralSettingsDialog
from system.theme import ThemeManager


class _FakePluginManagementTab(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__()


def test_settings_dialog_exposes_views_tab_controls():
    app = QApplication.instance() or QApplication([])
    del app

    theme_config = Mock()
    theme_config.get.return_value = "dark"
    ThemeManager._instance = None
    ThemeManager.instance(theme_config)

    config = Mock()
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_audio_engine.return_value = "mpv"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_albums_visible.return_value = True
    config.get_genres_visible.return_value = False
    config.get_cloud_drive_visible.return_value = True
    config.get_most_played_visible.return_value = False
    config.get_recently_added_visible.return_value = False
    config.get.side_effect = lambda key, default=None: default

    bootstrap = SimpleNamespace(
        plugin_manager=SimpleNamespace(
            registry=SimpleNamespace(settings_tabs=lambda: []),
        ),
    )

    with patch("ui.dialogs.settings_dialog.Bootstrap.instance", return_value=bootstrap), \
            patch("ui.dialogs.settings_dialog.PluginManagementTab", _FakePluginManagementTab):
        dialog = GeneralSettingsDialog(config)

    assert hasattr(dialog, "_show_albums_checkbox")
    assert hasattr(dialog, "_show_genres_checkbox")
    assert hasattr(dialog, "_show_cloud_checkbox")
    assert hasattr(dialog, "_show_most_played_checkbox")
    assert hasattr(dialog, "_show_recently_added_checkbox")
    assert dialog._show_albums_checkbox.isChecked() is True
    assert dialog._show_genres_checkbox.isChecked() is False
    assert dialog._show_cloud_checkbox.isChecked() is True
    assert dialog._show_most_played_checkbox.isChecked() is False
    assert dialog._show_recently_added_checkbox.isChecked() is False

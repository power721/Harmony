from unittest.mock import Mock

from PySide6.QtWidgets import QTabWidget

from system.theme import ThemeManager
from ui.dialogs.plugin_management_tab import PluginManagementTab
from ui.dialogs.settings_dialog import GeneralSettingsDialog


def test_plugin_management_tab_shows_plugin_rows(qtbot):
    manager = Mock()
    manager.list_plugins.return_value = [
        {
            "id": "lrclib",
            "name": "LRCLIB",
            "version": "1.0.0",
            "source": "builtin",
            "enabled": True,
            "load_error": None,
        },
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "source": "external",
            "enabled": False,
            "load_error": "load failed",
        },
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    assert widget._table.rowCount() == 2


def test_settings_dialog_includes_plugins_tab(monkeypatch, qtbot):
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"

    fake_manager = Mock()
    fake_manager.list_plugins.return_value = []
    fake_manager.registry.settings_tabs.return_value = []
    bootstrap = Mock(plugin_manager=fake_manager)
    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "Plugins" in tab_labels or "插件" in tab_labels


def test_settings_dialog_omits_qqmusic_tab_without_plugin(monkeypatch, qtbot):
    config = Mock()
    config.get.return_value = "dark"
    config.get_ai_enabled.return_value = False
    config.get_ai_base_url.return_value = ""
    config.get_ai_api_key.return_value = ""
    config.get_ai_model.return_value = ""
    config.get_acoustid_enabled.return_value = False
    config.get_acoustid_api_key.return_value = ""
    config.get_online_music_download_dir.return_value = "data/online_cache"
    config.get_cache_cleanup_strategy.return_value = "manual"
    config.get_cache_cleanup_auto_enabled.return_value = False
    config.get_cache_cleanup_time_days.return_value = 30
    config.get_cache_cleanup_size_mb.return_value = 1000
    config.get_cache_cleanup_count.return_value = 100
    config.get_cache_cleanup_interval_hours.return_value = 1
    config.get_audio_engine.return_value = "mpv"

    fake_manager = Mock()
    fake_manager.list_plugins.return_value = []
    fake_manager.registry.settings_tabs.return_value = []
    bootstrap = Mock(plugin_manager=fake_manager)
    monkeypatch.setattr("ui.dialogs.settings_dialog.Bootstrap.instance", lambda: bootstrap)
    ThemeManager._instance = None
    ThemeManager.instance(config)

    dialog = GeneralSettingsDialog(config)
    qtbot.addWidget(dialog)
    tab_widget = dialog.findChild(QTabWidget)

    tab_labels = [tab_widget.tabText(index) for index in range(tab_widget.count())]
    assert "QQ音乐" not in tab_labels
    assert "QQ Music" not in tab_labels

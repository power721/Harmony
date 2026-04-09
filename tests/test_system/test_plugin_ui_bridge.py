from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from harmony_plugin_api.manifest import PluginManifest
from system.theme import ThemeManager
from system.plugins.host_services import BootstrapPluginContextFactory


def test_plugin_context_ui_bridge_exposes_theme_and_dialog_helpers(tmp_path: Path):
    config = Mock()
    config.get.return_value = "dark"
    config.get_language.return_value = "zh"

    ThemeManager._instance = None
    ThemeManager.instance(config)

    registry = Mock()
    bootstrap = SimpleNamespace(
        _plugin_manager=SimpleNamespace(registry=registry),
        online_download_service=Mock(),
        playback_service=Mock(),
        library_service=Mock(),
        http_client=Mock(),
        event_bus=Mock(),
        config=config,
    )
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
        }
    )

    context = BootstrapPluginContextFactory(bootstrap, tmp_path).build(manifest)

    assert callable(context.ui.register_sidebar_entry)
    assert callable(context.ui.register_settings_tab)
    assert callable(context.ui.theme.get_qss)
    assert callable(context.ui.theme.register_widget)
    assert context.ui.theme.current_theme().text
    assert callable(context.ui.theme.get_popup_surface_style)
    assert callable(context.ui.theme.get_completer_popup_style)
    assert callable(context.ui.dialogs.information)
    assert callable(context.ui.dialogs.warning)
    assert callable(context.ui.dialogs.question)
    assert callable(context.ui.dialogs.critical)
    assert callable(context.ui.dialogs.setup_title_bar)
    assert callable(context.runtime.get_icon)
    assert callable(context.runtime.http_get_content)
    assert callable(context.runtime.event_bus)


def test_plugin_context_ui_bridge_exposes_foundation_theme_helpers(tmp_path: Path):
    config = Mock()
    config.get.return_value = "dark"
    config.get_language.return_value = "zh"

    ThemeManager._instance = None
    ThemeManager.instance(config)

    registry = Mock()
    bootstrap = SimpleNamespace(
        _plugin_manager=SimpleNamespace(registry=registry),
        online_download_service=Mock(),
        playback_service=Mock(),
        library_service=Mock(),
        http_client=Mock(),
        event_bus=Mock(),
        config=config,
    )
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
        }
    )

    context = BootstrapPluginContextFactory(bootstrap, tmp_path).build(manifest)

    assert callable(context.ui.theme.get_popup_surface_style)
    assert callable(context.ui.theme.get_completer_popup_style)


def test_plugin_context_ui_bridge_uses_host_bridge_modules(tmp_path: Path):
    config = Mock()
    config.get.return_value = "dark"
    config.get_language.return_value = "zh"

    ThemeManager._instance = None
    ThemeManager.instance(config)

    bootstrap = SimpleNamespace(
        _plugin_manager=SimpleNamespace(registry=Mock()),
        online_download_service=Mock(),
        playback_service=Mock(),
        library_service=Mock(),
        http_client=Mock(),
        event_bus=Mock(),
        config=config,
    )
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
        }
    )

    context = BootstrapPluginContextFactory(bootstrap, tmp_path).build(manifest)

    assert context.ui.theme.__class__.__module__ == "system.plugins.plugin_sdk_ui"
    assert context.ui.dialogs.__class__.__module__ == "system.plugins.plugin_sdk_ui"

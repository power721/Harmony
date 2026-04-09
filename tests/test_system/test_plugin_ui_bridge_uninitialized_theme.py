from unittest.mock import Mock

from system.plugins.plugin_sdk_ui import PluginThemeBridgeImpl
from system.theme import PRESET_THEMES, ThemeManager


def test_plugin_theme_bridge_tolerates_uninitialized_theme_manager():
    ThemeManager._instance = None
    bridge = PluginThemeBridgeImpl()
    widget = Mock()

    bridge.register_widget(widget)

    assert bridge.get_qss("QWidget { color: %text%; }") == "QWidget { color: %text%; }"
    assert bridge.current_theme() == PRESET_THEMES["dark"]
    assert bridge.get_popup_surface_style() == ""
    assert bridge.get_completer_popup_style() == ""

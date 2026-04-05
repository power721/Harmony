from harmony_plugin_api.registry_types import SidebarEntrySpec
from system.plugins.registry import PluginRegistry


def test_registry_unregister_plugin_removes_owned_entries():
    registry = PluginRegistry()
    spec = SidebarEntrySpec(
        plugin_id="qqmusic",
        entry_id="qqmusic.sidebar",
        title="QQ Music",
        order=80,
        icon_name="GLOBE",
        page_factory=lambda _context, _parent: object(),
    )

    registry.register_sidebar_entry("qqmusic", spec)
    registry.unregister_plugin("qqmusic")

    assert registry.sidebar_entries() == []

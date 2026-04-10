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


def test_registry_unregister_plugin_filters_lists_in_place():
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
    original_sidebar_entries = registry._sidebar_entries
    original_settings_tabs = registry._settings_tabs
    original_lyrics_sources = registry._lyrics_sources
    original_cover_sources = registry._cover_sources
    original_artist_cover_sources = registry._artist_cover_sources
    original_online_providers = registry._online_providers

    registry.unregister_plugin("qqmusic")

    assert registry._sidebar_entries is original_sidebar_entries
    assert registry._settings_tabs is original_settings_tabs
    assert registry._lyrics_sources is original_lyrics_sources
    assert registry._cover_sources is original_cover_sources
    assert registry._artist_cover_sources is original_artist_cover_sources
    assert registry._online_providers is original_online_providers

from pathlib import Path
from unittest.mock import Mock

from harmony_plugin_api.media import PluginPlaybackRequest
from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec
from system.plugins.host_services import (
    PluginServiceBridgeImpl,
    PluginSettingsBridgeImpl,
    PluginStorageBridgeImpl,
    PluginUiBridgeImpl,
)
from system.plugins.media_bridge import PluginMediaBridge
from system.plugins.registry import PluginRegistry


def test_plugin_settings_bridge_namespaces_keys():
    config = Mock()
    config.get.return_value = "flac"
    bridge = PluginSettingsBridgeImpl("qqmusic", config)

    assert bridge.get("quality") == "flac"
    config.get.assert_called_once_with("plugins.qqmusic.quality", None)

    bridge.set("quality", "320")
    config.set.assert_called_once_with("plugins.qqmusic.quality", "320")


def test_plugin_storage_bridge_creates_private_directories(tmp_path: Path):
    bridge = PluginStorageBridgeImpl(tmp_path, "qqmusic")

    assert bridge.data_dir == tmp_path / "qqmusic" / "data"
    assert bridge.cache_dir == tmp_path / "qqmusic" / "cache"
    assert bridge.temp_dir == tmp_path / "qqmusic" / "tmp"
    assert bridge.data_dir.exists()
    assert bridge.cache_dir.exists()
    assert bridge.temp_dir.exists()


def test_plugin_ui_bridge_registers_with_plugin_id():
    registry = PluginRegistry()
    bridge = PluginUiBridgeImpl("qqmusic", registry)
    sidebar_spec = SidebarEntrySpec(
        plugin_id="qqmusic",
        entry_id="qqmusic.sidebar",
        title="QQ Music",
        order=80,
        icon_name="GLOBE",
        page_factory=lambda _context, _parent: object(),
    )
    settings_spec = SettingsTabSpec(
        plugin_id="qqmusic",
        tab_id="qqmusic.settings",
        title="QQ Music",
        order=80,
        widget_factory=lambda _context, _parent: object(),
    )

    bridge.register_sidebar_entry(sidebar_spec)
    bridge.register_settings_tab(settings_spec)

    assert registry.sidebar_entries() == [sidebar_spec]
    assert registry.settings_tabs() == [settings_spec]


def test_plugin_service_bridge_registers_sources_and_exposes_media():
    registry = PluginRegistry()
    media = Mock()
    bridge = PluginServiceBridgeImpl("qqmusic", registry, media)
    lyrics_source = Mock()
    cover_source = Mock()
    artist_cover_source = Mock()
    provider = Mock()

    bridge.register_lyrics_source(lyrics_source)
    bridge.register_cover_source(cover_source)
    bridge.register_artist_cover_source(artist_cover_source)
    bridge.register_online_music_provider(provider)

    assert bridge.media is media
    assert registry.lyrics_sources() == [lyrics_source]
    assert registry.cover_sources() == [cover_source]
    assert registry.artist_cover_sources() == [artist_cover_source]
    assert registry.online_providers() == [provider]


def test_media_bridge_passes_explicit_quality_to_download_service():
    download_service = Mock()
    playback_service = Mock()
    library_service = Mock()
    bridge = PluginMediaBridge(download_service, playback_service, library_service)
    request = PluginPlaybackRequest(
        provider_id="qqmusic",
        track_id="mid-1",
        title="Song 1",
        quality="flac",
        metadata={
            "title": "Song 1",
            "artist": "Singer 1",
            "album": "Album 1",
            "duration": 180.0,
            "cover_url": "https://example.com/cover.jpg",
        },
    )

    bridge.cache_remote_track(request)
    download_service.download.assert_called_once_with(
        "mid-1",
        song_title="Song 1",
        quality="flac",
        progress_callback=None,
        force=False,
    )

    bridge.add_online_track(request)
    library_service.add_online_track.assert_called_once_with(
        "mid-1",
        "Song 1",
        "Singer 1",
        "Album 1",
        180.0,
        "https://example.com/cover.jpg",
    )

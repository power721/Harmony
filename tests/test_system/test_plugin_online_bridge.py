from pathlib import Path
from unittest.mock import Mock

from harmony_plugin_api.media import PluginPlaybackRequest
from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec
from system.plugins.host_services import (
    BootstrapPluginContextFactory,
    PluginServiceBridgeImpl,
    PluginSettingsBridgeImpl,
    PluginStorageBridgeImpl,
    PluginUiBridgeImpl,
)
from system.plugins.media_bridge import PluginMediaBridge
from system.plugins.registry import PluginRegistry
import system.plugins.plugin_sdk_runtime as plugin_sdk_runtime


def test_plugin_settings_bridge_namespaces_keys():
    config = Mock()
    config.get.return_value = "flac"
    bridge = PluginSettingsBridgeImpl("qqmusic", config)

    assert bridge.get("quality") == "flac"
    config.get.assert_called_once_with("plugins.qqmusic.quality", None)

    bridge.set("quality", "320")
    config.set.assert_called_once_with("plugins.qqmusic.quality", "320")


def test_plugin_settings_bridge_uses_secret_store_for_credentials():
    config = Mock()
    config.get_plugin_secret.return_value = '{"musicid":"1"}'
    bridge = PluginSettingsBridgeImpl("qqmusic", config)

    assert bridge.get("credential") == {"musicid": "1"}
    config.get_plugin_secret.assert_called_once_with("qqmusic", "credential", None)

    bridge.set("credential", {"musicid": "2"})
    config.set_plugin_secret.assert_called_once_with("qqmusic", "credential", '{"musicid": "2"}')


def test_plugin_settings_bridge_namespaces_language_key():
    config = Mock()
    config.get.return_value = "zh"
    bridge = PluginSettingsBridgeImpl("qqmusic", config)

    assert bridge.get("language") == "zh"
    config.get.assert_called_once_with("plugins.qqmusic.language", None)

    bridge.set("language", "en")
    config.set.assert_called_once_with("plugins.qqmusic.language", "en")


def test_bootstrap_plugin_context_factory_uses_existing_manager_without_reentry(tmp_path: Path):
    registry = PluginRegistry()

    class _Bootstrap:
        def __init__(self):
            self._plugin_manager = Mock(registry=registry)
            self.online_download_service = Mock()
            self.playback_service = Mock()
            self.library_service = Mock()
            self.http_client = Mock()
            self.event_bus = Mock()
            self.config = Mock()

        @property
        def plugin_manager(self):
            raise AssertionError("plugin_manager property should not be re-entered")

    manifest = Mock(id="qqmusic")
    factory = BootstrapPluginContextFactory(_Bootstrap(), tmp_path)

    context = factory.build(manifest)

    assert context.plugin_id == "qqmusic"


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
    playback_service.engine = Mock()
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
        provider_id="qqmusic",
        quality="flac",
        progress_callback=None,
        force=False,
    )

    bridge.add_online_track(request)
    library_service.add_online_track.assert_called_once_with(
        "qqmusic",
        "mid-1",
        "Song 1",
        "Singer 1",
        "Album 1",
        180.0,
        "https://example.com/cover.jpg",
    )


def test_media_bridge_can_play_online_track():
    download_service = Mock()
    download_service.is_cached.return_value = False
    playback_service = Mock()
    playback_service.engine = Mock()
    library_service = Mock()
    library_service.add_online_track.return_value = 42
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

    bridge.play_online_track(request)

    playback_service.engine.load_playlist_items.assert_called_once()
    playback_service.engine.play.assert_called_once_with()
    playback_service.save_queue.assert_called_once_with()
    item = playback_service.engine.load_playlist_items.call_args[0][0][0]
    assert item.source.value == "ONLINE"
    assert item.online_provider_id == "qqmusic"


def test_media_bridge_can_add_and_insert_online_track_to_queue():
    download_service = Mock()
    download_service.is_cached.return_value = False
    playback_service = Mock()
    playback_service.engine = Mock()
    playback_service.engine.current_index = 3
    library_service = Mock()
    library_service.add_online_track.return_value = 42
    bridge = PluginMediaBridge(download_service, playback_service, library_service)
    request = PluginPlaybackRequest(
        provider_id="qqmusic",
        track_id="mid-1",
        title="Song 1",
        quality="320",
        metadata={
            "title": "Song 1",
            "artist": "Singer 1",
            "album": "Album 1",
            "duration": 180.0,
        },
    )

    bridge.add_online_track_to_queue(request)
    bridge.insert_online_track_to_queue(request)

    assert playback_service.engine.add_track.call_count == 1
    playback_service.engine.insert_track.assert_called_once()
    assert playback_service._schedule_save_queue.call_count == 2
    queued_item = playback_service.engine.add_track.call_args[0][0]
    inserted_item = playback_service.engine.insert_track.call_args[0][1]
    assert queued_item.online_provider_id == "qqmusic"
    assert inserted_item.online_provider_id == "qqmusic"


def test_runtime_remove_library_favorite_by_mid_is_provider_aware(monkeypatch):
    instance = Mock()
    track = Mock(id=42)
    instance.library_service.get_track_by_cloud_file_id.return_value = track
    monkeypatch.setattr(plugin_sdk_runtime, "bootstrap", lambda: instance)

    result = plugin_sdk_runtime.remove_library_favorite_by_mid("mid-1", provider_id="qqmusic")

    assert result is True
    instance.library_service.get_track_by_cloud_file_id.assert_called_once_with(
        "mid-1",
        provider_id="qqmusic",
    )
    instance.favorites_service.remove_favorite.assert_called_once_with(track_id=42)

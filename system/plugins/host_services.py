from __future__ import annotations

import logging
from pathlib import Path


class PluginSettingsBridgeImpl:
    def __init__(self, plugin_id: str, config) -> None:
        self._plugin_id = plugin_id
        self._config = config

    def _key(self, key: str) -> str:
        return f"plugins.{self._plugin_id}.{key}"

    def get(self, key: str, default=None):
        return self._config.get(self._key(key), default)

    def set(self, key: str, value) -> None:
        self._config.set(self._key(key), value)


class PluginStorageBridgeImpl:
    def __init__(self, root: Path, plugin_id: str) -> None:
        self.data_dir = root / plugin_id / "data"
        self.cache_dir = root / plugin_id / "cache"
        self.temp_dir = root / plugin_id / "tmp"
        for path in (self.data_dir, self.cache_dir, self.temp_dir):
            path.mkdir(parents=True, exist_ok=True)


class PluginUiBridgeImpl:
    def __init__(self, plugin_id: str, registry) -> None:
        self._plugin_id = plugin_id
        self._registry = registry

    def register_sidebar_entry(self, spec) -> None:
        self._registry.register_sidebar_entry(self._plugin_id, spec)

    def register_settings_tab(self, spec) -> None:
        self._registry.register_settings_tab(self._plugin_id, spec)


class PluginServiceBridgeImpl:
    def __init__(self, plugin_id: str, registry, media_bridge) -> None:
        self._plugin_id = plugin_id
        self._registry = registry
        self._media = media_bridge

    @property
    def media(self):
        return self._media

    def register_lyrics_source(self, source) -> None:
        self._registry.register_lyrics_source(self._plugin_id, source)

    def register_cover_source(self, source) -> None:
        self._registry.register_cover_source(self._plugin_id, source)

    def register_artist_cover_source(self, source) -> None:
        self._registry.register_artist_cover_source(self._plugin_id, source)

    def register_online_music_provider(self, provider) -> None:
        self._registry.register_online_provider(self._plugin_id, provider)


class BootstrapPluginContextFactory:
    def __init__(self, bootstrap, storage_root: Path) -> None:
        self._bootstrap = bootstrap
        self._storage_root = storage_root

    def build(self, manifest):
        from harmony_plugin_api.context import PluginContext

        plugin_id = manifest.id
        registry = self._bootstrap.plugin_manager.registry
        media_bridge = PluginMediaBridge(
            self._bootstrap.online_download_service,
            self._bootstrap.playback_service,
            self._bootstrap.library_service,
        )
        return PluginContext(
            plugin_id=plugin_id,
            manifest=manifest,
            logger=logging.getLogger(f"plugin.{plugin_id}"),
            http=self._bootstrap.http_client,
            events=self._bootstrap.event_bus,
            storage=PluginStorageBridgeImpl(self._storage_root, plugin_id),
            settings=PluginSettingsBridgeImpl(plugin_id, self._bootstrap.config),
            ui=PluginUiBridgeImpl(plugin_id, registry),
            services=PluginServiceBridgeImpl(plugin_id, registry, media_bridge),
        )


from .media_bridge import PluginMediaBridge

__all__ = [
    "BootstrapPluginContextFactory",
    "PluginMediaBridge",
    "PluginServiceBridgeImpl",
    "PluginSettingsBridgeImpl",
    "PluginStorageBridgeImpl",
    "PluginUiBridgeImpl",
]

from __future__ import annotations

import json
import logging
from pathlib import Path

from .plugin_sdk_ui import PluginDialogBridgeImpl, PluginThemeBridgeImpl

class PluginSettingsBridgeImpl:
    def __init__(self, plugin_id: str, config) -> None:
        self._plugin_id = plugin_id
        self._config = config

    def _key(self, key: str) -> str:
        return f"plugins.{self._plugin_id}.{key}"

    def _is_secret_key(self, key: str) -> bool:
        return key in {"credential", "token", "secret", "api_key", "password"}

    def get(self, key: str, default=None):
        if self._is_secret_key(key) and hasattr(self._config, "get_plugin_secret"):
            value = self._config.get_plugin_secret(self._plugin_id, key, default)
            if key == "credential" and isinstance(value, str) and value:
                try:
                    return json.loads(value)
                except Exception:
                    return default
            return value
        return self._config.get(self._key(key), default)

    def set(self, key: str, value) -> None:
        if self._is_secret_key(key) and hasattr(self._config, "set_plugin_secret"):
            secret_value = value
            if key == "credential":
                if value in (None, ""):
                    secret_value = ""
                elif not isinstance(value, str):
                    secret_value = json.dumps(value, ensure_ascii=False)
            self._config.set_plugin_secret(self._plugin_id, key, secret_value)
            return
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
        self._theme = PluginThemeBridgeImpl()
        self._dialogs = PluginDialogBridgeImpl()

    def register_sidebar_entry(self, spec) -> None:
        self._registry.register_sidebar_entry(self._plugin_id, spec)

    def register_settings_tab(self, spec) -> None:
        self._registry.register_settings_tab(self._plugin_id, spec)

    @property
    def theme(self):
        return self._theme

    @property
    def dialogs(self):
        return self._dialogs
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
        logging.getLogger(__name__).info(
            "[PluginHost] Building context for plugin %s",
            plugin_id,
        )
        manager = getattr(self._bootstrap, "_plugin_manager", None)
        if manager is None:
            manager = self._bootstrap.plugin_manager
        registry = manager.registry
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
            language=self._bootstrap.config.get_language(),
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

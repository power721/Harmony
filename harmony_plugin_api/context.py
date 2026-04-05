from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .manifest import PluginManifest


class PluginSettingsBridge(Protocol):
    def get(self, key: str, default: Any = None) -> Any:
        ...

    def set(self, key: str, value: Any) -> None:
        ...


class PluginStorageBridge(Protocol):
    @property
    def data_dir(self) -> Path:
        ...

    @property
    def cache_dir(self) -> Path:
        ...

    @property
    def temp_dir(self) -> Path:
        ...


class PluginUiBridge(Protocol):
    def register_sidebar_entry(self, spec: Any) -> None:
        ...

    def register_settings_tab(self, spec: Any) -> None:
        ...


class PluginServiceBridge(Protocol):
    def register_lyrics_source(self, source: Any) -> None:
        ...

    def register_cover_source(self, source: Any) -> None:
        ...

    def register_artist_cover_source(self, source: Any) -> None:
        ...

    def register_online_music_provider(self, provider: Any) -> None:
        ...

    @property
    def media(self) -> Any:
        ...


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    manifest: PluginManifest
    logger: Any
    http: Any
    events: Any
    storage: PluginStorageBridge
    settings: PluginSettingsBridge
    ui: PluginUiBridge
    services: PluginServiceBridge

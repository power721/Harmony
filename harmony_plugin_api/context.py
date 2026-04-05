from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .cover import PluginArtistCoverSource, PluginCoverSource
from .lyrics import PluginLyricsSource
from .manifest import PluginManifest
from .online import PluginOnlineProvider
from .registry_types import SettingsTabSpec, SidebarEntrySpec


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
    def register_sidebar_entry(self, spec: SidebarEntrySpec) -> None:
        ...

    def register_settings_tab(self, spec: SettingsTabSpec) -> None:
        ...


class PluginMediaBridge(Protocol):
    # Marker bridge for host media operations exposed to plugins.
    def __repr__(self) -> str:
        ...


class PluginServiceBridge(Protocol):
    def register_lyrics_source(self, source: PluginLyricsSource) -> None:
        ...

    def register_cover_source(self, source: PluginCoverSource) -> None:
        ...

    def register_artist_cover_source(self, source: PluginArtistCoverSource) -> None:
        ...

    def register_online_music_provider(self, provider: PluginOnlineProvider) -> None:
        ...

    @property
    def media(self) -> PluginMediaBridge:
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

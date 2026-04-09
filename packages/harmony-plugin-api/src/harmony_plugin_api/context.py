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


class PluginThemeBridge(Protocol):
    def register_widget(self, widget) -> None:
        ...

    def get_qss(self, template: str) -> str:
        ...

    def current_theme(self):
        ...


class PluginDialogBridge(Protocol):
    def information(self, parent, title: str, message: str):
        ...

    def warning(self, parent, title: str, message: str):
        ...

    def question(self, parent, title: str, message: str, buttons, default_button):
        ...

    def critical(self, parent, title: str, message: str):
        ...

    def setup_title_bar(self, dialog, container_layout, title: str, **kwargs):
        ...


class PluginUiBridge(Protocol):
    def register_sidebar_entry(self, spec: SidebarEntrySpec) -> None:
        ...

    def register_settings_tab(self, spec: SettingsTabSpec) -> None:
        ...

    @property
    def theme(self) -> PluginThemeBridge:
        ...

    @property
    def dialogs(self) -> PluginDialogBridge:
        ...


class PluginMediaBridge(Protocol):
    def cache_remote_track(self, request: Any, progress_callback=None, force: bool = False):
        ...

    def add_online_track(self, request: Any):
        ...

    def play_online_track(self, request: Any) -> int | None:
        ...

    def add_online_track_to_queue(self, request: Any) -> int | None:
        ...

    def insert_online_track_to_queue(self, request: Any) -> int | None:
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


class PluginRuntimeBridge(Protocol):
    def get_icon(self, name, color, size: int = 16):
        ...

    def image_cache_get(self, url: str):
        ...

    def image_cache_set(self, url: str, image_data: bytes):
        ...

    def image_cache_path(self, url: str):
        ...

    def http_get_content(
        self,
        url: str,
        *,
        timeout: int,
        headers: dict[str, str] | None = None,
    ):
        ...

    def cover_pixmap_cache_initialize(self) -> None:
        ...

    def cover_pixmap_cache_get(self, cache_key: str):
        ...

    def cover_pixmap_cache_set(self, cache_key: str, pixmap) -> None:
        ...

    def bootstrap(self):
        ...

    def library_service(self):
        ...

    def favorites_service(self):
        ...

    def favorite_mids_from_library(self) -> set[str]:
        ...

    def remove_library_favorite_by_mid(self, mid: str, provider_id: str | None = None) -> bool:
        ...

    def add_requests_to_favorites(self, requests):
        ...

    def add_requests_to_playlist(self, parent, requests, log_prefix: str):
        ...

    def add_track_ids_to_playlist(self, parent, track_ids, log_prefix: str) -> None:
        ...

    def event_bus(self):
        ...


@dataclass(frozen=True)
class PluginContext:
    plugin_id: str
    manifest: PluginManifest
    logger: Any
    http: Any
    events: Any
    language: str
    storage: PluginStorageBridge
    settings: PluginSettingsBridge
    ui: PluginUiBridge
    services: PluginServiceBridge
    runtime: PluginRuntimeBridge

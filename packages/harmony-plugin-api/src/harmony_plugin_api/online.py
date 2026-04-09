from __future__ import annotations

from typing import Any, Protocol

from .media import PluginPlaybackRequest, PluginTrack

__all__ = ["PluginOnlineProvider", "PluginPlaybackRequest", "PluginTrack"]


class PluginOnlineProvider(Protocol):
    provider_id: str
    display_name: str

    def create_page(self, context: Any, parent: Any = None) -> Any:
        ...

    def get_playback_url_info(
        self,
        track_id: str,
        quality: str,
    ) -> dict[str, Any] | None:
        ...

    def download_track(
        self,
        track_id: str,
        quality: str,
        target_dir: str | None = None,
        progress_callback: Any = None,
        force: bool = False,
    ) -> str | dict[str, Any] | None:
        ...

    def get_download_qualities(self, track_id: str) -> list[dict[str, str]] | list[str]:
        ...

    def redownload_track(
        self,
        track_id: str,
        quality: str,
        target_dir: str | None = None,
        progress_callback: Any = None,
    ) -> str | dict[str, Any] | None:
        ...

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

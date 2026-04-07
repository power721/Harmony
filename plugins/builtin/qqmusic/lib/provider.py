from __future__ import annotations

import logging
from typing import Any

from harmony_plugin_api.media import PluginTrack

from .client import QQMusicPluginClient
from .legacy_config_adapter import QQMusicLegacyConfigAdapter
from .online_music_view import OnlineMusicView
from .runtime_bridge import create_qqmusic_service

logger = logging.getLogger(__name__)


class QQMusicOnlineProvider:
    provider_id = "qqmusic"
    display_name = "QQ 音乐"

    def __init__(self, context):
        self._context = context
        self._client = QQMusicPluginClient(context)
        self._logger = getattr(context, "logger", logger)

    def create_page(self, context, parent=None):
        self._logger.info("[QQMusic] Creating legacy online music view")
        config = self._create_legacy_config_adapter(context)
        credential = config.get_plugin_secret("qqmusic", "credential", "")
        service = create_qqmusic_service(credential) if credential else None
        return OnlineMusicView(
            config_manager=config,
            qqmusic_service=service,
            plugin_context=context,
            parent=parent,
        )

    @staticmethod
    def _create_legacy_config_adapter(context):
        return QQMusicLegacyConfigAdapter(context.settings)

    def is_logged_in(self) -> bool:
        return self._client.is_logged_in()

    def search(
        self,
        keyword: str,
        search_type: str = "song",
        *,
        page: int = 1,
        page_size: int = 30,
    ) -> dict[str, Any]:
        return self._client.search(keyword, search_type=search_type, limit=page_size, page=page)

    def search_tracks(self, keyword: str) -> list[dict]:
        return self.search(keyword, search_type="song").get("tracks", [])

    def get_top_lists(self) -> list[dict]:
        return self._client.get_top_lists()

    def get_top_list_tracks(self, top_id: int | str) -> list[dict]:
        return self._client.get_top_list_tracks(top_id)

    def get_recommendations(self) -> list[dict]:
        return self._client.get_recommendations()

    def get_favorites(self) -> list[dict]:
        return self._client.get_favorites()

    def get_artist_detail(self, singer_mid: str) -> dict | None:
        return self._client.get_artist_detail(singer_mid)

    def get_artist_albums(self, singer_mid: str, limit: int = 10) -> list[dict]:
        return self._client.get_artist_albums(singer_mid, limit=limit)

    def follow_artist(self, singer_mid: str) -> bool:
        return self._client.follow_artist(singer_mid)

    def unfollow_artist(self, singer_mid: str) -> bool:
        return self._client.unfollow_artist(singer_mid)

    def get_album_detail(self, album_mid: str) -> dict | None:
        return self._client.get_album_detail(album_mid)

    def fav_album(self, album_mid: str) -> bool:
        return self._client.fav_album(album_mid)

    def unfav_album(self, album_mid: str) -> bool:
        return self._client.unfav_album(album_mid)

    def get_playlist_detail(self, playlist_id: str) -> dict | None:
        return self._client.get_playlist_detail(playlist_id)

    def fav_playlist(self, playlist_id: str) -> bool:
        return self._client.fav_playlist(playlist_id)

    def unfav_playlist(self, playlist_id: str) -> bool:
        return self._client.unfav_playlist(playlist_id)

    def get_hotkeys(self) -> list[dict]:
        return self._client.get_hotkeys()

    def complete(self, keyword: str) -> list[dict]:
        return self._client.complete(keyword)

    def get_demo_track(self) -> PluginTrack:
        return PluginTrack(
            track_id="demo-mid",
            title="Demo Song",
            artist="Demo Artist",
            album="Demo Album",
        )

    def get_playback_url_info(self, track_id: str, quality: str):
        return self._client.get_playback_url_info(track_id, quality)

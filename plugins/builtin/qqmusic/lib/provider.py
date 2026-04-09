from __future__ import annotations

import logging
from typing import Any

from harmony_plugin_api.media import PluginTrack

from .api import QQMusicPluginAPI
from .client import QQMusicPluginClient
from .common import get_quality_label_key, get_selectable_qualities
from .config_adapter import QQMusicConfigAdapter
from .i18n import t
from .media_helpers import build_album_cover_url, extract_album_mid, pick_lyric_text
from .online_music_view import OnlineMusicView
from .runtime_bridge import (
    bind_context,
    create_online_download_service,
    create_qqmusic_service,
)

logger = logging.getLogger(__name__)


class QQMusicOnlineProvider:
    provider_id = "qqmusic"
    display_name = "QQ 音乐"

    def __init__(self, context):
        self._context = context
        bind_context(context)
        self._client = QQMusicPluginClient(context)
        self._download_service = None
        self._logger = getattr(context, "logger", logger)

    def create_page(self, context, parent=None):
        bind_context(context)
        self._logger.info("[QQMusic] Creating plugin online music view")
        config = self._create_config_adapter(context)
        credential = config.get_plugin_secret("qqmusic", "credential", "")
        service = create_qqmusic_service(credential) if credential else None
        return OnlineMusicView(
            config_manager=config,
            qqmusic_service=service,
            plugin_context=context,
            parent=parent,
        )

    @staticmethod
    def _create_config_adapter(context):
        return QQMusicConfigAdapter(context.settings)

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

    def get_lyrics(self, song_mid: str) -> str | None:
        service = self._client._get_service()
        if service is not None and self._client._can_use_legacy_network():
            try:
                lyric_data = service.get_lyrics(song_mid) or {}
            except Exception:
                lyric_data = {}
            lyric_text = pick_lyric_text(lyric_data)
            if lyric_text:
                return lyric_text

        try:
            return QQMusicPluginAPI(self._context).get_lyrics(song_mid)
        except Exception:
            return None

    def get_cover_url(
        self,
        mid: str | None = None,
        album_mid: str | None = None,
        size: int = 500,
    ) -> str | None:
        cover_url = build_album_cover_url(album_mid or "", size)
        if cover_url:
            return cover_url

        service = self._client._get_service()
        if service is not None and mid and self._client._can_use_legacy_network():
            try:
                detail = service.client.get_song_detail(mid)
            except Exception:
                detail = {}
            cover_url = build_album_cover_url(extract_album_mid(detail), size)
            if cover_url:
                return cover_url

        try:
            return QQMusicPluginAPI(self._context).get_cover_url(mid=mid, album_mid=album_mid, size=size)
        except Exception:
            return None

    def download_track(
        self,
        track_id: str,
        quality: str,
        target_dir: str | None = None,
        progress_callback=None,
        force: bool = False,
    ) -> dict[str, Any] | None:
        if self._download_service is None:
            self._download_service = create_online_download_service(
                config_manager=self._create_config_adapter(self._context),
                credential_provider=self._client,
                online_music_service=None,
            )
        if target_dir and hasattr(self._download_service, "set_download_dir"):
            self._download_service.set_download_dir(target_dir)
        local_path = self._download_service.download(
            track_id,
            quality=quality,
            progress_callback=progress_callback,
            force=force,
        )
        if not local_path:
            return None
        actual_quality = self._download_service.pop_last_download_quality(track_id)
        return {
            "local_path": local_path,
            "quality": actual_quality or quality,
        }

    def get_download_qualities(self, track_id: str) -> list[dict[str, str]]:
        del track_id
        options: list[dict[str, str]] = []
        for quality in get_selectable_qualities():
            label_key = get_quality_label_key(quality)
            label = t(label_key, quality)
            options.append({"value": quality, "label": label})
        return options

    def redownload_track(
        self,
        track_id: str,
        quality: str,
        target_dir: str | None = None,
        progress_callback=None,
    ) -> dict[str, Any] | None:
        return self.download_track(
            track_id=track_id,
            quality=quality,
            target_dir=target_dir,
            progress_callback=progress_callback,
            force=True,
        )

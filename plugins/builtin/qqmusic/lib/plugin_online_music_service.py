from __future__ import annotations

import html
import re
from typing import Any, Optional

from .client import QQMusicPluginClient
from .models import (
    AlbumInfo,
    OnlineAlbum,
    OnlineArtist,
    OnlinePlaylist,
    OnlineSinger,
    OnlineTrack,
    SearchResult,
)


class PluginOnlineMusicService:
    """Plugin-local online music service used by QQ Music pages."""

    def __init__(self, context, config_manager=None, credential_provider=None):
        self._context = context
        self._config = config_manager
        self._provider = credential_provider
        self._client_adapter = QQMusicPluginClient(context)

    @property
    def client(self):
        return getattr(self._provider, "client", None)

    def _has_qqmusic_credential(self) -> bool:
        if self._provider and getattr(self._provider, "_credential", None):
            return True
        if self._config and hasattr(self._config, "get_plugin_secret"):
            return bool(self._config.get_plugin_secret("qqmusic", "credential", ""))
        return bool(self._context.settings.get("credential", None))

    def search(
        self,
        keyword: str,
        search_type: str = "song",
        page: int = 1,
        page_size: int = 50,
    ) -> SearchResult:
        payload = self._client_adapter.search(
            keyword,
            search_type=search_type,
            limit=page_size,
            page=page,
        )
        result = SearchResult(
            keyword=keyword,
            search_type=search_type,
            page=page,
            page_size=page_size,
            total=int(payload.get("total", 0) or 0),
        )
        if search_type == "song":
            result.tracks = [self._dict_to_track(item) for item in payload.get("tracks", [])]
            if result.total <= 0:
                result.total = len(result.tracks)
        elif search_type == "singer":
            result.artists = [self._dict_to_artist(item) for item in payload.get("artists", [])]
            if result.total <= 0:
                result.total = len(result.artists)
        elif search_type == "album":
            result.albums = [self._dict_to_album(item) for item in payload.get("albums", [])]
            if result.total <= 0:
                result.total = len(result.albums)
        elif search_type == "playlist":
            result.playlists = [self._dict_to_playlist(item) for item in payload.get("playlists", [])]
            if result.total <= 0:
                result.total = len(result.playlists)
        return result

    def get_top_lists(self) -> list[dict[str, Any]]:
        return self._client_adapter.get_top_lists()

    def get_top_list_songs(self, top_id: int, num: int = 100) -> list[OnlineTrack]:
        items = self._client_adapter.get_top_list_tracks(top_id)
        return [self._dict_to_track(item) for item in items[:num]]

    def get_artist_detail(self, singer_mid: str, page: int = 1, page_size: int = 50) -> Optional[dict[str, Any]]:
        if self._provider and hasattr(self._provider, "get_singer_info_with_follow_status"):
            detail = self._provider.get_singer_info_with_follow_status(singer_mid, page=page, page_size=page_size)
            if detail:
                return detail
        return self._client_adapter.get_artist_detail(singer_mid)

    def get_artist_albums(self, singer_mid: str, number: int = 30, begin: int = 0) -> dict[str, Any]:
        _ = begin
        payload = self._client_adapter.get_artist_albums(singer_mid, limit=number)
        if isinstance(payload, dict):
            albums = payload.get("albums", [])
            total = int(payload.get("total", 0) or 0)
            if not isinstance(albums, list):
                albums = []
            if total <= 0:
                total = len(albums)
            return {
                "albums": albums,
                "total": total,
            }
        albums = payload if isinstance(payload, list) else []
        return {
            "albums": albums,
            "total": len(albums),
        }

    def get_album_detail(self, album_mid: str, page: int = 1, page_size: int = 50) -> Optional[dict[str, Any]]:
        if self._provider and hasattr(self._provider, "get_album_info_with_fav_status"):
            detail = self._provider.get_album_info_with_fav_status(album_mid, page=page, page_size=page_size)
            if detail:
                return detail
        return self._client_adapter.get_album_detail(album_mid)

    def get_playlist_detail(self, playlist_id: str, page: int = 1, page_size: int = 50) -> Optional[dict[str, Any]]:
        if self._provider and hasattr(self._provider, "get_playlist_info_with_fav_status"):
            detail = self._provider.get_playlist_info_with_fav_status(playlist_id, page=page, page_size=page_size)
            if detail:
                return detail
        return self._client_adapter.get_playlist_detail(playlist_id)

    def get_song_detail(self, song_mid: str) -> Optional[dict[str, Any]]:
        if self._provider and hasattr(self._provider, "get_song_detail"):
            return self._provider.get_song_detail(song_mid)
        return None

    def get_playback_url_info(self, song_mid: str, quality: str = "320") -> Optional[dict[str, Any]]:
        return self._client_adapter.get_playback_url_info(song_mid, quality)

    def get_playback_url(self, song_mid: str, quality: str = "320") -> Optional[str]:
        info = self.get_playback_url_info(song_mid, quality)
        if not info:
            return None
        return info.get("url")

    def follow_singer(self, singer_mid: str) -> bool:
        return bool(self._client_adapter.follow_artist(singer_mid))

    def unfollow_singer(self, singer_mid: str) -> bool:
        return bool(self._client_adapter.unfollow_artist(singer_mid))

    def fav_album(self, album_mid: str) -> bool:
        return bool(self._client_adapter.fav_album(album_mid))

    def unfav_album(self, album_mid: str) -> bool:
        return bool(self._client_adapter.unfav_album(album_mid))

    def fav_playlist(self, playlist_id: str) -> bool:
        return bool(self._client_adapter.fav_playlist(playlist_id))

    def unfav_playlist(self, playlist_id: str) -> bool:
        return bool(self._client_adapter.unfav_playlist(playlist_id))

    def fav_song(self, song_mid: str) -> bool:
        provider = self._provider
        if provider and hasattr(provider, "fav_song"):
            return bool(provider.fav_song(song_mid))
        return False

    def unfav_song(self, song_mid: str) -> bool:
        provider = self._provider
        if provider and hasattr(provider, "unfav_song"):
            return bool(provider.unfav_song(song_mid))
        return False

    @staticmethod
    def _dict_to_track(item: dict[str, Any]) -> OnlineTrack:
        artist = PluginOnlineMusicService._clean_text(
            item.get("artist", "") or item.get("singer", "")
        )
        singers = [
            OnlineSinger(name=name.strip())
            for name in artist.split(",")
            if name and name.strip()
        ]
        return OnlineTrack(
            mid=str(item.get("mid", "")),
            id=item.get("id"),
            title=PluginOnlineMusicService._clean_text(item.get("title", "") or item.get("name", "")),
            singer=singers,
            album=AlbumInfo(
                mid=str(item.get("album_mid", "")),
                name=PluginOnlineMusicService._clean_text(item.get("album", "")),
            ),
            duration=int(float(item.get("duration", 0) or 0)),
            pay_play=int(item.get("pay_play", 0) or 0),
        )

    @staticmethod
    def _dict_to_artist(item: dict[str, Any]) -> OnlineArtist:
        return OnlineArtist(
            mid=str(item.get("mid", "")),
            name=PluginOnlineMusicService._clean_text(item.get("name", "") or item.get("title", "")),
            avatar_url=item.get("avatar_url") or item.get("cover_url"),
            song_count=int(item.get("song_count", 0) or 0),
            album_count=int(item.get("album_count", 0) or 0),
            fan_count=int(item.get("fan_count", 0) or 0),
        )

    @staticmethod
    def _dict_to_album(item: dict[str, Any]) -> OnlineAlbum:
        return OnlineAlbum(
            mid=str(item.get("mid", "")),
            name=PluginOnlineMusicService._clean_text(item.get("name", "") or item.get("title", "")),
            singer_mid=str(item.get("singer_mid", "")),
            singer_name=PluginOnlineMusicService._clean_text(
                item.get("singer_name", "") or item.get("artist", "")
            ),
            cover_url=item.get("cover_url"),
            song_count=int(item.get("song_count", 0) or 0),
            publish_date=item.get("publish_date"),
        )

    @staticmethod
    def _dict_to_playlist(item: dict[str, Any]) -> OnlinePlaylist:
        return OnlinePlaylist(
            id=str(item.get("id", "")),
            mid=str(item.get("mid", "")),
            title=PluginOnlineMusicService._clean_text(item.get("title", "")),
            creator=PluginOnlineMusicService._clean_text(item.get("creator", "")),
            cover_url=item.get("cover_url"),
            song_count=int(item.get("song_count", 0) or 0),
            play_count=int(item.get("play_count", 0) or 0),
        )

    @classmethod
    def _clean_text(cls, value: Any) -> str:
        text = str(value or "")
        text = cls._HIGHLIGHT_TAG_PATTERN.sub("", text)
        return html.unescape(text).strip()
    _HIGHLIGHT_TAG_PATTERN = re.compile(r"</?em[^>]*>", re.IGNORECASE)

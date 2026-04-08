from __future__ import annotations

import socket
from typing import Any

from .api import QQMusicPluginAPI
from .qqmusic_service import QQMusicService


class QQMusicPluginClient:
    def __init__(self, context):
        self._context = context
        self._api = QQMusicPluginAPI(context)
        self._legacy_network_reachable: bool | None = None

    def get_quality(self) -> str:
        return str(self._context.settings.get("quality", "320"))

    def _get_credential(self) -> dict[str, Any] | None:
        credential = self._context.settings.get("credential", None)
        return credential if isinstance(credential, dict) else None

    def _get_service(self) -> QQMusicService | None:
        credential = self._get_credential()
        if not credential:
            return None
        return QQMusicService(credential, http_client=self._context.http)

    def _can_use_legacy_network(self) -> bool:
        if self._legacy_network_reachable is not None:
            return self._legacy_network_reachable
        try:
            sock = socket.create_connection(("u.y.qq.com", 443), timeout=0.5)
            sock.close()
            self._legacy_network_reachable = True
        except OSError:
            self._legacy_network_reachable = False
        return self._legacy_network_reachable

    def is_logged_in(self) -> bool:
        return bool(self._get_credential() or self._context.settings.get("nick", ""))

    def set_credential(self, credential: dict) -> None:
        self._context.settings.set("credential", credential)

    def clear_credential(self) -> None:
        self._context.settings.set("credential", None)

    def search(
        self,
        keyword: str,
        search_type: str = "song",
        limit: int = 20,
        page: int = 1,
    ) -> dict[str, list[dict]]:
        # Prefer QQ Music direct client when logged in
        if self._get_credential() and self._can_use_legacy_network():
            result = self._search_legacy(keyword, search_type, page, limit)
            if self._has_search_results(result, search_type):
                return result

        # Fallback to remote API
        return self._api.search(keyword, search_type=search_type, limit=limit, page=page)

    @staticmethod
    def _has_search_results(result: dict[str, Any] | None, search_type: str) -> bool:
        if not isinstance(result, dict):
            return False
        key_by_type = {
            "song": "tracks",
            "singer": "artists",
            "album": "albums",
            "playlist": "playlists",
        }
        result_key = key_by_type.get(search_type, "tracks")
        items = result.get(result_key, [])
        return isinstance(items, list) and len(items) > 0

    def _search_legacy(
        self,
        keyword: str,
        search_type: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, list[dict]] | None:
        """Search using legacy QQ Music client."""
        service = self._get_service()
        if service is None:
            return None

        try:
            raw_data = service.client.search(
                keyword,
                search_type=search_type,
                page_num=page,
                page_size=page_size,
            )
            return self._normalize_legacy_search_payload(raw_data, search_type)
        except Exception:
            return None

    def _normalize_legacy_search_payload(
        self,
        raw_data: dict[str, Any] | None,
        search_type: str,
    ) -> dict[str, list[dict]] | None:
        if not isinstance(raw_data, dict):
            return None

        root = raw_data.get("data", {}).get("body", {})
        if search_type == "song":
            song_section = root.get("song", {}) if isinstance(root, dict) else {}
            items = song_section.get("list", [])
            total = song_section.get("totalnum") or song_section.get("totalNum") or len(items)
            return {
                "tracks": [self._normalize_detail_song(item) for item in items if isinstance(item, dict)],
                "total": int(total or 0),
            }

        if search_type == "singer":
            singer_section = root.get("singer", {}) if isinstance(root, dict) else {}
            items = singer_section.get("list", [])
            total = singer_section.get("totalnum") or singer_section.get("totalNum") or len(items)
            return {
                "artists": [
                    {
                        "mid": str(item.get("singerMID", "") or item.get("mid", "")),
                        "name": str(item.get("singerName", "") or item.get("name", "")),
                        "pic_url": item.get("pic") or item.get("pic_url") or "",
                        "song_count": int(item.get("songNum", 0) or item.get("song_count", 0) or 0),
                    }
                    for item in items
                    if isinstance(item, dict)
                ],
                "total": int(total or 0),
            }

        if search_type == "album":
            album_section = root.get("album", {}) if isinstance(root, dict) else {}
            items = album_section.get("list", [])
            total = album_section.get("totalnum") or album_section.get("totalNum") or len(items)
            return {
                "albums": [
                    {
                        "mid": str(item.get("albumMID", "") or item.get("mid", "")),
                        "name": str(item.get("albumName", "") or item.get("name", "")),
                        "artist": str(item.get("singerName", "") or item.get("artist", "")),
                        "cover_url": item.get("albumPic", "") or item.get("cover_url", ""),
                    }
                    for item in items
                    if isinstance(item, dict)
                ],
                "total": int(total or 0),
            }

        if search_type == "playlist":
            playlist_section = root.get("songlist", {}) if isinstance(root, dict) else {}
            items = playlist_section.get("list", [])
            total = playlist_section.get("totalnum") or playlist_section.get("totalNum") or len(items)
            return {
                "playlists": [
                    {
                        "id": str(item.get("dissid", "") or item.get("id", "")),
                        "title": str(item.get("dissname", "") or item.get("title", "")),
                        "creator": str(
                            item.get("creator", {}).get("name", "")
                            if isinstance(item.get("creator"), dict)
                            else item.get("creator", "")
                        ),
                        "cover_url": item.get("imgurl", "") or item.get("cover_url", ""),
                    }
                    for item in items
                    if isinstance(item, dict)
                ],
                "total": int(total or 0),
            }

        return None

    def get_top_lists(self) -> list[dict]:
        return self._api.get_top_lists()

    def get_top_list_tracks(self, top_id: int | str) -> list[dict]:
        api_data = self._api.get_top_list_tracks(top_id)
        if isinstance(api_data, list) and api_data:
            return api_data
        service = self._get_service()
        if service is not None and self._can_use_legacy_network():
            data = service.get_top_list_songs(int(top_id), num=100)
            if isinstance(data, list) and data:
                return [self._normalize_top_list_track(item) for item in data]
        return api_data if isinstance(api_data, list) else []

    def get_recommendations(self) -> list[dict]:
        service = self._get_service()
        if service is None or not self._can_use_legacy_network():
            return []

        items: list[dict] = []
        for card_id, title, entry_type, loader in (
            ("home_feed", "首页推荐", "songs", service.get_home_feed),
            ("guess", "猜你喜欢", "songs", service.get_guess_recommend),
            ("radar", "雷达歌单", "songs", service.get_radar_recommend),
            ("songlist", "推荐歌单", "playlists", service.get_recommend_songlist),
            ("newsong", "新歌推荐", "songs", service.get_recommend_newsong),
        ):
            try:
                data = loader() or []
            except Exception:
                data = []
            if data:
                items.append(
                    {
                        "id": card_id,
                        "title": title,
                        "subtitle": f"{len(data)} 项",
                        "cover_url": self._pick_cover(data),
                        "items": data,
                        "entry_type": entry_type,
                    }
                )
        return items

    def get_favorites(self) -> list[dict]:
        service = self._get_service()
        if service is None or not self._can_use_legacy_network():
            return []

        sections = []
        for card_id, title, entry_type, loader in (
            ("fav_songs", "我喜欢的歌曲", "songs", lambda: service.get_my_fav_songs(page=1, num=30)),
            ("created_playlists", "我创建的歌单", "playlists", service.get_my_created_songlists),
            ("fav_playlists", "我收藏的歌单", "playlists", lambda: service.get_my_fav_songlists(page=1, num=30)),
            ("fav_albums", "我收藏的专辑", "albums", lambda: service.get_my_fav_albums(page=1, num=30)),
            ("followed_singers", "我关注的歌手", "artists", lambda: service.get_followed_singers(page=1, size=30)),
        ):
            try:
                data = loader() or []
            except Exception:
                data = []
            if data:
                sections.append(
                    {
                        "id": card_id,
                        "title": title,
                        "count": len(data),
                        "subtitle": f"{len(data)} 项",
                        "cover_url": self._pick_cover(data),
                        "items": data,
                        "entry_type": entry_type,
                    }
                )
        return sections

    def get_playback_url_info(self, track_id: str, quality: str):
        service = self._get_service()
        if service is not None:
            info = service.get_playback_url_info(track_id, quality)
            if info:
                return info
        return self._api.get_playback_url_info(track_id, quality)

    def get_artist_detail(self, singer_mid: str) -> dict | None:
        service = self._get_service()
        if service is not None:
            detail = service.get_singer_info_with_follow_status(singer_mid, page=1, page_size=30)
            if detail:
                return {
                    "title": detail.get("name", ""),
                    "description": detail.get("desc", ""),
                    "songs": [self._normalize_detail_song(item) for item in detail.get("songs", [])],
                    "follow_status": bool(detail.get("follow_status", False)),
                }
        return self._api.get_artist_detail(singer_mid)

    def get_artist_albums(self, singer_mid: str, limit: int = 10) -> list[dict]:
        service = self._get_service()
        if service is None:
            return []
        detail = service.get_singer_albums(singer_mid, number=limit, begin=0)
        if not isinstance(detail, dict):
            return []
        albums = detail.get("albums", [])
        return albums if isinstance(albums, list) else []

    def get_album_detail(self, album_mid: str) -> dict | None:
        service = self._get_service()
        if service is not None:
            detail = service.get_album_info_with_fav_status(album_mid, page=1, page_size=30)
            if detail:
                return {
                    "title": detail.get("name", ""),
                    "description": detail.get("description", ""),
                    "songs": [self._normalize_detail_song(item) for item in detail.get("songs", [])],
                    "is_faved": bool(detail.get("fav_status", False)),
                }
        return self._api.get_album_detail(album_mid)

    def get_playlist_detail(self, playlist_id: str) -> dict | None:
        service = self._get_service()
        if service is not None:
            detail = service.get_playlist_info_with_fav_status(playlist_id, page=1, page_size=30)
            if detail:
                return {
                    "title": detail.get("name", ""),
                    "description": detail.get("description", ""),
                    "songs": [self._normalize_detail_song(item) for item in detail.get("songs", [])],
                    "is_faved": bool(detail.get("fav_status", False)),
                }
        return self._api.get_playlist_detail(playlist_id)

    def follow_artist(self, singer_mid: str) -> bool:
        service = self._get_service()
        if service is None:
            return False
        return bool(service.follow_singer(singer_mid))

    def unfollow_artist(self, singer_mid: str) -> bool:
        service = self._get_service()
        if service is None:
            return False
        return bool(service.unfollow_singer(singer_mid))

    def fav_album(self, album_mid: str) -> bool:
        service = self._get_service()
        if service is None:
            return False
        return bool(service.fav_album(album_mid))

    def unfav_album(self, album_mid: str) -> bool:
        service = self._get_service()
        if service is None:
            return False
        return bool(service.unfav_album(album_mid))

    def fav_playlist(self, playlist_id: str) -> bool:
        service = self._get_service()
        if service is None:
            return False
        return bool(service.fav_playlist(playlist_id))

    def unfav_playlist(self, playlist_id: str) -> bool:
        service = self._get_service()
        if service is None:
            return False
        return bool(service.unfav_playlist(playlist_id))

    def get_hotkeys(self) -> list[dict]:
        api_items = self._api.get_hotkeys()
        if isinstance(api_items, list) and api_items:
            return api_items

        service = self._get_service()
        if service is not None and self._can_use_legacy_network():
            try:
                legacy_items = service.get_hotkey() or []
            except Exception:
                legacy_items = []
            normalized = []
            for item in legacy_items:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("k") or item.get("query") or "").strip()
                query = str(item.get("query") or item.get("k") or title).strip()
                if title:
                    normalized.append({"title": title, "query": query})
            if normalized:
                return normalized

        return []

    def complete(self, keyword: str) -> list[dict]:
        return self._api.complete(keyword)

    def _normalize_detail_song(self, item: dict) -> dict:
        singer_value = item.get("singer", "")
        if isinstance(singer_value, list):
            singer_name = ", ".join(entry.get("name", "") for entry in singer_value if isinstance(entry, dict) and entry.get("name"))
        else:
            singer_name = str(singer_value or "")
        album_value = item.get("album", {})
        if isinstance(album_value, dict):
            album_name = album_value.get("name", item.get("albumname", ""))
        else:
            album_name = str(album_value or item.get("albumname", ""))
        return {
            "mid": item.get("mid", "") or item.get("songmid", ""),
            "title": item.get("title", item.get("name", "")),
            "artist": singer_name,
            "album": album_name,
            "duration": item.get("interval", item.get("duration", 0)),
        }

    def _normalize_top_list_track(self, item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            singer_value = item.get("artist", item.get("singer", ""))
            if isinstance(singer_value, list):
                artist = ", ".join(
                    entry.get("name", "")
                    for entry in singer_value
                    if isinstance(entry, dict) and entry.get("name")
                )
            elif isinstance(singer_value, dict):
                artist = str(singer_value.get("name", ""))
            else:
                artist = str(singer_value or "")

            album_value = item.get("album", "")
            album_mid = ""
            if isinstance(album_value, dict):
                album = str(album_value.get("name", item.get("albumname", "")))
                album_mid = str(album_value.get("mid", item.get("album_mid", "")) or "")
            else:
                album = str(album_value or item.get("albumname", ""))
                album_mid = str(item.get("album_mid", item.get("albummid", "")) or "")

            return {
                "mid": str(item.get("mid", item.get("songmid", ""))),
                "title": str(item.get("title", item.get("name", ""))),
                "artist": artist,
                "album": album,
                "album_mid": album_mid,
                "duration": int(item.get("interval", item.get("duration", 0)) or 0),
            }

        return {
            "mid": getattr(item, "mid", ""),
            "title": getattr(item, "title", ""),
            "artist": getattr(item, "singer_name", ""),
            "album": getattr(item, "album_name", ""),
            "album_mid": getattr(getattr(item, "album", None), "mid", ""),
            "duration": getattr(item, "duration", 0),
        }

    def _pick_cover(self, items: list[dict[str, Any]]) -> str:
        for item in items:
            if not isinstance(item, dict):
                continue
            if isinstance(item.get("Track"), dict):
                track = item["Track"]
                album = track.get("album", {})
                if isinstance(album, dict) and album.get("mid"):
                    return f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album.get('mid')}.jpg"
                cover_url = track.get("cover_url") or track.get("cover") or track.get("picurl") or track.get("pic")
                if isinstance(cover_url, dict):
                    cover_url = cover_url.get("default_url") or cover_url.get("small_url")
                if cover_url:
                    return str(cover_url)
            if isinstance(item.get("Playlist"), dict):
                playlist = item["Playlist"]
                basic = playlist.get("basic", {}) if isinstance(playlist.get("basic"), dict) else {}
                content = playlist.get("content", {}) if isinstance(playlist.get("content"), dict) else {}
                cover_url = (
                    basic.get("cover_url")
                    or basic.get("cover")
                    or content.get("cover_url")
                    or content.get("cover")
                    or playlist.get("cover_url")
                    or playlist.get("cover")
                )
                if isinstance(cover_url, dict):
                    cover_url = cover_url.get("default_url") or cover_url.get("small_url")
                if cover_url:
                    return str(cover_url)
            cover_url = item.get("cover_url") or item.get("cover") or item.get("picurl") or item.get("pic")
            if isinstance(cover_url, dict):
                cover_url = cover_url.get("default_url") or cover_url.get("small_url")
            if cover_url:
                return str(cover_url)
            album = item.get("album", {})
            if isinstance(album, dict) and album.get("mid"):
                return f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album.get('mid')}.jpg"
            if item.get("album_mid"):
                return f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{item.get('album_mid')}.jpg"
        return ""

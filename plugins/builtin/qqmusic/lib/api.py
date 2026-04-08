from __future__ import annotations

from typing import Any, Optional

from plugins.builtin.qqmusic.lib.common import parse_quality
from .media_helpers import build_album_cover_url, build_artist_cover_url
from .search_normalizers import (
    normalize_album_item,
    normalize_artist_item,
    normalize_playlist_item,
    normalize_song_item,
)


class QQMusicPluginAPI:
    REMOTE_BASE_URL = "https://api.ygking.top/api"

    def __init__(self, context):
        self._context = context

    def search(
            self,
            keyword: str,
            search_type: str = "song",
            limit: int = 20,
            page: int = 1,
    ) -> dict[str, Any]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/search",
            params={"keyword": keyword, "type": search_type, "num": limit, "page": page},
            timeout=10,
        )
        data = response.json()
        payload = data.get("data", {}) if isinstance(data.get("data"), dict) else {}
        items = payload.get("list", [])
        if not isinstance(items, list):
            items = []
        total = self._extract_search_total(data, payload, items)
        if search_type == "song":
            return {
                "tracks": [normalize_song_item(song) for song in items[:limit]],
                "total": total,
            }
        if search_type == "singer":
            return {
                "artists": [
                    {
                        **normalize_artist_item(item),
                        "avatar_url": normalize_artist_item(item).get("avatar_url")
                        or build_artist_cover_url(
                            str(item.get("singerMID", item.get("mid", ""))),
                            300,
                        ),
                    }
                    for item in items[:limit]
                ],
                "total": total,
            }
        if search_type == "album":
            return {
                "albums": [
                    {
                        **normalize_album_item(item),
                        "cover_url": normalize_album_item(item).get("cover_url")
                        or build_album_cover_url(
                            str(item.get("albummid", item.get("mid", ""))),
                            500,
                        ),
                    }
                    for item in items[:limit]
                ],
                "total": total,
            }
        return {
            "playlists": [normalize_playlist_item(item) for item in items[:limit]],
            "total": total,
        }

    @staticmethod
    def _extract_search_total(raw_data: dict[str, Any], payload: dict[str, Any], items: list[Any]) -> int:
        """Extract total hit count from heterogeneous search payloads."""
        total_keys = (
            "total",
            "totalnum",
            "totalNum",
            "record_num",
            "recordNum",
            "count",
            "sum",
            "sum_count",
        )

        def _to_non_negative_int(value: Any) -> Optional[int]:
            if value is None or isinstance(value, bool):
                return None
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                return None
            return parsed if parsed >= 0 else None

        candidates: list[dict[str, Any]] = [payload]
        if isinstance(raw_data, dict):
            candidates.append(raw_data)
            raw_data_payload = raw_data.get("data")
            if isinstance(raw_data_payload, dict):
                candidates.append(raw_data_payload)
                meta = raw_data_payload.get("meta")
                if isinstance(meta, dict):
                    candidates.append(meta)
                extra_data = raw_data_payload.get("data")
                if isinstance(extra_data, dict):
                    candidates.append(extra_data)

        for container in candidates:
            for key in total_keys:
                parsed = _to_non_negative_int(container.get(key))
                if parsed is not None:
                    return parsed

        return len(items)

    def search_artist(
            self,
            keyword: str,
            limit: int = 20,
            page: int = 1,
    ) -> list[dict]:
        return self.search(
            keyword,
            search_type="singer",
            limit=limit,
            page=page,
        ).get("artists", [])

    def get_top_lists(self) -> list[dict]:
        response = self._context.http.get(f"{self.REMOTE_BASE_URL}/top", timeout=20)
        data = response.json()
        if data.get("code") != 0:
            return []
        groups = data.get("data", {}).get("group", [])
        return [
            {"id": item.get("topId", ""), "title": item.get("title", "")}
            for group in groups
            for item in group.get("toplist", [])
        ]

    def get_top_list_tracks(self, top_id: int | str, limit: int = 100) -> list[dict]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/top",
            params={"id": top_id, "num": limit},
            timeout=20,
        )
        data = response.json()
        if data.get("code") != 0:
            return []
        items = data.get("data", {}).get("songInfoList", [])
        if not items:
            items = data.get("data", {}).get("data", {}).get("song", [])
        return [normalize_song_item(song) for song in items[:limit]]

    def get_lyrics(self, mid: str) -> Optional[str]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/lyric",
            params={"mid": mid, "qrc": 1},
            timeout=10,
        )
        data = response.json()
        return data.get("data", {}).get("lyric")

    def get_cover_url(
            self,
            mid: str = None,
            album_mid: str = None,
            size: int = 500,
    ) -> Optional[str]:
        if album_mid:
            return build_album_cover_url(album_mid, size)
        if mid:
            response = self._context.http.get(
                f"{self.REMOTE_BASE_URL}/song/cover",
                params={"mid": mid, "size": size},
                timeout=10,
            )
            if response.status_code == 302:
                return response.headers.get("Location")
            data = response.json()
            if data.get("code") == 0:
                return data.get("data", {}).get("url")
        return None

    def get_artist_cover_url(self, singer_mid: str, size: int = 300) -> Optional[str]:
        return build_artist_cover_url(singer_mid, size)

    def get_playback_url_info(self, track_id: str, quality: str) -> dict[str, str] | None:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/song/url",
            params={"mid": track_id, "quality": quality},
            timeout=15,
        )
        data = response.json()
        print(data)
        if data.get("code") != 0:
            return None
        result = data.get("data", {})
        url = result.get(track_id, '')
        quality = result.get(quality, '')
        file_type = parse_quality(quality)

        if url:
            return {
                'url': url,
                'quality': quality,
                'file_type': file_type,
                'extension': file_type.get("e"),
            }

        return None

    def get_artist_detail(self, singer_mid: str) -> dict | None:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/singer",
            params={"mid": singer_mid},
            timeout=15,
        )
        data = response.json()
        if data.get("code") != 0:
            return None
        data_obj = data.get("data", {})
        singer_list = data_obj.get("singer_list", [])
        if not singer_list:
            return None
        singer = singer_list[0]
        title = singer.get("basic_info", {}).get("name", "")
        songs = self.search(title, search_type="song", limit=30).get("tracks", [])
        return {
            "title": title,
            "description": singer.get("ex_info", {}).get("desc", ""),
            "songs": songs,
        }

    def get_album_detail(self, album_mid: str) -> dict | None:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/album",
            params={"mid": album_mid},
            timeout=15,
        )
        data = response.json()
        if data.get("code") != 0:
            return None
        album = data.get("data", {})
        basic_info = album.get("basicInfo", {})
        songs = [normalize_song_item(item.get("songInfo", item)) for item in album.get("songList", [])]
        return {
            "title": basic_info.get("albumName", album.get("name", "")),
            "description": basic_info.get("desc", ""),
            "songs": songs,
        }

    def get_playlist_detail(self, playlist_id: str) -> dict | None:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/playlist",
            params={"id": playlist_id},
            timeout=15,
        )
        data = response.json()
        if data.get("code") != 0:
            return None
        playlist = data.get("data", {})
        dirinfo = playlist.get("dirinfo", {})
        songs = [normalize_song_item(item) for item in playlist.get("songlist", [])]
        return {
            "title": dirinfo.get("title", playlist.get("name", "")),
            "description": dirinfo.get("desc", playlist.get("description", "")),
            "songs": songs,
        }

    def get_hotkeys(self) -> list[dict]:
        response = self._context.http.get(f"{self.REMOTE_BASE_URL}/hotkey", timeout=10)
        data = response.json()
        if data.get("code") != 0:
            return []
        items = data.get("data", {}).get("vec_hotkey", []) or data.get("data", {}).get("vecHotkey", [])
        return [
            {
                "title": item.get("title", ""),
                "query": item.get("query", item.get("title", "")),
            }
            for item in items
            if item.get("title")
        ]

    def complete(self, keyword: str) -> list[dict]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/search/smartbox",
            params={"key": keyword},
            timeout=10,
        )
        data = response.json()
        if data.get("code") != 0:
            return []
        items = data.get("data", {}).get("itemlist", []) or data.get("data", {}).get("items", [])
        results = []
        for item in items:
            hint = item.get("name") or item.get("hint") or item.get("title")
            if hint:
                results.append({"hint": hint})
        return results

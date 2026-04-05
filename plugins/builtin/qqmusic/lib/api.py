from __future__ import annotations

from typing import Optional


class QQMusicPluginAPI:
    REMOTE_BASE_URL = "https://api.ygking.top/api"

    def __init__(self, context):
        self._context = context

    def search(self, keyword: str, limit: int = 5) -> list[dict]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/search",
            params={"keyword": keyword, "type": "song", "num": limit, "page": 1},
            timeout=10,
        )
        data = response.json()
        songs = data.get("data", {}).get("list", [])
        formatted = []
        for song in songs[:limit]:
            singer_info = song.get("singer", "")
            if isinstance(singer_info, list) and singer_info:
                singer_name = singer_info[0].get("name", "")
                singer_mid = singer_info[0].get("mid", "")
            elif isinstance(singer_info, dict):
                singer_name = singer_info.get("name", "")
                singer_mid = singer_info.get("mid", "")
            else:
                singer_name = str(singer_info) if singer_info else ""
                singer_mid = ""

            album_info = song.get("album", "")
            if isinstance(album_info, dict):
                album_name = album_info.get("name", "")
                album_mid = album_info.get("mid", "")
            else:
                album_name = str(album_info) if album_info else ""
                album_mid = song.get("album_mid", "")

            formatted.append(
                {
                    "mid": song.get("mid", "") or song.get("songmid", ""),
                    "name": song.get("name", "") or song.get("songname", ""),
                    "title": song.get("name", "") or song.get("songname", ""),
                    "singer": singer_name,
                    "singer_mid": singer_mid,
                    "album": album_name,
                    "album_mid": album_mid,
                    "interval": song.get("interval", 0),
                }
            )
        return formatted

    def search_artist(self, keyword: str, limit: int = 5) -> list[dict]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/search",
            params={"keyword": keyword, "type": "singer", "num": limit, "page": 1},
            timeout=10,
        )
        data = response.json()
        return data.get("data", {}).get("list", [])

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
            return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{album_mid}.jpg"
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
        return f"https://y.gtimg.cn/music/photo_new/T001R{size}x{size}M000{singer_mid}.jpg"

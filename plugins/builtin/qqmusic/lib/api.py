from __future__ import annotations

from typing import Optional


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
    ) -> dict[str, list[dict]]:
        response = self._context.http.get(
            f"{self.REMOTE_BASE_URL}/search",
            params={"keyword": keyword, "type": search_type, "num": limit, "page": page},
            timeout=10,
        )
        data = response.json()
        items = data.get("data", {}).get("list", [])
        if search_type == "song":
            return {"tracks": [self._format_song_item(song) for song in items[:limit]]}
        if search_type == "singer":
            return {
                "artists": [
                    {
                        "mid": item.get("singerMID", item.get("mid", "")),
                        "name": item.get("singerName", item.get("name", "")),
                        "avatar_url": item.get("singerPic", item.get("avatar", item.get("cover_url", "")))
                        or self.get_artist_cover_url(item.get("singerMID", item.get("mid", ""))),
                        "song_count": item.get("songNum", item.get("song_count", item.get("songnum", 0))),
                        "album_count": item.get("albumNum", item.get("album_count", item.get("albumnum", 0))),
                        "fan_count": item.get("fansNum", item.get("fan_count", item.get("FanNum", 0))),
                    }
                    for item in items[:limit]
                ]
            }
        if search_type == "album":
            return {
                "albums": [
                    {
                        "mid": item.get("albummid", item.get("mid", "")),
                        "name": item.get("name", item.get("albumname", "")),
                        "singer_name": self._extract_singer_name(item),
                        "cover_url": item.get("pic", item.get("cover", item.get("cover_url", "")))
                        or self.get_cover_url(album_mid=item.get("albummid", item.get("mid", ""))),
                        "song_count": item.get("song_num", item.get("song_count", 0)),
                        "publish_date": item.get("publish_date", item.get("pubTime", "")),
                    }
                    for item in items[:limit]
                ]
            }
        return {
            "playlists": [
                {
                    "id": str(item.get("dissid", item.get("id", ""))),
                    "mid": item.get("dissMID", item.get("mid", "")),
                    "title": item.get("dissname", item.get("title", "")),
                    "creator": item.get("nickname", item.get("creator", "")),
                    "cover_url": item.get("logo", item.get("imgurl", item.get("cover_url", item.get("cover", "")))),
                    "song_count": item.get("songnum", item.get("song_count", 0)),
                    "play_count": item.get("listennum", item.get("play_count", 0)),
                }
                for item in items[:limit]
            ]
        }

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
        return [self._format_song_item(song) for song in items[:limit]]

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

    def get_playback_url_info(self, track_id: str, quality: str) -> dict[str, str] | None:
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
        songs = [self._format_song_item(item.get("songInfo", item)) for item in album.get("songList", [])]
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
        songs = [self._format_song_item(item) for item in playlist.get("songlist", [])]
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

    def _format_song_item(self, song: dict) -> dict:
        singer_info = song.get("singer", "")
        if isinstance(singer_info, list) and singer_info:
            singer_name = ", ".join(item.get("name", "") for item in singer_info if item.get("name"))
        elif isinstance(singer_info, dict):
            singer_name = singer_info.get("name", "")
        else:
            singer_name = str(song.get("singerName", singer_info or ""))

        album_info = song.get("album", {})
        if isinstance(album_info, dict):
            album_name = album_info.get("name", "") or song.get("albumName", "")
            album_mid = album_info.get("mid", "") or song.get("albumMid", "")
        else:
            album_name = str(album_info or song.get("albumName", ""))
            album_mid = song.get("albumMid", "")

        return {
            "mid": song.get("mid", "") or song.get("songmid", "") or song.get("songMid", ""),
            "name": song.get("name", "") or song.get("songname", "") or song.get("title", ""),
            "title": song.get("name", "") or song.get("songname", "") or song.get("title", ""),
            "artist": singer_name,
            "singer": singer_name,
            "album": album_name,
            "album_mid": album_mid,
            "duration": song.get("interval", 0) or song.get("duration", 0),
        }

    def _extract_singer_name(self, item: dict) -> str:
        singer_list = item.get("singer_list", [])
        if singer_list and isinstance(singer_list, list):
            return ", ".join(entry.get("name", "") for entry in singer_list if entry.get("name"))
        return item.get("singer", "")

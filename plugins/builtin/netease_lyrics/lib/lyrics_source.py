from __future__ import annotations

import logging

from harmony_plugin_api.lyrics import PluginLyricsResult
from plugins.builtin.netease_shared.common import netease_headers

logger = logging.getLogger(__name__)


class NetEaseLyricsPluginSource:
    source_id = "netease"
    display_name = "NetEase"
    name = "NetEase"

    def __init__(self, http_client) -> None:
        self._http_client = http_client

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10,
    ) -> list[PluginLyricsResult]:
        response = self._http_client.get(
            "https://music.163.com/api/search/get/web",
            params={"s": f"{artist} {title}", "type": "1", "limit": str(limit)},
            headers=netease_headers(),
            timeout=3,
        )
        if response.status_code != 200:
            return []

        payload = response.json()
        if payload.get("code") != 200:
            return []

        results: list[PluginLyricsResult] = []
        for song in payload.get("result", {}).get("songs", []):
            album = song.get("album") or {}
            cover_url = album.get("picUrl")
            if not cover_url and album.get("pic"):
                pic = str(album.get("pic"))
                cover_url = f"https://p1.music.126.net/{pic}/{pic}.jpg"

            results.append(
                PluginLyricsResult(
                    song_id=str(song["id"]),
                    title=song.get("name", ""),
                    artist=song["artists"][0]["name"] if song.get("artists") else "",
                    album=album.get("name", ""),
                    duration=(song.get("duration") / 1000) if song.get("duration") else None,
                    source="netease",
                    cover_url=cover_url,
                    supports_yrc=True,
                )
            )
        return results

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        try:
            response = self._http_client.get(
                f"https://music.163.com/api/song/lyric?id={result.song_id}&lv=1&kv=0&tv=0&yv=0",
                headers=netease_headers(),
                timeout=3,
            )
            if response.status_code == 200:
                payload = response.json()
                if payload.get("code") == 200:
                    yrc = payload.get("yrc", {}).get("lyric")
                    if yrc:
                        return yrc
                    lrc = payload.get("lrc", {}).get("lyric")
                    if lrc:
                        return lrc

            fallback = self._http_client.get(
                f"https://music.163.com/api/song/lyric?id={result.song_id}&lv=1&kv=1&tv=-1",
                headers=netease_headers(),
                timeout=3,
            )
            if fallback.status_code != 200:
                return None

            payload = fallback.json()
            if payload.get("code") != 200:
                return None

            return payload.get("lrc", {}).get("lyric") or payload.get("lyric")
        except Exception:
            logger.exception("Error downloading NetEase lyrics")
            return None

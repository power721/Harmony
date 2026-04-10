from __future__ import annotations

import logging

from harmony_plugin_api.lyrics import PluginLyricsResult

logger = logging.getLogger(__name__)


class LRCLIBPluginSource:
    source_id = "lrclib"
    display_name = "LRCLIB"
    name = "LRCLIB"

    def __init__(self, http_client) -> None:
        self._http_client = http_client

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10,
    ) -> list[PluginLyricsResult]:
        logger.debug(f"LRCLIB lyrics search: {title} by {artist}")
        response = self._http_client.get(
            "https://lrclib.net/api/search",
            params={"track_name": title, "artist_name": artist},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3,
        )
        payload = response.json() if response.status_code == 200 else []
        if not isinstance(payload, list):
            return []
        return [
            PluginLyricsResult(
                song_id=str(item.get("id", "")),
                title=item.get("trackName", ""),
                artist=item.get("artistName", ""),
                album=item.get("albumName", ""),
                duration=item.get("duration"),
                source="lrclib",
                lyrics=item.get("syncedLyrics") or item.get("plainLyrics"),
            )
            for item in payload[:limit]
            if item.get("syncedLyrics") or item.get("plainLyrics")
        ]

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        return result.lyrics

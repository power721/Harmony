from __future__ import annotations

import base64
import logging
import zlib

from harmony_plugin_api.lyrics import PluginLyricsResult

logger = logging.getLogger(__name__)


class KugouLyricsPluginSource:
    source_id = "kugou"
    display_name = "Kugou"
    name = "Kugou"

    def __init__(self, http_client) -> None:
        self._http_client = http_client

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        keyword = f"{title} {artist}".strip()
        response = self._http_client.get(
            "https://lyrics.kugou.com/search",
            params={"keyword": keyword, "page": 1, "pagesize": limit},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=3,
        )
        payload = response.json()
        return [
            PluginLyricsResult(
                song_id=str(item["id"]),
                title=item.get("name", item.get("song", "")),
                artist=item.get("singer", ""),
                source="kugou",
                accesskey=item.get("accesskey", ""),
            )
            for item in payload.get("candidates", [])
        ]

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        try:
            response = self._http_client.get(
                "https://lyrics.kugou.com/download",
                params={
                    "id": result.song_id,
                    "accesskey": result.accesskey,
                    "fmt": "krc",
                    "charset": "utf8",
                },
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=5,
            )
            payload = response.json()
            content = payload.get("content")
            if not content:
                return None
            krc = base64.b64decode(content)
            if krc[:4] == b"krc1":
                krc = krc[4:]
            return zlib.decompress(krc).decode("utf-8", errors="ignore")
        except Exception:
            logger.exception("Error downloading Kugou lyrics")
            return None

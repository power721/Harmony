from __future__ import annotations

import re

from harmony_plugin_api.cover import PluginArtistCoverResult


class QQMusicArtistCoverPluginSource:
    source_id = "qqmusic-artist-cover"
    display_name = "QQMusic Artist"
    name = "QQMusic"

    def __init__(self, context):
        self._context = context

    def _convert_cover_url(self, url: str, size: int = 500) -> str:
        match = re.search(r"(T\d{3})R\d+x\d+M000([A-Za-z0-9]+)", url)
        if not match:
            return url
        return (
            f"https://y.gtimg.cn/music/photo_new/"
            f"{match.group(1)}R{size}x{size}M000{match.group(2)}.jpg"
        )

    def search(self, artist_name: str, limit: int = 10) -> list[PluginArtistCoverResult]:
        try:
            from services.lyrics.qqmusic_lyrics import QQMusicClient

            client = QQMusicClient()
            artists = client.search_artist(artist_name, limit)
            results = []
            for artist in artists:
                name = artist.get("singerName", "")
                singer_mid = artist.get("singerMID", "")
                cover_url = artist.get("singerPic", "")
                album_count = artist.get("albumNum", 0)
                if name and singer_mid:
                    results.append(
                        PluginArtistCoverResult(
                            artist_id=singer_mid,
                            name=name,
                            source="qqmusic",
                            cover_url=self._convert_cover_url(cover_url) if cover_url else None,
                            album_count=album_count,
                        )
                    )
            return results
        except Exception:
            return []

    def is_available(self) -> bool:
        return True

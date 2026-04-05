from __future__ import annotations


class QQMusicArtistCoverPluginSource:
    source_id = "qqmusic-artist-cover"
    display_name = "QQMusic Artist"

    def __init__(self, context):
        self._context = context

    def search(self, artist_name: str, limit: int = 10) -> list:
        return []

from __future__ import annotations


class QQMusicCoverPluginSource:
    source_id = "qqmusic-cover"
    display_name = "QQMusic"

    def __init__(self, context):
        self._context = context

    def search(self, title: str, artist: str, album: str = "", duration: float | None = None) -> list:
        return []

from __future__ import annotations

from harmony_plugin_api.lyrics import PluginLyricsResult


class QQMusicLyricsPluginSource:
    source_id = "qqmusic"
    display_name = "QQMusic"

    def __init__(self, context):
        self._context = context

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        return []

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        return None

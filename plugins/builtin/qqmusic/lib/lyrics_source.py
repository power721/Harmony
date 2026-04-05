from __future__ import annotations

from harmony_plugin_api.lyrics import PluginLyricsResult

from .api import QQMusicPluginAPI


class QQMusicLyricsPluginSource:
    source_id = "qqmusic"
    display_name = "QQMusic"
    name = "QQMusic"

    def __init__(self, context):
        self._context = context
        self._api = QQMusicPluginAPI(context)

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        try:
            keyword = f"{title} {artist}" if artist else title
            search_results = self._api.search(keyword, limit)
            return [
                PluginLyricsResult(
                    song_id=item.get("mid", ""),
                    title=item.get("title", ""),
                    artist=item.get("singer", ""),
                    album=item.get("album", ""),
                    duration=item.get("interval"),
                    source="qqmusic",
                    cover_url=self._api.get_cover_url(
                        mid=item.get("mid", ""),
                        album_mid=item.get("album_mid", ""),
                        size=500,
                    ),
                )
                for item in search_results
            ]
        except Exception:
            return []

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        try:
            return self._api.get_lyrics(result.song_id)
        except Exception:
            return None

    def is_available(self) -> bool:
        return True

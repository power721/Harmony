from __future__ import annotations

from harmony_plugin_api.lyrics import PluginLyricsResult


class QQMusicLyricsPluginSource:
    source_id = "qqmusic"
    display_name = "QQMusic"
    name = "QQMusic"

    def __init__(self, context):
        self._context = context

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        try:
            from services.lyrics.qqmusic_lyrics import search_from_qqmusic

            search_results = search_from_qqmusic(title, artist, limit)
            return [
                PluginLyricsResult(
                    song_id=item.get("id", ""),
                    title=item.get("title", ""),
                    artist=item.get("artist", ""),
                    album=item.get("album", ""),
                    duration=item.get("duration"),
                    source="qqmusic",
                    cover_url=item.get("cover_url"),
                )
                for item in search_results
            ]
        except Exception:
            return []

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        try:
            from services.lyrics.qqmusic_lyrics import download_qqmusic_lyrics

            return download_qqmusic_lyrics(result.song_id)
        except Exception:
            return None

    def is_available(self) -> bool:
        return True

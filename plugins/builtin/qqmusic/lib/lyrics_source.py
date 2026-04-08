from __future__ import annotations

from harmony_plugin_api.lyrics import PluginLyricsResult

from .provider import QQMusicOnlineProvider


class QQMusicLyricsPluginSource:
    source_id = "qqmusic"
    display_name = "QQMusic"
    name = "QQMusic"

    def __init__(self, context):
        self._context = context
        self._provider = QQMusicOnlineProvider(context)

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        try:
            keyword = f"{title} {artist}" if artist else title
            search_payload = self._provider.search(
                keyword,
                search_type="song",
                page=1,
                page_size=limit,
            )
            search_results = (
                search_payload.get("tracks", [])
                if isinstance(search_payload, dict)
                else search_payload
            )
            return [
                PluginLyricsResult(
                    song_id=item.get("mid", ""),
                    title=item.get("title", "") or item.get("name", ""),
                    artist=item.get("artist", "") or item.get("singer", ""),
                    album=item.get("album", ""),
                    duration=item.get("duration") or item.get("interval"),
                    source="qqmusic",
                    cover_url=self._provider.get_cover_url(
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
            return self._provider.get_lyrics(result.song_id)
        except Exception:
            return None

    def get_lyrics_by_song_id(self, song_id: str) -> str | None:
        return self.get_lyrics(
            PluginLyricsResult(song_id=song_id, title="", artist="", source="qqmusic")
        )

    def is_available(self) -> bool:
        return True

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
            search_payload = self._api.search(
                keyword,
                search_type="song",
                limit=limit,
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
                    artist=item.get("singer", "") or item.get("artist", ""),
                    album=(
                        item.get("album", {}).get("name", "")
                        if isinstance(item.get("album"), dict)
                        else item.get("album", "")
                    ),
                    duration=item.get("duration") or item.get("interval"),
                    source="qqmusic",
                    cover_url=self._api.get_cover_url(
                        mid=item.get("mid", ""),
                        album_mid=(
                            item.get("album_mid", "")
                            or (
                                item.get("album", {}).get("mid", "")
                                if isinstance(item.get("album"), dict)
                                else ""
                            )
                        ),
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

    def get_lyrics_by_song_id(self, song_id: str) -> str | None:
        return self.get_lyrics(
            PluginLyricsResult(song_id=song_id, title="", artist="", source="qqmusic")
        )

    def is_available(self) -> bool:
        return True

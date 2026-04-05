from __future__ import annotations

from harmony_plugin_api.cover import PluginCoverResult


class QQMusicCoverPluginSource:
    source_id = "qqmusic-cover"
    display_name = "QQMusic"
    name = "QQMusic"

    def __init__(self, context):
        self._context = context

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: float | None = None,
    ) -> list[PluginCoverResult]:
        try:
            from services.lyrics.qqmusic_lyrics import QQMusicClient

            client = QQMusicClient()
            keyword = f"{artist} {title}" if artist else title
            songs = client.search(keyword, limit=5)
            results = []
            for song in songs:
                artist_name = ""
                if isinstance(song.get("singer"), list) and song["singer"]:
                    artist_name = song["singer"][0].get("name", "")

                album_name = ""
                album_mid = ""
                album_data = song.get("album")
                if isinstance(album_data, dict):
                    album_name = album_data.get("name", "")
                    album_mid = album_data.get("mid", "")

                results.append(
                    PluginCoverResult(
                        item_id=song.get("mid", ""),
                        title=song.get("name", ""),
                        artist=artist_name,
                        album=album_name,
                        duration=song.get("interval"),
                        source="qqmusic",
                        cover_url=None,
                        extra_id=album_mid,
                    )
                )
            return results
        except Exception:
            return []

    def is_available(self) -> bool:
        return True

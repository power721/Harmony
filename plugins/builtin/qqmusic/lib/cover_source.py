from __future__ import annotations

from harmony_plugin_api.cover import PluginCoverResult

from .api import QQMusicPluginAPI


class QQMusicCoverPluginSource:
    source = "qqmusic"
    source_id = "qqmusic-cover"
    display_name = "QQMusic"
    name = "QQMusic"

    def __init__(self, context):
        self._context = context
        self._api = QQMusicPluginAPI(context)

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: float | None = None,
    ) -> list[PluginCoverResult]:
        try:
            keyword = f"{artist} {title}" if artist else title
            search_payload = self._api.search(
                keyword,
                search_type="song",
                limit=5,
            )
            songs = (
                search_payload.get("tracks", [])
                if isinstance(search_payload, dict)
                else search_payload
            )
            results = []
            for song in songs:
                artist_name = song.get("artist", "")
                singer_data = song.get("singer")
                if not artist_name:
                    if isinstance(singer_data, list) and singer_data:
                        artist_name = singer_data[0].get("name", "")
                    elif isinstance(singer_data, str):
                        artist_name = singer_data

                album_data = song.get("album")
                if isinstance(album_data, dict):
                    album_name = album_data.get("name", "")
                    album_mid = album_data.get("mid", "")
                else:
                    album_name = album_data or ""
                    album_mid = song.get("album_mid", "")

                results.append(
                    PluginCoverResult(
                        item_id=song.get("mid", ""),
                        title=song.get("name", "") or song.get("title", ""),
                        artist=artist_name,
                        album=album_name,
                        duration=song.get("duration") or song.get("interval"),
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

    def get_cover_url(
        self,
        mid: str = None,
        album_mid: str = None,
        size: int = 500,
    ):
        return self._api.get_cover_url(mid=mid, album_mid=album_mid, size=size)

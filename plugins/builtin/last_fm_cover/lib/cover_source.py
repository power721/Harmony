from __future__ import annotations

import logging
import os

from harmony_plugin_api.cover import PluginCoverResult

logger = logging.getLogger(__name__)


class LastFmCoverPluginSource:
    source = "lastfm"
    source_id = "lastfm-cover"
    display_name = "Last.fm"
    name = "Last.fm"
    _DEFAULT_API_KEY = "9b0cdcf446cc96dea3e747787ad23575"

    def __init__(self, http_client):
        self._http_client = http_client

    def _get_api_key(self) -> str:
        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key or api_key == "YOUR_LASTFM_API_KEY":
            return self._DEFAULT_API_KEY
        return api_key

    def is_available(self) -> bool:
        return True

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: float | None = None,
    ) -> list[PluginCoverResult]:
        results: list[PluginCoverResult] = []

        try:
            response = self._http_client.get(
                "http://ws.audioscrobbler.com/2.0/",
                params={
                    "method": "album.getinfo",
                    "api_key": self._get_api_key(),
                    "artist": artist,
                    "album": album or title,
                    "format": "json",
                },
                timeout=5,
            )

            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    logger.debug("Last.fm API error: %s", data.get("message"))
                    return results

                album_info = data.get("album")
                if album_info:
                    image_url = None
                    for image in reversed(album_info.get("image", [])):
                        if image.get("#text"):
                            image_url = image["#text"]
                            break

                    if image_url:
                        results.append(
                            PluginCoverResult(
                                item_id=album_info.get("mbid", ""),
                                title=album_info.get("name", ""),
                                artist=album_info.get("artist", ""),
                                album=album_info.get("name", ""),
                                source="lastfm",
                                cover_url=image_url,
                            )
                        )

        except Exception as exc:
            logger.debug("Last.fm search error: %s", exc)

        return results

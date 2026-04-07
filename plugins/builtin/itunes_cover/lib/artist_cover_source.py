from __future__ import annotations

import logging

from harmony_plugin_api.cover import PluginArtistCoverResult

logger = logging.getLogger(__name__)


class ITunesArtistCoverPluginSource:
    source = "itunes"
    source_id = "itunes-artist-cover"
    display_name = "iTunes Artist"
    name = "iTunes"

    def __init__(self, http_client):
        self._http_client = http_client

    def search(
        self,
        artist_name: str,
        limit: int = 10,
    ) -> list[PluginArtistCoverResult]:
        results: list[PluginArtistCoverResult] = []

        try:
            search_url = "https://itunes.apple.com/search"
            params = {
                "term": artist_name,
                "media": "music",
                "entity": "album",
                "limit": limit,
            }
            logger.debug("iTunes artist cover search: %s", artist_name)
            response = self._http_client.get(search_url, params=params, timeout=5)

            if response.status_code == 200:
                data = response.json()
                seen_artists: set[str] = set()
                for item in data.get("results", []):
                    name = item.get("artistName", "")
                    normalized_name = name.lower()
                    if not name or normalized_name in seen_artists:
                        continue
                    seen_artists.add(normalized_name)

                    artwork_url = item.get("artworkUrl100")
                    if not artwork_url:
                        continue

                    results.append(
                        PluginArtistCoverResult(
                            artist_id=str(item.get("artistId", "")),
                            name=name,
                            source="itunes",
                            cover_url=artwork_url.replace("100x100", "600x600"),
                            album_count=None,
                        )
                    )

        except Exception as exc:
            logger.debug("iTunes artist cover search error: %s", exc)

        return results

    def is_available(self) -> bool:
        return True

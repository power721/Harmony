from __future__ import annotations

import logging

from harmony_plugin_api.cover import PluginCoverResult

logger = logging.getLogger(__name__)


class ITunesCoverPluginSource:
    source = "itunes"
    source_id = "itunes-cover"
    display_name = "iTunes"
    name = "iTunes"

    def __init__(self, http_client):
        self._http_client = http_client

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: float | None = None,
    ) -> list[PluginCoverResult]:
        results: list[PluginCoverResult] = []

        try:
            search_url = "https://itunes.apple.com/search"

            params = {
                "term": f"{artist} {album or title}",
                "media": "music",
                "entity": "album",
                "limit": 5,
            }
            response = self._http_client.get(search_url, params=params, timeout=3)

            if response.status_code == 200:
                data = response.json()
                results.extend(self._build_results(data.get("results", [])))

            if album:
                params_album_only = {
                    "term": album,
                    "media": "music",
                    "entity": "album",
                    "limit": 5,
                }
                response = self._http_client.get(
                    search_url,
                    params=params_album_only,
                    timeout=3,
                )

                if response.status_code == 200:
                    data = response.json()
                    results.extend(self._build_results(data.get("results", [])))

        except Exception as exc:
            logger.debug("iTunes search error: %s", exc)

        return results

    def is_available(self) -> bool:
        return True

    def _build_results(self, items: list[dict]) -> list[PluginCoverResult]:
        results: list[PluginCoverResult] = []
        for item in items:
            artwork_url = item.get("artworkUrl100")
            if not artwork_url:
                continue
            results.append(
                PluginCoverResult(
                    item_id=str(item.get("collectionId", "")),
                    title=item.get("collectionName", ""),
                    artist=item.get("artistName", ""),
                    album=item.get("collectionName", ""),
                    source="itunes",
                    cover_url=artwork_url.replace("100x100", "600x600"),
                )
            )
        return results

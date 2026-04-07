from __future__ import annotations

import logging

from harmony_plugin_api.cover import PluginArtistCoverResult
from plugins.builtin.netease_shared.common import (
    build_netease_image_url,
    netease_headers,
)

logger = logging.getLogger(__name__)


class NetEaseArtistCoverPluginSource:
    source = "netease"
    source_id = "netease-artist-cover"
    display_name = "NetEase"
    name = "NetEase"

    def __init__(self, http_client):
        self._http_client = http_client

    def search(
        self,
        artist_name: str,
        limit: int = 10,
    ) -> list[PluginArtistCoverResult]:
        try:
            response = self._http_client.get(
                "https://music.163.com/api/search/get/web",
                params={"s": artist_name, "type": 100, "limit": limit, "offset": 0},
                headers=netease_headers(),
                timeout=5,
            )
            if response.status_code != 200:
                return []

            payload = response.json()
            if payload.get("code") != 200:
                return []

            results: list[PluginArtistCoverResult] = []
            for item in payload.get("result", {}).get("artists", []):
                cover_url = build_netease_image_url(
                    item.get("picUrl") or item.get("img1v1Url"),
                    "512y512",
                )
                if not cover_url:
                    continue
                results.append(
                    PluginArtistCoverResult(
                        artist_id=str(item.get("id", "")),
                        name=item.get("name", ""),
                        source="netease",
                        cover_url=cover_url,
                        album_count=item.get("albumSize", 0),
                    )
                )
            return results
        except Exception as exc:
            logger.debug("NetEase artist cover search error: %s", exc)
            return []

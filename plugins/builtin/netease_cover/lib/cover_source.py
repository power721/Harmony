from __future__ import annotations

import logging

from harmony_plugin_api.cover import PluginCoverResult
from plugins.builtin.netease_shared.common import (
    build_netease_image_url,
    netease_headers,
)

logger = logging.getLogger(__name__)


class NetEaseCoverPluginSource:
    source = "netease"
    source_id = "netease-cover"
    display_name = "NetEase"
    name = "NetEase"

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
            album_response = self._http_client.get(
                "https://music.163.com/api/search/get/web",
                params={"s": f"{artist} {album or title}", "type": 10, "limit": 5},
                headers=netease_headers(),
                timeout=5,
            )
            if album_response.status_code == 200:
                payload = album_response.json()
                if payload.get("code") == 200:
                    for item in payload.get("result", {}).get("albums", []):
                        cover_url = build_netease_image_url(
                            item.get("picUrl") or item.get("blurPicUrl"),
                            "500y500",
                        )
                        if not cover_url:
                            continue
                        results.append(
                            PluginCoverResult(
                                item_id=str(item.get("id", "")),
                                title=item.get("name", ""),
                                artist=item.get("artist", {}).get("name", ""),
                                album=item.get("name", ""),
                                source="netease",
                                cover_url=cover_url,
                            )
                        )

            song_response = self._http_client.get(
                "https://music.163.com/api/search/get/web",
                params={"s": f"{artist} {title}", "type": 1, "limit": 5},
                headers=netease_headers(),
                timeout=5,
            )
            if song_response.status_code == 200:
                payload = song_response.json()
                if payload.get("code") == 200:
                    for song in payload.get("result", {}).get("songs", []):
                        album_info = song.get("album", {})
                        cover_url = build_netease_image_url(
                            album_info.get("picUrl") or album_info.get("blurPicUrl"),
                            "500y500",
                        )
                        if not cover_url:
                            continue
                        results.append(
                            PluginCoverResult(
                                item_id=str(song.get("id", "")),
                                title=song.get("name", ""),
                                artist=song["artists"][0]["name"] if song.get("artists") else "",
                                album=album_info.get("name", ""),
                                duration=(song.get("duration") / 1000) if song.get("duration") else None,
                                source="netease",
                                cover_url=cover_url,
                            )
                        )
        except Exception as exc:
            logger.debug("NetEase cover search error: %s", exc)
            return []

        return results

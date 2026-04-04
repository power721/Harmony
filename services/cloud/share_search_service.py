"""Share search service for network disk links."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from infrastructure.network import HttpClient


@dataclass
class ShareSong:
    """Single search song item from share API."""

    id: str = ""
    title: str = ""
    artist: str = ""
    name: str = ""
    link0: str = ""
    link1: str = ""
    link2: str = ""
    created_time: str = ""
    scraped_at: str = ""

    @property
    def quark_link(self) -> Optional[str]:
        for link in (self.link0, self.link1, self.link2):
            if link and "pan.quark.cn/s/" in link:
                return link
        return None

    @property
    def has_quark_link(self) -> bool:
        return self.quark_link is not None


@dataclass
class ShareSearchResult:
    """Search response container."""

    limit: int = 20
    page: int = 1
    total: int = 0
    total_pages: int = 0
    songs: List[ShareSong] = None

    def __post_init__(self):
        if self.songs is None:
            self.songs = []


class ShareSearchService:
    """Service for querying shared cloud music links."""

    BASE_URL = "https://music.har01d.cn/api/search"
    _http_client = HttpClient.shared()

    @classmethod
    def search(cls, query: str, page: int = 1, limit: int = 20, timeout: int = 10) -> ShareSearchResult:
        params = {
            "q": query,
            "page": page,
            "limit": limit,
        }

        try:
            response = cls._http_client.get(cls.BASE_URL, params=params, timeout=timeout)
            if response.status_code != 200:
                return ShareSearchResult(limit=limit, page=page)

            payload = response.json() or {}
            songs = []
            for raw in payload.get("songs", []) or []:
                songs.append(
                    ShareSong(
                        id=str(raw.get("id", "")),
                        title=raw.get("title", "") or "",
                        artist=raw.get("artist", "") or "",
                        name=raw.get("name", "") or "",
                        link0=raw.get("link0", "") or "",
                        link1=raw.get("link1", "") or "",
                        link2=raw.get("link2", "") or "",
                        created_time=raw.get("createdTime", "") or "",
                        scraped_at=raw.get("scrapedAt", "") or "",
                    )
                )

            return ShareSearchResult(
                limit=int(payload.get("limit", limit) or limit),
                page=int(payload.get("page", page) or page),
                total=int(payload.get("total", 0) or 0),
                total_pages=int(payload.get("totalPages", 0) or 0),
                songs=songs,
            )
        except Exception:
            return ShareSearchResult(limit=limit, page=page)

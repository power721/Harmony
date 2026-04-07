from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PluginCoverResult:
    item_id: str
    title: str
    artist: str
    album: str = ""
    duration: float | None = None
    source: str = ""
    cover_url: str | None = None
    extra_id: str | None = None


@dataclass(frozen=True)
class PluginArtistCoverResult:
    artist_id: str
    name: str
    source: str = ""
    cover_url: str | None = None
    album_count: int | None = None


class PluginCoverSource(Protocol):
    source_id: str
    display_name: str

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: float | None = None,
    ) -> list[PluginCoverResult]:
        ...


class PluginArtistCoverSource(Protocol):
    source_id: str
    display_name: str

    def search(
        self,
        artist_name: str,
        limit: int = 10,
    ) -> list[PluginArtistCoverResult]:
        ...

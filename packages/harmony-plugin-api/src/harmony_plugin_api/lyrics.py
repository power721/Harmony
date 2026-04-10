from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PluginLyricsResult:
    id: str
    title: str
    artist: str
    album: str = ""
    duration: float | None = None
    source: str = ""
    cover_url: str | None = None
    lyrics: str | None = None
    accesskey: str | None = None
    supports_yrc: bool = False

    @property
    def song_id(self) -> str:
        """Backward-compatible alias for pre-id plugin implementations."""
        return self.id


class PluginLyricsSource(Protocol):
    source_id: str
    display_name: str

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10,
    ) -> list[PluginLyricsResult]:
        ...

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        ...

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PluginTrack:
    track_id: str
    title: str
    artist: str
    album: str = ""
    duration: int | None = None
    artwork_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PluginPlaybackRequest:
    provider_id: str
    track_id: str
    title: str
    quality: str
    metadata: dict[str, Any]

from __future__ import annotations

from typing import Any


def _iter_sources(kind: str):
    from app.bootstrap import Bootstrap

    registry = Bootstrap.instance().plugin_manager.registry
    if kind == "artist":
        return registry.artist_cover_sources()
    return registry.cover_sources()


def _matches_provider(source: Any, provider_id: str) -> bool:
    normalized = (provider_id or "").strip().lower()
    if not normalized:
        return False
    return (
        getattr(source, "source", None) == normalized
        or getattr(source, "name", "").lower() == normalized
        or getattr(source, "display_name", "").lower() == normalized
    )


def get_online_cover_url(
    provider_id: str | None,
    track_id: str | None = None,
    album_id: str | None = None,
    size: int = 500,
):
    for source in _iter_sources("cover"):
        if provider_id and not _matches_provider(source, provider_id):
            continue
        if hasattr(source, "get_cover_url"):
            return source.get_cover_url(mid=track_id, album_mid=album_id, size=size)
    return None


def get_online_artist_cover_url(provider_id: str | None, artist_id: str, size: int = 300):
    for source in _iter_sources("artist"):
        if provider_id and not _matches_provider(source, provider_id):
            continue
        if hasattr(source, "get_artist_cover_url"):
            return source.get_artist_cover_url(artist_id, size=size)
    return None

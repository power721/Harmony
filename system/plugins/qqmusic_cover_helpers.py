from __future__ import annotations


def _iter_sources(kind: str):
    from app.bootstrap import Bootstrap

    registry = Bootstrap.instance().plugin_manager.registry
    if kind == "artist":
        return registry.artist_cover_sources()
    return registry.cover_sources()


def _matches_qqmusic(source) -> bool:
    return (
        getattr(source, "source", None) == "qqmusic"
        or getattr(source, "name", "").lower() == "qqmusic"
        or getattr(source, "display_name", "").lower() == "qqmusic"
    )


def get_qqmusic_cover_url(mid: str = None, album_mid: str = None, size: int = 500):
    for source in _iter_sources("cover"):
        if _matches_qqmusic(source) and hasattr(source, "get_cover_url"):
            return source.get_cover_url(mid=mid, album_mid=album_mid, size=size)
    return None


def get_qqmusic_artist_cover_url(singer_mid: str, size: int = 300):
    for source in _iter_sources("artist"):
        if _matches_qqmusic(source) and hasattr(source, "get_artist_cover_url"):
            return source.get_artist_cover_url(singer_mid, size=size)
    return None

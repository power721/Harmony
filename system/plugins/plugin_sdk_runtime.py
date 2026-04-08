from __future__ import annotations

from typing import Any


class IconName:
    GRID = "grid.svg"
    LIST = "list.svg"


def event_bus():
    from system.event_bus import EventBus

    return EventBus.instance()


def get_host_icon(name, color, size: int = 16):
    from ui.icons import get_icon as _get_icon

    return _get_icon(name, color, size)


def get_icon(name, color, size: int = 16):
    return get_host_icon(name, color, size)


def image_cache_get(url: str):
    from infrastructure.cache import ImageCache

    return ImageCache.get(url)


def image_cache_set(url: str, image_data: bytes):
    from infrastructure.cache import ImageCache

    return ImageCache.set(url, image_data)


def image_cache_path(url: str):
    from infrastructure.cache import ImageCache

    return ImageCache._get_cache_path(url)


def http_get_content(url: str, *, timeout: int, headers: dict[str, str] | None = None):
    from infrastructure.network import HttpClient

    return HttpClient().get_content(url, timeout=timeout, headers=headers)


def cover_pixmap_cache_initialize() -> None:
    from infrastructure.cache.pixmap_cache import CoverPixmapCache

    CoverPixmapCache.initialize()


def cover_pixmap_cache_get(cache_key: str):
    from infrastructure.cache.pixmap_cache import CoverPixmapCache

    return CoverPixmapCache.get(cache_key)


def cover_pixmap_cache_set(cache_key: str, pixmap) -> None:
    from infrastructure.cache.pixmap_cache import CoverPixmapCache

    CoverPixmapCache.set(cache_key, pixmap)


def bootstrap():
    from app.bootstrap import Bootstrap

    return Bootstrap.instance()


def library_service():
    instance = bootstrap()
    return getattr(instance, "library_service", None) if instance else None


def favorites_service():
    instance = bootstrap()
    return getattr(instance, "favorites_service", None) if instance else None


def favorite_mids_from_library() -> set[str]:
    instance = bootstrap()
    if not instance or not getattr(instance, "favorites_service", None) or not getattr(instance, "library_service", None):
        return set()
    favorite_ids = instance.favorites_service.get_all_favorite_track_ids()
    if not isinstance(favorite_ids, (set, list, tuple)) or not favorite_ids:
        return set()
    tracks = instance.library_service.get_tracks_by_ids(list(favorite_ids))
    if not isinstance(tracks, list):
        return set()
    mids: set[str] = set()
    for track in tracks:
        cloud_file_id = getattr(track, "cloud_file_id", None)
        if cloud_file_id:
            mids.add(str(cloud_file_id))
    return mids


def remove_library_favorite_by_mid(mid: str) -> bool:
    instance = bootstrap()
    if not instance or not getattr(instance, "favorites_service", None) or not getattr(instance, "library_service", None):
        return False
    library_track = instance.library_service.get_track_by_cloud_file_id(mid)
    if library_track:
        instance.favorites_service.remove_favorite(track_id=library_track.id)
        return True
    instance.favorites_service.remove_favorite(cloud_file_id=mid)
    return True


def add_requests_to_favorites(requests: list[Any]) -> list[int]:
    instance = bootstrap()
    if not instance or not getattr(instance, "library_service", None) or not getattr(instance, "favorites_service", None):
        return []
    track_ids: list[int] = []
    for request in requests:
        track_id = instance.library_service.add_online_track(
            request.provider_id,
            request.track_id,
            request.metadata.get("title", request.title),
            request.metadata.get("artist", ""),
            request.metadata.get("album", ""),
            float(request.metadata.get("duration", 0.0) or 0.0),
            request.metadata.get("cover_url"),
        )
        if track_id:
            instance.favorites_service.add_favorite(track_id=track_id)
            track_ids.append(track_id)
    return track_ids


def add_requests_to_playlist(parent, requests: list[Any], log_prefix: str) -> list[int]:
    from utils.playlist_utils import add_tracks_to_playlist

    instance = bootstrap()
    if not instance or not getattr(instance, "library_service", None):
        return []

    track_ids: list[int] = []
    for request in requests:
        track_id = instance.library_service.add_online_track(
            request.provider_id,
            request.track_id,
            request.metadata.get("title", request.title),
            request.metadata.get("artist", ""),
            request.metadata.get("album", ""),
            float(request.metadata.get("duration", 0.0) or 0.0),
            request.metadata.get("cover_url"),
        )
        if track_id:
            track_ids.append(track_id)

    if track_ids:
        add_tracks_to_playlist(parent, instance.library_service, track_ids, log_prefix)
    return track_ids


def add_track_ids_to_playlist(parent, track_ids: list[int], log_prefix: str) -> None:
    from utils.playlist_utils import add_tracks_to_playlist

    instance = bootstrap()
    if not instance or not getattr(instance, "library_service", None) or not track_ids:
        return
    add_tracks_to_playlist(parent, instance.library_service, track_ids, log_prefix)

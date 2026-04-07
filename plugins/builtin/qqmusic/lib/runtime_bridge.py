from __future__ import annotations

import importlib
from typing import Any


def _runtime_module():
    return importlib.import_module("system.plugins.plugin_sdk_runtime")


def _ui_module():
    return importlib.import_module("system.plugins.plugin_sdk_ui")


def register_themed_widget(widget) -> None:
    _ui_module().register_themed_widget(widget)


def get_qss(template: str) -> str:
    return _ui_module().get_qss(template)


def current_theme():
    return _ui_module().current_theme()


def show_information(parent, title: str, message: str) -> None:
    _ui_module().information(parent, title, message)


def show_warning(parent, title: str, message: str) -> None:
    _ui_module().warning(parent, title, message)


def create_online_music_service(*, config_manager=None, credential_provider=None):
    return _runtime_module().create_online_music_service(
        config_manager=config_manager,
        credential_provider=credential_provider,
    )


def create_online_download_service(*, config_manager=None, credential_provider=None, online_music_service=None):
    return _runtime_module().create_online_download_service(
        config_manager=config_manager,
        credential_provider=credential_provider,
        online_music_service=online_music_service,
    )


def get_icon(name, color, size: int = 16):
    return _runtime_module().get_icon(name, color, size)


class IconName:
    GRID = "grid.svg"
    LIST = "list.svg"


def image_cache_get(url: str):
    return _runtime_module().image_cache_get(url)


def image_cache_set(url: str, image_data: bytes):
    return _runtime_module().image_cache_set(url, image_data)


def image_cache_path(url: str):
    return _runtime_module().image_cache_path(url)


def http_get_content(url: str, *, timeout: int, headers: dict[str, str] | None = None):
    return _runtime_module().http_get_content(url, timeout=timeout, headers=headers)


def cover_pixmap_cache_initialize() -> None:
    _runtime_module().cover_pixmap_cache_initialize()


def cover_pixmap_cache_get(cache_key: str):
    return _runtime_module().cover_pixmap_cache_get(cache_key)


def cover_pixmap_cache_set(cache_key: str, pixmap) -> None:
    _runtime_module().cover_pixmap_cache_set(cache_key, pixmap)


def bootstrap():
    return _runtime_module().bootstrap()


def library_service():
    return _runtime_module().library_service()


def favorites_service():
    return _runtime_module().favorites_service()


def favorite_mids_from_library() -> set[str]:
    return _runtime_module().favorite_mids_from_library()


def remove_library_favorite_by_mid(mid: str) -> bool:
    return _runtime_module().remove_library_favorite_by_mid(mid)


def add_requests_to_favorites(requests: list[Any]) -> list[int]:
    return _runtime_module().add_requests_to_favorites(requests)


def add_requests_to_playlist(parent, requests: list[Any], log_prefix: str) -> list[int]:
    return _runtime_module().add_requests_to_playlist(parent, requests, log_prefix)


def add_track_ids_to_playlist(parent, track_ids: list[int], log_prefix: str) -> None:
    _runtime_module().add_track_ids_to_playlist(parent, track_ids, log_prefix)


def event_bus():
    return _runtime_module().event_bus()


def create_qqmusic_service(credential):
    from .legacy.qqmusic_service import QQMusicService

    return QQMusicService(credential)


def create_qqmusic_login_dialog(context=None, parent=None):
    from .login_dialog import QQMusicLoginDialog

    return QQMusicLoginDialog(context, parent)


def format_duration(seconds: Any) -> str:
    try:
        total_seconds = int(float(seconds or 0))
    except (TypeError, ValueError):
        total_seconds = 0
    minutes, seconds_part = divmod(max(total_seconds, 0), 60)
    hours, minutes_part = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes_part:02d}:{seconds_part:02d}"
    return f"{minutes:d}:{seconds_part:02d}"

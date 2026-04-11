from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtGui import QIcon

from plugins.builtin.qqmusic.lib.runtime_bridge import bind_context
from system.theme import ThemeManager


class _Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _ThemeBridge:
    def __init__(self, theme_manager=None):
        self._theme_manager = theme_manager

    def _manager(self):
        return self._theme_manager or ThemeManager.instance()

    def register_widget(self, widget) -> None:
        manager = self._manager()
        if hasattr(manager, "register_widget"):
            manager.register_widget(widget)

    def get_qss(self, template: str) -> str:
        manager = self._manager()
        if hasattr(manager, "get_qss"):
            return manager.get_qss(template)
        return template

    def current_theme(self):
        theme = getattr(self._manager(), "current_theme", None)
        if theme is None:
            return None
        if hasattr(theme, "background") or hasattr(theme, "text"):
            return theme
        return theme() if callable(theme) else theme

    def get_popup_surface_style(self) -> str:
        manager = self._manager()
        getter = getattr(manager, "get_themed_popup_surface_style", None)
        if callable(getter):
            value = getter()
            return value if isinstance(value, str) else ""
        return ""

    def get_completer_popup_style(self) -> str:
        manager = self._manager()
        getter = getattr(manager, "get_themed_completer_popup_style", None)
        if callable(getter):
            value = getter()
            return value if isinstance(value, str) else ""
        return ""


class _DialogBridge:
    def information(self, *_args, **_kwargs):
        return None

    def warning(self, *_args, **_kwargs):
        return None

    def question(self, *_args, **_kwargs):
        return None

    def critical(self, *_args, **_kwargs):
        return None

    def show_cover_preview(self, *_args, **_kwargs):
        return None

    def setup_title_bar(self, *_args, **_kwargs):
        return None


class _SettingsBridge:
    def __init__(self):
        self._values = {}

    def get(self, key, default=None):
        return self._values.get(key, default)

    def set(self, key, value):
        self._values[key] = value


class _RuntimeBridge:
    def __init__(
        self,
        *,
        online_service=None,
        download_service=None,
        event_bus=None,
        bootstrap=None,
    ) -> None:
        self._online_service = online_service or SimpleNamespace(
            _has_qqmusic_credential=lambda: False
        )
        self._download_service = download_service or Mock()
        self._event_bus = event_bus or SimpleNamespace(
            language_changed=_Signal(),
            favorite_changed=_Signal(),
        )
        self._bootstrap = bootstrap

    def create_online_music_service(self, **_kwargs):
        return self._online_service

    def create_online_download_service(self, **_kwargs):
        return self._download_service

    def get_icon(self, *_args, **_kwargs):
        return QIcon()

    def image_cache_get(self, _url: str):
        return None

    def image_cache_set(self, _url: str, _image_data: bytes):
        return None

    def image_cache_path(self, _url: str):
        return None

    def http_get_content(self, _url: str, **_kwargs):
        return None

    def cover_pixmap_cache_initialize(self) -> None:
        return None

    def cover_pixmap_cache_get(self, _cache_key: str):
        return None

    def cover_pixmap_cache_set(self, _cache_key: str, _pixmap) -> None:
        return None

    def bootstrap(self):
        return self._bootstrap

    def library_service(self):
        return getattr(self._bootstrap, "library_service", None) if self._bootstrap else None

    def favorites_service(self):
        return getattr(self._bootstrap, "favorites_service", None) if self._bootstrap else None

    def favorite_mids_from_library(self) -> set[str]:
        return set()

    def remove_library_favorite_by_mid(self, _mid: str) -> bool:
        return False

    def add_requests_to_favorites(self, _requests):
        return []

    def add_requests_to_playlist(self, _parent, _requests, _log_prefix: str):
        return []

    def add_track_ids_to_playlist(self, _parent, _track_ids, _log_prefix: str) -> None:
        return None

    def event_bus(self):
        return self._event_bus


def bind_test_context(
    *,
    theme_manager=None,
    online_service=None,
    download_service=None,
    event_bus=None,
    bootstrap=None,
    language: str = "zh",
):
    context = SimpleNamespace(
        ui=SimpleNamespace(
            theme=_ThemeBridge(theme_manager),
            dialogs=_DialogBridge(),
        ),
        settings=_SettingsBridge(),
        runtime=_RuntimeBridge(
            online_service=online_service,
            download_service=download_service,
            event_bus=event_bus,
            bootstrap=bootstrap,
        ),
        events=SimpleNamespace(language_changed=_Signal()),
        language=language,
    )
    bind_context(context)
    return context

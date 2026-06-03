from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal

from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec

from .lib.artist_cover_source import QQMusicArtistCoverPluginSource
from .lib.cover_source import QQMusicCoverPluginSource
from .lib.i18n import get_language, set_language, t
from .lib.lyrics_source import QQMusicLyricsPluginSource
from .lib.provider import QQMusicOnlineProvider
from .lib.runtime_bridge import bind_context, clear_context, event_bus
from .lib.settings_tab import QQMusicSettingsTab

logger = logging.getLogger(__name__)
_SIDEBAR_ICON_PATH = str(Path(__file__).resolve().parent / "sidebar_icon.svg")


class _AutoRefreshThread(QThread):
    """Background thread to refresh QQ Music credential."""
    refreshed = Signal(bool, object)

    def __init__(self, credential: dict, http_client=None, parent=None):
        super().__init__(parent)
        self._credential = credential
        self._http_client = http_client
        self._updated = None

    def run(self):
        try:
            from .lib.qqmusic_client import QQMusicClient

            client = QQMusicClient(self._credential, http_client=self._http_client)
            updated = client.refresh_credential()
            if updated:
                self._updated = updated
                self.refreshed.emit(True, updated)
            else:
                self.refreshed.emit(False, None)
        except Exception as exc:
            logger.warning("Auto-refresh token failed: %s", exc)
            self.refreshed.emit(False, None)


class QQMusicPlugin:
    plugin_id = "qqmusic"

    def __init__(self):
        self._context = None
        self._refresh_timer: QTimer | None = None
        self._refresh_thread: _AutoRefreshThread | None = None

    def register(self, context) -> None:
        bind_context(context)
        self._context = context
        plugin_logger = getattr(context, "logger", None)
        if plugin_logger is None or not hasattr(plugin_logger, "info"):
            plugin_logger = logger

        # Sync initial language from app context
        app_lang = getattr(context, "language", None) or ""
        if app_lang and app_lang != get_language():
            set_language(app_lang)

        # Listen for language changes to update titles
        events = getattr(context, "events", None)
        if events is not None and hasattr(events, "language_changed"):
            events.language_changed.connect(self._on_language_changed)

        def _localized_title() -> str:
            return t("qqmusic_page_title", "QQ音乐")

        plugin_logger.info("[QQMusic] Registering plugin capabilities")
        context.ui.register_sidebar_entry(
            SidebarEntrySpec(
                plugin_id="qqmusic",
                entry_id="qqmusic.sidebar",
                title=_localized_title(),
                order=80,
                icon_name=None,
                icon_path=_SIDEBAR_ICON_PATH,
                page_factory=lambda _context, parent: QQMusicOnlineProvider(context).create_page(context, parent),
                title_provider=_localized_title,
            )
        )
        context.ui.register_settings_tab(
            SettingsTabSpec(
                plugin_id="qqmusic",
                tab_id="qqmusic.settings",
                title=_localized_title(),
                order=80,
                widget_factory=lambda _context, parent: QQMusicSettingsTab(context, parent),
                title_provider=_localized_title,
            )
        )
        context.services.register_lyrics_source(QQMusicLyricsPluginSource(context))
        context.services.register_cover_source(QQMusicCoverPluginSource(context))
        context.services.register_artist_cover_source(
            QQMusicArtistCoverPluginSource(context)
        )
        context.services.register_online_music_provider(QQMusicOnlineProvider(context))

        # Start hourly auto-refresh timer
        self._start_auto_refresh(context)

        plugin_logger.info("[QQMusic] Plugin registration completed")

    @staticmethod
    def _on_language_changed(language: str) -> None:
        """Handle language change from app."""
        if language and language != get_language():
            set_language(language)

    def unregister(self, context) -> None:
        if self._refresh_timer:
            self._refresh_timer.stop()
            self._refresh_timer = None
        if self._refresh_thread:
            self._refresh_thread.quit()
            self._refresh_thread.wait()
            self._refresh_thread = None
        clear_context(context)
        getattr(context, "logger", logger).info("[QQMusic] Plugin unregistered")
        return None

    def _start_auto_refresh(self, context) -> None:
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._auto_refresh_token)
        self._refresh_timer.start(60 * 60 * 1000)  # every 1 hour

    def _auto_refresh_token(self) -> None:
        if not self._context:
            return
        credential = self._context.settings.get("credential", None)
        if not credential:
            return
        if not credential.get("refresh_key") or not credential.get("refresh_token"):
            return

        logger.info("[QQMusic] Auto-refreshing token...")

        if self._refresh_thread:
            self._refresh_thread.quit()
            self._refresh_thread.wait()

        self._refresh_thread = _AutoRefreshThread(
            credential,
            http_client=self._context.http if hasattr(self._context, "http") else None,
        )
        self._refresh_thread.refreshed.connect(self._on_auto_refreshed)
        self._refresh_thread.start()

    def _on_auto_refreshed(self, success: bool, updated: object) -> None:
        if success and updated and isinstance(updated, dict):
            self._context.settings.set("credential", updated)
            nick = str(self._context.settings.get("nick", "") or "")
            event_bus().emit_qqmusic_auth_change("qqmusic", updated, nick)
            logger.info("[QQMusic] Auto-refresh token succeeded")
        else:
            logger.warning("[QQMusic] Auto-refresh token failed")

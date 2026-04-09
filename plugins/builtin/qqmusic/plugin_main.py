from __future__ import annotations

import logging
from pathlib import Path

from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec

from .lib.artist_cover_source import QQMusicArtistCoverPluginSource
from .lib.cover_source import QQMusicCoverPluginSource
from .lib.i18n import get_language, set_language, t
from .lib.lyrics_source import QQMusicLyricsPluginSource
from .lib.provider import QQMusicOnlineProvider
from .lib.runtime_bridge import bind_context, clear_context
from .lib.settings_tab import QQMusicSettingsTab

logger = logging.getLogger(__name__)
_SIDEBAR_ICON_PATH = str(Path(__file__).resolve().parent / "qq_music_logo.svg")


class QQMusicPlugin:
    plugin_id = "qqmusic"

    def register(self, context) -> None:
        bind_context(context)
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
        plugin_logger.info("[QQMusic] Plugin registration completed")

    @staticmethod
    def _on_language_changed(language: str) -> None:
        """Handle language change from app."""
        if language and language != get_language():
            set_language(language)

    def unregister(self, context) -> None:
        clear_context(context)
        getattr(context, "logger", logger).info("[QQMusic] Plugin unregistered")
        return None

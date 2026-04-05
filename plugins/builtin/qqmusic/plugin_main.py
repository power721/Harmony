from __future__ import annotations

from harmony_plugin_api.registry_types import SettingsTabSpec, SidebarEntrySpec

from .lib.artist_cover_source import QQMusicArtistCoverPluginSource
from .lib.cover_source import QQMusicCoverPluginSource
from .lib.lyrics_source import QQMusicLyricsPluginSource
from .lib.provider import QQMusicOnlineProvider
from .lib.settings_tab import QQMusicSettingsTab


class QQMusicPlugin:
    plugin_id = "qqmusic"

    def register(self, context) -> None:
        context.ui.register_sidebar_entry(
            SidebarEntrySpec(
                plugin_id="qqmusic",
                entry_id="qqmusic.sidebar",
                title="QQ 音乐",
                order=80,
                icon_name="GLOBE",
                page_factory=lambda _context, parent: QQMusicOnlineProvider(context).create_page(context, parent),
            )
        )
        context.ui.register_settings_tab(
            SettingsTabSpec(
                plugin_id="qqmusic",
                tab_id="qqmusic.settings",
                title="QQ 音乐",
                order=80,
                widget_factory=lambda _context, parent: QQMusicSettingsTab(context, parent),
            )
        )
        context.services.register_lyrics_source(QQMusicLyricsPluginSource(context))
        context.services.register_cover_source(QQMusicCoverPluginSource(context))
        context.services.register_artist_cover_source(
            QQMusicArtistCoverPluginSource(context)
        )
        context.services.register_online_music_provider(QQMusicOnlineProvider(context))

    def unregister(self, context) -> None:
        return None

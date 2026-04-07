from __future__ import annotations

from .lib.lyrics_source import NetEaseLyricsPluginSource


class NetEaseLyricsPlugin:
    plugin_id = "netease_lyrics"

    def register(self, context) -> None:
        context.services.register_lyrics_source(NetEaseLyricsPluginSource(context.http))

    def unregister(self, context) -> None:
        return None

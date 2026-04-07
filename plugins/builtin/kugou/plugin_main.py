from __future__ import annotations

from .lib.lyrics_source import KugouLyricsPluginSource


class KugouLyricsPlugin:
    plugin_id = "kuogo_lyrics"

    def register(self, context) -> None:
        context.services.register_lyrics_source(KugouLyricsPluginSource(context.http))

    def unregister(self, context) -> None:
        return None

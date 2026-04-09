from __future__ import annotations

from .lib.lrclib_source import LRCLIBPluginSource


class LRCLIBPlugin:
    plugin_id = "lrclib"

    def register(self, context) -> None:
        context.services.register_lyrics_source(LRCLIBPluginSource(context.http))

    def unregister(self, context) -> None:
        return None

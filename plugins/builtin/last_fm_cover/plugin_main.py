from __future__ import annotations

from .lib.cover_source import LastFmCoverPluginSource


class LastFmCoverPlugin:
    plugin_id = "last_fm_cover"

    def register(self, context) -> None:
        context.services.register_cover_source(LastFmCoverPluginSource(context.http))

    def unregister(self, context) -> None:
        return None

from __future__ import annotations

from .lib.artist_cover_source import NetEaseArtistCoverPluginSource
from .lib.cover_source import NetEaseCoverPluginSource


class NetEaseCoverPlugin:
    plugin_id = "netease_cover"

    def register(self, context) -> None:
        context.services.register_cover_source(NetEaseCoverPluginSource(context.http))
        context.services.register_artist_cover_source(
            NetEaseArtistCoverPluginSource(context.http)
        )

    def unregister(self, context) -> None:
        return None

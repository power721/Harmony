from __future__ import annotations

from .lib.artist_cover_source import ITunesArtistCoverPluginSource
from .lib.cover_source import ITunesCoverPluginSource


class ITunesCoverPlugin:
    plugin_id = "itunes_cover"

    def register(self, context) -> None:
        context.services.register_cover_source(ITunesCoverPluginSource(context.http))
        context.services.register_artist_cover_source(
            ITunesArtistCoverPluginSource(context.http)
        )

    def unregister(self, context) -> None:
        return None

from __future__ import annotations

from harmony_plugin_api.media import PluginPlaybackRequest


class PluginMediaBridge:
    """Host bridge for plugin-triggered cache/download/library actions."""

    def __init__(self, download_service, playback_service, library_service) -> None:
        self._download_service = download_service
        self._playback_service = playback_service
        self._library_service = library_service

    def cache_remote_track(
        self,
        request: PluginPlaybackRequest,
        progress_callback=None,
        force: bool = False,
    ):
        return self._download_service.download(
            request.track_id,
            song_title=request.title,
            quality=request.quality,
            progress_callback=progress_callback,
            force=force,
        )

    def add_online_track(self, request: PluginPlaybackRequest):
        metadata = request.metadata
        return self._library_service.add_online_track(
            request.track_id,
            metadata.get("title", request.title),
            metadata.get("artist", ""),
            metadata.get("album", ""),
            float(metadata.get("duration", 0.0) or 0.0),
            metadata.get("cover_url"),
        )

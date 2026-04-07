from __future__ import annotations

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from harmony_plugin_api.media import PluginPlaybackRequest


class PluginMediaBridge:
    """Host bridge for plugin-triggered cache/download/library/queue actions."""

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

    def play_online_track(self, request: PluginPlaybackRequest) -> int | None:
        track_id = self.add_online_track(request)
        item = self._build_playlist_item(request, track_id)
        self._playback_service.engine.load_playlist_items([item])
        self._playback_service.engine.play()
        self._playback_service.save_queue()
        return track_id

    def add_online_track_to_queue(self, request: PluginPlaybackRequest) -> int | None:
        track_id = self.add_online_track(request)
        item = self._build_playlist_item(request, track_id)
        self._playback_service.engine.add_track(item)
        self._playback_service._schedule_save_queue()
        return track_id

    def insert_online_track_to_queue(self, request: PluginPlaybackRequest) -> int | None:
        track_id = self.add_online_track(request)
        item = self._build_playlist_item(request, track_id)
        current_index = self._playback_service.engine.current_index
        insert_index = current_index + 1 if current_index >= 0 else 0
        self._playback_service.engine.insert_track(insert_index, item)
        self._playback_service._schedule_save_queue()
        return track_id

    def _build_playlist_item(
        self,
        request: PluginPlaybackRequest,
        track_id: int | None,
    ) -> PlaylistItem:
        metadata = request.metadata
        local_path = ""
        needs_download = True
        if self._download_service and self._download_service.is_cached(request.track_id):
            local_path = self._download_service.get_cached_path(request.track_id)
            needs_download = False
        return PlaylistItem(
            track_id=track_id,
            source=TrackSource.QQ,
            local_path=local_path,
            title=metadata.get("title", request.title),
            artist=metadata.get("artist", ""),
            album=metadata.get("album", ""),
            duration=float(metadata.get("duration", 0.0) or 0.0),
            cover_path=metadata.get("cover_url"),
            cloud_file_id=request.track_id,
            needs_download=needs_download,
            needs_metadata=False,
        )

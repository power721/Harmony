"""
Online music handler for MainWindow.

Handles online track playback and queue management.
"""

import logging
from typing import List, Tuple, TYPE_CHECKING

from PySide6.QtCore import QObject

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from system.i18n import t

if TYPE_CHECKING:
    from services.playback import PlaybackService
    from services.online import OnlineDownloadService

logger = logging.getLogger(__name__)


class OnlineMusicHandler(QObject):
    """
    Handler for online music operations.

    Manages:
    - Playing online tracks
    - Adding/inserting tracks to queue
    - Batch operations
    """

    def __init__(
            self,
            playback_service: "PlaybackService",
            status_callback=None,
            parent=None
    ):
        """
        Initialize the handler.

        Args:
            playback_service: Playback service for queue management
            status_callback: Callback for status messages (message: str)
            parent: Parent QObject
        """
        super().__init__(parent)
        self._playback = playback_service
        self._status_callback = status_callback
        self._download_service: "OnlineDownloadService" = None

    def set_download_service(self, service: "OnlineDownloadService"):
        """Set the download service for cache checking."""
        self._download_service = service

    def _show_status(self, message: str):
        """Show status message."""
        if self._status_callback:
            self._status_callback(message)

    def play_online_track(self, song_mid: str, local_path: str, metadata: dict = None):
        """
        Play a downloaded online track.

        Args:
            song_mid: Song MID
            local_path: Local file path
            metadata: Optional metadata dict
        """
        if not local_path:
            logger.error("No local path for online track")
            return

        title = metadata.get("title", "Online Track") if metadata else "Online Track"
        artist = metadata.get("artist", "") if metadata else ""
        album = metadata.get("album", "") if metadata else ""
        duration = metadata.get("duration", 0.0) if metadata else 0.0
        cover_url = metadata.get("cover_url", "") if metadata else ""

        # Create track record in database first
        from app.bootstrap import Bootstrap
        track_id = Bootstrap.instance().library_service.add_online_track(
            song_mid=song_mid,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_url=cover_url
        )

        item = PlaylistItem(
            track_id=track_id,
            source=TrackSource.QQ,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,
            needs_download=False
        )

        self._playback.engine.load_playlist_items([item])
        self._playback.engine.play()

    def add_to_queue(self, song_mid: str, metadata: dict):
        """
        Add online track to the play queue.

        Args:
            song_mid: Song MID
            metadata: Metadata dict
        """
        title = metadata.get("title", "Online Track")
        artist = metadata.get("artist", "")
        album = metadata.get("album", "")
        duration = metadata.get("duration", 0.0)
        cover_url = metadata.get("cover_url", "")

        # Create track record in database first
        from app.bootstrap import Bootstrap
        track_id = Bootstrap.instance().library_service.add_online_track(
            song_mid=song_mid,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_url=cover_url
        )

        local_path = ""
        needs_download = True

        if self._download_service and self._download_service.is_cached(song_mid):
            local_path = self._download_service.get_cached_path(song_mid)
            needs_download = False

        item = PlaylistItem(
            track_id=track_id,
            source=TrackSource.QQ,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,
            needs_download=needs_download
        )

        self._playback.engine.add_track(item)
        self._playback._schedule_save_queue()

        self._show_status(f"✓ {t('added_to_queue')}: {title}")

    def insert_to_queue(self, song_mid: str, metadata: dict):
        """
        Insert online track after current playing track.

        Args:
            song_mid: Song MID
            metadata: Metadata dict
        """
        title = metadata.get("title", "Online Track")
        artist = metadata.get("artist", "")
        album = metadata.get("album", "")
        duration = metadata.get("duration", 0.0)
        cover_url = metadata.get("cover_url", "")

        # Create track record in database first
        from app.bootstrap import Bootstrap
        track_id = Bootstrap.instance().library_service.add_online_track(
            song_mid=song_mid,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_url=cover_url
        )

        local_path = ""
        needs_download = True

        if self._download_service and self._download_service.is_cached(song_mid):
            local_path = self._download_service.get_cached_path(song_mid)
            needs_download = False

        item = PlaylistItem(
            track_id=track_id,
            source=TrackSource.QQ,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,
            needs_download=needs_download
        )

        current_index = self._playback.engine.current_index
        insert_index = current_index + 1 if current_index >= 0 else 0
        self._playback.engine.insert_track(insert_index, item)

        self._playback._schedule_save_queue()
        self._show_status(f"✓ {t('insert_to_queue')}: {title}")

    def add_multiple_to_queue(self, tracks_data: List[Tuple[str, dict]]):
        """
        Add multiple online tracks to the queue.

        Args:
            tracks_data: List of (song_mid, metadata) tuples
        """
        for song_mid, metadata in tracks_data:
            title = metadata.get("title", "Online Track")
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            duration = metadata.get("duration", 0.0)
            cover_url = metadata.get("cover_url", "")

            # Create track record in database first
            from app.bootstrap import Bootstrap
            track_id = Bootstrap.instance().library_service.add_online_track(
                song_mid=song_mid,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cover_url=cover_url
            )

            local_path = ""
            needs_download = True

            if self._download_service and self._download_service.is_cached(song_mid):
                local_path = self._download_service.get_cached_path(song_mid)
                needs_download = False

            item = PlaylistItem(
                track_id=track_id,
                source=TrackSource.QQ,
                local_path=local_path,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cloud_file_id=song_mid,
                needs_download=needs_download
            )

            self._playback.engine.add_track(item)

        self._playback.save_queue()

        count = len(tracks_data)
        s = "s" if count > 1 else ""
        msg = t("added_to_queue").replace("{count}", str(count)).replace("{s}", s)
        self._show_status(msg)

    def insert_multiple_to_queue(self, tracks_data: List[Tuple[str, dict]]):
        """
        Insert multiple online tracks after current playing track.

        Args:
            tracks_data: List of (song_mid, metadata) tuples
        """
        current_index = self._playback.engine.current_index
        insert_index = current_index + 1 if current_index >= 0 else 0

        for i, (song_mid, metadata) in enumerate(tracks_data):
            title = metadata.get("title", "Online Track")
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            duration = metadata.get("duration", 0.0)
            cover_url = metadata.get("cover_url", "")

            # Create track record in database first
            from app.bootstrap import Bootstrap
            track_id = Bootstrap.instance().library_service.add_online_track(
                song_mid=song_mid,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cover_url=cover_url
            )

            local_path = ""
            needs_download = True

            if self._download_service and self._download_service.is_cached(song_mid):
                local_path = self._download_service.get_cached_path(song_mid)
                needs_download = False

            item = PlaylistItem(
                track_id=track_id,
                source=TrackSource.QQ,
                local_path=local_path,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cloud_file_id=song_mid,
                needs_download=needs_download
            )

            self._playback.engine.insert_track(insert_index + i, item)

        self._playback.save_queue()

        count = len(tracks_data)
        self._show_status(f"✓ {t('insert_to_queue')}: {count}")

    def play_online_tracks(self, start_index: int, tracks_data: List[Tuple[str, dict]]):
        """
        Play a list of online tracks starting from a specific index.

        Args:
            start_index: Index to start playing from
            tracks_data: List of (song_mid, metadata) tuples
        """
        items = []

        for song_mid, metadata in tracks_data:
            title = metadata.get("title", "Online Track")
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            duration = metadata.get("duration", 0.0)
            cover_url = metadata.get("cover_url", "")

            # Create track record in database first
            from app.bootstrap import Bootstrap
            track_id = Bootstrap.instance().library_service.add_online_track(
                song_mid=song_mid,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cover_url=cover_url
            )

            local_path = ""
            needs_download = True

            if self._download_service and self._download_service.is_cached(song_mid):
                local_path = self._download_service.get_cached_path(song_mid)
                needs_download = False

            item = PlaylistItem(
                track_id=track_id,
                source=TrackSource.QQ,
                local_path=local_path,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cloud_file_id=song_mid,
                needs_download=needs_download
            )
            items.append(item)

        if items:
            self._playback.engine.load_playlist_items(items)
            if self._playback.engine.is_shuffle_mode() and 0 <= start_index < len(items):
                self._playback.engine.shuffle_and_play(items[start_index])
                self._playback.engine.play_at(0)
            else:
                self._playback.engine.play_at(start_index)

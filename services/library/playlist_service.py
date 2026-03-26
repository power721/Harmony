"""
Playlist service - Manages playlist operations.
"""

import logging
from typing import List, Optional

from domain.playlist import Playlist
from domain.track import Track, TrackId
from repositories.playlist_repository import SqlitePlaylistRepository
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class PlaylistService:
    """
    Service for managing playlists.

    Provides a clean API for UI components to interact with playlists
    without directly accessing the database layer.
    """

    def __init__(
        self,
        playlist_repo: SqlitePlaylistRepository,
        event_bus: EventBus = None
    ):
        """
        Initialize playlist service.

        Args:
            playlist_repo: Playlist repository for data persistence
            event_bus: Event bus for broadcasting changes
        """
        self._playlist_repo = playlist_repo
        self._event_bus = event_bus or EventBus.instance()

    def get_all_playlists(self) -> List[Playlist]:
        """
        Get all playlists.

        Returns:
            List of Playlist objects
        """
        return self._playlist_repo.get_all()

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """
        Get a playlist by ID.

        Args:
            playlist_id: Playlist ID

        Returns:
            Playlist object or None if not found
        """
        return self._playlist_repo.get_by_id(playlist_id)

    def create_playlist(self, playlist: Playlist) -> int:
        """
        Create a new playlist.

        Args:
            playlist: Playlist object with name

        Returns:
            ID of the created playlist
        """
        playlist_id = self._playlist_repo.add(playlist)
        logger.info(f"Created playlist: {playlist.name} (ID: {playlist_id})")
        return playlist_id

    def update_playlist(self, playlist: Playlist) -> bool:
        """
        Update an existing playlist.

        Args:
            playlist: Playlist object with updated data

        Returns:
            True if updated successfully
        """
        result = self._playlist_repo.update(playlist)
        if result:
            logger.info(f"Updated playlist: {playlist.name} (ID: {playlist.id})")
        return result

    def delete_playlist(self, playlist_id: int) -> bool:
        """
        Delete a playlist.

        Args:
            playlist_id: Playlist ID

        Returns:
            True if deleted successfully
        """
        result = self._playlist_repo.delete(playlist_id)
        if result:
            logger.info(f"Deleted playlist (ID: {playlist_id})")
        return result

    def get_playlist_tracks(self, playlist_id: int) -> List[Track]:
        """
        Get all tracks in a playlist.

        Args:
            playlist_id: Playlist ID

        Returns:
            List of Track objects
        """
        return self._playlist_repo.get_tracks(playlist_id)

    def add_track_to_playlist(self, playlist_id: int, track_id: TrackId) -> bool:
        """
        Add a track to a playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID

        Returns:
            True if added successfully, False if already exists
        """
        result = self._playlist_repo.add_track(playlist_id, track_id)
        if result:
            logger.debug(f"Added track {track_id} to playlist {playlist_id}")
        return result

    def remove_track_from_playlist(self, playlist_id: int, track_id: TrackId) -> bool:
        """
        Remove a track from a playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID

        Returns:
            True if removed successfully
        """
        result = self._playlist_repo.remove_track(playlist_id, track_id)
        if result:
            logger.debug(f"Removed track {track_id} from playlist {playlist_id}")
        return result

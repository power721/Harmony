"""
Library service - Manages music library operations.
"""

import logging
from pathlib import Path
from typing import List, Optional

from domain.track import Track
from domain.playlist import Playlist
from repositories.track_repository import SqliteTrackRepository
from repositories.playlist_repository import SqlitePlaylistRepository
from services.metadata.metadata_service import MetadataService
from system.event_bus import EventBus


logger = logging.getLogger(__name__)


class LibraryService:
    """
    Manages music library operations including scanning,
    track management, and playlist operations.
    """

    def __init__(
        self,
        track_repo: SqliteTrackRepository,
        playlist_repo: SqlitePlaylistRepository,
        event_bus: EventBus = None,
        cover_service: 'CoverService' = None
    ):
        self._track_repo = track_repo
        self._playlist_repo = playlist_repo
        self._event_bus = event_bus or EventBus.instance()
        self._cover_service = cover_service

    # ===== Track Operations =====

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get a track by ID."""
        return self._track_repo.get_by_id(track_id)

    def get_all_tracks(self) -> List[Track]:
        """Get all tracks in the library."""
        return self._track_repo.get_all()

    def search_tracks(self, query: str, limit: int = 100) -> List[Track]:
        """Search tracks by query."""
        return self._track_repo.search(query, limit)

    def add_track(self, track: Track) -> int:
        """Add a new track to the library."""
        track_id = self._track_repo.add(track)
        if track_id:
            self._event_bus.tracks_added.emit(1)
        return track_id

    def update_track(self, track: Track) -> bool:
        """Update an existing track."""
        return self._track_repo.update(track)

    def delete_track(self, track_id: int) -> bool:
        """Delete a track from the library."""
        return self._track_repo.delete(track_id)

    # ===== Playlist Operations =====

    def get_all_playlists(self) -> List[Playlist]:
        """Get all playlists."""
        return self._playlist_repo.get_all()

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """Get a playlist by ID."""
        return self._playlist_repo.get_by_id(playlist_id)

    def get_playlist_tracks(self, playlist_id: int) -> List[Track]:
        """Get all tracks in a playlist."""
        return self._playlist_repo.get_tracks(playlist_id)

    def create_playlist(self, name: str) -> int:
        """Create a new playlist."""
        playlist = Playlist(name=name)
        playlist_id = self._playlist_repo.add(playlist)
        if playlist_id:
            self._event_bus.playlist_created.emit(playlist_id)
        return playlist_id

    def delete_playlist(self, playlist_id: int) -> bool:
        """Delete a playlist."""
        result = self._playlist_repo.delete(playlist_id)
        if result:
            self._event_bus.playlist_deleted.emit(playlist_id)
        return result

    def add_track_to_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Add a track to a playlist."""
        result = self._playlist_repo.add_track(playlist_id, track_id)
        if result:
            self._event_bus.playlist_modified.emit(playlist_id)
        return result

    # ===== Scanning Operations =====

    def scan_directory(self, directory: str, recursive: bool = True) -> int:
        """
        Scan a directory for music files and add them to the library.

        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories

        Returns:
            Number of tracks added
        """
        supported_extensions = {'.mp3', '.flac', '.m4a', '.ogg', '.wav', '.oga'}
        added_count = 0

        path = Path(directory)
        if not path.exists():
            return 0

        if recursive:
            files = path.rglob('*')
        else:
            files = path.glob('*')

        for file_path in files:
            if file_path.suffix.lower() in supported_extensions:
                track = self._create_track_from_file(str(file_path))
                if track:
                    track_id = self._track_repo.add(track)
                    if track_id:
                        added_count += 1

        if added_count > 0:
            self._event_bus.tracks_added.emit(added_count)

        return added_count

    def _create_track_from_file(self, file_path: str) -> Optional[Track]:
        """Create a Track object from a file by extracting metadata."""
        try:
            metadata = MetadataService.extract_metadata(file_path)
            cover_path = None
            if self._cover_service:
                cover_path = self._cover_service.save_cover_from_metadata(
                    file_path,
                    metadata.get("cover")
                )

            return Track(
                path=file_path,
                title=metadata.get("title", Path(file_path).stem),
                artist=metadata.get("artist", ""),
                album=metadata.get("album", ""),
                duration=metadata.get("duration", 0.0),
                cover_path=cover_path,
            )
        except Exception as e:
            logger.error(f"Error creating track from {file_path}: {e}")
            return None

"""
Library service - Manages music library operations.
"""

import logging
from pathlib import Path
from typing import List, Optional

from domain.album import Album
from domain.artist import Artist
from domain.playlist import Playlist
from domain.track import Track, TrackSource
from repositories.playlist_repository import SqlitePlaylistRepository
from repositories.track_repository import SqliteTrackRepository
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

    # ===== Album/Artist Table Operations =====
    # NOTE: These methods are temporarily disabled. TODO: Create Album/Artist repositories

    def init_albums_artists(self):
        """Initialize album and artist tables if empty."""
        # TODO: Implement using Album/Artist repositories
        pass

    def refresh_albums_artists(self):
        """Refresh album and artist tables."""
        # TODO: Implement using Album/Artist repositories
        pass

    def rebuild_albums_artists(self) -> dict:
        """
        Rebuild albums and artists tables from tracks.

        This is useful for fixing data inconsistency issues.

        Returns:
            Dict with 'albums' and 'artists' counts
        """
        # TODO: Implement using Album/Artist repositories
        return {'albums': 0, 'artists': 0}

    # ===== Track Operations =====

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get a track by ID."""
        return self._track_repo.get_by_id(track_id)

    def get_tracks_by_ids(self, track_ids: List[int]) -> List[Track]:
        """Get multiple tracks by IDs in batch."""
        return self._track_repo.get_by_ids(track_ids)

    def get_track_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        return self._track_repo.get_by_path(path)

    def get_track_by_cloud_file_id(self, cloud_file_id: str) -> Optional[Track]:
        """Get a track by cloud file ID."""
        return self._track_repo.get_by_cloud_file_id(cloud_file_id)

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
            # TODO: Update albums and artists tables via Album/Artist repositories
        return track_id

    def add_online_track(
            self,
            song_mid: str,
            title: str,
            artist: str,
            album: str,
            duration: float,
            cover_url: str = None
    ) -> int:
        """
        Add an online track to the library.

        Creates a track record for online music (QQ Music, etc.)
        with empty path, indicating it needs to be downloaded before playback.

        Args:
            song_mid: Song MID (unique identifier from QQ Music)
            title: Track title
            artist: Artist name
            album: Album name
            duration: Duration in seconds
            cover_url: Cover image URL (optional)

        Returns:
            Track ID (existing or newly created)
        """
        # Check if already exists by cloud_file_id
        existing = self._track_repo.get_by_cloud_file_id(song_mid)
        if existing:
            logger.debug(f"[LibraryService] Online track already exists: {song_mid}")
            return existing.id

        # Create Track record with empty path
        track = Track(
            path="",  # Empty path indicates online track needs download
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_path=cover_url,
            source=TrackSource.QQ,
            cloud_file_id=song_mid
        )

        track_id = self._track_repo.add(track)
        if track_id:
            logger.info(f"[LibraryService] Added online track: {title} - {artist}")
            # TODO: Update albums and artists tables via Album/Artist repositories

        return track_id

    def update_track(self, track: Track, old_track: Track = None) -> bool:
        """
        Update an existing track.

        Args:
            track: Track with updated data
            old_track: Previous track data (optional, will be fetched if not provided)
        """
        # Get old track data if not provided
        if old_track is None and track.id:
            old_track = self._track_repo.get_by_id(track.id)

        result = self._track_repo.update(track)

        if result and old_track:
            # TODO: Update albums and artists tables via Album/Artist repositories
            pass

        return result

    def update_track_metadata(
        self,
        track_id: int,
        title: str = None,
        artist: str = None,
        album: str = None,
        cloud_file_id: str = None
    ) -> bool:
        """
        Update track metadata directly.

        This is a lightweight update that doesn't trigger album/artist recalculation.
        Used for cloud file metadata updates.

        Args:
            track_id: Track ID
            title: New title
            artist: New artist
            album: New album
            cloud_file_id: Cloud file ID to associate

        Returns:
            True if updated successfully
        """
        track = self._track_repo.get_by_id(track_id)
        if not track:
            return False

        # Update track object
        if title is not None:
            track.title = title
        if artist is not None:
            track.artist = artist
        if album is not None:
            track.album = album
        if cloud_file_id is not None:
            track.cloud_file_id = cloud_file_id

        # Use repository to update
        return self._track_repo.update(track)

    def delete_track(self, track_id: int) -> bool:
        """Delete a track from the library."""
        # Get track data before deletion
        track = self._track_repo.get_by_id(track_id)

        result = self._track_repo.delete(track_id)

        if result and track:
            # TODO: Update albums and artists tables via Album/Artist repositories
            # Emit event to notify other components (e.g., playback queue)
            self._event_bus.track_deleted.emit(track_id)

        return result

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
            # Refresh albums/artists after adding tracks
            self.refresh_albums_artists()

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

    # ===== Album Operations =====

    def get_albums(self) -> List[Album]:
        """Get all albums in the library."""
        return self._track_repo.get_albums()

    def get_album_tracks(self, album_name: str, artist: str = None) -> List[Track]:
        """Get all tracks for a specific album."""
        return self._track_repo.get_album_tracks(album_name, artist)

    # ===== Artist Operations =====

    def get_artists(self) -> List[Artist]:
        """Get all artists in the library."""
        return self._track_repo.get_artists()

    def get_artist_tracks(self, artist_name: str) -> List[Track]:
        """Get all tracks for a specific artist."""
        return self._track_repo.get_artist_tracks(artist_name)

    def get_artist_albums(self, artist_name: str) -> List[Album]:
        """Get all albums for a specific artist."""
        return self._track_repo.get_artist_albums(artist_name)

    def get_artist_by_name(self, artist_name: str) -> Optional[Artist]:
        """Get a specific artist by name."""
        return self._track_repo.get_artist_by_name(artist_name)

    def get_album_by_name(self, album_name: str, artist: str = None) -> Optional[Album]:
        """
        Get a specific album by name and optionally artist.

        Args:
            album_name: Album name
            artist: Artist name (optional, but recommended for unique identification)

        Returns:
            Album object or None if not found
        """
        return self._track_repo.get_album_by_name(album_name, artist)

    def rename_artist(self, old_name: str, new_name: str) -> dict:
        """
        Rename an artist and update all associated tracks.

        This will:
        1. Update artist metadata in all audio files
        2. Update database records
        3. Rebuild albums/artists cache tables
        4. Handle merge scenario if new_name already exists

        Args:
            old_name: Current artist name
            new_name: New artist name

        Returns:
            Dict with 'updated_tracks', 'errors', 'merged' keys
        """
        if not old_name or not new_name:
            return {'updated_tracks': 0, 'errors': ['Empty name provided'], 'merged': False}

        if old_name == new_name:
            return {'updated_tracks': 0, 'errors': ['Names are identical'], 'merged': False}

        # Check if new_name already exists (merge scenario)
        existing_artist = self._track_repo.get_artist_by_name(new_name)
        is_merge = existing_artist is not None

        # Get all tracks for the old artist
        tracks = self._track_repo.get_artist_tracks(old_name)
        if not tracks:
            return {'updated_tracks': 0, 'errors': ['Artist not found'], 'merged': False}

        updated_count = 0
        errors = []

        for track in tracks:
            try:
                # Update file metadata
                success = MetadataService.save_metadata(
                    track.path,
                    title=track.title,
                    artist=new_name,
                    album=track.album
                )

                if success:
                    # Update database
                    updated_track = Track(
                        id=track.id,
                        path=track.path,
                        title=track.title,
                        artist=new_name,
                        album=track.album,
                        duration=track.duration,
                        cover_path=track.cover_path,
                        cloud_file_id=track.cloud_file_id
                    )
                    self._track_repo.update(updated_track)

                    # Emit metadata_updated signal
                    self._event_bus.metadata_updated.emit(track.id)
                    updated_count += 1
                else:
                    errors.append(f"Failed to save metadata: {track.path}")
            except Exception as e:
                errors.append(f"Error processing {track.path}: {str(e)}")
                logger.error(f"Error renaming artist for track {track.id}: {e}")

        # TODO: Rebuild albums and artists cache tables via Album/Artist repositories
        if updated_count > 0:
            # Notify UI to refresh
            self._event_bus.tracks_added.emit(0)

        return {
            'updated_tracks': updated_count,
            'errors': errors,
            'merged': is_merge
        }

    def rename_album(self, old_name: str, artist: str, new_name: str) -> dict:
        """
        Rename an album and update all associated tracks.

        This will:
        1. Update album metadata in all audio files
        2. Update database records
        3. Rebuild albums/artists cache tables
        4. Handle merge scenario if new_name already exists for this artist

        Args:
            old_name: Current album name
            artist: Artist name (albums are identified by name + artist)
            new_name: New album name

        Returns:
            Dict with 'updated_tracks', 'errors', 'merged' keys
        """
        if not old_name or not new_name:
            return {'updated_tracks': 0, 'errors': ['Empty name provided'], 'merged': False}

        if old_name == new_name:
            return {'updated_tracks': 0, 'errors': ['Names are identical'], 'merged': False}

        # Get all tracks for this album
        tracks = self._track_repo.get_album_tracks(old_name, artist)
        if not tracks:
            return {'updated_tracks': 0, 'errors': ['Album not found'], 'merged': False}

        # Check if new_name already exists for this artist (merge scenario)
        existing_tracks = self._track_repo.get_album_tracks(new_name, artist)
        is_merge = len(existing_tracks) > 0

        updated_count = 0
        errors = []

        for track in tracks:
            try:
                # Update file metadata
                success = MetadataService.save_metadata(
                    track.path,
                    title=track.title,
                    artist=track.artist,
                    album=new_name
                )

                if success:
                    # Update database
                    updated_track = Track(
                        id=track.id,
                        path=track.path,
                        title=track.title,
                        artist=track.artist,
                        album=new_name,
                        duration=track.duration,
                        cover_path=track.cover_path,
                        cloud_file_id=track.cloud_file_id
                    )
                    self._track_repo.update(updated_track)

                    # Emit metadata_updated signal
                    self._event_bus.metadata_updated.emit(track.id)
                    updated_count += 1
                else:
                    errors.append(f"Failed to save metadata: {track.path}")
            except Exception as e:
                errors.append(f"Error processing {track.path}: {str(e)}")
                logger.error(f"Error renaming album for track {track.id}: {e}")

        # TODO: Rebuild albums and artists cache tables via Album/Artist repositories
        if updated_count > 0:
            # Notify UI to refresh
            self._event_bus.tracks_added.emit(0)

        return {
            'updated_tracks': updated_count,
            'errors': errors,
            'merged': is_merge
        }

    # ===== Cover Update Operations =====

    def update_artist_cover(self, artist_name: str, cover_path: str) -> bool:
        """
        Update cover path for an artist.

        Args:
            artist_name: Artist name
            cover_path: Path to cover image

        Returns:
            True if updated successfully
        """
        # TODO: Implement using Artist repository
        logger.warning("update_artist_cover not yet implemented without Album/Artist repositories")
        return False

    def update_album_cover(self, album_name: str, artist: str, cover_path: str) -> bool:
        """
        Update cover path for an album.

        Args:
            album_name: Album name
            artist: Artist name
            cover_path: Path to cover image

        Returns:
            True if updated successfully
        """
        # TODO: Implement using Album repository
        logger.warning("update_album_cover not yet implemented without Album/Artist repositories")
        return False

"""
Library service - Manages music library operations.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import QTimer

from domain.album import Album
from domain.artist import Artist
from domain.playlist import Playlist
from domain.track import Track, TrackSource
from repositories.playlist_repository import SqlitePlaylistRepository
from repositories.track_repository import SqliteTrackRepository
from repositories.album_repository import SqliteAlbumRepository
from repositories.artist_repository import SqliteArtistRepository
from repositories.genre_repository import SqliteGenreRepository
from services.metadata.metadata_service import MetadataService
from system.event_bus import EventBus

if TYPE_CHECKING:
    from domain.genre import Genre
    from services.metadata.cover_service import CoverService

logger = logging.getLogger(__name__)


class LibraryService:
    """
    Manages music library operations including scanning,
    track management, and playlist operations.
    """

    DEFAULT_TRACK_PAGE_SIZE = 500

    def __init__(
            self,
            track_repo: SqliteTrackRepository,
            playlist_repo: SqlitePlaylistRepository,
            album_repo: SqliteAlbumRepository,
            artist_repo: SqliteArtistRepository,
            genre_repo: SqliteGenreRepository = None,
            event_bus: EventBus = None,
            cover_service: 'CoverService' = None
    ):
        self._track_repo = track_repo
        self._playlist_repo = playlist_repo
        self._album_repo = album_repo
        self._artist_repo = artist_repo
        self._genre_repo = genre_repo
        self._event_bus = event_bus or EventBus.instance()
        self._cover_service = cover_service

        # Debounce timer for album/artist refresh
        self._refresh_timer = QTimer()
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.timeout.connect(self._do_refresh)

    # ===== Album/Artist Table Operations =====

    def init_albums_artists(self):
        """Initialize album and artist tables if empty."""
        if self._album_repo.is_empty():
            self._album_repo.refresh()
        if self._artist_repo.is_empty():
            self._artist_repo.refresh()
        if self._genre_repo:
            self._genre_repo.fix_covers()

    def rebuild_albums_artists(self) -> dict:
        """
        Rebuild albums and artists tables from tracks.

        This is useful for fixing data inconsistency issues.

        Returns:
            Dict with 'albums' and 'artists' counts
        """
        # Rebuild both tables
        albums_count = 0
        artists_count = 0

        # Get counts before rebuild
        conn = self._album_repo._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM albums")
        result = cursor.fetchone()
        albums_count = result["count"] if result else 0
        cursor.execute("SELECT COUNT(*) as count FROM artists")
        result = cursor.fetchone()
        artists_count = result["count"] if result else 0

        # Rebuild
        self._artist_repo.rebuild_with_albums()

        # Rebuild track_artists junction table
        self._track_repo.rebuild_track_artists()

        # Notify UI to refresh
        self._event_bus.tracks_added.emit(0)

        return {'albums': albums_count, 'artists': artists_count}

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

    def get_track_by_cloud_file_id(
        self,
        cloud_file_id: str,
        provider_id: str | None = None,
    ) -> Optional[Track]:
        """Get a track by cloud file ID."""
        if provider_id is None:
            return self._track_repo.get_by_cloud_file_id(cloud_file_id)
        return self._track_repo.get_by_cloud_file_id(cloud_file_id, provider_id=provider_id)

    def get_track_index_for_paths(self, paths: List[str]) -> dict[str, dict[str, int | float | None]]:
        """Get path -> {size, mtime} index for incremental scan."""
        return self._track_repo.get_index_for_paths(paths)

    def get_all_tracks(
            self,
            limit: int = DEFAULT_TRACK_PAGE_SIZE,
            offset: int = 0,
            source: TrackSource | str | None = None,
    ) -> List[Track]:
        """Get tracks in the library with optional pagination and source filtering."""
        return self._track_repo.get_all(limit=limit, offset=offset, source=source)

    def get_track_count(self, source: TrackSource | str | None = None) -> int:
        """Get total track count, optionally filtered by source."""
        return self._track_repo.get_track_count(source=source)

    def search_tracks(
            self,
            query: str,
            limit: int = 100,
            offset: int = 0,
            source: TrackSource | str | None = None,
    ) -> List[Track]:
        """Search tracks by query with optional pagination and source filtering."""
        return self._track_repo.search(query, limit=limit, offset=offset, source=source)

    def get_search_track_count(self, query: str, source: TrackSource | str | None = None) -> int:
        """Get the total count for a track search."""
        return self._track_repo.get_search_count(query, source=source)

    def add_track(self, track: Track) -> int:
        """Add a new track to the library."""
        track_id = self._track_repo.add(track)
        if track_id:
            self._event_bus.tracks_added.emit(1)
            # Refresh albums and artists cache tables
            self._refresh_albums_artist_async()
        return track_id

    def add_tracks_bulk(self, tracks: List[Track]) -> tuple[int, int]:
        """Add tracks in batch, returning (added, skipped)."""
        if not tracks:
            return 0, 0

        added = self._track_repo.batch_add(tracks)
        skipped = max(0, len(tracks) - added)
        if added:
            self._event_bus.tracks_added.emit(added)
            self._refresh_albums_artist_async()
        return added, skipped

    def _refresh_albums_artist_async(self):
        """Refresh albums and artists tables asynchronously (debounced)."""
        # Debounce: wait 500ms before actually refreshing
        # Multiple rapid calls will only trigger one refresh
        self._refresh_timer.start(500)

    def refresh_albums_artists(self, immediate: bool = False):
        """
        Refresh albums and artists tables.

        Args:
            immediate: If True, refresh immediately; otherwise debounce
        """
        if immediate:
            self._refresh_timer.stop()
            self._do_refresh()
        else:
            self._refresh_albums_artist_async()

    def _do_refresh(self):
        """Actually perform the album/artist/genre refresh."""
        self._album_repo.refresh()
        self._artist_repo.refresh()
        if self._genre_repo:
            self._genre_repo.refresh()

    def add_online_track(
            self,
            provider_id: str,
            song_mid: str,
            title: str,
            artist: str,
            album: str,
            duration: float,
            cover_url: str = None
    ) -> int:
        """
        Add an online track to the library.

        Creates a track record for online music provided by plugins
        with a virtual path, indicating it needs to be downloaded before playback.

        Args:
            provider_id: Plugin provider id
            song_mid: Provider-side track id
            title: Track title
            artist: Artist name
            album: Album name
            duration: Duration in seconds
            cover_url: Cover image URL (optional)

        Returns:
            Track ID (existing or newly created)
        """
        # Check if already exists by cloud_file_id
        existing = self._track_repo.get_by_cloud_file_id(song_mid, provider_id=provider_id)
        if existing:
            return existing.id

        # Use virtual path for online tracks (required for UNIQUE constraint on path)
        virtual_path = f"online://{provider_id}/track/{song_mid}"

        # Create Track record with virtual path
        track = Track(
            path=virtual_path,  # Virtual path for online track
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_path=cover_url,
            source=TrackSource.ONLINE,
            cloud_file_id=song_mid,
            online_provider_id=provider_id,
        )

        track_id = self._track_repo.add(track)
        if track_id:
            # logger.info(f"[LibraryService] Added online track: {title} - {artist}")
            # Refresh albums and artists cache tables
            self._refresh_albums_artist_async()

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
            # Check if album or artist changed
            album_changed = old_track.album != track.album
            artist_changed = old_track.artist != track.artist
            if album_changed or artist_changed:
                # Refresh albums and artists cache tables
                self._refresh_albums_artist_async()

        return result

    def update_track_metadata(
        self,
        track_id: int,
        title: str = None,
        artist: str = None,
        album: str = None,
        genre: str = None,
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
            genre: New genre
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
        if genre is not None:
            track.genre = genre
        if cloud_file_id is not None:
            track.cloud_file_id = cloud_file_id

        # Use repository to update
        return self._track_repo.update(track)

    def update_track_path(self, track_id: int, path: str) -> bool:
        """Update a track's file path."""
        return self._track_repo.update_path(track_id, path)

    def update_track_cover_path(self, track_id: int, cover_path: str) -> bool:
        """Update a track's cover path."""
        return self._track_repo.update_cover_path(track_id, cover_path)

    def delete_track(self, track_id: int) -> bool:
        """Delete a track from the library."""
        # Get track data before deletion
        track = self._track_repo.get_by_id(track_id)

        result = self._track_repo.delete(track_id)

        if result:
            # Deletions should update aggregate tables synchronously so the
            # library reflects the new counts immediately and after restart.
            self.refresh_albums_artists(immediate=True)
        if result and track:
            # Emit event to notify other components (e.g., playback queue)
            self._event_bus.track_deleted.emit(track_id)

        return result

    def delete_tracks(self, track_ids: List[int]) -> int:
        """
        Delete multiple tracks from the library efficiently.

        This is much faster than calling delete_track() in a loop for large batches,
        as it performs a single database transaction and only refreshes albums/artists once.

        Args:
            track_ids: List of track IDs to delete

        Returns:
            Number of tracks deleted
        """
        if not track_ids:
            return 0

        # Batch delete from database
        deleted_count = self._track_repo.delete_batch(track_ids)

        if deleted_count > 0:
            # Batch deletions also need immediate aggregate persistence.
            self.refresh_albums_artists(immediate=True)
            # Emit batch event with all deleted track IDs
            self._event_bus.tracks_deleted.emit(track_ids)

        return deleted_count

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
        supported_extensions = {'.mp3', '.flac', '.m4a', '.ogg', '.wav', '.oga', '.opus'}
        added_count = 0

        path = Path(directory)
        if not path.exists():
            return 0

        if recursive:
            files = [file_path for file_path in path.rglob('*') if file_path.suffix.lower() in supported_extensions]
        else:
            files = [file_path for file_path in path.glob('*') if file_path.suffix.lower() in supported_extensions]

        if not files:
            return 0

        max_workers = min(4, len(files))
        # Parallel metadata extraction, then batch insert in single transaction
        valid_tracks = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._create_track_from_file, str(file_path)): file_path
                for file_path in files
            }
            for future in as_completed(futures):
                track = future.result()
                if track:
                    valid_tracks.append(track)

        if valid_tracks:
            added_count = self._track_repo.batch_add(valid_tracks)

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

    def get_albums_without_cover(self) -> List[Album]:
        """Get all albums without covers."""
        return self._album_repo.get_albums_without_cover()

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

    def rebuild_track_artists(self) -> int:
        """Rebuild the track_artists junction table for all tracks."""
        return self._track_repo.rebuild_track_artists()

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

    # ===== Genre Operations =====

    def get_genres(self):
        """Get all genres in the library."""
        if self._genre_repo:
            return self._genre_repo.get_all()
        return []

    def get_genre_tracks(self, name: str) -> List[Track]:
        """Get all tracks for a specific genre."""
        if self._genre_repo:
            return self._genre_repo.get_tracks(name)
        return []

    def get_genre_by_name(self, name: str) -> Optional['Genre']:
        """Get a specific genre by name."""
        if self._genre_repo:
            return self._genre_repo.get_by_name(name)
        return None

    def fill_missing_genre_covers(self, max_tracks_per_genre: int = 10) -> int:
        """
        Fill missing genre covers by fetching online covers from sample tracks.

        Args:
            max_tracks_per_genre: Maximum number of tracks to try for each genre

        Returns:
            Number of genres successfully filled
        """
        if not self._genre_repo or not self._cover_service:
            return 0

        filled = 0
        genres = self._genre_repo.get_all()
        missing_genres = [g for g in genres if not g.cover_path]

        for genre in missing_genres:
            tracks = self._genre_repo.get_tracks(genre.name)
            if not tracks:
                continue

            for track in tracks[:max_tracks_per_genre]:
                title = track.title or ""
                artist = track.artist or ""
                album = track.album or ""
                if not title and not album:
                    continue

                cover_path = self._cover_service.fetch_online_cover(
                    title,
                    artist,
                    album,
                    track.duration
                )
                if cover_path:
                    if self._genre_repo.update_cover_path(genre.name, cover_path):
                        filled += 1
                    break

        return filled

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

        # Rebuild albums and artists cache tables via Album/Artist repositories
        if updated_count > 0:
            self._album_repo.refresh()
            self._artist_repo.refresh()
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

        # Rebuild albums and artists cache tables via Album/Artist repositories
        if updated_count > 0:
            self._album_repo.refresh()
            self._artist_repo.refresh()
            # Notify UI to refresh
            self._event_bus.tracks_added.emit(0)

        return {
            'updated_tracks': updated_count,
            'errors': errors,
            'merged': is_merge
        }

    # ===== Cover Update Operations =====

    def rename_genre(self, old_name: str, new_name: str) -> dict:
        """
        Rename a genre and update all associated tracks.

        This will:
        1. Update genre metadata in all audio files
        2. Update database records
        3. Rebuild genres cache table
        4. Handle merge scenario if new_name already exists

        Args:
            old_name: Current genre name
            new_name: New genre name

        Returns:
            Dict with 'updated_tracks', 'errors', 'merged' keys
        """
        if not old_name or not new_name:
            return {'updated_tracks': 0, 'errors': ['Empty name provided'], 'merged': False}

        if old_name == new_name:
            return {'updated_tracks': 0, 'errors': ['Names are identical'], 'merged': False}

        # Check if new_name already exists (merge scenario)
        existing_genre = self.get_genre_by_name(new_name)
        is_merge = existing_genre is not None

        # Get all tracks for the old genre
        tracks = self.get_genre_tracks(old_name)
        if not tracks:
            return {'updated_tracks': 0, 'errors': ['Genre not found'], 'merged': False}

        updated_count = 0
        errors = []

        for track in tracks:
            try:
                # Update file metadata
                success = MetadataService.save_metadata(
                    track.path,
                    title=track.title,
                    artist=track.artist,
                    album=track.album,
                    genre=new_name
                )

                if success:
                    # Update database
                    updated_track = Track(
                        id=track.id,
                        path=track.path,
                        title=track.title,
                        artist=track.artist,
                        album=track.album,
                        genre=new_name,
                        duration=track.duration,
                        cover_path=track.cover_path,
                        cloud_file_id=track.cloud_file_id,
                        source=track.source,
                    )
                    self._track_repo.update(updated_track)

                    # Emit metadata_updated signal
                    self._event_bus.metadata_updated.emit(track.id)
                    updated_count += 1
                else:
                    errors.append(f"Failed to save metadata: {track.path}")
            except Exception as e:
                errors.append(f"Error processing {track.path}: {str(e)}")
                logger.error(f"Error renaming genre for track {track.id}: {e}")

        # Rebuild genre cache table
        if updated_count > 0:
            if self._genre_repo:
                self._genre_repo.refresh()
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
        return self._artist_repo.update_cover_path(artist_name, cover_path)

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
        return self._album_repo.update_cover_path(album_name, artist, cover_path)

    def update_genre_cover(self, genre_name: str, cover_path: str) -> bool:
        """
        Update cover path for a genre.

        Args:
            genre_name: Genre name
            cover_path: Path to cover image

        Returns:
            True if updated successfully
        """
        if not self._genre_repo:
            return False
        return self._genre_repo.update_cover_path(genre_name, cover_path)

    def fix_album_covers(self) -> dict:
        """
        Fix album covers by finding tracks with covers for albums without covers.

        For each album without a cover, finds the first track with a cover
        and sets that as the album cover.

        Returns:
            Dict with 'fixed' count (albums fixed) and 'total' count (albums without covers)
        """
        # Get albums without covers
        albums = self._album_repo.get_albums_without_cover()
        total = len(albums)
        fixed = 0

        for album in albums:
            # Get tracks for this album
            tracks = self._track_repo.get_album_tracks(album.name, album.artist)
            logger.info(f"{album.name} {album.artist} - {len(tracks)}")

            # Find first track with a cover (local or online URL)
            for track in tracks:
                logger.info(f"Track {track.id} - {track.cover_path}")
                if track.cover_path:
                    # Update album cover
                    logger.info(f"{album.name} {album.artist} - {track.title} {track.cover_path}")
                    if self._album_repo.update_cover_path(album.name, album.artist, track.cover_path):
                        fixed += 1
                        logger.info(f"Fixed cover for album: {album.artist} - {album.name}")
                    break

        return {
            'fixed': fixed,
            'total': total
        }

    def fix_genre_covers(self) -> int:
        """
        Fix genre covers by finding tracks with covers for genres without covers.

        Returns:
            Number of genres fixed
        """
        if not self._genre_repo:
            return 0
        fixed = self._genre_repo.fix_covers()
        if fixed > 0:
            self._event_bus.tracks_added.emit(0)
        return fixed

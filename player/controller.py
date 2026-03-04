"""
Player controller that manages playback state and database interactions.
"""

from typing import Optional, List
from pathlib import Path
from PySide6.QtCore import QUrl

from .engine import PlayerEngine, PlayMode, PlayerState
from database import DatabaseManager, Track
from services import MetadataService


class PlayerController:
    """
    Controller for the playback engine.

    Manages the interaction between the player engine and the database,
    handling track loading, playback history, and favorites.
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize player controller.

        Args:
            db_manager: Database manager instance
        """
        self._db = db_manager
        self._engine = PlayerEngine()

        # Store current track ID for history
        self._current_track_id: Optional[int] = None

        # Connect engine signals
        self._engine.current_track_changed.connect(self._on_track_changed)
        self._engine.position_changed.connect(self._on_position_changed)

    @property
    def engine(self) -> PlayerEngine:
        """Get the player engine."""
        return self._engine

    @property
    def current_track_id(self) -> Optional[int]:
        """Get the current track ID."""
        return self._current_track_id

    def load_track(self, track_id: int) -> bool:
        """
        Load a track by ID and prepare for playback.
        Uses current queue if available, otherwise loads entire library.

        Args:
            track_id: Track ID from database

        Returns:
            True if track loaded successfully
        """
        track = self._db.get_track(track_id)
        if not track or not Path(track.path).exists():
            return False

        # Check if track is already in current queue
        current_playlist = self._engine.playlist
        target_index = -1

        for i, t in enumerate(current_playlist):
            if t.get("id") == track_id:
                target_index = i
                break

        # Build track dict
        track_dict = {
            "id": track.id,
            "path": track.path,
            "title": track.title,
            "artist": track.artist,
            "album": track.album,
            "duration": track.duration,
        }

        if target_index >= 0:
            # Track is in queue, play it
            self._engine.play_at(target_index)
        elif len(current_playlist) == 0:
            # Queue is empty, load entire library
            tracks = self._db.get_all_tracks()
            track_dicts = []
            start_index = 0

            for i, t in enumerate(tracks):
                t_dict = {
                    "id": t.id,
                    "path": t.path,
                    "title": t.title,
                    "artist": t.artist,
                    "album": t.album,
                    "duration": t.duration,
                }
                if t.id == track_id:
                    start_index = i
                track_dicts.append(t_dict)

            self._engine.load_playlist(track_dicts)
            self._engine.play_at(start_index)
        else:
            # Add to queue and play
            self._engine.add_track(track_dict)
            # Play the newly added track (last position)
            self._engine.play_at(len(current_playlist))

        return True

    def load_tracks(self, track_ids: List[int], start_index: int = 0):
        """
        Load multiple tracks into the playlist.

        Args:
            track_ids: List of track IDs
            start_index: Index to start playback from
        """
        self._engine.clear_playlist()

        for track_id in track_ids:
            track = self._db.get_track(track_id)
            if track and Path(track.path).exists():
                track_dict = {
                    "id": track.id,
                    "path": track.path,
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "duration": track.duration,
                }
                self._engine.add_track(track_dict)

        if self._engine.playlist and start_index > 0:
            self._engine.play_at(min(start_index, len(self._engine.playlist) - 1))

    def load_playlist(self, playlist_id: int):
        """
        Load a playlist from the database.

        Args:
            playlist_id: Playlist ID
        """
        tracks = self._db.get_playlist_tracks(playlist_id)

        track_dicts = []
        for track in tracks:
            if Path(track.path).exists():
                track_dicts.append(
                    {
                        "id": track.id,
                        "path": track.path,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album,
                        "duration": track.duration,
                    }
                )

        self._engine.load_playlist(track_dicts)

    def load_library(self):
        """Load all tracks from the library."""
        tracks = self._db.get_all_tracks()

        track_dicts = []
        for track in tracks:
            if Path(track.path).exists():
                track_dicts.append(
                    {
                        "id": track.id,
                        "path": track.path,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album,
                        "duration": track.duration,
                    }
                )

        self._engine.load_playlist(track_dicts)

    def load_favorites(self):
        """Load all favorite tracks."""
        tracks = self._db.get_favorites()

        track_dicts = []
        for track in tracks:
            if Path(track.path).exists():
                track_dicts.append(
                    {
                        "id": track.id,
                        "path": track.path,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album,
                        "duration": track.duration,
                    }
                )

        self._engine.load_playlist(track_dicts)

    def play_track(self, track_id: int):
        """
        Load and play a track.

        Args:
            track_id: Track ID to play
        """
        if self.load_track(track_id):
            self._db.add_play_history(track_id)
            self._engine.play()

    def scan_directory(self, directory: str, progress_callback=None) -> int:
        """
        Scan directory for audio files and add to database.

        Args:
            directory: Directory path to scan
            progress_callback: Optional callback for progress updates

        Returns:
            Number of files added
        """
        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return 0

        added_count = 0
        audio_files = []

        # Find all supported audio files
        for ext in MetadataService.SUPPORTED_FORMATS:
            audio_files.extend(path.rglob(f"*{ext}"))

        total = len(audio_files)

        for i, file_path in enumerate(audio_files):
            # Skip if already in database
            existing = self._db.get_track_by_path(str(file_path))
            if existing:
                continue

            # Extract metadata
            metadata = MetadataService.extract_metadata(str(file_path))

            # Save cover if available
            cover_path = None
            if metadata.get("cover"):
                # Save to cache directory
                cache_dir = Path.home() / ".cache" / "harmony_player" / "covers"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cover_filename = f"{file_path.stem}.jpg"
                cover_path = str(cache_dir / cover_filename)

                if MetadataService.save_cover(str(file_path), cover_path):
                    metadata["cover_path"] = cover_path

            # Create track and add to database
            track = Track(
                path=str(file_path),
                title=metadata.get("title", ""),
                artist=metadata.get("artist", ""),
                album=metadata.get("album", ""),
                duration=metadata.get("duration", 0),
                cover_path=metadata.get("cover_path"),
            )

            self._db.add_track(track)
            added_count += 1

            # Report progress
            if progress_callback:
                progress_callback(i + 1, total)

        return added_count

    def _on_track_changed(self, track_dict: dict):
        """Handle track change in engine."""
        self._current_track_id = track_dict.get("id")

    def _on_position_changed(self, position_ms: int):
        """
        Handle position change.
        """

    def toggle_favorite(self, track_id: int = None) -> bool:
        """
        Toggle favorite status for a track.

        Args:
            track_id: Track ID (uses current if not specified)

        Returns:
            New favorite status
        """
        if track_id is None:
            track_id = self._current_track_id

        if track_id is None:
            return False

        if self._db.is_favorite(track_id):
            self._db.remove_favorite(track_id)
            return False
        else:
            self._db.add_favorite(track_id)
            return True

    def is_favorite(self, track_id: int = None) -> bool:
        """
        Check if a track is favorited.

        Args:
            track_id: Track ID (uses current if not specified)

        Returns:
            True if favorited
        """
        if track_id is None:
            track_id = self._current_track_id

        if track_id is None:
            return False

        return self._db.is_favorite(track_id)

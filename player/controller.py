"""
Player controller that manages playback state and database interactions.
"""

import logging
from typing import Optional, List, TYPE_CHECKING
from pathlib import Path
from PySide6.QtCore import QUrl, QObject, Signal, QThread

from .engine import PlayerEngine, PlayMode, PlayerState
from .playlist_item import PlaylistItem, CloudProvider
from database import DatabaseManager, Track
from services import MetadataService
from utils.config import ConfigManager
from utils.event_bus import EventBus

if TYPE_CHECKING:
    from database.models import CloudFile, CloudAccount

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class PlayerController:
    """
    Controller for the playback engine.

    Manages the interaction between the player engine and the database,
    handling track loading, playback history, and favorites.

    Supports both local and cloud playback.
    """

    # Signals for cloud playback
    cloud_track_needs_download = Signal(object)  # PlaylistItem
    cloud_track_downloaded = Signal(int, str)  # index, local_path

    def __init__(self, db_manager: DatabaseManager, config: "ConfigManager"):
        """
        Initialize player controller.

        Args:
            db_manager: Database manager instance
            config: ConfigManager instance for settings
        """
        self._db = db_manager
        self._engine = PlayerEngine()
        self._config = config

        # Store current track ID for history
        self._current_track_id: Optional[int] = None

        # Cloud playback state
        self._current_cloud_account_id: Optional[int] = None
        self._cloud_files: List["CloudFile"] = []  # Current cloud file list
        self._downloaded_files: dict = {}  # cloud_file_id -> local_path

        # Connect engine signals
        self._engine.current_track_changed.connect(self._on_track_changed)
        self._engine.position_changed.connect(self._on_position_changed)
        self._engine.play_mode_changed.connect(self._on_play_mode_changed)
        self._engine.volume_changed.connect(self._on_volume_changed)
        self._engine.track_needs_download.connect(self._on_track_needs_download)

        # Restore saved settings
        self._restore_settings()

    @property
    def engine(self) -> PlayerEngine:
        """Get the player engine."""
        return self._engine

    @property
    def current_track_id(self) -> Optional[int]:
        """Get the current track ID."""
        return self._current_track_id

    @property
    def current_playlist_item(self) -> Optional[PlaylistItem]:
        """Get the current playlist item."""
        return self._engine.current_playlist_item

    @property
    def playback_source(self) -> str:
        """Get current playback source: 'local' or 'cloud'."""
        item = self._engine.current_playlist_item
        if item and item.is_cloud:
            return "cloud"
        return "local"

    def load_track(self, track_id: int) -> bool:
        """
        Load a track by ID and prepare for playback.
        Always loads entire library to ensure proper queue management.

        Args:
            track_id: Track ID from database

        Returns:
            True if track loaded successfully
        """
        track = self._db.get_track(track_id)
        if not track:
            return False

        # Skip cloud file virtual tracks (negative IDs)
        if track_id < 0:
            return False

        if not Path(track.path).exists():
            return False

        # Clear current playlist first to ensure clean state
        self._engine.clear_playlist()
        self._engine.cleanup_temp_files()

        # Load entire library
        tracks = self._db.get_all_tracks()
        track_dicts = []
        start_index = 0

        for i, t in enumerate(tracks):
            # Only include local tracks (positive IDs) that exist
            if t.id and t.id > 0 and Path(t.path).exists():
                t_dict = {
                    "id": t.id,
                    "path": t.path,
                    "title": t.title,
                    "artist": t.artist,
                    "album": t.album,
                    "duration": t.duration,
                }
                if t.id == track_id:
                    start_index = len(track_dicts)
                track_dicts.append(t_dict)

        self._engine.load_playlist(track_dicts)

        # If in shuffle mode, shuffle the playlist with the target track at front
        if self._engine.is_shuffle_mode():
            items = self._engine.playlist_items
            if 0 <= start_index < len(items):
                self._engine.shuffle_and_play(items[start_index])
                self._engine.play_at(0)
                return True

        self._engine.play_at(start_index)

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

        if self._engine.playlist:
            # If in shuffle mode, shuffle the playlist with the target track at front
            if self._engine.is_shuffle_mode() and start_index >= 0:
                items = self._engine.playlist_items
                if start_index < len(items):
                    self._engine.shuffle_and_play(items[start_index])
                    self._engine.play_at(0)
                    return

            if start_index > 0:
                self._engine.play_at(min(start_index, len(self._engine.playlist) - 1))
            else:
                self._engine.play_at(0)

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

        # If in shuffle mode, shuffle and start from first
        if self._engine.is_shuffle_mode() and track_dicts:
            self._engine.shuffle_and_play()
            self._engine.play_at(0)

    # ===== Cloud playback methods =====

    def load_cloud_playlist(
        self,
        cloud_files: List["CloudFile"],
        start_index: int,
        account: "CloudAccount",
        first_file_path: str = "",
        start_position: float = 0.0
    ):
        """
        Load a cloud file playlist.

        Args:
            cloud_files: List of CloudFile objects
            start_index: Index to start playback from
            account: CloudAccount for the files
            first_file_path: Optional local path for the first file (if already downloaded)
            start_position: Optional position to start from (in seconds)
        """
        logger.debug(f"[PlayerController] load_cloud_playlist: start_index={start_index}, files={len(cloud_files)}")

        # Store cloud state
        self._current_cloud_account_id = account.id
        self._cloud_files = cloud_files
        self._downloaded_files = {}

        # Build playlist items
        items = []
        for i, cloud_file in enumerate(cloud_files):
            # Check if file is already downloaded
            local_path = ""
            if i == start_index and first_file_path:
                local_path = first_file_path
                self._downloaded_files[cloud_file.file_id] = local_path

            item = PlaylistItem.from_cloud_file(cloud_file, account.id, local_path)
            items.append(item)

        # Load into engine
        self._engine.load_playlist_items(items)

        # Set playback source to cloud
        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

        # Start playback
        if start_position > 0:
            position_ms = int(start_position * 1000)
            self._engine.play_at_with_position(start_index, position_ms)
        else:
            self._engine.play_at(start_index)

    def on_cloud_file_downloaded(self, cloud_file_id: str, local_path: str):
        """
        Called when a cloud file has been downloaded.

        Args:
            cloud_file_id: Cloud file ID
            local_path: Local path of downloaded file
        """
        logger.debug(f"[PlayerController] on_cloud_file_downloaded: {cloud_file_id} -> {local_path}")

        # Store the downloaded path
        self._downloaded_files[cloud_file_id] = local_path

        # Find the index in the playlist
        items = self._engine.playlist_items
        for i, item in enumerate(items):
            if item.cloud_file_id == cloud_file_id:
                # Update the item path
                item.local_path = local_path
                item.needs_download = False

                # If this is the current track, play it
                if i == self._engine.current_index:
                    logger.debug(f"[PlayerController] Playing downloaded track at index {i}")
                    self._engine.play_after_download(i, local_path)

                # Emit signal for UI updates
                self.cloud_track_downloaded.emit(i, local_path)
                break

    def _on_track_needs_download(self, item: PlaylistItem):
        """
        Handle when a track needs to be downloaded.

        Args:
            item: PlaylistItem that needs download
        """
        logger.debug(f"[PlayerController] _on_track_needs_download: {item.cloud_file_id}")

        # Check if already downloaded
        if item.cloud_file_id in self._downloaded_files:
            local_path = self._downloaded_files[item.cloud_file_id]
            index = self._engine.current_index
            self._engine.play_after_download(index, local_path)
            return

        # Emit signal for external handling (e.g., download service)
        self.cloud_track_needs_download.emit(item)

    # ===== End cloud playback methods =====

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

        # Record play history for local tracks only
        track_id = track_dict.get("id")
        source_type = track_dict.get("source_type", "local")

        if track_id and source_type == "local":
            self._db.add_play_history(track_id)

    def _on_position_changed(self, position_ms: int):
        """
        Handle position change.
        """

    def _on_play_mode_changed(self, mode: PlayMode):
        """
        Handle play mode change and save to config.

        Args:
            mode: New play mode
        """
        # Save the integer value of the enum
        self._config.set_play_mode(mode.value)

    def _on_volume_changed(self, volume: int):
        """
        Handle volume change and save to config.

        Args:
            volume: New volume level (0-100)
        """
        self._config.set_volume(volume)

    def _restore_settings(self):
        """Restore saved settings from config."""
        # Restore play mode (convert int to PlayMode)
        saved_mode_int = self._config.get_play_mode()
        try:
            saved_mode = PlayMode(saved_mode_int)
            self._engine.set_play_mode(saved_mode)
        except ValueError:
            # Invalid mode, use default
            self._engine.set_play_mode(PlayMode.SEQUENTIAL)

        # Restore volume
        saved_volume = self._config.get_volume()
        self._engine.set_volume(saved_volume)

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

        bus = EventBus.instance()
        if self._db.is_favorite(track_id):
            self._db.remove_favorite(track_id)
            bus.emit_favorite_change(track_id, False)
            return False
        else:
            self._db.add_favorite(track_id)
            bus.emit_favorite_change(track_id, True)
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

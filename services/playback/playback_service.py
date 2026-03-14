"""
Playback service - Unified business logic for audio playback.

This service handles both local and cloud playback, queue persistence,
favorites management, and EventBus integration.
"""

import logging
from typing import Optional, List, TYPE_CHECKING
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from domain import PlaylistItem
from domain.playback import PlayMode, PlaybackState
from domain.track import Track
from infrastructure.audio import PlayerEngine
from infrastructure.database import DatabaseManager
from system.config import ConfigManager
from system.event_bus import EventBus

if TYPE_CHECKING:
    from domain import CloudFile, CloudAccount
    from services.cloud.download_service import CloudDownloadService

logger = logging.getLogger(__name__)


class PlaybackService(QObject):
    """
    Unified playback service for all music sources.

    This service provides a single interface for playback operations,
    handling both local tracks and cloud files transparently.

    Features:
    - Unified API for local and cloud playback
    - Automatic cloud file downloading
    - Playback state persistence
    - Favorites management
    - Integration with EventBus

    Signals:
        source_changed: Emitted when playback source changes ("local" or "cloud")
    """

    source_changed = Signal(str)  # "local" or "cloud"

    def __init__(
        self,
        db_manager: DatabaseManager,
        config_manager: ConfigManager,
        cover_service: 'CoverService' = None,
        parent=None
    ):
        """
        Initialize the playback service.

        Args:
            db_manager: Database manager for track data
            config_manager: Configuration manager for settings
            cover_service: Cover service for album art
            parent: Optional parent QObject
        """
        super().__init__(parent)

        self._db = db_manager
        self._config = config_manager
        self._cover_service = cover_service
        self._engine = PlayerEngine()
        self._event_bus = EventBus.instance()

        # Playback state
        self._current_source = "local"  # "local" or "cloud"
        self._cloud_account: Optional["CloudAccount"] = None
        self._cloud_files: List["CloudFile"] = []
        self._downloaded_files: dict = {}  # cloud_file_id -> local_path

        # Current track ID for history
        self._current_track_id: Optional[int] = None

        # Connect engine signals
        self._connect_engine_signals()

        # Connect download service signals
        self._connect_download_service_signals()

        # Restore settings
        self._restore_settings()

    def _connect_engine_signals(self):
        """Connect engine signals to internal handlers and EventBus."""
        self._engine.current_track_changed.connect(self._on_track_changed)
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.position_changed.connect(self._event_bus.position_changed.emit)
        self._engine.duration_changed.connect(self._event_bus.duration_changed.emit)
        self._engine.play_mode_changed.connect(self._on_play_mode_changed)
        self._engine.volume_changed.connect(self._event_bus.volume_changed.emit)
        self._engine.track_finished.connect(self._event_bus.track_finished.emit)
        self._engine.track_needs_download.connect(self._on_track_needs_download)

    def _connect_download_service_signals(self):
        """Connect CloudDownloadService signals to EventBus."""
        from services.cloud.download_service import CloudDownloadService

        service = CloudDownloadService.instance()
        service.download_started.connect(self._event_bus.download_started.emit)
        service.download_progress.connect(self._event_bus.download_progress.emit)
        service.download_completed.connect(self._event_bus.download_completed.emit)
        service.download_error.connect(self._event_bus.download_error.emit)

    def _restore_settings(self):
        """Restore saved settings from config."""
        saved_mode_int = self._config.get_play_mode()
        try:
            saved_mode = PlayMode(saved_mode_int)
            self._engine.set_play_mode(saved_mode)
        except ValueError:
            self._engine.set_play_mode(PlayMode.SEQUENTIAL)

        saved_volume = self._config.get_volume()
        self._engine.set_volume(saved_volume)

        self._current_source = self._config.get_playback_source()

    # ===== Properties =====

    @property
    def engine(self) -> PlayerEngine:
        """Get the player engine."""
        return self._engine

    @property
    def current_source(self) -> str:
        """Get current playback source ("local" or "cloud")."""
        return self._current_source

    @property
    def current_track(self) -> Optional[PlaylistItem]:
        """Get current playlist item."""
        return self._engine.current_playlist_item

    @property
    def current_track_id(self) -> Optional[int]:
        """Get the current track ID."""
        return self._current_track_id

    @property
    def cover_service(self) -> Optional['CoverService']:
        """Get the cover service."""
        return self._cover_service

    @property
    def state(self) -> PlaybackState:
        """Get current player state."""
        return self._engine.state

    @property
    def volume(self) -> int:
        """Get current volume (0-100)."""
        return self._engine.volume

    @property
    def play_mode(self) -> PlayMode:
        """Get current play mode."""
        return self._engine.play_mode

    # ===== Playback Control =====

    def play(self):
        """Start or resume playback."""
        self._engine.play()

    def pause(self):
        """Pause playback."""
        self._engine.pause()

    def stop(self):
        """Stop playback."""
        self._engine.stop()

    def play_next(self):
        """Play next track."""
        self._engine.play_next()

    def play_previous(self):
        """Play previous track."""
        self._engine.play_previous()

    def seek(self, position_ms: int):
        """Seek to position in milliseconds."""
        self._engine.seek(position_ms)

    def set_volume(self, volume: int):
        """Set volume (0-100)."""
        self._engine.set_volume(volume)

    def set_play_mode(self, mode: PlayMode):
        """Set play mode and persist to config."""
        self._engine.set_play_mode(mode)

    # ===== Local Playback =====

    def play_local_track(self, track_id: int):
        """
        Play a local track by ID.

        Args:
            track_id: Database track ID
        """
        track = self._db.get_track(track_id)
        if not track:
            logger.error(f"[PlaybackService] Track not found: {track_id}")
            return

        if not Path(track.path).exists():
            logger.error(f"[PlaybackService] File not found: {track.path}")
            return

        self._set_source("local")

        # Clear playlist and load library
        self._engine.clear_playlist()
        self._engine.cleanup_temp_files()

        tracks = self._db.get_all_tracks()
        items = []
        start_index = 0

        for t in tracks:
            if t.id and t.id > 0 and Path(t.path).exists():
                item = PlaylistItem.from_track(t)
                if t.id == track_id:
                    start_index = len(items)
                items.append(item)

        self._engine.load_playlist_items(items)

        # If in shuffle mode, shuffle the playlist with the target track at front
        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        else:
            self._engine.play_at(start_index)

        # Save queue and state
        self.save_queue()
        self._config.set_current_track_id(track_id)
        self._config.set_playback_source("local")

    def play_local_tracks(self, track_ids: List[int], start_index: int = 0):
        """
        Play multiple local tracks.

        Args:
            track_ids: List of track IDs
            start_index: Index to start playback from
        """
        self._set_source("local")
        self._engine.clear_playlist()

        items = []
        for track_id in track_ids:
            track = self._db.get_track(track_id)
            if track and Path(track.path).exists():
                items.append(PlaylistItem.from_track(track))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        elif items:
            self._engine.play_at(min(start_index, len(items) - 1))

        self.save_queue()
        self._config.set_playback_source("local")

    def play_local_library(self):
        """Play all tracks in the library."""
        self._set_source("local")

        tracks = self._db.get_all_tracks()
        items = []

        for t in tracks:
            if t.id and t.id > 0 and Path(t.path).exists():
                items.append(PlaylistItem.from_track(t))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()
            self._engine.play_at(0)
        else:
            self._engine.play()

    def load_playlist(self, playlist_id: int):
        """
        Load a playlist from the database.

        Args:
            playlist_id: Playlist ID
        """
        logger.debug(f"[PlaybackService] Loading playlist: {playlist_id}")

        self._set_source("local")

        tracks = self._db.get_playlist_tracks(playlist_id)
        items = []

        for track in tracks:
            if track.id and track.id > 0 and Path(track.path).exists():
                items.append(PlaylistItem.from_track(track))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()

        self._config.set_playback_source("local")

    def play_playlist_track(self, playlist_id: int, track_id: int):
        """
        Play a specific track from a playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID to play
        """
        self._set_source("local")

        tracks = self._db.get_playlist_tracks(playlist_id)
        items = []
        start_index = 0

        for track in tracks:
            if track.id and track.id > 0 and Path(track.path).exists():
                item = PlaylistItem.from_track(track)
                if track.id == track_id:
                    start_index = len(items)
                items.append(item)

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        else:
            self._engine.play_at(start_index)

        self.save_queue()
        self._config.set_current_track_id(track_id)
        self._config.set_playback_source("local")

    def load_favorites(self):
        """Load all favorite tracks."""
        tracks = self._db.get_favorites()
        items = []

        for track in tracks:
            if track.id and Path(track.path).exists():
                items.append(PlaylistItem.from_track(track))

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()

    # ===== Cloud Playback =====

    def play_cloud_track(
        self,
        cloud_file: "CloudFile",
        account: "CloudAccount",
        cloud_files: List["CloudFile"] = None
    ):
        """
        Play a cloud file.

        Args:
            cloud_file: CloudFile to play
            account: CloudAccount for authentication
            cloud_files: Optional list of all cloud files for playlist
        """
        self._cloud_account = account
        self._cloud_files = cloud_files or [cloud_file]
        self._set_source("cloud")

        # Build playlist items
        items = []
        start_index = 0

        for i, cf in enumerate(self._cloud_files):
            local_path = self._get_cached_path(cf.file_id)
            item = PlaylistItem.from_cloud_file(cf, account.id, local_path)
            if cf.file_id == cloud_file.file_id:
                start_index = i
            items.append(item)

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            self._engine.play_at(0)
        else:
            self._engine.play_at(start_index)

        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

    def play_cloud_playlist(
        self,
        cloud_files: List["CloudFile"],
        start_index: int,
        account: "CloudAccount",
        first_file_path: str = "",
        start_position: float = 0.0
    ):
        """
        Play a cloud file playlist.

        Args:
            cloud_files: List of CloudFile objects
            start_index: Index to start playback from
            account: CloudAccount for authentication
            first_file_path: Optional local path for the first file (if already downloaded)
            start_position: Optional position to start from (in seconds)
        """
        self._cloud_account = account
        self._cloud_files = cloud_files
        self._set_source("cloud")

        # Build playlist items
        items = []

        for i, cf in enumerate(cloud_files):
            local_path = ""
            if i == start_index and first_file_path:
                local_path = first_file_path
                self._downloaded_files[cf.file_id] = local_path
            else:
                local_path = self._get_cached_path(cf.file_id)

            item = PlaylistItem.from_cloud_file(cf, account.id, local_path)
            items.append(item)

        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and 0 <= start_index < len(items):
            self._engine.shuffle_and_play(items[start_index])
            start_index = 0

        # Start playback
        if start_position > 0:
            position_ms = int(start_position * 1000)
            self._engine.play_at_with_position(start_index, position_ms)
        else:
            self._engine.play_at(start_index)

        self.save_queue()
        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

    def on_cloud_file_downloaded(self, cloud_file_id: str, local_path: str):
        """
        Called when a cloud file has been downloaded.

        Args:
            cloud_file_id: Cloud file ID
            local_path: Local path of downloaded file
        """
        self._downloaded_files[cloud_file_id] = local_path

        # Extract metadata and save to library
        cover_path = self._save_cloud_track_to_library(cloud_file_id, local_path)

        # Get track from database to retrieve metadata
        track = self._db.get_track_by_cloud_file_id(cloud_file_id)

        # Update playlist items with metadata
        items = self._engine.playlist_items
        for i, item in enumerate(items):
            if item.cloud_file_id == cloud_file_id:
                item.local_path = local_path
                item.needs_download = False
                item.cover_path = cover_path

                # Update metadata from database track
                if track:
                    item.title = track.title or item.title
                    item.artist = track.artist or item.artist
                    item.album = track.album or item.album
                    item.duration = track.duration or item.duration
                    item.needs_metadata = False

                # Play if this is current track
                if i == self._engine.current_index:
                    self._engine.play_after_download(i, local_path)
                break

    # ===== Favorites Management =====

    def toggle_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        cloud_account_id: int = None
    ) -> bool:
        """
        Toggle favorite status for a track or cloud file.

        Args:
            track_id: Track ID (uses current if not specified)
            cloud_file_id: Cloud file ID (for cloud files)
            cloud_account_id: Cloud account ID (for cloud files)

        Returns:
            New favorite status
        """
        if track_id is None and cloud_file_id is None:
            track_id = self._current_track_id

        if track_id is None and cloud_file_id is None:
            return False

        if track_id:
            if self._db.is_favorite(track_id=track_id):
                self._db.remove_favorite(track_id=track_id)
                self._event_bus.emit_favorite_change(track_id, False, is_cloud=False)
                return False
            else:
                self._db.add_favorite(track_id=track_id)
                self._event_bus.emit_favorite_change(track_id, True, is_cloud=False)
                return True
        else:
            if self._db.is_favorite(cloud_file_id=cloud_file_id):
                self._db.remove_favorite(cloud_file_id=cloud_file_id)
                self._event_bus.emit_favorite_change(cloud_file_id, False, is_cloud=True)
                return False
            else:
                self._db.add_favorite(
                    cloud_file_id=cloud_file_id,
                    cloud_account_id=cloud_account_id
                )
                self._event_bus.emit_favorite_change(cloud_file_id, True, is_cloud=True)
                return True

    def is_favorite(self, track_id: int = None, cloud_file_id: str = None) -> bool:
        """
        Check if a track or cloud file is favorited.

        Args:
            track_id: Track ID (uses current if not specified)
            cloud_file_id: Cloud file ID (for cloud files)

        Returns:
            True if favorited
        """
        if track_id is None and cloud_file_id is None:
            track_id = self._current_track_id

        if track_id is None and cloud_file_id is None:
            return False

        return self._db.is_favorite(track_id=track_id, cloud_file_id=cloud_file_id)

    # ===== Queue Persistence =====

    def save_queue(self):
        """Save the current play queue to database."""
        items = self._engine.playlist_items
        if not items:
            return

        current_idx = self._engine.current_index

        # Convert to PlayQueueItem list
        queue_items = []
        for i, item in enumerate(items):
            queue_item = item.to_play_queue_item(i)
            queue_items.append(queue_item)

        self._db.save_play_queue(queue_items)

        # Save current index and play mode
        self._config.set("queue_current_index", current_idx)
        self._config.set("queue_play_mode", self._engine.play_mode.value)

        logger.debug(f"[PlaybackService] Saved queue: {len(queue_items)} items, index={current_idx}")

    def restore_queue(self) -> bool:
        """
        Restore the play queue from database.

        Returns:
            True if queue was restored successfully
        """
        queue_items = self._db.load_play_queue()
        if not queue_items:
            return False

        # Convert to PlaylistItem list
        items = [PlaylistItem.from_play_queue_item(item, self._db) for item in queue_items]

        # Get saved index and play mode
        saved_index = self._config.get("queue_current_index", 0)
        saved_mode = self._config.get("queue_play_mode", PlayMode.SEQUENTIAL.value)

        # Determine source type from items at saved_index
        if items and 0 <= saved_index < len(items):
            target_item = items[saved_index]
        elif items:
            target_item = items[0]
            saved_index = 0
        else:
            return False

        if target_item.is_cloud:
            self._set_source("cloud")
            if target_item.cloud_account_id:
                self._cloud_account = self._db.get_cloud_account(target_item.cloud_account_id)
        else:
            self._set_source("local")

        # Load queue into engine
        self._engine.load_playlist_items(items)

        # Restore play mode
        try:
            mode = PlayMode(saved_mode)
            self._engine._play_mode = mode
        except ValueError:
            pass

        # Clamp index to valid range
        if saved_index < 0 or saved_index >= len(items):
            saved_index = 0

        # Set current index and load track (but don't play)
        self._engine._current_index = saved_index
        if 0 <= saved_index < len(items):
            self._engine._load_track(saved_index)

        return True

    def clear_saved_queue(self):
        """Clear the saved play queue from database."""
        self._db.clear_play_queue()
        self._config.delete("queue_current_index")
        self._config.delete("queue_play_mode")

    # ===== Library Scanning =====

    def scan_directory(self, directory: str, progress_callback=None) -> int:
        """
        Scan directory for audio files and add to database.

        Args:
            directory: Directory path to scan
            progress_callback: Optional callback for progress updates

        Returns:
            Number of files added
        """
        from services.metadata import MetadataService

        path = Path(directory)
        if not path.exists() or not path.is_dir():
            return 0

        added_count = 0
        audio_files = []

        for ext in MetadataService.SUPPORTED_FORMATS:
            audio_files.extend(path.rglob(f"*{ext}"))

        total = len(audio_files)

        for i, file_path in enumerate(audio_files):
            existing = self._db.get_track_by_path(str(file_path))
            if existing:
                continue

            metadata = MetadataService.extract_metadata(str(file_path))

            cover_path = None
            if metadata.get("cover"):
                cache_dir = Path.home() / ".cache" / "harmony_player" / "covers"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cover_filename = f"{file_path.stem}.jpg"
                cover_path = str(cache_dir / cover_filename)

                if MetadataService.save_cover(str(file_path), cover_path):
                    metadata["cover_path"] = cover_path

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

            if progress_callback:
                progress_callback(i + 1, total)

        return added_count

    # ===== Internal Methods =====

    def _set_source(self, source: str):
        """Set playback source and emit signal."""
        if self._current_source != source:
            self._current_source = source
            self.source_changed.emit(source)

    def _get_cached_path(self, file_id: str) -> str:
        """Get cached local path for a cloud file."""
        from services.cloud.download_service import CloudDownloadService

        service = CloudDownloadService.instance()
        cached = service.get_cached_path(file_id)
        return cached or ""

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        self._current_track_id = track_dict.get("id")

        item = self._engine.current_playlist_item
        if item:
            self._event_bus.emit_track_change(item)

            # Record play history
            if item.is_local and item.track_id:
                self._db.add_play_history(item.track_id)
            elif item.is_cloud and item.local_path:
                track = self._db.get_track_by_path(item.local_path)
                if not track:
                    track = self._db.get_track_by_cloud_file_id(item.cloud_file_id)

                if track and track.id:
                    self._db.add_play_history(track.id)
                else:
                    # Create a new Track record for this cloud file
                    new_track = Track(
                        path=item.local_path,
                        title=item.title,
                        artist=item.artist,
                        album=item.album,
                        duration=item.duration,
                    )
                    track_id = self._db.add_track(new_track)
                    if track_id and item.cloud_file_id:
                        conn = self._db._get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE tracks SET cloud_file_id = ? WHERE id = ?",
                            (item.cloud_file_id, track_id)
                        )
                        conn.commit()

                    if track_id:
                        self._db.add_play_history(track_id)

    def _on_state_changed(self, state: PlaybackState):
        """Handle state change."""
        state_str = {
            PlaybackState.PLAYING: "playing",
            PlaybackState.PAUSED: "paused",
            PlaybackState.STOPPED: "stopped",
        }.get(state, "stopped")
        self._event_bus.emit_playback_state(state_str)

    def _on_play_mode_changed(self, mode: PlayMode):
        """Handle play mode change - save to config and emit to EventBus."""
        self._config.set_play_mode(mode.value)
        self._event_bus.play_mode_changed.emit(mode.value)

    def _on_track_needs_download(self, item: PlaylistItem):
        """Handle track that needs download."""
        from services.cloud.download_service import CloudDownloadService

        if not self._cloud_account:
            logger.error("[PlaybackService] No cloud account for download")
            if item.cloud_account_id:
                self._cloud_account = self._db.get_cloud_account(item.cloud_account_id)
                if not self._cloud_account:
                    return
            else:
                return

        service = CloudDownloadService.instance()
        service.set_download_dir(self._config.get_cloud_download_dir())

        # Find the CloudFile
        cloud_file = None
        for cf in self._cloud_files:
            if cf.file_id == item.cloud_file_id:
                cloud_file = cf
                break

        if not cloud_file:
            cloud_file = self._db.get_cloud_file_by_file_id(item.cloud_file_id)
            if not cloud_file:
                logger.error(f"[PlaybackService] CloudFile not found: {item.cloud_file_id}")
                return

        if cloud_file:
            service.download_file(cloud_file, self._cloud_account)

    def _save_cloud_track_to_library(self, file_id: str, local_path: str) -> str:
        """
        Save downloaded cloud track to library with metadata and cover art.

        Args:
            file_id: Cloud file ID
            local_path: Local path of downloaded file

        Returns:
            cover_path: Path to the extracted cover art, or None
        """
        from services.metadata.metadata_service import MetadataService

        existing = self._db.get_track_by_cloud_file_id(file_id)
        if existing:
            return existing.cover_path

        existing_by_path = self._db.get_track_by_path(local_path)
        if existing_by_path:
            conn = self._db._get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tracks SET cloud_file_id = ? WHERE id = ?",
                (file_id, existing_by_path.id)
            )
            conn.commit()
            return existing_by_path.cover_path

        metadata = MetadataService.extract_metadata(local_path)

        title = metadata.get("title", Path(local_path).stem)
        artist = metadata.get("artist", "")
        album = metadata.get("album", "")

        cover_path = None
        if self._cover_service:
            cover_path = self._cover_service.save_cover_from_metadata(
                local_path,
                metadata.get("cover")
            )

        track = Track(
            path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=metadata.get("duration", 0),
            cloud_file_id=file_id,
            cover_path=cover_path,
        )

        self._db.add_track(track)
        return cover_path

    def get_track_cover(self, track_path: str, title: str, artist: str, album: str = "") -> Optional[str]:
        """
        Get cover art for a track.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            album: Album name

        Returns:
            Path to the cover image, or None
        """
        if self._cover_service:
            return self._cover_service.get_cover(track_path, title, artist, album)
        return None

    def save_cover_from_metadata(self, track_path: str, cover_data: bytes) -> Optional[str]:
        """
        Save cover art from already extracted metadata.

        Args:
            track_path: Path to the audio file (used for generating cache filename)
            cover_data: Cover image data from metadata

        Returns:
            Path to saved cover, or None
        """
        if self._cover_service:
            return self._cover_service.save_cover_from_metadata(track_path, cover_data)
        return None

"""
Unified playback manager for local and cloud playback.

This module provides a single entry point for all playback operations,
abstracting the differences between local and cloud music sources.
"""

import logging
from typing import Optional, List, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from .engine import PlayerEngine, PlayMode, PlayerState
from .playlist_item import PlaylistItem, CloudProvider
from .controller import PlayerController
from database import DatabaseManager
from utils.config import ConfigManager
from utils.event_bus import EventBus

if TYPE_CHECKING:
    from database.models import Track, CloudFile, CloudAccount
    from services.cloud_download_service import CloudDownloadService

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class PlaybackManager(QObject):
    """
    Unified playback manager for all music sources.

    This class provides a single interface for playback operations,
    handling both local tracks and cloud files transparently.

    Features:
    - Unified API for local and cloud playback
    - Automatic cloud file downloading
    - Preloading of next track
    - Playback state persistence
    - Integration with EventBus

    Signals:
        source_changed: Emitted when playback source changes ("local" or "cloud")
    """

    source_changed = Signal(str)  # "local" or "cloud"

    def __init__(
        self,
        db_manager: DatabaseManager,
        config_manager: ConfigManager,
        parent=None
    ):
        """
        Initialize the playback manager.

        Args:
            db_manager: Database manager for track data
            config_manager: Configuration manager for settings
            parent: Optional parent QObject
        """
        super().__init__(parent)

        self._db = db_manager
        self._config = config_manager
        self._engine = PlayerEngine()
        self._event_bus = EventBus.instance()

        # Playback state
        self._current_source = "local"  # "local" or "cloud"
        self._cloud_account: Optional["CloudAccount"] = None
        self._cloud_files: List["CloudFile"] = []

        # Download service (lazy initialized)
        self._download_service: Optional["CloudDownloadService"] = None

        # Connect engine signals
        self._connect_engine_signals()

        # Connect download service signals
        self._connect_download_service_signals()

        # Restore settings
        self._restore_settings()

        logger.debug("[PlaybackManager] Initialized")

    def _connect_engine_signals(self):
        """Connect engine signals to internal handlers and EventBus."""
        # Engine -> EventBus forwarding
        self._engine.current_track_changed.connect(self._on_track_changed)
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.position_changed.connect(self._event_bus.position_changed.emit)
        self._engine.duration_changed.connect(self._event_bus.duration_changed.emit)
        self._engine.play_mode_changed.connect(
            lambda mode: self._event_bus.play_mode_changed.emit(mode.value)
        )
        self._engine.volume_changed.connect(self._event_bus.volume_changed.emit)
        self._engine.track_finished.connect(self._event_bus.track_finished.emit)
        self._engine.track_needs_download.connect(self._on_track_needs_download)

    def _connect_download_service_signals(self):
        """Connect CloudDownloadService signals to EventBus."""
        from services.cloud_download_service import CloudDownloadService

        service = CloudDownloadService.instance()
        # Forward download signals to EventBus
        service.download_started.connect(self._event_bus.download_started.emit)
        service.download_progress.connect(self._event_bus.download_progress.emit)
        service.download_completed.connect(self._event_bus.download_completed.emit)
        service.download_error.connect(self._event_bus.download_error.emit)

    def _restore_settings(self):
        """Restore saved settings from config."""
        # Restore play mode
        saved_mode_int = self._config.get_play_mode()
        try:
            saved_mode = PlayMode(saved_mode_int)
            self._engine.set_play_mode(saved_mode)
        except ValueError:
            self._engine.set_play_mode(PlayMode.SEQUENTIAL)

        # Restore volume
        saved_volume = self._config.get_volume()
        self._engine.set_volume(saved_volume)

        # Restore playback source
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
    def state(self) -> PlayerState:
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

    # ===== Local Playback =====

    def play_local_track(self, track_id: int):
        """
        Play a local track by ID.

        Args:
            track_id: Database track ID
        """
        from pathlib import Path

        logger.debug(f"[PlaybackManager] Playing local track: {track_id}")

        track = self._db.get_track(track_id)
        if not track:
            logger.error(f"[PlaybackManager] Track not found: {track_id}")
            return

        if not Path(track.path).exists():
            logger.error(f"[PlaybackManager] File not found: {track.path}")
            return

        # Set source to local
        self._set_source("local")

        # Clear playlist and load library
        self._engine.clear_playlist()

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
        self._engine.play_at(start_index)

        # Save state
        self._config.set_current_track_id(track_id)
        self._config.set_playback_source("local")

    def play_local_library(self):
        """Play all tracks in the library."""
        from pathlib import Path

        logger.debug("[PlaybackManager] Playing library")

        self._set_source("local")

        tracks = self._db.get_all_tracks()
        items = []

        for t in tracks:
            if t.id and t.id > 0 and Path(t.path).exists():
                items.append(PlaylistItem.from_track(t))

        self._engine.load_playlist_items(items)
        self._engine.play()

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
        logger.debug(f"[PlaybackManager] Playing cloud track: {cloud_file.name}")

        self._cloud_account = account
        self._cloud_files = cloud_files or [cloud_file]
        self._set_source("cloud")

        # Build playlist items
        items = []
        start_index = 0

        for i, cf in enumerate(self._cloud_files):
            # Check if file is already downloaded
            local_path = self._get_cached_path(cf.file_id)

            item = PlaylistItem.from_cloud_file(cf, account.id, local_path)
            if cf.file_id == cloud_file.file_id:
                start_index = i
            items.append(item)

        self._engine.load_playlist_items(items)
        self._engine.play_at(start_index)

        # Save state
        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

    def play_cloud_playlist(
        self,
        cloud_files: List["CloudFile"],
        start_index: int,
        account: "CloudAccount",
        start_position: float = 0.0
    ):
        """
        Play a cloud file playlist.

        Args:
            cloud_files: List of CloudFile objects
            start_index: Index to start playback from
            account: CloudAccount for authentication
            start_position: Optional position to start from (in seconds)
        """
        logger.debug(f"[PlaybackManager] Playing cloud playlist: {len(cloud_files)} files, start={start_index}")

        self._cloud_account = account
        self._cloud_files = cloud_files
        self._set_source("cloud")

        # Build playlist items
        items = []

        for cf in cloud_files:
            local_path = self._get_cached_path(cf.file_id)
            item = PlaylistItem.from_cloud_file(cf, account.id, local_path)
            items.append(item)

        self._engine.load_playlist_items(items)

        # Start playback
        if start_position > 0:
            position_ms = int(start_position * 1000)
            self._engine.play_at_with_position(start_index, position_ms)
        else:
            self._engine.play_at(start_index)

        # Save state
        self._config.set_playback_source("cloud")
        self._config.set_cloud_account_id(account.id)

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
        """Set play mode."""
        self._engine.set_play_mode(mode)

    # ===== Internal Methods =====

    def _set_source(self, source: str):
        """Set playback source and emit signal."""
        if self._current_source != source:
            self._current_source = source
            self.source_changed.emit(source)
            logger.debug(f"[PlaybackManager] Source changed to: {source}")

    def _get_cached_path(self, file_id: str) -> str:
        """Get cached local path for a cloud file."""
        from services.cloud_download_service import CloudDownloadService

        service = CloudDownloadService.instance()
        cached = service.get_cached_path(file_id)
        return cached or ""

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        # Emit to EventBus
        item = self._engine.current_playlist_item
        if item:
            self._event_bus.emit_track_change(item)

            # Record play history for local tracks
            if item.is_local and item.track_id:
                self._db.add_play_history(item.track_id)

    def _on_state_changed(self, state: PlayerState):
        """Handle state change."""
        state_str = {
            PlayerState.PLAYING: "playing",
            PlayerState.PAUSED: "paused",
            PlayerState.STOPPED: "stopped",
        }.get(state, "stopped")
        self._event_bus.emit_playback_state(state_str)

    def _on_track_needs_download(self, item: PlaylistItem):
        """Handle track that needs download."""
        logger.debug(f"[PlaybackManager] Track needs download: {item.cloud_file_id}")

        from services.cloud_download_service import CloudDownloadService

        if not self._cloud_account:
            logger.error("[PlaybackManager] No cloud account for download")
            return

        # Start download
        service = CloudDownloadService.instance()
        service.set_download_dir(self._config.get_cloud_download_dir())

        # Find the CloudFile
        cloud_file = None
        for cf in self._cloud_files:
            if cf.file_id == item.cloud_file_id:
                cloud_file = cf
                break

        if cloud_file:
            service.download_file(cloud_file, self._cloud_account)

    def on_download_completed(self, file_id: str, local_path: str):
        """
        Handle download completion.

        Args:
            file_id: Cloud file ID
            local_path: Local path of downloaded file
        """
        logger.debug(f"[PlaybackManager] Download completed: {file_id}")

        # Update playlist items
        items = self._engine.playlist_items
        for i, item in enumerate(items):
            if item.cloud_file_id == file_id:
                item.local_path = local_path
                item.needs_download = False

                # Play if this is current track
                if i == self._engine.current_index:
                    self._engine.play_after_download(i, local_path)
                break

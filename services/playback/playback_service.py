"""
Playback service - Unified business logic for audio playback.

This service handles both local and cloud playback, queue persistence,
favorites management, and EventBus integration.

Architecture:
- PlaybackService acts as a coordinator/facade
- LocalTrackHandler handles local file playback
- CloudTrackHandler handles cloud file playback
- OnlineTrackHandler handles online (QQ Music) playback
"""

import logging
import threading
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Qt, QTimer

from domain import PlaylistItem
from domain.playback import PlayMode, PlaybackState
from domain.track import Track, TrackSource
from infrastructure.audio.audio_backend import AudioEffectsState
from infrastructure.audio import PlayerEngine
from system.config import ConfigManager
from system.event_bus import EventBus
from utils.helpers import get_cache_dir

if TYPE_CHECKING:
    from domain import CloudFile, CloudAccount
    from services.cloud.download_service import CloudDownloadService
    from services.online import OnlineDownloadService
    from repositories.track_repository import SqliteTrackRepository
    from repositories.favorite_repository import SqliteFavoriteRepository
    from repositories.queue_repository import SqliteQueueRepository
    from repositories.cloud_repository import SqliteCloudRepository
    from repositories.history_repository import SqliteHistoryRepository
    from repositories.album_repository import SqliteAlbumRepository
    from repositories.artist_repository import SqliteArtistRepository

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
    _metadata_processed = Signal(str, str, int, str, str, str, float, str)  # Internal signal for metadata
    _metadata_batch_complete = Signal()  # Emitted when batch metadata processing completes
    LIBRARY_PAGE_SIZE = 1000

    def __init__(
            self,
            db_manager: 'DatabaseManager' = None,
            config_manager: ConfigManager = None,
            cover_service: 'CoverService' = None,
            online_download_service: 'OnlineDownloadService' = None,
            event_bus: EventBus = None,
            track_repo: 'SqliteTrackRepository' = None,
            favorite_repo: 'SqliteFavoriteRepository' = None,
            queue_repo: 'SqliteQueueRepository' = None,
            cloud_repo: 'SqliteCloudRepository' = None,
            history_repo: 'SqliteHistoryRepository' = None,
            album_repo: 'SqliteAlbumRepository' = None,
            artist_repo: 'SqliteArtistRepository' = None,
            parent=None
    ):
        """
        Initialize the playback service.

        Args:
            db_manager: Database manager (deprecated, for backward compat)
            config_manager: Configuration manager for settings
            cover_service: Cover service for album art
            online_download_service: Service for downloading online tracks (QQ Music)
            event_bus: Event bus for event publishing (defaults to singleton)
            track_repo: Track repository
            favorite_repo: Favorite repository
            queue_repo: Queue repository
            cloud_repo: Cloud repository
            history_repo: History repository
            album_repo: Album repository
            artist_repo: Artist repository
            parent: Optional parent QObject
        """
        super().__init__(parent)

        self._db = db_manager
        self._config = config_manager
        self._cover_service = cover_service
        self._online_download_service = online_download_service
        self._track_repo = track_repo
        self._favorite_repo = favorite_repo
        self._queue_repo = queue_repo
        self._cloud_repo = cloud_repo
        self._history_repo = history_repo
        self._album_repo = album_repo
        self._artist_repo = artist_repo
        if self._config and hasattr(self._config, "get_audio_engine"):
            backend_type = self._config.get_audio_engine()
        else:
            backend_type = PlayerEngine.BACKEND_MPV
        self._engine = PlayerEngine(backend_type=backend_type)
        self._event_bus = event_bus or EventBus.instance()

        # Playback state
        self._current_source = "local"  # "local" or "cloud"
        self._cloud_account: Optional["CloudAccount"] = None
        self._cloud_files: List["CloudFile"] = []
        self._cloud_files_by_id: dict = {}  # O(1) lookup by file_id
        self._downloaded_files: dict = {}  # cloud_file_id -> local_path

        # Current track ID for history
        self._current_track_id: Optional[int] = None

        # Online download workers (song_mid -> QThread)
        self._online_download_workers: dict = {}
        self._online_download_lock = threading.Lock()

        # Queue save debouncing
        self._save_queue_timer = None
        self._pending_save = False

        # Connect internal signal for thread-safe metadata updates
        self._metadata_processed.connect(self._on_metadata_processed)
        self._metadata_batch_complete.connect(self._on_metadata_batch_complete)

        # NOTE: _db_lock removed - DBWriteWorker now handles serialization

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

        # Connect EventBus track_needs_download for retry functionality
        self._event_bus.track_needs_download.connect(self._on_track_needs_download)

    def _connect_download_service_signals(self):
        """Connect CloudDownloadService signals to EventBus."""
        from services.cloud.download_service import CloudDownloadService

        service = CloudDownloadService.instance()
        service.download_started.connect(self._event_bus.download_started.emit)
        service.download_progress.connect(self._event_bus.download_progress.emit)
        service.download_completed.connect(self._event_bus.download_completed.emit)
        service.download_error.connect(self._event_bus.download_error.emit)

        # Handle cloud download errors - mark item as failed
        self._event_bus.download_error.connect(self._on_cloud_download_error)

        # Connect to metadata_updated to update play_queue
        self._event_bus.metadata_updated.connect(self._on_metadata_updated)

        # Connect to online_track_metadata_loaded to update play_queue for online tracks
        self._event_bus.online_track_metadata_loaded.connect(self._on_online_track_metadata_loaded)

        # Connect to track_deleted to remove from play queue
        self._event_bus.track_deleted.connect(self._on_track_deleted)

        # Connect to tracks_deleted for batch removal from play queue
        self._event_bus.tracks_deleted.connect(self._on_tracks_deleted)

    def _on_metadata_updated(self, track_id: int):
        """Handle metadata update from manual edit - update play_queue."""
        # Get updated track from database
        track = self._track_repo.get_by_id(track_id)
        if not track:
            return

        # Update all playlist items with this track_id
        updated_indices = self._engine.update_item_metadata(
            track_id=track_id,
            title=track.title,
            artist=track.artist,
            album=track.album,
            duration=track.duration,
            cover_path=track.cover_path
        )

        # Schedule a debounced save if any item was updated
        if updated_indices:
            self._schedule_save_queue()

        # Check if current track was updated
        current_idx = self._engine.current_index
        if current_idx in updated_indices:
            current_item = self._engine.current_playlist_item
            if current_item:
                self._event_bus.emit_track_change(current_item)

    def _on_online_track_metadata_loaded(self, song_mid: str, metadata: dict):
        """Handle online track metadata loaded - update play_queue.

        Args:
            song_mid: Song MID
            metadata: Metadata dict with title, artist, album, duration, etc.
        """
        # Update playlist items that match this song_mid (stored in cloud_file_id)
        updated_indices = self._engine.update_item_metadata(
            cloud_file_id=song_mid,
            title=metadata.get("title"),
            artist=metadata.get("artist"),
            album=metadata.get("album"),
            duration=metadata.get("duration"),
            needs_metadata=False
        )

        # Schedule a debounced save if any item was updated
        # This batches multiple metadata updates into a single save
        if updated_indices:
            self._schedule_save_queue()

        # Note: We don't emit track_change here because:
        # 1. For downloads: on_cloud_file_downloaded already handles this via play_after_download
        # 2. The metadata update is already reflected in the playlist item

    def _on_track_deleted(self, track_id: int):
        """
        Handle track deletion - remove from play queue.

        Args:
            track_id: ID of the deleted track
        """
        logger.info(f"[PlaybackService] Track deleted, removing from queue: {track_id}")

        # Remove all items with this track_id from the queue
        removed_indices = self._engine.remove_playlist_item_by_track_id(track_id)

        if removed_indices:
            logger.info(f"[PlaybackService] Removed {len(removed_indices)} item(s) from queue")
            # Save the updated queue
            self.save_queue()
            # Emit playlist changed signal
            self._engine.playlist_changed.emit()

    def _on_tracks_deleted(self, track_ids: List[int]):
        """
        Handle batch track deletion - remove from play queue efficiently.

        Args:
            track_ids: List of deleted track IDs
        """
        if not track_ids:
            return

        logger.info(f"[PlaybackService] Batch track deletion: {len(track_ids)} tracks")

        # Remove all items with matching track_ids from the queue
        removed_indices = self._engine.remove_playlist_items_by_track_ids(track_ids)

        if removed_indices:
            logger.info(f"[PlaybackService] Removed {len(removed_indices)} item(s) from queue")
            # Save the updated queue
            self.save_queue()
            # Emit playlist changed signal
            self._engine.playlist_changed.emit()

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
        self.apply_audio_effects(self._config.get_audio_effects())

    def apply_audio_effects(self, effects: dict):
        """Apply and persist global audio effects settings."""
        state = AudioEffectsState(
            enabled=bool(effects.get("enabled", True)),
            eq_bands=list(effects.get("eq_bands", [])),
            bass_boost=float(effects.get("bass_boost", 0.0)),
            treble_boost=float(effects.get("treble_boost", 0.0)),
            reverb_level=float(effects.get("reverb_level", 0.0)),
            stereo_enhance=float(effects.get("stereo_enhance", 0.0)),
        )
        self._engine.backend.set_audio_effects(state)
        self._config.set_audio_effects(
            {
                "enabled": state.enabled,
                "eq_bands": state.eq_bands,
                "bass_boost": state.bass_boost,
                "treble_boost": state.treble_boost,
                "reverb_level": state.reverb_level,
                "stereo_enhance": state.stereo_enhance,
            }
        )

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

    def _filter_and_convert_tracks(self, tracks: List[Track]) -> List[PlaylistItem]:
        """
        Filter and convert tracks to playlist items.

        This helper method consolidates the common logic for:
        - Filtering out invalid tracks
        - Checking file existence for local tracks
        - Including online tracks (QQ Music)
        - Converting Track to PlaylistItem

        Args:
            tracks: List of Track objects to process

        Returns:
            List of PlaylistItem objects
        """
        items = []
        # Pre-build path existence cache to avoid per-track disk I/O
        local_paths = set()
        for track in tracks:
            if track and track.path:
                local_paths.add(track.path)
        existing_paths = {p for p in local_paths if Path(p).exists()}

        for track in tracks:
            if not track or not track.id or track.id <= 0:
                continue

            # QQ items stay in the queue even when they still need download, but
            # downloaded QQ files should be treated as ready local files.
            has_local_file = bool(track.path) and track.path in existing_paths
            is_online = track.source == TrackSource.QQ and not has_local_file
            if is_online or (track.path and track.path in existing_paths):
                items.append(PlaylistItem.from_track(track))

        return items

    def _iter_library_track_batches(
            self, source: TrackSource | str | None = None, page_size: Optional[int] = None
    ):
        """Yield library tracks in bounded batches to avoid unbounded SELECT * loads."""
        batch_size = page_size or self.LIBRARY_PAGE_SIZE
        total_count = self._track_repo.get_track_count(source=source)
        offset = 0

        while offset < total_count:
            tracks = self._track_repo.get_all(limit=batch_size, offset=offset, source=source)
            if not tracks:
                break
            yield tracks
            offset += len(tracks)

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
        """Stop playback and cleanup download tasks."""
        self._engine.stop()
        # Cleanup any ongoing download tasks
        self.cleanup_download_workers()

    def cleanup_download_workers(self):
        """Clean up all online download workers."""
        logger.info("[PlaybackService] Cleaning up online download workers")
        with self._online_download_lock:
            for song_mid, worker in list(self._online_download_workers.items()):
                if worker.isRunning():
                    worker.requestInterruption()
                    worker.quit()
                    if not worker.wait(1000):
                        logger.warning(f"[PlaybackService] Worker did not stop in time, terminating: {song_mid}")
                        worker.terminate()
                        if not worker.wait(1000):
                            logger.error(f"[PlaybackService] Worker still running after terminate timeout: {song_mid}")
            self._online_download_workers.clear()

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

        Handles both local files and online tracks (QQ Music).
        Online tracks (empty path) will be downloaded before playback.

        Args:
            track_id: Database track ID
        """
        track = self._track_repo.get_by_id(track_id)
        if not track:
            logger.error(f"[PlaybackService] Track not found: {track_id}")
            return

        has_local_file = bool(track.path) and Path(track.path).exists()
        is_online_track = track.source == TrackSource.QQ and not has_local_file

        # For local tracks with path, verify file exists
        if not is_online_track and (not track.path or not Path(track.path).exists()):
            logger.error(f"[PlaybackService] File not found: {track.path}")
            return

        self._set_source("local")

        # Clear playlist and load library
        self._engine.clear_playlist()
        self._engine.cleanup_temp_files()

        items = []
        start_index = 0
        for tracks in self._iter_library_track_batches():
            batch_items = self._filter_and_convert_tracks(tracks)
            batch_item_ids = [item.track_id for item in batch_items]
            if track_id in batch_item_ids:
                start_index = len(items) + batch_item_ids.index(track_id)
            items.extend(batch_items)

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

        Handles both local files and online tracks.

        Args:
            track_ids: List of track IDs
            start_index: Index to start playback from
        """
        self._set_source("local")
        self._engine.clear_playlist()

        # Batch-load all tracks at once
        tracks = self._track_repo.get_by_ids(track_ids)
        items = self._filter_and_convert_tracks(tracks)

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

        items = []
        for tracks in self._iter_library_track_batches():
            items.extend(self._filter_and_convert_tracks(tracks))
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

        # self._set_source("local")

        tracks = self._track_repo.get_playlist_tracks(playlist_id)
        items = self._filter_and_convert_tracks(tracks)
        self._engine.load_playlist_items(items)

        if self._engine.is_shuffle_mode() and items:
            self._engine.shuffle_and_play()

        # self._config.set_playback_source("local")

    def play_playlist_track(self, playlist_id: int, track_id: int):
        """
        Play a specific track from a playlist.

        Args:
            playlist_id: Playlist ID
            track_id: Track ID to play
        """
        self._set_source("local")

        tracks = self._track_repo.get_playlist_tracks(playlist_id)
        items = self._filter_and_convert_tracks(tracks)
        start_index = 0
        for i, item in enumerate(items):
            if item.track_id == track_id:
                start_index = i
                break

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
        tracks = self._favorite_repo.get_favorites()
        items = self._filter_and_convert_tracks(tracks)
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
        self._cloud_files_by_id = {cf.file_id: cf for cf in self._cloud_files}
        self._set_source("cloud")

        # Build playlist items
        items = []
        start_index = 0

        for i, cf in enumerate(self._cloud_files):
            local_path = self._get_cached_path(cf.file_id)
            item = PlaylistItem.from_cloud_file(cf, account.id, local_path, provider=account.provider)
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
        self._cloud_files_by_id = {cf.file_id: cf for cf in cloud_files}
        self._set_source("cloud")

        # Batch-load all tracks by cloud file IDs
        cloud_file_ids = [cf.file_id for cf in cloud_files]
        tracks_by_cloud_id = self._track_repo.get_by_cloud_file_ids(cloud_file_ids)

        # Build playlist items - fast path, no blocking operations
        items = []
        files_to_process = []  # Files that need background metadata processing

        for i, cf in enumerate(cloud_files):
            local_path = ""
            if i == start_index and first_file_path:
                local_path = first_file_path
                self._downloaded_files[cf.file_id] = local_path
            else:
                local_path = self._get_cached_path(cf.file_id)

            item = PlaylistItem.from_cloud_file(cf, account.id, local_path, provider=account.provider)

            # For already downloaded files, try fast path first
            if local_path:
                # Try to get existing track record (fast batch lookup)
                track = tracks_by_cloud_id.get(cf.file_id)
                if track:
                    item.track_id = track.id
                    item.title = track.title or item.title
                    item.artist = track.artist or item.artist
                    item.album = track.album or item.album
                    item.duration = track.duration or item.duration
                    item.cover_path = track.cover_path
                    item.needs_metadata = False
                else:
                    # No existing record - defer metadata extraction to background
                    files_to_process.append((cf.file_id, local_path, account.provider))
                    item.needs_metadata = True

            items.append(item)

        # Start playback immediately
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

        # Process metadata in background thread
        if files_to_process:
            self._process_metadata_async(files_to_process)

    def on_cloud_file_downloaded(self, cloud_file_id: str, local_path: str):
        """
        Called when a cloud file has been downloaded.

        Args:
            cloud_file_id: Cloud file ID
            local_path: Local path of downloaded file
        """
        # Check if this is an online track (QQ Music) by looking up the playlist item
        # QQ Music downloads are handled by on_online_track_downloaded
        for item in self._engine.playlist_items:
            if item.cloud_file_id == cloud_file_id:
                if item.source == TrackSource.QQ:
                    logger.debug(f"[PlaybackService] Skipping on_cloud_file_downloaded for QQ Music track: {cloud_file_id}")
                    return
                break

        self._downloaded_files[cloud_file_id] = local_path

        # Update cloud_files table with local_path (fast DB operation)
        if self._cloud_account:
            self._cloud_repo.update_file_local_path(
                cloud_file_id, self._cloud_account.id, local_path
            )

        # Determine provider
        provider = self._cloud_account.provider if self._cloud_account else "quark"

        # Process metadata in background thread
        self._process_metadata_async([(cloud_file_id, local_path, provider)])

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
            # For cloud files, get cloud_file_id and cloud_account_id from current item
            if track_id is None:
                current_item = self._engine.current_playlist_item
                if current_item:
                    cloud_file_id = current_item.cloud_file_id
                    cloud_account_id = current_item.cloud_account_id

        if track_id is None and cloud_file_id is None:
            return False

        if track_id:
            if self._favorite_repo.is_favorite(track_id=track_id):
                self._favorite_repo.remove_favorite(track_id=track_id)
                self._event_bus.emit_favorite_change(track_id, False, is_cloud=False)
                return False
            else:
                self._favorite_repo.add_favorite(track_id=track_id)
                self._event_bus.emit_favorite_change(track_id, True, is_cloud=False)
                return True
        else:
            if self._favorite_repo.is_favorite(cloud_file_id=cloud_file_id):
                self._favorite_repo.remove_favorite(cloud_file_id=cloud_file_id)
                self._event_bus.emit_favorite_change(cloud_file_id, False, is_cloud=True)
                return False
            else:
                self._favorite_repo.add_favorite(
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

        return self._favorite_repo.is_favorite(track_id=track_id, cloud_file_id=cloud_file_id)

    # ===== Queue Persistence =====

    def _schedule_save_queue(self, delay_ms: int = 100):
        """
        Schedule a queue save with debouncing.

        If another save is scheduled before this one executes, it will be reset.
        This is useful when multiple items are being added/updated in quick succession.

        Args:
            delay_ms: Delay in milliseconds before saving (default: 100ms)
        """
        if self._save_queue_timer is None:
            self._save_queue_timer = QTimer()
            self._save_queue_timer.setSingleShot(True)
            self._save_queue_timer.timeout.connect(self._on_save_queue_timeout)

        # Stop any pending timer
        self._save_queue_timer.stop()
        self._pending_save = True

        # Schedule new save
        self._save_queue_timer.start(delay_ms)

    def _on_save_queue_timeout(self):
        """Handle save queue timer timeout."""
        if self._pending_save:
            self.save_queue()
            self._pending_save = False

    def save_queue(self):
        """Save the current play queue to database."""
        items = self._engine.playlist_items
        if not items:
            self.clear_saved_queue()
            return

        current_idx = self._engine.current_index

        # Convert to PlayQueueItem list
        queue_items = []
        for i, item in enumerate(items):
            queue_item = item.to_play_queue_item(i)
            queue_items.append(queue_item)

        # DBWriteWorker handles serialization
        self._queue_repo.save(queue_items)

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
        queue_items = self._queue_repo.load()
        if not queue_items:
            return False

        # Convert to PlaylistItem list (pure conversion, no DB access)
        items = [PlaylistItem.from_play_queue_item(item) for item in queue_items]

        # Enrich metadata from track repository
        if self._track_repo:
            items = [self._enrich_queue_item_metadata(item) for item in items]

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
                self._cloud_account = self._cloud_repo.get_account_by_id(target_item.cloud_account_id)
        else:
            self._set_source("local")

        # Load queue into engine
        self._engine.load_playlist_items(items)

        # Clamp index to valid range
        if saved_index < 0 or saved_index >= len(items):
            saved_index = 0

        # Restore play mode and current index
        try:
            mode = PlayMode(saved_mode)
            self._engine.restore_state(mode, saved_index)
        except ValueError:
            pass

        # Load track at saved index (but don't play)
        if 0 <= saved_index < len(items):
            self._engine.load_track_at(saved_index)

        return True

    def _enrich_queue_item_metadata(self, item: PlaylistItem) -> PlaylistItem:
        """
        Enrich PlaylistItem with metadata from track repository.

        Args:
            item: PlaylistItem to enrich

        Returns:
            Enriched PlaylistItem
        """
        if not self._track_repo:
            return item

        track = None

        # For local tracks with track_id, get by track_id
        if item.track_id and item.is_local:
            track = self._track_repo.get_by_id(item.track_id)
        # For online/cloud tracks, try to get by cloud_file_id
        elif item.is_cloud and item.cloud_file_id:
            track = self._track_repo.get_by_cloud_file_id(item.cloud_file_id)
        # For local files without track_id, try to find by path
        elif item.local_path and not item.cloud_file_id:
            track = self._track_repo.get_by_path(item.local_path)

        if track:
            # Determine needs_download based on source and file existence
            from pathlib import Path
            local_path = track.path or item.local_path
            file_exists = local_path and Path(local_path).exists()
            needs_download = False

            if item.source == TrackSource.QQ:
                needs_download = not file_exists
                if not file_exists:
                    local_path = ""
            elif item.source in (TrackSource.QUARK, TrackSource.BAIDU):
                if item.cloud_file_id and not file_exists:
                    needs_download = True
                    local_path = ""

            return item.with_metadata(
                cover_path=track.cover_path,
                title=track.title or item.title,
                artist=track.artist or item.artist,
                album=track.album or item.album,
                duration=track.duration or item.duration,
                local_path=local_path,
                track_id=track.id or item.track_id,
                needs_download=needs_download,
            )

        return item

    def clear_saved_queue(self):
        """Clear the saved play queue from database."""
        self._queue_repo.clear()
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
            existing = self._track_repo.get_by_path(str(file_path))
            if existing:
                continue

            metadata = MetadataService.extract_metadata(str(file_path))

            cover_path = None
            if metadata.get("cover"):
                cache_dir = get_cache_dir('covers')
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

            self._track_repo.add(track)
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
                self._history_repo.add(item.track_id)
            elif item.is_cloud and item.local_path:
                track = self._track_repo.get_by_path(item.local_path)
                if not track:
                    track = self._track_repo.get_by_cloud_file_id(item.cloud_file_id)

                if track and track.id:
                    self._history_repo.add(track.id)
                    # Update PlaylistItem with track_id if not set
                    if not item.track_id:
                        item.track_id = track.id
                        self.save_queue()
                else:
                    # Create a new Track record for this cloud file
                    new_track = Track(
                        path=item.local_path,
                        title=item.title,
                        artist=item.artist,
                        album=item.album,
                        duration=item.duration,
                        cloud_file_id=item.cloud_file_id,
                        source=item.source,  # Already TrackSource
                    )
                    track_id = self._track_repo.add(new_track)

                    if track_id:
                        self._history_repo.add(track_id)
                        # Update PlaylistItem with track_id and save queue
                        item.track_id = track_id
                        self.save_queue()

            # Preload next track
            self._preload_next_cloud_track()

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

    def _on_track_needs_download(self, item):
        """Handle track that needs download."""
        # Clear download_failed state when retrying
        if isinstance(item, dict):
            cloud_file_id = item.get("cloud_file_id")
            if cloud_file_id:
                self._engine.update_playlist_item(
                    cloud_file_id=cloud_file_id,
                    download_failed=False,
                    needs_download=True,
                )
            source_str = item.get("source", "Local")
        else:
            item.download_failed = False
            item.needs_download = True
            source_str = item.source.value

        from domain.track import TrackSource
        try:
            source = TrackSource(source_str)
        except ValueError:
            source = TrackSource.LOCAL

        if source == TrackSource.QQ:
            self._download_online_track(item if hasattr(item, 'source') else PlaylistItem.from_dict(item))
        else:
            self._download_cloud_track(item if hasattr(item, 'source') else PlaylistItem.from_dict(item))

    def _download_online_track(self, item: PlaylistItem):
        """Download an online track."""
        from services.online import OnlineDownloadService

        song_mid = item.cloud_file_id
        worker = None

        # Check if already downloading this song - atomically check and reserve slot
        with self._online_download_lock:
            if song_mid in self._online_download_workers:
                existing = self._online_download_workers[song_mid]
                if existing.isRunning():
                    logger.info(f"[PlaybackService] Already downloading: {song_mid}")
                    return
                else:
                    # Clean up finished worker properly
                    del self._online_download_workers[song_mid]
                    existing.deleteLater()

            # Use injected download service
            if not self._online_download_service:
                logger.error("[PlaybackService] Online download service not available")
                # Skip to next track - need to release lock first
                self._engine.play_next()
                return

            # Create worker while holding lock to prevent race condition
            logger.info(f"[PlaybackService] Downloading online track: {song_mid}")

            # Download in background thread
            from PySide6.QtCore import QThread

            class OnlineDownloadWorker(QThread):
                download_finished = Signal(str, str)  # (song_mid, local_path) - path is empty if failed

                def __init__(self, service, song_mid, title):
                    super().__init__()
                    self._service = service
                    self._song_mid = song_mid
                    self._title = title

                def run(self):
                    path = self._service.download(self._song_mid, self._title)
                    # Always emit, even if path is None (failed)
                    self.download_finished.emit(self._song_mid, path or "")

            worker = OnlineDownloadWorker(
                self._online_download_service,
                song_mid,
                item.title
            )

            # Handle download result
            def on_download_finished(mid, path):
                self.on_online_track_downloaded(mid, path)

            # Clean up worker ONLY after thread has fully stopped
            def on_thread_finished():
                with self._online_download_lock:
                    if song_mid in self._online_download_workers:
                        worker_obj = self._online_download_workers.pop(song_mid)
                        worker_obj.deleteLater()

            # Connect signals - use AutoConnection (default) for thread safety
            worker.download_finished.connect(on_download_finished)
            worker.finished.connect(on_thread_finished)

            # Store in dict before starting
            self._online_download_workers[song_mid] = worker

        # Start worker outside lock to avoid blocking
        worker.start()

    def _download_cloud_track(self, item: PlaylistItem):
        """Download a cloud track."""
        from services.cloud.download_service import CloudDownloadService

        if not self._cloud_account:
            logger.error("[PlaybackService] No cloud account for download")
            if item.cloud_account_id:
                self._cloud_account = self._cloud_repo.get_account_by_id(item.cloud_account_id)
                if not self._cloud_account:
                    return
            else:
                return

        service = CloudDownloadService.instance()
        service.set_download_dir(self._config.get_cloud_download_dir())

        # Find the CloudFile - O(1) lookup
        cloud_file = self._cloud_files_by_id.get(item.cloud_file_id)

        if not cloud_file:
            cloud_file = self._cloud_repo.get_file_by_file_id(item.cloud_file_id)
            if not cloud_file:
                logger.error(f"[PlaybackService] CloudFile not found: {item.cloud_file_id}")
                return

        if cloud_file:
            service.download_file(cloud_file, self._cloud_account)

    def _on_cloud_download_error(self, file_id: str, error_message: str):
        """Handle cloud file download error - mark item as failed and skip."""
        logger.warning(f"[PlaybackService] Cloud download failed: {file_id} - {error_message}")

        # Mark as failed in engine
        self._engine.update_playlist_item(
            cloud_file_id=file_id,
            needs_download=True,
            download_failed=True,
        )

        # Skip if this is the current track
        current_item = self._engine.current_playlist_item
        if current_item and current_item.cloud_file_id == file_id:
            self._engine.play_next()

        self._schedule_save_queue()

    def on_online_track_downloaded(self, song_mid: str, local_path: str):
        """
        Called when an online track has been downloaded.

        Args:
            song_mid: Song MID
            local_path: Local path of downloaded file (empty if failed)
        """
        # Handle download failure
        if not local_path:
            logger.warning(f"[PlaybackService] Online track download failed: {song_mid}")
            # Mark as failed instead of removing
            self._engine.update_playlist_item(
                cloud_file_id=song_mid,
                needs_download=True,
                download_failed=True,
            )
            # Skip to next track if this was the current track
            current_item = self._engine.current_playlist_item
            if current_item and current_item.cloud_file_id == song_mid:
                logger.warning(f"[PlaybackService] Current track failed to download, skipping: {song_mid}")
                self._engine.play_next()
            self._schedule_save_queue()
            return

        logger.info(f"[PlaybackService] Online track downloaded: {song_mid} -> {local_path}")

        # Save to library and get track_id
        track_id = self._save_online_track_to_library(song_mid, local_path)

        # Update playlist item in engine
        track = None
        if track_id:
            track = self._track_repo.get_by_id(track_id)

        if track:
            updated_index = self._engine.update_playlist_item(
                cloud_file_id=song_mid,
                local_path=local_path,
                track_id=track.id,
                title=track.title,
                artist=track.artist,
                album=track.album,
                duration=track.duration,
                needs_download=False,
                needs_metadata=False,
                expected_index=self._engine.current_index
            )
        else:
            updated_index = self._engine.update_playlist_item(
                cloud_file_id=song_mid,
                local_path=local_path,
                needs_download=False,
                expected_index=self._engine.current_index
            )

        # Play if this is current track
        # Note: play_after_download already emits current_track_changed signal,
        # which is forwarded to EventBus by _on_track_changed handler.
        # No need to emit track_change here to avoid duplicate events.
        if updated_index is not None and updated_index == self._engine.current_index:
            self._engine.play_after_download(updated_index, local_path)

        # Save queue to persist the updated metadata
        # self.save_queue()

    def _save_online_track_to_library(self, song_mid: str, local_path: str) -> Optional[int]:
        """
        Save downloaded online track to library.

        Updates existing track if found by cloud_file_id, otherwise creates new.

        Args:
            song_mid: Song MID
            local_path: Local file path

        Returns:
            Track ID if saved successfully
        """
        from pathlib import Path
        from services.metadata.metadata_service import MetadataService

        if not local_path or not Path(local_path).exists():
            return None

        # Check if track already exists by cloud_file_id (song_mid)
        existing = self._track_repo.get_by_cloud_file_id(song_mid)
        if existing:
            # Update existing track with local path
            self._track_repo.update_path(existing.id, local_path)
            logger.info(f"[PlaybackService] Updated existing track {existing.id} with local path")
            return existing.id

        # Extract metadata from file
        metadata = MetadataService.extract_metadata(local_path)

        title = metadata.get("title") or Path(local_path).stem
        artist = metadata.get("artist") or ""
        album = metadata.get("album") or ""
        duration = metadata.get("duration") or 0.0

        # Check if track already exists (by path)
        existing = self._track_repo.get_by_path(local_path)
        if existing:
            return existing.id

        # Create new track
        from domain.track import Track, TrackSource
        track = Track(
            path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,  # Store song_mid as cloud_file_id
            source=TrackSource.QQ,  # Online music from QQ
        )

        # DBWriteWorker handles serialization
        track_id = self._track_repo.add(track)
        return track_id

    def _preload_next_cloud_track(self):
        """Preload the next track in the queue (cloud or online)."""
        # TODO: delay

        # Don't preload if stopped
        if self._engine.state == PlaybackState.STOPPED:
            return

        # Single track loop modes - don't preload
        if self._engine.play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            return

        # Get next item
        next_item = self._engine.get_next_item()
        if not next_item:
            return

        # Skip if not needing download or local file already exists
        if not next_item.needs_download or (next_item.local_path and Path(next_item.local_path).exists()):
            return

        # Handle online music preload
        if next_item.source == TrackSource.QQ:
            self._preload_online_track(next_item)
            return

        # Handle cloud file preload
        if next_item.is_cloud:
            self._preload_cloud_track(next_item)

    def _preload_online_track(self, item: PlaylistItem):
        """Preload an online track."""
        # Skip if already downloaded
        if item.local_path:
            return

        # Skip if already downloading
        song_mid = item.cloud_file_id
        with self._online_download_lock:
            if song_mid in self._online_download_workers and self._online_download_workers[song_mid].isRunning():
                return

        logger.info(f"[PlaybackService] Preloading online track: {item.title}")
        self._download_online_track(item)

    def _preload_cloud_track(self, item: PlaylistItem):
        """Preload a cloud track."""
        from services.cloud.download_service import CloudDownloadService

        # Skip if already downloaded
        if item.local_path:
            return

        service = CloudDownloadService.instance()
        if service.is_downloading(item.cloud_file_id):
            return

        # Find the CloudFile
        cloud_file = None
        for cf in self._cloud_files:
            if cf.file_id == item.cloud_file_id:
                cloud_file = cf
                break

        if not cloud_file:
            cloud_file = self._cloud_repo.get_file_by_file_id(item.cloud_file_id)

        if not cloud_file:
            return

        # Get cloud account if needed
        account = self._cloud_account
        if not account and item.cloud_account_id:
            account = self._cloud_repo.get_account_by_id(item.cloud_account_id)

        if not account:
            return

        # Start preload
        logger.info(f"[PlaybackService] Preloading cloud track: {item.title}")
        service.set_download_dir(self._config.get_cloud_download_dir())
        service.download_file(cloud_file, account)

    def _save_cloud_track_to_library(self, file_id: str, local_path: str, source: TrackSource = None) -> str:
        """
        Save downloaded cloud track to library with metadata and cover art.

        This method is called AFTER cloud file download completes. It:
        1. Extracts metadata from the downloaded file
        2. Saves embedded cover if present (as fallback)
        3. Fetches cover from online sources (even if embedded cover exists)

        Args:
            file_id: Cloud file ID
            local_path: Local path of downloaded file
            source: Track source (QUARK, BAIDU, or QQ). If None, infers from cloud_account.

        Returns:
            cover_path: Path to the extracted cover art, or None
        """
        # Determine source if not provided
        if source is None:
            if self._cloud_account:
                provider = self._cloud_account.provider.lower()
                if provider == "quark":
                    source = TrackSource.QUARK
                elif provider == "baidu":
                    source = TrackSource.BAIDU
                else:
                    source = TrackSource.LOCAL  # Fallback for unknown providers
            else:
                # Try to get source from current playlist item
                current_item = self._engine.current_playlist_item
                if current_item and current_item.cloud_file_id == file_id:
                    source = current_item.source
                else:
                    source = TrackSource.QQ  # Default fallback
        from services.metadata.metadata_service import MetadataService
        from services.lyrics.lyrics_service import LyricsService
        from utils.helpers import is_filename_like

        # Extract metadata from downloaded file
        metadata = MetadataService.extract_metadata(local_path)
        new_title = metadata.get("title", Path(local_path).stem if local_path else "")
        new_artist = metadata.get("artist", "")
        new_album = metadata.get("album", "")
        new_duration = metadata.get("duration", 0)

        # Check if track already exists
        existing = self._track_repo.get_by_cloud_file_id(file_id)
        if existing:
            # Update path if it's empty or different
            if not existing.path or existing.path != local_path:
                self._track_repo.update_path(existing.id, local_path)
                logger.info(f"[PlaybackService] Updated track {existing.id} path: {local_path}")

            # Check if existing metadata needs update (e.g., title looks like filename or artist is empty)
            needs_update = False
            if is_filename_like(existing.title) or not existing.artist:
                needs_update = True

            if needs_update and (new_artist or not is_filename_like(new_title)):
                # Update existing track with better metadata
                self._track_repo.update_fields(
                    existing.id,
                    title=new_title if not is_filename_like(new_title) else None,
                    artist=new_artist if new_artist else None,
                    album=new_album if new_album else None,
                )
                logger.info(f"[PlaybackService] Updated track {existing.id} metadata: {new_title} - {new_artist}")

                # Delete old lyrics file if metadata was wrong (will re-download with correct metadata)
                if LyricsService.lyrics_file_exists(local_path):
                    LyricsService.delete_lyrics(local_path)
                    logger.info(f"[PlaybackService] Deleted old lyrics file for re-download with correct metadata")

            # Fetch and update cover if missing
            if not existing.cover_path and self._cover_service:
                cover_path = self._fetch_cover_for_track(file_id, new_title, new_artist, new_album, new_duration, metadata, local_path)
                if cover_path:
                    self._track_repo.update_cover_path(existing.id, cover_path)
                    logger.info(f"[PlaybackService] Updated track {existing.id} cover: {cover_path}")
                    return cover_path

            return existing.cover_path

        existing_by_path = self._track_repo.get_by_path(local_path)
        if existing_by_path:
            self._track_repo.update_fields(existing_by_path.id, cloud_file_id=file_id)

            # Also update metadata if needed
            if is_filename_like(existing_by_path.title) or not existing_by_path.artist:
                if new_artist or not is_filename_like(new_title):
                    self._track_repo.update_fields(
                        existing_by_path.id,
                        title=new_title if not is_filename_like(new_title) else None,
                        artist=new_artist if new_artist else None,
                        album=new_album if new_album else None,
                    )

                    # Delete old lyrics file if metadata was wrong
                    if LyricsService.lyrics_file_exists(local_path):
                        LyricsService.delete_lyrics(local_path)
                        logger.info(f"[PlaybackService] Deleted old lyrics file for re-download with correct metadata")

            # Fetch and update cover if missing
            if not existing_by_path.cover_path and self._cover_service:
                cover_path = self._fetch_cover_for_track(file_id, new_title, new_artist, new_album, new_duration, metadata, local_path)
                if cover_path:
                    self._track_repo.update_cover_path(existing_by_path.id, cover_path)
                    logger.info(f"[PlaybackService] Updated track {existing_by_path.id} cover: {cover_path}")
                    return cover_path

            return existing_by_path.cover_path

        # Create new track
        title = new_title
        artist = new_artist
        album = new_album
        duration = new_duration

        # Check if lyrics file exists with wrong metadata and delete it
        # This happens when lyrics were downloaded before metadata was extracted
        if LyricsService.lyrics_file_exists(local_path):
            # If we now have proper artist info, old lyrics (downloaded with filename as title) should be deleted
            if artist and not is_filename_like(title):
                LyricsService.delete_lyrics(local_path)
                logger.info(f"[PlaybackService] Deleted old lyrics file for new track (metadata now available)")

        # Fetch cover art
        cover_path = None
        if self._cover_service:
            cover_path = self._fetch_cover_for_track(file_id, title, artist, album, duration, metadata, local_path)

        track = Track(
            path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=file_id,
            cover_path=cover_path,
            source=source,  # Use determined source (QUARK, BAIDU, or QQ)
        )

        self._track_repo.add(track)

        # Update albums and artists tables
        # TODO: Move to album_repo/artist_repo incremental update methods
        self._db.update_albums_on_track_added(album, artist, cover_path, duration)
        self._db.update_artists_on_track_added(artist, album, cover_path)

        # Notify UI to refresh
        self._event_bus.tracks_added.emit(1)

        return cover_path

    def _fetch_cover_for_track(self, file_id: str, title: str, artist: str, album: str,
                               duration: float, metadata: dict, local_path: str) -> Optional[str]:
        """
        Fetch cover art for a track from various sources.

        Args:
            file_id: Cloud file ID or song_mid
            title: Track title
            artist: Track artist
            album: Album name
            duration: Track duration
            metadata: Metadata dict from file
            local_path: Local file path

        Returns:
            Cover path if found, None otherwise
        """
        cover_path = None
        embedded_cover_path = None

        # Step 1: Save embedded cover as fallback (if present)
        if metadata.get("cover"):
            embedded_cover_path = self._cover_service.save_cover_from_metadata(
                local_path,
                metadata.get("cover")
            )
            logger.info(f"[PlaybackService] Embedded cover saved: {embedded_cover_path}")

        # Step 2: For QQ Music online tracks, try to get cover directly by song_mid
        if file_id:
            logger.info(f"[PlaybackService] Trying QQ Music cover by song_mid: {file_id}")
            qq_cover_path = self._cover_service.get_online_cover(
                song_mid=file_id,
                artist=artist,
                title=title
            )
            if qq_cover_path:
                logger.info(f"[PlaybackService] QQ Music cover downloaded: {qq_cover_path}")
                cover_path = qq_cover_path
            elif title and artist:
                # Fallback to search if direct fetch failed
                logger.info(f"[PlaybackService] QQ Music cover not found, searching: {title} - {artist}")
                online_cover_path = self._cover_service.fetch_online_cover(
                    title,
                    artist,
                    album,
                    duration
                )
                if online_cover_path:
                    logger.info(f"[PlaybackService] Online cover downloaded: {online_cover_path}")
                    cover_path = online_cover_path
        # Step 3: Fallback to search for tracks without song_mid
        elif title and artist:
            logger.info(f"[PlaybackService] Fetching online cover for: {title} - {artist}")
            online_cover_path = self._cover_service.fetch_online_cover(
                title,
                artist,
                album,
                duration
            )
            if online_cover_path:
                logger.info(f"[PlaybackService] Online cover downloaded: {online_cover_path}")
                cover_path = online_cover_path

        # Use embedded cover as last resort
        if not cover_path and embedded_cover_path:
            logger.info(f"[PlaybackService] Using embedded cover as fallback")
            cover_path = embedded_cover_path

        return cover_path

    def get_track_cover(self, track_path: str, title: str, artist: str, album: str = "", skip_online: bool = False) -> \
    Optional[str]:
        """
        Get cover art for a track.

        Args:
            track_path: Path to the audio file
            title: Track title
            artist: Track artist
            album: Album name
            skip_online: If True, skip online fetching (for cloud files before download completes)

        Returns:
            Path to the cover image, or None
        """
        if self._cover_service:
            return self._cover_service.get_cover(track_path, title, artist, album, skip_online=skip_online)
        return None


    def get_online_track_cover(self, source: str, cloud_file_id: str, artist: str = "", title: str = "") -> Optional[str]:
        if self._cover_service:
            return self._cover_service.get_online_cover(cloud_file_id, "", artist, title)
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

    def _process_metadata_async(self, files: List[tuple]):
        """
        Process metadata for cloud files in background thread.

        Args:
            files: List of (file_id, local_path, provider) tuples
        """
        def process():
            for file_id, local_path, provider in files:
                try:
                    # Determine TrackSource
                    if provider.lower() == "quark":
                        source = TrackSource.QUARK
                    elif provider.lower() == "baidu":
                        source = TrackSource.BAIDU
                    else:
                        source = TrackSource.LOCAL

                    # Extract metadata and save to library
                    cover_path = self._save_cloud_track_to_library(file_id, local_path, source)

                    # Get track from database
                    track = self._track_repo.get_by_cloud_file_id(file_id)

                    # Emit signal to update UI in main thread (skip_save=True)
                    if track:
                        self._metadata_processed.emit(
                            file_id,
                            local_path,
                            track.id,
                            track.title or "",
                            track.artist or "",
                            track.album or "",
                            track.duration or 0.0,
                            cover_path or ""
                        )
                except Exception as e:
                    logger.error(f"[PlaybackService] Error processing metadata for {file_id}: {e}")

            # Save queue once after all metadata processing is complete
            self._metadata_batch_complete.emit()

        # Start background thread
        thread = threading.Thread(target=process, daemon=True)
        thread.start()

    def _on_metadata_processed(
            self,
            cloud_file_id: str,
            local_path: str,
            track_id: int,
            title: str,
            artist: str,
            album: str,
            duration: float,
            cover_path: str
    ):
        """Handle metadata processing completion (called from main thread via signal)."""
        # Update playlist item in engine
        updated_index = self._engine.update_playlist_item(
            cloud_file_id=cloud_file_id,
            local_path=local_path,
            track_id=track_id,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cover_path=cover_path if cover_path else None,
            needs_download=False,
            needs_metadata=False
        )

        # Play if this is current track (for on_cloud_file_downloaded case)
        if updated_index is not None and updated_index == self._engine.current_index:
            self._engine.play_after_download(updated_index, local_path)

        # Note: Queue is saved once after batch completes (see _on_metadata_batch_complete)
        # Preload next cloud track
        self._preload_next_cloud_track()

    def _on_metadata_batch_complete(self):
        """Handle batch metadata processing completion - save queue once."""
        self.save_queue()
        logger.debug(f"[PlaybackService] Batch metadata processing complete, saved queue: {len(self._engine.playlist_items)} items")

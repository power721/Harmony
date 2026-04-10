"""Audio playback engine with pluggable backends (Qt or mpv)."""
import logging
import os
import threading
import importlib
import sys
from pathlib import Path
from typing import Optional, List, Union

from PySide6.QtCore import QObject, Signal

from domain import PlaylistItem
from domain.playback import PlayMode, PlaybackState

# Configure logging
logger = logging.getLogger(__name__)

_BUNDLED_AUDIO_BACKEND_ALL = "all"
_BUNDLED_AUDIO_BACKEND_FILE = Path("bundle") / "audio_backend.txt"
_MAX_TEMP_FILES = 50
_TEMP_FILES_TO_KEEP = 30


def _normalize_bundled_audio_backend_mode(mode: str | None) -> str:
    normalized = (mode or _BUNDLED_AUDIO_BACKEND_ALL).strip().lower()
    if normalized in {_BUNDLED_AUDIO_BACKEND_ALL, "qt", "mpv"}:
        return normalized
    return _BUNDLED_AUDIO_BACKEND_ALL


def _get_bundled_audio_backend_mode() -> str:
    override = os.environ.get("HARMONY_AUDIO_BACKEND_BUNDLE")
    if override:
        return _normalize_bundled_audio_backend_mode(override)

    if not getattr(sys, "frozen", False):
        return _BUNDLED_AUDIO_BACKEND_ALL

    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / _BUNDLED_AUDIO_BACKEND_FILE)
    candidates.append(Path(sys.executable).resolve().parent / _BUNDLED_AUDIO_BACKEND_FILE)

    for candidate in candidates:
        try:
            if candidate.exists():
                return _normalize_bundled_audio_backend_mode(
                    candidate.read_text(encoding="utf-8").strip()
                )
        except OSError:
            logger.debug("[PlayerEngine] Failed to read bundled backend metadata: %s", candidate)

    return _BUNDLED_AUDIO_BACKEND_ALL


class PlayerEngine(QObject):
    """
    Audio playback engine with playlist management + pluggable audio backend.

    Signals:
        position_changed: Emitted when playback position changes (position_ms)
        duration_changed: Emitted when track duration changes (duration_ms)
        state_changed: Emitted when player state changes (PlaybackState)
        current_track_changed: Emitted when current playable track changes
        current_track_pending: Emitted when a selected track still needs download
        volume_changed: Emitted when volume changes (volume 0-100)
        track_finished: Emitted when current track finishes playing
        track_needs_download: Emitted when a cloud track needs to be downloaded
    """

    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(PlaybackState)
    current_track_changed = Signal(object)  # PlaylistItem or dict (backward compat)
    current_track_pending = Signal(object)  # PlaylistItem or dict awaiting download
    volume_changed = Signal(int)
    track_finished = Signal()
    error_occurred = Signal(str)
    play_mode_changed = Signal(PlayMode)  # Emitted when play mode changes
    track_needs_download = Signal(object)  # Emitted when cloud track needs download (PlaylistItem)
    playlist_changed = Signal()  # Emitted when playlist is modified (add/remove/reorder)

    BACKEND_QT = "qt"
    BACKEND_MPV = "mpv"

    def __init__(self, backend_type: str = BACKEND_MPV, parent=None):
        """Initialize the player engine."""
        super().__init__(parent)

        self._backend_type = backend_type or self.BACKEND_MPV
        self._backend = self._create_backend(self._backend_type)

        self._playlist_lock = threading.RLock()  # Lock for playlist state
        self._playlist: List[PlaylistItem] = []  # Current playlist (may be shuffled)
        self._original_playlist: List[PlaylistItem] = []  # Original order for restoration
        self._current_index: int = -1
        self._play_mode: PlayMode = PlayMode.SEQUENTIAL
        self._temp_files: List[str] = []  # Track temporary files for cleanup
        self._pending_seek: int = 0  # Position to seek before playing (in ms)
        self._pending_play: bool = False  # Whether to play after seek
        self._cloud_file_id_to_index: dict = {}  # Dict for O(1) lookup by cloud_file_id
        self._prevent_auto_next: bool = False  # Flag to prevent auto-play next track
        self._media_loaded_flag: bool = False  # Track if media has been loaded for current source
        self._shutdown_complete: bool = False

        # Connect signals
        self._backend.position_changed.connect(self._on_position_changed)
        self._backend.duration_changed.connect(self._on_duration_changed)
        self._backend.state_changed.connect(self._on_backend_state_changed)
        self._backend.media_loaded.connect(self._on_media_loaded)
        self._backend.end_of_media.connect(self._on_end_of_media)
        self._backend.error_occurred.connect(self._on_error)

        # Set initial volume
        self.set_volume(70)

    def __del__(self):
        """Ensure cleanup on destruction."""
        self.shutdown()

    def shutdown(self):
        """Explicitly cleanup backend and temp files once."""
        if getattr(self, "_shutdown_complete", False):
            return
        self._shutdown_complete = True

        backend = getattr(self, "_backend", None)
        if backend is not None:
            try:
                backend.cleanup()
            except Exception as exc:
                logger.error("Error cleaning up backend: %s", exc, exc_info=True)

        try:
            self.cleanup_temp_files()
        except Exception as exc:
            logger.error("Error cleaning up temp files: %s", exc, exc_info=True)

    def _create_backend(self, backend_type: str):
        """Create audio backend and fallback to Qt if mpv is unavailable."""
        if backend_type == self.BACKEND_QT:
            logger.info("[PlayerEngine] Using Qt audio backend")
            return self._create_qt_backend()
        try:
            logger.info("[PlayerEngine] Using mpv audio backend")
            return self._create_mpv_backend()
        except Exception as exc:
            if not self._qt_fallback_enabled():
                raise RuntimeError(
                    "mpv backend initialization failed and Qt fallback is disabled "
                    "(set HARMONY_ENABLE_QT_FALLBACK=1 to enable fallback)."
                ) from exc
            logger.warning(
                "[PlayerEngine] Failed to init mpv backend (%s), falling back to Qt backend",
                exc,
            )
            return self._create_qt_backend()

    @staticmethod
    def _qt_fallback_enabled() -> bool:
        """Whether mpv failures should fall back to QtMultimedia backend."""
        return os.environ.get("HARMONY_ENABLE_QT_FALLBACK", "1") == "1"

    @classmethod
    def is_backend_available(cls, backend_type: str) -> bool:
        """Whether a backend can be instantiated in the current runtime."""
        bundled_mode = _get_bundled_audio_backend_mode()
        if backend_type == cls.BACKEND_MPV:
            if bundled_mode == cls.BACKEND_QT:
                return False
            return importlib.util.find_spec("mpv") is not None
        if backend_type == cls.BACKEND_QT:
            if bundled_mode == cls.BACKEND_MPV:
                return False
            try:
                importlib.import_module("infrastructure.audio.qt_backend")
                return True
            except Exception:
                return False
        return False

    def _create_mpv_backend(self):
        """Import mpv backend lazily so qt-only builds can exclude python-mpv."""
        mpv_module = importlib.import_module("infrastructure.audio.mpv_backend")
        return mpv_module.MpvAudioBackend(parent=self)

    def _create_qt_backend(self):
        """Import Qt backend lazily so mpv-only builds can exclude QtMultimedia."""
        qt_module = importlib.import_module("infrastructure.audio.qt_backend")
        return qt_module.QtAudioBackend(parent=self)

    def _rebuild_cloud_file_id_index(self):
        """Rebuild the cloud_file_id -> index mapping."""
        self._cloud_file_id_to_index.clear()
        for i, item in enumerate(self._playlist):
            if item.cloud_file_id:
                # Only keep first occurrence to avoid ambiguity
                if item.cloud_file_id not in self._cloud_file_id_to_index:
                    self._cloud_file_id_to_index[item.cloud_file_id] = i

    @property
    def playlist(self) -> List[dict]:
        """Get the current playlist as list of dicts (backward compatibility)."""
        with self._playlist_lock:
            return [item.to_dict() for item in self._playlist]

    @property
    def playlist_items(self) -> List[PlaylistItem]:
        """Get the current playlist as PlaylistItem objects."""
        with self._playlist_lock:
            return self._playlist.copy()

    @property
    def current_index(self) -> int:
        """Get the current track index."""
        with self._playlist_lock:
            return self._current_index

    @property
    def current_track(self) -> Optional[dict]:
        """Get the current track as dict (backward compatibility)."""
        with self._playlist_lock:
            if 0 <= self._current_index < len(self._playlist):
                return self._playlist[self._current_index].to_dict()
        return None

    @property
    def current_playlist_item(self) -> Optional[PlaylistItem]:
        """Get the current track as PlaylistItem."""
        with self._playlist_lock:
            if 0 <= self._current_index < len(self._playlist):
                return self._playlist[self._current_index]
        return None

    @property
    def play_mode(self) -> PlayMode:
        """Get the current play mode."""
        return self._play_mode

    @property
    def backend(self):
        """Expose current audio backend instance."""
        return self._backend

    @property
    def position(self) -> int:
        """Expose current audio backend instance."""
        return self._backend.position()

    @property
    def state(self) -> PlaybackState:
        """Get the current player state."""
        if self._backend.is_playing():
            return PlaybackState.PLAYING
        elif self._backend.is_paused():
            return PlaybackState.PAUSED
        return PlaybackState.STOPPED

    @property
    def volume(self) -> int:
        """Get the current volume (0-100)."""
        return self._backend.get_volume()

    def load_playlist(self, tracks: Union[List[dict], List[PlaylistItem]]):
        """
        Load a playlist.

        Args:
            tracks: List of track dictionaries or PlaylistItem objects
        """
        with self._playlist_lock:
            self._playlist = []
            for track in tracks:
                if isinstance(track, PlaylistItem):
                    self._playlist.append(track)
                else:
                    self._playlist.append(PlaylistItem.from_dict(track))
            self._original_playlist = self._playlist.copy()  # Save original order
            self._current_index = -1
            self._rebuild_cloud_file_id_index()
        self.playlist_changed.emit()

    MAX_PLAYLIST_SIZE = 50000

    def load_playlist_items(self, items: List[PlaylistItem]):
        """
        Load a playlist from PlaylistItem objects.

        Args:
            items: List of PlaylistItem objects
        """
        if len(items) > self.MAX_PLAYLIST_SIZE:
            logger.warning(
                f"[Engine] Playlist has {len(items)} items, truncating to {self.MAX_PLAYLIST_SIZE}"
            )
            items = items[:self.MAX_PLAYLIST_SIZE]
        with self._playlist_lock:
            self._playlist = items.copy()
            self._original_playlist = items.copy()  # Save original order
            self._current_index = -1
            self._rebuild_cloud_file_id_index()
        self.playlist_changed.emit()

    def reorder_playlist(self, items: List[PlaylistItem], current_index: int):
        """
        Reorder the playlist while preserving the currently playing track.

        This is used for drag-drop reordering in the queue view.
        Unlike load_playlist_items, this preserves playback state.

        Args:
            items: List of PlaylistItem objects in new order
            current_index: Index of the currently playing track in the new order
        """
        with self._playlist_lock:
            self._playlist = items.copy()
            self._original_playlist = items.copy()  # Update original order to new order
            self._current_index = current_index
            self._rebuild_cloud_file_id_index()
        self.playlist_changed.emit()

    def clear_playlist(self):
        """Clear the playlist."""
        with self._playlist_lock:
            self._playlist.clear()
            self._original_playlist.clear()
            self._cloud_file_id_to_index.clear()
            self._current_index = -1
        self.stop()
        self.playlist_changed.emit()

    def cleanup_temp_files(self):
        """Clean up temporary files from cloud playback."""
        import os
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.error(f"Failed to delete temp file {temp_file}: {e}", exc_info=True)
        self._temp_files.clear()

    def add_temp_file(self, file_path: str):
        """
        Add a temporary file for tracking and cleanup.

        Args:
            file_path: Path to temporary file
        """
        self._temp_files.append(file_path)
        # Prevent unlimited growth - cleanup old files if list gets too large
        if len(self._temp_files) > _MAX_TEMP_FILES:
            self._cleanup_old_temp_files()

    def _cleanup_old_temp_files(self):
        """Clean up old temporary files, keeping only recent ones."""
        import os
        # Keep only the most recent tracked temp files.
        files_to_remove = self._temp_files[:-_TEMP_FILES_TO_KEEP]
        self._temp_files = self._temp_files[-_TEMP_FILES_TO_KEEP:]

        for temp_file in files_to_remove:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                logger.debug(f"Failed to delete old temp file {temp_file}: {e}")

    def add_track(self, track: Union[dict, PlaylistItem]):
        """
        Add a track to the playlist.

        Args:
            track: Track dictionary or PlaylistItem
        """
        with self._playlist_lock:
            if isinstance(track, PlaylistItem):
                item = track
            else:
                item = PlaylistItem.from_dict(track)
            self._playlist.append(item)
            # Update cloud_file_id index if applicable
            if item.cloud_file_id and item.cloud_file_id not in self._cloud_file_id_to_index:
                self._cloud_file_id_to_index[item.cloud_file_id] = len(self._playlist) - 1
        self.playlist_changed.emit()

    def insert_track(self, index: int, track: Union[dict, PlaylistItem]):
        """
        Insert a track at a specific position.

        Args:
            index: Position to insert at
            track: Track dictionary or PlaylistItem
        """
        with self._playlist_lock:
            if 0 <= index <= len(self._playlist):
                item = track if isinstance(track, PlaylistItem) else PlaylistItem.from_dict(track)
                self._playlist.insert(index, item)
                if self._current_index >= index:
                    self._current_index += 1
                # Incremental index update - shift all indices >= index by 1
                for cloud_id, idx in list(self._cloud_file_id_to_index.items()):
                    if idx >= index:
                        self._cloud_file_id_to_index[cloud_id] = idx + 1
                # Add new item's cloud_file_id if present
                if item.cloud_file_id and item.cloud_file_id not in self._cloud_file_id_to_index:
                    self._cloud_file_id_to_index[item.cloud_file_id] = index
        self.playlist_changed.emit()

    def move_track(self, from_index: int, to_index: int):
        """
        Move a track from one position to another in the playlist.

        Args:
            from_index: Current index of the track
            to_index: Target index for the track
        """
        with self._playlist_lock:
            if not (0 <= from_index < len(self._playlist)):
                return
            if to_index < 0:
                to_index = 0
            if to_index > len(self._playlist) - 1:
                to_index = len(self._playlist) - 1
            if from_index == to_index:
                return

            item = self._playlist.pop(from_index)
            self._playlist.insert(to_index, item)

            # Update current index
            if self._current_index == from_index:
                self._current_index = to_index
            elif from_index < self._current_index <= to_index:
                self._current_index -= 1
            elif to_index <= self._current_index < from_index:
                self._current_index += 1

            self._rebuild_cloud_file_id_index()
        self.playlist_changed.emit()

    def remove_track(self, index: int):
        """
        Remove a track from the playlist.

        Args:
            index: Index of track to remove
        """
        need_stop = False
        with self._playlist_lock:
            if 0 <= index < len(self._playlist):
                removed_item = self._playlist.pop(index)
                # Incremental index update - remove the item and shift indices > index
                if removed_item.cloud_file_id and removed_item.cloud_file_id in self._cloud_file_id_to_index:
                    del self._cloud_file_id_to_index[removed_item.cloud_file_id]
                for cloud_id, idx in list(self._cloud_file_id_to_index.items()):
                    if idx > index:
                        self._cloud_file_id_to_index[cloud_id] = idx - 1
                if self._current_index == index:
                    need_stop = True
                    self._current_index = -1
                elif self._current_index > index:
                    self._current_index -= 1
        if need_stop:
            self.stop()
        self.playlist_changed.emit()

    def update_track_path(self, index: int, local_path: str):
        """
        Update the local path for a track (after download completes).

        Args:
            index: Index of track to update
            local_path: New local path
        """
        with self._playlist_lock:
            if 0 <= index < len(self._playlist):
                item = self._playlist[index]
                item.local_path = local_path
                item.needs_download = False

    def update_playlist_item(
        self,
        cloud_file_id: str,
        local_path: str = None,
        track_id: int = None,
        title: str = None,
        artist: str = None,
        album: str = None,
        duration: float = None,
        cover_path: str = None,
        needs_download: bool = False,
        needs_metadata: bool = False,
        download_failed: bool = False,
        expected_index: int = None
    ) -> Optional[int]:
        """
        Update a playlist item by cloud_file_id.

        This method modifies the internal playlist directly (not a copy),
        ensuring changes are persisted when save_queue() is called.

        Args:
            cloud_file_id: Cloud file ID to find the item
            local_path: New local path
            track_id: Track ID from database
            title: Track title
            artist: Track artist
            album: Track album
            duration: Track duration
            cover_path: Path to cover art
            needs_download: Whether file needs download
            needs_metadata: Whether metadata needs extraction
            expected_index: Expected index of the item (for handling duplicates)

        Returns:
            Index of updated item, or None if not found
        """
        with self._playlist_lock:
            matched_indices = []

            if expected_index is not None and 0 <= expected_index < len(self._playlist):
                if self._playlist[expected_index].cloud_file_id == cloud_file_id:
                    matched_indices.append(expected_index)
            elif cloud_file_id in self._cloud_file_id_to_index:
                mapped_index = self._cloud_file_id_to_index[cloud_file_id]
                if 0 <= mapped_index < len(self._playlist):
                    if self._playlist[mapped_index].cloud_file_id == cloud_file_id:
                        matched_indices.append(mapped_index)

            for i, item in enumerate(self._playlist):
                if item.cloud_file_id == cloud_file_id and i not in matched_indices:
                    matched_indices.append(i)

            if not matched_indices:
                return None

            for i in matched_indices:
                item = self._playlist[i]
                if local_path is not None:
                    item.local_path = local_path
                if track_id is not None:
                    item.track_id = track_id
                if title is not None:
                    item.title = title
                if artist is not None:
                    item.artist = artist
                if album is not None:
                    item.album = album
                if duration is not None:
                    item.duration = duration
                if cover_path is not None:
                    item.cover_path = cover_path
                item.needs_download = needs_download
                item.needs_metadata = needs_metadata
                item.download_failed = download_failed

            return matched_indices[0]

    def remove_playlist_item_by_cloud_id(self, cloud_file_id: str) -> Optional[int]:
        """
        Remove a playlist item by cloud_file_id.

        Args:
            cloud_file_id: Cloud file ID to find and remove

        Returns:
            Index of removed item, or None if not found
        """
        with self._playlist_lock:
            # O(1) lookup by cloud_file_id
            i = self._cloud_file_id_to_index.get(cloud_file_id)
            if i is not None and 0 <= i < len(self._playlist):
                item = self._playlist[i]
                if item.cloud_file_id == cloud_file_id:
                    # RLock allows reentrant acquire by remove_track
                    self.remove_track(i)
                    return i
        return None

    def remove_playlist_item_by_track_id(self, track_id: int) -> list[int]:
        """
        Remove all playlist items with the given track_id.

        Args:
            track_id: Track ID to find and remove

        Returns:
            List of removed indices (in descending order)
        """
        with self._playlist_lock:
            indices = []
            for i, item in enumerate(self._playlist):
                if item.track_id == track_id:
                    indices.append(i)

        # Remove from highest index first to maintain valid indices
        for i in sorted(indices, reverse=True):
            self.remove_track(i)

        return indices

    def remove_playlist_items_by_track_ids(self, track_ids: List[int]) -> list[int]:
        """
        Remove all playlist items with the given track_ids efficiently.

        Args:
            track_ids: List of track IDs to find and remove

        Returns:
            List of removed indices (in descending order)
        """
        if not track_ids:
            return []

        # Convert to set for O(1) lookups
        track_id_set = set(track_ids)

        with self._playlist_lock:
            indices = []
            for i, item in enumerate(self._playlist):
                if item.track_id in track_id_set:
                    indices.append(i)

        # Remove from highest index first to maintain valid indices
        for i in sorted(indices, reverse=True):
            self.remove_track(i)

        return indices

    def play(self):
        """Start or resume playback."""
        should_skip_current = False

        with self._playlist_lock:
            if self._current_index < 0 and self._playlist:
                self._current_index = 0

            if 0 <= self._current_index < len(self._playlist):
                item = self._playlist[self._current_index]

                # Check if current track has failed download - auto-skip
                if item.download_failed:
                    logger.info(f"[Engine] Skipping failed track: {item.title}")
                    self.track_finished.emit()
                    return

                # Check if current track needs download or file doesn't exist
                if self._item_needs_download(item):
                    item.needs_download = True
                    self.track_needs_download.emit(item)
                    return
                if self._item_is_missing_local_file(item):
                    self._emit_missing_local_track_error(item)
                    should_skip_current = True
                else:
                    current_index = self._current_index
                    local_path = item.local_path

            else:
                return

        if should_skip_current:
            self.play_next()
            return

        # Load track if not already loaded (outside lock)
        current_source = self._backend.get_source_path()
        if current_source != local_path:
            if not self._load_track_if_match(current_index, item, require_current=True):
                return

        self._backend.play()

    def pause(self):
        """Pause playback."""
        self._backend.pause()

    def stop(self):
        """Stop playback."""
        self._backend.stop()

    def set_prevent_auto_next(self, prevent: bool):
        """Set whether to prevent auto-playing next track."""
        self._prevent_auto_next = prevent

    def play_at(self, index: int):
        """
        Play track at specific index.

        Args:
            index: Index of track to play
        """
        with self._playlist_lock:
            if 0 <= index < len(self._playlist):
                self._current_index = index
                item = self._playlist[index]

                # Check if track has failed download - auto-skip
                if item.download_failed:
                    logger.info(f"[Engine] Skipping failed track at index {index}: {item.title}")
                    return

                # Check if track needs download or file doesn't exist
                if item.needs_download or not item.local_path or not Path(item.local_path).exists():
                    item.needs_download = True
                    item_copy = item
                else:
                    item_copy = None
            else:
                return

        if item_copy:
            self.current_track_pending.emit(item_copy.to_dict())
            self.track_needs_download.emit(item_copy)
            return

        self._load_track(index)
        self._backend.play()

    def play_at_with_position(self, index: int, position_ms: int):
        """
        Load track and seek to position before starting playback.
        This avoids the brief play-from-start issue.

        Args:
            index: Index of track to play
            position_ms: Position to seek to before playing (in milliseconds)
        """
        with self._playlist_lock:
            if 0 <= index < len(self._playlist):
                self._current_index = index
                item = self._playlist[index]

                # Save pending seek for use after download
                self._pending_seek = position_ms
                self._pending_play = True

                # Check if track needs download or file doesn't exist
                if item.needs_download or not item.local_path or not Path(item.local_path).exists():
                    item.needs_download = True
                    item_copy = item
                else:
                    item_copy = None
            else:
                return

        if item_copy:
            self.current_track_pending.emit(item_copy.to_dict())
            self.track_needs_download.emit(item_copy)
            return

        self._load_track(index)
        # Don't call play() here - will play after media is loaded and seeked

    def play_after_download(self, index: int, local_path: str):
        """
        Play a track after download completes.

        Args:
            index: Index of track
            local_path: Downloaded local path
        """
        self.update_track_path(index, local_path)
        metadata = None
        with self._playlist_lock:
            if not (0 <= index < len(self._playlist)):
                return
            item = self._playlist[index]
            expected_item = item
            should_extract_metadata = item.needs_metadata and bool(local_path)

        if should_extract_metadata:
            from services.metadata.metadata_service import MetadataService
            metadata = MetadataService.extract_metadata(local_path)

        with self._playlist_lock:
            if not (0 <= index < len(self._playlist)):
                return
            item = self._playlist[index]
            if item is not expected_item:
                return

            if metadata:
                if metadata.get("title"):
                    item.title = metadata["title"]
                if metadata.get("artist"):
                    item.artist = metadata["artist"]
                if metadata.get("album"):
                    item.album = metadata["album"]
                item.needs_metadata = False

            # Only play if this is the current track
            is_current = index == self._current_index
            item_copy = item.to_dict()

        if is_current:
            # Check if we're already playing this file to avoid interrupting playback
            current_source = self._backend.get_source_path()
            logger.debug(f"[PlayerEngine] play_after_download: index={index}, local_path={local_path}, current_source={current_source}, state={self.state}")

            if current_source == local_path:
                # Same file - just emit track change to update UI metadata
                logger.debug(f"[PlayerEngine] Same file {local_path}, just updating metadata")
                self.current_track_changed.emit(item_copy)
                return

            # Current index still points at this item, so loading the downloaded file is safe
            # even if the backend source is still the previous track after an auto-next.
            self._media_loaded_flag = False  # Reset flag for new source
            self._backend.set_source(local_path)

            # Always use pending play mechanism to wait for media_loaded
            # This fixes race condition where play() is called before media is ready
            if not self._media_loaded_flag:
                self._pending_play = True
                logger.debug(f"[PlayerEngine] Set pending play for index {index}, will play after media loaded")
            else:
                # Media already loaded (rare case), play directly
                self._backend.play()
                logger.debug(f"[PlayerEngine] Media already loaded, playing directly for index {index}")

            self.current_track_changed.emit(item_copy)

    def play_next(self):
        """Play the next track. Manual skip ignores single track loop mode."""
        with self._playlist_lock:
            if not self._playlist:
                return

            remaining = len(self._playlist)

            while remaining > 0:
                remaining -= 1

                # Move to next track (manual skip ignores single track loop mode)
                self._current_index += 1

                if self._current_index >= len(self._playlist):
                    if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                        # Reshuffle for random loop mode
                        if self._play_mode == PlayMode.RANDOM_LOOP:
                            self._shuffle_playlist_locked()
                        self._current_index = 0
                    else:
                        self._current_index = len(self._playlist) - 1
                        self.stop()
                        return

                current_index = self._current_index
                if not (0 <= current_index < len(self._playlist)):
                    return

                item = self._playlist[current_index]

                if self._item_is_missing_local_file(item):
                    self._emit_missing_local_track_error(item)
                    continue

                break
            else:
                self.stop()
                return

        if self._item_needs_download(item):
            validated_item = self._get_playlist_item_if_match(current_index, item)
            if validated_item is None:
                return
            validated_item.needs_download = True
            self.track_needs_download.emit(validated_item)
        elif self._item_has_local_file(item):
            if not self._load_track_if_match(current_index, item):
                return
            self._backend.play()

    def play_previous(self):
        """Play the previous track. Manual skip ignores single track loop mode."""
        with self._playlist_lock:
            if not self._playlist:
                return

        # Check if we should go to previous track or restart current
        # Manual skip ignores single track loop mode
        # Only restart if we have a valid position and it's > 3 seconds
        current_pos = self._backend.position()
        should_restart = current_pos > 3000

        if should_restart:
            self._backend.seek(0)
            # Ensure playback continues if it was playing
            if self._backend.is_playing():
                pass  # Already playing, position change won't stop it
            elif self._backend.is_paused():
                pass  # Stay paused at beginning
            else:
                # Stopped state - need to play
                self._backend.play()
        else:
            with self._playlist_lock:
                remaining = len(self._playlist)

                while remaining > 0:
                    remaining -= 1

                    self._current_index -= 1
                    if self._current_index < 0:
                        if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                            self._current_index = len(self._playlist) - 1
                        else:
                            self._current_index = 0
                            return

                    current_index = self._current_index
                    if not (0 <= current_index < len(self._playlist)):
                        return

                    item = self._playlist[current_index]

                    if self._item_is_missing_local_file(item):
                        self._emit_missing_local_track_error(item)
                        continue

                    break
                else:
                    self.stop()
                    return

            self._load_track(current_index)

            if self._item_needs_download(item):
                item.needs_download = True
                self.track_needs_download.emit(item)
            elif self._item_has_local_file(item):
                self._backend.play()

    def seek(self, position_ms: int):
        """
        Seek to position in current track.

        Args:
            position_ms: Position in milliseconds
        """
        self._backend.seek(max(0, position_ms))

    def position(self) -> int:  # noqa: F811
        """
        Get current playback position.

        Returns:
            Current position in milliseconds
        """
        return self._backend.position()

    def duration(self) -> int:
        """
        Get current track duration.

        Returns:
            Duration in milliseconds
        """
        return self._backend.duration()

    def set_volume(self, volume: int):
        """
        Set volume.

        Args:
            volume: Volume level (0-100)
        """
        volume = max(0, min(100, int(volume)))
        self._backend.set_volume(volume)
        self.volume_changed.emit(volume)

    def set_eq_bands(self, bands: List[float]):
        """Apply equalizer settings to current backend (if supported)."""
        self._backend.set_eq_bands(bands)

    def supports_eq(self) -> bool:
        """Return whether current backend supports equalizer processing."""
        return self._backend.supports_eq()

    def set_play_mode(self, mode: PlayMode):
        """
        Set the playback mode.

        When switching to/from shuffle mode, the playlist is shuffled/restored:
        - Sequential/Loop -> Shuffle: Shuffle queue, current song at front
        - Shuffle -> Sequential/Loop: Restore original order

        Args:
            mode: PlayMode to set
        """
        with self._playlist_lock:
            old_mode = self._play_mode
            old_is_shuffle = old_mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)
            new_is_shuffle = mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)

            # Handle shuffle mode transition
            if new_is_shuffle and not old_is_shuffle:
                # Entering shuffle mode - shuffle the queue
                self._shuffle_playlist_locked()
            elif not new_is_shuffle and old_is_shuffle:
                # Exiting shuffle mode - restore original order
                self._restore_playlist_order_locked()

            self._play_mode = mode
        self.play_mode_changed.emit(mode)

    def _shuffle_playlist(self):
        """Shuffle the playlist with current track at front."""
        with self._playlist_lock:
            self._shuffle_playlist_locked()

    def _shuffle_playlist_locked(self):
        """Shuffle the playlist with current track at front. Must be called with lock held."""
        if not self._playlist:
            return

        # Get current item before shuffling (if any)
        current_item = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None

        # Shuffle (random.shuffle is Fisher-Yates internally)
        import random
        self._playlist = self._original_playlist[:]
        random.shuffle(self._playlist)

        # Move current item to front via O(1) swap instead of pop+insert
        if current_item:
            try:
                idx = self._playlist.index(current_item)
                if idx != 0:
                    self._playlist[idx] = self._playlist[0]
                    self._playlist[0] = current_item
            except ValueError:
                pass

        self._current_index = 0
        self._rebuild_cloud_file_id_index()

    def _restore_playlist_order(self):
        """Restore the playlist to original order."""
        with self._playlist_lock:
            self._restore_playlist_order_locked()

    def _restore_playlist_order_locked(self):
        """Restore the playlist to original order. Must be called with lock held."""
        if not self._original_playlist:
            return

        # Get current item before restoring
        current_item = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None

        # Restore original order
        self._playlist = self._original_playlist.copy()

        # Find current item in restored playlist
        if current_item:
            for i, item in enumerate(self._playlist):
                # Match by track_id for local, or cloud_file_id for cloud
                if item.track_id and current_item.track_id and item.track_id == current_item.track_id:
                    self._current_index = i
                    break
                elif item.cloud_file_id and current_item.cloud_file_id and item.cloud_file_id == current_item.cloud_file_id:
                    self._current_index = i
                    break
            else:
                self._current_index = 0

        self._rebuild_cloud_file_id_index()

    def shuffle_and_play(self, item_to_play: PlaylistItem = None):
        """
        Shuffle the playlist and optionally set a specific item as current.

        This is used when a new song is played while in shuffle mode.

        Args:
            item_to_play: Optional item to place at front of shuffled queue
        """
        with self._playlist_lock:
            if not self._original_playlist:
                return

            import random
            self._playlist = self._original_playlist.copy()
            random.shuffle(self._playlist)

            if item_to_play:
                try:
                    idx = self._playlist.index(item_to_play)
                    self._playlist.pop(idx)
                    self._playlist.insert(0, item_to_play)
                    self._current_index = 0
                except ValueError:
                    self._current_index = 0
            else:
                self._current_index = 0

            self._rebuild_cloud_file_id_index()

    def is_shuffle_mode(self) -> bool:
        """Check if currently in shuffle mode."""
        with self._playlist_lock:
            return self._play_mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)

    def restore_state(self, play_mode: PlayMode, current_index: int):
        """
        Restore player state without starting playback.

        Args:
            play_mode: PlayMode to restore
            current_index: Current track index to restore
        """
        with self._playlist_lock:
            self._play_mode = play_mode
            self._current_index = current_index
        self.play_mode_changed.emit(play_mode)

    def update_item_metadata(self, track_id: int = None, cloud_file_id: str = None,
                             title: str = None, artist: str = None, album: str = None,
                             duration: float = None, cover_path: str = None,
                             needs_metadata: bool = None) -> List[int]:
        """
        Update metadata for playlist items matching track_id or cloud_file_id.

        Args:
            track_id: Track ID to match (for local tracks)
            cloud_file_id: Cloud file ID to match (for cloud tracks)
            title: New title
            artist: New artist
            album: New album
            duration: New duration
            cover_path: New cover path
            needs_metadata: New needs_metadata flag

        Returns:
            List of indices of updated items
        """
        with self._playlist_lock:
            updated_indices = []
            for i, item in enumerate(self._playlist):
                match = False
                if track_id is not None and item.track_id == track_id:
                    match = True
                elif cloud_file_id is not None and item.cloud_file_id == cloud_file_id:
                    match = True

                if match:
                    if title is not None:
                        item.title = title
                    if artist is not None:
                        item.artist = artist
                    if album is not None:
                        item.album = album
                    if duration is not None:
                        item.duration = duration
                    if cover_path is not None:
                        item.cover_path = cover_path
                    if needs_metadata is not None:
                        item.needs_metadata = needs_metadata
                    updated_indices.append(i)
            return updated_indices

    def load_track_at(self, index: int):
        """
        Load track at index without playing.

        Args:
            index: Index of track to load
        """
        with self._playlist_lock:
            valid = 0 <= index < len(self._playlist)
        if valid:
            self._load_track(index)

    def get_next_item(self) -> Optional[PlaylistItem]:
        """
        Get the next playlist item without changing state.

        Returns:
            Next PlaylistItem or None if no next item
        """
        with self._playlist_lock:
            if not self._playlist:
                return None

            # Single track loop modes - next is current
            if self._play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
                if 0 <= self._current_index < len(self._playlist):
                    return self._playlist[self._current_index]
                return None

            # Calculate next index
            next_index = self._current_index + 1

            # Handle end of playlist
            if next_index >= len(self._playlist):
                # Playlist loop modes wrap around
                if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                    next_index = 0
                else:
                    # Sequential mode - no next item
                    return None

            return self._playlist[next_index]

    def _load_track(self, index: int):
        """Load a track for playback."""
        with self._playlist_lock:
            if not (0 <= index < len(self._playlist)):
                return
            item = self._playlist[index]

            # Skip loading if path is empty or file doesn't exist (for cloud files not yet downloaded)
            if self._item_needs_download(item):
                item_dict = item.to_dict()
                self.current_track_pending.emit(item_dict)
                return

            local_path = item.local_path
            item_dict = item.to_dict()

        self._media_loaded_flag = False  # Reset flag for new source
        self._backend.set_source(local_path)
        self.current_track_changed.emit(item_dict)

    def _get_playlist_item_if_match(
        self,
        index: int,
        expected_item: PlaylistItem,
        *,
        require_current: bool = False,
    ) -> Optional[PlaylistItem]:
        with self._playlist_lock:
            if not (0 <= index < len(self._playlist)):
                return None
            if require_current and self._current_index != index:
                return None

            item = self._playlist[index]
            if item is not expected_item:
                return None
            return item

    def _load_track_if_match(
        self,
        index: int,
        expected_item: PlaylistItem,
        *,
        require_current: bool = False,
    ) -> bool:
        item = self._get_playlist_item_if_match(
            index,
            expected_item,
            require_current=require_current,
        )
        if item is None:
            return False

        item_dict = item.to_dict()
        local_path = item.local_path

        self._media_loaded_flag = False
        self._backend.set_source(local_path)
        self.current_track_changed.emit(item_dict)
        return True

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        self.position_changed.emit(position_ms)

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self.duration_changed.emit(duration_ms)

    def _on_backend_state_changed(self, state: int):
        """Handle state change."""
        if state == 1:
            self.state_changed.emit(PlaybackState.PLAYING)
        elif state == 2:
            self.state_changed.emit(PlaybackState.PAUSED)
        else:
            self.state_changed.emit(PlaybackState.STOPPED)

    def _on_media_loaded(self):
        """Handle media loaded event from backend."""
        logger.debug("[PlayerEngine] Media loaded, checking pending seek")
        self._media_loaded_flag = True
        if self._pending_seek > 0:
            logger.debug(f"[PlayerEngine] Pending seek: {self._pending_seek}ms")
            self._backend.seek(self._pending_seek)
            self._pending_seek = 0
        if self._pending_play:
            logger.debug("[PlayerEngine] Executing pending play after media loaded")
            self._pending_play = False
            self._backend.play()

    def _on_end_of_media(self):
        """Handle end-of-media event from backend."""
        self.track_finished.emit()

        # Check if auto-next is prevented
        if self._prevent_auto_next:
            logger.info("[PlayerEngine] Auto-next prevented by sleep timer")
            self._prevent_auto_next = False  # Reset flag
            return

        # Auto-play next based on mode
        if self._play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            # Track loop modes
            self.seek(0)
            self.play()
        elif self._play_mode in (
            PlayMode.SEQUENTIAL,
            PlayMode.PLAYLIST_LOOP,
            PlayMode.RANDOM,
            PlayMode.RANDOM_LOOP,
        ):
            # Modes that advance to next track
            self.play_next()

    def _on_error(self, error_string: str):
        """Handle playback error."""
        self.error_occurred.emit(error_string)

    def _item_has_local_file(self, item: PlaylistItem) -> bool:
        """Whether the playlist item has a playable local file on disk."""
        return bool(item.local_path) and Path(item.local_path).exists()

    def _item_needs_download(self, item: PlaylistItem) -> bool:
        """Whether the playlist item should be handled by the download pipeline."""
        return item.is_cloud and (item.needs_download or not self._item_has_local_file(item))

    def _item_is_missing_local_file(self, item: PlaylistItem) -> bool:
        """Whether a local-library item points to a missing file."""
        return item.is_local and not self._item_has_local_file(item)

    def _emit_missing_local_track_error(self, item: PlaylistItem):
        """Emit a consistent error when a local queue entry no longer exists on disk."""
        track_name = item.title or item.local_path or "Unknown Track"
        message = f"Local track file not found: {track_name}"
        logger.warning("[PlayerEngine] %s", message)
        self.error_occurred.emit(message)

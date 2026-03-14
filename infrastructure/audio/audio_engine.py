"""
Audio playback engine using Qt Multimedia.
"""
import logging

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QObject, Signal
from typing import Optional, List, Union

from domain import PlaylistItem
from domain.playback import PlayMode, PlaybackState


# Configure logging
logger = logging.getLogger(__name__)


class PlayerEngine(QObject):
    """
    Audio playback engine using QMediaPlayer.

    Signals:
        position_changed: Emitted when playback position changes (position_ms)
        duration_changed: Emitted when track duration changes (duration_ms)
        state_changed: Emitted when player state changes (PlaybackState)
        current_track_changed: Emitted when current track changes
        volume_changed: Emitted when volume changes (volume 0-100)
        track_finished: Emitted when current track finishes playing
        track_needs_download: Emitted when a cloud track needs to be downloaded
    """

    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(PlaybackState)
    current_track_changed = Signal(object)  # PlaylistItem or dict (backward compat)
    volume_changed = Signal(int)
    track_finished = Signal()
    error_occurred = Signal(str)
    play_mode_changed = Signal(PlayMode)  # Emitted when play mode changes
    track_needs_download = Signal(object)  # Emitted when cloud track needs download (PlaylistItem)
    playlist_changed = Signal()  # Emitted when playlist is modified (add/remove/reorder)

    def __init__(self, parent=None):
        """Initialize the player engine."""
        super().__init__(parent)

        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)

        self._playlist: List[PlaylistItem] = []  # Current playlist (may be shuffled)
        self._original_playlist: List[PlaylistItem] = []  # Original order for restoration
        self._current_index: int = -1
        self._play_mode: PlayMode = PlayMode.SEQUENTIAL
        self._temp_files: List[str] = []  # Track temporary files for cleanup
        self._pending_seek: int = 0  # Position to seek before playing (in ms)
        self._pending_play: bool = False  # Whether to play after seek

        # Connect signals
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status_changed)
        self._player.errorOccurred.connect(self._on_error)

        # Set initial volume
        self.set_volume(70)

    @property
    def playlist(self) -> List[dict]:
        """Get the current playlist as list of dicts (backward compatibility)."""
        return [item.to_dict() for item in self._playlist]

    @property
    def playlist_items(self) -> List[PlaylistItem]:
        """Get the current playlist as PlaylistItem objects."""
        return self._playlist.copy()

    @property
    def current_index(self) -> int:
        """Get the current track index."""
        return self._current_index

    @property
    def current_track(self) -> Optional[dict]:
        """Get the current track as dict (backward compatibility)."""
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index].to_dict()
        return None

    @property
    def current_playlist_item(self) -> Optional[PlaylistItem]:
        """Get the current track as PlaylistItem."""
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index]
        return None

    @property
    def play_mode(self) -> PlayMode:
        """Get the current play mode."""
        return self._play_mode

    @property
    def state(self) -> PlaybackState:
        """Get the current player state."""
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            return PlaybackState.PLAYING
        elif state == QMediaPlayer.PlaybackState.PausedState:
            return PlaybackState.PAUSED
        return PlaybackState.STOPPED

    @property
    def volume(self) -> int:
        """Get the current volume (0-100)."""
        return int(self._audio_output.volume() * 100)

    def load_playlist(self, tracks: Union[List[dict], List[PlaylistItem]]):
        """
        Load a playlist.

        Args:
            tracks: List of track dictionaries or PlaylistItem objects
        """
        self._playlist = []
        for track in tracks:
            if isinstance(track, PlaylistItem):
                self._playlist.append(track)
            else:
                self._playlist.append(PlaylistItem.from_dict(track))
        self._original_playlist = self._playlist.copy()  # Save original order
        self._current_index = -1
        self.playlist_changed.emit()

    def load_playlist_items(self, items: List[PlaylistItem]):
        """
        Load a playlist from PlaylistItem objects.

        Args:
            items: List of PlaylistItem objects
        """
        self._playlist = items.copy()
        self._original_playlist = items.copy()  # Save original order
        self._current_index = -1
        self.playlist_changed.emit()

    def clear_playlist(self):
        """Clear the playlist."""
        self._playlist.clear()
        self._original_playlist.clear()
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

    def add_track(self, track: Union[dict, PlaylistItem]):
        """
        Add a track to the playlist.

        Args:
            track: Track dictionary or PlaylistItem
        """
        if isinstance(track, PlaylistItem):
            self._playlist.append(track)
        else:
            self._playlist.append(PlaylistItem.from_dict(track))
        self.playlist_changed.emit()

    def insert_track(self, index: int, track: Union[dict, PlaylistItem]):
        """
        Insert a track at a specific position.

        Args:
            index: Position to insert at
            track: Track dictionary or PlaylistItem
        """
        if 0 <= index <= len(self._playlist):
            item = track if isinstance(track, PlaylistItem) else PlaylistItem.from_dict(track)
            self._playlist.insert(index, item)
            if self._current_index >= index:
                self._current_index += 1
            self.playlist_changed.emit()

    def remove_track(self, index: int):
        """
        Remove a track from the playlist.

        Args:
            index: Index of track to remove
        """
        if 0 <= index < len(self._playlist):
            self._playlist.pop(index)
            if self._current_index == index:
                self.stop()
                self._current_index = -1
            elif self._current_index > index:
                self._current_index -= 1
            self.playlist_changed.emit()

    def update_track_path(self, index: int, local_path: str):
        """
        Update the local path for a track (after download completes).

        Args:
            index: Index of track to update
            local_path: New local path
        """
        if 0 <= index < len(self._playlist):
            item = self._playlist[index]
            item.local_path = local_path
            item.needs_download = False

    def play(self):
        """Start or resume playback."""
        if self._current_index < 0 and self._playlist:
            self._current_index = 0

        if 0 <= self._current_index < len(self._playlist):
            item = self._playlist[self._current_index]

            # Check if current track needs download
            if item.needs_download or not item.local_path:
                self.track_needs_download.emit(item)
                return

            # Load track if not already loaded
            current_source = self._player.source()
            if not current_source.isValid() or current_source.toLocalFile() != item.local_path:
                self._load_track(self._current_index)

            self._player.play()

    def pause(self):
        """Pause playback."""
        self._player.pause()

    def stop(self):
        """Stop playback."""
        self._player.stop()

    def play_at(self, index: int):
        """
        Play track at specific index.

        Args:
            index: Index of track to play
        """
        if 0 <= index < len(self._playlist):
            self._current_index = index
            item = self._playlist[index]

            # Check if track needs download
            if item.needs_download or not item.local_path:
                self.current_track_changed.emit(item.to_dict())
                self.track_needs_download.emit(item)
                return

            self._load_track(index)
            self._player.play()

    def play_at_with_position(self, index: int, position_ms: int):
        """
        Load track and seek to position before starting playback.
        This avoids the brief play-from-start issue.

        Args:
            index: Index of track to play
            position_ms: Position to seek to before playing (in milliseconds)
        """
        if 0 <= index < len(self._playlist):
            self._current_index = index
            item = self._playlist[index]

            # Save pending seek for use after download
            self._pending_seek = position_ms
            self._pending_play = True

            # Check if track needs download
            if item.needs_download or not item.local_path:
                self.current_track_changed.emit(item.to_dict())
                self.track_needs_download.emit(item)
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
        if 0 <= index < len(self._playlist):
            self.update_track_path(index, local_path)
            item = self._playlist[index]

            # Extract metadata if needed (for cloud files)
            if item.needs_metadata and local_path:
                from services.metadata.metadata_service import MetadataService
                metadata = MetadataService.extract_metadata(local_path)
                if metadata:
                    if metadata.get("title"):
                        item.title = metadata["title"]
                    if metadata.get("artist"):
                        item.artist = metadata["artist"]
                    if metadata.get("album"):
                        item.album = metadata["album"]
                    item.needs_metadata = False

            # Only play if this is the current track
            if index == self._current_index:
                url = QUrl.fromLocalFile(local_path)
                self._player.setSource(url)

                # Use pending seek if available
                if self._pending_seek and self._pending_seek > 0:
                    # Will seek after media is loaded
                    self._pending_play = True
                else:
                    self._player.play()

                self.current_track_changed.emit(item.to_dict())

    def play_next(self):
        """Play the next track."""
        if not self._playlist:
            return

        # Handle loop one mode - stay on current track
        if self._play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            # Just restart playback
            self._player.setPosition(0)
            self._player.play()
            return

        # Move to next track
        self._current_index += 1

        if self._current_index >= len(self._playlist):
            if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                # Reshuffle for random loop mode
                if self._play_mode == PlayMode.RANDOM_LOOP:
                    self._shuffle_playlist()
                self._current_index = 0
            else:
                self._current_index = len(self._playlist) - 1
                self.stop()
                return

        item = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None

        self._load_track(self._current_index)

        # Check if track needs download
        if item and (item.needs_download or not item.local_path):
            self.track_needs_download.emit(item)
        elif item and item.local_path:
            self._player.play()

    def play_previous(self):
        """Play the previous track."""
        if not self._playlist:
            return

        # Handle loop one mode - stay on current track
        if self._play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            self._player.setPosition(0)
            return

        if self._player.position() > 3000:  # If more than 3 seconds played, restart track
            self._player.setPosition(0)
        else:
            self._current_index -= 1
            if self._current_index < 0:
                if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                    self._current_index = len(self._playlist) - 1
                else:
                    self._current_index = 0

            item = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None

            self._load_track(self._current_index)

            # Check if track needs download
            if item and (item.needs_download or not item.local_path):
                self.track_needs_download.emit(item)
            elif item and item.local_path:
                self._player.play()

    def seek(self, position_ms: int):
        """
        Seek to position in current track.

        Args:
            position_ms: Position in milliseconds
        """
        self._player.setPosition(position_ms)

    def position(self) -> int:
        """
        Get current playback position.

        Returns:
            Current position in milliseconds
        """
        return self._player.position()

    def duration(self) -> int:
        """
        Get current track duration.

        Returns:
            Duration in milliseconds
        """
        return self._player.duration()

    def set_volume(self, volume: int):
        """
        Set volume.

        Args:
            volume: Volume level (0-100)
        """
        volume = max(0, min(100, volume))
        self._audio_output.setVolume(volume / 100.0)
        self.volume_changed.emit(volume)

    def set_play_mode(self, mode: PlayMode):
        """
        Set the playback mode.

        When switching to/from shuffle mode, the playlist is shuffled/restored:
        - Sequential/Loop -> Shuffle: Shuffle queue, current song at front
        - Shuffle -> Sequential/Loop: Restore original order

        Args:
            mode: PlayMode to set
        """
        old_mode = self._play_mode
        old_is_shuffle = old_mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)
        new_is_shuffle = mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)

        # Handle shuffle mode transition
        if new_is_shuffle and not old_is_shuffle:
            # Entering shuffle mode - shuffle the queue
            self._shuffle_playlist()
        elif not new_is_shuffle and old_is_shuffle:
            # Exiting shuffle mode - restore original order
            self._restore_playlist_order()

        self._play_mode = mode
        self.play_mode_changed.emit(mode)

    def _shuffle_playlist(self):
        """Shuffle the playlist with current track at front."""
        if not self._playlist:
            return

        # Get current item before shuffling (if any)
        current_item = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None

        # Shuffle the playlist
        import random
        self._playlist = self._original_playlist.copy()
        random.shuffle(self._playlist)

        # Move current item to front if there's one playing
        if current_item:
            try:
                idx = self._playlist.index(current_item)
                self._playlist.pop(idx)
                self._playlist.insert(0, current_item)
            except ValueError:
                pass

        self._current_index = 0

    def _restore_playlist_order(self):
        """Restore the playlist to original order."""
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

    def shuffle_and_play(self, item_to_play: PlaylistItem = None):
        """
        Shuffle the playlist and optionally set a specific item as current.

        This is used when a new song is played while in shuffle mode.

        Args:
            item_to_play: Optional item to place at front of shuffled queue
        """
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

    def is_shuffle_mode(self) -> bool:
        """Check if currently in shuffle mode."""
        return self._play_mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)

    def _load_track(self, index: int):
        """Load a track for playback."""
        if 0 <= index < len(self._playlist):
            item = self._playlist[index]

            # Skip loading if path is empty (for cloud files not yet downloaded)
            if not item.local_path or item.needs_download:
                self.current_track_changed.emit(item.to_dict())
                return

            url = QUrl.fromLocalFile(item.local_path)

            self._player.setSource(url)
            self.current_track_changed.emit(item.to_dict())

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        self.position_changed.emit(position_ms)

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self.duration_changed.emit(duration_ms)

    def _on_state_changed(self, state):
        """Handle state change."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.state_changed.emit(PlaybackState.PLAYING)
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.state_changed.emit(PlaybackState.PAUSED)
        else:
            self.state_changed.emit(PlaybackState.STOPPED)

    def _on_media_status_changed(self, status):
        """Handle media status change."""
        import time

        logger.debug(f"[PlayerEngine] _on_media_status_changed: status={status}")

        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            logger.debug("[PlayerEngine] Media loaded, checking pending seek")
            # Media is loaded and ready - now we can seek if needed
            if self._pending_seek > 0:
                logger.debug(f"[PlayerEngine] Pending seek: {self._pending_seek}ms")
                self._player.setPosition(self._pending_seek)
                self._pending_seek = 0
                if self._pending_play:
                    self._pending_play = False
                    self._player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.track_finished.emit()

            # Auto-play next based on mode
            if self._play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
                # Track loop modes
                self.seek(0)
                self.play()
            elif self._play_mode in (PlayMode.SEQUENTIAL, PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM, PlayMode.RANDOM_LOOP):
                # Modes that advance to next track
                self.play_next()

    def _on_error(self, error, error_string):
        """Handle playback error."""
        self.error_occurred.emit(error_string)

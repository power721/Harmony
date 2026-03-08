"""
Audio playback engine using Qt Multimedia.
"""
import logging

from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QObject, Signal, QTimer
from typing import Optional, List
from enum import Enum

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


class PlayMode(Enum):
    """Playback mode enumeration."""
    SEQUENTIAL = 0  # Play tracks in order
    LOOP = 1        # Loop the current track
    PLAYLIST_LOOP = 2  # Loop the entire playlist
    RANDOM = 3      # Random playback
    RANDOM_LOOP = 4 # Random playback with playlist loop
    RANDOM_TRACK_LOOP = 5  # Random playback with track loop


class PlayerState(Enum):
    """Player state enumeration."""
    STOPPED = 0
    PLAYING = 1
    PAUSED = 2


class PlayerEngine(QObject):
    """
    Audio playback engine using QMediaPlayer.

    Signals:
        position_changed: Emitted when playback position changes (position_ms)
        duration_changed: Emitted when track duration changes (duration_ms)
        state_changed: Emitted when player state changes (PlayerState)
        current_track_changed: Emitted when current track changes
        volume_changed: Emitted when volume changes (volume 0-100)
        track_finished: Emitted when current track finishes playing
    """

    position_changed = Signal(int)
    duration_changed = Signal(int)
    state_changed = Signal(PlayerState)
    current_track_changed = Signal(object)
    volume_changed = Signal(int)
    track_finished = Signal()
    error_occurred = Signal(str)
    play_mode_changed = Signal(PlayMode)  # Emitted when play mode changes

    def __init__(self, parent=None):
        """Initialize the player engine."""
        super().__init__(parent)

        self._player = QMediaPlayer()
        self._audio_output = QAudioOutput()
        self._player.setAudioOutput(self._audio_output)

        self._playlist: List[dict] = []  # List of track dictionaries
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
        """Get the current playlist."""
        return self._playlist.copy()

    @property
    def current_index(self) -> int:
        """Get the current track index."""
        return self._current_index

    @property
    def current_track(self) -> Optional[dict]:
        """Get the current track."""
        if 0 <= self._current_index < len(self._playlist):
            return self._playlist[self._current_index]
        return None

    @property
    def play_mode(self) -> PlayMode:
        """Get the current play mode."""
        return self._play_mode

    @property
    def state(self) -> PlayerState:
        """Get the current player state."""
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            return PlayerState.PLAYING
        elif state == QMediaPlayer.PlaybackState.PausedState:
            return PlayerState.PAUSED
        return PlayerState.STOPPED

    @property
    def volume(self) -> int:
        """Get the current volume (0-100)."""
        return int(self._audio_output.volume() * 100)

    def load_playlist(self, tracks: List[dict]):
        """
        Load a playlist.

        Args:
            tracks: List of track dictionaries with at least 'path' key
        """
        self._playlist = tracks.copy()
        self._current_index = -1

    def clear_playlist(self):
        """Clear the playlist."""
        self._playlist.clear()
        self._current_index = -1
        self.stop()

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

    def add_track(self, track: dict):
        """
        Add a track to the playlist.

        Args:
            track: Track dictionary
        """
        self._playlist.append(track)

    def insert_track(self, index: int, track: dict):
        """
        Insert a track at a specific position.

        Args:
            index: Position to insert at
            track: Track dictionary
        """
        if 0 <= index <= len(self._playlist):
            self._playlist.insert(index, track)
            if self._current_index >= index:
                self._current_index += 1

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

    def play(self):
        """Start or resume playback."""
        if self._current_index < 0 and self._playlist:
            self._current_index = 0
            self._load_track(self._current_index)

        if self._current_index >= 0:
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
            self._pending_seek = position_ms
            self._pending_play = True
            self._load_track(index)
            # Don't call play() here - will play after media is loaded and seeked

    def play_next(self):
        """Play the next track."""
        import time
        start_time = time.time()

        logger.debug(f"[PlayerEngine] play_next called: current_index={self._current_index}, playlist_size={len(self._playlist)}")

        if not self._playlist:
            logger.debug("[PlayerEngine] play_next: No playlist, returning")
            return

        if self._play_mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP):
            import random
            self._current_index = random.randint(0, len(self._playlist) - 1)
            logger.debug(f"[PlayerEngine] play_next: Random mode, new index={self._current_index}")
        else:
            self._current_index += 1
            logger.debug(f"[PlayerEngine] play_next: Sequential mode, new index={self._current_index}")

        if self._current_index >= len(self._playlist):
            if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                self._current_index = 0
                logger.debug(f"[PlayerEngine] play_next: Playlist loop, reset to index 0")
            else:
                self._current_index = len(self._playlist) - 1
                logger.debug(f"[PlayerEngine] play_next: End of playlist, stopping")
                self.stop()
                return

        current_track = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None
        logger.debug(f"[PlayerEngine] play_next: Loading track at index {self._current_index}, path={current_track.get('path') if current_track else None}")

        self._load_track(self._current_index)

        # Only call play() if the track has a valid path
        # For cloud files with empty paths, playback will be triggered after download completes
        if current_track and current_track.get('path'):
            logger.debug(f"[PlayerEngine] play_next: Calling play()")
            self._player.play()
        else:
            logger.debug(f"[PlayerEngine] play_next: Path is empty, skipping play() - waiting for download")

        logger.debug(f"[PlayerEngine] play_next took: {time.time() - start_time:.3f}s")

    def play_previous(self):
        """Play the previous track."""
        import time
        start_time = time.time()

        logger.debug(f"[PlayerEngine] play_previous called: current_index={self._current_index}")

        if not self._playlist:
            logger.debug("[PlayerEngine] play_previous: No playlist, returning")
            return

        if self._player.position() > 3000:  # If more than 3 seconds played, restart track
            logger.debug("[PlayerEngine] play_previous: Position > 3000ms, restarting track")
            self._player.setPosition(0)
        else:
            self._current_index -= 1
            if self._current_index < 0:
                if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                    self._current_index = len(self._playlist) - 1
                else:
                    self._current_index = 0

            current_track = self._playlist[self._current_index] if 0 <= self._current_index < len(self._playlist) else None
            logger.debug(f"[PlayerEngine] play_previous: Loading track at index {self._current_index}, path={current_track.get('path') if current_track else None}")

            self._load_track(self._current_index)

            # Only call play() if the track has a valid path
            # For cloud files with empty paths, playback will be triggered after download completes
            if current_track and current_track.get('path'):
                logger.debug("[PlayerEngine] play_previous: Calling play()")
                self._player.play()
            else:
                logger.debug("[PlayerEngine] play_previous: Path is empty, skipping play() - waiting for download")

        logger.debug(f"[PlayerEngine] play_previous took: {time.time() - start_time:.3f}s")

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

        Args:
            mode: PlayMode to set
        """
        self._play_mode = mode
        self.play_mode_changed.emit(mode)

    def _load_track(self, index: int):
        """Load a track for playback."""
        import time
        start_time = time.time()

        logger.debug(f"[PlayerEngine] _load_track called: index={index}")

        if 0 <= index < len(self._playlist):
            track = self._playlist[index]
            logger.debug(f"[PlayerEngine] _load_track: track={track}")

            # Skip loading if path is empty (for cloud files not yet downloaded)
            if not track.get('path'):
                logger.debug(f"[PlayerEngine] _load_track: Path is empty, emitting current_track_changed signal")
                self.current_track_changed.emit(track)
                logger.debug(f"[PlayerEngine] _load_track took: {time.time() - start_time:.3f}s (empty path)")
                return

            url = QUrl.fromLocalFile(track['path'])

            logger.debug(f'[PlayerEngine] Loading track from {url}')
            self._player.setSource(url)
            logger.debug(f"[PlayerEngine] _load_track: setSource done, emitting current_track_changed")
            self.current_track_changed.emit(track)

            logger.debug(f"[PlayerEngine] _load_track took: {time.time() - start_time:.3f}s")
        else:
            logger.debug(f"[PlayerEngine] _load_track: Invalid index {index}")

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        self.position_changed.emit(position_ms)

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self.duration_changed.emit(duration_ms)

    def _on_state_changed(self, state):
        """Handle state change."""
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.state_changed.emit(PlayerState.PLAYING)
        elif state == QMediaPlayer.PlaybackState.PausedState:
            self.state_changed.emit(PlayerState.PAUSED)
        else:
            self.state_changed.emit(PlayerState.STOPPED)

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
                    logger.debug("[PlayerEngine] Calling play() after seek")
                    self._player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            logger.debug("[PlayerEngine] EndOfMedia reached")
            self.track_finished.emit()

            # Auto-play next based on mode
            if self._play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
                # Track loop modes
                logger.debug("[PlayerEngine] Track loop mode, seeking to 0 and playing")
                self.seek(0)
                self.play()
            elif self._play_mode in (PlayMode.SEQUENTIAL, PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM, PlayMode.RANDOM_LOOP):
                # Modes that advance to next track
                logger.debug(f"[PlayerEngine] Calling play_next, mode={self._play_mode}")
                self.play_next()

    def _on_error(self, error, error_string):
        """Handle playback error."""
        self.error_occurred.emit(error_string)

"""
Audio playback engine using Qt Multimedia.
"""
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl, QObject, Signal, QTimer
from typing import Optional, List
from enum import Enum


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

        self._player = QMediaPlayer(parent)
        self._audio_output = QAudioOutput(parent)
        self._player.setAudioOutput(self._audio_output)

        self._playlist: List[dict] = []  # List of track dictionaries
        self._current_index: int = -1
        self._play_mode: PlayMode = PlayMode.SEQUENTIAL

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

    def play_next(self):
        """Play the next track."""
        if not self._playlist:
            return

        if self._play_mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP):
            import random
            self._current_index = random.randint(0, len(self._playlist) - 1)
        else:
            self._current_index += 1

        if self._current_index >= len(self._playlist):
            if self._play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                self._current_index = 0
            else:
                self._current_index = len(self._playlist) - 1
                self.stop()
                return

        self._load_track(self._current_index)
        self._player.play()

    def play_previous(self):
        """Play the previous track."""
        if not self._playlist:
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

            self._load_track(self._current_index)
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

        Args:
            mode: PlayMode to set
        """
        self._play_mode = mode
        self.play_mode_changed.emit(mode)

    def _load_track(self, index: int):
        """Load a track for playback."""
        if 0 <= index < len(self._playlist):
            track = self._playlist[index]
            url = QUrl.fromLocalFile(track['path'])
            self._player.setSource(url)
            self.current_track_changed.emit(track)

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
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
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

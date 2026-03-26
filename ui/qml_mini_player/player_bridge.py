"""
PlayerBridge - Qt ↔ QML data binding layer.

Exposes player state as Qt properties for QML binding.
"""
import logging
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal, Property, Slot

from domain.playback import PlaybackState
from utils import format_time

logger = logging.getLogger(__name__)


class PlayerBridge(QObject):
    """
    Bridge between PlaybackService and QML UI.

    Exposes player state as Qt properties that QML can bind to.
    All property changes emit signals to update QML bindings.
    """

    # Property change signals
    titleChanged = Signal()
    artistChanged = Signal()
    progressChanged = Signal()
    playingChanged = Signal()
    coverPathChanged = Signal()
    currentTimeChanged = Signal()
    totalTimeChanged = Signal()

    # Action signals
    closeRequested = Signal()

    def __init__(self, player, parent=None):
        """
        Initialize bridge with PlaybackService.

        Args:
            player: PlaybackService instance
            parent: Parent QObject
        """
        super().__init__(parent)
        self._player = player
        self._engine = player.engine

        # Internal state
        self._title = ""
        self._artist = ""
        self._progress = 0.0
        self._playing = False
        self._cover_path = ""
        self._current_time = "0:00"
        self._total_time = "0:00"
        self._duration_ms = 0
        self._is_seeking = False
        self._current_track_dict: Optional[dict] = None

        # Connect to engine signals
        self._setup_connections()

        # Initialize with current state
        self._initialize_state()

    def _setup_connections(self):
        """Connect to PlayerEngine signals."""
        self._engine.state_changed.connect(self._on_state_changed)
        self._engine.position_changed.connect(self._on_position_changed)
        self._engine.duration_changed.connect(self._on_duration_changed)
        self._engine.current_track_changed.connect(self._on_track_changed)

    def _initialize_state(self):
        """Initialize with current playback state."""
        # Get current state
        state = self._engine.state
        self._playing = state == PlaybackState.PLAYING
        self.playingChanged.emit()

        # Get current track
        track = self._engine.current_track
        if track:
            self._update_track_info(track)

        # Get position/duration
        position_ms = self._engine.position()
        duration_ms = self._engine.duration()
        if duration_ms > 0:
            self._duration_ms = duration_ms
            self._total_time = format_time(duration_ms / 1000)
            self.totalTimeChanged.emit()
            self._update_progress(position_ms)

    # ===== Properties =====

    def getTitle(self) -> str:
        return self._title

    def setTitle(self, value: str):
        if self._title != value:
            self._title = value
            self.titleChanged.emit()

    title = Property(str, getTitle, notify=titleChanged)

    def getArtist(self) -> str:
        return self._artist

    def setArtist(self, value: str):
        if self._artist != value:
            self._artist = value
            self.artistChanged.emit()

    artist = Property(str, getArtist, notify=artistChanged)

    def getProgress(self) -> float:
        return self._progress

    def setProgress(self, value: float):
        if abs(self._progress - value) > 0.001:
            self._progress = value
            self.progressChanged.emit()

    progress = Property(float, getProgress, notify=progressChanged)

    def isPlaying(self) -> bool:
        return self._playing

    def setPlaying(self, value: bool):
        if self._playing != value:
            self._playing = value
            self.playingChanged.emit()

    playing = Property(bool, isPlaying, notify=playingChanged)

    def getCoverPath(self) -> str:
        return self._cover_path

    def setCoverPath(self, value: str):
        if self._cover_path != value:
            self._cover_path = value
            self.coverPathChanged.emit()

    coverPath = Property(str, getCoverPath, notify=coverPathChanged)

    def getCurrentTime(self) -> str:
        return self._current_time

    currentTime = Property(str, getCurrentTime, notify=currentTimeChanged)

    def getTotalTime(self) -> str:
        return self._total_time

    totalTime = Property(str, getTotalTime, notify=totalTimeChanged)

    # ===== Slots (callable from QML) =====

    @Slot()
    def togglePlay(self):
        """Toggle play/pause."""
        if self._playing:
            self._engine.pause()
        else:
            self._engine.play()

    @Slot()
    def playNext(self):
        """Play next track."""
        self._engine.play_next()

    @Slot()
    def playPrevious(self):
        """Play previous track."""
        # Mini player always goes to previous track (ignore 3-second rule)
        current_index = self._engine.current_index
        playlist_size = len(self._engine.playlist_items)

        if playlist_size == 0:
            return

        new_index = current_index - 1
        if new_index < 0:
            new_index = playlist_size - 1

        self._engine.play_at(new_index)

    @Slot(float)
    def seek(self, progress: float):
        """Seek to position (0.0-1.0)."""
        if self._duration_ms > 0:
            position_ms = int(progress * self._duration_ms)
            self._engine.seek(position_ms)

    @Slot()
    def close(self):
        """Request close (emits signal)."""
        self.closeRequested.emit()

    # ===== Internal handlers =====

    def _on_state_changed(self, state: PlaybackState):
        """Handle player state change."""
        self.setPlaying(state == PlaybackState.PLAYING)

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        if not self._is_seeking:
            self._update_progress(position_ms)

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self._duration_ms = duration_ms
        self._total_time = format_time(duration_ms / 1000)
        self.totalTimeChanged.emit()

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        self._current_track_dict = track_dict
        self._update_track_info(track_dict)
        self._load_cover_async(track_dict)

    def _update_progress(self, position_ms: int):
        """Update progress and current time."""
        if self._duration_ms > 0:
            self.setProgress(position_ms / self._duration_ms)
        self._current_time = format_time(position_ms / 1000)
        self.currentTimeChanged.emit()

    def _update_track_info(self, track_dict: dict):
        """Update track title and artist."""
        if track_dict:
            title = track_dict.get("title", "")
            artist = track_dict.get("artist", "")
            self.setTitle(title or "Unknown")
            self.setArtist(artist or "")
        else:
            self.setTitle("Not Playing")
            self.setArtist("")

    def _load_cover_async(self, track_dict: dict):
        """Load cover art asynchronously."""
        def load_cover():
            if not track_dict:
                return ""

            # Check if cover_path is already saved
            cover_path = track_dict.get("cover_path")
            if cover_path and Path(cover_path).exists():
                return cover_path

            # Fall back to extracting from file
            path = track_dict.get("path", "")
            title = track_dict.get("title", "")
            artist = track_dict.get("artist", "")
            album = track_dict.get("album", "")

            # Check for online track
            source = track_dict.get("source", "")
            cloud_file_id = track_dict.get("cloud_file_id", "")
            is_qq_music = source == "QQ"

            if is_qq_music and cloud_file_id:
                try:
                    cover_service = self._player.cover_service
                    if cover_service:
                        cover_path = cover_service.get_online_cover(
                            song_mid=cloud_file_id,
                            album_mid=None,
                            artist=artist,
                            title=title
                        )
                        if cover_path:
                            return cover_path
                except Exception as e:
                    logger.error(f"Error getting online cover: {e}")

            needs_download = track_dict.get("needs_download", False)
            is_cloud = track_dict.get("is_cloud", False)
            skip_online = needs_download or (is_cloud and not path)

            return self._player.get_track_cover(path, title, artist, album, skip_online=skip_online)

        def worker():
            cover_path = load_cover()
            # Must emit from main thread, use timer
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.setCoverPath(cover_path or ""))

        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def set_seeking(self, seeking: bool):
        """Set seeking state (pause progress updates)."""
        self._is_seeking = seeking

"""
Playback service - Business logic for audio playback.
"""

import logging
from typing import Optional, List

from PySide6.QtCore import QObject, Signal

from domain import PlaylistItem
from domain.playback import PlayMode, PlaybackState
from infrastructure.audio import PlayerEngine
from repositories.track_repository import SqliteTrackRepository
from repositories.queue_repository import SqliteQueueRepository
from system.event_bus import EventBus


logger = logging.getLogger(__name__)


class PlaybackService(QObject):
    """
    Business logic for audio playback.

    This service orchestrates playback operations, handling both
    local tracks and cloud files transparently.
    """

    source_changed = Signal(str)  # "local" or "cloud"

    def __init__(
        self,
        track_repo: SqliteTrackRepository,
        queue_repo: SqliteQueueRepository,
        config_manager,
        parent=None
    ):
        super().__init__(parent)

        self._track_repo = track_repo
        self._queue_repo = queue_repo
        self._config = config_manager
        self._engine = PlayerEngine()
        self._event_bus = EventBus.instance()

        # Playback state
        self._current_source = "local"

        # Connect engine signals
        self._connect_engine_signals()

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
        return self._engine

    @property
    def current_source(self) -> str:
        return self._current_source

    @property
    def current_track(self) -> Optional[PlaylistItem]:
        return self._engine.current_playlist_item

    @property
    def state(self) -> PlaybackState:
        return self._engine.state

    @property
    def volume(self) -> int:
        return self._engine.volume

    @property
    def play_mode(self) -> PlayMode:
        return self._engine.play_mode

    # ===== Playback Control =====

    def play(self):
        self._engine.play()

    def pause(self):
        self._engine.pause()

    def stop(self):
        self._engine.stop()

    def play_next(self):
        self._engine.play_next()

    def play_previous(self):
        self._engine.play_previous()

    def seek(self, position_ms: int):
        self._engine.seek(position_ms)

    def set_volume(self, volume: int):
        self._engine.set_volume(volume)

    def set_play_mode(self, mode: PlayMode):
        self._engine.set_play_mode(mode)

    # ===== Internal Methods =====

    def _set_source(self, source: str):
        if self._current_source != source:
            self._current_source = source
            self.source_changed.emit(source)

    def _on_track_changed(self, track_dict: dict):
        item = self._engine.current_playlist_item
        if item:
            self._event_bus.emit_track_change(item)

            if item.is_local and item.track_id:
                # Could add to play history here
                pass

    def _on_state_changed(self, state: PlaybackState):
        state_str = {
            PlaybackState.PLAYING: "playing",
            PlaybackState.PAUSED: "paused",
            PlaybackState.STOPPED: "stopped",
        }.get(state, "stopped")
        self._event_bus.emit_playback_state(state_str)

    def _on_play_mode_changed(self, mode: PlayMode):
        self._config.set_play_mode(mode.value)
        self._event_bus.play_mode_changed.emit(mode.value)

    def _on_track_needs_download(self, item: PlaylistItem):
        """Handle track that needs download - to be connected to cloud service."""
        pass

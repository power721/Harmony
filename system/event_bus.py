"""
Event bus for centralized signal management.

This module provides a singleton EventBus class that centralizes
all application-wide signals, reducing coupling between components.
"""

import logging
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from domain.playlist_item import PlaylistItem

# Configure logging
logger = logging.getLogger(__name__)


class EventBus(QObject):
    """
    Central event bus for application-wide signals.

    This singleton provides a centralized way for components to communicate
    without direct coupling. Components can emit signals through the bus
    and connect to signals from other components.

    Usage:
        bus = EventBus.instance()
        bus.track_changed.connect(self._on_track_changed)
        bus.track_changed.emit(track_item)

    Categories of signals:
        - Playback events: track changes, state changes, position updates
        - Download events: download start, progress, completion
        - UI events: lyrics loaded, metadata updated
        - Library events: tracks added, playlists changed
    """

    # ===== Playback Events =====

    # Emitted when the current track changes (PlaylistItem or dict)
    track_changed = Signal(object)

    # Emitted when playback state changes ("playing", "paused", "stopped")
    playback_state_changed = Signal(str)

    # Emitted when playback position changes (position_ms)
    position_changed = Signal(int)

    # Emitted when track duration becomes known (duration_ms)
    duration_changed = Signal(int)

    # Emitted when playback mode changes (PlayMode enum value)
    play_mode_changed = Signal(int)

    # Emitted when volume changes (0-100)
    volume_changed = Signal(int)

    # Emitted when a track finishes playing
    track_finished = Signal()

    # ===== Cloud Download Events =====

    # Emitted when a cloud file download starts (file_id)
    download_started = Signal(str)

    # Emitted during download progress (file_id, current_bytes, total_bytes)
    download_progress = Signal(str, int, int)

    # Emitted when download completes (file_id, local_path)
    download_completed = Signal(str, str)

    # Emitted when download fails (file_id, error_message)
    download_error = Signal(str, str)

    # Emitted when a track needs to be downloaded (PlaylistItem)
    track_needs_download = Signal(object)

    # ===== UI Events =====

    # Emitted when lyrics are loaded (lyrics_text)
    lyrics_loaded = Signal(str)

    # Emitted when lyrics loading fails (error_message)
    lyrics_error = Signal(str)

    # Emitted when track metadata is updated (track_id)
    metadata_updated = Signal(int)

    # Emitted when cover art is updated (item_id, is_cloud)
    # item_id: track_id (int) for local tracks, cloud_file_id (str) for cloud files
    cover_updated = Signal(object, bool)

    # ===== Library Events =====

    # Emitted when tracks are added to the library (count)
    tracks_added = Signal(int)

    # Emitted when a playlist is created (playlist_id)
    playlist_created = Signal(int)

    # Emitted when a playlist is modified (playlist_id)
    playlist_modified = Signal(int)

    # Emitted when a playlist is deleted (playlist_id)
    playlist_deleted = Signal(int)

    # Emitted when favorite status changes (id, is_favorite, is_cloud)
    # id: track_id (int) for local tracks, cloud_file_id (str) for cloud files
    favorite_changed = Signal(object, bool, bool)

    # ===== Cloud Account Events =====

    # Emitted when a cloud account is added (account_id)
    cloud_account_added = Signal(int)

    # Emitted when a cloud account is removed (account_id)
    cloud_account_removed = Signal(int)

    # Emitted when cloud account token is updated (account_id)
    cloud_token_updated = Signal(int)

    # Singleton instance
    _instance: Optional["EventBus"] = None

    @classmethod
    def instance(cls) -> "EventBus":
        """Get the singleton EventBus instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls):
        """Reset the singleton instance (for testing)."""
        if cls._instance is not None:
            cls._instance.deleteLater()
            cls._instance = None

    def __init__(self, parent=None):
        """Initialize the event bus."""
        super().__init__(parent)

    # ===== Convenience Methods =====

    def emit_track_change(self, track_item):
        """Emit a track change event with logging."""
        self.track_changed.emit(track_item)

    def emit_playback_state(self, state: str):
        """Emit a playback state change with validation."""
        valid_states = ("playing", "paused", "stopped")
        if state not in valid_states:
            logger.warning(f"[EventBus] Invalid playback state: {state}")
            return
        self.playback_state_changed.emit(state)

    def emit_download_complete(self, file_id: str, local_path: str):
        """Emit a download completion event with logging."""
        self.download_completed.emit(file_id, local_path)

    def emit_favorite_change(self, item_id, is_favorite: bool, is_cloud: bool = False):
        """Emit a favorite change event."""
        self.favorite_changed.emit(item_id, is_favorite, is_cloud)


# Global convenience function
def get_event_bus() -> EventBus:
    """Get the global EventBus instance."""
    return EventBus.instance()

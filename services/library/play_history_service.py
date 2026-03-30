"""
Play history service - Manages play history records.
"""

import logging
from typing import List, Optional

from domain.history import PlayHistory
from domain.track import Track
from repositories.history_repository import SqliteHistoryRepository
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class PlayHistoryService:
    """
    Service for managing play history.

    Provides a clean API for UI components to interact with play history
    without directly accessing the database layer.
    """

    def __init__(self, history_repo: SqliteHistoryRepository, event_bus: EventBus = None):
        """
        Initialize play history service.

        Args:
            history_repo: History repository for data persistence
            event_bus: Event bus for broadcasting changes
        """
        self._history_repo = history_repo
        self._event_bus = event_bus or EventBus.instance()

    def get_history(self, limit: int = 100) -> List[PlayHistory]:
        """
        Get recent play history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of PlayHistory objects
        """
        return self._history_repo.get_recent(limit)

    def get_history_tracks(self, limit: int = 100) -> List[Track]:
        """
        Get recently played tracks (returns Track objects).

        This is a convenience method for UI that needs Track objects
        instead of PlayHistory objects.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of Track objects ordered by most recently played
        """
        return self._history_repo.get_recent_tracks(limit)

    def add_history(self, track_id: int) -> bool:
        """
        Add a track to play history.

        Args:
            track_id: Track ID

        Returns:
            True if added successfully
        """
        return self._history_repo.add(track_id)

    def get_most_played(self, limit: int = 20) -> List[Track]:
        """
        Get most played tracks.

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of Track objects ordered by play count (descending)
        """
        return self._history_repo.get_most_played(limit)

    def clear_history(self) -> bool:
        """
        Clear all play history.

        Returns:
            True if cleared successfully
        """
        result = self._history_repo.clear()
        if result:
            self._event_bus.history_cleared.emit()
        return result

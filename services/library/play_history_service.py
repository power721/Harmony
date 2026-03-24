"""
Play history service - Manages play history records.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from domain.history import PlayHistory
from system.event_bus import EventBus

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class PlayHistoryService:
    """
    Service for managing play history.

    Provides a clean API for UI components to interact with play history
    without directly accessing the database layer.
    """

    def __init__(self, db_manager: "DatabaseManager", event_bus: EventBus = None):
        """
        Initialize play history service.

        Args:
            db_manager: Database manager for data persistence
            event_bus: Event bus for broadcasting changes
        """
        self._db = db_manager
        self._event_bus = event_bus or EventBus.instance()

    def get_history(self, limit: int = 100) -> List[PlayHistory]:
        """
        Get recent play history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of PlayHistory objects
        """
        return self._db.get_play_history(limit=limit)

    def add_history(self, track_id: int) -> int:
        """
        Add a track to play history.

        Args:
            track_id: Track ID

        Returns:
            History entry ID
        """
        return self._db.add_play_history(track_id=track_id)

    def get_most_played(self, limit: int = 20) -> List[tuple]:
        """
        Get most played tracks.

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of tuples with track data and play counts
        """
        return self._db.get_most_played(limit=limit)

    def clear_history(self) -> bool:
        """
        Clear all play history.

        Returns:
            True if cleared successfully
        """
        # This method doesn't exist in DatabaseManager yet, would need to add
        # For now, return False to indicate not implemented
        logger.warning("[PlayHistoryService] clear_history not implemented")
        return False

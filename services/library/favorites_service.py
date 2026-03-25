"""
Favorites service - Manages favorite tracks and cloud files.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from domain.track import Track
from system.event_bus import EventBus

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class FavoritesService:
    """
    Service for managing favorite tracks and cloud files.

    Provides a clean API for UI components to interact with favorites
    without directly accessing the database layer.
    """

    def __init__(self, db_manager: "DatabaseManager", event_bus: EventBus = None):
        """
        Initialize favorites service.

        Args:
            db_manager: Database manager for data persistence
            event_bus: Event bus for broadcasting changes
        """
        self._db = db_manager
        self._event_bus = event_bus or EventBus.instance()

    def is_favorite(self, track_id: int = None, cloud_file_id: str = None) -> bool:
        """
        Check if a track or cloud file is favorited.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID

        Returns:
            True if favorited, False otherwise
        """
        return self._db.is_favorite(track_id=track_id, cloud_file_id=cloud_file_id)

    def get_all_favorite_track_ids(self) -> set:
        """
        Get all favorite local track IDs as a set for O(1) lookup.

        Returns:
            Set of track IDs that are favorited
        """
        return self._db.get_all_favorite_track_ids()

    def add_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        cloud_account_id: int = None
    ) -> bool:
        """
        Add a track or cloud file to favorites.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID
            cloud_account_id: Cloud account ID (for cloud files)

        Returns:
            True if added successfully, False if already exists
        """
        result = self._db.add_favorite(
            track_id=track_id,
            cloud_file_id=cloud_file_id,
            cloud_account_id=cloud_account_id
        )
        if result:
            is_cloud = cloud_file_id is not None
            item_id = cloud_file_id if is_cloud else track_id
            self._event_bus.emit_favorite_change(item_id, True, is_cloud)
        return result

    def remove_favorite(self, track_id: int = None, cloud_file_id: str = None) -> bool:
        """
        Remove a track or cloud file from favorites.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID

        Returns:
            True if removed, False if not found
        """
        result = self._db.remove_favorite(track_id=track_id, cloud_file_id=cloud_file_id)
        if result:
            is_cloud = cloud_file_id is not None
            item_id = cloud_file_id if is_cloud else track_id
            self._event_bus.emit_favorite_change(item_id, False, is_cloud)
        return result

    def toggle_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        cloud_account_id: int = None
    ) -> tuple[bool, bool]:
        """
        Toggle favorite status.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID
            cloud_account_id: Cloud account ID (for cloud files)

        Returns:
            Tuple of (is_now_favorite, was_changed)
        """
        is_fav = self.is_favorite(track_id=track_id, cloud_file_id=cloud_file_id)

        if is_fav:
            removed = self.remove_favorite(track_id=track_id, cloud_file_id=cloud_file_id)
            return False, removed
        else:
            added = self.add_favorite(
                track_id=track_id,
                cloud_file_id=cloud_file_id,
                cloud_account_id=cloud_account_id
            )
            return True, added

    def get_favorites(self) -> List[Track]:
        """
        Get all favorite tracks (local tracks and downloaded cloud files).

        Returns:
            List of Track objects
        """
        return self._db.get_favorites()

    def get_favorites_with_cloud(self) -> List[dict]:
        """
        Get all favorites including local tracks and undownloaded cloud files.

        Returns:
            List of dicts with track/cloud file info
        """
        return self._db.get_favorites_with_cloud()

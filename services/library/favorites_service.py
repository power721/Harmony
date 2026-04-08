"""
Favorites service - Manages favorite tracks and cloud files.
"""

import logging
from typing import List

from domain.track import Track
from repositories.favorite_repository import SqliteFavoriteRepository
from system.event_bus import EventBus

logger = logging.getLogger(__name__)


class FavoritesService:
    """
    Service for managing favorite tracks and cloud files.

    Provides a clean API for UI components to interact with favorites
    without directly accessing the database layer.
    """

    def __init__(
        self,
        favorite_repo: SqliteFavoriteRepository,
        event_bus: EventBus = None
    ):
        """
        Initialize favorites service.

        Args:
            favorite_repo: Favorite repository for data persistence
            event_bus: Event bus for broadcasting changes
        """
        self._favorite_repo = favorite_repo
        self._event_bus = event_bus or EventBus.instance()

    def is_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        online_provider_id: str | None = None,
    ) -> bool:
        """
        Check if a track or cloud file is favorited.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID

        Returns:
            True if favorited, False otherwise
        """
        return self._favorite_repo.is_favorite(
            track_id=track_id,
            cloud_file_id=cloud_file_id,
            online_provider_id=online_provider_id,
        )

    def get_all_favorite_track_ids(self) -> set:
        """
        Get all favorite local track IDs as a set for O(1) lookup.

        Returns:
            Set of track IDs that are favorited
        """
        return self._favorite_repo.get_all_favorite_track_ids()

    def add_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        cloud_account_id: int = None,
        online_provider_id: str | None = None,
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
        result = self._favorite_repo.add_favorite(
            track_id=track_id,
            cloud_file_id=cloud_file_id,
            cloud_account_id=cloud_account_id,
            online_provider_id=online_provider_id,
        )
        if result:
            is_cloud = cloud_file_id is not None
            item_id = cloud_file_id if is_cloud else track_id
            self._event_bus.emit_favorite_change(item_id, True, is_cloud)
        return result

    def remove_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        online_provider_id: str | None = None,
    ) -> bool:
        """
        Remove a track or cloud file from favorites.

        Args:
            track_id: Local track ID
            cloud_file_id: Cloud file ID

        Returns:
            True if removed, False if not found
        """
        result = self._favorite_repo.remove_favorite(
            track_id=track_id,
            cloud_file_id=cloud_file_id,
            online_provider_id=online_provider_id,
        )
        if result:
            is_cloud = cloud_file_id is not None
            item_id = cloud_file_id if is_cloud else track_id
            self._event_bus.emit_favorite_change(item_id, False, is_cloud)
        return result

    def toggle_favorite(
        self,
        track_id: int = None,
        cloud_file_id: str = None,
        cloud_account_id: int = None,
        online_provider_id: str | None = None,
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
        is_fav = self.is_favorite(
            track_id=track_id,
            cloud_file_id=cloud_file_id,
            online_provider_id=online_provider_id,
        )

        if is_fav:
            removed = self.remove_favorite(
                track_id=track_id,
                cloud_file_id=cloud_file_id,
                online_provider_id=online_provider_id,
            )
            return False, removed
        else:
            added = self.add_favorite(
                track_id=track_id,
                cloud_file_id=cloud_file_id,
                cloud_account_id=cloud_account_id,
                online_provider_id=online_provider_id,
            )
            return True, added

    def get_favorites(self) -> List[Track]:
        """
        Get all favorite tracks (local tracks and downloaded cloud files).

        Returns:
            List of Track objects
        """
        return self._favorite_repo.get_favorites()

    def get_favorites_with_cloud(self) -> List[dict]:
        """
        Get all favorites including local tracks and undownloaded cloud files.

        Returns:
            List of dicts with track/cloud file info
        """
        return self._favorite_repo.get_favorites_with_cloud()

"""
Cloud file service - Manages cloud file metadata.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from domain.cloud import CloudFile
from system.event_bus import EventBus

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class CloudFileService:
    """
    Service for managing cloud file metadata.

    Provides a clean API for UI components to interact with cloud files
    without directly accessing the database layer.
    """

    def __init__(self, db_manager: "DatabaseManager", event_bus: EventBus = None):
        """
        Initialize cloud file service.

        Args:
            db_manager: Database manager for data persistence
            event_bus: Event bus for broadcasting changes
        """
        self._db = db_manager
        self._event_bus = event_bus or EventBus.instance()

    def get_files(self, account_id: int, parent_id: str = "") -> List[CloudFile]:
        """
        Get cached files for an account and parent folder.

        Args:
            account_id: Cloud account ID
            parent_id: Parent folder ID (empty string for root)

        Returns:
            List of CloudFile objects
        """
        return self._db.get_cloud_files(account_id=account_id, parent_id=parent_id)

    def get_file(self, file_id: str, account_id: int) -> Optional[CloudFile]:
        """
        Get a cloud file by ID and account.

        Args:
            file_id: File ID
            account_id: Cloud account ID

        Returns:
            CloudFile or None if not found
        """
        return self._db.get_cloud_file(file_id=file_id, account_id=account_id)

    def get_file_by_file_id(self, file_id: str) -> Optional[CloudFile]:
        """
        Get a cloud file by file ID only.

        Args:
            file_id: File ID

        Returns:
            CloudFile or None if not found
        """
        return self._db.get_cloud_file_by_file_id(file_id)

    def get_file_by_local_path(self, local_path: str) -> Optional[CloudFile]:
        """
        Get a cloud file by its local path.

        Args:
            local_path: Local file path

        Returns:
            CloudFile or None if not found
        """
        return self._db.get_cloud_file_by_local_path(local_path)

    def cache_files(self, account_id: int, files: List[CloudFile]) -> bool:
        """
        Cache cloud file metadata for current folder.

        This preserves local_path and files from other folders.

        Args:
            account_id: Cloud account ID
            files: List of CloudFile objects to cache

        Returns:
            True if cached successfully
        """
        return self._db.cache_cloud_files(account_id=account_id, files=files)

    def update_local_path(self, file_id: str, account_id: int, local_path: str) -> bool:
        """
        Update the local path for a downloaded cloud file.

        Args:
            file_id: File ID
            account_id: Cloud account ID
            local_path: Local file path

        Returns:
            True if updated successfully
        """
        result = self._db.update_cloud_file_local_path(
            file_id=file_id,
            account_id=account_id,
            local_path=local_path
        )
        if result:
            logger.debug(f"[CloudFileService] Updated local path for file {file_id}")
        return result

    def get_all_downloaded_files(self) -> List[CloudFile]:
        """
        Get all cloud files that have been downloaded.

        Returns:
            List of CloudFile objects with local_path
        """
        return self._db.get_all_downloaded_cloud_files()

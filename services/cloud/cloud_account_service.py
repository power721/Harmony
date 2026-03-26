"""
Cloud account service - Manages cloud storage accounts.
"""

import logging
from typing import List, Optional, TYPE_CHECKING

from domain.cloud import CloudAccount
from system.event_bus import EventBus

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager
    from repositories.cloud_repository import SqliteCloudRepository

logger = logging.getLogger(__name__)


class CloudAccountService:
    """
    Service for managing cloud storage accounts.

    Provides a clean API for UI components to interact with cloud accounts
    without directly accessing the database layer.
    """

    def __init__(
        self,
        db_manager: "DatabaseManager",
        event_bus: EventBus = None,
        cloud_repo: "SqliteCloudRepository" = None,
    ):
        """
        Initialize cloud account service.

        Args:
            db_manager: Database manager for data persistence
            event_bus: Event bus for broadcasting changes
            cloud_repo: Cloud repository for account operations
        """
        self._db = db_manager
        self._event_bus = event_bus or EventBus.instance()
        self._cloud_repo = cloud_repo

    def get_accounts(self, provider: str = None) -> List[CloudAccount]:
        """
        Get all cloud accounts, optionally filtered by provider.

        Args:
            provider: Optional provider filter (e.g., "quark", "baidu")

        Returns:
            List of CloudAccount objects
        """
        return self._db.get_cloud_accounts(provider=provider)

    def get_account(self, account_id: int) -> Optional[CloudAccount]:
        """
        Get a cloud account by ID.

        Args:
            account_id: Account ID

        Returns:
            CloudAccount or None if not found
        """
        return self._db.get_cloud_account(account_id)

    def create_account(
        self,
        provider: str,
        account_name: str,
        account_email: str,
        access_token: str,
        refresh_token: str = ""
    ) -> int:
        """
        Create a new cloud account.

        Args:
            provider: Cloud provider (e.g., "quark", "baidu")
            account_name: Display name for the account
            account_email: Account email
            access_token: OAuth access token
            refresh_token: OAuth refresh token

        Returns:
            New account ID
        """
        account_id = self._db.create_cloud_account(
            provider=provider,
            account_name=account_name,
            account_email=account_email,
            access_token=access_token,
            refresh_token=refresh_token
        )
        logger.info(f"[CloudAccountService] Created account: {account_name} ({provider})")
        return account_id

    def update_token(
        self,
        account_id: int,
        access_token: str,
        refresh_token: str = None
    ) -> bool:
        """
        Update account tokens.

        Args:
            account_id: Account ID
            access_token: New access token
            refresh_token: New refresh token (optional)

        Returns:
            True if updated successfully
        """
        result = self._db.update_cloud_account_token(
            account_id=account_id,
            access_token=access_token,
            refresh_token=refresh_token
        )
        if result:
            logger.debug(f"[CloudAccountService] Updated token for account {account_id}")
        return result

    def update_folder(
        self,
        account_id: int,
        folder_id: str,
        folder_path: str,
        parent_folder_id: str = "0",
        fid_path: str = "0"
    ) -> bool:
        """
        Update the last opened folder for an account.

        Args:
            account_id: Account ID
            folder_id: Current folder ID
            folder_path: Display path for the folder
            parent_folder_id: Parent folder ID
            fid_path: Full path of folder IDs

        Returns:
            True if updated successfully
        """
        return self._db.update_cloud_account_folder(
            account_id=account_id,
            folder_id=folder_id,
            folder_path=folder_path,
            parent_folder_id=parent_folder_id,
            fid_path=fid_path
        )

    def update_playing_state(
        self,
        account_id: int,
        playing_fid: str = None,
        position: float = None,
        local_path: str = None
    ) -> bool:
        """
        Update the last playing file and position for an account.

        Args:
            account_id: Account ID
            playing_fid: File ID of the playing file
            position: Playback position in seconds
            local_path: Local path of the downloaded file

        Returns:
            True if updated successfully
        """
        return self._db.update_cloud_account_playing_state(
            account_id=account_id,
            playing_fid=playing_fid,
            position=position,
            local_path=local_path
        )

    def delete_account(self, account_id: int) -> bool:
        """
        Delete a cloud account.

        Args:
            account_id: Account ID to delete

        Returns:
            True if deleted successfully
        """
        # Use injected cloud_repo for deletion
        if self._cloud_repo:
            return self._cloud_repo.delete_account(account_id)
        # Fallback to db_manager
        return self._db.delete_cloud_account(account_id)

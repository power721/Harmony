"""
SQLite implementation of CloudRepository.
"""

import sqlite3
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from domain.cloud import CloudAccount, CloudFile
from infrastructure.security import SecretStore
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteCloudRepository(BaseRepository):
    """SQLite implementation of CloudRepository."""

    def __init__(
        self,
        db_path: str = "Harmony.db",
        db_manager: "DatabaseManager" = None,
        secret_store: Optional[SecretStore] = None,
    ):
        super().__init__(db_path, db_manager)
        self._secret_store = secret_store or SecretStore.default()

    # ===== Cloud Account methods =====

    def get_account_by_id(self, account_id: int) -> Optional[CloudAccount]:
        """Get a cloud account by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cloud_accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_account(row)
        return None

    def get_all_accounts(self, provider: str = None) -> List[CloudAccount]:
        """Get all cloud accounts, optionally filtered by provider."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if provider:
            cursor.execute(
                """
                SELECT * FROM cloud_accounts
                WHERE provider = ? AND is_active = 1
                ORDER BY created_at DESC
                """,
                (provider,),
            )
        else:
            cursor.execute(
                """
                SELECT * FROM cloud_accounts
                WHERE is_active = 1
                ORDER BY created_at DESC
                """
            )

        rows = cursor.fetchall()
        return [self._row_to_account(row) for row in rows]

    def create_account(
        self,
        provider: str,
        account_name: str,
        account_email: str,
        access_token: str,
        refresh_token: str = "",
    ) -> int:
        """Create a new cloud account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO cloud_accounts
                (provider, account_name, account_email, access_token, refresh_token)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                provider,
                account_name,
                account_email,
                self._encrypt_secret(access_token),
                self._encrypt_secret(refresh_token),
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def add_account(self, account: CloudAccount) -> int:
        """Add a new cloud account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO cloud_accounts (provider, account_name, account_email, access_token, refresh_token,
                                                   token_expires_at, is_active, last_folder_path, last_fid_path,
                                                   last_playing_fid, last_position, last_playing_local_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           account.provider, account.account_name, account.account_email,
                           self._encrypt_secret(account.access_token),
                           self._encrypt_secret(account.refresh_token),
                           account.token_expires_at,
                           account.is_active, account.last_folder_path, account.last_fid_path,
                           account.last_playing_fid, account.last_position, account.last_playing_local_path
                       ))
        conn.commit()
        return cursor.lastrowid

    def update_account(self, account: CloudAccount) -> bool:
        """Update a cloud account."""
        if not account.id:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       UPDATE cloud_accounts
                       SET provider                = ?,
                           account_name            = ?,
                           account_email           = ?,
                           access_token            = ?,
                           refresh_token           = ?,
                           token_expires_at        = ?,
                           is_active               = ?,
                           last_folder_path        = ?,
                           last_fid_path           = ?,
                           last_playing_fid        = ?,
                           last_position           = ?,
                           last_playing_local_path = ?
                       WHERE id = ?
                       """, (
                           account.provider, account.account_name, account.account_email,
                           self._encrypt_secret(account.access_token),
                           self._encrypt_secret(account.refresh_token),
                           account.token_expires_at,
                           account.is_active, account.last_folder_path, account.last_fid_path,
                           account.last_playing_fid, account.last_position, account.last_playing_local_path,
                           account.id
                       ))
        conn.commit()
        return cursor.rowcount > 0

    def update_account_token(
        self, account_id: int, access_token: str, refresh_token: str = None
    ) -> bool:
        """Update account tokens."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if refresh_token is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token  = ?,
                    refresh_token = ?,
                    updated_at    = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    self._encrypt_secret(access_token),
                    self._encrypt_secret(refresh_token),
                    account_id,
                ),
            )
        else:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token = ?,
                    updated_at   = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (self._encrypt_secret(access_token), account_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def update_account_folder(
        self, account_id: int, folder_id: str, folder_path: str, parent_folder_id: str = "0", fid_path: str = "0"
    ) -> bool:
        """Update the last opened folder for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_accounts
            SET last_folder_path = ?,
                last_fid_path    = ?,
                updated_at       = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (folder_path, fid_path, account_id),
        )

        conn.commit()
        return cursor.rowcount > 0

    def update_account_playing_state(
        self, account_id: int, playing_fid: str = None, position: float = None, local_path: str = None
    ) -> bool:
        """Update the last playing file and position for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build update query dynamically based on provided parameters
        if playing_fid is not None and position is not None and local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid        = ?,
                    last_position           = ?,
                    last_playing_local_path = ?,
                    updated_at              = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, position, local_path, account_id),
            )
        elif playing_fid is not None and position is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?,
                    last_position    = ?,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, position, account_id),
            )
        elif playing_fid is not None and local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid        = ?,
                    last_playing_local_path = ?,
                    updated_at              = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, local_path, account_id),
            )
        elif playing_fid is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, account_id),
            )
        elif position is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_position = ?,
                    updated_at    = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (position, account_id),
            )
        elif local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_local_path = ?,
                    updated_at              = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (local_path, account_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def delete_account(self, account_id: int) -> bool:
        """Delete a cloud account (soft delete - sets is_active to False)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_accounts
            SET is_active  = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (account_id,),
        )

        conn.commit()
        return cursor.rowcount > 0

    def hard_delete_account(self, account_id: int) -> bool:
        """Hard delete a cloud account and associated files."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM cloud_accounts WHERE id = ?", (account_id,))
            if cursor.fetchone() is None:
                return False
            # Delete associated files first
            cursor.execute("DELETE FROM cloud_files WHERE account_id = ?", (account_id,))
            # Delete account
            cursor.execute("DELETE FROM cloud_accounts WHERE id = ?", (account_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            raise

    # ===== Cloud File methods =====

    def get_file_by_id(self, file_id: str) -> Optional[CloudFile]:
        """Get a cloud file by file ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cloud_files WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_file(row)
        return None

    def get_file_by_file_id(self, file_id: str) -> Optional[CloudFile]:
        """Get a cloud file by file ID (alias for get_file_by_id)."""
        return self.get_file_by_id(file_id)

    def get_files_by_file_ids(self, file_ids: List[str]) -> List[CloudFile]:
        """
        Get multiple cloud files by their file IDs.

        Args:
            file_ids: List of file IDs to fetch

        Returns:
            List of CloudFile objects (only files that are found)
        """
        if not file_ids:
            return []

        conn = self._get_connection()
        cursor = conn.cursor()

        # Use IN clause for batch lookup
        placeholders = ','.join(['?' for _ in file_ids])
        cursor.execute(
            f"SELECT * FROM cloud_files WHERE file_id IN ({placeholders})",
            file_ids
        )
        rows = cursor.fetchall()

        return [self._row_to_file(row) for row in rows]

    def get_file_by_local_path(self, local_path: str) -> Optional[CloudFile]:
        """Get a cloud file by its local path."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE local_path = ?
            """,
            (local_path,),
        )

        row = cursor.fetchone()
        if row:
            return self._row_to_file(row)
        return None

    def get_files_by_account(self, account_id: int) -> List[CloudFile]:
        """Get all files for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cloud_files WHERE account_id = ?", (account_id,))
        rows = cursor.fetchall()
        return [self._row_to_file(row) for row in rows]

    def get_files_by_parent(self, account_id: int, parent_id: str = "") -> List[CloudFile]:
        """Get cached files for an account and parent folder."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE account_id = ? AND parent_id = ?
            ORDER BY file_type DESC, name ASC
            """,
            (account_id, parent_id),
        )

        rows = cursor.fetchall()
        return [self._row_to_file(row) for row in rows]

    def get_file(self, file_id: str, account_id: int) -> Optional[CloudFile]:
        """Get a cloud file by ID and account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE file_id = ? AND account_id = ?
            """,
            (file_id, account_id),
        )

        row = cursor.fetchone()
        if row:
            return self._row_to_file(row)
        return None

    def get_all_downloaded(self) -> List[CloudFile]:
        """Get all cloud files that have been downloaded (have local_path)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE local_path IS NOT NULL AND local_path != ''
            ORDER BY name ASC
            """
        )

        rows = cursor.fetchall()
        return [self._row_to_file(row) for row in rows]

    def add_file(self, file: CloudFile) -> int:
        """Add a cloud file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       INSERT INTO cloud_files (account_id, file_id, parent_id, name, file_type, size,
                                                mime_type, duration, metadata, local_path)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       """, (
                           file.account_id, file.file_id, file.parent_id, file.name,
                           file.file_type, file.size, file.mime_type, file.duration,
                           file.metadata, file.local_path
                       ))
        conn.commit()
        return cursor.lastrowid

    def cache_files(
        self,
        account_id: int,
        files: List[CloudFile],
        parent_id: Optional[str] = None,
    ) -> bool:
        """Cache cloud file metadata for current folder (preserve local_path and other folders)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get the parent_id from the explicit argument or first file.
        if parent_id is None:
            if not files:
                return True
            parent_id = files[0].parent_id

        if not files:
            cursor.execute(
                "DELETE FROM cloud_files WHERE account_id = ? AND parent_id = ?",
                (account_id, parent_id),
            )
            conn.commit()
            return True

        # First, get existing local_paths for files in this folder
        cursor.execute(
            "SELECT file_id, local_path FROM cloud_files WHERE account_id = ? AND parent_id = ? AND local_path IS NOT NULL",
            (account_id, parent_id)
        )
        existing_paths = {row["file_id"]: row["local_path"] for row in cursor.fetchall()}

        # Delete old cache only for this folder (not the entire account)
        cursor.execute("DELETE FROM cloud_files WHERE account_id = ? AND parent_id = ?", (account_id, parent_id))

        # Insert new files in batch, preserving local_path if it existed
        file_data = [
            (
                account_id,
                file.file_id,
                file.parent_id,
                file.name,
                file.file_type,
                file.size,
                file.mime_type,
                file.duration,
                file.metadata,
                existing_paths.get(file.file_id),  # Preserve local_path
            )
            for file in files
        ]

        cursor.executemany(
            """
            INSERT INTO cloud_files
            (account_id, file_id, parent_id, name, file_type, size, mime_type, duration, metadata, local_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            file_data,
        )

        conn.commit()
        return True

    def update_local_path(self, file_id: str, local_path: str) -> bool:
        """Update a cloud file's local path."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE cloud_files
            SET local_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE file_id = ?
            """,
            (local_path, file_id)
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_file_local_path(self, file_id: str, account_id: int, local_path: str) -> bool:
        """Update the local path for a downloaded cloud file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE cloud_files
            SET local_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE file_id = ? AND account_id = ?
            """,
            (local_path, file_id, account_id),
        )
        conn.commit()
        return cursor.rowcount > 0

    def _row_to_account(self, row: sqlite3.Row) -> CloudAccount:
        """Convert a database row to a CloudAccount object."""
        return CloudAccount(
            id=row["id"],
            provider=row["provider"],
            account_name=row["account_name"],
            account_email=row["account_email"],
            access_token=self._decrypt_secret(row["access_token"]),
            refresh_token=self._decrypt_secret(row["refresh_token"]),
            token_expires_at=datetime.fromisoformat(row["token_expires_at"])
            if row["token_expires_at"]
            else None,
            is_active=bool(row["is_active"]),
            last_folder_path=row["last_folder_path"] or "/",
            last_fid_path=row["last_fid_path"] if "last_fid_path" in row.keys() else "0",
            last_playing_fid=row["last_playing_fid"] if "last_playing_fid" in row.keys() else "",
            last_position=row["last_position"] if "last_position" in row.keys() else 0.0,
            last_playing_local_path=row[
                "last_playing_local_path"] if "last_playing_local_path" in row.keys() else "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def _row_to_file(self, row: sqlite3.Row) -> CloudFile:
        """Convert a database row to a CloudFile object."""
        return CloudFile(
            id=row["id"],
            account_id=row["account_id"],
            file_id=row["file_id"],
            parent_id=row["parent_id"],
            name=row["name"],
            file_type=row["file_type"],
            size=row["size"],
            mime_type=row["mime_type"],
            duration=row["duration"],
            metadata=row["metadata"],
            local_path=row["local_path"] if "local_path" in row.keys() else None,
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )

    def get_account_id_by_file_id(self, file_id: str) -> Optional[int]:
        """Get account_id for a cloud file by file_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT account_id FROM cloud_files WHERE file_id = ?", (file_id,))
        row = cursor.fetchone()
        if row:
            return row["account_id"]
        return None

    def _encrypt_secret(self, value: Optional[str]) -> str:
        """Encrypt a persisted secret value."""
        return self._secret_store.encrypt(value)

    def _decrypt_secret(self, value: Optional[str]) -> str:
        """Decrypt a persisted secret value, keeping plaintext rows readable."""
        return self._secret_store.decrypt(value)

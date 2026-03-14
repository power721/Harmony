"""
SQLite implementation of CloudRepository.
"""

import sqlite3
import threading
from typing import List, Optional

from domain.cloud import CloudAccount, CloudFile


class SqliteCloudRepository:
    """SQLite implementation of CloudRepository."""

    def __init__(self, db_path: str = "music_player.db"):
        self.db_path = db_path
        self.local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

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

    def get_all_accounts(self) -> List[CloudAccount]:
        """Get all cloud accounts."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cloud_accounts ORDER BY id DESC")
        rows = cursor.fetchall()
        return [self._row_to_account(row) for row in rows]

    def add_account(self, account: CloudAccount) -> int:
        """Add a new cloud account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cloud_accounts (
                provider, account_name, account_email, access_token, refresh_token,
                token_expires_at, is_active, last_folder_path, last_fid_path,
                last_playing_fid, last_position, last_playing_local_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account.provider, account.account_name, account.account_email,
            account.access_token, account.refresh_token, account.token_expires_at,
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
            UPDATE cloud_accounts SET
                provider = ?, account_name = ?, account_email = ?, access_token = ?,
                refresh_token = ?, token_expires_at = ?, is_active = ?,
                last_folder_path = ?, last_fid_path = ?, last_playing_fid = ?,
                last_position = ?, last_playing_local_path = ?
            WHERE id = ?
        """, (
            account.provider, account.account_name, account.account_email,
            account.access_token, account.refresh_token, account.token_expires_at,
            account.is_active, account.last_folder_path, account.last_fid_path,
            account.last_playing_fid, account.last_position, account.last_playing_local_path,
            account.id
        ))
        conn.commit()
        return cursor.rowcount > 0

    def delete_account(self, account_id: int) -> bool:
        """Delete a cloud account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Delete associated files first
        cursor.execute("DELETE FROM cloud_files WHERE account_id = ?", (account_id,))
        # Delete account
        cursor.execute("DELETE FROM cloud_accounts WHERE id = ?", (account_id,))
        conn.commit()
        return cursor.rowcount > 0

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

    def get_files_by_account(self, account_id: int) -> List[CloudFile]:
        """Get all files for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cloud_files WHERE account_id = ?", (account_id,))
        rows = cursor.fetchall()
        return [self._row_to_file(row) for row in rows]

    def add_file(self, file: CloudFile) -> int:
        """Add a cloud file."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO cloud_files (
                account_id, file_id, parent_id, name, file_type, size,
                mime_type, duration, metadata, local_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file.account_id, file.file_id, file.parent_id, file.name,
            file.file_type, file.size, file.mime_type, file.duration,
            file.metadata, file.local_path
        ))
        conn.commit()
        return cursor.lastrowid

    def _row_to_account(self, row: sqlite3.Row) -> CloudAccount:
        """Convert a database row to a CloudAccount object."""
        return CloudAccount(
            id=row["id"],
            provider=row["provider"],
            account_name=row["account_name"],
            account_email=row["account_email"],
            access_token=row["access_token"],
            refresh_token=row["refresh_token"],
            is_active=row["is_active"],
            last_folder_path=row["last_folder_path"],
            last_fid_path=row["last_fid_path"],
            last_playing_fid=row["last_playing_fid"],
            last_position=row["last_position"],
            last_playing_local_path=row["last_playing_local_path"],
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
            local_path=row["local_path"],
        )

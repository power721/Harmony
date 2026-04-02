"""
Base class for SQLite repositories.
"""
import sqlite3
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class BaseRepository:
    """Base class for SQLite repositories with common connection handling."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        self.db_path = db_path
        self._db_manager = db_manager
        self.local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection from db_manager or create thread-local connection."""
        if self._db_manager:
            return self._db_manager._get_connection()

        # Fallback: create thread-local connection (for tests)
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self.local.conn.row_factory = sqlite3.Row
            self.local.conn.execute("PRAGMA journal_mode=WAL")
            self.local.conn.execute("PRAGMA busy_timeout=30000")
        return self.local.conn

    def close(self):
        """Close the thread-local connection if it exists."""
        if hasattr(self.local, "conn") and self.local.conn:
            try:
                self.local.conn.close()
            except Exception:
                pass
            self.local.conn = None

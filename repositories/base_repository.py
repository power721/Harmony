"""
Base class for SQLite repositories.
"""
import logging
import sqlite3
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class BaseRepository:
    """Base class for SQLite repositories with common connection handling."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager | None" = None):
        self.db_path = db_path
        self._db_manager = db_manager
        self.local = threading.local()
        self._table_exists_cache: dict[str, bool] = {}

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
            try:
                self.local.conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                # Another thread may already be switching journal mode on a shared
                # test database. The connection remains usable without failing init.
                logger.debug("[BaseRepository] Failed to enable WAL mode for %s", self.db_path, exc_info=True)
            self.local.conn.execute("PRAGMA busy_timeout=30000")
        return self.local.conn

    def close(self):
        """Close the thread-local connection if it exists."""
        if hasattr(self.local, "conn") and self.local.conn:
            try:
                self.local.conn.close()
            except Exception:
                logger.debug("[BaseRepository] Failed to close connection for %s", self.db_path, exc_info=True)
            self.local.conn = None

    @staticmethod
    def _require_lastrowid(cursor: sqlite3.Cursor) -> int:
        """Return a concrete lastrowid after a successful insert."""
        lastrowid = cursor.lastrowid
        if lastrowid is None:
            raise RuntimeError("SQLite cursor.lastrowid was unexpectedly None")
        return int(lastrowid)

    def _table_exists(self, table_name: str) -> bool:
        """Return whether a table exists, caching the schema lookup per repository instance."""
        cached = self._table_exists_cache.get(table_name)
        if cached is not None:
            return cached

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table_name,),
        )
        exists = cursor.fetchone() is not None
        self._table_exists_cache[table_name] = exists
        return exists

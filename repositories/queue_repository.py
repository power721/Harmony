"""
SQLite implementation of QueueRepository.
"""

import sqlite3
import threading
from typing import List, TYPE_CHECKING
from datetime import datetime

from domain.playback import PlayQueueItem

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteQueueRepository:
    """SQLite implementation of QueueRepository."""

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
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self.local.conn.row_factory = sqlite3.Row
            self.local.conn.execute("PRAGMA journal_mode=WAL")
            self.local.conn.execute("PRAGMA busy_timeout=30000")
        return self.local.conn

    def load(self) -> List[PlayQueueItem]:
        """Load the saved play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM play_queue ORDER BY position")
        rows = cursor.fetchall()

        if not rows:
            return []

        # Get column names to handle both old and new schema
        columns = rows[0].keys()

        def get_source(row, columns):
            """Get source value, handling both old and new schema."""
            if "source" in columns:
                return row["source"] or "Local"
            # Old schema: combine source_type and cloud_type
            if "source_type" in columns:
                source_type = row["source_type"]
                cloud_type = row["cloud_type"] if "cloud_type" in columns else ""
                if source_type == "local":
                    return "Local"
                elif source_type == "online":
                    return "QQ"
                elif source_type == "cloud" and cloud_type:
                    return cloud_type.upper()
            return "Local"

        return [
            PlayQueueItem(
                id=row["id"],
                position=row["position"],
                source=get_source(row, columns),
                track_id=row["track_id"],
                cloud_file_id=row["cloud_file_id"],
                cloud_account_id=row["cloud_account_id"],
                local_path=row["local_path"] or "",
                title=row["title"] or "",
                artist=row["artist"] or "",
                album=row["album"] or "",
                duration=row["duration"] or 0.0,
                created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else None,
            )
            for row in rows
        ]

    def save(self, items: List[PlayQueueItem]) -> bool:
        """Save the play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Clear existing queue
        cursor.execute("DELETE FROM play_queue")
        # Insert new items
        for item in items:
            cursor.execute("""
                           INSERT INTO play_queue (position, source, track_id, cloud_file_id,
                                                   cloud_account_id, local_path, title, artist, album, duration, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           """, (
                               item.position, item.source, item.track_id,
                               item.cloud_file_id, item.cloud_account_id, item.local_path,
                               item.title, item.artist, item.album, item.duration,
                               item.created_at or datetime.now()
                           ))
        conn.commit()
        return True

    def clear(self) -> bool:
        """Clear the saved play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM play_queue")
        conn.commit()
        return True

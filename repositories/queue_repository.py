"""
SQLite implementation of QueueRepository.
"""

import sqlite3
import threading
from typing import List

from domain.playback import PlayQueueItem


class SqliteQueueRepository:
    """SQLite implementation of QueueRepository."""

    def __init__(self, db_path: str = "Harmony.db"):
        self.db_path = db_path
        self.local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

    def load(self) -> List[PlayQueueItem]:
        """Load the saved play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM play_queue ORDER BY position")
        rows = cursor.fetchall()
        return [self._row_to_item(row) for row in rows]

    def save(self, items: List[PlayQueueItem]) -> bool:
        """Save the play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Clear existing queue
        cursor.execute("DELETE FROM play_queue")
        # Insert new items
        for item in items:
            cursor.execute("""
                           INSERT INTO play_queue (position, source_type, cloud_type, track_id, cloud_file_id,
                                                   cloud_account_id, local_path, title, artist, album, duration)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           """, (
                               item.position, item.source_type, item.cloud_type, item.track_id,
                               item.cloud_file_id, item.cloud_account_id, item.local_path,
                               item.title, item.artist, item.album, item.duration
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

    def _row_to_item(self, row: sqlite3.Row) -> PlayQueueItem:
        """Convert a database row to a PlayQueueItem object."""
        return PlayQueueItem(
            id=row["id"],
            position=row["position"],
            source_type=row["source_type"],
            cloud_type=row["cloud_type"],
            track_id=row["track_id"],
            cloud_file_id=row["cloud_file_id"],
            cloud_account_id=row["cloud_account_id"],
            local_path=row["local_path"],
            title=row["title"],
            artist=row["artist"],
            album=row["album"],
            duration=row["duration"],
        )

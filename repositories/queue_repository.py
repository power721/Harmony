"""
SQLite implementation of QueueRepository.
"""

import logging
import sqlite3
from datetime import datetime
from typing import List, TYPE_CHECKING

from domain.playback import PlayQueueItem
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteQueueRepository(BaseRepository):
    """SQLite implementation of QueueRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)

    @staticmethod
    def _normalize_online_provider_id(value):
        normalized = str(value or "").strip()
        if not normalized or normalized.lower() == "online":
            return None
        return normalized

    def load(self) -> List[PlayQueueItem]:
        """Load the saved play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM play_queue ORDER BY position")
        rows = cursor.fetchall()

        if not rows:
            return []

        # Get column names to handle both old and new schema
        columns = rows[0].keys() if rows else []

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
                    return "ONLINE"
                elif source_type == "cloud" and cloud_type:
                    return cloud_type.upper()
            return "Local"

        def get_download_failed(row, columns):
            """Get download_failed value, handling schema migration."""
            if "download_failed" in columns:
                return bool(row["download_failed"])
            return False

        normalized_items = [
            PlayQueueItem(
                id=row["id"],
                position=row["position"],
                source=get_source(row, columns),
                track_id=row["track_id"],
                cloud_file_id=row["cloud_file_id"],
                online_provider_id=self._normalize_online_provider_id(
                    row["online_provider_id"] if "online_provider_id" in columns else None
                ),
                cloud_account_id=row["cloud_account_id"],
                local_path=row["local_path"] or "",
                title=row["title"] or "",
                artist=row["artist"] or "",
                album=row["album"] or "",
                duration=row["duration"] or 0.0,
                download_failed=get_download_failed(row, columns),
                created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else None,
            )
            for row in rows
        ]
        if "online_provider_id" in columns:
            repair_ids = [
                row["id"]
                for row in rows
                if self._normalize_online_provider_id(row["online_provider_id"]) is None
                and str(row["online_provider_id"] or "").strip().lower() == "online"
            ]
            if repair_ids:
                placeholders = ",".join("?" * len(repair_ids))
                cursor.execute(
                    f"UPDATE play_queue SET online_provider_id = NULL WHERE id IN ({placeholders})",
                    repair_ids,
                )
                conn.commit()
        return normalized_items

    def save(self, items: List[PlayQueueItem]) -> bool:
        """Save the play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Clear existing queue
            cursor.execute("DELETE FROM play_queue")
            # Batch insert using executemany for better performance
            if items:
                cursor.executemany("""
                                   INSERT INTO play_queue (position, source, track_id, cloud_file_id,
                                                           online_provider_id, cloud_account_id, local_path, title, artist, album, duration, created_at,
                                                           download_failed)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                   """, [
                                       (item.position, item.source, item.track_id,
                                        item.cloud_file_id, self._normalize_online_provider_id(item.online_provider_id),
                                        item.cloud_account_id, item.local_path,
                                        item.title, item.artist, item.album, item.duration,
                                        (item.created_at or datetime.now()).isoformat(sep=" "),
                                        int(item.download_failed))
                                       for item in items
                                   ])
            conn.commit()
            return True
        except sqlite3.Error as e:
            conn.rollback()
            logging.error(f"Failed to save play queue: {e}")
            return False

    def clear(self) -> bool:
        """Clear the saved play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM play_queue")
        conn.commit()
        return True

    def update_local_path(self, track_id: int, local_path: str) -> bool:
        """Update local_path for all play_queue entries with the given track_id."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE play_queue SET local_path = ? WHERE track_id = ?",
            (local_path, track_id)
        )
        conn.commit()
        return True

    def count(self) -> int:
        """Get the number of items in the play queue."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM play_queue")
        row = cursor.fetchone()
        return row["count"] if row else 0

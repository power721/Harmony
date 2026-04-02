"""
SQLite implementation of HistoryRepository.
"""

from datetime import datetime
from typing import List, TYPE_CHECKING

from domain.history import PlayHistory
from domain.track import Track, TrackId
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqliteHistoryRepository(BaseRepository):
    """SQLite implementation of HistoryRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)
        # Import here to avoid circular import
        from repositories.track_repository import SqliteTrackRepository
        self._track_repo = SqliteTrackRepository(db_path, db_manager)

    def add(self, track_id: TrackId) -> bool:
        """
        Add a play history entry.

        Args:
            track_id: Track ID to add to history

        Returns:
            True if added successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Single UPSERT: update timestamp if exists, insert if not
        cursor.execute("""
            INSERT INTO play_history (track_id, played_at)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(track_id) DO UPDATE SET played_at = CURRENT_TIMESTAMP
        """, (track_id,))

        conn.commit()
        return True

    def get_recent(self, limit: int = 50) -> List[PlayHistory]:
        """
        Get recently played tracks.

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of PlayHistory objects ordered by most recently played
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ph.id, ph.track_id, ph.played_at
            FROM play_history ph
            ORDER BY ph.played_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()

        return [
            PlayHistory(
                id=row["id"],
                track_id=row["track_id"],
                played_at=datetime.fromisoformat(row["played_at"]) if row["played_at"] else datetime.now()
            )
            for row in rows
        ]

    def get_recent_tracks(self, limit: int = 50) -> List[Track]:
        """
        Get recently played tracks (returns Track objects).

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of Track objects ordered by most recently played
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*
            FROM play_history ph
            JOIN tracks t ON ph.track_id = t.id
            ORDER BY ph.played_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [self._track_repo._row_to_track(row) for row in rows]

    def get_most_played(self, limit: int = 20) -> List[Track]:
        """
        Get most played tracks (returns Track objects).

        Args:
            limit: Maximum number of tracks to return

        Returns:
            List of Track objects ordered by play count (descending)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, SUM(ph.play_count) as total_plays
            FROM play_history ph
            JOIN tracks t ON ph.track_id = t.id
            GROUP BY t.id
            ORDER BY total_plays DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [self._track_repo._row_to_track(row) for row in rows]

    def clear(self) -> bool:
        """
        Clear all play history.

        Returns:
            True if cleared successfully
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM play_history")
        conn.commit()
        return True

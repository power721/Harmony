"""
SQLite implementation of PlaylistRepository.
"""

import sqlite3
import time
from typing import List, Optional, TYPE_CHECKING

from domain.playlist import Playlist
from domain.track import Track, TrackId
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from infrastructure.database import DatabaseManager


class SqlitePlaylistRepository(BaseRepository):
    """SQLite implementation of PlaylistRepository."""

    def __init__(self, db_path: str = "Harmony.db", db_manager: "DatabaseManager" = None):
        super().__init__(db_path, db_manager)
        # Import here to avoid circular import
        from repositories.track_repository import SqliteTrackRepository
        self._track_repo = SqliteTrackRepository(db_path, db_manager)

    def get_by_id(self, playlist_id: int) -> Optional[Playlist]:
        """Get a playlist by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()
        if row:
            return Playlist(
                id=row["id"],
                name=row["name"],
            )
        return None

    def get_all(self) -> List[Playlist]:
        """Get all playlists."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM playlists ORDER BY id DESC")
        rows = cursor.fetchall()
        return [Playlist(id=row["id"], name=row["name"]) for row in rows]

    def get_tracks(self, playlist_id: int) -> List[Track]:
        """Get all tracks in a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT t.*
                       FROM tracks t
                                JOIN playlist_items pi ON t.id = pi.track_id
                       WHERE pi.playlist_id = ?
                       ORDER BY pi.position
                       """, (playlist_id,))
        rows = cursor.fetchall()
        return [self._track_repo._row_to_track(row) for row in rows]

    def add(self, playlist: Playlist) -> int:
        """Add a new playlist and return its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO playlists (name) VALUES (?)", (playlist.name,))
        conn.commit()
        return cursor.lastrowid

    def update(self, playlist: Playlist) -> bool:
        """Update an existing playlist."""
        if not playlist.id:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE playlists SET name = ? WHERE id = ?", (playlist.name, playlist.id))
        conn.commit()
        return cursor.rowcount > 0

    def delete(self, playlist_id: int) -> bool:
        """Delete a playlist by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        # Delete playlist items first
        cursor.execute("DELETE FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
        # Delete playlist
        cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()
        return cursor.rowcount > 0

    def add_track(self, playlist_id: int, track_id: TrackId) -> bool:
        """Add a track to a playlist.

        Returns True if track was added, False if it already exists.
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                # Get next position
                cursor.execute("SELECT MAX(position) FROM playlist_items WHERE playlist_id = ?", (playlist_id,))
                row = cursor.fetchone()
                # Use is not None check because MAX can return 0 which is falsy
                position = (row[0] if row[0] is not None else -1) + 1

                cursor.execute("""
                               INSERT OR IGNORE INTO playlist_items (playlist_id, track_id, position)
                               VALUES (?, ?, ?)
                               """, (playlist_id, track_id, position))
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.OperationalError as e:
                if "locked" in str(e) and attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

    def remove_track(self, playlist_id: int, track_id: TrackId) -> bool:
        """Remove a track from a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
                       DELETE
                       FROM playlist_items
                       WHERE playlist_id = ?
                         AND track_id = ?
                       """, (playlist_id, track_id))
        conn.commit()
        return cursor.rowcount > 0

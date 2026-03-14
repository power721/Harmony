"""
SQLite implementation of TrackRepository.
"""

import sqlite3
import threading
from typing import List, Optional

from domain.track import Track, TrackId


class SqliteTrackRepository:
    """SQLite implementation of TrackRepository."""

    def __init__(self, db_path: str = "music_player.db"):
        self.db_path = db_path
        self.local = threading.local()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

    def get_by_id(self, track_id: TrackId) -> Optional[Track]:
        """Get a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

    def get_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE path = ?", (path,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

    def get_all(self) -> List[Track]:
        """Get all tracks."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks ORDER BY id DESC")
        rows = cursor.fetchall()
        return [self._row_to_track(row) for row in rows]

    def search(self, query: str, limit: int = 100) -> List[Track]:
        """Search tracks by query using FTS5 or LIKE fallback."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Try FTS5 search first
        try:
            cursor.execute("""
                SELECT t.* FROM tracks t
                JOIN tracks_fts fts ON t.id = fts.rowid
                WHERE tracks_fts MATCH ?
                ORDER BY t.id DESC
                LIMIT ?
            """, (query, limit))
            rows = cursor.fetchall()
            return [self._row_to_track(row) for row in rows]
        except sqlite3.OperationalError:
            # Fallback to LIKE search
            like_query = f"%{query}%"
            cursor.execute("""
                SELECT * FROM tracks
                WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
                ORDER BY id DESC
                LIMIT ?
            """, (like_query, like_query, like_query, limit))
            rows = cursor.fetchall()
            return [self._row_to_track(row) for row in rows]

    def add(self, track: Track) -> TrackId:
        """Add a new track and return its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO tracks (path, title, artist, album, duration, cover_path, cloud_file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                track.path, track.title, track.artist, track.album,
                track.duration, track.cover_path, track.cloud_file_id
            ))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            # Track already exists
            return 0

    def update(self, track: Track) -> bool:
        """Update an existing track."""
        if not track.id:
            return False
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tracks SET title = ?, artist = ?, album = ?, duration = ?, cover_path = ?, cloud_file_id = ?
            WHERE id = ?
        """, (
            track.title, track.artist, track.album, track.duration,
            track.cover_path, track.cloud_file_id, track.id
        ))
        conn.commit()
        return cursor.rowcount > 0

    def delete(self, track_id: TrackId) -> bool:
        """Delete a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()
        return cursor.rowcount > 0

    def get_by_cloud_file_id(self, cloud_file_id: str) -> Optional[Track]:
        """Get a track by cloud file ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_track(row)
        return None

    def _row_to_track(self, row: sqlite3.Row) -> Track:
        """Convert a database row to a Track object."""
        return Track(
            id=row["id"],
            path=row["path"],
            title=row["title"] or "",
            artist=row["artist"] or "",
            album=row["album"] or "",
            duration=row["duration"] or 0.0,
            cover_path=row["cover_path"],
            cloud_file_id=row["cloud_file_id"],
        )

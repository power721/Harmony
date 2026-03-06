"""
Database manager for the music player using SQLite.
"""

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import Track, Playlist, PlaylistItem, PlayHistory, Favorite


class DatabaseManager:
    """Manages SQLite database operations for the music player."""

    def __init__(self, db_path: str = "music_player.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.local = threading.local()
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.local.conn.row_factory = sqlite3.Row
        return self.local.conn

    def _init_database(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create tracks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL DEFAULT 0,
                cover_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create playlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create playlist_items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                playlist_id INTEGER NOT NULL,
                track_id INTEGER NOT NULL,
                position INTEGER NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                UNIQUE(playlist_id, track_id),
                UNIQUE(playlist_id, position)
            )
        """)

        # Create play_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS play_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL,
                played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                play_count INTEGER DEFAULT 1,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
            )
        """)

        # Create favorites table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER NOT NULL UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for better performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracks_artist
            ON tracks(artist)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_tracks_album
            ON tracks(album)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_play_history_track
            ON play_history(track_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_play_history_played_at
            ON play_history(played_at DESC)
        """)

        conn.commit()

        # Migration: add unique constraint if not exists
        try:
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_playlist_items_track
                ON playlist_items(playlist_id, track_id)
            """)
            conn.commit()
        except sqlite3.OperationalError:
            pass

    # Track operations

    def add_track(self, track: Track) -> int:
        """Add a track to the database. Returns track ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, title, artist, album, duration, cover_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                track.path,
                track.title,
                track.artist,
                track.album,
                track.duration,
                track.cover_path,
                track.created_at or datetime.now(),
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()

        if row:
            return Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def get_track_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks WHERE path = ?", (path,))
        row = cursor.fetchone()

        if row:
            return Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks ORDER BY artist, album, title")
        rows = cursor.fetchall()

        return [
            Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def search_tracks(self, query: str) -> List[Track]:
        """Search tracks by title, artist, or album."""
        conn = self._get_connection()
        cursor = conn.cursor()

        search_pattern = f"%{query}%"
        cursor.execute(
            """
            SELECT * FROM tracks
            WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
            ORDER BY artist, album, title
        """,
            (search_pattern, search_pattern, search_pattern),
        )

        rows = cursor.fetchall()

        return [
            Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def delete_track(self, track_id: int) -> bool:
        """Delete a track from the database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()

        return cursor.rowcount > 0

    def update_track(
        self, track_id: int, title: str = None, artist: str = None, album: str = None
    ) -> bool:
        """Update track metadata in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()

        updates = []
        params = []

        if title is not None:
            updates.append("title = ?")
            params.append(title)
        if artist is not None:
            updates.append("artist = ?")
            params.append(artist)
        if album is not None:
            updates.append("album = ?")
            params.append(album)

        if not updates:
            return False

        params.append(track_id)

        cursor.execute(
            f"""
            UPDATE tracks
            SET {", ".join(updates)}
            WHERE id = ?
        """,
            params,
        )

        conn.commit()
        return cursor.rowcount > 0

    # Playlist operations

    def create_playlist(self, name: str) -> int:
        """Create a new playlist. Returns playlist ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO playlists (name)
            VALUES (?)
        """,
            (name,),
        )

        conn.commit()
        return cursor.lastrowid

    def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
        """Get a playlist by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()

        if row:
            return Playlist(
                id=row["id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def get_all_playlists(self) -> List[Playlist]:
        """Get all playlists."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM playlists ORDER BY name")
        rows = cursor.fetchall()

        return [
            Playlist(
                id=row["id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def get_playlist_tracks(self, playlist_id: int) -> List[Track]:
        """Get all tracks in a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.* FROM tracks t
            INNER JOIN playlist_items pi ON t.id = pi.track_id
            WHERE pi.playlist_id = ?
            ORDER BY pi.position
        """,
            (playlist_id,),
        )

        rows = cursor.fetchall()

        return [
            Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def add_track_to_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Add a track to a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if already exists
        cursor.execute(
            "SELECT 1 FROM playlist_items WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        if cursor.fetchone():
            return False

        # Get the next position
        cursor.execute(
            "SELECT MAX(position) as max_pos FROM playlist_items WHERE playlist_id = ?",
            (playlist_id,),
        )

        result = cursor.fetchone()
        next_position = (result["max_pos"] or 0) + 1

        try:
            cursor.execute(
                "INSERT INTO playlist_items (playlist_id, track_id, position) VALUES (?, ?, ?)",
                (playlist_id, track_id, next_position),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_track_from_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Remove a track from a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM playlist_items
            WHERE playlist_id = ? AND track_id = ?
        """,
            (playlist_id, track_id),
        )

        # Reorder remaining items
        if cursor.rowcount > 0:
            cursor.execute(
                """
                UPDATE playlist_items
                SET position = position - 1
                WHERE playlist_id = ? AND position > (
                    SELECT position FROM playlist_items
                    WHERE playlist_id = ? AND track_id = ?
                )
            """,
                (playlist_id, playlist_id, track_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def delete_playlist(self, playlist_id: int) -> bool:
        """Delete a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()

        return cursor.rowcount > 0

    def remove_track(self, track_id: int) -> bool:
        """Remove a track from the library (does not delete the file)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()

        return cursor.rowcount > 0

    # Play history operations

    def add_play_history(self, track_id: int) -> int:
        """Add a play history entry or increment play count."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if there's a recent entry for today
        cursor.execute(
            """
            SELECT id, play_count FROM play_history
            WHERE track_id = ? AND DATE(played_at) = DATE('now')
            ORDER BY played_at DESC LIMIT 1
        """,
            (track_id,),
        )

        row = cursor.fetchone()

        if row:
            # Increment play count
            cursor.execute(
                """
                UPDATE play_history
                SET play_count = play_count + 1, played_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (row["id"],),
            )
            history_id = row["id"]
        else:
            # Create new entry
            cursor.execute(
                """
                INSERT INTO play_history (track_id, play_count)
                VALUES (?, 1)
            """,
                (track_id,),
            )
            history_id = cursor.lastrowid

        conn.commit()
        return history_id

    def get_play_history(self, limit: int = 50) -> List[PlayHistory]:
        """Get recent play history."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM play_history
            ORDER BY played_at DESC
            LIMIT ?
        """,
            (limit,),
        )

        rows = cursor.fetchall()

        return [
            PlayHistory(
                id=row["id"],
                track_id=row["track_id"],
                played_at=datetime.fromisoformat(row["played_at"]),
                play_count=row["play_count"],
            )
            for row in rows
        ]

    def get_most_played(self, limit: int = 20) -> List[tuple]:
        """Get most played tracks with their counts."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.*, SUM(ph.play_count) as total_plays
            FROM tracks t
            INNER JOIN play_history ph ON t.id = ph.track_id
            GROUP BY t.id
            ORDER BY total_plays DESC
            LIMIT ?
        """,
            (limit,),
        )

        return cursor.fetchall()

    # Favorites operations

    def add_favorite(self, track_id: int) -> bool:
        """Add a track to favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO favorites (track_id)
                VALUES (?)
            """,
                (track_id,),
            )

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_favorite(self, track_id: int) -> bool:
        """Remove a track from favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM favorites WHERE track_id = ?", (track_id,))
        conn.commit()

        return cursor.rowcount > 0

    def is_favorite(self, track_id: int) -> bool:
        """Check if a track is in favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM favorites WHERE track_id = ?", (track_id,))
        return cursor.fetchone() is not None

    def get_favorites(self) -> List[Track]:
        """Get all favorite tracks."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.* FROM tracks t
            INNER JOIN favorites f ON t.id = f.track_id
            ORDER BY f.created_at DESC
        """)

        rows = cursor.fetchall()

        return [
            Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]

    def close(self):
        """Close database connection."""
        if hasattr(self.local, "conn"):
            self.local.conn.close()
            delattr(self.local, "conn")

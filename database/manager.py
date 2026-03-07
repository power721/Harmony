"""
Database manager for the music player using SQLite.
"""

import sqlite3
import threading
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .models import Track, Playlist, PlaylistItem, PlayHistory, Favorite, CloudAccount, CloudFile


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

        # Create cloud_accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cloud_accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                account_name TEXT,
                account_email TEXT,
                access_token TEXT,
                refresh_token TEXT,
                token_expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create cloud_files table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cloud_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id INTEGER NOT NULL,
                file_id TEXT NOT NULL,
                parent_id TEXT DEFAULT '',
                name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size INTEGER,
                mime_type TEXT,
                duration REAL,
                metadata TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (account_id) REFERENCES cloud_accounts(id) ON DELETE CASCADE
            )
        """)

        # Create indexes for cloud tables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cloud_accounts_provider
            ON cloud_accounts(provider)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cloud_files_account
            ON cloud_files(account_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_cloud_files_parent
            ON cloud_files(parent_id)
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

    # Cloud account operations

    def create_cloud_account(self, provider: str, account_name: str,
                            account_email: str, access_token: str,
                            refresh_token: str = "") -> int:
        """Create a new cloud account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO cloud_accounts
            (provider, account_name, account_email, access_token, refresh_token)
            VALUES (?, ?, ?, ?, ?)
        """,
            (provider, account_name, account_email, access_token, refresh_token)
        )

        conn.commit()
        return cursor.lastrowid

    def get_cloud_accounts(self, provider: str = None) -> List[CloudAccount]:
        """Get all cloud accounts, optionally filtered by provider."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if provider:
            cursor.execute(
                """
                SELECT * FROM cloud_accounts
                WHERE provider = ? AND is_active = 1
                ORDER BY created_at DESC
            """,
                (provider,)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM cloud_accounts
                WHERE is_active = 1
                ORDER BY created_at DESC
            """
            )

        rows = cursor.fetchall()

        return [
            CloudAccount(
                id=row["id"],
                provider=row["provider"],
                account_name=row["account_name"],
                account_email=row["account_email"],
                access_token=row["access_token"],
                refresh_token=row["refresh_token"],
                token_expires_at=datetime.fromisoformat(row["token_expires_at"]) if row["token_expires_at"] else None,
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def get_cloud_account(self, account_id: int) -> Optional[CloudAccount]:
        """Get a cloud account by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM cloud_accounts WHERE id = ?", (account_id,))
        row = cursor.fetchone()

        if row:
            return CloudAccount(
                id=row["id"],
                provider=row["provider"],
                account_name=row["account_name"],
                account_email=row["account_email"],
                access_token=row["access_token"],
                refresh_token=row["refresh_token"],
                token_expires_at=datetime.fromisoformat(row["token_expires_at"]) if row["token_expires_at"] else None,
                is_active=bool(row["is_active"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

    def update_cloud_account_token(self, account_id: int, access_token: str,
                                  refresh_token: str = None) -> bool:
        """Update account tokens."""
        conn = self._get_connection()
        cursor = conn.cursor()

        if refresh_token is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token = ?, refresh_token = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (access_token, refresh_token, account_id)
            )
        else:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (access_token, account_id)
            )

        conn.commit()
        return cursor.rowcount > 0

    def delete_cloud_account(self, account_id: int) -> bool:
        """Delete a cloud account (sets is_active to False)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_accounts
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (account_id,)
        )

        conn.commit()
        return cursor.rowcount > 0

    # Cloud file operations

    def cache_cloud_files(self, account_id: int, files: List[CloudFile]) -> bool:
        """Cache cloud file metadata (replace existing files for account)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Delete old cache
        cursor.execute("DELETE FROM cloud_files WHERE account_id = ?", (account_id,))

        # Insert new files
        for file in files:
            cursor.execute(
                """
                INSERT INTO cloud_files
                (account_id, file_id, parent_id, name, file_type, size, mime_type, duration, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (account_id, file.file_id, file.parent_id, file.name,
                 file.file_type, file.size, file.mime_type, file.duration, file.metadata)
            )

        conn.commit()
        return True

    def get_cloud_files(self, account_id: int, parent_id: str = "") -> List[CloudFile]:
        """Get cached files for an account and parent folder."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE account_id = ? AND parent_id = ?
            ORDER BY file_type DESC, name ASC
        """,
            (account_id, parent_id)
        )

        rows = cursor.fetchall()

        return [
            CloudFile(
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
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

    def get_cloud_file(self, file_id: str, account_id: int) -> Optional[CloudFile]:
        """Get a cloud file by ID and account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE file_id = ? AND account_id = ?
        """,
            (file_id, account_id)
        )

        row = cursor.fetchone()

        if row:
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
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

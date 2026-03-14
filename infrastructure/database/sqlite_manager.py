"""
Database manager for the music player using SQLite.
"""
import logging
import sqlite3
import threading
from typing import List, Optional
from datetime import datetime

from domain.track import Track
from domain.playlist import Playlist
from domain.cloud import CloudAccount, CloudFile
from domain.playback import PlayQueueItem
from domain.history import PlayHistory


# Configure logging
logger = logging.getLogger(__name__)

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
                cloud_file_id TEXT,
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
                track_id INTEGER,
                cloud_file_id TEXT,
                cloud_account_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                FOREIGN KEY (cloud_account_id) REFERENCES cloud_accounts(id) ON DELETE CASCADE,
                UNIQUE(track_id),
                UNIQUE(cloud_file_id)
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
                last_folder_id TEXT DEFAULT '0',
                last_folder_path TEXT DEFAULT '/',
                last_parent_folder_id TEXT DEFAULT '0',
                last_fid_path TEXT DEFAULT '0',
                last_playing_fid TEXT DEFAULT '',
                last_position REAL DEFAULT 0.0,
                last_playing_local_path TEXT DEFAULT '',
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
                local_path TEXT,
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

        # Create settings table for unified configuration storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create play_queue table for persistent playback queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS play_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                source_type TEXT NOT NULL,
                cloud_type TEXT,
                track_id INTEGER,
                cloud_file_id TEXT,
                cloud_account_id INTEGER,
                local_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for play_queue position
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_play_queue_position
            ON play_queue(position)
        """)

        # Create FTS5 virtual table for full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                title,
                artist,
                album,
                content='tracks',
                content_rowid='id'
            )
        """)

        # Create triggers to keep FTS index in sync with tracks table
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
                INSERT INTO tracks_fts(rowid, title, artist, album)
                VALUES (new.id, new.title, new.artist, new.album);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
                DELETE FROM tracks_fts WHERE rowid = old.id;
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
                UPDATE tracks_fts
                SET title = new.title,
                    artist = new.artist,
                    album = new.album
                WHERE rowid = new.id;
            END
        """)

        # Run migrations for existing databases
        self._run_migrations(conn, cursor)

        conn.commit()

    def _run_migrations(self, conn, cursor):
        """Run database migrations for schema updates."""
        # Migration 1: Add cloud file support to favorites table
        cursor.execute("PRAGMA table_info(favorites)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'cloud_file_id' not in columns:
            cursor.execute("ALTER TABLE favorites ADD COLUMN cloud_file_id TEXT")
        if 'cloud_account_id' not in columns:
            cursor.execute("ALTER TABLE favorites ADD COLUMN cloud_account_id INTEGER")

        # Check if track_id is NOT NULL (needs to be nullable for cloud files)
        cursor.execute("PRAGMA table_info(favorites)")
        needs_rebuild = False
        for col in cursor.fetchall():
            if col[1] == 'track_id' and col[3] == 1:  # col[3] is notnull flag
                needs_rebuild = True
                break

        if needs_rebuild:
            # Recreate table with nullable track_id and proper constraints
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER,
                    cloud_file_id TEXT,
                    cloud_account_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                    FOREIGN KEY (cloud_account_id) REFERENCES cloud_accounts(id) ON DELETE CASCADE,
                    UNIQUE(track_id),
                    UNIQUE(cloud_file_id)
                )
            """)
            cursor.execute("""
                INSERT INTO favorites_new (id, track_id, cloud_file_id, cloud_account_id, created_at)
                SELECT id, track_id, cloud_file_id, cloud_account_id, created_at FROM favorites
            """)
            cursor.execute("DROP TABLE favorites")
            cursor.execute("ALTER TABLE favorites_new RENAME TO favorites")

        # Migration 2: Initialize FTS5 index for existing tracks
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks_fts'")
        fts_exists = cursor.fetchone() is not None

        cursor.execute("SELECT COUNT(*) FROM tracks")
        tracks_count = cursor.fetchone()[0]

        if tracks_count > 0:
            if fts_exists:
                # FTS table exists, check if it needs to be repopulated
                cursor.execute("SELECT COUNT(*) FROM tracks_fts")
                fts_count = cursor.fetchone()[0]

                # Check if FTS index is valid by testing a simple search
                fts_valid = False
                if fts_count == tracks_count:
                    try:
                        # Get a sample track title and test search
                        cursor.execute("SELECT title FROM tracks WHERE title IS NOT NULL AND title != '' LIMIT 1")
                        sample = cursor.fetchone()
                        if sample:
                            sample_title = sample[0]
                            # Extract first word for testing
                            test_word = sample_title.split()[0] if ' ' in sample_title else sample_title[:3]
                            if test_word:
                                cursor.execute(
                                    "SELECT rowid FROM tracks_fts WHERE tracks_fts MATCH ? LIMIT 1",
                                    (f"{test_word}*",)
                                )
                                fts_valid = cursor.fetchone() is not None
                    except Exception:
                        fts_valid = False

                if not fts_valid:
                    # FTS index is invalid, rebuild it
                    logger.info(f"[Database] Rebuilding FTS5 index (was {fts_count} entries, expected {tracks_count})")
                    cursor.execute("DELETE FROM tracks_fts")
                    cursor.execute("""
                        INSERT INTO tracks_fts(rowid, title, artist, album)
                        SELECT id, COALESCE(title, ''), COALESCE(artist, ''), COALESCE(album, '')
                        FROM tracks
                    """)
                    logger.info(f"[Database] Rebuilt FTS5 index with {tracks_count} tracks")
            else:
                # FTS table doesn't exist but tracks do - this shouldn't happen with current init
                logger.info(f"[Database] Populating FTS5 index with {tracks_count} tracks")
                cursor.execute("""
                    INSERT INTO tracks_fts(rowid, title, artist, album)
                    SELECT id, COALESCE(title, ''), COALESCE(artist, ''), COALESCE(album, '')
                    FROM tracks
                """)

    # Track operations

    def add_track(self, track: Track) -> int:
        """Add a track to the database. Returns track ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, title, artist, album, duration, cover_path, created_at, cloud_file_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                track.path,
                track.title,
                track.artist,
                track.album,
                track.duration,
                track.cover_path,
                track.created_at or datetime.now(),
                track.cloud_file_id,
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
                cloud_file_id=row["cloud_file_id"],
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
                cloud_file_id=row["cloud_file_id"],
            )
        return None

    def get_track_by_cloud_file_id(self, cloud_file_id: str) -> Optional[Track]:
        """Get a track by cloud file ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
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
                cloud_file_id=row["cloud_file_id"],
            )
        return None

    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the database, including downloaded cloud files."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get local tracks
        cursor.execute("SELECT * FROM tracks ORDER BY artist, album, title")
        rows = cursor.fetchall()

        tracks = [
            Track(
                id=row["id"],
                path=row["path"],
                title=row["title"],
                artist=row["artist"],
                album=row["album"],
                duration=row["duration"],
                cover_path=row["cover_path"],
                created_at=datetime.fromisoformat(row["created_at"]),
                cloud_file_id=row["cloud_file_id"],
            )
            for row in rows
        ]

        # Get downloaded cloud files and convert to virtual tracks
        # Use negative IDs to distinguish from real tracks
        cloud_files = self.get_all_downloaded_cloud_files()
        for i, cloud_file in enumerate(cloud_files):
            # Create a virtual track from cloud file
            virtual_track = Track(
                id=-(1000000 + i),  # Negative ID to indicate cloud file
                path=cloud_file.local_path,
                title=cloud_file.name,
                artist="☁️ Cloud File",  # Mark as cloud file
                album="",
                duration=cloud_file.duration or 0.0,
                cover_path=None,
                created_at=cloud_file.created_at,
            )
            tracks.append(virtual_track)

        return tracks

    def search_tracks(self, query: str) -> List[Track]:
        """
        Search tracks using FTS5 full-text search.

        Supports:
        - Word search: "beatles" matches any field containing "beatles"
        - Prefix search: "beat*" matches "beat", "beatles", "beating"
        - Multi-word: "beatles hey" matches tracks with both words
        - Field-specific: "artist:beatles" searches only artist field

        Args:
            query: Search query string

        Returns:
            List of matching Track objects sorted by relevance
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if FTS table has data
        cursor.execute("SELECT COUNT(*) FROM tracks_fts")
        if cursor.fetchone()[0] == 0:
            # Fallback to LIKE search if FTS not populated
            return self._search_tracks_like(query)

        try:
            # Use FTS5 for full-text search with BM25 ranking
            # Handle special characters that might break FTS query
            safe_query = query.replace('"', '""')

            # Build FTS query - wrap in quotes for exact phrase or use as-is for multi-word
            fts_query = f'"{safe_query}"'

            cursor.execute(
                """
                SELECT t.*, bm25(tracks_fts) AS score
                FROM tracks t
                JOIN tracks_fts f ON t.id = f.rowid
                WHERE tracks_fts MATCH ?
                ORDER BY score
                LIMIT 100
                """,
                (fts_query,),
            )

            rows = cursor.fetchall()

            if not rows:
                # Try without quotes for multi-word search
                fts_query = safe_query
                cursor.execute(
                    """
                    SELECT t.*, bm25(tracks_fts) AS score
                    FROM tracks t
                    JOIN tracks_fts f ON t.id = f.rowid
                    WHERE tracks_fts MATCH ?
                    ORDER BY score
                    LIMIT 100
                    """,
                    (fts_query,),
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
                    cloud_file_id=row["cloud_file_id"],
                )
                for row in rows
            ]

        except sqlite3.OperationalError:
            # FTS query failed, fallback to LIKE search
            return self._search_tracks_like(query)

    def _search_tracks_like(self, query: str) -> List[Track]:
        """
        Fallback LIKE-based search when FTS is not available.

        Args:
            query: Search query string

        Returns:
            List of matching Track objects
        """
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
                cloud_file_id=row["cloud_file_id"],
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

    def update_track_cover_path(self, track_id: int, cover_path: str) -> bool:
        """Update cover_path for a track."""
        logger = logging.getLogger(__name__)
        logger.info(f"[DatabaseManager] update_track_cover_path: track_id={track_id}, cover_path={cover_path}")

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE tracks
            SET cover_path = ?
            WHERE id = ?
        """,
            (cover_path, track_id),
        )

        conn.commit()
        affected = cursor.rowcount
        logger.info(f"[DatabaseManager] Updated {affected} row(s)")
        return affected > 0

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

    def rename_playlist(self, playlist_id: int, new_name: str) -> bool:
        """Rename a playlist."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE playlists SET name = ? WHERE id = ?",
            (new_name, playlist_id)
        )
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

    def add_favorite(self, track_id: int = None, cloud_file_id: str = None, cloud_account_id: int = None) -> bool:
        """Add a track or cloud file to favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # If cloud_file_id provided, check if there's already a track record
        if cloud_file_id and not track_id:
            cursor.execute("SELECT id FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
            row = cursor.fetchone()
            if row:
                track_id = row["id"]
                cloud_file_id = None  # Use track_id instead

        try:
            cursor.execute(
                """
                INSERT INTO favorites (track_id, cloud_file_id, cloud_account_id)
                VALUES (?, ?, ?)
            """,
                (track_id, cloud_file_id, cloud_account_id),
            )

            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def remove_favorite(self, track_id: int = None, cloud_file_id: str = None) -> bool:
        """Remove a track or cloud file from favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # If cloud_file_id provided, check if there's a track record
        if cloud_file_id and not track_id:
            cursor.execute("SELECT id FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
            row = cursor.fetchone()
            if row:
                track_id = row["id"]
                cloud_file_id = None

        if track_id:
            cursor.execute("DELETE FROM favorites WHERE track_id = ?", (track_id,))
        else:
            cursor.execute("DELETE FROM favorites WHERE cloud_file_id = ?", (cloud_file_id,))
        conn.commit()

        return cursor.rowcount > 0

    def is_favorite(self, track_id: int = None, cloud_file_id: str = None) -> bool:
        """Check if a track or cloud file is in favorites."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # If cloud_file_id provided, check if there's a track record
        if cloud_file_id and not track_id:
            cursor.execute("SELECT id FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
            row = cursor.fetchone()
            if row:
                track_id = row["id"]

        if track_id:
            cursor.execute("SELECT 1 FROM favorites WHERE track_id = ?", (track_id,))
        else:
            cursor.execute("SELECT 1 FROM favorites WHERE cloud_file_id = ?", (cloud_file_id,))
        return cursor.fetchone() is not None

    def get_favorites(self) -> List[Track]:
        """Get all favorite tracks (including downloaded cloud files with track_id)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT t.* FROM tracks t
            INNER JOIN favorites f ON t.id = f.track_id
            WHERE f.track_id IS NOT NULL
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
                cloud_file_id=row["cloud_file_id"] if "cloud_file_id" in row.keys() else None,
            )
            for row in rows
        ]

    def get_favorites_with_cloud(self) -> List[dict]:
        """Get all favorites including local tracks and undownloaded cloud files."""
        conn = self._get_connection()
        cursor = conn.cursor()

        results = []

        # Get track favorites (including downloaded cloud files that now have track_id)
        cursor.execute("""
            SELECT t.*, f.created_at as fav_created_at FROM tracks t
            INNER JOIN favorites f ON t.id = f.track_id
            WHERE f.track_id IS NOT NULL
            ORDER BY f.created_at DESC
        """)

        for row in cursor.fetchall():
            is_cloud = row["cloud_file_id"] is not None if "cloud_file_id" in row.keys() else False
            results.append({
                "type": "cloud" if is_cloud else "local",
                "id": row["id"],
                "track_id": row["id"],
                "title": row["title"] or "",
                "artist": row["artist"] or "",
                "album": row["album"] or "",
                "duration": row["duration"] or 0,
                "path": row["path"],
                "cloud_file_id": row["cloud_file_id"] if "cloud_file_id" in row.keys() else None,
                "created_at": row["fav_created_at"],
            })

        # Get undownloaded cloud file favorites (no track_id yet)
        cursor.execute("""
            SELECT f.cloud_file_id, f.cloud_account_id, f.created_at,
                   cf.name, cf.duration, cf.local_path
            FROM favorites f
            LEFT JOIN cloud_files cf ON f.cloud_file_id = cf.file_id
            WHERE f.cloud_file_id IS NOT NULL AND f.track_id IS NULL
            ORDER BY f.created_at DESC
        """)

        for row in cursor.fetchall():
            # Extract title from filename (remove extension)
            name = row["name"] or ""
            title = name.rsplit(".", 1)[0] if "." in name else name
            results.append({
                "type": "cloud",
                "id": row["cloud_file_id"],
                "cloud_file_id": row["cloud_file_id"],
                "cloud_account_id": row["cloud_account_id"],
                "title": title,
                "artist": "",
                "album": "",
                "duration": row["duration"] or 0,
                "path": row["local_path"] or "",
                "created_at": row["created_at"],
            })

        # Sort by created_at descending
        results.sort(key=lambda x: x.get("created_at") or "", reverse=True)

        return results

    def close(self):
        """Close database connection."""
        if hasattr(self.local, "conn"):
            self.local.conn.close()
            delattr(self.local, "conn")

    # Cloud account operations

    def create_cloud_account(
        self,
        provider: str,
        account_name: str,
        account_email: str,
        access_token: str,
        refresh_token: str = "",
    ) -> int:
        """Create a new cloud account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO cloud_accounts
            (provider, account_name, account_email, access_token, refresh_token)
            VALUES (?, ?, ?, ?, ?)
        """,
            (provider, account_name, account_email, access_token, refresh_token),
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
                (provider,),
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
                token_expires_at=datetime.fromisoformat(row["token_expires_at"])
                if row["token_expires_at"]
                else None,
                is_active=bool(row["is_active"]),
                last_folder_path=row["last_folder_path"] or "/",
                last_fid_path=row["last_fid_path"] if "last_fid_path" in row.keys() else "0",
                last_playing_fid=row["last_playing_fid"] if "last_playing_fid" in row.keys() else "",
                last_position=row["last_position"] if "last_position" in row.keys() else 0.0,
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
                token_expires_at=datetime.fromisoformat(row["token_expires_at"])
                if row["token_expires_at"]
                else None,
                is_active=bool(row["is_active"]),
                last_folder_path=row["last_folder_path"] or "/",
                last_fid_path=row["last_fid_path"] if "last_fid_path" in row.keys() else "0",
                last_playing_fid=row["last_playing_fid"] if "last_playing_fid" in row.keys() else "",
                last_position=row["last_position"] if "last_position" in row.keys() else 0.0,
                last_playing_local_path=row["last_playing_local_path"] if "last_playing_local_path" in row.keys() else "",
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

    def update_cloud_account_token(
        self, account_id: int, access_token: str, refresh_token: str = None
    ) -> bool:
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
                (access_token, refresh_token, account_id),
            )
        else:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (access_token, account_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def update_cloud_account_folder(
        self, account_id: int, folder_id: str, folder_path: str, parent_folder_id: str = "0", fid_path: str = "0"
    ) -> bool:
        """Update the last opened folder for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_accounts
            SET last_folder_path = ?, last_fid_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (folder_path, fid_path, account_id),
        )

        conn.commit()
        return cursor.rowcount > 0

    def update_cloud_account_playing_state(
        self, account_id: int, playing_fid: str = None, position: float = None, local_path: str = None
    ) -> bool:
        """Update the last playing file and position for an account."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Build update query dynamically based on provided parameters
        if playing_fid is not None and position is not None and local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?, last_position = ?, last_playing_local_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (playing_fid, position, local_path, account_id),
            )
        elif playing_fid is not None and position is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?, last_position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (playing_fid, position, account_id),
            )
        elif playing_fid is not None and local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?, last_playing_local_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (playing_fid, local_path, account_id),
            )
        elif playing_fid is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (playing_fid, account_id),
            )
        elif position is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_position = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (position, account_id),
            )
        elif local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_local_path = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (local_path, account_id),
            )

        conn.commit()
        return cursor.rowcount > 0

    def update_cloud_file_local_path(
        self, file_id: str, account_id: int, local_path: str
    ) -> bool:
        """Update the local path for a downloaded cloud file."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_files
            SET local_path = ?, updated_at = CURRENT_TIMESTAMP
            WHERE file_id = ? AND account_id = ?
        """,
            (local_path, file_id, account_id),
        )

        conn.commit()
        return cursor.rowcount > 0

    def get_cloud_file_by_local_path(self, local_path: str) -> Optional[CloudFile]:
        """Get a cloud file by its local path."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files WHERE local_path = ?
        """,
            (local_path,),
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
                local_path=row["local_path"] if "local_path" in row.keys() else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

    def get_all_downloaded_cloud_files(self) -> List[CloudFile]:
        """Get all cloud files that have been downloaded (have local_path)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE local_path IS NOT NULL AND local_path != ''
            ORDER BY name ASC
        """
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
                local_path=row["local_path"] if "local_path" in row.keys() else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            for row in rows
        ]

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
            (account_id,),
        )

        conn.commit()
        return cursor.rowcount > 0

    # Cloud file operations

    def cache_cloud_files(self, account_id: int, files: List[CloudFile]) -> bool:
        """Cache cloud file metadata for current folder (preserve local_path and other folders)."""
        if not files:
            return True

        conn = self._get_connection()
        cursor = conn.cursor()

        # Get the parent_id from the first file (all files should be in the same folder)
        parent_id = files[0].parent_id if files else ""

        # First, get existing local_paths for files in this folder
        cursor.execute(
            "SELECT file_id, local_path FROM cloud_files WHERE account_id = ? AND parent_id = ? AND local_path IS NOT NULL",
            (account_id, parent_id)
        )
        existing_paths = {row["file_id"]: row["local_path"] for row in cursor.fetchall()}

        # Delete old cache only for this folder (not the entire account)
        cursor.execute("DELETE FROM cloud_files WHERE account_id = ? AND parent_id = ?", (account_id, parent_id))

        # Insert new files, preserving local_path if it existed
        for file in files:
            local_path = existing_paths.get(file.file_id)  # Get existing local_path

            cursor.execute(
                """
                INSERT INTO cloud_files
                (account_id, file_id, parent_id, name, file_type, size, mime_type, duration, metadata, local_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    account_id,
                    file.file_id,
                    file.parent_id,
                    file.name,
                    file.file_type,
                    file.size,
                    file.mime_type,
                    file.duration,
                    file.metadata,
                    local_path,
                ),
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
            (account_id, parent_id),
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
                local_path=row["local_path"] if "local_path" in row.keys() else None,
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
            (file_id, account_id),
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
                local_path=row["local_path"] if "local_path" in row.keys() else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

    def get_cloud_file_by_file_id(self, file_id: str) -> Optional[CloudFile]:
        """Get a cloud file by file_id only."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM cloud_files
            WHERE file_id = ?
        """,
            (file_id,),
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
                local_path=row["local_path"] if "local_path" in row.keys() else None,
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

    # Settings operations

    def get_setting(self, key: str, default=None):
        """
        Get a setting value by key.

        Args:
            key: Setting key
            default: Default value if not found

        Returns:
            Setting value or default
        """
        import json
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if row:
            value = row["value"]
            # Try to parse JSON for complex types
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value
        return default

    def set_setting(self, key: str, value) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting key
            value: Setting value (will be JSON serialized if not a string)

        Returns:
            True if successful
        """
        import json
        conn = self._get_connection()
        cursor = conn.cursor()

        # Serialize value to string
        if isinstance(value, str):
            value_str = value
        else:
            value_str = json.dumps(value)

        cursor.execute(
            """
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            """,
            (key, value_str),
        )

        conn.commit()
        return cursor.rowcount > 0

    def get_settings(self, keys: list) -> dict:
        """
        Get multiple setting values.

        Args:
            keys: List of setting keys

        Returns:
            Dict of key-value pairs
        """
        import json
        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(keys))
        cursor.execute(
            f"SELECT key, value FROM settings WHERE key IN ({placeholders})",
            keys,
        )

        result = {}
        for row in cursor.fetchall():
            value = row["value"]
            try:
                result[row["key"]] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                result[row["key"]] = value

        return result

    def delete_setting(self, key: str) -> bool:
        """
        Delete a setting.

        Args:
            key: Setting key

        Returns:
            True if deleted
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM settings WHERE key = ?", (key,))
        conn.commit()

        return cursor.rowcount > 0

    # Play queue operations

    def save_play_queue(self, items: List["PlayQueueItem"]) -> bool:
        """
        Save the play queue to the database.
        Replaces any existing queue.

        Args:
            items: List of PlayQueueItem objects

        Returns:
            True if successful
        """
        from domain.playlist_item import PlaylistItem

        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing queue
        cursor.execute("DELETE FROM play_queue")

        # Insert new items
        for position, item in enumerate(items):
            cursor.execute(
                """
                INSERT INTO play_queue
                (position, source_type, cloud_type, track_id, cloud_file_id, cloud_account_id,
                 local_path, title, artist, album, duration, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    position,
                    item.source_type,
                    item.cloud_type,
                    item.track_id,
                    item.cloud_file_id,
                    item.cloud_account_id,
                    item.local_path,
                    item.title,
                    item.artist,
                    item.album,
                    item.duration,
                    item.created_at or datetime.now(),
                ),
            )

        conn.commit()
        return True

    def load_play_queue(self) -> List[PlayQueueItem]:
        """
        Load the play queue from the database.

        Returns:
            List of PlayQueueItem objects in order
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT * FROM play_queue ORDER BY position ASC
            """
        )

        rows = cursor.fetchall()

        return [
            PlayQueueItem(
                id=row["id"],
                position=row["position"],
                source_type=row["source_type"],
                cloud_type=row["cloud_type"] if "cloud_type" in row.keys() else "",
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

    def clear_play_queue(self) -> bool:
        """
        Clear the play queue.

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM play_queue")
        conn.commit()

        return True

    def get_play_queue_count(self) -> int:
        """
        Get the number of items in the play queue.

        Returns:
            Number of items
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) as count FROM play_queue")
        row = cursor.fetchone()

        return row["count"] if row else 0

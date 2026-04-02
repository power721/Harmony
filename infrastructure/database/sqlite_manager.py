"""
Database manager for the music player using SQLite.
"""
import logging
import sqlite3
import threading
from concurrent.futures import Future
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from domain.cloud import CloudAccount, CloudFile
from domain.history import PlayHistory
from domain.playback import PlayQueueItem
from domain.playlist import Playlist
from domain.track import Track, TrackSource
from infrastructure.database.db_write_worker import DBWriteWorker, get_write_worker

# Configure logging
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database operations for the music player."""

    def __init__(self, db_path: str = "Harmony.db"):
        """
        Initialize database manager.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.local = threading.local()
        self._write_worker = get_write_worker(db_path)
        self._init_database()

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self.local, "conn"):
            self.local.conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
            self.local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            self.local.conn.execute("PRAGMA journal_mode=WAL")
            # Set busy timeout for this connection
            self.local.conn.execute("PRAGMA busy_timeout=30000")
            # Performance optimizations
            self.local.conn.execute("PRAGMA synchronous=NORMAL")
            self.local.conn.execute("PRAGMA cache_size=-10000")
            self.local.conn.execute("PRAGMA temp_store=MEMORY")
            self.local.conn.execute("PRAGMA foreign_keys=ON")
        return self.local.conn

    def _submit_write(self, func: Callable, *args, **kwargs) -> Future:
        """
        Submit a write operation to the worker thread.

        Args:
            func: Function to execute (will receive 'conn' kwarg if signature has it)
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Future with the result
        """
        return self._write_worker.submit(func, *args, **kwargs)

    def _submit_write_async(self, func: Callable, *args, **kwargs):
        """
        Submit a write operation without waiting for result.

        Fire-and-forget for operations where you don't need the result.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        """
        self._write_worker.submit_async(func, *args, **kwargs)

    def _init_database(self):
        """Initialize database tables."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Create tracks table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS tracks
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           path
                           TEXT
                           UNIQUE
                           NOT
                           NULL,
                           title
                           TEXT,
                           artist
                           TEXT,
                           album
                           TEXT,
                           duration
                           REAL
                           DEFAULT
                           0,
                           cover_path
                           TEXT,
                           cloud_file_id
                           TEXT,
                           source
                           TEXT
                           DEFAULT
                           'Local',
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # Create playlists table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS playlists
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT
                           NOT
                           NULL,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # Create playlist_items table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS playlist_items
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           playlist_id
                           INTEGER
                           NOT
                           NULL,
                           track_id
                           INTEGER
                           NOT
                           NULL,
                           position
                           INTEGER
                           NOT
                           NULL,
                           FOREIGN
                           KEY
                       (
                           playlist_id
                       ) REFERENCES playlists
                       (
                           id
                       ) ON DELETE CASCADE,
                           FOREIGN KEY
                       (
                           track_id
                       ) REFERENCES tracks
                       (
                           id
                       )
                         ON DELETE CASCADE,
                           UNIQUE
                       (
                           playlist_id,
                           track_id
                       ),
                           UNIQUE
                       (
                           playlist_id,
                           position
                       )
                           )
                       """)

        # Create play_history table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS play_history
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           track_id
                           INTEGER
                           NOT
                           NULL,
                           played_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           play_count
                           INTEGER
                           DEFAULT
                           1,
                           FOREIGN
                           KEY
                       (
                           track_id
                       ) REFERENCES tracks
                       (
                           id
                       ) ON DELETE CASCADE
                           )
                       """)

        # Create favorites table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS favorites
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           track_id
                           INTEGER,
                           cloud_file_id
                           TEXT,
                           cloud_account_id
                           INTEGER,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           track_id
                       ) REFERENCES tracks
                       (
                           id
                       ) ON DELETE CASCADE,
                           FOREIGN KEY
                       (
                           cloud_account_id
                       ) REFERENCES cloud_accounts
                       (
                           id
                       )
                         ON DELETE CASCADE,
                           UNIQUE
                       (
                           track_id
                       ),
                           UNIQUE
                       (
                           cloud_file_id
                       )
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
        # Additional indexes for common queries
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_tracks_cloud_file_id
                           ON tracks(cloud_file_id)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_tracks_source
                           ON tracks(source)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_tracks_created_at
                           ON tracks(created_at DESC)
                       """)
        # Index for genre queries
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_tracks_genre
                           ON tracks(genre)
                       """)

        # H-02: Indexes for favorites table
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_favorites_track_id
                           ON favorites(track_id)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_favorites_cloud_file_id
                           ON favorites(cloud_file_id)
                       """)

        # H-03: Indexes for playlist_items table
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist_id
                           ON playlist_items(playlist_id)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_playlist_items_track_id
                           ON playlist_items(track_id)
                       """)

        # H-04: Composite indexes for album/artist queries
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_tracks_artist_album
                           ON tracks(artist, album)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist_position
                           ON playlist_items(playlist_id, position)
                       """)

        # Create cloud_accounts table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS cloud_accounts
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           provider
                           TEXT
                           NOT
                           NULL,
                           account_name
                           TEXT,
                           account_email
                           TEXT,
                           access_token
                           TEXT,
                           refresh_token
                           TEXT,
                           token_expires_at
                           TIMESTAMP,
                           is_active
                           BOOLEAN
                           DEFAULT
                           1,
                           last_folder_id
                           TEXT
                           DEFAULT
                           '0',
                           last_folder_path
                           TEXT
                           DEFAULT
                           '/',
                           last_parent_folder_id
                           TEXT
                           DEFAULT
                           '0',
                           last_fid_path
                           TEXT
                           DEFAULT
                           '0',
                           last_playing_fid
                           TEXT
                           DEFAULT
                           '',
                           last_position
                           REAL
                           DEFAULT
                           0.0,
                           last_playing_local_path
                           TEXT
                           DEFAULT
                           '',
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # Create cloud_files table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS cloud_files
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           account_id
                           INTEGER
                           NOT
                           NULL,
                           file_id
                           TEXT
                           NOT
                           NULL,
                           parent_id
                           TEXT
                           DEFAULT
                           '',
                           name
                           TEXT
                           NOT
                           NULL,
                           file_type
                           TEXT
                           NOT
                           NULL,
                           size
                           INTEGER,
                           mime_type
                           TEXT,
                           duration
                           REAL,
                           metadata
                           TEXT,
                           local_path
                           TEXT,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           FOREIGN
                           KEY
                       (
                           account_id
                       ) REFERENCES cloud_accounts
                       (
                           id
                       ) ON DELETE CASCADE
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
        # H-01: Index for cloud_files.file_id lookups
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_cloud_files_file_id
                           ON cloud_files(file_id)
                       """)
        # H-04: Additional composite index for cloud folder browsing
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_cloud_files_account_parent
                           ON cloud_files(account_id, parent_id)
                       """)
        # M-04: Partial index for cloud_files.local_path
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_cloud_files_local_path
                           ON cloud_files(local_path)
                           WHERE local_path IS NOT NULL
                       """)

        # Create settings table for unified configuration storage
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS settings
                       (
                           key
                           TEXT
                           PRIMARY
                           KEY,
                           value
                           TEXT,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # Create play_queue table for persistent playback queue
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS play_queue
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           position
                           INTEGER
                           NOT
                           NULL,
                           source
                           TEXT
                           NOT
                           NULL,
                           track_id
                           INTEGER,
                           cloud_file_id
                           TEXT,
                           cloud_account_id
                           INTEGER,
                           local_path
                           TEXT,
                           title
                           TEXT,
                           artist
                           TEXT,
                           album
                           TEXT,
                           duration
                           REAL,
                           download_failed
                           INTEGER
                           DEFAULT
                           0,
                           created_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
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
                       CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks
                       BEGIN
                INSERT INTO tracks_fts(rowid, title, artist, album)
                VALUES (new.id, new.title, new.artist, new.album);
                       END
                       """)

        cursor.execute("""
                       CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER
                       DELETE
                       ON tracks BEGIN
                       DELETE
                       FROM tracks_fts
                       WHERE rowid = old.id;
                       END
                       """)

        cursor.execute("""
                       CREATE TRIGGER IF NOT EXISTS tracks_au AFTER
                       UPDATE ON tracks BEGIN
                       UPDATE tracks_fts
                       SET title  = new.title,
                           artist = new.artist,
                           album  = new.album
                       WHERE rowid = new.id;
                       END
                       """)

        # Create albums table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS albums
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT
                           NOT
                           NULL,
                           artist
                           TEXT
                           NOT
                           NULL,
                           cover_path
                           TEXT,
                           song_count
                           INTEGER
                           DEFAULT
                           0,
                           total_duration
                           REAL
                           DEFAULT
                           0,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP,
                           UNIQUE(name, artist)
                       )
                       """)

        # Create artists table
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS artists
                       (
                           id
                           INTEGER
                           PRIMARY
                           KEY
                           AUTOINCREMENT,
                           name
                           TEXT
                           UNIQUE
                           NOT
                           NULL,
                           cover_path
                           TEXT,
                           song_count
                           INTEGER
                           DEFAULT
                           0,
                           album_count
                           INTEGER
                           DEFAULT
                           0,
                           updated_at
                           TIMESTAMP
                           DEFAULT
                           CURRENT_TIMESTAMP
                       )
                       """)

        # Run migrations for existing databases
        self._run_migrations(conn, cursor)

        conn.commit()

    def _get_track_source_from_row(self, row) -> TrackSource:
        """
        Helper to get TrackSource from database row.

        Handles missing 'source' column for backward compatibility.
        """
        if "source" not in row.keys() or not row["source"]:
            return TrackSource.LOCAL
        try:
            return TrackSource(row["source"])
        except ValueError:
            # Invalid source value, fallback to Local
            return TrackSource.LOCAL

    def _run_migrations(self, conn, cursor):
        """Run database migrations for schema updates."""
        # Current schema version - increment when making schema changes
        CURRENT_SCHEMA_VERSION = 9

        # Create db_meta table for schema version tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS db_meta (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Get current schema version
        cursor.execute("SELECT value FROM db_meta WHERE key = 'schema_version'")
        row = cursor.fetchone()
        stored_version = int(row[0]) if row else 0
        schema_changed = stored_version < CURRENT_SCHEMA_VERSION

        if schema_changed:
            logger.info(f"[Database] Schema version changed: {stored_version} -> {CURRENT_SCHEMA_VERSION}")

        # Migration 1: Add source column to tracks table
        cursor.execute("PRAGMA table_info(tracks)")
        track_columns = [col[1] for col in cursor.fetchall()]
        if 'source' not in track_columns:
            cursor.execute("ALTER TABLE tracks ADD COLUMN source TEXT DEFAULT 'Local'")
            logger.info("[Database] Added 'source' column to tracks table")

        # Migration 2: Add cloud file support to favorites table
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
                           CREATE TABLE IF NOT EXISTS favorites_new
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               track_id
                               INTEGER,
                               cloud_file_id
                               TEXT,
                               cloud_account_id
                               INTEGER,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               FOREIGN
                               KEY
                           (
                               track_id
                           ) REFERENCES tracks
                           (
                               id
                           ) ON DELETE CASCADE,
                               FOREIGN KEY
                           (
                               cloud_account_id
                           ) REFERENCES cloud_accounts
                           (
                               id
                           )
                             ON DELETE CASCADE,
                               UNIQUE
                           (
                               track_id
                           ),
                               UNIQUE
                           (
                               cloud_file_id
                           )
                               )
                           """)
            cursor.execute("""
                           INSERT INTO favorites_new (id, track_id, cloud_file_id, cloud_account_id, created_at)
                           SELECT id, track_id, cloud_file_id, cloud_account_id, created_at
                           FROM favorites
                           """)
            cursor.execute("DROP TABLE favorites")
            cursor.execute("ALTER TABLE favorites_new RENAME TO favorites")

        # Migration 3: Migrate play_queue from source_type+cloud_type to source
        cursor.execute("PRAGMA table_info(play_queue)")
        pq_columns = [col[1] for col in cursor.fetchall()]

        if 'source_type' in pq_columns and 'source' not in pq_columns:
            # Need to migrate - create new table and copy data
            logger.info("[Database] Migrating play_queue to use 'source' column")

            # Create new table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS play_queue_new
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    position INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    track_id INTEGER,
                    cloud_file_id TEXT,
                    cloud_account_id INTEGER,
                    local_path TEXT,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    duration REAL,
                    download_failed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Copy and transform data
            # source_type + cloud_type -> source
            # 'local' + '' -> 'Local'
            # 'online' + 'QQ' -> 'QQ'
            # 'cloud' + 'quark' -> 'QUARK'
            # 'cloud' + 'baidu' -> 'BAIDU'
            cursor.execute("""
                INSERT INTO play_queue_new
                    (id, position, source, track_id, cloud_file_id, cloud_account_id,
                     local_path, title, artist, album, duration, created_at)
                SELECT
                    id, position,
                    CASE
                        WHEN source_type = 'local' THEN 'Local'
                        WHEN source_type = 'online' THEN 'QQ'
                        WHEN source_type = 'cloud' THEN UPPER(cloud_type)
                        ELSE 'Local'
                    END,
                    track_id, cloud_file_id, cloud_account_id,
                    local_path, title, artist, album, duration, created_at
                FROM play_queue
            """)

            # Drop old table and rename new
            cursor.execute("DROP TABLE play_queue")
            cursor.execute("ALTER TABLE play_queue_new RENAME TO play_queue")

            # Recreate index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_play_queue_position
                ON play_queue(position)
            """)

            logger.info("[Database] play_queue migration completed")

        # Migration 4: Add download_failed column to play_queue
        cursor.execute("PRAGMA table_info(play_queue)")
        pq_columns = {row[1] for row in cursor.fetchall()}
        if "download_failed" not in pq_columns:
            cursor.execute("ALTER TABLE play_queue ADD COLUMN download_failed INTEGER DEFAULT 0")

        # Migration 2: Initialize FTS5 index for existing tracks
        # Only validate/rebuild FTS when schema has changed (not on every startup)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks_fts'")
        fts_exists = cursor.fetchone() is not None

        cursor.execute("SELECT COUNT(*) FROM tracks")
        tracks_count = cursor.fetchone()[0]

        if tracks_count > 0 and schema_changed:
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

        # Migration 4: Multi-artist support
        # Add normalized_name column to artists table
        cursor.execute("PRAGMA table_info(artists)")
        artist_columns = [col[1] for col in cursor.fetchall()]
        if 'normalized_name' not in artist_columns:
            cursor.execute("ALTER TABLE artists ADD COLUMN normalized_name TEXT")
            # Populate normalized_name for existing artists
            cursor.execute("UPDATE artists SET normalized_name = LOWER(name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_normalized ON artists(normalized_name)")
            logger.info("[Database] Added 'normalized_name' column to artists table")

        # Create track_artists junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS track_artists (
                track_id INTEGER NOT NULL,
                artist_id INTEGER NOT NULL,
                position INTEGER DEFAULT 0,
                PRIMARY KEY (track_id, artist_id),
                FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_track_artists_artist
            ON track_artists(artist_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_track_artists_track
            ON track_artists(track_id)
        """)

        # Migration 5: Fix NULL normalized_name in artists table
        cursor.execute("SELECT COUNT(*) FROM artists WHERE normalized_name IS NULL")
        null_count = cursor.fetchone()[0]
        if null_count > 0:
            cursor.execute("UPDATE artists SET normalized_name = LOWER(name) WHERE normalized_name IS NULL")
            logger.info(f"[Database] Fixed {null_count} artists with NULL normalized_name")

        # Migration 6: Add file_size and file_mtime to tracks table (incremental scan)
        cursor.execute("PRAGMA table_info(tracks)")
        track_columns = [col[1] for col in cursor.fetchall()]
        if 'file_size' not in track_columns:
            cursor.execute("ALTER TABLE tracks ADD COLUMN file_size BIGINT")
            logger.info("[Database] Added 'file_size' column to tracks table")
        if 'file_mtime' not in track_columns:
            cursor.execute("ALTER TABLE tracks ADD COLUMN file_mtime DOUBLE")
            logger.info("[Database] Added 'file_mtime' column to tracks table")

        # Migration 7: Add genre column to tracks and create genres cache table
        cursor.execute("PRAGMA table_info(tracks)")
        track_columns = [col[1] for col in cursor.fetchall()]
        if 'genre' not in track_columns:
            cursor.execute("ALTER TABLE tracks ADD COLUMN genre TEXT")
            logger.info("[Database] Added 'genre' column to tracks table")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                cover_path TEXT,
                song_count INTEGER DEFAULT 0,
                album_count INTEGER DEFAULT 0
            )
        """)

        # Migration 8: Add total_duration column to genres table
        cursor.execute("PRAGMA table_info(genres)")
        genre_columns = [col[1] for col in cursor.fetchall()]
        if 'total_duration' not in genre_columns:
            cursor.execute("ALTER TABLE genres ADD COLUMN total_duration REAL DEFAULT 0.0")
            logger.info("[Database] Added 'total_duration' column to genres table")

        # Migration 9: Add unique indexes for UPSERT/INSERT OR IGNORE support
        if stored_version < 9:
            # Deduplicate play_history: keep only the most recent entry per track_id
            cursor.execute("""
                DELETE FROM play_history WHERE id NOT IN (
                    SELECT MAX(id) FROM play_history GROUP BY track_id
                )
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_play_history_track_unique
                    ON play_history(track_id)
            """)
            # Add partial unique indexes for favorites
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_track_unique
                    ON favorites(track_id)
                    WHERE track_id IS NOT NULL
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_cloud_file_unique
                    ON favorites(cloud_file_id)
                    WHERE cloud_file_id IS NOT NULL
            """)
            logger.info("[Database] Added unique indexes for UPSERT support")

        # Update schema version after all migrations complete
        if schema_changed:
            cursor.execute(
                "INSERT OR REPLACE INTO db_meta (key, value) VALUES ('schema_version', ?)",
                (str(CURRENT_SCHEMA_VERSION),)
            )
            logger.info(f"[Database] Schema version updated to {CURRENT_SCHEMA_VERSION}")

    # Track operations

    def add_track(self, track: Track) -> int:
        """Add a track to the database. Returns track ID."""
        # Serialize track data for thread safety
        track_data = {
            'path': track.path,
            'title': track.title,
            'artist': track.artist,
            'album': track.album,
            'genre': getattr(track, 'genre', None),
            'duration': track.duration,
            'cover_path': track.cover_path,
            'created_at': track.created_at or datetime.now(),
            'cloud_file_id': track.cloud_file_id,
            'source': track.source.value if hasattr(track, 'source') and track.source else 'Local',
            'file_size': getattr(track, 'file_size', None),
            'file_mtime': getattr(track, 'file_mtime', None),
        }

        # Check if we're in the write worker thread - execute directly
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_add_track(track_data, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_add_track, track_data)
        return future.result(timeout=10.0)

    def add_track_async(self, track: Track, callback: Callable[[int], None] = None) -> None:
        """
        Add a track asynchronously without blocking.

        Args:
            track: Track to add
            callback: Optional callback called with track ID on completion
        """
        track_data = {
            'path': track.path,
            'title': track.title,
            'artist': track.artist,
            'album': track.album,
            'genre': getattr(track, 'genre', None),
            'duration': track.duration,
            'cover_path': track.cover_path,
            'created_at': track.created_at or datetime.now(),
            'cloud_file_id': track.cloud_file_id,
            'source': track.source.value if hasattr(track, 'source') and track.source else 'Local',
            'file_size': getattr(track, 'file_size', None),
            'file_mtime': getattr(track, 'file_mtime', None),
        }

        if callback:
            future = self._submit_write(self._do_add_track, track_data)
            future.add_done_callback(lambda f: callback(f.result()))
        else:
            self._submit_write_async(self._do_add_track, track_data)

    def _do_add_track(self, track_data: dict, conn: sqlite3.Connection = None) -> int:
        """Internal method to add a track (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, title, artist, album, genre, duration, cover_path, created_at, cloud_file_id, source, file_size, file_mtime)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                track_data['path'],
                track_data['title'],
                track_data['artist'],
                track_data['album'],
                track_data['genre'],
                track_data['duration'],
                track_data['cover_path'],
                track_data['created_at'],
                track_data['cloud_file_id'],
                track_data['source'],
                track_data['file_size'],
                track_data['file_mtime'],
            ),
        )

        conn.commit()
        return cursor.lastrowid

    def _row_to_track(self, row) -> Track:
        """Convert a database row to a Track domain model."""
        return Track(
            id=row["id"],
            path=row["path"],
            title=row["title"],
            artist=row["artist"],
            album=row["album"],
            genre=row["genre"] if "genre" in row.keys() else None,
            duration=row["duration"],
            cover_path=row["cover_path"],
            created_at=datetime.fromisoformat(row["created_at"]),
            cloud_file_id=row["cloud_file_id"],
            source=self._get_track_source_from_row(row),
            file_size=row["file_size"] if "file_size" in row.keys() else None,
            file_mtime=row["file_mtime"] if "file_mtime" in row.keys() else None,
        )

    def get_track(self, track_id: int) -> Optional[Track]:
        """Get a track by ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks WHERE id = ?", (track_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_track(row)
        return None

    def get_tracks_by_ids(self, track_ids: List[int]) -> List[Track]:
        """
        Get multiple tracks by IDs in batch.

        Args:
            track_ids: List of track IDs

        Returns:
            List of Track objects (only existing tracks)
        """
        if not track_ids:
            return []

        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(track_ids))
        cursor.execute(f"SELECT * FROM tracks WHERE id IN ({placeholders})", track_ids)
        rows = cursor.fetchall()

        return [self._row_to_track(row) for row in rows]

    def get_track_by_path(self, path: str) -> Optional[Track]:
        """Get a track by file path."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks WHERE path = ?", (path,))
        row = cursor.fetchone()

        if row:
            return self._row_to_track(row)
        return None

    def get_track_by_cloud_file_id(self, cloud_file_id: str) -> Optional[Track]:
        """Get a track by cloud file ID."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM tracks WHERE cloud_file_id = ?", (cloud_file_id,))
        row = cursor.fetchone()

        if row:
            return self._row_to_track(row)
        return None

    def get_tracks_by_cloud_file_ids(self, cloud_file_ids: List[str]) -> Dict[str, Track]:
        """
        Get multiple tracks by cloud file IDs in batch.

        Args:
            cloud_file_ids: List of cloud file IDs

        Returns:
            Dict mapping cloud_file_id -> Track
        """
        if not cloud_file_ids:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()

        placeholders = ",".join("?" * len(cloud_file_ids))
        cursor.execute(f"SELECT * FROM tracks WHERE cloud_file_id IN ({placeholders})", cloud_file_ids)
        rows = cursor.fetchall()

        return {row["cloud_file_id"]: self._row_to_track(row) for row in rows if row["cloud_file_id"]}

    def get_track_index_for_paths(self, paths: list[str]) -> dict[str, dict]:
        """
        Bulk lookup of track metadata by file paths for incremental scan.

        Args:
            paths: List of file paths to look up

        Returns:
            Dict mapping path -> {"size": int|None, "mtime": float|None}
        """
        if not paths:
            return {}

        conn = self._get_connection()
        cursor = conn.cursor()

        # SQLite has a limit on bind params; chunk if needed
        chunk_size = 500
        result = {}

        for i in range(0, len(paths), chunk_size):
            chunk = paths[i:i + chunk_size]
            placeholders = ",".join("?" for _ in chunk)
            cursor.execute(
                f"SELECT path, file_size, file_mtime FROM tracks WHERE path IN ({placeholders})",
                chunk,
            )
            for row in cursor.fetchall():
                result[row[0]] = {
                    "size": row[1],
                    "mtime": row[2],
                }

        return result

    def add_tracks_bulk(self, tracks: list[Track]) -> tuple[int, int]:
        """
        Bulk insert/update tracks in a single transaction.

        Optimized to use batch operations instead of individual INSERTs.

        Args:
            tracks: List of Track objects to add

        Returns:
            (added_count, skipped_count)
        """
        def _bulk_insert(conn: sqlite3.Connection):
            added = 0
            skipped = 0
            cursor = conn.cursor()

            if not tracks:
                return added, skipped

            # Batch check for existing paths
            paths = [track.path for track in tracks]
            placeholders = ",".join("?" for _ in paths)
            cursor.execute(f"SELECT id, path FROM tracks WHERE path IN ({placeholders})", paths)
            existing_map = {row["path"]: row["id"] for row in cursor.fetchall()}

            # Separate into new tracks and updates
            new_tracks = []
            update_tracks = []

            for track in tracks:
                track_data = {
                    'path': track.path,
                    'title': track.title,
                    'artist': track.artist,
                    'album': track.album,
                    'genre': getattr(track, 'genre', None),
                    'duration': track.duration,
                    'cover_path': track.cover_path,
                    'created_at': track.created_at or datetime.now(),
                    'cloud_file_id': track.cloud_file_id,
                    'source': track.source.value if hasattr(track, 'source') and track.source else 'Local',
                    'file_size': getattr(track, 'file_size', None),
                    'file_mtime': getattr(track, 'file_mtime', None),
                }

                if track.path in existing_map:
                    update_tracks.append(track_data)
                else:
                    new_tracks.append(track_data)

            # Batch insert new tracks
            if new_tracks:
                cursor.executemany(
                    """
                    INSERT INTO tracks
                    (path, title, artist, album, genre, duration, cover_path, created_at, cloud_file_id, source, file_size, file_mtime)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            t['path'], t['title'], t['artist'], t['album'],
                            t['genre'], t['duration'], t['cover_path'], t['created_at'],
                            t['cloud_file_id'], t['source'], t['file_size'], t['file_mtime']
                        )
                        for t in new_tracks
                    ]
                )
                added = len(new_tracks)

            # Batch update existing tracks
            if update_tracks:
                cursor.executemany(
                    """
                    UPDATE tracks
                    SET title=?, artist=?, album=?, genre=?, duration=?, cover_path=?,
                        file_size=?, file_mtime=?
                    WHERE path=?
                    """,
                    [
                        (
                            t['title'], t['artist'], t['album'], t['genre'],
                            t['duration'], t['cover_path'],
                            t['file_size'], t['file_mtime'], t['path']
                        )
                        for t in update_tracks
                    ]
                )
                skipped = len(update_tracks)

            conn.commit()
            return added, skipped

        future = self._submit_write(_bulk_insert)
        return future.result(timeout=60.0)

    def get_all_tracks(self) -> List[Track]:
        """Get all tracks from the database, including downloaded cloud files."""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Get local tracks
        cursor.execute("SELECT * FROM tracks ORDER BY artist, album, title")
        rows = cursor.fetchall()

        tracks = [
            self._row_to_track(row)
            for row in rows
        ]

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
                ORDER BY score LIMIT 100
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
                    ORDER BY score LIMIT 100
                    """,
                    (fts_query,),
                )
                rows = cursor.fetchall()

            return [
                self._row_to_track(row)
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
            SELECT *
            FROM tracks
            WHERE title LIKE ?
               OR artist LIKE ?
               OR album LIKE ?
            ORDER BY artist, album, title
            """,
            (search_pattern, search_pattern, search_pattern),
        )

        rows = cursor.fetchall()

        return [
            self._row_to_track(row)
            for row in rows
        ]

    def delete_track(self, track_id: int) -> bool:
        """Delete a track from the database."""
        future = self._submit_write(self._do_delete_track, track_id)
        return future.result(timeout=10.0)

    def delete_track_async(self, track_id: int, callback: Callable[[bool], None] = None) -> None:
        """
        Delete a track asynchronously without blocking.

        Args:
            track_id: Track ID to delete
            callback: Optional callback called with success boolean on completion
        """
        if callback:
            future = self._submit_write(self._do_delete_track, track_id)
            future.add_done_callback(lambda f: callback(f.result()))
        else:
            self._submit_write_async(self._do_delete_track, track_id)

    def _do_delete_track(self, track_id: int, conn: sqlite3.Connection = None) -> bool:
        """Internal method to delete a track (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()

        return cursor.rowcount > 0

    def update_track(
            self, track_id: int, title: str = None, artist: str = None, album: str = None,
            genre: str = None, cloud_file_id: str = None
    ) -> bool:
        """Update track metadata in the database."""
        future = self._submit_write(self._do_update_track, track_id, title, artist, album, genre, cloud_file_id)
        return future.result(timeout=10.0)

    def update_track_async(
            self, track_id: int, title: str = None, artist: str = None, album: str = None,
            genre: str = None, cloud_file_id: str = None, callback: Callable[[bool], None] = None
    ) -> None:
        """
        Update track metadata asynchronously without blocking.

        Args:
            track_id: Track ID to update
            title: New title (optional)
            artist: New artist (optional)
            album: New album (optional)
            genre: New genre (optional)
            cloud_file_id: New cloud file ID (optional)
            callback: Optional callback called with success boolean on completion
        """
        if callback:
            future = self._submit_write(self._do_update_track, track_id, title, artist, album, genre, cloud_file_id)
            future.add_done_callback(lambda f: callback(f.result()))
        else:
            self._submit_write_async(self._do_update_track, track_id, title, artist, album, genre, cloud_file_id)

    def _do_update_track(
            self, track_id: int, title: str = None, artist: str = None, album: str = None,
            genre: str = None, cloud_file_id: str = None, conn: sqlite3.Connection = None
    ) -> bool:
        """Internal method to update track metadata (runs in write worker)."""
        if conn is None:
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
        if genre is not None:
            updates.append("genre = ?")
            params.append(genre)
        if cloud_file_id is not None:
            updates.append("cloud_file_id = ?")
            params.append(cloud_file_id)

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
        logger.info(f"[DatabaseManager] update_track_cover_path: track_id={track_id}, cover_path={cover_path}")

        future = self._submit_write(self._do_update_track_cover_path, track_id, cover_path)
        return future.result(timeout=10.0)

    def _do_update_track_cover_path(self, track_id: int, cover_path: str, conn: sqlite3.Connection = None) -> bool:
        """Internal method to update track cover path (runs in write worker)."""
        if conn is None:
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

    def update_track_path(self, track_id: int, path: str) -> bool:
        """Update path for a track."""
        logger.info(f"[DatabaseManager] update_track_path: track_id={track_id}, path={path}")

        # Check if we're in the write worker thread - execute directly
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_update_track_path(track_id, path, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_update_track_path, track_id, path)
        return future.result(timeout=10.0)

    def _do_update_track_path(self, track_id: int, path: str, conn: sqlite3.Connection = None) -> bool:
        """Internal method to update track path (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE tracks
            SET path = ?
            WHERE id = ?
            """,
            (path, track_id),
        )

        conn.commit()
        affected = cursor.rowcount
        logger.info(f"[DatabaseManager] Updated {affected} row(s)")
        return affected > 0

    # Playlist operations

    def create_playlist(self, name: str) -> int:
        """Create a new playlist. Returns playlist ID."""
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_create_playlist(name, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_create_playlist, name)
        return future.result(timeout=10.0)

    def _do_create_playlist(self, name: str, conn: sqlite3.Connection = None) -> int:
        """Internal method to create playlist (runs in write worker)."""
        if conn is None:
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
            SELECT t.*
            FROM tracks t
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
                cloud_file_id=row["cloud_file_id"],
                source=self._get_track_source_from_row(row),
            )
            for row in rows
        ]

    def add_track_to_playlist(self, playlist_id: int, track_id: int) -> bool:
        """Add a track to a playlist."""
        # Check if we're in the write worker thread - execute directly
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_add_track_to_playlist(playlist_id, track_id, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_add_track_to_playlist, playlist_id, track_id)
        return future.result(timeout=10.0)

    def _do_add_track_to_playlist(self, playlist_id: int, track_id: int, conn: sqlite3.Connection = None) -> bool:
        """Internal method to add track to playlist (runs in write worker)."""
        if conn is None:
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
        # Use is not None check because MAX can return 0 which is falsy
        next_position = (result["max_pos"] if result["max_pos"] is not None else -1) + 1

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
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_remove_track_from_playlist(playlist_id, track_id, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_remove_track_from_playlist, playlist_id, track_id)
        return future.result(timeout=10.0)

    def _do_remove_track_from_playlist(self, playlist_id: int, track_id: int, conn: sqlite3.Connection = None) -> bool:
        """Internal method to remove track from playlist (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        # Get position before deletion
        cursor.execute(
            "SELECT position FROM playlist_items WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )
        row = cursor.fetchone()
        if row is None:
            return False

        position = row["position"]

        # Delete the track
        cursor.execute(
            "DELETE FROM playlist_items WHERE playlist_id = ? AND track_id = ?",
            (playlist_id, track_id),
        )

        # Reorder remaining items using saved position
        cursor.execute(
            "UPDATE playlist_items SET position = position - 1 WHERE playlist_id = ? AND position > ?",
            (playlist_id, position),
        )

        conn.commit()
        return True

    def delete_playlist(self, playlist_id: int) -> bool:
        """Delete a playlist."""
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_delete_playlist(playlist_id, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_delete_playlist, playlist_id)
        return future.result(timeout=10.0)

    def _do_delete_playlist(self, playlist_id: int, conn: sqlite3.Connection = None) -> bool:
        """Internal method to delete playlist (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
        conn.commit()

        return cursor.rowcount > 0

    def rename_playlist(self, playlist_id: int, new_name: str) -> bool:
        """Rename a playlist."""
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_rename_playlist(playlist_id, new_name, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_rename_playlist, playlist_id, new_name)
        return future.result(timeout=10.0)

    def _do_rename_playlist(self, playlist_id: int, new_name: str, conn: sqlite3.Connection = None) -> bool:
        """Internal method to rename playlist (runs in write worker)."""
        if conn is None:
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
        current_thread = threading.current_thread()
        if current_thread.name == "DBWriteWorker":
            return self._do_remove_track(track_id, conn=self._write_worker._get_connection())

        future = self._submit_write(self._do_remove_track, track_id)
        return future.result(timeout=10.0)

    def _do_remove_track(self, track_id: int, conn: sqlite3.Connection = None) -> bool:
        """Internal method to remove track (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("DELETE FROM tracks WHERE id = ?", (track_id,))
        conn.commit()

        return cursor.rowcount > 0

    # Play history operations

    def add_play_history(self, track_id: int) -> int:
        """Add a play history entry or increment play count."""
        future = self._submit_write(self._do_add_play_history, track_id)
        return future.result(timeout=10.0)

    def _do_add_play_history(self, track_id: int, conn: sqlite3.Connection = None) -> int:
        """Internal method to add play history (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        # Check if there's a recent entry for today
        cursor.execute(
            """
            SELECT id, play_count
            FROM play_history
            WHERE track_id = ? AND DATE (played_at) = DATE ('now')
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
                SET play_count = play_count + 1,
                    played_at  = CURRENT_TIMESTAMP
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

    def get_play_history(self, limit: int = 100) -> List[PlayHistory]:
        """Get recent play history."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM play_history
            ORDER BY played_at DESC LIMIT ?
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
            ORDER BY total_plays DESC LIMIT ?
            """,
            (limit,),
        )

        return cursor.fetchall()

    # Favorites operations

    def add_favorite(self, track_id: int = None, cloud_file_id: str = None, cloud_account_id: int = None) -> bool:
        """Add a track or cloud file to favorites."""
        future = self._submit_write(self._do_add_favorite, track_id, cloud_file_id, cloud_account_id)
        return future.result(timeout=10.0)

    def _do_add_favorite(self, track_id: int = None, cloud_file_id: str = None, cloud_account_id: int = None, conn: sqlite3.Connection = None) -> bool:
        """Internal method to add favorite (runs in write worker)."""
        if conn is None:
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
        future = self._submit_write(self._do_remove_favorite, track_id, cloud_file_id)
        return future.result(timeout=10.0)

    def _do_remove_favorite(self, track_id: int = None, cloud_file_id: str = None, conn: sqlite3.Connection = None) -> bool:
        """Internal method to remove favorite (runs in write worker)."""
        if conn is None:
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

    def get_all_favorite_track_ids(self) -> set:
        """Get all favorite local track IDs as a set for O(1) lookup."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT track_id FROM favorites WHERE track_id IS NOT NULL")
        return {row["track_id"] for row in cursor.fetchall()}

    def get_favorites(self) -> List[Track]:
        """Get all favorite tracks (including downloaded cloud files with track_id)."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
                       SELECT t.*
                       FROM tracks t
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
                source=self._get_track_source_from_row(row),
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
                       SELECT t.*, f.created_at as fav_created_at
                       FROM tracks t
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
                       SELECT f.cloud_file_id,
                              f.cloud_account_id,
                              f.created_at,
                              cf.name,
                              cf.duration,
                              cf.local_path
                       FROM favorites f
                                LEFT JOIN cloud_files cf ON f.cloud_file_id = cf.file_id
                       WHERE f.cloud_file_id IS NOT NULL
                         AND f.track_id IS NULL
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
        future = self._submit_write(
            self._do_create_cloud_account, provider, account_name, account_email, access_token, refresh_token
        )
        return future.result(timeout=10.0)

    def _do_create_cloud_account(
            self, provider: str, account_name: str, account_email: str, access_token: str, refresh_token: str,
            conn: sqlite3.Connection = None,
    ) -> int:
        """Internal: create cloud account (runs in write worker)."""
        if conn is None:
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
                SELECT *
                FROM cloud_accounts
                WHERE provider = ?
                  AND is_active = 1
                ORDER BY created_at DESC
                """,
                (provider,),
            )
        else:
            cursor.execute(
                """
                SELECT *
                FROM cloud_accounts
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
                last_playing_local_path=row[
                    "last_playing_local_path"] if "last_playing_local_path" in row.keys() else "",
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
        return None

    def update_cloud_account_token(
            self, account_id: int, access_token: str, refresh_token: str = None
    ) -> bool:
        """Update account tokens."""
        future = self._submit_write(self._do_update_cloud_account_token, account_id, access_token, refresh_token)
        return future.result(timeout=10.0)

    def _do_update_cloud_account_token(
            self, account_id: int, access_token: str, refresh_token: str,
            conn: sqlite3.Connection = None,
    ) -> bool:
        """Internal: update account tokens (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        if refresh_token is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token  = ?,
                    refresh_token = ?,
                    updated_at    = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (access_token, refresh_token, account_id),
            )
        else:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET access_token = ?,
                    updated_at   = CURRENT_TIMESTAMP
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
        future = self._submit_write(self._do_update_cloud_account_folder, account_id, folder_path, fid_path)
        return future.result(timeout=10.0)

    def _do_update_cloud_account_folder(
            self, account_id: int, folder_path: str, fid_path: str,
            conn: sqlite3.Connection = None,
    ) -> bool:
        """Internal: update account folder (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_accounts
            SET last_folder_path = ?,
                last_fid_path    = ?,
                updated_at       = CURRENT_TIMESTAMP
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
        future = self._submit_write(
            self._do_update_cloud_account_playing_state, account_id, playing_fid, position, local_path
        )
        return future.result(timeout=10.0)

    def _do_update_cloud_account_playing_state(
            self, account_id: int, playing_fid: str, position: float, local_path: str,
            conn: sqlite3.Connection = None,
    ) -> bool:
        """Internal: update playing state (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        # Build update query dynamically based on provided parameters
        if playing_fid is not None and position is not None and local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid        = ?,
                    last_position           = ?,
                    last_playing_local_path = ?,
                    updated_at              = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, position, local_path, account_id),
            )
        elif playing_fid is not None and position is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?,
                    last_position    = ?,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, position, account_id),
            )
        elif playing_fid is not None and local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid        = ?,
                    last_playing_local_path = ?,
                    updated_at              = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, local_path, account_id),
            )
        elif playing_fid is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_fid = ?,
                    updated_at       = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (playing_fid, account_id),
            )
        elif position is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_position = ?,
                    updated_at    = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (position, account_id),
            )
        elif local_path is not None:
            cursor.execute(
                """
                UPDATE cloud_accounts
                SET last_playing_local_path = ?,
                    updated_at              = CURRENT_TIMESTAMP
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
        future = self._submit_write(self._do_update_cloud_file_local_path, file_id, account_id, local_path)
        return future.result(timeout=10.0)

    def _do_update_cloud_file_local_path(
            self, file_id: str, account_id: int, local_path: str, conn: sqlite3.Connection = None
    ) -> bool:
        """Internal method to update cloud file local path (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_files
            SET local_path = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE file_id = ?
              AND account_id = ?
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
            SELECT *
            FROM cloud_files
            WHERE local_path = ?
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
            SELECT *
            FROM cloud_files
            WHERE local_path IS NOT NULL
              AND local_path != ''
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
        future = self._submit_write(self._do_delete_cloud_account, account_id)
        return future.result(timeout=10.0)

    def _do_delete_cloud_account(self, account_id: int, conn: sqlite3.Connection = None) -> bool:
        """Internal: delete cloud account (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE cloud_accounts
            SET is_active  = 0,
                updated_at = CURRENT_TIMESTAMP
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

        future = self._submit_write(self._do_cache_cloud_files, account_id, files)
        return future.result(timeout=30.0)

    def _do_cache_cloud_files(
            self, account_id: int, files: List[CloudFile], conn: sqlite3.Connection = None
    ) -> bool:
        """Internal: cache cloud files (runs in write worker)."""
        if conn is None:
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

        # Insert new files, preserving local_path if it existed (use executemany for bulk performance)
        cursor.executemany(
            """
            INSERT INTO cloud_files
            (account_id, file_id, parent_id, name, file_type, size, mime_type, duration, metadata, local_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
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
                    existing_paths.get(file.file_id),
                )
                for file in files
            ],
        )

        conn.commit()
        return True

    def get_cloud_files(self, account_id: int, parent_id: str = "") -> List[CloudFile]:
        """Get cached files for an account and parent folder."""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT *
            FROM cloud_files
            WHERE account_id = ?
              AND parent_id = ?
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
            SELECT *
            FROM cloud_files
            WHERE file_id = ?
              AND account_id = ?
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
            SELECT *
            FROM cloud_files
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
        # Serialize value to string
        if isinstance(value, str):
            value_str = value
        else:
            value_str = json.dumps(value)

        future = self._submit_write(self._do_set_setting, key, value_str)
        return future.result(timeout=10.0)

    def _do_set_setting(self, key: str, value_str: str, conn: sqlite3.Connection = None) -> bool:
        """Internal method to set setting (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

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
        future = self._submit_write(self._do_delete_setting, key)
        return future.result(timeout=10.0)

    def _do_delete_setting(self, key: str, conn: sqlite3.Connection = None) -> bool:
        """Internal: delete setting (runs in write worker)."""
        if conn is None:
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
        # Serialize items to simple dicts for thread safety
        items_data = [
            {
                'position': i,
                'source': item.source,
                'track_id': item.track_id,
                'cloud_file_id': item.cloud_file_id,
                'cloud_account_id': item.cloud_account_id,
                'local_path': item.local_path,
                'title': item.title,
                'artist': item.artist,
                'album': item.album,
                'duration': item.duration,
                'created_at': item.created_at or datetime.now(),
                'download_failed': int(item.download_failed),
            }
            for i, item in enumerate(items)
        ]

        # Use async submit to avoid blocking Qt event loop
        self._submit_write_async(self._do_save_play_queue, items_data)
        return True

    def _do_save_play_queue(self, items_data: list, conn: sqlite3.Connection = None) -> bool:
        """Internal method to save play queue (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing queue
        cursor.execute("DELETE FROM play_queue")

        # Insert new items using executemany for bulk performance
        if items_data:
            cursor.executemany(
                """
                INSERT INTO play_queue
                (position, source, track_id, cloud_file_id, cloud_account_id,
                 local_path, title, artist, album, duration, created_at,
                 download_failed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item['position'],
                        item['source'],
                        item['track_id'],
                        item['cloud_file_id'],
                        item['cloud_account_id'],
                        item['local_path'],
                        item['title'],
                        item['artist'],
                        item['album'],
                        item['duration'],
                        item['created_at'],
                        item['download_failed'],
                    )
                    for item in items_data
                ],
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
            SELECT *
            FROM play_queue
            ORDER BY position ASC
            """
        )

        rows = cursor.fetchall()

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
                    return "QQ"
                elif source_type == "cloud" and cloud_type:
                    return cloud_type.upper()
            return "Local"

        def get_download_failed(row, columns):
            """Get download_failed value, handling schema migration."""
            if "download_failed" in columns:
                return bool(row["download_failed"])
            return False

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
                download_failed=get_download_failed(row, columns),
                created_at=datetime.fromisoformat(row["created_at"])
                if row["created_at"]
                else None,
            )
            for row in rows
        ]

    def update_play_queue_local_path(self, track_id: int, local_path: str) -> bool:
        """
        Update local_path for all play_queue entries with the given track_id.

        Args:
            track_id: Track ID to update
            local_path: New local path

        Returns:
            True if successful
        """
        future = self._submit_write(self._do_update_play_queue_local_path, track_id, local_path)
        return future.result(timeout=10.0)

    def _do_update_play_queue_local_path(
            self, track_id: int, local_path: str, conn: sqlite3.Connection = None
    ) -> bool:
        """Internal: update play_queue local_path (runs in write worker)."""
        if conn is None:
            conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE play_queue SET local_path = ? WHERE track_id = ?",
            (local_path, track_id)
        )

        conn.commit()
        return True

    def clear_play_queue(self) -> bool:
        """
        Clear the play queue.

        Returns:
            True if successful
        """
        future = self._submit_write(self._do_clear_play_queue)
        return future.result(timeout=10.0)

    def _do_clear_play_queue(self, conn: sqlite3.Connection = None) -> bool:
        """Internal method to clear play queue (runs in write worker)."""
        if conn is None:
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

    # Album operations

    def refresh_albums(self) -> bool:
        """
        Refresh the albums table from tracks table.
        Preserves existing cover_path for albums that already have one.

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Save existing cover_path values before clearing
        cursor.execute("""
            SELECT name, artist, cover_path FROM albums
            WHERE cover_path IS NOT NULL AND cover_path != ''
        """)
        existing_covers = {(row['name'], row['artist']): row['cover_path'] for row in cursor.fetchall()}

        # Clear existing data
        cursor.execute("DELETE FROM albums")

        # Populate from tracks
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            SELECT
                album as name,
                artist,
                cover_path,
                COUNT(*) as song_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE album IS NOT NULL AND album != ''
            GROUP BY album, artist
        """)

        # Restore preserved cover_path values (user-set covers)
        for (name, artist), cover_path in existing_covers.items():
            cursor.execute("""
                UPDATE albums SET cover_path = ?
                WHERE name = ? AND artist = ?
            """, (cover_path, name, artist))

        conn.commit()
        return True

    def get_albums_from_db(self) -> List[dict]:
        """
        Get all albums from database.

        Returns:
            List of album dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, artist, cover_path, song_count, total_duration
            FROM albums
            ORDER BY song_count DESC
        """)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def is_albums_empty(self) -> bool:
        """Check if albums table is empty."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM albums")
        row = cursor.fetchone()
        return row["count"] == 0 if row else True

    # Genre operations

    def refresh_genres(self) -> bool:
        """
        Refresh the genres table from tracks table.

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Clear existing data
        cursor.execute("DELETE FROM genres")

        # Populate from tracks
        cursor.execute("""
            INSERT INTO genres (name, cover_path, song_count, album_count)
            SELECT
                genre as name,
                MAX(CASE WHEN cover_path IS NOT NULL THEN cover_path END) as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count
            FROM tracks
            WHERE genre IS NOT NULL AND genre != ''
            GROUP BY genre
        """)

        conn.commit()
        return True

    def get_genres_from_db(self) -> List[dict]:
        """
        Get all genres from database.

        Returns:
            List of genre dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, cover_path, song_count, album_count
            FROM genres
            ORDER BY song_count DESC
        """)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # Artist operations

    def refresh_artists(self) -> bool:
        """
        Refresh the artists table from tracks table.
        Preserves existing cover_path for artists that already have one.

        Returns:
            True if successful
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Save existing cover_path values before clearing
        cursor.execute("""
            SELECT name, cover_path FROM artists
            WHERE cover_path IS NOT NULL AND cover_path != ''
        """)
        existing_covers = {row['name']: row['cover_path'] for row in cursor.fetchall()}

        # Clear existing data
        cursor.execute("DELETE FROM artists")

        # Populate from tracks
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
            SELECT
                artist as name,
                MAX(CASE WHEN cover_path IS NOT NULL THEN cover_path END) as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                LOWER(artist) as normalized_name
            FROM tracks
            WHERE artist IS NOT NULL AND artist != ''
            GROUP BY artist
        """)

        # Restore preserved cover_path values (user-set covers)
        for name, cover_path in existing_covers.items():
            cursor.execute("""
                UPDATE artists SET cover_path = ?
                WHERE name = ?
            """, (cover_path, name))

        conn.commit()
        return True

    def rebuild_albums_artists(self) -> dict:
        """
        Rebuild albums and artists tables from tracks table.
        Preserves existing cover_path for albums and artists.

        This is useful for fixing data inconsistency issues.

        Returns:
            Dict with 'albums' and 'artists' counts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Save existing cover_path values before clearing
        cursor.execute("""
            SELECT name, artist, cover_path FROM albums
            WHERE cover_path IS NOT NULL AND cover_path != ''
        """)
        album_covers = {(row['name'], row['artist']): row['cover_path'] for row in cursor.fetchall()}

        cursor.execute("""
            SELECT name, cover_path FROM artists
            WHERE cover_path IS NOT NULL AND cover_path != ''
        """)
        artist_covers = {row['name']: row['cover_path'] for row in cursor.fetchall()}

        # Rebuild albums
        cursor.execute("DELETE FROM albums")
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            SELECT
                album as name,
                artist,
                cover_path,
                COUNT(*) as song_count,
                SUM(duration) as total_duration
            FROM tracks
            WHERE album IS NOT NULL AND album != ''
            GROUP BY album, artist
        """)
        albums_count = cursor.rowcount

        # Restore preserved album cover_path values
        for (name, artist), cover_path in album_covers.items():
            cursor.execute("""
                UPDATE albums SET cover_path = ?
                WHERE name = ? AND artist = ?
            """, (cover_path, name, artist))

        # Rebuild artists
        cursor.execute("DELETE FROM artists")
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
            SELECT
                artist as name,
                (SELECT cover_path FROM tracks t2
                 WHERE t2.artist = tracks.artist AND cover_path IS NOT NULL
                 LIMIT 1) as cover_path,
                COUNT(*) as song_count,
                COUNT(DISTINCT album) as album_count,
                LOWER(artist) as normalized_name
            FROM tracks
            WHERE artist IS NOT NULL AND artist != ''
            GROUP BY artist
        """)
        artists_count = cursor.rowcount

        # Restore preserved artist cover_path values
        for name, cover_path in artist_covers.items():
            cursor.execute("""
                UPDATE artists SET cover_path = ?
                WHERE name = ?
            """, (cover_path, name))

        conn.commit()

        return {
            'albums': albums_count,
            'artists': artists_count
        }

    def get_artists_from_db(self) -> List[dict]:
        """
        Get all artists from database.

        Returns:
            List of artist dictionaries
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name, cover_path, song_count, album_count
            FROM artists
            ORDER BY song_count DESC
        """)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def is_artists_empty(self) -> bool:
        """Check if artists table is empty."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM artists")
        row = cursor.fetchone()
        return row["count"] == 0 if row else True

    # === Albums Incremental Updates ===

    def update_albums_on_track_added(self, album: str, artist: str, cover_path: str, duration: float) -> None:
        """
        Update albums table when a track is added.

        Args:
            album: Album name
            artist: Artist name
            cover_path: Path to cover image
            duration: Track duration in seconds
        """
        if not album or not artist:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if album exists
        cursor.execute(
            "SELECT id, song_count, total_duration FROM albums WHERE name = ? AND artist = ?",
            (album, artist)
        )
        row = cursor.fetchone()

        if row:
            # Update existing album
            cursor.execute("""
                UPDATE albums
                SET song_count = song_count + 1,
                    total_duration = total_duration + ?,
                    cover_path = COALESCE(cover_path, ?)
                WHERE id = ?
            """, (duration, cover_path, row["id"]))
        else:
            # Insert new album
            cursor.execute("""
                INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
                VALUES (?, ?, ?, 1, ?)
            """, (album, artist, cover_path, duration))

        conn.commit()

    def update_albums_on_track_updated(
        self,
        old_album: str, old_artist: str, old_duration: float,
        new_album: str, new_artist: str, new_cover_path: str, new_duration: float
    ) -> None:
        """
        Update albums table when a track's metadata is updated.

        Args:
            old_album: Previous album name
            old_artist: Previous artist name
            old_duration: Previous duration
            new_album: New album name
            new_artist: New artist name
            new_cover_path: New cover path
            new_duration: New duration
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # If album or artist changed, we need to update both old and new albums
        if old_album != new_album or old_artist != new_artist:
            # Decrease count for old album
            if old_album and old_artist:
                cursor.execute("""
                    UPDATE albums
                    SET song_count = song_count - 1,
                        total_duration = total_duration - ?
                    WHERE name = ? AND artist = ?
                """, (old_duration, old_album, old_artist))

                # Delete album if no songs left
                cursor.execute("""
                    DELETE FROM albums WHERE name = ? AND artist = ? AND song_count <= 0
                """, (old_album, old_artist))

            # Increase count for new album
            if new_album and new_artist:
                self.update_albums_on_track_added(new_album, new_artist, new_cover_path, new_duration)
        else:
            # Same album, just update duration and cover
            cursor.execute("""
                UPDATE albums
                SET total_duration = total_duration - ? + ?,
                    cover_path = COALESCE(cover_path, ?)
                WHERE name = ? AND artist = ?
            """, (old_duration, new_duration, new_cover_path, new_album, new_artist))

        conn.commit()

    def update_albums_on_track_deleted(self, album: str, artist: str, duration: float) -> None:
        """
        Update albums table when a track is deleted.

        Args:
            album: Album name
            artist: Artist name
            duration: Track duration in seconds
        """
        if not album or not artist:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        # Decrease count
        cursor.execute("""
            UPDATE albums
            SET song_count = song_count - 1,
                total_duration = total_duration - ?
            WHERE name = ? AND artist = ?
        """, (duration, album, artist))

        # Delete album if no songs left
        cursor.execute("""
            DELETE FROM albums WHERE name = ? AND artist = ? AND song_count <= 0
        """, (album, artist))

        conn.commit()

    # === Artists Incremental Updates ===

    def update_artists_on_track_added(self, artist: str, album: str, cover_path: str) -> None:
        """
        Update artists table when a track is added.

        Args:
            artist: Artist name
            album: Album name (for album count)
            cover_path: Path to cover image
        """
        if not artist:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        # Check if artist exists
        cursor.execute(
            "SELECT id, song_count, album_count FROM artists WHERE name = ?",
            (artist,)
        )
        row = cursor.fetchone()

        if row:
            # Update existing artist
            # Check if this is a new album for this artist
            cursor.execute("""
                SELECT COUNT(*) as count FROM tracks
                WHERE artist = ? AND album = ?
            """, (artist, album))
            album_exists = cursor.fetchone()["count"] > 0

            new_album_count = row["album_count"]
            if album and not album_exists:
                new_album_count += 1

            cursor.execute("""
                UPDATE artists
                SET song_count = song_count + 1,
                    album_count = ?,
                    cover_path = COALESCE(cover_path, ?)
                WHERE id = ?
            """, (new_album_count, cover_path, row["id"]))
        else:
            # Insert new artist
            cursor.execute("""
                INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
                VALUES (?, ?, 1, ?, LOWER(?))
            """, (artist, cover_path, 1 if album else 0, artist))

        conn.commit()

    def update_artists_on_track_updated(
        self,
        old_artist: str, old_album: str,
        new_artist: str, new_album: str, new_cover_path: str
    ) -> None:
        """
        Update artists table when a track's metadata is updated.

        Args:
            old_artist: Previous artist name
            old_album: Previous album name
            new_artist: New artist name
            new_album: New album name
            new_cover_path: New cover path
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # If artist changed, we need to update both old and new artists
        if old_artist != new_artist:
            # Decrease count for old artist
            if old_artist:
                cursor.execute("""
                    UPDATE artists
                    SET song_count = song_count - 1
                    WHERE name = ?
                """, (old_artist,))

                # Recalculate album count for old artist
                cursor.execute("""
                    UPDATE artists
                    SET album_count = (
                        SELECT COUNT(DISTINCT album) FROM tracks WHERE artist = ?
                    )
                    WHERE name = ?
                """, (old_artist, old_artist))

                # Delete artist if no songs left
                cursor.execute("DELETE FROM artists WHERE name = ? AND song_count <= 0", (old_artist,))

            # Increase count for new artist
            if new_artist:
                self.update_artists_on_track_added(new_artist, new_album, new_cover_path)
        else:
            # Same artist, check if album changed
            if old_album != new_album:
                # Recalculate album count
                cursor.execute("""
                    UPDATE artists
                    SET album_count = (
                        SELECT COUNT(DISTINCT album) FROM tracks WHERE artist = ?
                    ),
                    cover_path = COALESCE(cover_path, ?)
                    WHERE name = ?
                """, (new_artist, new_cover_path, new_artist))

        conn.commit()

    def update_artists_on_track_deleted(self, artist: str, album: str) -> None:
        """
        Update artists table when a track is deleted.

        Args:
            artist: Artist name
            album: Album name
        """
        if not artist:
            return

        conn = self._get_connection()
        cursor = conn.cursor()

        # Decrease count
        cursor.execute("""
            UPDATE artists
            SET song_count = song_count - 1
            WHERE name = ?
        """, (artist,))

        # Recalculate album count
        cursor.execute("""
            UPDATE artists
            SET album_count = (
                SELECT COUNT(DISTINCT album) FROM tracks WHERE artist = ?
            )
            WHERE name = ?
        """, (artist, artist))

        # Delete artist if no songs left
        cursor.execute("DELETE FROM artists WHERE name = ? AND song_count <= 0", (artist,))

        conn.commit()

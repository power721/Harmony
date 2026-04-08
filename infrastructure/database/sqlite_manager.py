"""
Database manager for the music player using SQLite.
"""
import atexit
import logging
import re
import sqlite3
import threading
from concurrent.futures import Future
from datetime import datetime
from typing import Callable, Dict, List, Optional

from domain.cloud import CloudAccount, CloudFile
from domain.playlist import Playlist
from domain.track import Track, TrackSource
from infrastructure.database.db_write_worker import get_write_worker

# Configure logging
logger = logging.getLogger(__name__)

_FTS_BOOLEAN_OPERATORS = re.compile(r"\b(?:AND|OR|NOT)\b", re.IGNORECASE)
_FTS_FIELD_SPECIFIERS = re.compile(r"\b(?:title|artist|album)\s*:", re.IGNORECASE)
_FTS_UNSAFE_CHARACTERS = re.compile(r"[^\w\s.-]+", re.UNICODE)


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
        self._connections: Dict[int, sqlite3.Connection] = {}
        self._connections_lock = threading.Lock()
        self._write_worker = get_write_worker(db_path)
        atexit.register(self.close)
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
            with self._connections_lock:
                self._connections[threading.get_ident()] = self.local.conn
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

    @staticmethod
    def _build_safe_fts_query(query: str) -> Optional[str]:
        """Normalize user input into literal FTS terms and remove FTS operators."""
        cleaned = _FTS_FIELD_SPECIFIERS.sub(" ", query)
        cleaned = _FTS_BOOLEAN_OPERATORS.sub(" ", cleaned)
        cleaned = cleaned.replace("*", " ")
        cleaned = _FTS_UNSAFE_CHARACTERS.sub(" ", cleaned)
        terms = [term for term in cleaned.split() if term]
        if not terms:
            return None
        return " ".join(f'"{term}"' for term in terms)

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
                           online_provider_id
                           TEXT,
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
        cursor.execute("PRAGMA table_info(tracks)")
        track_columns = {col[1] for col in cursor.fetchall()}
        if "cloud_file_id" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_cloud_file_id
                               ON tracks(cloud_file_id)
                           """)
        if "source" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_source
                               ON tracks(source)
                           """)
        if "created_at" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_created_at
                               ON tracks(created_at DESC)
                           """)
        if "genre" in track_columns:
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
                           online_provider_id
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

        # Create indexes for columns that may be added by migrations.
        cursor.execute("PRAGMA table_info(tracks)")
        track_columns = {col[1] for col in cursor.fetchall()}
        if "cloud_file_id" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_cloud_file_id
                               ON tracks(cloud_file_id)
                           """)
        if "source" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_source
                               ON tracks(source)
                           """)
        if "created_at" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_created_at
                               ON tracks(created_at DESC)
                           """)
        if "genre" in track_columns:
            cursor.execute("""
                           CREATE INDEX IF NOT EXISTS idx_tracks_genre
                               ON tracks(genre)
                           """)

        conn.commit()

    def _get_track_source_from_row(self, row) -> TrackSource:
        """
        Helper to get TrackSource from database row.

        Handles missing 'source' column for backward compatibility.
        """
        if "source" not in row.keys() or not row["source"]:
            return TrackSource.LOCAL
        return TrackSource.from_value(row["source"])

    def _run_migrations(self, conn, cursor):
        """Run database migrations for schema updates."""
        # Current schema version - increment when making schema changes
        CURRENT_SCHEMA_VERSION = 11

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
            # 'online' + any provider -> 'ONLINE'
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
                        WHEN source_type = 'online' THEN 'ONLINE'
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

        cursor.execute("PRAGMA table_info(tracks)")
        track_columns = {row[1] for row in cursor.fetchall()}
        if "online_provider_id" not in track_columns:
            cursor.execute("ALTER TABLE tracks ADD COLUMN online_provider_id TEXT")

        cursor.execute("PRAGMA table_info(play_queue)")
        pq_columns = {row[1] for row in cursor.fetchall()}
        if "online_provider_id" not in pq_columns:
            cursor.execute("ALTER TABLE play_queue ADD COLUMN online_provider_id TEXT")

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

        # Migration 10: Repair legacy QQ online-provider rows.
        if stored_version < 11:
            cursor.execute("""
                UPDATE tracks
                SET source = 'ONLINE',
                    online_provider_id = 'qqmusic'
                WHERE UPPER(COALESCE(source, '')) = 'QQ'
                  AND (
                    online_provider_id IS NULL
                    OR TRIM(online_provider_id) = ''
                    OR LOWER(online_provider_id) = 'online'
                  )
            """)
            cursor.execute("""
                UPDATE tracks
                SET online_provider_id = 'qqmusic'
                WHERE UPPER(COALESCE(source, '')) = 'ONLINE'
                  AND LOWER(COALESCE(path, '')) LIKE 'online://qqmusic/%'
                  AND (
                    online_provider_id IS NULL
                    OR TRIM(online_provider_id) = ''
                    OR LOWER(online_provider_id) = 'online'
                  )
            """)
            cursor.execute("""
                UPDATE play_queue
                SET online_provider_id = 'qqmusic'
                WHERE UPPER(COALESCE(source, '')) = 'ONLINE'
                  AND LOWER(COALESCE(online_provider_id, '')) = 'online'
                  AND cloud_file_id IN (
                    SELECT cloud_file_id
                    FROM tracks
                    WHERE online_provider_id = 'qqmusic'
                  )
            """)
            cursor.execute("""
                UPDATE play_queue
                SET online_provider_id = NULL
                WHERE LOWER(COALESCE(online_provider_id, '')) = 'online'
            """)
            logger.info("[Database] Repaired legacy QQ online provider ids")

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

        User input is normalized to literal terms before being passed to FTS.

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
            fts_query = self._build_safe_fts_query(query)
            if fts_query is None:
                return []

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

    def close(self):
        """Close database connections and stop the write worker."""
        with self._connections_lock:
            connections = list(self._connections.values())
            self._connections.clear()

        for conn in connections:
            try:
                conn.close()
            except sqlite3.Error as exc:
                logger.warning("[Database] Error closing thread-local connection: %s", exc)

        if hasattr(self.local, "conn"):
            delattr(self.local, "conn")

        if self._write_worker is not None:
            try:
                self._write_worker.stop()
            except Exception as exc:
                logger.warning("[Database] Error stopping write worker: %s", exc)

    # Cloud account operations

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

    # Cloud file operations

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

    # Play queue operations

    # Album operations

    # Genre operations

    # Artist operations

    # === Albums Incremental Updates ===

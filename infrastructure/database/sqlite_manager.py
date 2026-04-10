"""
Database manager for the music player using SQLite.
"""
import atexit
import logging
import re
import sqlite3
import threading
from concurrent.futures import Future
from typing import Callable, Dict, Optional

from infrastructure.database.db_write_worker import get_write_worker

# Configure logging
logger = logging.getLogger(__name__)

_FTS_BOOLEAN_OPERATORS = re.compile(r"\b(?:AND|OR|NOT)\b", re.IGNORECASE)
_FTS_FIELD_SPECIFIERS = re.compile(r"\b(?:title|artist|album)\s*:", re.IGNORECASE)
_FTS_UNSAFE_CHARACTERS = re.compile(r"[^\w\s.-]+", re.UNICODE)


class DatabaseManager:
    """Manages SQLite database operations for the music player."""

    @staticmethod
    def _enable_wal_mode(conn: sqlite3.Connection) -> None:
        """Enable WAL mode and warn if SQLite keeps a different journal mode."""
        row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
        journal_mode = str(row[0]).lower() if row else ""
        if journal_mode != "wal":
            logger.warning("[DatabaseManager] WAL mode was not applied; current journal_mode=%s", journal_mode or "unknown")

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
            self._enable_wal_mode(self.local.conn)
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
                           online_provider_id
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
                       CREATE INDEX IF NOT EXISTS idx_tracks_path
                           ON tracks(path)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_play_history_track
                           ON play_history(track_id)
                       """)
        cursor.execute("""
                       CREATE INDEX IF NOT EXISTS idx_play_history_played_at
                           ON play_history(played_at DESC)
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
                       CREATE INDEX IF NOT EXISTS idx_cloud_accounts_is_active
                           ON cloud_accounts(is_active)
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

        cursor.execute("""
                       CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_unique
                           ON albums(name, artist)
                       """)
        cursor.execute("""
                       CREATE UNIQUE INDEX IF NOT EXISTS idx_artists_unique
                           ON artists(name)
                       """)
        cursor.execute("""
                       CREATE UNIQUE INDEX IF NOT EXISTS idx_genres_unique
                           ON genres(name)
                       """)

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

    def _run_migrations(self, conn, cursor):
        """Run database migrations for schema updates."""
        # Current schema version - increment when making schema changes
        CURRENT_SCHEMA_VERSION = 12

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
        if 'online_provider_id' not in columns:
            cursor.execute("ALTER TABLE favorites ADD COLUMN online_provider_id TEXT")

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
                               online_provider_id
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
                           )
                               )
                           """)
            cursor.execute("""
                           INSERT INTO favorites_new (
                               id, track_id, cloud_file_id, online_provider_id, cloud_account_id, created_at
                           )
                           SELECT id, track_id, cloud_file_id, online_provider_id, cloud_account_id, created_at
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
                    ON favorites(cloud_file_id, COALESCE(online_provider_id, ''))
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

        # Migration 11: Make online favorites provider-aware.
        if stored_version < 12:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS favorites_new
                (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    track_id INTEGER,
                    cloud_file_id TEXT,
                    online_provider_id TEXT,
                    cloud_account_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(track_id) REFERENCES tracks(id) ON DELETE CASCADE,
                    FOREIGN KEY(cloud_account_id) REFERENCES cloud_accounts(id) ON DELETE CASCADE
                )
            """)
            cursor.execute("""
                INSERT INTO favorites_new (
                    id, track_id, cloud_file_id, online_provider_id, cloud_account_id, created_at
                )
                SELECT
                    id,
                    track_id,
                    cloud_file_id,
                    online_provider_id,
                    cloud_account_id,
                    created_at
                FROM favorites
            """)
            cursor.execute("DROP TABLE favorites")
            cursor.execute("ALTER TABLE favorites_new RENAME TO favorites")
            cursor.execute("DROP INDEX IF EXISTS idx_favorites_track_unique")
            cursor.execute("DROP INDEX IF EXISTS idx_favorites_cloud_file_unique")
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_track_unique
                    ON favorites(track_id)
                    WHERE track_id IS NOT NULL
            """)
            cursor.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_favorites_cloud_file_unique
                    ON favorites(cloud_file_id, COALESCE(online_provider_id, ''))
                    WHERE cloud_file_id IS NOT NULL
            """)
            logger.info("[Database] Made online favorites provider-aware")

        # Update schema version after all migrations complete
        if schema_changed:
            cursor.execute(
                "INSERT OR REPLACE INTO db_meta (key, value) VALUES ('schema_version', ?)",
                (str(CURRENT_SCHEMA_VERSION),)
            )
            logger.info(f"[Database] Schema version updated to {CURRENT_SCHEMA_VERSION}")


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

    # Settings operations

    # Play queue operations

    # Album operations

    # Genre operations

    # Artist operations

    # === Albums Incremental Updates ===

"""Migration compatibility tests for DatabaseManager."""

import os
import sqlite3
import tempfile
from unittest.mock import Mock

from infrastructure.database.sqlite_manager import DatabaseManager
import infrastructure.database.sqlite_manager as sqlite_manager_module


def test_init_database_handles_legacy_tracks_without_genre_column():
    """Database init should migrate legacy tracks schema instead of crashing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE tracks (
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
            """
        )
        conn.commit()
        conn.close()

        db = DatabaseManager(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "genre" in columns

        cursor.execute("PRAGMA index_list(tracks)")
        indexes = {row[1] for row in cursor.fetchall()}
        assert "idx_tracks_genre" in indexes
        conn.close()
        db.close()
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_init_database_creates_missing_filter_indexes():
    """Database init should create the still-missing lookup indexes used by filters."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = DatabaseManager(db_path)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA index_list(tracks)")
        track_indexes = {row[1] for row in cursor.fetchall()}
        assert "idx_tracks_path" in track_indexes

        cursor.execute("PRAGMA index_list(cloud_accounts)")
        account_indexes = {row[1] for row in cursor.fetchall()}
        assert "idx_cloud_accounts_is_active" in account_indexes

        conn.close()
        db.close()
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_init_database_migrates_legacy_qq_online_provider_rows():
    """Database init should repair legacy QQ online provider ids in tracks and queue."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE tracks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL DEFAULT 0,
                cover_path TEXT,
                cloud_file_id TEXT,
                source TEXT DEFAULT 'Local',
                online_provider_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
                title, artist, album,
                content='tracks', content_rowid='id'
            )
        """)
        cursor.execute("""
            CREATE TABLE play_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                source TEXT NOT NULL,
                track_id INTEGER,
                cloud_file_id TEXT,
                online_provider_id TEXT,
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
        cursor.execute("""
            CREATE TABLE favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE genres (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                cover_path TEXT,
                song_count INTEGER DEFAULT 0,
                album_count INTEGER DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE play_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                track_id INTEGER
            )
        """)
        cursor.execute("CREATE TABLE db_meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("INSERT INTO db_meta (key, value) VALUES ('schema_version', '10')")
        cursor.execute("""
            INSERT INTO tracks (path, title, cloud_file_id, source, online_provider_id)
            VALUES (?, ?, ?, ?, ?)
        """, ("/music/song.flac", "Legacy QQ", "qq_mid", "QQ", None))
        cursor.execute("""
            INSERT INTO play_queue (position, source, cloud_file_id, online_provider_id, title)
            VALUES (?, ?, ?, ?, ?)
        """, (0, "ONLINE", "qq_mid", "online", "Legacy QQ"))
        conn.commit()
        conn.close()

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        class _CursorProxy:
            def __init__(self, inner):
                self._inner = inner

            def execute(self, sql, params=()):
                normalized = " ".join(sql.split()).lower()
                if normalized.startswith("delete from tracks_fts") or normalized.startswith(
                    "insert into tracks_fts"
                ):
                    return self
                self._inner.execute(sql, params)
                return self

            def fetchone(self):
                return self._inner.fetchone()

            def fetchall(self):
                return self._inner.fetchall()

        cursor_proxy = _CursorProxy(cursor)
        manager = DatabaseManager.__new__(DatabaseManager)
        DatabaseManager._run_migrations(manager, conn, cursor_proxy)
        conn.commit()
        cursor.execute("SELECT source, online_provider_id FROM tracks WHERE cloud_file_id = ?", ("qq_mid",))
        track_row = cursor.fetchone()
        cursor.execute("SELECT online_provider_id FROM play_queue WHERE cloud_file_id = ?", ("qq_mid",))
        queue_row = cursor.fetchone()
        conn.close()

        assert track_row == ("ONLINE", "qqmusic")
        assert queue_row == ("qqmusic",)
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_init_database_does_not_create_track_indexes_twice(monkeypatch):
    """Fresh database init should not emit duplicate CREATE INDEX statements for migrated track columns."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    statements = []
    real_connect = sqlite3.connect

    def _tracking_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    monkeypatch.setattr(sqlite_manager_module, "get_write_worker", lambda _db_path: Mock(stop=Mock()))
    monkeypatch.setattr(sqlite_manager_module.sqlite3, "connect", _tracking_connect)

    try:
        db = DatabaseManager(db_path)
        db.close()
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

    cloud_file_index_statements = [
        statement for statement in statements if "CREATE INDEX IF NOT EXISTS idx_tracks_cloud_file_id" in statement
    ]
    assert len(cloud_file_index_statements) == 1

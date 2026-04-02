"""Migration compatibility tests for DatabaseManager."""

import os
import sqlite3
import tempfile

from infrastructure.database.sqlite_manager import DatabaseManager


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

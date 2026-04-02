"""Tests for SqliteGenreRepository."""

import os
import sqlite3
import tempfile

from repositories.genre_repository import SqliteGenreRepository



def _create_schema(db_path: str) -> None:
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
            genre TEXT,
            duration REAL,
            cover_path TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE genres (
            name TEXT,
            cover_path TEXT,
            song_count INTEGER,
            album_count INTEGER,
            total_duration REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE albums (
            name TEXT,
            artist TEXT,
            cover_path TEXT
        )
        """
    )

    conn.commit()
    conn.close()



def test_get_all_uses_random_track_cover_when_cached_cover_missing():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _create_schema(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT INTO tracks (path, title, artist, album, genre, duration, cover_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("/music/a.mp3", "A", "Artist", "Album 1", "Rock", 180.0, ""),
                ("/music/b.mp3", "B", "Artist", "Album 1", "Rock", 200.0, "/covers/rock1.jpg"),
                ("/music/c.mp3", "C", "Artist", "Album 2", "Rock", 210.0, "/covers/rock2.jpg"),
            ],
        )

        cursor.execute(
            """
            INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
            VALUES ('Rock', NULL, 3, 2, 590.0)
            """
        )

        conn.commit()
        conn.close()

        repo = SqliteGenreRepository(db_path)
        genres = repo.get_all(use_cache=True)

        assert len(genres) == 1
        assert genres[0].cover_path in {"/covers/rock1.jpg", "/covers/rock2.jpg"}
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

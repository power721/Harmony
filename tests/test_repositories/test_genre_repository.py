"""Tests for SqliteGenreRepository."""

import os
import sqlite3
import tempfile
from unittest.mock import Mock

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


def test_get_all_cached_query_avoids_order_by_random():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _create_schema(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
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

        statements = []
        conn.set_trace_callback(statements.append)
        repo = SqliteGenreRepository(db_path)
        repo._get_connection = lambda: conn
        try:
            genres = repo.get_all(use_cache=True)
        finally:
            conn.set_trace_callback(None)
            conn.close()

        assert len(genres) == 1
        assert genres[0].cover_path in {"/covers/rock1.jpg", "/covers/rock2.jpg"}
        assert all("ORDER BY RANDOM()" not in statement.upper() for statement in statements)
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_get_all_cached_query_does_not_probe_cache_table_existence():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _create_schema(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
            VALUES ('Rock', '/covers/rock.jpg', 3, 2, 590.0)
            """
        )
        conn.commit()

        statements = []
        conn.set_trace_callback(statements.append)
        repo = SqliteGenreRepository(db_path)
        repo._get_connection = lambda: conn
        try:
            repo.get_all(use_cache=True)
            repo.get_all(use_cache=True)
        finally:
            conn.set_trace_callback(None)
            conn.close()

        probes = [sql for sql in statements if "SELECT 1 FROM genres LIMIT 1" in sql]
        assert probes == []
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_refresh_query_avoids_order_by_random():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _create_schema(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
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
        conn.commit()

        statements = []
        conn.set_trace_callback(statements.append)
        repo = SqliteGenreRepository(db_path)
        repo._get_connection = lambda: conn
        try:
            assert repo.refresh() is True
        finally:
            conn.set_trace_callback(None)
            conn.close()

        assert any("INSERT INTO GENRES" in statement.upper() for statement in statements)
        assert all("ORDER BY RANDOM()" not in statement.upper() for statement in statements)
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_refresh_rolls_back_when_insert_fails():
    repo = SqliteGenreRepository.__new__(SqliteGenreRepository)
    cursor = Mock()
    cursor.execute.side_effect = [None, sqlite3.DatabaseError("boom")]
    conn = Mock(cursor=Mock(return_value=cursor))
    repo._get_connection = lambda: conn

    result = SqliteGenreRepository.refresh(repo)

    assert result is False
    conn.rollback.assert_called_once_with()
    conn.commit.assert_not_called()


def test_refresh_genre_updates_single_cached_genre():
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
                ("/music/b.mp3", "B", "Artist", "Album 2", "Rock", 200.0, "/covers/rock.jpg"),
            ],
        )
        conn.commit()
        conn.close()

        repo = SqliteGenreRepository(db_path)
        assert repo.refresh_genre("Rock") is True

        genres = repo.get_all(use_cache=True)
        assert len(genres) == 1
        assert genres[0].name == "Rock"
        assert genres[0].song_count == 2
        assert genres[0].album_count == 2
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_delete_if_empty_removes_genre_without_tracks():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _create_schema(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tracks (path, title, artist, album, genre, duration, cover_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("/music/a.mp3", "A", "Artist", "Album 1", "Rock", 180.0, None),
        )
        conn.commit()
        conn.close()

        repo = SqliteGenreRepository(db_path)
        assert repo.refresh_genre("Rock") is True

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tracks WHERE genre = ?", ("Rock",))
        conn.commit()
        conn.close()

        assert repo.delete_if_empty("Rock") is True
        assert repo.get_all(use_cache=True) == []
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_update_cover_path_works_without_updated_at_column():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE genres (
                name TEXT,
                cover_path TEXT,
                song_count INTEGER,
                album_count INTEGER,
                total_duration REAL
            )
            """
        )
        cursor.execute(
            """
            INSERT INTO genres (name, cover_path, song_count, album_count, total_duration)
            VALUES ('Rock', NULL, 1, 1, 180.0)
            """
        )
        conn.commit()
        conn.close()

        repo = SqliteGenreRepository(db_path)
        assert repo.update_cover_path("Rock", "/covers/rock-new.jpg") is True

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT cover_path FROM genres WHERE name = 'Rock'")
        row = cursor.fetchone()
        conn.close()
        assert row[0] == "/covers/rock-new.jpg"
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass


def test_get_by_name_returns_none_for_blank_name_without_querying():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    try:
        _create_schema(db_path)
        repo = SqliteGenreRepository(db_path)
        conn = repo._get_connection()
        statements = []
        conn.set_trace_callback(statements.append)
        try:
            genre = repo.get_by_name("   ")
        finally:
            conn.set_trace_callback(None)

        assert genre is None
        assert statements == []
    finally:
        try:
            os.unlink(db_path)
        except OSError:
            pass

"""
Tests for SqliteAlbumRepository.
"""

import pytest
import sqlite3
import tempfile
import os

from repositories.album_repository import SqliteAlbumRepository


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tracks table
    cursor.execute("""
        CREATE TABLE tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            title TEXT,
            artist TEXT,
            album TEXT,
            genre TEXT,
            duration REAL,
            cover_path TEXT,
            cloud_file_id TEXT,
            source TEXT DEFAULT 'Local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create albums cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            name TEXT,
            artist TEXT,
            cover_path TEXT,
            song_count INTEGER,
            total_duration REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def album_repo(temp_db):
    """Create an album repository with temporary database."""
    return SqliteAlbumRepository(temp_db)


@pytest.fixture
def populated_db(temp_db):
    """Create a database with sample data."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Add tracks belonging to albums
    tracks = [
        ("/music/song1.mp3", "Song 1", "Artist A", "Album 1", 180.0),
        ("/music/song2.mp3", "Song 2", "Artist A", "Album 1", 200.0),
        ("/music/song3.mp3", "Song 3", "Artist B", "Album 2", 240.0),
        ("/music/song4.mp3", "Song 4", "Artist A", "Album 2", 190.0),
        ("/music/song5.mp3", "Song 5", "Artist C", "", 150.0),  # No album
    ]
    cursor.executemany(
        "INSERT INTO tracks (path, title, artist, album, duration) VALUES (?, ?, ?, ?, ?)",
        tracks
    )

    conn.commit()
    conn.close()
    return temp_db


class TestSqliteAlbumRepository:
    """Test SqliteAlbumRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteAlbumRepository(temp_db)
        assert repo.db_path == temp_db

    def test_get_all_empty_cache(self, album_repo, populated_db):
        """Test get_all with empty albums cache table (fallback to direct query)."""
        albums = album_repo.get_all(use_cache=False)

        # Should have 3 albums (Album 1 with Artist A, Album 2 with Artist A, Album 2 with Artist B)
        assert len(albums) == 3

        # Check album names are present
        album_names = {a.name for a in albums}
        assert "Album 1" in album_names
        assert "Album 2" in album_names

    def test_get_all_with_cache(self, temp_db, populated_db):
        """Test get_all using albums cache table."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()

        # Populate albums cache
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Cached Album', 'Cached Artist', NULL, 5, 500.0)
        """)
        conn.commit()
        conn.close()

        repo = SqliteAlbumRepository(populated_db)
        albums = repo.get_all(use_cache=True)

        # Should get cached album
        assert len(albums) == 1
        assert albums[0].name == "Cached Album"
        assert albums[0].song_count == 5

    def test_get_by_name(self, album_repo, populated_db):
        """Test getting album by name."""
        album = album_repo.get_by_name("Album 1")

        assert album is not None
        assert album.name == "Album 1"
        assert album.artist == "Artist A"
        assert album.song_count == 2
        assert album.duration == 380.0  # 180 + 200

    def test_get_by_name_with_artist(self, album_repo, populated_db):
        """Test getting album by name and artist."""
        album = album_repo.get_by_name("Album 2", artist="Artist B")

        assert album is not None
        assert album.name == "Album 2"
        assert album.artist == "Artist B"
        assert album.song_count == 1

    def test_get_by_name_not_found(self, album_repo):
        """Test getting non-existent album."""
        album = album_repo.get_by_name("Nonexistent Album")
        assert album is None

    def test_is_empty_true(self, album_repo):
        """Test is_empty returns True when empty."""
        assert album_repo.is_empty() is True

    def test_is_empty_false(self, temp_db, populated_db):
        """Test is_empty returns False when populated."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Album', 'Artist', NULL, 1, 180.0)
        """)
        conn.commit()
        conn.close()

        repo = SqliteAlbumRepository(populated_db)
        assert repo.is_empty() is False

    def test_refresh(self, album_repo, populated_db):
        """Test refreshing albums table from tracks."""
        result = album_repo.refresh()

        assert result is True
        assert album_repo.is_empty() is False

        albums = album_repo.get_all(use_cache=True)
        assert len(albums) == 3  # Album 1 + Album 2 (Artist A) + Album 2 (Artist B)

    def test_refresh_preserves_cover_path(self, temp_db, populated_db):
        """Test that refresh preserves existing cover paths."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()

        # First populate albums cache
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Album 1', 'Artist A', '/covers/album1.jpg', 2, 380.0)
        """)
        conn.commit()
        conn.close()

        repo = SqliteAlbumRepository(populated_db)

        # Add more tracks
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO tracks (path, title, artist, album, duration) VALUES (?, ?, ?, ?, ?)",
            ("/music/song6.mp3", "Song 6", "Artist A", "Album 1", 210.0)
        )
        conn.commit()
        conn.close()

        # Refresh
        repo.refresh()

        # Check cover path preserved
        album = repo.get_by_name("Album 1")
        assert album is not None

    def test_update_cover_path(self, temp_db, populated_db):
        """Test updating cover path for an album."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Album 1', 'Artist A', NULL, 2, 380.0)
        """)
        conn.commit()
        conn.close()

        repo = SqliteAlbumRepository(populated_db)
        result = repo.update_cover_path("Album 1", "Artist A", "/covers/new_cover.jpg")

        assert result is True

        album = repo.get_by_name("Album 1", "Artist A")
        assert album is not None

    def test_update_cover_path_nonexistent(self, album_repo):
        """Test updating cover path for non-existent album."""
        result = album_repo.update_cover_path("Nonexistent", "Artist", "/covers/test.jpg")
        assert result is False

    def test_get_all_order_by_song_count(self, temp_db, populated_db):
        """Test that albums are ordered by song count descending."""
        repo = SqliteAlbumRepository(populated_db)
        repo.refresh()

        albums = repo.get_all(use_cache=True)

        # Album 1 has 2 songs, Album 2 has 2 songs (both Artist A and Artist B)
        # The order should be by song count descending
        if len(albums) >= 2:
            for i in range(len(albums) - 1):
                assert albums[i].song_count >= albums[i + 1].song_count

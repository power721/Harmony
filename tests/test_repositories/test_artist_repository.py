"""
Tests for SqliteArtistRepository.
"""

import pytest
import sqlite3
import tempfile
import os

from repositories.artist_repository import SqliteArtistRepository
from domain.artist import Artist


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
            duration REAL,
            cover_path TEXT,
            cloud_file_id TEXT,
            source TEXT DEFAULT 'Local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create artists cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            name TEXT PRIMARY KEY,
            cover_path TEXT,
            song_count INTEGER,
            album_count INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            normalized_name TEXT
        )
    """)

    # Create albums cache table (for rebuild_with_albums)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            name TEXT,
            artist TEXT,
            cover_path TEXT,
            song_count INTEGER,
            total_duration REAL
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
def artist_repo(temp_db):
    """Create an artist repository with temporary database."""
    return SqliteArtistRepository(temp_db)


@pytest.fixture
def populated_db(temp_db):
    """Create a database with sample data."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Add tracks with different artists
    tracks = [
        ("/music/song1.mp3", "Song 1", "Artist A", "Album 1", 180.0),
        ("/music/song2.mp3", "Song 2", "Artist A", "Album 2", 200.0),
        ("/music/song3.mp3", "Song 3", "Artist A", "Album 1", 240.0),  # Same album as song1
        ("/music/song4.mp3", "Song 4", "Artist B", "Album 3", 190.0),
        ("/music/song5.mp3", "Song 5", "Artist B", "Album 3", 150.0),  # Same album
        ("/music/song6.mp3", "Song 6", "", "Album 4", 160.0),  # No artist
    ]
    cursor.executemany(
        "INSERT INTO tracks (path, title, artist, album, duration) VALUES (?, ?, ?, ?, ?)",
        tracks
    )

    conn.commit()
    conn.close()
    return temp_db


class TestSqliteArtistRepository:
    """Test SqliteArtistRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteArtistRepository(temp_db)
        assert repo.db_path == temp_db

    def test_get_all_empty_cache(self, artist_repo, populated_db):
        """Test get_all with empty artists cache table (fallback to direct query)."""
        artists = artist_repo.get_all(use_cache=False)

        # Should have 2 artists (Artist A and Artist B)
        assert len(artists) == 2

        # Check artist names
        artist_names = {a.name for a in artists}
        assert "Artist A" in artist_names
        assert "Artist B" in artist_names

    def test_get_all_with_cache(self, temp_db, populated_db):
        """Test get_all using artists cache table."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()

        # Populate artists cache
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count)
            VALUES ('Cached Artist', '/covers/artist.jpg', 10, 3)
        """)
        conn.commit()
        conn.close()

        repo = SqliteArtistRepository(populated_db)
        artists = repo.get_all(use_cache=True)

        # Should get cached artist
        assert len(artists) == 1
        assert artists[0].name == "Cached Artist"
        assert artists[0].song_count == 10
        assert artists[0].album_count == 3

    def test_get_all_order_by_song_count(self, artist_repo, populated_db):
        """Test that artists are ordered by song count descending."""
        artists = artist_repo.get_all(use_cache=False)

        # Artist A has 3 songs, Artist B has 2 songs
        assert len(artists) == 2
        assert artists[0].name == "Artist A"  # 3 songs
        assert artists[0].song_count == 3
        assert artists[1].name == "Artist B"  # 2 songs
        assert artists[1].song_count == 2

    def test_get_by_name(self, artist_repo, populated_db):
        """Test getting artist by name."""
        artist = artist_repo.get_by_name("Artist A")

        assert artist is not None
        assert artist.name == "Artist A"
        assert artist.song_count == 3
        assert artist.album_count == 2  # Album 1 and Album 2

    def test_get_by_name_not_found(self, artist_repo):
        """Test getting non-existent artist."""
        artist = artist_repo.get_by_name("Nonexistent Artist")
        assert artist is None

    def test_is_empty_true(self, artist_repo):
        """Test is_empty returns True when empty."""
        assert artist_repo.is_empty() is True

    def test_is_empty_false(self, temp_db, populated_db):
        """Test is_empty returns False when populated."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count)
            VALUES ('Artist', '/covers/artist.jpg', 1, 1)
        """)
        conn.commit()
        conn.close()

        repo = SqliteArtistRepository(populated_db)
        assert repo.is_empty() is False

    def test_refresh(self, artist_repo, populated_db):
        """Test refreshing artists table from tracks."""
        result = artist_repo.refresh()

        assert result is True
        assert artist_repo.is_empty() is False

        artists = artist_repo.get_all(use_cache=True)
        assert len(artists) == 2

    def test_update_cover_path(self, temp_db, populated_db):
        """Test updating cover path for an artist."""
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count)
            VALUES ('Artist A', NULL, 3, 2)
        """)
        conn.commit()
        conn.close()

        repo = SqliteArtistRepository(populated_db)
        result = repo.update_cover_path("Artist A", "/covers/new_cover.jpg")

        assert result is True

    def test_update_cover_path_nonexistent(self, artist_repo):
        """Test updating cover path for non-existent artist."""
        result = artist_repo.update_cover_path("Nonexistent", "/covers/test.jpg")
        assert result is False

    def test_rebuild_with_albums(self, temp_db, populated_db):
        """Test rebuilding both artists and albums tables."""
        repo = SqliteArtistRepository(populated_db)
        count = repo.rebuild_with_albums()

        # Should return total count of albums + artists
        assert count > 0

        # Check artists are populated
        artists = repo.get_all(use_cache=True)
        assert len(artists) == 2

        # Check albums are populated (via album repo)
        from repositories.album_repository import SqliteAlbumRepository
        album_repo = SqliteAlbumRepository(populated_db)
        albums = album_repo.get_all(use_cache=True)
        assert len(albums) >= 2  # At least Album 1, 2, 3

    def test_get_all_album_count(self, artist_repo, populated_db):
        """Test that album_count is correctly calculated."""
        artists = artist_repo.get_all(use_cache=False)

        artist_a = next((a for a in artists if a.name == "Artist A"), None)
        assert artist_a is not None
        assert artist_a.album_count == 2  # Album 1 and Album 2

        artist_b = next((a for a in artists if a.name == "Artist B"), None)
        assert artist_b is not None
        assert artist_b.album_count == 1  # Only Album 3

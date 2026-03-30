"""
Tests for SqliteFavoriteRepository.
"""

import pytest
import sqlite3
import tempfile
import os

from repositories.favorite_repository import SqliteFavoriteRepository
from repositories.track_repository import SqliteTrackRepository
from domain.track import Track


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

    # Create favorites table
    cursor.execute("""
        CREATE TABLE favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER,
            cloud_file_id TEXT,
            cloud_account_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (track_id) REFERENCES tracks(id)
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
def favorite_repo(temp_db):
    """Create a favorite repository with temporary database."""
    return SqliteFavoriteRepository(temp_db)


@pytest.fixture
def track_repo(temp_db):
    """Create a track repository with temporary database."""
    return SqliteTrackRepository(temp_db)


@pytest.fixture
def populated_db(temp_db):
    """Create a database with sample tracks."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    # Add sample tracks
    tracks = [
        ("/music/song1.mp3", "Song 1", "Artist A", "Album 1", 180.0),
        ("/music/song2.mp3", "Song 2", "Artist B", "Album 2", 200.0),
        ("/music/song3.mp3", "Song 3", "Artist C", "Album 3", 240.0),
    ]
    cursor.executemany(
        "INSERT INTO tracks (path, title, artist, album, duration) VALUES (?, ?, ?, ?, ?)",
        tracks
    )

    conn.commit()
    conn.close()
    return temp_db


class TestSqliteFavoriteRepository:
    """Test SqliteFavoriteRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteFavoriteRepository(temp_db)
        assert repo.db_path == temp_db

    # ===== is_favorite Tests =====

    def test_is_favorite_local_track_false(self, favorite_repo):
        """Test is_favorite returns False for non-favorited track."""
        result = favorite_repo.is_favorite(track_id=1)
        assert result is False

    def test_is_favorite_cloud_file_false(self, favorite_repo):
        """Test is_favorite returns False for non-favorited cloud file."""
        result = favorite_repo.is_favorite(cloud_file_id="cloud_123")
        assert result is False

    def test_is_favorite_no_params(self, favorite_repo):
        """Test is_favorite with no parameters returns False."""
        result = favorite_repo.is_favorite()
        assert result is False

    # ===== add_favorite Tests =====

    def test_add_favorite_local_track(self, favorite_repo, populated_db):
        """Test adding local track to favorites."""
        result = favorite_repo.add_favorite(track_id=1)
        assert result is True

        # Verify it's favorited
        assert favorite_repo.is_favorite(track_id=1) is True

    def test_add_favorite_cloud_file(self, favorite_repo):
        """Test adding cloud file to favorites."""
        result = favorite_repo.add_favorite(
            cloud_file_id="cloud_123",
            cloud_account_id=1
        )
        assert result is True

        # Verify it's favorited
        assert favorite_repo.is_favorite(cloud_file_id="cloud_123") is True

    def test_add_favorite_no_params(self, favorite_repo):
        """Test adding favorite with no parameters returns False."""
        result = favorite_repo.add_favorite()
        assert result is False

    def test_add_favorite_duplicate(self, favorite_repo, populated_db):
        """Test adding duplicate favorite returns False."""
        favorite_repo.add_favorite(track_id=1)

        # Try to add again
        result = favorite_repo.add_favorite(track_id=1)
        assert result is False

    # ===== remove_favorite Tests =====

    def test_remove_favorite_local_track(self, favorite_repo, populated_db):
        """Test removing local track from favorites."""
        favorite_repo.add_favorite(track_id=1)

        result = favorite_repo.remove_favorite(track_id=1)
        assert result is True

        # Verify it's removed
        assert favorite_repo.is_favorite(track_id=1) is False

    def test_remove_favorite_cloud_file(self, favorite_repo):
        """Test removing cloud file from favorites."""
        favorite_repo.add_favorite(cloud_file_id="cloud_123")

        result = favorite_repo.remove_favorite(cloud_file_id="cloud_123")
        assert result is True

    def test_remove_favorite_not_found(self, favorite_repo):
        """Test removing non-existent favorite returns False."""
        result = favorite_repo.remove_favorite(track_id=999)
        assert result is False

    def test_remove_favorite_no_params(self, favorite_repo):
        """Test removing favorite with no parameters returns False."""
        result = favorite_repo.remove_favorite()
        assert result is False

    # ===== get_all_favorite_track_ids Tests =====

    def test_get_all_favorite_track_ids(self, favorite_repo, populated_db):
        """Test getting all favorite track IDs."""
        favorite_repo.add_favorite(track_id=1)
        favorite_repo.add_favorite(track_id=2)

        ids = favorite_repo.get_all_favorite_track_ids()
        assert ids == {1, 2}

    def test_get_all_favorite_track_ids_empty(self, favorite_repo):
        """Test getting favorite IDs when empty."""
        ids = favorite_repo.get_all_favorite_track_ids()
        assert ids == set()

    def test_get_all_favorite_track_ids_excludes_cloud(self, favorite_repo, populated_db):
        """Test that cloud file favorites are not included."""
        favorite_repo.add_favorite(track_id=1)
        favorite_repo.add_favorite(cloud_file_id="cloud_123")

        ids = favorite_repo.get_all_favorite_track_ids()
        assert ids == {1}

    # ===== get_favorites Tests =====

    def test_get_favorites(self, favorite_repo, populated_db, track_repo):
        """Test getting all favorite tracks."""
        favorite_repo.add_favorite(track_id=1)
        favorite_repo.add_favorite(track_id=2)

        favorites = favorite_repo.get_favorites()
        assert len(favorites) == 2

        # Verify track data
        track_ids = {t.id for t in favorites}
        assert track_ids == {1, 2}

    def test_get_favorites_empty(self, favorite_repo):
        """Test getting favorites when empty."""
        favorites = favorite_repo.get_favorites()
        assert favorites == []

    # ===== get_favorites_with_cloud Tests =====

    def test_get_favorites_with_cloud(self, favorite_repo, populated_db):
        """Test getting favorites including cloud files."""
        favorite_repo.add_favorite(track_id=1)
        favorite_repo.add_favorite(cloud_file_id="cloud_123", cloud_account_id=1)

        favorites = favorite_repo.get_favorites_with_cloud()
        assert len(favorites) == 2

    def test_get_favorites_with_cloud_empty(self, favorite_repo):
        """Test getting favorites with cloud when empty."""
        favorites = favorite_repo.get_favorites_with_cloud()
        assert favorites == []

    def test_get_favorites_order(self, favorite_repo, populated_db):
        """Test that favorites are ordered by id DESC (most recent first)."""
        favorite_repo.add_favorite(track_id=1)
        favorite_repo.add_favorite(track_id=2)
        favorite_repo.add_favorite(track_id=3)

        favorites = favorite_repo.get_favorites()
        assert len(favorites) == 3
        # Most recently added should be first
        assert favorites[0].id == 3
        assert favorites[1].id == 2
        assert favorites[2].id == 1

"""
Tests for SqliteHistoryRepository.
"""

import pytest
import sqlite3
import tempfile
import os
import time
from unittest.mock import Mock

from repositories.history_repository import SqliteHistoryRepository
from domain.history import PlayHistory
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

    # Create play_history table
    cursor.execute("""
        CREATE TABLE play_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            track_id INTEGER NOT NULL,
            played_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            play_count INTEGER DEFAULT 1,
            FOREIGN KEY (track_id) REFERENCES tracks(id)
        )
    """)

    # Create unique index for UPSERT support
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_play_history_track_unique
            ON play_history(track_id)
    """)

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except Exception:
        pass


@pytest.fixture
def history_repo(temp_db):
    """Create a history repository with temporary database."""
    return SqliteHistoryRepository(temp_db)


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
        ("/music/song4.mp3", "Song 4", "Artist D", "Album 4", 190.0),
    ]
    cursor.executemany(
        "INSERT INTO tracks (path, title, artist, album, duration) VALUES (?, ?, ?, ?, ?)",
        tracks
    )

    conn.commit()
    conn.close()
    return temp_db


class TestSqliteHistoryRepository:
    """Test SqliteHistoryRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteHistoryRepository(temp_db)
        assert repo.db_path == temp_db

    # ===== add Tests =====

    def test_add(self, history_repo, populated_db):
        """Test adding play history entry."""
        result = history_repo.add(track_id=1)
        assert result is True

    def test_add_updates_timestamp(self, history_repo, populated_db):
        """Test that adding existing track updates timestamp."""
        history_repo.add(track_id=1)
        time.sleep(0.1)  # Small delay
        history_repo.add(track_id=1)

        # Should only have one entry
        history = history_repo.get_recent(limit=10)
        assert len(history) == 1
        assert history[0].play_count == 2

    def test_add_increments_play_count(self, history_repo, populated_db):
        """Replaying the same track should increment play_count instead of replacing it."""
        history_repo.add(track_id=1)
        history_repo.add(track_id=1)
        history_repo.add(track_id=1)

        history = history_repo.get_recent(limit=10)

        assert len(history) == 1
        assert history[0].play_count == 3

    def test_add_rolls_back_when_upsert_fails(self):
        repo = SqliteHistoryRepository.__new__(SqliteHistoryRepository)
        cursor = Mock()
        cursor.execute.side_effect = sqlite3.DatabaseError("boom")
        conn = Mock(cursor=Mock(return_value=cursor))
        repo._get_connection = lambda: conn

        result = SqliteHistoryRepository.add(repo, 1)

        assert result is False
        conn.rollback.assert_called_once_with()
        conn.commit.assert_not_called()

    # ===== get_recent Tests =====

    def test_get_recent(self, history_repo, populated_db):
        """Test getting recent play history."""
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)
        history_repo.add(track_id=3)

        history = history_repo.get_recent(limit=10)
        assert len(history) == 3

    def test_get_recent_limit(self, history_repo, populated_db):
        """Test get_recent respects limit."""
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)
        history_repo.add(track_id=3)

        history = history_repo.get_recent(limit=2)
        assert len(history) == 2

    def test_get_recent_empty(self, history_repo):
        """Test getting recent history when empty."""
        history = history_repo.get_recent()
        assert history == []

    def test_get_recent_order(self, history_repo, populated_db):
        """Test that history is ordered by most recently played."""
        # Add in order: 1, 2, 3 - when we re-add, the timestamp updates
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)
        history_repo.add(track_id=3)

        # Now re-add track 1 to make it most recent
        time.sleep(0.1)
        history_repo.add(track_id=1)

        history = history_repo.get_recent()
        assert len(history) == 3
        # Track 1 was just re-added, so it should be first
        assert history[0].track_id == 1

    def test_get_recent_returns_play_history(self, history_repo, populated_db):
        """Test that get_recent returns PlayHistory objects."""
        history_repo.add(track_id=1)

        history = history_repo.get_recent()
        assert len(history) == 1
        assert isinstance(history[0], PlayHistory)
        assert history[0].track_id == 1
        assert history[0].id is not None
        assert history[0].played_at is not None
        assert history[0].play_count == 1

    # ===== get_recent_tracks Tests =====

    def test_get_recent_tracks(self, history_repo, populated_db):
        """Test getting recent tracks."""
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)

        tracks = history_repo.get_recent_tracks(limit=10)
        assert len(tracks) == 2

    def test_get_recent_tracks_returns_track_objects(self, history_repo, populated_db):
        """Test that get_recent_tracks returns Track objects."""
        history_repo.add(track_id=1)

        tracks = history_repo.get_recent_tracks()
        assert len(tracks) == 1
        assert isinstance(tracks[0], Track)
        assert tracks[0].title == "Song 1"

    def test_get_recent_tracks_limit(self, history_repo, populated_db):
        """Test get_recent_tracks respects limit."""
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)
        history_repo.add(track_id=3)

        tracks = history_repo.get_recent_tracks(limit=2)
        assert len(tracks) == 2

    def test_get_recent_tracks_order(self, history_repo, populated_db):
        """Test that tracks are ordered by most recently played."""
        # Add in order: 1, 2, 3
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)
        history_repo.add(track_id=3)

        # Now re-add track 1 to make it most recent
        time.sleep(0.1)
        history_repo.add(track_id=1)

        tracks = history_repo.get_recent_tracks()
        assert len(tracks) == 3
        # Track 1 was just re-added, so it should be first
        assert tracks[0].title == "Song 1"

    def test_get_recent_tracks_empty(self, history_repo):
        """Test getting recent tracks when empty."""
        tracks = history_repo.get_recent_tracks()
        assert tracks == []

    def test_get_most_played_orders_by_play_count(self, history_repo, populated_db):
        """Most played query should rank tracks by accumulated play_count."""
        history_repo.add(track_id=2)
        history_repo.add(track_id=1)
        history_repo.add(track_id=1)
        history_repo.add(track_id=3)
        history_repo.add(track_id=1)
        history_repo.add(track_id=2)

        tracks = history_repo.get_most_played(limit=10)

        assert [track.title for track in tracks[:3]] == ["Song 1", "Song 2", "Song 3"]

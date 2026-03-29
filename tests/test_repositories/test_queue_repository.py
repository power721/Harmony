"""
Tests for SqliteQueueRepository.
"""

import pytest
import sqlite3
import tempfile
import os

from repositories.queue_repository import SqliteQueueRepository
from domain.playback import PlayQueueItem


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create play_queue table with new schema
    cursor.execute("""
        CREATE TABLE play_queue (
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

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def queue_repo(temp_db):
    """Create a queue repository with temporary database."""
    return SqliteQueueRepository(temp_db)


class TestSqliteQueueRepository:
    """Test SqliteQueueRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteQueueRepository(temp_db)
        assert repo.db_path == temp_db

    def test_save_and_load_queue(self, queue_repo):
        """Test saving and loading queue."""
        items = [
            PlayQueueItem(
                position=0,
                source="Local",
                track_id=1,
                title="Song 1",
                artist="Artist 1"
            ),
            PlayQueueItem(
                position=1,
                source="Local",
                track_id=2,
                title="Song 2",
                artist="Artist 2"
            )
        ]

        # Save queue
        result = queue_repo.save(items)
        assert result is True

        # Load queue
        loaded = queue_repo.load()
        assert len(loaded) == 2
        assert loaded[0].title == "Song 1"
        assert loaded[1].title == "Song 2"

    def test_load_empty_queue(self, queue_repo):
        """Test loading from empty queue."""
        loaded = queue_repo.load()
        assert len(loaded) == 0

    def test_clear_queue(self, queue_repo):
        """Test clearing the queue."""
        # Add items
        items = [
            PlayQueueItem(position=0, source="Local", track_id=1)
        ]
        queue_repo.save(items)

        # Clear queue
        result = queue_repo.clear()
        assert result is True

        # Verify empty
        loaded = queue_repo.load()
        assert len(loaded) == 0

    def test_save_overwrites_existing(self, queue_repo):
        """Test that save overwrites existing queue."""
        # Save initial queue
        items1 = [
            PlayQueueItem(position=0, source="Local", track_id=1, title="Song 1")
        ]
        queue_repo.save(items1)

        # Save new queue
        items2 = [
            PlayQueueItem(position=0, source="Local", track_id=2, title="Song 2"),
            PlayQueueItem(position=1, source="Local", track_id=3, title="Song 3")
        ]
        queue_repo.save(items2)

        # Verify only new items exist
        loaded = queue_repo.load()
        assert len(loaded) == 2
        assert loaded[0].title == "Song 2"
        assert loaded[1].title == "Song 3"

    def test_save_cloud_items(self, queue_repo):
        """Test saving cloud file items."""
        items = [
            PlayQueueItem(
                position=0,
                source="QUARK",
                cloud_file_id="file123",
                cloud_account_id=1,
                local_path="/cache/file123.mp3",
                title="Cloud Song",
                artist="Cloud Artist",
                duration=180.0
            )
        ]

        result = queue_repo.save(items)
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "QUARK"
        assert loaded[0].cloud_file_id == "file123"
        assert loaded[0].title == "Cloud Song"

    def test_save_online_items(self, queue_repo):
        """Test saving online (QQ Music) items."""
        items = [
            PlayQueueItem(
                position=0,
                source="QQ",
                cloud_file_id="song_mid_123",
                title="Online Song",
                artist="Online Artist",
                duration=200.0
            )
        ]

        result = queue_repo.save(items)
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "QQ"
        assert loaded[0].cloud_file_id == "song_mid_123"

    def test_row_to_item_conversion(self, queue_repo):
        """Test conversion from database row to PlayQueueItem."""
        items = [
            PlayQueueItem(
                id=1,
                position=0,
                source="Local",
                track_id=42,
                title="Test Song",
                artist="Test Artist",
                album="Test Album",
                duration=200.0
            )
        ]

        queue_repo.save(items)
        loaded = queue_repo.load()

        assert loaded[0].position == 0
        assert loaded[0].source == "Local"
        assert loaded[0].track_id == 42
        assert loaded[0].title == "Test Song"
        assert loaded[0].artist == "Test Artist"
        assert loaded[0].album == "Test Album"
        assert loaded[0].duration == 200.0

    def test_save_and_load_with_download_failed(self, queue_repo):
        """Test saving and loading queue items with download_failed field."""
        items = [
            PlayQueueItem(
                position=0, source="Local", track_id=1,
                local_path="/music/song.mp3", title="Local Song",
            ),
            PlayQueueItem(
                position=1, source="QUARK", cloud_file_id="quark_123",
                cloud_account_id=1, local_path="", title="Cloud Song",
                download_failed=True,
            ),
        ]
        assert queue_repo.save(items) is True

        loaded = queue_repo.load()
        assert len(loaded) == 2
        assert loaded[0].download_failed is False
        assert loaded[1].download_failed is True

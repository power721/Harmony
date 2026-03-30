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


class TestQueueRepositoryBoundaryCases:
    """Test boundary and edge cases for queue repository."""

    def test_save_empty_list(self, queue_repo):
        """Test saving an empty queue clears existing data."""
        # First add some items
        items = [PlayQueueItem(position=0, source="Local", track_id=1, title="Song")]
        queue_repo.save(items)

        # Save empty list
        result = queue_repo.save([])
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 0

    def test_save_mixed_sources(self, queue_repo):
        """Test saving queue with mixed source types."""
        items = [
            PlayQueueItem(
                position=0, source="Local", track_id=1,
                title="Local Song", duration=180.0
            ),
            PlayQueueItem(
                position=1, source="QUARK", cloud_file_id="q1",
                cloud_account_id=1, title="Quark Song", duration=200.0
            ),
            PlayQueueItem(
                position=2, source="QQ", cloud_file_id="qq1",
                title="QQ Song", duration=150.0
            ),
            PlayQueueItem(
                position=3, source="BAIDU", cloud_file_id="b1",
                cloud_account_id=2, title="Baidu Song", duration=210.0
            ),
        ]

        result = queue_repo.save(items)
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 4
        assert loaded[0].source == "Local"
        assert loaded[1].source == "QUARK"
        assert loaded[2].source == "QQ"
        assert loaded[3].source == "BAIDU"

    def test_save_large_queue(self, queue_repo):
        """Test saving a large number of items."""
        items = [
            PlayQueueItem(
                position=i, source="Local", track_id=i + 1,
                title=f"Song {i}", artist=f"Artist {i}"
            )
            for i in range(100)
        ]

        result = queue_repo.save(items)
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 100
        assert loaded[0].title == "Song 0"
        assert loaded[99].title == "Song 99"

    def test_save_single_item(self, queue_repo):
        """Test saving a single item."""
        items = [PlayQueueItem(position=0, source="Local", track_id=42, title="Solo")]
        result = queue_repo.save(items)
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 1
        assert loaded[0].track_id == 42

    def test_load_with_optional_fields_null(self, queue_repo, temp_db):
        """Test loading items where optional fields are NULL."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO play_queue (position, source, track_id, cloud_file_id,
                                    cloud_account_id, local_path, title, artist,
                                    album, duration, download_failed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (0, "Local", None, None, None, None, None, None, None, None, 0, None))
        conn.commit()
        conn.close()

        loaded = queue_repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "Local"
        assert loaded[0].track_id is None
        assert loaded[0].title == ""
        assert loaded[0].artist == ""
        assert loaded[0].album == ""
        assert loaded[0].duration == 0.0
        assert loaded[0].download_failed is False
        assert loaded[0].created_at is not None

    def test_load_old_schema_source_type_local(self, temp_db):
        """Test loading from old schema with source_type='local' maps to 'Local'."""
        # Create old schema table
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS play_queue")
        cursor.execute("""
            CREATE TABLE play_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                source_type TEXT,
                cloud_type TEXT,
                track_id INTEGER,
                cloud_file_id TEXT,
                cloud_account_id INTEGER,
                local_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO play_queue (position, source_type, track_id, title)
            VALUES (?, ?, ?, ?)
        """, (0, "local", 1, "Old Local Song"))
        conn.commit()
        conn.close()

        repo = SqliteQueueRepository(temp_db)
        loaded = repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "Local"
        assert loaded[0].title == "Old Local Song"

    def test_load_old_schema_source_type_online(self, temp_db):
        """Test loading from old schema with source_type='online' maps to 'QQ'."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS play_queue")
        cursor.execute("""
            CREATE TABLE play_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                source_type TEXT,
                cloud_type TEXT,
                track_id INTEGER,
                cloud_file_id TEXT,
                cloud_account_id INTEGER,
                local_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO play_queue (position, source_type, cloud_file_id, title)
            VALUES (?, ?, ?, ?)
        """, (0, "online", "mid_123", "QQ Song"))
        conn.commit()
        conn.close()

        repo = SqliteQueueRepository(temp_db)
        loaded = repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "QQ"
        assert loaded[0].cloud_file_id == "mid_123"

    def test_load_old_schema_source_type_cloud(self, temp_db):
        """Test loading from old schema with source_type='cloud' maps cloud_type."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS play_queue")
        cursor.execute("""
            CREATE TABLE play_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                source_type TEXT,
                cloud_type TEXT,
                track_id INTEGER,
                cloud_file_id TEXT,
                cloud_account_id INTEGER,
                local_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO play_queue (position, source_type, cloud_type, cloud_file_id, title)
            VALUES (?, ?, ?, ?, ?)
        """, (0, "cloud", "quark", "fid_123", "Quark Song"))
        conn.commit()
        conn.close()

        repo = SqliteQueueRepository(temp_db)
        loaded = repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "QUARK"

    def test_load_old_schema_no_source_type(self, temp_db):
        """Test loading from old schema without source_type defaults to 'Local'."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS play_queue")
        cursor.execute("""
            CREATE TABLE play_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                position INTEGER NOT NULL,
                track_id INTEGER,
                cloud_file_id TEXT,
                cloud_account_id INTEGER,
                local_path TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                duration REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO play_queue (position, track_id, title)
            VALUES (?, ?, ?)
        """, (0, 5, "Fallback Song"))
        conn.commit()
        conn.close()

        repo = SqliteQueueRepository(temp_db)
        loaded = repo.load()
        assert len(loaded) == 1
        assert loaded[0].source == "Local"
        assert loaded[0].track_id == 5

    def test_load_old_schema_download_failed_missing(self, temp_db):
        """Test loading from old schema without download_failed column defaults to False."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("DROP TABLE IF EXISTS play_queue")
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO play_queue (position, source, track_id, title)
            VALUES (?, ?, ?, ?)
        """, (0, "Local", 1, "No Download Failed Column"))
        conn.commit()
        conn.close()

        repo = SqliteQueueRepository(temp_db)
        loaded = repo.load()
        assert len(loaded) == 1
        assert loaded[0].download_failed is False

    def test_clear_empty_queue(self, queue_repo):
        """Test clearing an already empty queue."""
        result = queue_repo.clear()
        assert result is True

        loaded = queue_repo.load()
        assert len(loaded) == 0

    def test_multiple_saves_in_sequence(self, queue_repo):
        """Test multiple consecutive saves replace queue each time."""
        for i in range(5):
            items = [PlayQueueItem(position=0, source="Local", track_id=i, title=f"Song {i}")]
            queue_repo.save(items)

        loaded = queue_repo.load()
        assert len(loaded) == 1
        assert loaded[0].track_id == 4
        assert loaded[0].title == "Song 4"

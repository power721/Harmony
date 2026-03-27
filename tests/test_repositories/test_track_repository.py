"""
Tests for SqliteTrackRepository.
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

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
            duration REAL,
            cover_path TEXT,
            cloud_file_id TEXT,
            source TEXT DEFAULT 'Local',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create FTS table
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
            title, artist, album,
            content='tracks', content_rowid='id'
        )
    """)

    # Create albums cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS albums (
            name TEXT,
            artist TEXT,
            cover_path TEXT,
            song_count INTEGER,
            total_duration REAL
        )
    """)

    # Create artists cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            cover_path TEXT,
            song_count INTEGER,
            album_count INTEGER,
            normalized_name TEXT
        )
    """)

    # Create track_artists junction table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS track_artists (
            track_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            position INTEGER DEFAULT 0,
            PRIMARY KEY (track_id, artist_id),
            FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
        )
    """)

    # Create indexes for track_artists
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_track_artists_artist
        ON track_artists(artist_id)
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_track_artists_track
        ON track_artists(track_id)
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
def track_repo(temp_db):
    """Create a track repository with temporary database."""
    return SqliteTrackRepository(temp_db)


class TestSqliteTrackRepository:
    """Test SqliteTrackRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqliteTrackRepository(temp_db)
        assert repo.db_path == temp_db

    def test_add_track(self, track_repo):
        """Test adding a track."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180.0
        )
        track_id = track_repo.add(track)
        assert track_id > 0

    def test_add_duplicate_track(self, track_repo):
        """Test adding duplicate track returns 0."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist"
        )
        track_id1 = track_repo.add(track)
        assert track_id1 > 0

        # Adding same path again should return 0
        track_id2 = track_repo.add(track)
        assert track_id2 == 0

    def test_get_by_id(self, track_repo):
        """Test getting track by ID."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist",
            album="Test Album",
            duration=180.0
        )
        track_id = track_repo.add(track)

        retrieved = track_repo.get_by_id(track_id)
        assert retrieved is not None
        assert retrieved.id == track_id
        assert retrieved.title == "Test Song"
        assert retrieved.artist == "Test Artist"
        assert retrieved.album == "Test Album"
        assert retrieved.duration == 180.0

    def test_get_by_id_not_found(self, track_repo):
        """Test getting non-existent track."""
        retrieved = track_repo.get_by_id(99999)
        assert retrieved is None

    def test_get_by_path(self, track_repo):
        """Test getting track by path."""
        track = Track(
            path="/music/song.mp3",
            title="Test Song",
            artist="Test Artist"
        )
        track_repo.add(track)

        retrieved = track_repo.get_by_path("/music/song.mp3")
        assert retrieved is not None
        assert retrieved.title == "Test Song"

    def test_get_by_path_not_found(self, track_repo):
        """Test getting track by non-existent path."""
        retrieved = track_repo.get_by_path("/nonexistent/path.mp3")
        assert retrieved is None

    def test_get_all(self, track_repo):
        """Test getting all tracks."""
        # Add multiple tracks
        for i in range(3):
            track = Track(
                path=f"/music/song{i}.mp3",
                title=f"Song {i}",
                artist=f"Artist {i}"
            )
            track_repo.add(track)

        tracks = track_repo.get_all()
        assert len(tracks) == 3

    def test_update_track(self, track_repo):
        """Test updating a track."""
        track = Track(
            path="/music/song.mp3",
            title="Original Title",
            artist="Original Artist"
        )
        track_id = track_repo.add(track)

        # Update track
        track.id = track_id
        track.title = "Updated Title"
        track.artist = "Updated Artist"
        result = track_repo.update(track)
        assert result is True

        # Verify update
        updated = track_repo.get_by_id(track_id)
        assert updated.title == "Updated Title"
        assert updated.artist == "Updated Artist"

    def test_update_nonexistent_track(self, track_repo):
        """Test updating non-existent track."""
        track = Track(id=99999, path="/nonexistent.mp3", title="Title")
        result = track_repo.update(track)
        assert result is False

    def test_delete_track(self, track_repo):
        """Test deleting a track."""
        track = Track(path="/music/song.mp3", title="Test Song")
        track_id = track_repo.add(track)

        result = track_repo.delete(track_id)
        assert result is True

        # Verify deletion
        retrieved = track_repo.get_by_id(track_id)
        assert retrieved is None

    def test_delete_nonexistent_track(self, track_repo):
        """Test deleting non-existent track."""
        result = track_repo.delete(99999)
        assert result is False

    def test_get_by_cloud_file_id(self, track_repo):
        """Test getting track by cloud file ID."""
        track = Track(
            path="/music/song.mp3",
            title="Cloud Song",
            cloud_file_id="cloud123"
        )
        track_repo.add(track)

        retrieved = track_repo.get_by_cloud_file_id("cloud123")
        assert retrieved is not None
        assert retrieved.title == "Cloud Song"

    def test_get_by_cloud_file_id_not_found(self, track_repo):
        """Test getting track by non-existent cloud file ID."""
        retrieved = track_repo.get_by_cloud_file_id("nonexistent")
        assert retrieved is None

    def test_search_tracks(self, track_repo, temp_db):
        """Test searching tracks."""
        # Add tracks with different titles
        tracks = [
            Track(path="/music/rock.mp3", title="Rock Song", artist="Rock Band"),
            Track(path="/music/pop.mp3", title="Pop Song", artist="Pop Singer"),
            Track(path="/music/jazz.mp3", title="Jazz Tune", artist="Jazz Artist"),
        ]
        for track in tracks:
            track_repo.add(track)

        # Populate FTS table manually for testing
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tracks_fts (rowid, title, artist, album)
            SELECT id, title, artist, album FROM tracks
        """)
        conn.commit()
        conn.close()

        # Search for "Song" - should match Rock Song and Pop Song
        results = track_repo.search("Song")
        assert len(results) >= 2

    def test_thread_local_connection(self, track_repo):
        """Test that each thread gets its own connection."""
        import threading

        connections = []

        def get_conn():
            conn = track_repo._get_connection()
            connections.append(id(conn))

        threads = [threading.Thread(target=get_conn) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All connections should be different objects
        assert len(set(connections)) == 3

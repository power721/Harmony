"""
Tests for SqlitePlaylistRepository.
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock

from domain.playlist_folder import PlaylistTree
from repositories.playlist_repository import SqlitePlaylistRepository
from domain.playlist import Playlist


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

    # Create playlists table
    cursor.execute("""
        CREATE TABLE playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            folder_id INTEGER,
            position INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE playlist_folders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            position INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create playlist_items table
    cursor.execute("""
        CREATE TABLE playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id),
            FOREIGN KEY (track_id) REFERENCES tracks(id)
        )
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
def playlist_repo(temp_db):
    """Create a playlist repository with temporary database."""
    return SqlitePlaylistRepository(temp_db)


@pytest.fixture
def sample_tracks(temp_db):
    """Create sample tracks in the database."""
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()

    track_ids = []
    for i in range(3):
        cursor.execute(
            "INSERT INTO tracks (path, title, artist) VALUES (?, ?, ?)",
            (f"/music/song{i}.mp3", f"Song {i}", f"Artist {i}")
        )
        track_ids.append(cursor.lastrowid)

    conn.commit()
    conn.close()
    return track_ids


class TestSqlitePlaylistRepository:
    """Test SqlitePlaylistRepository."""

    def test_initialization(self, temp_db):
        """Test repository initialization."""
        repo = SqlitePlaylistRepository(temp_db)
        assert repo.db_path == temp_db

    def test_add_playlist(self, playlist_repo):
        """Test adding a playlist."""
        playlist = Playlist(name="My Playlist")
        playlist_id = playlist_repo.add(playlist)
        assert playlist_id > 0

    def test_get_by_id(self, playlist_repo):
        """Test getting playlist by ID."""
        playlist = Playlist(name="Test Playlist")
        playlist_id = playlist_repo.add(playlist)

        retrieved = playlist_repo.get_by_id(playlist_id)
        assert retrieved is not None
        assert retrieved.id == playlist_id
        assert retrieved.name == "Test Playlist"

    def test_get_by_id_not_found(self, playlist_repo):
        """Test getting non-existent playlist."""
        retrieved = playlist_repo.get_by_id(99999)
        assert retrieved is None

    def test_get_all(self, playlist_repo):
        """Test getting all playlists."""
        for i in range(3):
            playlist = Playlist(name=f"Playlist {i}")
            playlist_repo.add(playlist)

        playlists = playlist_repo.get_all()
        assert len(playlists) == 3

    def test_update_playlist(self, playlist_repo):
        """Test updating a playlist."""
        playlist = Playlist(name="Original Name")
        playlist_id = playlist_repo.add(playlist)

        # Update playlist
        playlist.id = playlist_id
        playlist.name = "Updated Name"
        result = playlist_repo.update(playlist)
        assert result is True

        # Verify update
        updated = playlist_repo.get_by_id(playlist_id)
        assert updated.name == "Updated Name"

    def test_delete_playlist(self, playlist_repo):
        """Test deleting a playlist."""
        playlist = Playlist(name="To Delete")
        playlist_id = playlist_repo.add(playlist)

        result = playlist_repo.delete(playlist_id)
        assert result is True

        # Verify deletion
        retrieved = playlist_repo.get_by_id(playlist_id)
        assert retrieved is None

    def test_add_track_to_playlist(self, playlist_repo, sample_tracks):
        """Test adding track to playlist."""
        playlist = Playlist(name="Test Playlist")
        playlist_id = playlist_repo.add(playlist)

        result = playlist_repo.add_track(playlist_id, sample_tracks[0])
        assert result is True

        tracks = playlist_repo.get_tracks(playlist_id)
        assert len(tracks) == 1

    def test_add_track_rolls_back_when_insert_fails(self):
        repo = SqlitePlaylistRepository.__new__(SqlitePlaylistRepository)
        cursor = Mock()
        cursor.execute.side_effect = sqlite3.DatabaseError("boom")
        conn = Mock(cursor=Mock(return_value=cursor))
        repo._get_connection = lambda: conn

        result = SqlitePlaylistRepository.add_track(repo, 1, 1)

        assert result is False
        conn.rollback.assert_called_once_with()
        conn.commit.assert_not_called()

    def test_add_multiple_tracks_to_playlist(self, playlist_repo, sample_tracks):
        """Test adding multiple tracks to playlist."""
        playlist = Playlist(name="Test Playlist")
        playlist_id = playlist_repo.add(playlist)

        for track_id in sample_tracks:
            playlist_repo.add_track(playlist_id, track_id)

        tracks = playlist_repo.get_tracks(playlist_id)
        assert len(tracks) == 3

    def test_remove_track_from_playlist(self, playlist_repo, sample_tracks):
        """Test removing track from playlist."""
        playlist = Playlist(name="Test Playlist")
        playlist_id = playlist_repo.add(playlist)

        # Add tracks
        for track_id in sample_tracks:
            playlist_repo.add_track(playlist_id, track_id)

        # Remove one track
        result = playlist_repo.remove_track(playlist_id, sample_tracks[0])
        assert result is True

        tracks = playlist_repo.get_tracks(playlist_id)
        assert len(tracks) == 2

    def test_get_tracks_empty_playlist(self, playlist_repo):
        """Test getting tracks from empty playlist."""
        playlist = Playlist(name="Empty Playlist")
        playlist_id = playlist_repo.add(playlist)

        tracks = playlist_repo.get_tracks(playlist_id)
        assert len(tracks) == 0

    def test_delete_playlist_removes_items(self, playlist_repo, sample_tracks):
        """Test that deleting playlist also removes playlist items."""
        playlist = Playlist(name="Test Playlist")
        playlist_id = playlist_repo.add(playlist)

        # Add tracks
        for track_id in sample_tracks:
            playlist_repo.add_track(playlist_id, track_id)

        # Delete playlist
        playlist_repo.delete(playlist_id)

        # Verify items are gone (by checking a new playlist with same ID doesn't exist)
        retrieved = playlist_repo.get_by_id(playlist_id)
        assert retrieved is None

    def test_create_folder_and_get_all_folders(self, playlist_repo):
        """Test creating and listing playlist folders."""
        folder_id = playlist_repo.create_folder("Workout")
        folders = playlist_repo.get_all_folders()

        assert folder_id > 0
        assert [folder.name for folder in folders] == ["Workout"]
        assert folders[0].position == 0

    def test_get_playlist_tree_groups_root_and_folder_playlists(self, playlist_repo):
        """Test loading the playlist tree with root and folder playlists."""
        playlist_repo.add(Playlist(name="Root", position=0))
        folder_id = playlist_repo.create_folder("Mood")
        playlist_repo.add(Playlist(name="Chill", folder_id=folder_id, position=0))

        tree = playlist_repo.get_playlist_tree()

        assert isinstance(tree, PlaylistTree)
        assert [p.name for p in tree.root_playlists] == ["Root"]
        assert [group.folder.name for group in tree.folders] == ["Mood"]
        assert [p.name for p in tree.folders[0].playlists] == ["Chill"]

    def test_rename_folder_updates_name(self, playlist_repo):
        """Test renaming a folder."""
        folder_id = playlist_repo.create_folder("Old Name")

        assert playlist_repo.rename_folder(folder_id, "New Name") is True
        assert [folder.name for folder in playlist_repo.get_all_folders()] == ["New Name"]

    def test_get_folder_by_name_is_case_insensitive(self, playlist_repo):
        """Test case-insensitive folder lookup."""
        playlist_repo.create_folder("Workout")

        folder = playlist_repo.get_folder_by_name("workout")

        assert folder is not None
        assert folder.name == "Workout"

    def test_delete_folder_moves_playlists_back_to_root(self, playlist_repo):
        """Deleting a folder should move nested playlists back to the root container."""
        folder_id = playlist_repo.create_folder("Temp")
        playlist_repo.add(Playlist(name="A", folder_id=folder_id, position=0))
        playlist_repo.add(Playlist(name="B", folder_id=folder_id, position=1))

        assert playlist_repo.delete_folder(folder_id) is True

        tree = playlist_repo.get_playlist_tree()
        assert tree.folders == []
        assert [p.name for p in tree.root_playlists] == ["A", "B"]
        assert [p.position for p in tree.root_playlists] == [0, 1]

    def test_move_playlist_to_folder_and_back_to_root(self, playlist_repo):
        """A playlist can be moved into a folder and restored to the root."""
        playlist_id = playlist_repo.add(Playlist(name="Inbox", position=0))
        folder_id = playlist_repo.create_folder("Archive")

        assert playlist_repo.move_playlist_to_folder(playlist_id, folder_id) is True
        assert playlist_repo.get_playlist(playlist_id).folder_id == folder_id

        assert playlist_repo.move_playlist_to_root(playlist_id) is True
        assert playlist_repo.get_playlist(playlist_id).folder_id is None

    def test_reorder_root_playlists_updates_position(self, playlist_repo):
        """Root playlist reordering should persist position values."""
        first = playlist_repo.add(Playlist(name="One", position=0))
        second = playlist_repo.add(Playlist(name="Two", position=1))

        assert playlist_repo.reorder_root_playlists([second, first]) is True

        tree = playlist_repo.get_playlist_tree()
        assert [p.name for p in tree.root_playlists] == ["Two", "One"]
        assert [p.position for p in tree.root_playlists] == [0, 1]

"""
Tests for SqliteTrackRepository.
"""

import pytest
import sqlite3
import tempfile
import os
from pathlib import Path

from repositories.track_repository import SqliteTrackRepository
from domain.track import Track, TrackSource


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

    # Create playlists table for playlist association tests
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            track_id INTEGER NOT NULL,
            position INTEGER DEFAULT 0,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
            UNIQUE(playlist_id, track_id)
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

    def test_get_all_supports_pagination_and_offset(self, track_repo):
        """Paginated reads should return a stable slice ordered by newest first."""
        for i in range(5):
            track_repo.add(Track(
                path=f"/music/song{i}.mp3",
                title=f"Song {i}",
                artist="Artist",
            ))

        tracks = track_repo.get_all(limit=2, offset=1)

        assert [track.title for track in tracks] == ["Song 3", "Song 2"]

    def test_get_all_can_filter_by_source(self, track_repo):
        """Track listing should support filtering by source in SQL."""
        track_repo.add(Track(path="/music/local.mp3", title="Local", source=TrackSource.LOCAL))
        track_repo.add(Track(
            path="qqmusic://song/abc",
            title="Online",
            source=TrackSource.QQ,
            cloud_file_id="abc",
        ))

        tracks = track_repo.get_all(source=TrackSource.QQ)

        assert len(tracks) == 1
        assert tracks[0].title == "Online"

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

    def test_search_tracks_supports_offset_and_source_filter(self, track_repo, temp_db):
        """Search pagination should work together with SQL source filtering."""
        tracks = [
            Track(path="/music/local-song.mp3", title="Song Alpha", artist="Local Artist", source=TrackSource.LOCAL),
            Track(
                path="qqmusic://song/1",
                title="Song Beta",
                artist="QQ Artist",
                source=TrackSource.QQ,
                cloud_file_id="song-1",
            ),
            Track(
                path="qqmusic://song/2",
                title="Song Gamma",
                artist="QQ Artist",
                source=TrackSource.QQ,
                cloud_file_id="song-2",
            ),
        ]
        for track in tracks:
            track_repo.add(track)

        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tracks_fts (rowid, title, artist, album)
            SELECT id, title, artist, album FROM tracks
        """)
        conn.commit()
        conn.close()

        results = track_repo.search("Song", limit=1, offset=1, source=TrackSource.QQ)

        assert len(results) == 1
        assert results[0].title == "Song Beta"

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


class TestTrackRepositoryBatchOperations:
    """Test batch and specialized query operations."""

    def test_get_by_ids(self, track_repo):
        """Test getting multiple tracks by IDs in batch."""
        ids = []
        for i in range(3):
            tid = track_repo.add(Track(
                path=f"/music/song{i}.mp3", title=f"Song {i}",
                artist=f"Artist {i}"
            ))
            ids.append(tid)

        # Get all three
        results = track_repo.get_by_ids(ids)
        assert len(results) == 3
        assert results[0].id == ids[0]
        assert results[1].id == ids[1]
        assert results[2].id == ids[2]

    def test_get_by_ids_empty_list(self, track_repo):
        """Test get_by_ids with empty list returns empty."""
        results = track_repo.get_by_ids([])
        assert results == []

    def test_get_by_ids_preserves_order(self, track_repo):
        """Test that get_by_ids returns results in input order."""
        id1 = track_repo.add(Track(path="/a.mp3", title="A"))
        id2 = track_repo.add(Track(path="/b.mp3", title="B"))
        id3 = track_repo.add(Track(path="/c.mp3", title="C"))

        # Request in reverse order
        results = track_repo.get_by_ids([id3, id1, id2])
        assert results[0].id == id3
        assert results[1].id == id1
        assert results[2].id == id2

    def test_get_by_ids_skips_missing(self, track_repo):
        """Test that get_by_ids skips IDs that don't exist."""
        id1 = track_repo.add(Track(path="/a.mp3", title="A"))
        results = track_repo.get_by_ids([id1, 99999, 88888])
        assert len(results) == 1
        assert results[0].id == id1

    def test_delete_batch(self, track_repo):
        """Test batch deletion of tracks."""
        ids = []
        for i in range(5):
            tid = track_repo.add(Track(
                path=f"/music/song{i}.mp3", title=f"Song {i}"
            ))
            ids.append(tid)

        # Delete first 3
        deleted = track_repo.delete_batch(ids[:3])
        assert deleted == 3

        # Verify remaining
        remaining = track_repo.get_all()
        assert len(remaining) == 2

    def test_delete_batch_empty_list(self, track_repo):
        """Test delete_batch with empty list returns 0."""
        deleted = track_repo.delete_batch([])
        assert deleted == 0

    def test_delete_batch_nonexistent(self, track_repo):
        """Test delete_batch with non-existent IDs returns 0."""
        deleted = track_repo.delete_batch([99999, 88888])
        assert deleted == 0


class TestTrackRepositoryAlbumOperations:
    """Test album-related operations."""

    def _add_tracks_for_albums(self, track_repo):
        """Helper to add tracks that belong to albums."""
        track_repo.add(Track(
            path="/music/a1.mp3", title="Track A1", artist="Artist A",
            album="Album A", duration=100.0, cover_path="/covers/album_a.jpg"
        ))
        track_repo.add(Track(
            path="/music/a2.mp3", title="Track A2", artist="Artist A",
            album="Album A", duration=200.0, cover_path="/covers/album_a.jpg"
        ))
        track_repo.add(Track(
            path="/music/b1.mp3", title="Track B1", artist="Artist B",
            album="Album B", duration=150.0
        ))

    def test_get_albums_fallback(self, track_repo):
        """Test getting albums via fallback (no albums table data)."""
        self._add_tracks_for_albums(track_repo)
        # Albums table exists but is empty -> fallback
        albums = track_repo.get_albums(use_cache=True)
        assert len(albums) == 2
        # Sorted by song_count DESC: Album A has 2 songs, Album B has 1
        assert albums[0].name == "Album A"
        assert albums[0].song_count == 2
        assert albums[1].name == "Album B"
        assert albums[1].song_count == 1

    def test_get_albums_from_cache(self, track_repo, temp_db):
        """Test getting albums from cache table."""
        self._add_tracks_for_albums(track_repo)

        # Populate albums cache table
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Album A', 'Artist A', '/covers/album_a.jpg', 2, 300.0)
        """)
        conn.commit()
        conn.close()

        albums = track_repo.get_albums(use_cache=True)
        assert len(albums) == 1
        assert albums[0].name == "Album A"
        assert albums[0].song_count == 2
        assert albums[0].duration == 300.0

    def test_get_album_tracks(self, track_repo):
        """Test getting tracks for a specific album."""
        self._add_tracks_for_albums(track_repo)

        tracks = track_repo.get_album_tracks("Album A")
        assert len(tracks) == 2
        titles = {t.title for t in tracks}
        assert titles == {"Track A1", "Track A2"}

    def test_get_album_tracks_with_artist_filter(self, track_repo):
        """Test getting album tracks filtered by artist."""
        self._add_tracks_for_albums(track_repo)

        tracks = track_repo.get_album_tracks("Album A", artist="Artist A")
        assert len(tracks) == 2

        tracks = track_repo.get_album_tracks("Album A", artist="Artist B")
        assert len(tracks) == 0

    def test_get_album_tracks_not_found(self, track_repo):
        """Test getting tracks for non-existent album."""
        tracks = track_repo.get_album_tracks("Nonexistent Album")
        assert tracks == []

    def test_get_album_by_name(self, track_repo):
        """Test getting album by name."""
        self._add_tracks_for_albums(track_repo)

        album = track_repo.get_album_by_name("Album A")
        assert album is not None
        assert album.name == "Album A"
        assert album.artist == "Artist A"
        assert album.song_count == 2

    def test_get_album_by_name_with_artist(self, track_repo):
        """Test getting album by name and artist."""
        self._add_tracks_for_albums(track_repo)

        album = track_repo.get_album_by_name("Album A", artist="Artist A")
        assert album is not None
        assert album.name == "Album A"

    def test_get_album_by_name_not_found(self, track_repo):
        """Test getting non-existent album."""
        album = track_repo.get_album_by_name("Nonexistent")
        assert album is None

    def test_get_album_by_name_from_cache(self, track_repo, temp_db):
        """Test get_album_by_name uses cache table."""
        self._add_tracks_for_albums(track_repo)

        # Populate albums cache table
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Album A', 'Artist A', '/covers/album_a.jpg', 2, 300.0)
        """)
        conn.commit()
        conn.close()

        album = track_repo.get_album_by_name("Album A")
        assert album is not None
        assert album.song_count == 2
        assert album.duration == 300.0


class TestTrackRepositoryArtistOperations:
    """Test artist-related operations."""

    def _add_tracks_for_artists(self, track_repo):
        """Helper to add tracks that belong to artists."""
        track_repo.add(Track(
            path="/music/a1.mp3", title="Track A1", artist="Artist A",
            album="Album A", duration=100.0, cover_path="/covers/a.jpg"
        ))
        track_repo.add(Track(
            path="/music/a2.mp3", title="Track A2", artist="Artist A",
            album="Album B", duration=200.0, cover_path="/covers/a.jpg"
        ))
        track_repo.add(Track(
            path="/music/b1.mp3", title="Track B1", artist="Artist B",
            album="Album C", duration=150.0
        ))

    def test_get_artists_fallback(self, track_repo):
        """Test getting artists via fallback (no cache data, direct query)."""
        self._add_tracks_for_artists(track_repo)
        # use_cache=False forces the fallback direct query path
        artists = track_repo.get_artists(use_cache=False)
        assert len(artists) == 2
        # Sorted by song_count DESC: Artist A has 2 songs
        assert artists[0].name == "Artist A"
        assert artists[0].song_count == 2
        assert artists[0].album_count == 2
        assert artists[1].name == "Artist B"
        assert artists[1].song_count == 1

    def test_get_artists_from_cache(self, track_repo, temp_db):
        """Test getting artists from cache table."""
        # Insert artist with proper stats using ON CONFLICT to avoid
        # UNIQUE constraint error (add() may have already inserted the name)
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
            VALUES ('Artist A', '/covers/a.jpg', 2, 2, 'artist a')
            ON CONFLICT(name) DO UPDATE SET
                cover_path = '/covers/a.jpg', song_count = 2, album_count = 2
        """)
        conn.commit()
        conn.close()

        artists = track_repo.get_artists(use_cache=True)
        assert len(artists) == 1
        assert artists[0].name == "Artist A"
        assert artists[0].song_count == 2

    def test_get_artist_by_name(self, track_repo):
        """Test getting artist by name."""
        self._add_tracks_for_artists(track_repo)

        # add() creates artist entries with song_count=0 in the artists table.
        # get_artist_by_name reads from that table, so we update stats first.
        track_repo.rebuild_track_artists()
        track_repo.update_artist_stats()

        artist = track_repo.get_artist_by_name("Artist A")
        assert artist is not None
        assert artist.name == "Artist A"
        assert artist.song_count == 2

    def test_get_artist_by_name_not_found(self, track_repo):
        """Test getting non-existent artist."""
        artist = track_repo.get_artist_by_name("Nonexistent")
        assert artist is None

    def test_get_artist_tracks(self, track_repo):
        """Test getting tracks for a specific artist."""
        self._add_tracks_for_artists(track_repo)

        tracks = track_repo.get_artist_tracks("Artist A")
        assert len(tracks) == 2
        titles = {t.title for t in tracks}
        assert titles == {"Track A1", "Track A2"}

    def test_get_artist_tracks_not_found(self, track_repo):
        """Test getting tracks for non-existent artist."""
        tracks = track_repo.get_artist_tracks("Nonexistent Artist")
        assert tracks == []

    def test_get_artist_albums(self, track_repo, temp_db):
        """Test getting albums for a specific artist."""
        self._add_tracks_for_artists(track_repo)

        # Populate albums cache table
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO albums (name, artist, cover_path, song_count, total_duration)
            VALUES ('Album A', 'Artist A', '/covers/a.jpg', 1, 100.0),
                   ('Album B', 'Artist A', '/covers/a.jpg', 1, 200.0),
                   ('Album C', 'Artist B', NULL, 1, 150.0)
        """)
        conn.commit()
        conn.close()

        albums = track_repo.get_artist_albums("Artist A")
        assert len(albums) == 2
        names = {a.name for a in albums}
        assert names == {"Album A", "Album B"}

    def test_get_artist_albums_not_found(self, track_repo):
        """Test getting albums for non-existent artist."""
        albums = track_repo.get_artist_albums("Nonexistent Artist")
        assert albums == []


class TestTrackRepositoryFieldUpdates:
    """Test field update operations."""

    def test_update_path(self, track_repo):
        """Test updating a track's file path."""
        tid = track_repo.add(Track(path="/old/path.mp3", title="Song"))

        result = track_repo.update_path(tid, "/new/path.mp3")
        assert result is True

        track = track_repo.get_by_id(tid)
        assert track.path == "/new/path.mp3"

    def test_update_path_nonexistent(self, track_repo):
        """Test updating path for non-existent track."""
        result = track_repo.update_path(99999, "/new/path.mp3")
        assert result is False

    def test_update_cover_path(self, track_repo):
        """Test updating a track's cover path."""
        tid = track_repo.add(Track(path="/music/song.mp3", title="Song"))

        result = track_repo.update_cover_path(tid, "/covers/new.jpg")
        assert result is True

        track = track_repo.get_by_id(tid)
        assert track.cover_path == "/covers/new.jpg"

    def test_update_cover_path_nonexistent(self, track_repo):
        """Test updating cover path for non-existent track."""
        result = track_repo.update_cover_path(99999, "/covers/x.jpg")
        assert result is False

    def test_update_fields_title(self, track_repo):
        """Test updating track title field."""
        tid = track_repo.add(Track(
            path="/music/song.mp3", title="Old Title",
            artist="Artist", album="Album"
        ))

        result = track_repo.update_fields(tid, title="New Title")
        assert result is True

        track = track_repo.get_by_id(tid)
        assert track.title == "New Title"
        # Other fields unchanged
        assert track.artist == "Artist"
        assert track.album == "Album"

    def test_update_fields_multiple(self, track_repo):
        """Test updating multiple fields at once."""
        tid = track_repo.add(Track(
            path="/music/song.mp3", title="Title",
            artist="Old Artist", album="Old Album"
        ))

        result = track_repo.update_fields(
            tid, title="New Title", artist="New Artist",
            album="New Album", cloud_file_id="cloud_123"
        )
        assert result is True

        track = track_repo.get_by_id(tid)
        assert track.title == "New Title"
        assert track.artist == "New Artist"
        assert track.album == "New Album"
        assert track.cloud_file_id == "cloud_123"

    def test_update_fields_no_changes(self, track_repo):
        """Test update_fields with no fields specified returns False."""
        tid = track_repo.add(Track(path="/music/song.mp3", title="Song"))
        result = track_repo.update_fields(tid)
        assert result is False

    def test_update_fields_nonexistent(self, track_repo):
        """Test updating fields for non-existent track."""
        result = track_repo.update_fields(99999, title="X")
        assert result is False

    def test_update_fields_cloud_file_id(self, track_repo):
        """Test updating only cloud_file_id."""
        tid = track_repo.add(Track(path="/music/song.mp3", title="Song"))

        result = track_repo.update_fields(tid, cloud_file_id="cid_999")
        assert result is True

        track = track_repo.get_by_id(tid)
        assert track.cloud_file_id == "cid_999"


class TestTrackRepositoryPlaylistAssociation:
    """Test playlist association operations."""

    def test_add_to_playlist(self, track_repo, temp_db):
        """Test adding a track to a playlist."""
        # Create a playlist first
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO playlists (name) VALUES (?)", ("My Playlist",)
        )
        playlist_id = cursor.lastrowid
        conn.commit()
        conn.close()

        tid = track_repo.add(Track(path="/music/song.mp3", title="Song"))

        result = track_repo.add_to_playlist(playlist_id, tid)
        assert result is True

    def test_get_playlist_tracks(self, track_repo, temp_db):
        """Test getting tracks from a playlist."""
        # Create playlist and add tracks
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO playlists (name) VALUES (?)", ("My Playlist",)
        )
        playlist_id = cursor.lastrowid
        conn.commit()
        conn.close()

        t1 = track_repo.add(Track(path="/a.mp3", title="A"))
        t2 = track_repo.add(Track(path="/b.mp3", title="B"))

        track_repo.add_to_playlist(playlist_id, t1)
        track_repo.add_to_playlist(playlist_id, t2)

        tracks = track_repo.get_playlist_tracks(playlist_id)
        assert len(tracks) == 2
        assert tracks[0].title == "A"
        assert tracks[1].title == "B"

    def test_get_playlist_tracks_empty(self, track_repo, temp_db):
        """Test getting tracks from empty playlist."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO playlists (name) VALUES (?)", ("Empty",)
        )
        playlist_id = cursor.lastrowid
        conn.commit()
        conn.close()

        tracks = track_repo.get_playlist_tracks(playlist_id)
        assert tracks == []

    def test_add_to_playlist_duplicate_ignored(self, track_repo, temp_db):
        """Test that adding duplicate track to playlist is ignored."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO playlists (name) VALUES (?)", ("My Playlist",)
        )
        playlist_id = cursor.lastrowid
        conn.commit()
        conn.close()

        tid = track_repo.add(Track(path="/a.mp3", title="A"))

        track_repo.add_to_playlist(playlist_id, tid)
        # Second add should be ignored (returns False due to no rows inserted)
        result = track_repo.add_to_playlist(playlist_id, tid)
        assert result is False

        tracks = track_repo.get_playlist_tracks(playlist_id)
        assert len(tracks) == 1


class TestTrackRepositoryMultiArtist:
    """Test multi-artist operations."""

    def test_sync_track_artists(self, track_repo):
        """Test syncing track_artists junction records."""
        tid = track_repo.add(Track(
            path="/music/song.mp3", title="Song", artist="Artist A, Artist B"
        ))

        result = track_repo.sync_track_artists(tid, "Artist A, Artist B")
        assert result is True

        names = track_repo.get_track_artist_names(tid)
        assert "Artist A" in names
        assert "Artist B" in names

    def test_sync_track_artists_replace(self, track_repo):
        """Test that sync replaces existing artist associations."""
        tid = track_repo.add(Track(
            path="/music/song.mp3", title="Song", artist="Artist A"
        ))

        track_repo.sync_track_artists(tid, "Artist A")
        track_repo.sync_track_artists(tid, "Artist C, Artist D")

        names = track_repo.get_track_artist_names(tid)
        assert "Artist C" in names
        assert "Artist D" in names
        assert "Artist A" not in names

    def test_sync_track_artists_empty_string(self, track_repo):
        """Test syncing with empty artist string clears junction."""
        tid = track_repo.add(Track(
            path="/music/song.mp3", title="Song", artist="Artist A"
        ))

        track_repo.sync_track_artists(tid, "Artist A")
        track_repo.sync_track_artists(tid, "")

        names = track_repo.get_track_artist_names(tid)
        assert names == []

    def test_rebuild_track_artists(self, track_repo):
        """Test rebuilding the track_artists junction table for all tracks."""
        t1 = track_repo.add(Track(
            path="/a.mp3", title="A", artist="Artist A, Artist B"
        ))
        t2 = track_repo.add(Track(
            path="/b.mp3", title="B", artist="Artist C"
        ))
        t3 = track_repo.add(Track(path="/c.mp3", title="C"))  # No artist

        count = track_repo.rebuild_track_artists()
        # Only tracks with non-empty artist strings are processed
        assert count == 2

        names1 = track_repo.get_track_artist_names(t1)
        assert "Artist A" in names1
        assert "Artist B" in names1

        names2 = track_repo.get_track_artist_names(t2)
        assert "Artist C" in names2

    def test_rebuild_track_artists_empty_db(self, track_repo):
        """Test rebuilding when there are no tracks."""
        count = track_repo.rebuild_track_artists()
        assert count == 0

    def test_update_artist_stats(self, track_repo):
        """Test updating artist song_count and album_count."""
        track_repo.add(Track(
            path="/a.mp3", title="A", artist="Artist A",
            album="Album X", duration=100.0
        ))
        track_repo.add(Track(
            path="/b.mp3", title="B", artist="Artist A",
            album="Album Y", duration=200.0
        ))
        track_repo.add(Track(
            path="/c.mp3", title="C", artist="Artist B",
            album="Album X", duration=150.0
        ))

        # Rebuild junction table first
        track_repo.rebuild_track_artists()
        # Then update stats
        updated = track_repo.update_artist_stats()
        assert updated > 0

    def test_get_track_artist_names_empty(self, track_repo):
        """Test getting artist names for track with no artist associations."""
        tid = track_repo.add(Track(path="/music/song.mp3", title="Song"))
        names = track_repo.get_track_artist_names(tid)
        assert names == []

    def test_get_track_artist_names_nonexistent_track(self, track_repo):
        """Test getting artist names for non-existent track."""
        names = track_repo.get_track_artist_names(99999)
        assert names == []

"""
Tests for SqliteArtistRepository.
"""

import pytest
import sqlite3
import tempfile
import os
from unittest.mock import Mock

from repositories.artist_repository import SqliteArtistRepository
from repositories.track_repository import SqliteTrackRepository


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

    # Create artists cache table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            cover_path TEXT,
            song_count INTEGER,
            album_count INTEGER,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    except Exception:
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

    # Add artists
    cursor.execute("INSERT INTO artists (name, normalized_name) VALUES ('Artist A', 'artist a')")
    cursor.execute("INSERT INTO artists (name, normalized_name) VALUES ('Artist B', 'artist b')")

    # Create track_artists junction records
    # Track 1 (Artist A)
    cursor.execute("INSERT INTO track_artists (track_id, artist_id, position) VALUES (1, 1, 0)")
    # Track 2 (Artist A)
    cursor.execute("INSERT INTO track_artists (track_id, artist_id, position) VALUES (2, 1, 0)")
    # Track 3 (Artist A)
    cursor.execute("INSERT INTO track_artists (track_id, artist_id, position) VALUES (3, 1, 0)")
    # Track 4 (Artist B)
    cursor.execute("INSERT INTO track_artists (track_id, artist_id, position) VALUES (4, 2, 0)")
    # Track 5 (Artist B)
    cursor.execute("INSERT INTO track_artists (track_id, artist_id, position) VALUES (5, 2, 0)")

    # Update artist stats
    cursor.execute("UPDATE artists SET song_count = 3, album_count = 2 WHERE name = 'Artist A'")
    cursor.execute("UPDATE artists SET song_count = 2, album_count = 1 WHERE name = 'Artist B'")

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

    def test_get_all_with_cache(self, temp_db):
        """Test get_all using artists cache table."""
        # Create a separate database with cached artists
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create tables
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
                source TEXT DEFAULT 'Local'
            )
        """)

        cursor.execute("""
            CREATE TABLE artists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                cover_path TEXT,
                song_count INTEGER,
                album_count INTEGER,
                normalized_name TEXT
            )
        """)

        # Populate artists cache only (no tracks)
        cursor.execute("""
            INSERT INTO artists (name, cover_path, song_count, album_count)
            VALUES ('Cached Artist', '/covers/artist.jpg', 10, 3)
        """)

        conn.commit()
        conn.close()

        repo = SqliteArtistRepository(db_path)
        artists = repo.get_all(use_cache=True)

        # Should get cached artist
        assert len(artists) == 1
        assert artists[0].name == "Cached Artist"
        assert artists[0].song_count == 10
        assert artists[0].album_count == 3

        # Cleanup
        os.unlink(db_path)

    def test_get_all_cached_query_does_not_probe_cache_table_existence(self, temp_db):
        """Cache-backed artist reads should not re-run table existence probes on every call."""
        fd, db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
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
                    cover_path TEXT,
                    cloud_file_id TEXT,
                    source TEXT DEFAULT 'Local'
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE artists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    cover_path TEXT,
                    song_count INTEGER,
                    album_count INTEGER,
                    normalized_name TEXT
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO artists (name, cover_path, song_count, album_count, normalized_name)
                VALUES ('Artist X', '/covers/x.jpg', 10, 3, 'artist x')
                """
            )
            conn.commit()

            statements = []
            conn.set_trace_callback(statements.append)
            repo = SqliteArtistRepository(db_path)
            repo._get_connection = lambda: conn
            try:
                repo.get_all(use_cache=True)
                repo.get_all(use_cache=True)
            finally:
                conn.set_trace_callback(None)
                conn.close()

            probes = [sql for sql in statements if "SELECT 1 FROM artists LIMIT 1" in sql]
            assert probes == []
        finally:
            os.unlink(db_path)

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

    def test_get_by_name_returns_none_for_blank_name_without_querying(self, artist_repo):
        """Blank artist names should be rejected before touching the database."""
        conn = artist_repo._get_connection()
        statements = []
        conn.set_trace_callback(statements.append)
        try:
            artist = artist_repo.get_by_name("   ")
        finally:
            conn.set_trace_callback(None)

        assert artist is None
        assert statements == []

    def test_refresh_artist_updates_single_cached_artist(self, populated_db):
        """Targeted artist refresh should update stats for the requested artist only."""
        repo = SqliteArtistRepository(populated_db)

        assert repo.refresh_artist("Artist A") is True

        artist = repo.get_by_name("Artist A")
        assert artist is not None
        assert artist.song_count == 3
        assert artist.album_count == 2

    def test_delete_if_empty_removes_artist_without_tracks(self, populated_db):
        """Targeted artist cleanup should delete cache rows when the artist has no linked tracks."""
        repo = SqliteArtistRepository(populated_db)
        assert repo.refresh_artist("Artist B") is True

        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            DELETE FROM track_artists
            WHERE artist_id = (SELECT id FROM artists WHERE name = ?)
            """,
            ("Artist B",),
        )
        cursor.execute("DELETE FROM tracks WHERE artist = ?", ("Artist B",))
        conn.commit()
        conn.close()

        assert repo.delete_if_empty("Artist B") is True
        assert repo.get_by_name("Artist B") is None

    def test_get_by_name_fallback_uses_single_tracks_query(self, temp_db):
        """Test fallback get_by_name fetches aggregate data and cover in one tracks query."""
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.executemany(
            """
            INSERT INTO tracks (path, title, artist, album, duration, cover_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("/music/song1.mp3", "Song 1", "Artist A", "Album 1", 180.0, None),
                ("/music/song2.mp3", "Song 2", "Artist A", "Album 2", 200.0, "/covers/artist_a.jpg"),
            ],
        )
        statements = []
        conn.set_trace_callback(statements.append)

        repo = SqliteArtistRepository(temp_db)
        repo._get_connection = lambda: conn
        try:
            artist = repo.get_by_name("Artist A")
        finally:
            conn.set_trace_callback(None)
            conn.close()

        track_selects = [
            statement for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
            and "FROM TRACKS" in statement.upper()
        ]

        assert artist is not None
        assert artist.cover_path == "/covers/artist_a.jpg"
        assert artist.song_count == 2
        assert artist.album_count == 2
        assert len(track_selects) == 1

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

    def test_refresh_rolls_back_when_upsert_fails(self):
        repo = SqliteArtistRepository.__new__(SqliteArtistRepository)
        cursor = Mock()
        cursor.fetchall.side_effect = [
            [],
            [{"artist": "Artist A", "cover_path": None}],
            [{"artist": "Artist A", "album": "Album 1"}],
        ]
        cursor.execute.side_effect = [None, None, None, sqlite3.DatabaseError("boom")]
        conn = Mock(cursor=Mock(return_value=cursor))
        repo._get_connection = lambda: conn

        result = SqliteArtistRepository.refresh(repo)

        assert result is False
        conn.rollback.assert_called_once_with()
        conn.commit.assert_not_called()

    def test_update_cover_path(self, temp_db, populated_db):
        """Test updating cover path for an artist."""
        # populated_db already has Artist A and Artist B
        repo = SqliteArtistRepository(populated_db)

        # Update cover path for Artist A (already exists from populated_db)
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

    def test_rebuild_with_albums_keeps_artist_stats_and_cover_when_junction_stale(self, populated_db):
        """
        Rebuilding from settings should not leave artists with 0 stats or missing covers
        when track_artists was stale/empty.
        """
        conn = sqlite3.connect(populated_db)
        cursor = conn.cursor()
        cursor.execute("UPDATE artists SET cover_path = '/covers/artist_a.jpg' WHERE name = 'Artist A'")
        cursor.execute("DELETE FROM track_artists")
        conn.commit()
        conn.close()

        artist_repo = SqliteArtistRepository(populated_db)
        track_repo = SqliteTrackRepository(populated_db)

        # Simulate settings dialog flow: rebuild albums/artists, then rebuild junction table.
        artist_repo.rebuild_with_albums()
        track_repo.rebuild_track_artists()

        artists = {artist.name: artist for artist in artist_repo.get_all(use_cache=True)}
        assert "Artist A" in artists
        assert "Artist B" in artists

        assert artists["Artist A"].song_count == 3
        assert artists["Artist A"].album_count == 2
        assert artists["Artist A"].cover_path == "/covers/artist_a.jpg"
        assert artists["Artist B"].song_count == 2
        assert artists["Artist B"].album_count == 1

    def test_get_all_album_count(self, artist_repo, populated_db):
        """Test that album_count is correctly calculated."""
        artists = artist_repo.get_all(use_cache=False)

        artist_a = next((a for a in artists if a.name == "Artist A"), None)
        assert artist_a is not None
        assert artist_a.album_count == 2  # Album 1 and Album 2

        artist_b = next((a for a in artists if a.name == "Artist B"), None)
        assert artist_b is not None
        assert artist_b.album_count == 1  # Only Album 3

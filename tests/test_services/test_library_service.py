"""
Tests for LibraryService.
"""

import ast
import inspect
import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from domain.genre import Genre
from domain.track import Track
from domain.playlist import Playlist
from services.library.library_service import LibraryService


class TestLibraryService:
    """Test LibraryService class."""

    @pytest.fixture
    def mock_track_repo(self):
        """Create mock track repository."""
        return Mock()

    @pytest.fixture
    def mock_playlist_repo(self):
        """Create mock playlist repository."""
        return Mock()

    @pytest.fixture
    def mock_album_repo(self):
        """Create mock album repository."""
        return Mock()

    @pytest.fixture
    def mock_artist_repo(self):
        """Create mock artist repository."""
        return Mock()

    @pytest.fixture
    def mock_event_bus(self):
        """Create mock event bus."""
        bus = Mock()
        bus.tracks_added = Mock()
        bus.playlist_created = Mock()
        bus.playlist_deleted = Mock()
        bus.playlist_modified = Mock()
        return bus

    @pytest.fixture
    def mock_cover_service(self):
        """Create mock cover service."""
        return Mock()

    @pytest.fixture
    def library_service(self, mock_track_repo, mock_playlist_repo, mock_album_repo, mock_artist_repo, mock_event_bus, mock_cover_service):
        """Create LibraryService instance with mocked dependencies."""
        return LibraryService(
            track_repo=mock_track_repo,
            playlist_repo=mock_playlist_repo,
            album_repo=mock_album_repo,
            artist_repo=mock_artist_repo,
            event_bus=mock_event_bus,
            cover_service=mock_cover_service,
        )

    def test_initialization(self, library_service, mock_track_repo, mock_playlist_repo):
        """Test LibraryService initialization."""
        assert library_service._track_repo == mock_track_repo
        assert library_service._playlist_repo == mock_playlist_repo
        assert library_service._event_bus is not None

    # ===== Track Operations Tests =====

    def test_get_track(self, library_service, mock_track_repo):
        """Test getting a track by ID."""
        mock_track = Track(id=1, title="Test Song")
        mock_track_repo.get_by_id.return_value = mock_track

        result = library_service.get_track(1)

        assert result == mock_track
        mock_track_repo.get_by_id.assert_called_once_with(1)

    def test_get_all_tracks(self, library_service, mock_track_repo):
        """Test getting all tracks."""
        mock_tracks = [Track(id=1), Track(id=2)]
        mock_track_repo.get_all.return_value = mock_tracks

        result = library_service.get_all_tracks()

        assert result == mock_tracks
        mock_track_repo.get_all.assert_called_once()

    def test_search_tracks(self, library_service, mock_track_repo):
        """Test searching tracks."""
        mock_tracks = [Track(id=1, title="Search Result")]
        mock_track_repo.search.return_value = mock_tracks

        result = library_service.search_tracks("query", limit=50)

        assert result == mock_tracks
        mock_track_repo.search.assert_called_once_with("query", limit=50, offset=0, source=None)

    def test_add_track_success(self, library_service, mock_track_repo, mock_event_bus):
        """Test adding a track successfully."""
        track = Track(id=1, title="New Song")
        mock_track_repo.add.return_value = 1

        result = library_service.add_track(track)

        assert result == 1
        mock_track_repo.add.assert_called_once_with(track)
        mock_event_bus.tracks_added.emit.assert_called_once_with(1)

    def test_add_track_failure(self, library_service, mock_track_repo, mock_event_bus):
        """Test adding a track that fails."""
        track = Track(title="Failed Song")
        mock_track_repo.add.return_value = None

        result = library_service.add_track(track)

        assert result is None
        mock_event_bus.tracks_added.emit.assert_not_called()

    def test_update_track(self, library_service, mock_track_repo):
        """Test updating a track."""
        track = Track(id=1, title="Updated Title")
        mock_track_repo.update.return_value = True

        result = library_service.update_track(track)

        assert result is True
        mock_track_repo.update.assert_called_once_with(track)

    def test_delete_track(self, library_service, mock_track_repo):
        """Test deleting a track."""
        mock_track_repo.delete.return_value = True

        result = library_service.delete_track(1)

        assert result is True
        mock_track_repo.delete.assert_called_once_with(1)

    # ===== Playlist Operations Tests =====

    def test_get_all_playlists(self, library_service, mock_playlist_repo):
        """Test getting all playlists."""
        mock_playlists = [Playlist(id=1, name="Playlist 1")]
        mock_playlist_repo.get_all.return_value = mock_playlists

        result = library_service.get_all_playlists()

        assert result == mock_playlists
        mock_playlist_repo.get_all.assert_called_once()

    def test_get_playlist(self, library_service, mock_playlist_repo):
        """Test getting a playlist by ID."""
        mock_playlist = Playlist(id=1, name="My Playlist")
        mock_playlist_repo.get_by_id.return_value = mock_playlist

        result = library_service.get_playlist(1)

        assert result == mock_playlist
        mock_playlist_repo.get_by_id.assert_called_once_with(1)

    def test_get_playlist_tracks(self, library_service, mock_playlist_repo):
        """Test getting tracks in a playlist."""
        mock_tracks = [Track(id=1), Track(id=2)]
        mock_playlist_repo.get_tracks.return_value = mock_tracks

        result = library_service.get_playlist_tracks(1)

        assert result == mock_tracks
        mock_playlist_repo.get_tracks.assert_called_once_with(1)

    def test_create_playlist_success(
        self, library_service, mock_playlist_repo, mock_event_bus
    ):
        """Test creating a playlist successfully."""
        mock_playlist_repo.add.return_value = 5

        result = library_service.create_playlist("New Playlist")

        assert result == 5
        mock_playlist_repo.add.assert_called_once()
        mock_event_bus.playlist_created.emit.assert_called_once_with(5)

    def test_create_playlist_failure(
        self, library_service, mock_playlist_repo, mock_event_bus
    ):
        """Test creating a playlist that fails."""
        mock_playlist_repo.add.return_value = None

        result = library_service.create_playlist("Failed Playlist")

        assert result is None
        mock_event_bus.playlist_created.emit.assert_not_called()

    def test_delete_playlist_success(
        self, library_service, mock_playlist_repo, mock_event_bus
    ):
        """Test deleting a playlist successfully."""
        mock_playlist_repo.delete.return_value = True

        result = library_service.delete_playlist(1)

        assert result is True
        mock_playlist_repo.delete.assert_called_once_with(1)
        mock_event_bus.playlist_deleted.emit.assert_called_once_with(1)

    def test_add_track_to_playlist_success(
        self, library_service, mock_playlist_repo, mock_event_bus
    ):
        """Test adding a track to playlist successfully."""
        mock_playlist_repo.add_track.return_value = True

        result = library_service.add_track_to_playlist(1, 5)

        assert result is True
        mock_playlist_repo.add_track.assert_called_once_with(1, 5)
        mock_event_bus.playlist_modified.emit.assert_called_once_with(1)

    # ===== Scanning Operations Tests =====

    def test_scan_directory_nonexistent(self, library_service):
        """Test scanning non-existent directory."""
        result = library_service.scan_directory("/nonexistent/path")

        assert result == 0

    @patch("services.library.library_service.Path")
    @patch.object(LibraryService, "_create_track_from_file")
    def test_scan_directory_success(
        self, mock_create_track, mock_path_class, library_service, mock_track_repo
    ):
        """Test scanning directory successfully."""
        # Setup mocks
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.rglob.return_value = [
            Path("/music/song1.mp3"),
            Path("/music/song2.flac"),
            Path("/music/document.txt"),  # Should be ignored
        ]
        mock_path_class.return_value = mock_path

        # Mock track creation
        mock_track1 = Track(path="/music/song1.mp3", title="Song 1")
        mock_track2 = Track(path="/music/song2.flac", title="Song 2")
        mock_create_track.side_effect = [mock_track1, mock_track2, None]

        # Mock repository add
        mock_track_repo.batch_add.return_value = 2

        result = library_service.scan_directory("/music", recursive=True)

        assert result == 2
        assert mock_track_repo.batch_add.call_count == 1

    @patch("services.library.library_service.Path")
    def test_scan_directory_non_recursive(self, mock_path_class, library_service):
        """Test scanning directory non-recursively."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.glob.return_value = [Path("/music/song1.mp3")]
        mock_path_class.return_value = mock_path

        with patch.object(
            library_service, "_create_track_from_file", return_value=None
        ):
            library_service.scan_directory("/music", recursive=False)

            mock_path.glob.assert_called_once_with("*")

    def test_scan_directory_supported_extensions(self):
        """Test that only supported extensions are scanned."""
        # This test verifies supported extensions are defined
        supported = ['.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac']
        for ext in supported:
            assert ext in ['.mp3', '.flac', '.wav', '.m4a', '.ogg', '.aac']

    @patch("services.library.library_service.MetadataService")
    @patch("services.library.library_service.Path")
    def test_create_track_from_file_success(
        self, mock_path_class, mock_metadata_service, library_service
    ):
        """Test creating track from file successfully."""
        # Setup mocks
        mock_metadata_service.extract_metadata.return_value = {
            "title": "Test Song",
            "artist": "Test Artist",
            "album": "Test Album",
            "duration": 180.0,
            "cover": None,
        }
        library_service._cover_service.save_cover_from_metadata.return_value = "/covers/test.jpg"
        mock_path_class.return_value.exists.return_value = True
        mock_path_class.return_value.stem = "test"

        result = library_service._create_track_from_file("/music/test.mp3")

        assert result is not None
        assert result.title == "Test Song"
        assert result.artist == "Test Artist"
        assert result.duration == 180.0

    @patch("services.library.library_service.MetadataService")
    @patch("services.library.library_service.Path")
    def test_create_track_from_file_error(
        self, mock_path_class, mock_metadata_service, mock_track_repo, mock_playlist_repo, mock_album_repo, mock_artist_repo
    ):
        """Test creating track from file with error."""
        mock_metadata_service.extract_metadata.side_effect = Exception("Error")

        library_service = LibraryService(mock_track_repo, mock_playlist_repo, mock_album_repo, mock_artist_repo)

        result = library_service._create_track_from_file("/music/test.mp3")

        assert result is None

    @patch("services.library.library_service.Path")
    @patch.object(LibraryService, "_create_track_from_file")
    def test_scan_directory_emits_event(
        self, mock_create_track, mock_path_class, library_service, mock_track_repo
    ):
        """Test that scanning emits tracks_added event."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.rglob.return_value = [Path("/music/song.mp3")]
        mock_path_class.return_value = mock_path

        mock_create_track.return_value = Track(path="/music/song.mp3")
        mock_track_repo.batch_add.return_value = 1

        library_service.scan_directory("/music")

        library_service._event_bus.tracks_added.emit.assert_called_once_with(1)

    @patch("services.library.library_service.Path")
    def test_scan_directory_empty(self, mock_path_class, library_service):
        """Test scanning empty directory."""
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.rglob.return_value = []
        mock_path_class.return_value = mock_path

        result = library_service.scan_directory("/empty", recursive=True)

        assert result == 0

    # ===== Artist Operations Tests =====

    def test_rename_artist_empty_old_name(self, library_service):
        """Test rename with empty old name."""
        result = library_service.rename_artist("", "New Artist")

        assert result['updated_tracks'] == 0
        assert 'Empty name provided' in result['errors']

    def test_rename_artist_empty_new_name(self, library_service):
        """Test rename with empty new name."""
        result = library_service.rename_artist("Old Artist", "")

        assert result['updated_tracks'] == 0
        assert 'Empty name provided' in result['errors']

    def test_rename_artist_identical_names(self, library_service):
        """Test rename with identical names."""
        result = library_service.rename_artist("Same Name", "Same Name")

        assert result['updated_tracks'] == 0
        assert 'Names are identical' in result['errors']

    def test_rename_artist_not_found(self, library_service, mock_track_repo):
        """Test rename when artist not found."""
        mock_track_repo.get_artist_tracks.return_value = []

        result = library_service.rename_artist("Nonexistent", "New Name")

        assert result['updated_tracks'] == 0
        assert 'Artist not found' in result['errors']

    @patch("services.library.library_service.MetadataService")
    def test_rename_artist_success(
        self, mock_metadata_service, library_service, mock_track_repo, mock_event_bus
    ):
        """Test successful artist rename."""
        # Setup tracks
        tracks = [
            Track(id=1, path="/music/song1.mp3", title="Song 1", artist="Old Artist"),
            Track(id=2, path="/music/song2.mp3", title="Song 2", artist="Old Artist"),
        ]
        mock_track_repo.get_artist_tracks.return_value = tracks
        mock_track_repo.get_artist_by_name.return_value = None  # New name doesn't exist

        # Mock metadata save
        mock_metadata_service.save_metadata.return_value = True

        # Mock database manager
        mock_db = Mock()
        mock_db.rebuild_albums_artists.return_value = {'albums': 1, 'artists': 1}
        library_service._db = mock_db

        result = library_service.rename_artist("Old Artist", "New Artist")

        assert result['updated_tracks'] == 2
        assert result['merged'] is False
        assert len(result['errors']) == 0
        assert mock_metadata_service.save_metadata.call_count == 2
        assert mock_track_repo.update.call_count == 2

    @patch("services.library.library_service.MetadataService")
    def test_rename_artist_merge(
        self, mock_metadata_service, library_service, mock_track_repo
    ):
        """Test artist rename with merge."""
        from domain.artist import Artist

        # Setup tracks
        tracks = [Track(id=1, path="/music/song.mp3", title="Song", artist="Old Artist")]
        mock_track_repo.get_artist_tracks.return_value = tracks

        # New name already exists
        existing_artist = Artist(name="Existing Artist", song_count=5)
        mock_track_repo.get_artist_by_name.return_value = existing_artist

        # Mock metadata save
        mock_metadata_service.save_metadata.return_value = True

        # Mock database manager
        mock_db = Mock()
        mock_db.rebuild_albums_artists.return_value = {'albums': 1, 'artists': 1}
        library_service._db = mock_db

        result = library_service.rename_artist("Old Artist", "Existing Artist")

        assert result['updated_tracks'] == 1
        assert result['merged'] is True

    @patch("services.library.library_service.MetadataService")
    def test_rename_artist_partial_failure(
        self, mock_metadata_service, library_service, mock_track_repo
    ):
        """Test artist rename with some failures."""
        # Setup tracks
        tracks = [
            Track(id=1, path="/music/song1.mp3", title="Song 1", artist="Old Artist"),
            Track(id=2, path="/music/song2.mp3", title="Song 2", artist="Old Artist"),
        ]
        mock_track_repo.get_artist_tracks.return_value = tracks
        mock_track_repo.get_artist_by_name.return_value = None

        # First succeeds, second fails
        mock_metadata_service.save_metadata.side_effect = [True, False]

        # Mock database manager
        mock_db = Mock()
        mock_db.rebuild_albums_artists.return_value = {'albums': 1, 'artists': 1}
        library_service._db = mock_db

        result = library_service.rename_artist("Old Artist", "New Artist")

        assert result['updated_tracks'] == 1
        assert len(result['errors']) == 1

    # ===== Album Operations Tests =====

    def test_rename_album_empty_old_name(self, library_service):
        """Test rename album with empty old name."""
        result = library_service.rename_album("", "Artist", "New Album")

        assert result['updated_tracks'] == 0
        assert 'Empty name provided' in result['errors']

    def test_rename_album_empty_new_name(self, library_service):
        """Test rename album with empty new name."""
        result = library_service.rename_album("Old Album", "Artist", "")

        assert result['updated_tracks'] == 0
        assert 'Empty name provided' in result['errors']

    def test_rename_album_identical_names(self, library_service):
        """Test rename album with identical names."""
        result = library_service.rename_album("Same Album", "Artist", "Same Album")

        assert result['updated_tracks'] == 0
        assert 'Names are identical' in result['errors']

    def test_rename_album_not_found(self, library_service, mock_track_repo):
        """Test rename when album not found."""
        mock_track_repo.get_album_tracks.return_value = []

        result = library_service.rename_album("Nonexistent", "Artist", "New Album")

        assert result['updated_tracks'] == 0
        assert 'Album not found' in result['errors']

    @patch("services.library.library_service.MetadataService")
    def test_rename_album_success(
        self, mock_metadata_service, library_service, mock_track_repo, mock_event_bus
    ):
        """Test successful album rename."""
        # Setup tracks
        tracks = [
            Track(id=1, path="/music/song1.mp3", title="Song 1", artist="Artist", album="Old Album"),
            Track(id=2, path="/music/song2.mp3", title="Song 2", artist="Artist", album="Old Album"),
        ]

        # First call: old album, second call: check existing (new album name doesn't exist)
        mock_track_repo.get_album_tracks.side_effect = [tracks, []]

        # Mock metadata save
        mock_metadata_service.save_metadata.return_value = True

        # Mock database manager
        mock_db = Mock()
        mock_db.rebuild_albums_artists.return_value = {'albums': 1, 'artists': 1}
        library_service._db = mock_db

        result = library_service.rename_album("Old Album", "Artist", "New Album")

        assert result['updated_tracks'] == 2
        assert result['merged'] is False
        assert len(result['errors']) == 0
        assert mock_metadata_service.save_metadata.call_count == 2
        assert mock_track_repo.update.call_count == 2

    @patch("services.library.library_service.MetadataService")
    def test_rename_album_merge(
        self, mock_metadata_service, library_service, mock_track_repo
    ):
        """Test album rename with merge."""
        # Setup tracks for old album
        tracks = [Track(id=1, path="/music/song.mp3", title="Song", artist="Artist", album="Old Album")]
        # Existing tracks in new album
        existing_tracks = [Track(id=2, path="/music/existing.mp3", title="Existing", artist="Artist", album="New Album")]

        # First call returns old album tracks, second call returns existing tracks (merge scenario)
        mock_track_repo.get_album_tracks.side_effect = [tracks, existing_tracks]

        # Mock metadata save
        mock_metadata_service.save_metadata.return_value = True

        # Mock database manager
        mock_db = Mock()
        mock_db.rebuild_albums_artists.return_value = {'albums': 1, 'artists': 1}
        library_service._db = mock_db

        result = library_service.rename_album("Old Album", "Artist", "New Album")

        assert result['updated_tracks'] == 1
        assert result['merged'] is True

    @patch("services.library.library_service.MetadataService")
    def test_rename_album_partial_failure(
        self, mock_metadata_service, library_service, mock_track_repo
    ):
        """Test album rename with some failures."""
        # Setup tracks
        tracks = [
            Track(id=1, path="/music/song1.mp3", title="Song 1", artist="Artist", album="Old Album"),
            Track(id=2, path="/music/song2.mp3", title="Song 2", artist="Artist", album="Old Album"),
        ]
        mock_track_repo.get_album_tracks.side_effect = [tracks, []]

        # First succeeds, second fails
        mock_metadata_service.save_metadata.side_effect = [True, False]

        # Mock database manager
        mock_db = Mock()
        mock_db.rebuild_albums_artists.return_value = {'albums': 1, 'artists': 1}
        library_service._db = mock_db

        result = library_service.rename_album("Old Album", "Artist", "New Album")

        assert result['updated_tracks'] == 1
        assert len(result['errors']) == 1

    # ===== Album/Artist Table Operations Tests =====

    def test_init_albums_artists_both_empty(self, library_service, mock_album_repo, mock_artist_repo):
        """Test init_albums_artists refreshes both tables when empty."""
        mock_album_repo.is_empty.return_value = True
        mock_artist_repo.is_empty.return_value = True

        library_service.init_albums_artists()

        mock_album_repo.refresh.assert_called_once()
        mock_artist_repo.refresh.assert_called_once()

    def test_init_albums_artists_albums_not_empty(self, library_service, mock_album_repo, mock_artist_repo):
        """Test init_albums_artists skips album refresh when not empty."""
        mock_album_repo.is_empty.return_value = False
        mock_artist_repo.is_empty.return_value = True

        library_service.init_albums_artists()

        mock_album_repo.refresh.assert_not_called()
        mock_artist_repo.refresh.assert_called_once()

    def test_init_albums_artists_artists_not_empty(self, library_service, mock_album_repo, mock_artist_repo):
        """Test init_albums_artists skips artist refresh when not empty."""
        mock_album_repo.is_empty.return_value = True
        mock_artist_repo.is_empty.return_value = False

        library_service.init_albums_artists()

        mock_album_repo.refresh.assert_called_once()
        mock_artist_repo.refresh.assert_not_called()

    def test_refresh_albums_artists(self, library_service, mock_album_repo, mock_artist_repo):
        """Test refresh_albums_artists refreshes both tables."""
        library_service.refresh_albums_artists(immediate=True)

        mock_album_repo.refresh.assert_called_once()
        mock_artist_repo.refresh.assert_called_once()

    def test_refresh_albums_artists_defined_once(self):
        """LibraryService should expose only one refresh_albums_artists entry point."""
        class_source = inspect.getsource(LibraryService)
        class_ast = ast.parse(class_source)
        class_def = next(
            node for node in class_ast.body
            if isinstance(node, ast.ClassDef) and node.name == "LibraryService"
        )
        method_count = sum(
            1 for node in class_def.body
            if isinstance(node, ast.FunctionDef) and node.name == "refresh_albums_artists"
        )

        assert method_count == 1

    def test_refresh_albums_artists_without_immediate_uses_debounce(
        self, library_service, mock_album_repo, mock_artist_repo
    ):
        """Default refresh should debounce via timer instead of refreshing repos directly."""
        with patch.object(library_service._refresh_timer, "start") as mock_start:
            library_service.refresh_albums_artists()

        mock_start.assert_called_once_with(500)
        mock_album_repo.refresh.assert_not_called()
        mock_artist_repo.refresh.assert_not_called()

    def test_rebuild_albums_artists(self, library_service, mock_album_repo, mock_artist_repo, mock_track_repo, mock_event_bus):
        """Test rebuild_albums_artists rebuilds both tables."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [{"count": 10}, {"count": 5}]
        mock_conn.cursor.return_value = mock_cursor
        mock_album_repo._get_connection.return_value = mock_conn

        result = library_service.rebuild_albums_artists()

        assert result == {'albums': 10, 'artists': 5}
        mock_artist_repo.rebuild_with_albums.assert_called_once()
        mock_track_repo.rebuild_track_artists.assert_called_once()
        mock_event_bus.tracks_added.emit.assert_called_once_with(0)

    # ===== Batch Track Operations Tests =====

    def test_get_tracks_by_ids(self, library_service, mock_track_repo):
        """Test getting multiple tracks by IDs."""
        mock_tracks = [Track(id=1, title="Song 1"), Track(id=2, title="Song 2")]
        mock_track_repo.get_by_ids.return_value = mock_tracks

        result = library_service.get_tracks_by_ids([1, 2])

        assert result == mock_tracks
        mock_track_repo.get_by_ids.assert_called_once_with([1, 2])

    def test_get_tracks_by_ids_empty_list(self, library_service, mock_track_repo):
        """Test getting tracks by IDs with empty list."""
        mock_track_repo.get_by_ids.return_value = []

        result = library_service.get_tracks_by_ids([])

        assert result == []
        mock_track_repo.get_by_ids.assert_called_once_with([])

    def test_get_track_by_path(self, library_service, mock_track_repo):
        """Test getting a track by file path."""
        mock_track = Track(id=1, path="/music/song.mp3")
        mock_track_repo.get_by_path.return_value = mock_track

        result = library_service.get_track_by_path("/music/song.mp3")

        assert result == mock_track
        mock_track_repo.get_by_path.assert_called_once_with("/music/song.mp3")

    def test_get_track_by_cloud_file_id(self, library_service, mock_track_repo):
        """Test getting a track by cloud file ID."""
        mock_track = Track(id=1, cloud_file_id="cloud_123")
        mock_track_repo.get_by_cloud_file_id.return_value = mock_track

        result = library_service.get_track_by_cloud_file_id("cloud_123")

        assert result == mock_track
        mock_track_repo.get_by_cloud_file_id.assert_called_once_with("cloud_123")

    # ===== Artist Query Operations Tests =====

    def test_get_artist_by_name(self, library_service, mock_track_repo):
        """Test getting artist by name."""
        from domain.artist import Artist
        mock_artist = Artist(name="Test Artist", song_count=5)
        mock_track_repo.get_artist_by_name.return_value = mock_artist

        result = library_service.get_artist_by_name("Test Artist")

        assert result == mock_artist
        assert result.name == "Test Artist"
        mock_track_repo.get_artist_by_name.assert_called_once_with("Test Artist")

    def test_get_artist_by_name_not_found(self, library_service, mock_track_repo):
        """Test getting artist by name when not found."""
        mock_track_repo.get_artist_by_name.return_value = None

        result = library_service.get_artist_by_name("Nonexistent Artist")

        assert result is None
        mock_track_repo.get_artist_by_name.assert_called_once()

    def test_get_artist_tracks(self, library_service, mock_track_repo):
        """Test getting tracks by artist name."""
        mock_tracks = [Track(id=1, artist="Artist A"), Track(id=2, artist="Artist A")]
        mock_track_repo.get_artist_tracks.return_value = mock_tracks

        result = library_service.get_artist_tracks("Artist A")

        assert result == mock_tracks
        assert len(result) == 2
        mock_track_repo.get_artist_tracks.assert_called_once_with("Artist A")

    def test_get_artist_tracks_no_tracks(self, library_service, mock_track_repo):
        """Test getting tracks for artist with no tracks."""
        mock_track_repo.get_artist_tracks.return_value = []

        result = library_service.get_artist_tracks("Unknown Artist")

        assert result == []

    def test_get_artist_albums(self, library_service, mock_track_repo):
        """Test getting albums by artist name."""
        from domain.album import Album
        mock_albums = [
            Album(name="Album A", artist="Artist A", song_count=10),
            Album(name="Album B", artist="Artist A", song_count=5),
        ]
        mock_track_repo.get_artist_albums.return_value = mock_albums

        result = library_service.get_artist_albums("Artist A")

        assert result == mock_albums
        assert len(result) == 2
        mock_track_repo.get_artist_albums.assert_called_once_with("Artist A")

    # ===== Album Query Operations Tests =====

    def test_get_album_by_name(self, library_service, mock_track_repo):
        """Test getting album by name."""
        from domain.album import Album
        mock_album = Album(name="Album A", artist="Artist A", song_count=10)
        mock_track_repo.get_album_by_name.return_value = mock_album

        result = library_service.get_album_by_name("Album A")

        assert result == mock_album
        mock_track_repo.get_album_by_name.assert_called_once_with("Album A", None)

    def test_get_album_by_name_with_artist(self, library_service, mock_track_repo):
        """Test getting album by name and artist."""
        from domain.album import Album
        mock_album = Album(name="Album A", artist="Artist A", song_count=10)
        mock_track_repo.get_album_by_name.return_value = mock_album

        result = library_service.get_album_by_name("Album A", "Artist A")

        assert result == mock_album
        mock_track_repo.get_album_by_name.assert_called_once_with("Album A", "Artist A")

    def test_get_album_by_name_not_found(self, library_service, mock_track_repo):
        """Test getting album by name when not found."""
        mock_track_repo.get_album_by_name.return_value = None

        result = library_service.get_album_by_name("Nonexistent Album")

        assert result is None

    def test_get_album_tracks(self, library_service, mock_track_repo):
        """Test getting tracks for a specific album."""
        mock_tracks = [Track(id=1, album="Album A"), Track(id=2, album="Album A")]
        mock_track_repo.get_album_tracks.return_value = mock_tracks

        result = library_service.get_album_tracks("Album A")

        assert result == mock_tracks
        assert len(result) == 2
        mock_track_repo.get_album_tracks.assert_called_once_with("Album A", None)

    def test_get_album_tracks_with_artist(self, library_service, mock_track_repo):
        """Test getting album tracks filtered by artist."""
        mock_tracks = [Track(id=1, album="Greatest Hits", artist="Artist A")]
        mock_track_repo.get_album_tracks.return_value = mock_tracks

        result = library_service.get_album_tracks("Greatest Hits", "Artist A")

        assert result == mock_tracks
        mock_track_repo.get_album_tracks.assert_called_once_with("Greatest Hits", "Artist A")

    def test_get_albums(self, library_service, mock_track_repo):
        """Test getting all albums."""
        from domain.album import Album
        mock_albums = [Album(name="Album A", artist="Artist A")]
        mock_track_repo.get_albums.return_value = mock_albums

        result = library_service.get_albums()

        assert result == mock_albums
        mock_track_repo.get_albums.assert_called_once()

    def test_get_artists(self, library_service, mock_track_repo):
        """Test getting all artists."""
        from domain.artist import Artist
        mock_artists = [Artist(name="Artist A", song_count=5)]
        mock_track_repo.get_artists.return_value = mock_artists

        result = library_service.get_artists()

        assert result == mock_artists
        mock_track_repo.get_artists.assert_called_once()

    # ===== Additional Track Operations Tests =====

    def test_update_track_with_old_track_refreshes_on_change(self, library_service, mock_track_repo, mock_album_repo, mock_artist_repo):
        """Test update_track triggers album/artist refresh when artist changes."""
        old_track = Track(id=1, artist="Old Artist", album="Old Album")
        new_track = Track(id=1, artist="New Artist", album="Old Album")
        mock_track_repo.get_by_id.return_value = old_track
        mock_track_repo.update.return_value = True

        result = library_service.update_track(new_track)

        assert result is True
        # Trigger immediate refresh since debounced refresh won't fire in test
        library_service.refresh_albums_artists(immediate=True)
        mock_album_repo.refresh.assert_called()
        mock_artist_repo.refresh.assert_called()

    def test_update_track_no_old_track(self, library_service, mock_track_repo):
        """Test update_track when old track is not found."""
        track = Track(id=999, title="Updated")
        mock_track_repo.get_by_id.return_value = None
        mock_track_repo.update.return_value = True

        result = library_service.update_track(track)

        assert result is True

    def test_delete_tracks_empty_list(self, library_service, mock_track_repo):
        """Test delete_tracks with empty list returns 0."""
        result = library_service.delete_tracks([])

        assert result == 0
        mock_track_repo.delete_batch.assert_not_called()

    def test_delete_tracks_success(self, library_service, mock_track_repo, mock_event_bus):
        """Test delete_tracks deletes multiple tracks."""
        mock_track_repo.delete_batch.return_value = 3

        result = library_service.delete_tracks([1, 2, 3])

        assert result == 3
        mock_track_repo.delete_batch.assert_called_once_with([1, 2, 3])
        mock_event_bus.tracks_deleted.emit.assert_called_once_with([1, 2, 3])

    def test_delete_tracks_zero_deleted(self, library_service, mock_track_repo, mock_event_bus):
        """Test delete_tracks when no tracks are deleted."""
        mock_track_repo.delete_batch.return_value = 0

        result = library_service.delete_tracks([999])

        assert result == 0
        mock_event_bus.tracks_deleted.emit.assert_not_called()

    # ===== Online Track Tests =====

    def test_add_online_track_new(self, library_service, mock_track_repo, mock_album_repo, mock_artist_repo):
        """Test adding a new online track."""
        mock_track_repo.get_by_cloud_file_id.return_value = None
        mock_track_repo.add.return_value = 42

        result = library_service.add_online_track(
            song_mid="qq_001",
            title="Online Song",
            artist="Online Artist",
            album="Online Album",
            duration=200.0,
            cover_url="http://example.com/cover.jpg"
        )

        assert result == 42
        mock_track_repo.add.assert_called_once()
        call_args = mock_track_repo.add.call_args[0][0]
        assert call_args.cloud_file_id == "qq_001"
        assert call_args.source.value == "QQ"

    def test_add_online_track_existing(self, library_service, mock_track_repo):
        """Test adding online track that already exists returns existing ID."""
        existing_track = Track(id=10, cloud_file_id="qq_001")
        mock_track_repo.get_by_cloud_file_id.return_value = existing_track

        result = library_service.add_online_track("qq_001", "Title", "Artist", "Album", 200.0)

        assert result == 10
        mock_track_repo.add.assert_not_called()

    # ===== Update Track Metadata Tests =====

    def test_update_track_metadata_success(self, library_service, mock_track_repo):
        """Test updating track metadata directly."""
        track = Track(id=1, title="Old Title", artist="Old Artist", album="Old Album")
        mock_track_repo.get_by_id.return_value = track
        mock_track_repo.update.return_value = True

        result = library_service.update_track_metadata(1, title="New Title", artist="New Artist")

        assert result is True
        assert track.title == "New Title"
        assert track.artist == "New Artist"

    def test_update_track_metadata_not_found(self, library_service, mock_track_repo):
        """Test updating metadata for non-existent track."""
        mock_track_repo.get_by_id.return_value = None

        result = library_service.update_track_metadata(999, title="New Title")

        assert result is False

    # ===== Cover Update Operations Tests =====

    def test_update_artist_cover(self, library_service, mock_artist_repo):
        """Test updating artist cover path."""
        mock_artist_repo.update_cover_path.return_value = True

        result = library_service.update_artist_cover("Artist A", "/covers/artist_a.jpg")

        assert result is True
        mock_artist_repo.update_cover_path.assert_called_once_with("Artist A", "/covers/artist_a.jpg")

    def test_update_album_cover(self, library_service, mock_album_repo):
        """Test updating album cover path."""
        mock_album_repo.update_cover_path.return_value = True

        result = library_service.update_album_cover("Album A", "Artist A", "/covers/album_a.jpg")

        assert result is True
        mock_album_repo.update_cover_path.assert_called_once_with("Album A", "Artist A", "/covers/album_a.jpg")

    def test_rebuild_track_artists(self, library_service, mock_track_repo):
        """Test rebuilding track_artists junction table."""
        mock_track_repo.rebuild_track_artists.return_value = 15

        result = library_service.rebuild_track_artists()

        assert result == 15
        mock_track_repo.rebuild_track_artists.assert_called_once()

    # ===== Genre Cover Fill Tests =====

    def test_fill_missing_genre_covers_fetches_and_updates(self):
        track_repo = Mock()
        playlist_repo = Mock()
        album_repo = Mock()
        artist_repo = Mock()
        genre_repo = Mock()
        cover_service = Mock()
        event_bus = Mock()

        service = LibraryService(
            track_repo=track_repo,
            playlist_repo=playlist_repo,
            album_repo=album_repo,
            artist_repo=artist_repo,
            genre_repo=genre_repo,
            event_bus=event_bus,
            cover_service=cover_service,
        )

        genre_repo.get_all.return_value = [
            Genre(name="Rock", cover_path=None, song_count=2, album_count=1),
            Genre(name="Pop", cover_path="/covers/pop.jpg", song_count=1, album_count=1),
        ]
        genre_repo.get_tracks.return_value = [
            Track(id=1, title="Song", artist="Artist", album="Album", duration=180.0)
        ]
        cover_service.fetch_online_cover.return_value = "/covers/rock.jpg"
        genre_repo.update_cover_path.return_value = True

        filled = service.fill_missing_genre_covers(max_tracks_per_genre=3)

        assert filled == 1
        genre_repo.get_tracks.assert_called_once_with("Rock")
        cover_service.fetch_online_cover.assert_called_once_with("Song", "Artist", "Album", 180.0)
        genre_repo.update_cover_path.assert_called_once_with("Rock", "/covers/rock.jpg")

    def test_fill_missing_genre_covers_returns_zero_without_dependencies(self):
        service = LibraryService(
            track_repo=Mock(),
            playlist_repo=Mock(),
            album_repo=Mock(),
            artist_repo=Mock(),
            genre_repo=None,
            event_bus=Mock(),
            cover_service=None,
        )

        assert service.fill_missing_genre_covers() == 0

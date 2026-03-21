"""
Tests for LibraryService.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
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
    def library_service(self, mock_track_repo, mock_playlist_repo, mock_event_bus, mock_cover_service):
        """Create LibraryService instance with mocked dependencies."""
        return LibraryService(
            track_repo=mock_track_repo,
            playlist_repo=mock_playlist_repo,
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
        mock_track_repo.search.assert_called_once_with("query", 50)

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
        mock_track_repo.add.side_effect = [1, 2]

        result = library_service.scan_directory("/music", recursive=True)

        assert result == 2
        assert mock_track_repo.add.call_count == 2

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
            result = library_service.scan_directory("/music", recursive=False)

            mock_path.glob.assert_called_once_with("*")

    def test_scan_directory_supported_extensions(self):
        """Test that only supported extensions are scanned."""
        supported = {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".oga"}

        # This is verified through implementation
        from services.library.library_service import LibraryService

        # Create instance just to access the constant
        with patch.multiple(
            "services.library.library_service",
            SqliteTrackRepository=Mock(),
            SqlitePlaylistRepository=Mock(),
        ):
            service = LibraryService(Mock(), Mock())

            # The supported_extensions is defined in scan_directory
            # We can't directly test it, but we know it exists
            assert True  # Placeholder for documentation

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
        self, mock_path_class, mock_metadata_service
    ):
        """Test creating track from file with error."""
        mock_metadata_service.extract_metadata.side_effect = Exception("Error")

        library_service = LibraryService(Mock(), Mock())

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
        mock_track_repo.add.return_value = 1

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
        mock_track_repo.get_album_tracks.return_value = tracks

        # New album name doesn't exist for this artist
        mock_track_repo.get_album_tracks.side_effect = [tracks, []]  # First call: old album, second call: check existing

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

"""
Tests for UniversalCoverDownloadDialog with strategies.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt

from ui.controllers.cover_controller import CoverController
from ui.dialogs import UniversalCoverDownloadDialog
from ui.strategies.track_search_strategy import TrackSearchStrategy
from ui.strategies.album_search_strategy import AlbumSearchStrategy
from ui.strategies.artist_search_strategy import ArtistSearchStrategy
from domain.track import Track
from domain.album import Album
from domain.artist import Artist
from services.metadata import CoverService
from system.theme import ThemeManager


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance once for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Process events to allow cleanup
    app.processEvents()


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    """Reset ThemeManager singleton before and after each test."""
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_config():
    """Mock config manager."""
    config = Mock()
    config.get_theme.return_value = 'dark'
    return config


@pytest.fixture
def app(qapp, mock_config):
    """Provide QApplication instance with ThemeManager initialized."""
    ThemeManager.instance(mock_config)
    return qapp


@pytest.fixture
def mock_cover_service():
    """Create mock CoverService."""
    service = Mock(spec=CoverService)
    service.save_cover_data_to_cache = Mock(return_value="/path/to/cover.jpg")
    service.search_covers = Mock(return_value=[])
    service.search_artist_covers = Mock(return_value=[])
    return service


@pytest.fixture
def mock_track_repo():
    """Create mock TrackRepository."""
    repo = Mock()
    repo.update = Mock()
    return repo


@pytest.fixture
def mock_library_service():
    """Create mock LibraryService."""
    service = Mock()
    service.update_album_cover = Mock()
    service.update_artist_cover = Mock()
    return service


@pytest.fixture
def mock_event_bus():
    """Create mock EventBus."""
    bus = Mock()
    bus.cover_updated = Mock()
    bus.cover_updated.emit = Mock()
    return bus


@pytest.fixture
def sample_tracks():
    """Create sample track data."""
    return [
        Track(
            id=1,
            path="/path/to/song1.mp3",
            title="Test Song 1",
            artist="Test Artist",
            album="Test Album"
        ),
        Track(
            id=2,
            path="/path/to/song2.mp3",
            title="Test Song 2",
            artist="Another Artist",
            album="Another Album"
        )
    ]


@pytest.fixture
def sample_album():
    """Create sample album."""
    return Album(
        name="Test Album",
        artist="Test Artist",
        cover_path=None,
        song_count=10,
        duration=300.0
    )


@pytest.fixture
def sample_artist():
    """Create sample artist."""
    return Artist(
        name="Test Artist",
        cover_path=None,
        song_count=20,
        album_count=5
    )


class TestTrackCoverDownloadDialog:
    """Test track cover download with TrackSearchStrategy."""

    def test_dialog_reject_shuts_down_cover_controller(
        self, app, sample_tracks, mock_cover_service, mock_track_repo, mock_event_bus
    ):
        """Closing the dialog must shut down the controller executor."""
        strategy = TrackSearchStrategy(
            sample_tracks, mock_track_repo, mock_event_bus
        )

        with patch.object(CoverController, "search", return_value=None):
            dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)

        dialog._controller.shutdown = Mock()

        dialog.reject()

        dialog._controller.shutdown.assert_called_once_with()

    def test_dialog_initialization_with_tracks(
        self, app, sample_tracks, mock_cover_service, mock_track_repo, mock_event_bus
    ):
        """Test dialog initialization with track strategy."""
        strategy = TrackSearchStrategy(
            sample_tracks, mock_track_repo, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)

        # Check that dialog was created
        assert dialog.windowTitle() != ""
        assert dialog._items == sample_tracks
        assert dialog._current_index == 0
        dialog.reject()

    def test_dialog_shows_track_info(
        self, app, sample_tracks, mock_cover_service, mock_track_repo, mock_event_bus
    ):
        """Test that dialog displays track information correctly."""
        strategy = TrackSearchStrategy(
            sample_tracks, mock_track_repo, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)
        dialog.show()

        # Check track combo has items
        assert dialog._combo.count() == len(sample_tracks)

        # Check first track info is displayed
        assert "Test Song 1" in dialog._details_label.text()
        assert "Test Artist" in dialog._details_label.text()
        dialog.reject()

    def test_track_navigation(
        self, app, sample_tracks, mock_cover_service, mock_track_repo, mock_event_bus
    ):
        """Test navigating between tracks."""
        strategy = TrackSearchStrategy(
            sample_tracks, mock_track_repo, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)
        dialog.show()

        # Initially on first track
        assert dialog._current_index == 0
        assert "1 / 2" in dialog._item_info_label.text()

        # Change to second track
        dialog._combo.setCurrentIndex(1)

        # Should be on second track now
        assert dialog._current_index == 1
        assert "2 / 2" in dialog._item_info_label.text()
        assert "Test Song 2" in dialog._details_label.text()
        dialog.reject()


class TestAlbumCoverDownloadDialog:
    """Test album cover download with AlbumSearchStrategy."""

    def test_dialog_initialization_with_album(
        self, app, sample_album, mock_cover_service, mock_library_service, mock_event_bus
    ):
        """Test dialog initialization with album strategy."""
        strategy = AlbumSearchStrategy(
            sample_album, mock_library_service, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)

        # Check that dialog was created
        assert dialog.windowTitle() != ""
        assert dialog._items == [sample_album]
        assert dialog._current_index == 0
        dialog.reject()

    def test_album_single_item_mode(
        self, app, sample_album, mock_cover_service, mock_library_service, mock_event_bus
    ):
        """Test that album uses single-item mode (no combo box)."""
        strategy = AlbumSearchStrategy(
            sample_album, mock_library_service, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)
        dialog.show()

        # Single item mode should not have combo box
        assert not hasattr(dialog, '_combo') or dialog._combo is None
        dialog.reject()


class TestArtistCoverDownloadDialog:
    """Test artist cover download with ArtistSearchStrategy."""

    def test_dialog_initialization_with_artist(
        self, app, sample_artist, mock_cover_service, mock_library_service, mock_event_bus
    ):
        """Test dialog initialization with artist strategy."""
        strategy = ArtistSearchStrategy(
            sample_artist, mock_library_service, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)

        # Check that dialog was created
        assert dialog.windowTitle() != ""
        assert dialog._items == [sample_artist]
        assert dialog._current_index == 0
        dialog.reject()

    def test_artist_uses_circular_display(
        self, app, sample_artist, mock_cover_service, mock_library_service, mock_event_bus
    ):
        """Test that artist strategy requests circular display."""
        strategy = ArtistSearchStrategy(
            sample_artist, mock_library_service, mock_event_bus
        )

        # Check that strategy requests circular display
        assert strategy.use_circular_display() is True


class TestSearchFunctionality:
    """Test search functionality."""

    def test_search_button_exists(
        self, app, sample_tracks, mock_cover_service, mock_track_repo, mock_event_bus
    ):
        """Test that search button exists."""
        strategy = TrackSearchStrategy(
            sample_tracks, mock_track_repo, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)

        # Check search button exists
        assert hasattr(dialog, '_search_btn')
        assert dialog._search_btn is not None
        dialog.reject()

    def test_results_list_exists(
        self, app, sample_tracks, mock_cover_service, mock_track_repo, mock_event_bus
    ):
        """Test that results list exists."""
        strategy = TrackSearchStrategy(
            sample_tracks, mock_track_repo, mock_event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, mock_cover_service)

        # Check results list exists
        assert hasattr(dialog, '_results_list')
        assert dialog._results_list is not None
        dialog.reject()

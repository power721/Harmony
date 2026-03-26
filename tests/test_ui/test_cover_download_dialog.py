"""
Tests for TrackCoverDownloadDialog (CoverDownloadDialog alias).
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import Qt

from ui.dialogs import TrackCoverDownloadDialog, CoverDownloadDialog
from domain.track import Track
from services.metadata import CoverService


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication instance once for all tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app
    # Process events to allow cleanup
    app.processEvents()


@pytest.fixture
def app(qapp):
    """Provide QApplication instance."""
    return qapp


@pytest.fixture
def mock_cover_service():
    """Create mock CoverService."""
    service = Mock(spec=CoverService)
    service.save_cover_data_to_cache = Mock(return_value="/path/to/cover.jpg")
    service.search_covers = Mock(return_value=[])
    return service


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


class TestCoverDownloadDialog:
    """Test CoverDownloadDialog functionality."""

    def test_dialog_initialization(self, app, sample_tracks, mock_cover_service):
        """Test dialog initialization with tracks."""
        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)

        # Check that dialog was created
        # Window title is set via i18n t("download_cover_manual")
        assert dialog.windowTitle() != ""
        assert dialog.tracks == sample_tracks
        assert dialog.cover_service == mock_cover_service
        assert dialog.current_track_index == 0
        dialog.reject()

    def test_dialog_shows_track_info(self, app, sample_tracks, mock_cover_service):
        """Test that dialog displays track information correctly."""
        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)
        dialog.show()

        # Check track combo has items
        assert dialog.track_combo.count() == len(sample_tracks)

        # Check first track info is displayed
        assert "Test Song 1" in dialog.details_label.text()
        assert "Test Artist" in dialog.details_label.text()
        dialog.reject()

    def test_search_button_exists(self, app, sample_tracks, mock_cover_service):
        """Test that search button exists."""
        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)

        # Check search button exists
        assert hasattr(dialog, 'search_btn')
        assert dialog.search_btn is not None
        dialog.reject()

    def test_results_list_exists(self, app, sample_tracks, mock_cover_service):
        """Test that results list exists."""
        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)

        # Check results list exists
        assert hasattr(dialog, 'results_list')
        assert dialog.results_list is not None
        dialog.reject()

    @patch('ui.dialogs.track_cover_download_dialog.CoverSearchThread')
    def test_search_button_starts_thread(self, mock_thread_class, app, sample_tracks, mock_cover_service):
        """Test that search button starts search thread."""
        # Mock thread instance
        mock_thread = MagicMock()
        mock_thread.isRunning.return_value = False
        mock_thread_class.return_value = mock_thread

        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)

        # Reset mock before the actual test call
        mock_thread_class.reset_mock()

        # Click search button
        dialog._search_covers()

        # Verify thread was created and started
        mock_thread_class.assert_called()
        mock_thread.start.assert_called()
        dialog.reject()

    def test_track_navigation(self, app, sample_tracks, mock_cover_service):
        """Test navigating between tracks."""
        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)
        dialog.show()

        # Initially on first track
        assert dialog.current_track_index == 0
        assert "1 / 2" in dialog.track_info_label.text()

        # Change to second track
        dialog.track_combo.setCurrentIndex(1)

        # Should be on second track now
        assert dialog.current_track_index == 1
        assert "2 / 2" in dialog.track_info_label.text()
        assert "Test Song 2" in dialog.details_label.text()
        dialog.reject()

    @patch('app.Application.instance')
    def test_save_cover_updates_database(self, mock_app_instance, app, sample_tracks, mock_cover_service):
        """Test that saving cover updates database."""
        # Setup mocks
        mock_bootstrap = Mock()
        mock_track_repo = Mock()
        mock_bootstrap.track_repo = mock_track_repo

        mock_app = Mock()
        mock_app.bootstrap = mock_bootstrap
        mock_app_instance.return_value = mock_app

        dialog = CoverDownloadDialog(sample_tracks, mock_cover_service)
        dialog.current_cover_data = b"fake_cover_data"

        # Save cover
        dialog._save_cover()

        # Verify cover was saved to cache
        mock_cover_service.save_cover_data_to_cache.assert_called_once_with(
            b"fake_cover_data",
            sample_tracks[0].artist,
            sample_tracks[0].title,
            sample_tracks[0].album
        )

        # Verify track was updated in database
        mock_track_repo.update.assert_called_once()
        updated_track = mock_track_repo.update.call_args[0][0]
        assert updated_track.cover_path == "/path/to/cover.jpg"
        dialog.reject()

    def test_dialog_with_single_track(self, app, sample_tracks, mock_cover_service):
        """Test dialog with single track."""
        single_track = [sample_tracks[0]]
        dialog = CoverDownloadDialog(single_track, mock_cover_service)

        # Should have one item in combo
        assert dialog.track_combo.count() == 1
        assert "1 / 1" in dialog.track_info_label.text()
        dialog.reject()

    def test_dialog_handles_empty_track_list(self, app, mock_cover_service):
        """Test dialog behavior with empty track list."""
        dialog = CoverDownloadDialog([], mock_cover_service)

        # Should have no items
        assert dialog.track_combo.count() == 0
        dialog.reject()

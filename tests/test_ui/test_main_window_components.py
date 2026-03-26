"""
Tests for MainWindow components.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui.windows.components.sidebar import Sidebar
from ui.windows.components.lyrics_panel import LyricsPanel
from ui.windows.components.online_music_handler import OnlineMusicHandler


# Ensure QApplication exists for widget tests
@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


class TestSidebar:
    """Tests for Sidebar widget."""

    def test_init(self, qapp):
        """Test sidebar initialization."""
        sidebar = Sidebar()
        assert sidebar is not None

    def test_page_constants(self, qapp):
        """Test page index constants match stacked widget order in MainWindow."""
        # Stacked widget order:
        # 0: library_view, 1: cloud_drive_view, 2: playlist_view, 3: queue_view
        # 4: albums_view, 5: artists_view, 6: artist_view, 7: album_view, 8: online_music_view
        assert Sidebar.PAGE_LIBRARY == 0
        assert Sidebar.PAGE_CLOUD == 1
        assert Sidebar.PAGE_PLAYLISTS == 2
        assert Sidebar.PAGE_QUEUE == 3
        assert Sidebar.PAGE_ALBUMS == 4
        assert Sidebar.PAGE_ARTISTS == 5
        assert Sidebar.PAGE_ONLINE == 8
        # Special pages (not in stacked widget)
        assert Sidebar.PAGE_FAVORITES == 100
        assert Sidebar.PAGE_HISTORY == 101

    def test_signals_exist(self, qapp):
        """Test that all expected signals exist."""
        sidebar = Sidebar()

        assert hasattr(sidebar, 'page_requested')
        assert hasattr(sidebar, 'language_toggled')
        assert hasattr(sidebar, 'settings_requested')
        assert hasattr(sidebar, 'add_music_requested')

    def test_set_current_page(self, qapp):
        """Test setting current page."""
        sidebar = Sidebar()

        sidebar.set_current_page(Sidebar.PAGE_ALBUMS)

        # Check that the albums button is checked
        for idx, btn in sidebar._nav_buttons:
            if idx == Sidebar.PAGE_ALBUMS:
                assert btn.isChecked()
                break

    def test_update_settings_status(self, qapp):
        """Test updating settings status."""
        mock_config = Mock()
        mock_config.get_ai_enabled.return_value = True

        sidebar = Sidebar(config_manager=mock_config)
        sidebar.update_settings_status(True)

        # Button text should contain the checkmark
        assert "✅" in sidebar._settings_btn.text()


class TestLyricsPanel:
    """Tests for LyricsPanel widget."""

    def test_init(self, qapp):
        """Test panel initialization."""
        panel = LyricsPanel()
        assert panel is not None

    def test_signals_exist(self, qapp):
        """Test that all expected signals exist."""
        panel = LyricsPanel()

        assert hasattr(panel, 'download_requested')
        assert hasattr(panel, 'edit_requested')
        assert hasattr(panel, 'delete_requested')
        assert hasattr(panel, 'refresh_requested')
        assert hasattr(panel, 'open_location_requested')
        assert hasattr(panel, 'seek_requested')

    def test_set_lyrics(self, qapp):
        """Test setting lyrics content."""
        panel = LyricsPanel()

        panel.set_lyrics("Test lyrics content")

        # Should not raise any exceptions

    def test_set_no_lyrics(self, qapp):
        """Test setting no lyrics message."""
        panel = LyricsPanel()

        panel.set_no_lyrics()

        # Should not raise any exceptions


class TestOnlineMusicHandler:
    """Tests for OnlineMusicHandler."""

    def test_init(self, qapp):
        """Test handler initialization."""
        mock_playback = Mock()
        handler = OnlineMusicHandler(playback_service=mock_playback)

        assert handler is not None

    def test_play_online_track(self, qapp):
        """Test playing an online track."""
        mock_playback = Mock()
        mock_playback.engine = Mock()

        handler = OnlineMusicHandler(playback_service=mock_playback)

        handler.play_online_track(
            "song_mid_123",
            "/path/to/file.mp3",
            {"title": "Test Song", "artist": "Test Artist"}
        )

        # Verify engine was called
        mock_playback.engine.load_playlist_items.assert_called_once()
        mock_playback.engine.play.assert_called_once()

    def test_add_to_queue(self, qapp):
        """Test adding track to queue."""
        mock_playback = Mock()
        mock_playback.engine = Mock()
        mock_playback._schedule_save_queue = Mock()

        handler = OnlineMusicHandler(
            playback_service=mock_playback,
            status_callback=lambda msg: None
        )

        handler.add_to_queue(
            "song_mid_123",
            {"title": "Test Song", "artist": "Test Artist"}
        )

        mock_playback.engine.add_track.assert_called_once()
        mock_playback._schedule_save_queue.assert_called_once()


class TestSidebarWithConfig:
    """Tests for Sidebar with ConfigManager."""

    def test_ai_enabled_shows_checkmark(self, qapp):
        """Test that AI enabled shows checkmark in settings button."""
        mock_config = Mock()
        mock_config.get_ai_enabled.return_value = True

        sidebar = Sidebar(config_manager=mock_config)

        assert "✅" in sidebar._settings_btn.text()

    def test_ai_disabled_shows_gear(self, qapp):
        """Test that AI disabled shows gear emoji in settings button."""
        mock_config = Mock()
        mock_config.get_ai_enabled.return_value = False

        sidebar = Sidebar(config_manager=mock_config)

        assert "⚙️" in sidebar._settings_btn.text()

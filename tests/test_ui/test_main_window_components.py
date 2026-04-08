"""
Tests for MainWindow components.
"""

import pytest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PySide6.QtWidgets import QApplication
from domain.playback import PlaybackState

from ui.windows.main_window import MainWindow
from ui.windows.components.sidebar import Sidebar
from ui.windows.components.lyrics_panel import LyricsPanel
from ui.windows.components.online_music_handler import OnlineMusicHandler
from system.theme import ThemeManager


@pytest.fixture(scope="module")
def qapp():
    """Create QApplication for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    """Reset ThemeManager singleton before and after each test."""
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def mock_config():
    """Mock config manager for ThemeManager."""
    config = Mock()
    config.get.return_value = 'dark'
    return config


class TestSidebar:
    """Tests for Sidebar widget."""

    def test_init(self, qapp, mock_config):
        """Test sidebar initialization."""
        ThemeManager.instance(mock_config)
        sidebar = Sidebar()
        assert sidebar is not None

    def test_page_constants(self, qapp, mock_config):
        """Test page index constants match stacked widget order in MainWindow."""
        ThemeManager.instance(mock_config)
        # Stacked widget order:
        # 0: library_view, 1: cloud_drive_view, 2: playlist_view, 3: queue_view
        # 4: albums_view, 5: artists_view, 6: artist_view, 7: album_view, 8: genres_view
        assert Sidebar.PAGE_LIBRARY == 0
        assert Sidebar.PAGE_CLOUD == 1
        assert Sidebar.PAGE_PLAYLISTS == 2
        assert Sidebar.PAGE_QUEUE == 3
        assert Sidebar.PAGE_ALBUMS == 4
        assert Sidebar.PAGE_ARTISTS == 5
        assert Sidebar.PAGE_GENRES == 8
        assert not hasattr(Sidebar, "PAGE_ONLINE")
        # Special pages (not in stacked widget)
        assert Sidebar.PAGE_FAVORITES == 100
        assert Sidebar.PAGE_HISTORY == 101

    def test_signals_exist(self, qapp, mock_config):
        """Test that all expected signals exist."""
        ThemeManager.instance(mock_config)
        sidebar = Sidebar()

        assert hasattr(sidebar, 'page_requested')
        assert hasattr(sidebar, 'language_toggled')
        assert hasattr(sidebar, 'settings_requested')
        assert hasattr(sidebar, 'add_music_requested')

    def test_set_current_page(self, qapp, mock_config):
        """Test setting current page."""
        ThemeManager.instance(mock_config)
        sidebar = Sidebar()

        sidebar.set_current_page(Sidebar.PAGE_ALBUMS)

        # Check that the albums button is checked
        for idx, btn in sidebar._nav_buttons:
            if idx == Sidebar.PAGE_ALBUMS:
                assert btn.isChecked()
                break

    def test_update_settings_status(self, qapp, mock_config):
        """Test updating settings status."""
        ThemeManager.instance(mock_config)
        mock_config_ai = Mock()
        mock_config_ai.get_ai_enabled.return_value = True

        sidebar = Sidebar(config_manager=mock_config_ai)
        sidebar.update_settings_status(True)

        # Button text should contain the checkmark
        assert "✅" in sidebar._settings_btn.text()


class TestLyricsPanel:
    """Tests for LyricsPanel widget."""

    def test_init(self, qapp, mock_config):
        """Test panel initialization."""
        ThemeManager.instance(mock_config)
        panel = LyricsPanel()
        assert panel is not None

    def test_signals_exist(self, qapp, mock_config):
        """Test that all expected signals exist."""
        ThemeManager.instance(mock_config)
        panel = LyricsPanel()

        assert hasattr(panel, 'download_requested')
        assert hasattr(panel, 'edit_requested')
        assert hasattr(panel, 'delete_requested')
        assert hasattr(panel, 'refresh_requested')
        assert hasattr(panel, 'open_location_requested')
        assert hasattr(panel, 'seek_requested')

    def test_set_lyrics(self, qapp, mock_config):
        """Test setting lyrics content."""
        ThemeManager.instance(mock_config)
        panel = LyricsPanel()

        panel.set_lyrics("Test lyrics content")

        # Should not raise any exceptions

    def test_set_no_lyrics(self, qapp, mock_config):
        """Test setting no lyrics message."""
        ThemeManager.instance(mock_config)
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

    def test_resolve_provider_id_does_not_fallback_to_placeholder(self, qapp):
        """Missing provider metadata should not invent a non-existent provider id."""
        assert OnlineMusicHandler._resolve_provider_id(None, {}) == ""

    def test_resolve_provider_id_ignores_placeholder_source(self, qapp):
        """Legacy placeholder source should not override a real provider id."""
        assert OnlineMusicHandler._resolve_provider_id(None, {"source": "online"}) == ""
        assert OnlineMusicHandler._resolve_provider_id(
            None,
            {"source": "online", "provider_id": "qqmusic"},
        ) == "qqmusic"

    def test_play_online_tracks_respects_shuffle_mode(self, qapp):
        """Batch online playback should preserve shuffle semantics."""
        mock_playback = Mock()
        mock_playback.engine = Mock()
        mock_playback.engine.is_shuffle_mode.return_value = True

        bootstrap = Mock()
        bootstrap.library_service.add_online_track.side_effect = [101, 102]

        handler = OnlineMusicHandler(playback_service=mock_playback)

        with patch("app.bootstrap.Bootstrap.instance", return_value=bootstrap):
            handler.play_online_tracks(
                1,
                [
                    ("song_mid_1", {"title": "Song 1", "artist": "Artist 1"}),
                    ("song_mid_2", {"title": "Song 2", "artist": "Artist 2"}),
                ],
            )

        mock_playback.engine.load_playlist_items.assert_called_once()
        selected_item = mock_playback.engine.shuffle_and_play.call_args[0][0]

        assert selected_item.cloud_file_id == "song_mid_2"
        mock_playback.engine.shuffle_and_play.assert_called_once()
        mock_playback.engine.play_at.assert_called_once_with(0)


class TestMainWindowPlayerProxy:
    """Tests for the PlayerProxy exposed by MainWindow."""

    def test_player_proxy_exposes_play_local_tracks(self, qapp):
        """LibraryView batch playback should be supported through PlayerProxy."""
        playback = Mock()
        playback.engine = Mock()

        bootstrap = Mock()
        bootstrap.db = Mock()
        bootstrap.config = Mock()
        bootstrap.playback_service = playback
        bootstrap.library_service = Mock()
        bootstrap.favorites_service = Mock()
        bootstrap.play_history_service = Mock()
        bootstrap.cloud_account_service = Mock()
        bootstrap.cloud_file_service = Mock()

        theme_manager = Mock()
        event_bus = Mock()

        with patch("ui.windows.main_window.Bootstrap.instance", return_value=bootstrap), \
                patch("ui.windows.main_window.EventBus.instance", return_value=event_bus), \
                patch("ui.windows.main_window.ThemeManager.instance", return_value=theme_manager), \
                patch.object(MainWindow, "_setup_ui"), \
                patch.object(MainWindow, "_setup_connections"), \
                patch.object(MainWindow, "_setup_system_tray"), \
                patch.object(MainWindow, "_setup_hotkeys"), \
                patch.object(MainWindow, "_restore_settings"):
            window = MainWindow()

        window._player.play_local_tracks([1, 2, 3], start_index=1)

        playback.play_local_tracks.assert_called_once_with([1, 2, 3], start_index=1)

    def test_close_event_uses_playback_shutdown(self, qapp):
        """MainWindow shutdown should explicitly close playback backend resources."""
        cloud_download_service = SimpleNamespace(cleanup=Mock())
        download_manager = SimpleNamespace(
            cleanup=Mock(),
            download_completed=SimpleNamespace(disconnect=Mock()),
            download_failed=SimpleNamespace(disconnect=Mock()),
        )
        fake = SimpleNamespace(
            _now_playing_window=None,
            _config=SimpleNamespace(
                set_start_in_now_playing=Mock(),
                set_volume=Mock(),
                set_playback_position=Mock(),
                set_was_playing=Mock(),
                get_playback_source=Mock(return_value="local"),
                set_playback_source=Mock(),
                set_current_track_id=Mock(),
                clear_cloud_account_id=Mock(),
            ),
            _settings=SimpleNamespace(setValue=Mock()),
            saveGeometry=Mock(return_value=b"geometry"),
            _splitter=SimpleNamespace(saveState=Mock(return_value=b"splitter")),
            _save_view_state=Mock(),
            _player=SimpleNamespace(
                current_source="local",
                state=PlaybackState.PLAYING,
                current_track=None,
                volume=35,
                engine=SimpleNamespace(
                    position=Mock(return_value=1200),
                    current_index=0,
                    stop=Mock(),
                ),
            ),
            _playback=SimpleNamespace(
                begin_shutdown=Mock(),
                save_queue=Mock(),
                shutdown=Mock(),
                cleanup_download_workers=Mock(),
            ),
            _force_quit_requested=False,
            _scan_controller=None,
            _lyrics_controller=None,
            _event_bus=SimpleNamespace(
                track_changed=SimpleNamespace(disconnect=Mock()),
                position_changed=SimpleNamespace(disconnect=Mock()),
                playback_state_changed=SimpleNamespace(disconnect=Mock()),
                download_completed=SimpleNamespace(disconnect=Mock()),
            ),
            _on_track_changed=Mock(),
            _on_position_changed=Mock(),
            _on_playback_state_changed=Mock(),
            _on_cloud_download_completed=Mock(),
            _on_playlist_redownload_completed=Mock(),
            _on_playlist_redownload_failed=Mock(),
            _db=SimpleNamespace(close=Mock()),
        )
        event = SimpleNamespace(accept=Mock())

        with patch(
            "services.cloud.download_service.CloudDownloadService.instance",
            return_value=cloud_download_service,
        ), patch(
            "services.download.download_manager.DownloadManager.instance",
            return_value=download_manager,
        ):
            MainWindow.closeEvent(fake, event)

        fake._playback.begin_shutdown.assert_called_once_with()
        fake._playback.save_queue.assert_called_once_with(force=True)
        fake._playback.shutdown.assert_called_once_with()
        fake._player.engine.stop.assert_not_called()
        cloud_download_service.cleanup.assert_called_once_with()
        download_manager.cleanup.assert_called_once_with()
        fake._db.close.assert_called_once_with()
        event.accept.assert_called_once_with()


class TestSidebarWithConfig:
    """Tests for Sidebar with ConfigManager."""

    def test_ai_enabled_shows_checkmark(self, qapp, mock_config):
        """Test that AI enabled shows checkmark in settings button."""
        ThemeManager.instance(mock_config)
        mock_config_ai = Mock()
        mock_config_ai.get_ai_enabled.return_value = True

        sidebar = Sidebar(config_manager=mock_config_ai)

        assert "✅" in sidebar._settings_btn.text()

    def test_ai_disabled_shows_gear(self, qapp, mock_config):
        """Test that AI disabled shows gear emoji in settings button."""
        ThemeManager.instance(mock_config)
        mock_config_ai = Mock()
        mock_config_ai.get_ai_enabled.return_value = False

        sidebar = Sidebar(config_manager=mock_config_ai)

        assert "⚙️" in sidebar._settings_btn.text()

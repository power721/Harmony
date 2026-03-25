"""
Tests for EventBus system component.
"""

import pytest
from unittest.mock import Mock, MagicMock
from PySide6.QtCore import QObject


@pytest.fixture(autouse=True)
def reset_event_bus():
    """Reset EventBus singleton before and after each test for isolation."""
    from system.event_bus import EventBus
    EventBus.reset()
    yield
    EventBus.reset()


class TestEventBus:
    """Test EventBus singleton."""

    def test_singleton_instance(self):
        """Test that EventBus returns singleton instance."""
        from system.event_bus import EventBus

        instance1 = EventBus.instance()
        instance2 = EventBus.instance()

        assert instance1 is instance2
        assert isinstance(instance1, QObject)

    def test_signal_existence(self):
        """Test that all expected signals exist."""
        from system.event_bus import EventBus

        bus = EventBus.instance()

        # Playback signals
        assert hasattr(bus, "track_changed")
        assert hasattr(bus, "playback_state_changed")
        assert hasattr(bus, "position_changed")

        # Download signals
        assert hasattr(bus, "download_progress")
        assert hasattr(bus, "download_completed")
        assert hasattr(bus, "online_track_metadata_loaded")

        # UI signals
        assert hasattr(bus, "lyrics_loaded")
        assert hasattr(bus, "metadata_updated")

        # Library signals
        assert hasattr(bus, "tracks_added")
        assert hasattr(bus, "playlist_created")
        assert hasattr(bus, "playlist_deleted")
        assert hasattr(bus, "playlist_modified")

    def test_track_changed_signal_emission(self):
        """Test track_changed signal emission."""
        from system.event_bus import EventBus
        from domain.track import Track

        bus = EventBus.instance()
        mock_handler = Mock()
        bus.track_changed.connect(mock_handler)

        track = Track(id=1, title="Test Song")
        bus.track_changed.emit(track)

        mock_handler.assert_called_once()
        # Check that the handler was called with a Track or dict

    def test_playback_state_changed_signal(self):
        """Test playback_state_changed signal."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_handler = Mock()
        bus.playback_state_changed.connect(mock_handler)

        bus.playback_state_changed.emit("playing")

        mock_handler.assert_called_once_with("playing")

    def test_position_changed_signal(self):
        """Test position_changed signal."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_handler = Mock()
        bus.position_changed.connect(mock_handler)

        bus.position_changed.emit(5000)

        mock_handler.assert_called_once_with(5000)

    def test_tracks_added_signal(self):
        """Test tracks_added signal."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_handler = Mock()
        bus.tracks_added.connect(mock_handler)

        bus.tracks_added.emit(5)

        mock_handler.assert_called_once_with(5)

    def test_multiple_handlers(self):
        """Test multiple handlers can connect to same signal."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_handler1 = Mock()
        mock_handler2 = Mock()

        bus.track_changed.connect(mock_handler1)
        bus.track_changed.connect(mock_handler2)

        from domain.track import Track
        track = Track(id=1)
        bus.track_changed.emit(track)

        mock_handler1.assert_called_once()
        mock_handler2.assert_called_once()

    def test_disconnect_signal(self):
        """Test disconnecting from signal."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_handler = Mock()

        bus.track_changed.connect(mock_handler)
        bus.track_changed.disconnect(mock_handler)

        from domain.track import Track
        bus.track_changed.emit(Track(id=1))

        mock_handler.assert_not_called()

    def test_playlist_signals(self):
        """Test playlist-related signals."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_created = Mock()
        mock_deleted = Mock()
        mock_modified = Mock()

        bus.playlist_created.connect(mock_created)
        bus.playlist_deleted.connect(mock_deleted)
        bus.playlist_modified.connect(mock_modified)

        bus.playlist_created.emit(1)
        bus.playlist_deleted.emit(2)
        bus.playlist_modified.emit(3)

        mock_created.assert_called_once_with(1)
        mock_deleted.assert_called_once_with(2)
        mock_modified.assert_called_once_with(3)

    def test_download_signals(self):
        """Test download-related signals."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_progress = Mock()
        mock_completed = Mock()

        bus.download_progress.connect(mock_progress)
        bus.download_completed.connect(mock_completed)

        bus.download_progress.emit("file_id", 50, 100)
        bus.download_completed.emit("file_id", "/path/to/file")

        mock_progress.assert_called_once_with("file_id", 50, 100)
        mock_completed.assert_called_once_with("file_id", "/path/to/file")

    def test_online_track_metadata_loaded_signal(self):
        """Test online_track_metadata_loaded signal."""
        from system.event_bus import EventBus

        bus = EventBus.instance()
        mock_handler = Mock()

        bus.online_track_metadata_loaded.connect(mock_handler)

        metadata = {"title": "Test Song", "artist": "Test Artist"}
        bus.online_track_metadata_loaded.emit("song_mid_123", metadata)

        mock_handler.assert_called_once_with("song_mid_123", metadata)

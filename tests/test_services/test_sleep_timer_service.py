"""Tests for SleepTimerService."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from PySide6.QtCore import QTimer

from services.playback.sleep_timer_service import SleepTimerService, SleepTimerConfig


@pytest.fixture
def mock_playback_service():
    """Create mock playback service."""
    service = Mock()
    service.volume = 50
    service.set_volume = Mock()
    service.stop = Mock()
    return service


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    bus = Mock()
    bus.track_finished = Mock()
    bus.track_finished.connect = Mock()
    bus.track_finished.disconnect = Mock()
    return bus


@pytest.fixture
def sleep_timer_service(mock_playback_service, mock_event_bus):
    """Create sleep timer service instance."""
    return SleepTimerService(mock_playback_service, mock_event_bus)


class TestSleepTimerService:
    """Test cases for SleepTimerService."""

    def test_initial_state(self, sleep_timer_service):
        """Test initial state is inactive."""
        assert not sleep_timer_service.is_active
        assert sleep_timer_service.remaining == 0
        assert sleep_timer_service.config is None

    def test_start_time_mode(self, sleep_timer_service, mock_event_bus):
        """Test starting time-based timer."""
        config = SleepTimerConfig(
            mode='time',
            value=60,  # 60 seconds
            action='stop',
            fade_out=False
        )
        sleep_timer_service.start(config)

        assert sleep_timer_service.is_active
        assert sleep_timer_service.remaining == 60
        assert sleep_timer_service.config == config

        # Clean up
        sleep_timer_service.cancel()

    def test_start_track_mode(self, sleep_timer_service, mock_event_bus):
        """Test starting track-count timer."""
        config = SleepTimerConfig(
            mode='track',
            value=5,  # 5 tracks
            action='quit',
            fade_out=False
        )
        sleep_timer_service.start(config)

        assert sleep_timer_service.is_active
        assert sleep_timer_service.remaining == 5
        mock_event_bus.track_finished.connect.assert_called_once()

        # Clean up
        sleep_timer_service.cancel()

    def test_cancel_timer(self, sleep_timer_service, mock_event_bus):
        """Test canceling timer."""
        config = SleepTimerConfig(
            mode='time',
            value=60,
            action='stop',
            fade_out=False
        )
        sleep_timer_service.start(config)
        sleep_timer_service.cancel()

        assert not sleep_timer_service.is_active
        assert sleep_timer_service.remaining == 0
        assert sleep_timer_service.config is None

    def test_time_mode_tick(self, sleep_timer_service, mock_playback_service):
        """Test countdown in time mode."""
        config = SleepTimerConfig(
            mode='time',
            value=3,  # 3 seconds for quick test
            action='stop',
            fade_out=False
        )

        remaining_values = []
        sleep_timer_service.remaining_changed.connect(remaining_values.append)

        sleep_timer_service.start(config)

        # Simulate timer ticks
        sleep_timer_service._tick()
        sleep_timer_service._tick()
        sleep_timer_service._tick()

        # Should have triggered action and stopped
        assert not sleep_timer_service.is_active
        mock_playback_service.stop.assert_called_once()

    def test_track_mode_countdown(self, sleep_timer_service, mock_event_bus, mock_playback_service):
        """Test track count mode."""
        config = SleepTimerConfig(
            mode='track',
            value=2,  # 2 tracks
            action='stop',
            fade_out=False
        )

        # Mock playlist for queue advancement
        mock_playback_service._engine.current_index = 0
        mock_playback_service._engine.playlist_items = [Mock(), Mock(), Mock()]  # 3 tracks

        sleep_timer_service.start(config)

        # Simulate track finished events
        sleep_timer_service._on_track_finished()
        assert sleep_timer_service.remaining == 1

        sleep_timer_service._on_track_finished()
        # Should have triggered action and stopped
        assert not sleep_timer_service.is_active
        mock_playback_service.stop.assert_called_once()
        # Should have set prevent_auto_next flag
        mock_playback_service._engine.set_prevent_auto_next.assert_called_once_with(True)
        # Should have advanced queue index to next track via restore_state
        mock_playback_service._engine.restore_state.assert_called()

    def test_fade_out_volume(self, sleep_timer_service, mock_playback_service, qtbot):
        """Test volume fade out."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='stop',
            fade_out=True
        )

        mock_playback_service.volume = 100
        sleep_timer_service.start(config)

        # Trigger action
        sleep_timer_service._trigger_action()

        # Should start fade out - wait a bit for timer to start
        qtbot.wait(100)
        assert sleep_timer_service._fade_timer.isActive()

        # Clean up
        sleep_timer_service.cancel()

    def test_quit_action(self, sleep_timer_service, mock_playback_service):
        """Test quit action."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='quit',
            fade_out=False
        )

        sleep_timer_service.start(config)

        with patch('PySide6.QtWidgets.QApplication') as mock_app:
            mock_instance = Mock()
            mock_app.instance.return_value = mock_instance

            sleep_timer_service._execute_action()

            mock_playback_service.stop.assert_called_once()
            mock_instance.quit.assert_called_once()

        sleep_timer_service.cancel()

    def test_shutdown_action_windows(self, sleep_timer_service, mock_playback_service):
        """Test shutdown action on Windows."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='shutdown',
            fade_out=False
        )

        sleep_timer_service.start(config)

        with patch('sys.platform', 'win32'):
            with patch('os.system') as mock_system:
                sleep_timer_service._execute_action()
                mock_system.assert_called_once_with('shutdown /s /t 0')

        sleep_timer_service.cancel()

    def test_shutdown_action_linux(self, sleep_timer_service, mock_playback_service):
        """Test shutdown action on Linux."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='shutdown',
            fade_out=False
        )

        sleep_timer_service.start(config)

        with patch('sys.platform', 'linux'):
            with patch('os.system') as mock_system:
                sleep_timer_service._execute_action()
                mock_system.assert_called_once_with('shutdown now')

        sleep_timer_service.cancel()

    def test_signals_emitted(self, sleep_timer_service):
        """Test that signals are emitted correctly."""
        config = SleepTimerConfig(
            mode='time',
            value=10,
            action='stop',
            fade_out=False
        )

        # Track signals
        started_called = []
        stopped_called = []
        remaining_changed_called = []

        sleep_timer_service.timer_started.connect(lambda: started_called.append(True))
        sleep_timer_service.timer_stopped.connect(lambda: stopped_called.append(True))
        sleep_timer_service.remaining_changed.connect(lambda v: remaining_changed_called.append(v))

        sleep_timer_service.start(config)
        assert started_called

        sleep_timer_service.cancel()
        assert stopped_called

        assert 10 in remaining_changed_called

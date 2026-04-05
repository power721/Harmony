"""Tests for SleepTimerService."""

import warnings
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QObject, Signal

from services.playback.sleep_timer_service import SleepTimerService, SleepTimerConfig


class _QtEventBus(QObject):
    track_finished = Signal()


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

    def test_start_track_mode_does_not_warn_when_signal_not_preconnected(self, mock_playback_service):
        """Test starting track mode does not warn when no prior track signal connection exists."""
        event_bus = _QtEventBus()
        sleep_timer_service = SleepTimerService(mock_playback_service, event_bus)
        config = SleepTimerConfig(
            mode='track',
            value=1,
            action='stop',
            fade_out=False
        )

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            sleep_timer_service.start(config)

        sleep_timer_service.cancel()

        assert not any("Failed to disconnect" in str(w.message) for w in caught)

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
        # Should keep current index so restart restores the same track
        mock_playback_service._engine.restore_state.assert_not_called()

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

    # ===== _trigger_action Tests =====

    def test_trigger_action_stop_no_fade(self, sleep_timer_service, mock_playback_service):
        """Test _trigger_action executes stop without fade out."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='stop',
            fade_out=False
        )
        sleep_timer_service._config = config
        sleep_timer_service._is_active = True

        triggered = []
        sleep_timer_service.timer_triggered.connect(lambda: triggered.append(True))

        sleep_timer_service._trigger_action()

        assert not sleep_timer_service.is_active
        assert triggered
        mock_playback_service.stop.assert_called_once()

    def test_trigger_action_starts_fade_out(self, sleep_timer_service, mock_playback_service):
        """Test _trigger_action starts fade out when enabled."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='stop',
            fade_out=True
        )
        sleep_timer_service._config = config
        sleep_timer_service._is_active = True
        mock_playback_service.volume = 80

        sleep_timer_service._trigger_action()

        assert not sleep_timer_service.is_active
        assert sleep_timer_service._original_volume == 80
        assert sleep_timer_service._fade_steps == 20

    def test_trigger_action_quit(self, sleep_timer_service, mock_playback_service):
        """Test _trigger_action with quit action."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='quit',
            fade_out=False
        )
        sleep_timer_service._config = config
        sleep_timer_service._is_active = True

        with patch('PySide6.QtWidgets.QApplication') as mock_app:
            mock_instance = Mock()
            mock_app.instance.return_value = mock_instance

            sleep_timer_service._trigger_action()

            mock_playback_service.stop.assert_called_once()
            mock_instance.quit.assert_called_once()

    def test_trigger_action_shutdown(self, sleep_timer_service, mock_playback_service):
        """Test _trigger_action with shutdown action."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='shutdown',
            fade_out=False
        )
        sleep_timer_service._config = config
        sleep_timer_service._is_active = True

        with patch('sys.platform', 'linux'):
            with patch('os.system') as mock_system:
                sleep_timer_service._trigger_action()
                mock_system.assert_called_once_with('shutdown now')

    def test_trigger_action_emits_timer_triggered(self, sleep_timer_service, mock_playback_service):
        """Test _trigger_action emits timer_triggered signal."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='stop',
            fade_out=False
        )
        sleep_timer_service._config = config
        sleep_timer_service._is_active = True

        triggered = []
        sleep_timer_service.timer_triggered.connect(lambda: triggered.append(True))

        sleep_timer_service._trigger_action()

        assert len(triggered) == 1

    # ===== _fade_step Tests =====

    def test_fade_step_reduces_volume(self, sleep_timer_service, mock_playback_service):
        """Test _fade_step reduces volume by step size."""
        sleep_timer_service._original_volume = 100
        sleep_timer_service._fade_steps = 5
        mock_playback_service.volume = 100

        sleep_timer_service._fade_step()

        assert sleep_timer_service._fade_steps == 4
        mock_playback_service.set_volume.assert_called_once()

    def test_fade_step_calls_set_volume(self, sleep_timer_service, mock_playback_service):
        """Test _fade_step calls set_volume with correct value."""
        sleep_timer_service._original_volume = 100
        sleep_timer_service._fade_steps = 10
        mock_playback_service.volume = 100

        sleep_timer_service._fade_step()

        call_args = mock_playback_service.set_volume.call_args[0][0]
        assert call_args < 100  # Volume should decrease
        assert call_args >= 0    # Volume should not go negative

    def test_fade_step_does_not_go_below_zero(self, sleep_timer_service, mock_playback_service):
        """Test _fade_step clamps volume to 0."""
        sleep_timer_service._original_volume = 5
        sleep_timer_service._fade_steps = 10
        mock_playback_service.volume = 2

        sleep_timer_service._fade_step()

        call_args = mock_playback_service.set_volume.call_args[0][0]
        assert call_args >= 0

    def test_fade_step_zero_steps_executes_action(self, sleep_timer_service, mock_playback_service):
        """Test _fade_step executes action when fade_steps reaches 0."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='stop',
            fade_out=True
        )
        sleep_timer_service._config = config
        sleep_timer_service._fade_steps = 0

        sleep_timer_service._fade_step()

        mock_playback_service.stop.assert_called_once()

    def test_fade_step_volume_zero_original(self, sleep_timer_service, mock_playback_service):
        """Test _fade_step handles zero original volume gracefully."""
        sleep_timer_service._original_volume = 0
        sleep_timer_service._fade_steps = 5
        mock_playback_service.volume = 0

        # Should not crash when original_volume is 0
        sleep_timer_service._fade_step()

        assert sleep_timer_service._fade_steps == 4

    # ===== Track Mode with Fade Out Tests =====

    def test_track_mode_with_fade_out(self, sleep_timer_service, mock_event_bus, mock_playback_service):
        """Test track count mode with fade out enabled."""
        config = SleepTimerConfig(
            mode='track',
            value=1,
            action='stop',
            fade_out=True
        )
        mock_playback_service._engine.current_index = 0
        mock_playback_service._engine.playlist_items = [Mock(), Mock()]
        mock_playback_service.volume = 80

        sleep_timer_service.start(config)

        sleep_timer_service._on_track_finished()

        # Should have triggered fade out instead of immediate stop
        assert not sleep_timer_service.is_active
        assert sleep_timer_service._original_volume == 80

    def test_track_mode_last_track_index_reset(self, sleep_timer_service, mock_event_bus, mock_playback_service):
        """Test track mode keeps index unchanged even at last track."""
        config = SleepTimerConfig(
            mode='track',
            value=1,
            action='stop',
            fade_out=False
        )
        mock_playback_service._engine.current_index = 1
        mock_playback_service._engine.playlist_items = [Mock(), Mock()]  # 2 tracks, index=1 is last

        sleep_timer_service.start(config)
        sleep_timer_service._on_track_finished()

        # Should not mutate queue index during sleep timer action
        mock_playback_service._engine.restore_state.assert_not_called()

    # ===== Cancel with Volume Restoration Tests =====

    def test_cancel_restores_volume(self, sleep_timer_service, mock_playback_service):
        """Test canceling timer restores original volume."""
        config = SleepTimerConfig(
            mode='time',
            value=60,
            action='stop',
            fade_out=True
        )
        sleep_timer_service.start(config)
        sleep_timer_service._original_volume = 75

        sleep_timer_service.cancel()

        mock_playback_service.set_volume.assert_called_with(75)
        assert sleep_timer_service._original_volume is None

    def test_cancel_no_volume_to_restore(self, sleep_timer_service, mock_playback_service):
        """Test canceling timer when no volume was saved."""
        config = SleepTimerConfig(
            mode='time',
            value=60,
            action='stop',
            fade_out=False
        )
        sleep_timer_service.start(config)

        sleep_timer_service.cancel()

        mock_playback_service.set_volume.assert_not_called()

    # ===== Start Cancels Existing Timer =====

    def test_start_cancels_existing_timer(self, sleep_timer_service, mock_playback_service):
        """Test starting a new timer cancels the existing one."""
        config1 = SleepTimerConfig(mode='time', value=60, action='stop', fade_out=False)
        config2 = SleepTimerConfig(mode='time', value=30, action='quit', fade_out=False)

        sleep_timer_service.start(config1)
        assert sleep_timer_service.remaining == 60

        sleep_timer_service.start(config2)
        assert sleep_timer_service.remaining == 30
        assert sleep_timer_service.config.action == 'quit'

        sleep_timer_service.cancel()

    # ===== Execute Action Tests =====

    def test_execute_action_restores_volume_after_fade(self, sleep_timer_service, mock_playback_service):
        """Test _execute_action restores volume after fade out."""
        config = SleepTimerConfig(
            mode='time',
            value=1,
            action='stop',
            fade_out=True
        )
        sleep_timer_service._config = config
        sleep_timer_service._original_volume = 80
        mock_playback_service.volume = 0  # Volume was faded to 0

        sleep_timer_service._execute_action()

        # Volume should be restored before stopping
        # Last set_volume call should restore original volume
        assert mock_playback_service.set_volume.call_args_list[-1][0][0] == 80

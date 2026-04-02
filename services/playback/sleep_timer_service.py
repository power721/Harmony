"""Sleep timer service for scheduled playback actions."""

import os
import sys
import logging
from dataclasses import dataclass
from typing import Optional
from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)


@dataclass
class SleepTimerConfig:
    """Sleep timer configuration."""
    mode: str  # 'time' | 'track'
    value: int  # seconds (time mode) or track count (track mode)
    action: str  # 'stop' | 'quit' | 'shutdown'
    fade_out: bool


class SleepTimerService(QObject):
    """
    Sleep timer service that supports:
    - Time-based countdown
    - Track-count based triggering
    - Actions: stop, quit, shutdown
    - Volume fade out
    """

    # Signals
    remaining_changed = Signal(int)  # Remaining seconds or track count
    timer_started = Signal()
    timer_stopped = Signal()
    timer_triggered = Signal()

    def __init__(self, playback_service, event_bus):
        super().__init__()
        self._playback_service = playback_service
        self._event_bus = event_bus

        # Timer state
        self._config: Optional[SleepTimerConfig] = None
        self._remaining: int = 0
        self._is_active = False
        self._original_volume: Optional[int] = None

        # QTimer for countdown
        self._timer = QTimer()
        self._timer.timeout.connect(self._tick)

        # Fade out timer
        self._fade_timer = QTimer()
        self._fade_timer.timeout.connect(self._fade_step)
        self._fade_steps = 0

    @property
    def is_active(self) -> bool:
        """Check if timer is active."""
        return self._is_active

    @property
    def remaining(self) -> int:
        """Get remaining seconds or track count."""
        return self._remaining

    @property
    def config(self) -> Optional[SleepTimerConfig]:
        """Get current config."""
        return self._config

    def start(self, config: SleepTimerConfig):
        """Start the sleep timer with given configuration."""
        if self._is_active:
            self.cancel()

        self._config = config
        self._remaining = config.value
        self._is_active = True

        if config.mode == 'time':
            # Start countdown timer (1 second interval)
            self._timer.start(1000)
            logger.info(f"Started sleep timer: {config.value} seconds, action={config.action}")
        else:
            # Track mode: listen to track_finished event
            try:
                self._event_bus.track_finished.disconnect(self._on_track_finished)
            except TypeError:
                pass
            self._event_bus.track_finished.connect(self._on_track_finished)
            logger.info(f"Started sleep timer: {config.value} tracks, action={config.action}")

        self.timer_started.emit()
        self.remaining_changed.emit(self._remaining)

    def cancel(self):
        """Cancel the active timer."""
        if not self._is_active:
            return

        # Stop timers
        self._timer.stop()
        self._fade_timer.stop()

        # Disconnect track finished signal if in track mode
        if self._config and self._config.mode == 'track':
            try:
                self._event_bus.track_finished.disconnect(self._on_track_finished)
            except RuntimeError:
                pass  # Already disconnected

        # Restore volume if we saved it
        if self._original_volume is not None:
            self._playback_service.set_volume(self._original_volume)
            self._original_volume = None

        self._is_active = False
        self._config = None
        self._remaining = 0
        self._fade_steps = 0

        logger.info("Sleep timer cancelled")
        self.timer_stopped.emit()

    def _tick(self):
        """Timer tick handler for countdown mode."""
        self._remaining -= 1
        self.remaining_changed.emit(self._remaining)

        if self._remaining <= 0:
            self._timer.stop()
            self._trigger_action()

    def _on_track_finished(self):
        """Track finished handler for track count mode."""
        # Disconnect immediately to prevent re-entry
        try:
            self._event_bus.track_finished.disconnect(self._on_track_finished)
        except RuntimeError:
            return  # Already disconnected, skip

        self._remaining -= 1
        self.remaining_changed.emit(self._remaining)
        logger.info(f"Track finished, remaining: {self._remaining}")

        if self._remaining <= 0:
            # In track mode without fade out, prevent auto-next and trigger action immediately
            if not self._config.fade_out:
                logger.info("Track countdown finished, preventing auto-next and stopping playback")
                # Prevent AudioEngine from auto-playing next track
                self._playback_service._engine.set_prevent_auto_next(True)
            self._trigger_action()
        else:
            # Re-connect for next track
            self._event_bus.track_finished.connect(self._on_track_finished)

    def _trigger_action(self):
        """Trigger the configured action."""
        logger.info(f"Sleep timer triggered, action={self._config.action}")
        self._is_active = False
        self.timer_triggered.emit()

        # Start fade out if enabled
        if self._config.fade_out:
            self._start_fade_out()
        else:
            self._execute_action()

    def _start_fade_out(self):
        """Start volume fade out over 10 seconds."""
        self._original_volume = self._playback_service.volume
        self._fade_steps = 20  # 20 steps over 10 seconds (500ms each)

        logger.info(f"Starting fade out from volume {self._original_volume}")
        self._fade_timer.start(500)  # 500ms interval

    def _fade_step(self):
        """Reduce volume by one step."""
        if self._fade_steps <= 0:
            self._fade_timer.stop()
            self._execute_action()
            return

        current = self._playback_service.volume
        if self._original_volume:
            step_size = max(1, self._original_volume // 20)
            new_volume = max(0, current - step_size)
            self._playback_service.set_volume(new_volume)

        self._fade_steps -= 1

    def _execute_action(self):
        """Execute the final action."""
        action = self._config.action

        # Restore original volume before action (if fade out was enabled)
        if self._original_volume is not None:
            self._playback_service.set_volume(self._original_volume)
            logger.info(f"Restored volume to {self._original_volume}")
            self._original_volume = None

        # For track mode, advance to next track before stopping
        # So that when restarted, it will play the next song
        if self._config.mode == 'track':
            current_index = self._playback_service._engine.current_index
            playlist_length = len(self._playback_service._engine.playlist_items)
            if current_index >= 0 and current_index < playlist_length - 1:
                # Move to next track
                self._playback_service._engine.restore_state(
                    self._playback_service._engine.play_mode, current_index + 1
                )
                logger.info(f"Advanced queue index to next track: {current_index + 1}")
            elif current_index == playlist_length - 1:
                # At the last track, set index to -1 (no track)
                self._playback_service._engine.restore_state(
                    self._playback_service._engine.play_mode, -1
                )
                logger.info("At last track, queue index reset to -1")

        # Stop playback for all actions
        self._playback_service.stop()

        if action == 'stop':
            logger.info("Sleep timer: stopped playback")
        elif action == 'quit':
            logger.info("Sleep timer: quitting application")
            from PySide6.QtWidgets import QApplication
            QApplication.instance().quit()
        elif action == 'shutdown':
            logger.info("Sleep timer: shutting down system")
            self._shutdown_system()

    def _shutdown_system(self):
        """Shutdown the system (cross-platform)."""
        try:
            if sys.platform.startswith('win'):
                # Windows
                os.system('shutdown /s /t 0')
            elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                # Linux or macOS
                os.system('shutdown now')
            else:
                logger.warning(f"Unsupported platform for shutdown: {sys.platform}")
        except Exception as e:
            logger.error(f"Failed to shutdown system: {e}")

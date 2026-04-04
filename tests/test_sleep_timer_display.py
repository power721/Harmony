"""Test script to verify sleep timer display in PlayerControls."""

import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.bootstrap import Bootstrap
from services.playback.sleep_timer_service import SleepTimerConfig


def test_sleep_timer_display(qtbot):
    """Test sleep timer display functionality."""
    bootstrap = Bootstrap.instance()
    sleep_timer = bootstrap.sleep_timer_service

    time_config = SleepTimerConfig(
        mode='time',
        value=2,
        action='stop',
        fade_out=False
    )
    sleep_timer.start(time_config)

    qtbot.waitUntil(lambda: sleep_timer.remaining < time_config.value, timeout=3000)
    assert sleep_timer.is_active is True
    assert sleep_timer.remaining in {0, 1}

    sleep_timer.cancel()
    assert sleep_timer.is_active is False

    track_config = SleepTimerConfig(
        mode='track',
        value=3,
        action='stop',
        fade_out=False
    )
    sleep_timer.start(track_config)

    assert sleep_timer.is_active is True
    assert sleep_timer.remaining == 3

    sleep_timer.cancel()
    assert sleep_timer.is_active is False


if __name__ == "__main__":
    test_sleep_timer_display()

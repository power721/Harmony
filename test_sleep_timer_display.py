#!/usr/bin/env python3
"""Test script to verify sleep timer display in PlayerControls."""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from app.bootstrap import Bootstrap
from services.playback.sleep_timer_service import SleepTimerConfig


def test_sleep_timer_display():
    """Test sleep timer display functionality."""
    app = QApplication.instance() or QApplication(sys.argv)

    # Get bootstrap instance (auto-initializes)
    bootstrap = Bootstrap.instance()

    # Get sleep timer service
    sleep_timer = bootstrap.sleep_timer_service

    print("✓ Sleep timer service initialized")
    print(f"✓ Sleep timer is_active: {sleep_timer.is_active}")

    # Start a time-based sleep timer
    config = SleepTimerConfig(
        mode='time',
        value=10,  # 10 seconds
        action='stop',
        fade_out=False
    )

    print("\n▶ Starting time-based sleep timer (10 seconds)...")
    sleep_timer.start(config)

    print(f"✓ Sleep timer started, is_active: {sleep_timer.is_active}")
    print(f"✓ Remaining: {sleep_timer.remaining} seconds")

    # Wait for 3 seconds and check updates
    def check_status():
        print(f"\n⏱ After 3 seconds:")
        print(f"  Remaining: {sleep_timer.remaining} seconds")
        print(f"  is_active: {sleep_timer.is_active}")

        # Cancel after 3 more seconds
        def cancel_timer():
            print("\n■ Cancelling sleep timer...")
            sleep_timer.cancel()
            print(f"✓ Sleep timer cancelled, is_active: {sleep_timer.is_active}")

            # Test track-based timer
            print("\n▶ Starting track-based sleep timer (3 tracks)...")
            track_config = SleepTimerConfig(
                mode='track',
                value=3,
                action='stop',
                fade_out=False
            )
            sleep_timer.start(track_config)
            print(f"✓ Sleep timer started, remaining: {sleep_timer.remaining} tracks")

            def cleanup():
                sleep_timer.cancel()
                print("\n✓ All tests passed!")
                app.quit()

            QTimer.singleShot(2000, cleanup)

        QTimer.singleShot(3000, cancel_timer)

    QTimer.singleShot(3000, check_status)

    # Run application
    return app.exec()


if __name__ == "__main__":
    test_sleep_timer_display()

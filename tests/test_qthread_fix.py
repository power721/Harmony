"""
Test to verify QThread lifecycle fix.
"""
import sys
import time
from pathlib import Path
from PySide6.QtWidgets import QApplication
from unittest.mock import Mock

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.bootstrap import Bootstrap
from system.theme import ThemeManager


def _init_theme():
    """Initialize ThemeManager singleton for widget tests."""
    config = Mock()
    config.get.return_value = 'dark'
    ThemeManager._instance = None
    ThemeManager.instance(config)


def test_main_window_close(tmp_path):
    """Test that MainWindow closes without QThread errors."""
    from ui.windows.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    _init_theme()
    Bootstrap._instance = None
    bootstrap = Bootstrap.instance(str(tmp_path / "qthread-main-window.db"))

    # Create main window
    window = MainWindow()
    window.show()

    # Process events to ensure everything is initialized
    app.processEvents()
    time.sleep(0.5)

    # Close the window
    window.close()

    # Process events to ensure cleanup happens
    app.processEvents()
    time.sleep(0.5)

    bootstrap.shutdown_database()
    Bootstrap._instance = None

    print("MainWindow closed without QThread errors")


def test_lyrics_panel_cleanup(monkeypatch):
    """Test that LyricsController properly cleans up threads."""
    from ui.windows.components.lyrics_panel import LyricsPanel, LyricsController
    from services.lyrics.lyrics_service import LyricsService

    app = QApplication.instance() or QApplication(sys.argv)
    _init_theme()
    monkeypatch.setattr(LyricsService, "get_lyrics", classmethod(lambda cls, *_args, **_kwargs: ""))

    # Create panel and controller
    panel = LyricsPanel()
    mock_playback = Mock()
    mock_playback.current_track = None
    mock_library = Mock()

    controller = LyricsController(
        panel, mock_playback, mock_library
    )

    # Start a lyrics loading thread
    controller.load_lyrics_async(
        "/fake/path.mp3", "Test Song", "Test Artist"
    )

    # Give thread time to start
    app.processEvents()
    time.sleep(0.1)

    # Call cleanup
    controller.cleanup()

    # Verify threads are cleaned up
    assert controller._lyrics_thread is None
    assert controller._lyrics_download_thread is None

    print("LyricsController cleanup works correctly")


def test_lyrics_loader_interruption(monkeypatch):
    """Test that LyricsLoader respects interruption requests."""
    from services.lyrics.lyrics_loader import LyricsLoader
    from services.lyrics.lyrics_service import LyricsService

    QApplication.instance() or QApplication(sys.argv)
    monkeypatch.setattr(
        LyricsService,
        "get_lyrics",
        classmethod(lambda cls, *_args, **_kwargs: ""),
    )

    # Create a loader with a fake path (will take time to fail)
    loader = LyricsLoader("/fake/path.mp3", "Test", "Artist")
    loader.start()

    # Request interruption immediately
    loader.requestInterruption()

    # Wait for thread to finish
    if not loader.wait(2000):
        loader.terminate()
        loader.wait()
        assert False, "LyricsLoader did not respect interruption"


if __name__ == "__main__":
    print("Testing QThread lifecycle management fixes...")
    print()

    try:
        test_lyrics_loader_interruption()
    except Exception as e:
        print(f"LyricsLoader interruption test failed: {e}")

    try:
        test_lyrics_panel_cleanup()
    except Exception as e:
        print(f"LyricsPanel cleanup test failed: {e}")

    try:
        test_main_window_close()
    except Exception as e:
        print(f"MainWindow close test failed: {e}")

    print()
    print("All tests completed!")

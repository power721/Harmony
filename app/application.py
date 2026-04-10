"""
Application - Main application singleton.
"""

import logging
import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QApplication

from .bootstrap import Bootstrap

logger = logging.getLogger(__name__)


class Application(QObject):
    """
    Main application singleton.

    Manages application lifecycle and provides access to
    all core components through the bootstrap container.
    """

    _instance: Optional["Application"] = None
    _lock = threading.Lock()

    # Signals
    initialized = Signal()

    def __init__(self, qt_app: QApplication, db_path: str = "Harmony.db"):
        """
        Initialize application.

        Args:
            qt_app: QApplication instance
            db_path: Path to database file
        """
        super().__init__()

        self._qt_app = qt_app
        # Use Bootstrap singleton to avoid duplicate service instances
        self._bootstrap = Bootstrap.instance(db_path)
        self._main_window = None

    @classmethod
    def instance(cls) -> "Application":
        """Get singleton instance."""
        with cls._lock:
            if cls._instance is None:
                raise RuntimeError("Application has not been created")
            return cls._instance

    @classmethod
    def create(cls, qt_app: QApplication, db_path: str = "Harmony.db") -> "Application":
        """
        Create application instance.

        Args:
            qt_app: QApplication instance
            db_path: Path to database file

        Returns:
            Application instance
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(qt_app, db_path)
            return cls._instance

    @property
    def bootstrap(self) -> Bootstrap:
        """Get bootstrap container."""
        return self._bootstrap

    @property
    def config(self):
        """Get config manager."""
        return self._bootstrap.config

    @property
    def event_bus(self):
        """Get event bus."""
        return self._bootstrap.event_bus

    @property
    def playback(self):
        """Get playback service."""
        return self._bootstrap.playback_service

    @property
    def library(self):
        """Get library service."""
        return self._bootstrap.library_service

    @property
    def main_window(self):
        """Get main window."""
        return self._main_window

    def set_main_window(self, window):
        """Set main window."""
        self._main_window = window

    def _dispatch_to_ui(self, fn, *args, **kwargs):
        QTimer.singleShot(0, lambda: fn(*args, **kwargs))

    def run(self) -> int:
        """
        Run the application.

        Returns:
            Exit code
        """
        self.initialized.emit()

        # Clean up old image cache
        from infrastructure.cache import ImageCache
        try:
            ImageCache.cleanup(days=7)
        except Exception:
            logger.warning("Image cache cleanup failed", exc_info=True)

        # Start cache cleaner service
        cache_cleaner = self._bootstrap.cache_cleaner_service
        if cache_cleaner:
            try:
                cache_cleaner.start()
            except Exception:
                logger.warning("Cache cleaner start failed", exc_info=True)

        # Start MPRIS D-Bus service (Linux only)
        try:
            self._bootstrap.start_mpris(self._main_window, self._dispatch_to_ui)
        except Exception:
            logger.warning("MPRIS startup failed", exc_info=True)

        return self._qt_app.exec()

    def quit(self):
        """Quit the application."""
        # Stop MPRIS D-Bus service
        self._bootstrap.stop_mpris()

        from system import hotkeys
        hotkeys.cleanup()

        # Stop cache cleaner service
        cache_cleaner = self._bootstrap.cache_cleaner_service
        if cache_cleaner:
            cache_cleaner.stop()

        self._bootstrap.shutdown_database()

        self._qt_app.quit()

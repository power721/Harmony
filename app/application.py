"""
Application - Main application singleton.
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QObject, Signal

from .bootstrap import Bootstrap


logger = logging.getLogger(__name__)


class Application(QObject):
    """
    Main application singleton.

    Manages application lifecycle and provides access to
    all core components through the bootstrap container.
    """

    _instance: Optional["Application"] = None

    # Signals
    initialized = Signal()

    def __init__(self, qt_app: QApplication, db_path: str = "music_player.db"):
        """
        Initialize application.

        Args:
            qt_app: QApplication instance
            db_path: Path to database file
        """
        super().__init__()

        self._qt_app = qt_app
        self._bootstrap = Bootstrap(db_path)
        self._main_window = None

        Application._instance = self

    @classmethod
    def instance(cls) -> "Application":
        """Get singleton instance."""
        return cls._instance

    @classmethod
    def create(cls, qt_app: QApplication, db_path: str = "music_player.db") -> "Application":
        """
        Create application instance.

        Args:
            qt_app: QApplication instance
            db_path: Path to database file

        Returns:
            Application instance
        """
        if cls._instance is None:
            cls._instance = cls(qt_app, db_path)
        return cls._instance

    @property
    def bootstrap(self) -> Bootstrap:
        """Get bootstrap container."""
        return self._bootstrap

    @property
    def db(self):
        """Get database manager."""
        return self._bootstrap.db

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

    def run(self) -> int:
        """
        Run the application.

        Returns:
            Exit code
        """
        self.initialized.emit()
        return self._qt_app.exec()

    def quit(self):
        """Quit the application."""
        self._qt_app.quit()

"""
Harmony - Modern Music Player
A PySide6-based music player with a modern, Spotify-like interface.

Architecture:
    - app/        : Application bootstrap and dependency injection
    - domain/     : Pure domain models (no dependencies)
    - repositories: Data access abstraction layer
    - services/   : Business logic layer
    - infrastructure: Technical implementations
    - ui/         : PySide6 user interface
    - system/     : Application-wide components
"""

import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s - %(message)s'
)

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from app import Application
from ui import MainWindow


def main():
    """Main entry point for the application."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create Qt application
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName('Harmony')
    qt_app.setOrganizationName('HarmonyPlayer')
    qt_app.setWindowIcon(QIcon("icon.png"))

    # Set default font
    font = QFont('Segoe UI', 10)
    qt_app.setFont(font)

    # Create application with dependency injection
    app = Application.create(qt_app)

    # Create and show main window
    window = MainWindow()
    window.show()
    app.set_main_window(window)

    # Run event loop
    sys.exit(app.run())


if __name__ == '__main__':
    main()

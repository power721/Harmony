"""
Harmony - Modern Music Player
A PySide6-based music player with a modern, Spotify-like interface.
"""
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QIcon

from ui import MainWindow


def main():
    """Main entry point for the application."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName('Harmony')
    app.setOrganizationName('HarmonyPlayer')
    app.setWindowIcon(QIcon("icon.png"))

    # Set default font
    font = QFont('Segoe UI', 10)
    app.setFont(font)

    # Create and show main window
    window = MainWindow()
    window.show()

    # Run event loop
    sys.exit(app.exec())


if __name__ == '__main__':
    main()

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
import os
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QFont, QIcon

from app import Application
from ui import MainWindow

# Setup SSL certificates for PyInstaller bundle
def setup_ssl_certificates():
    """Setup SSL certificates for HTTPS connections in PyInstaller bundle."""
    # Check if running in PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = Path(sys._MEIPASS)

        # Try certifi bundled certificates
        certifi_cert = base_path / "certifi" / "cacert.pem"
        if certifi_cert.exists():
            os.environ['SSL_CERT_FILE'] = str(certifi_cert)
            os.environ['REQUESTS_CA_BUNDLE'] = str(certifi_cert)
            return

        # Try system bundled certificates
        system_cert = base_path / "certs" / "ca-certificates.crt"
        if system_cert.exists():
            os.environ['SSL_CERT_FILE'] = str(system_cert)
            os.environ['REQUESTS_CA_BUNDLE'] = str(system_cert)
            return

        # Fallback: try to use certifi at runtime
        try:
            import certifi
            os.environ['SSL_CERT_FILE'] = certifi.where()
            os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
        except ImportError:
            pass

# Setup SSL before any HTTPS requests
setup_ssl_certificates()


def get_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        base_path = Path(sys._MEIPASS)
    else:
        # Running in development
        base_path = Path(__file__).parent
    return base_path / relative_path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(name)s - %(message)s'
)

# Suppress verbose third-party library logging
logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
logging.getLogger("urllib3.util.retry").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)


def qt_message_handler(mode, context, message):
    """Filter out verbose Qt debug messages."""
    # Suppress specific Qt debug messages
    suppressed_messages = [
        "Using Qt multimedia with FFmpeg",
        "Parent future has",
        "AtSpiAdaptor::applicationInterface",
    ]

    # Only show warnings and above, or debug messages not in suppressed list
    if mode == QtMsgType.QtDebugMsg:
        if not any(suppressed in message for suppressed in suppressed_messages):
            logging.debug(f"Qt: {message}")
    elif mode == QtMsgType.QtWarningMsg:
        logging.warning(f"Qt: {message}")
    elif mode == QtMsgType.QtCriticalMsg:
        logging.error(f"Qt: {message}")
    elif mode == QtMsgType.QtFatalMsg:
        logging.critical(f"Qt: {message}")


def main():
    """Main entry point for the application."""
    # Install Qt message handler to filter verbose messages
    qInstallMessageHandler(qt_message_handler)

    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    # Create Qt application
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName('Harmony')
    qt_app.setOrganizationName('HarmonyPlayer')

    # Load bundled fonts
    from infrastructure.fonts import FontLoader
    FontLoader.instance().load_fonts()

    # Set application font
    font = QFont()
    font.setFamilies([
        "Inter",
        "Noto Sans SC",
        "Noto Color Emoji"
    ])
    qt_app.setFont(font)

    # Create application with dependency injection
    app = Application.create(qt_app)

    # Load and apply themed global stylesheet
    try:
        theme = app.bootstrap.theme
        theme.apply_global_stylesheet()
    except Exception as e:
        logging.warning(f"Failed to load themed stylesheet: {e}")
        try:
            qss_path = get_resource_path("ui/styles.qss")
            with open(qss_path, "r", encoding="utf-8") as f:
                qt_app.setStyleSheet(f.read())
        except Exception as e2:
            logging.warning(f"Failed to load stylesheet: {e2}")

    # Set window icon
    icon_path = get_resource_path("icon.png")
    if icon_path.exists():
        qt_app.setWindowIcon(QIcon(str(icon_path)))

    # Create and show main window
    window = MainWindow()
    window.show()
    app.set_main_window(window)

    # Run event loop
    sys.exit(app.run())


if __name__ == '__main__':
    main()

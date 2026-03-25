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

# Setup input method for Linux
def setup_input_method():
    """Setup input method environment for Chinese input on Linux."""
    if sys.platform == "linux":
        # Check if fcitx5 is running
        if os.path.exists("/usr/bin/fcitx5") or os.environ.get("QT_IM_MODULE") == "fcitx":
            # Add system Qt plugin path to load fcitx5 input method plugin
            # The system fcitx5 plugin is built for Qt 6.4.2 but may work with newer versions
            system_plugin_path = "/usr/lib/x86_64-linux-gnu/qt6/plugins"
            if os.path.exists(system_plugin_path):
                # Prepend system path to QT_PLUGIN_PATH
                current_path = os.environ.get("QT_PLUGIN_PATH", "")
                if current_path:
                    os.environ["QT_PLUGIN_PATH"] = f"{system_plugin_path}:{current_path}"
                else:
                    os.environ["QT_PLUGIN_PATH"] = system_plugin_path
            # Ensure QT_IM_MODULE is set
            if not os.environ.get("QT_IM_MODULE"):
                os.environ["QT_IM_MODULE"] = "fcitx"


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

# Setup input method before Qt application starts
setup_input_method()

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

    # Set default font
    font = QFont()
    font.setFamilies([
        "Inter",
        "Source Han Sans SC",
        "Noto Color Emoji"
    ])

    qt_app.setFont(font)

    # Load global stylesheet
    try:
        qss_path = get_resource_path("ui/styles.qss")
        with open(qss_path, "r", encoding="utf-8") as f:
            stylesheet = f.read()
            qt_app.setStyleSheet(stylesheet)
    except Exception as e:
        logging.warning(f"Failed to load stylesheet: {e}")

    # Set window icon
    icon_path = get_resource_path("icon.png")
    if icon_path.exists():
        qt_app.setWindowIcon(QIcon(str(icon_path)))

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

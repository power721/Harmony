"""
QML-based Mini Player.

A modern QML implementation of the mini player with:
- Native rounded corners (no mask hack)
- GPU-accelerated animations
- Declarative UI syntax
"""
import logging
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QWidget

from services.playback import PlaybackService
from .player_bridge import PlayerBridge

logger = logging.getLogger(__name__)


class QmlMiniPlayer(QObject):
    """
    QML-based Mini Player.

    This class creates a QML window and bridges it to the PlaybackService.
    It uses QQmlApplicationEngine to load the QML UI file.
    """

    # Signal compatible with existing MiniPlayer
    closed = Signal()

    def __init__(self, player: PlaybackService, parent=None):
        """
        Initialize QML Mini Player.

        Args:
            player: PlaybackService instance
            parent: Parent QObject (not used for QML windows)
        """
        super().__init__(parent)
        self._player = player
        self._engine: Optional[QQmlApplicationEngine] = None
        self._bridge: Optional[PlayerBridge] = None
        self._root_object = None

        self._setup_qml()

    def _get_qml_path(self) -> Path:
        """Get the path to the QML file."""
        # Development path
        qml_dir = Path(__file__).parent / "qml"
        qml_file = qml_dir / "MiniPlayer.qml"

        if qml_file.exists():
            return qml_file

        # PyInstaller bundle path
        if getattr(sys, 'frozen', False):
            base_path = Path(sys._MEIPASS)
            qml_file = base_path / "ui" / "qml_mini_player" / "qml" / "MiniPlayer.qml"
            if qml_file.exists():
                return qml_file

        raise FileNotFoundError(f"QML file not found: {qml_file}")

    def _setup_qml(self):
        """Setup QML engine and bridge."""
        # Create bridge
        self._bridge = PlayerBridge(self._player, self)

        # Connect bridge close signal
        self._bridge.closeRequested.connect(self._on_close_requested)

        # Create QML engine
        self._engine = QQmlApplicationEngine()

        # Expose bridge to QML
        root_context = self._engine.rootContext()
        root_context.setContextProperty("playerBridge", self._bridge)

        # Load QML file
        qml_path = self._get_qml_path()
        qml_url = QUrl.fromLocalFile(str(qml_path))

        self._engine.load(qml_url)

        # Get root object
        root_objects = self._engine.rootObjects()
        if not root_objects:
            raise RuntimeError("Failed to load QML file")

        self._root_object = root_objects[0]

        # Set bridge property on root
        self._root_object.setProperty("bridge", self._bridge)

    def _on_close_requested(self):
        """Handle close request from bridge."""
        self.close()

    def show(self):
        """Show the mini player."""
        if self._root_object:
            self._root_object.show()

    def hide(self):
        """Hide the mini player."""
        if self._root_object:
            self._root_object.hide()

    def close(self):
        """Close the mini player."""
        if self._root_object:
            # Disconnect signals before closing
            try:
                self._root_object.closing.disconnect()
            except RuntimeError:
                pass
            self._root_object.close()

        # Clean up
        if self._engine:
            self._engine.deleteLater()
            self._engine = None

        # Emit closed signal for compatibility
        self.closed.emit()

    def isVisible(self) -> bool:
        """Check if mini player is visible."""
        if self._root_object:
            return self._root_object.isVisible()
        return False

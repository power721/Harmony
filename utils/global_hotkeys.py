"""
Global hotkey support for media keys.

Note: True global hotkeys require platform-specific implementations:
- Windows: pynput, keyboard, or RegisterHotKey
- macOS: CGEventTap
- Linux: dbus (org.mpris.MediaPlayer2)

This is a simplified implementation using Qt's shortcuts
which work when the window has focus.
"""
import logging

from PySide6.QtWidgets import QApplication

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut

from player import PlayerController
from player.engine import PlayerState


class GlobalHotkeys(QObject):
    """
    Global hotkey manager.

    Note: This implementation uses Qt shortcuts which work when
    the application window has focus. For true global hotkeys
    (working when app is in background), you would need to use
    platform-specific APIs or integrate with MPRIS (Linux) or
    similar systems.
    """

    def __init__(self, player: PlayerController, window):
        """
        Initialize global hotkeys.

        Args:
            player: Player controller
            window: Main window to attach shortcuts to
        """
        super().__init__()

        self._player = player
        self._window = window

        self._setup_shortcuts()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Space - Play/Pause
        QShortcut(QKeySequence(Qt.Key_Space), self._window, self._toggle_play_pause)

        # Ctrl/Cmd + Left - Previous track
        QShortcut(
            QKeySequence("Ctrl+Left"),
            self._window,
            self._player.engine.play_previous
        )

        # Ctrl/Cmd + Right - Next track
        QShortcut(
            QKeySequence("Ctrl+Right"),
            self._window,
            self._player.engine.play_next
        )

        # Ctrl/Cmd + Up - Volume up
        QShortcut(
            QKeySequence("Ctrl+Up"),
            self._window,
            self._volume_up
        )

        # Ctrl/Cmd + Down - Volume down
        QShortcut(
            QKeySequence("Ctrl+Down"),
            self._window,
            self._volume_down
        )

        # Ctrl/Cmd + F - Toggle favorite
        QShortcut(
            QKeySequence("Ctrl+F"),
            self._window,
            self._toggle_favorite
        )

        # Ctrl/Cmd + M - Toggle mini mode
        QShortcut(
            QKeySequence("Ctrl+M"),
            self._window,
            self._toggle_mini_mode
        )

        # Ctrl/Cmd + Q - Quit
        QShortcut(
            QKeySequence("Ctrl+Q"),
            self._window,
            self._window.close
        )

        # Ctrl/Cmd + N - New playlist
        QShortcut(
            QKeySequence("Ctrl+N"),
            self._window,
            self._new_playlist
        )

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._player.engine.state == PlayerState.PLAYING:
            self._player.engine.pause()
        else:
            self._player.engine.play()

    def _volume_up(self):
        """Increase volume."""
        current_volume = self._player.engine.volume
        new_volume = min(100, current_volume + 5)
        self._player.engine.set_volume(new_volume)

    def _volume_down(self):
        """Decrease volume."""
        current_volume = self._player.engine.volume
        new_volume = max(0, current_volume - 5)
        self._player.engine.set_volume(new_volume)

    def _toggle_favorite(self):
        """Toggle favorite for current track."""
        self._player.toggle_favorite()

    def _toggle_mini_mode(self):
        """Toggle mini player mode."""
        # This would be connected to the main window's mini mode toggle
        # Implementation depends on how mini mode is integrated
        if hasattr(self._window, 'toggle_mini_mode'):
            self._window.toggle_mini_mode()

    def _new_playlist(self):
        """Create new playlist."""
        if hasattr(self._window, '_playlist_view'):
            self._window._playlist_view._create_playlist()


def setup_media_key_handler(player: PlayerController):
    """
    Setup media key handler using system-specific APIs.

    This is a placeholder for platform-specific implementations:
    - Windows: Use keyboard or pynput library
    - macOS: Use pyobjc to listen to media key events
    - Linux: Use MPRIS D-Bus interface

    Args:
        player: Player controller
    """
    try:
        # Try to setup platform-specific media key handling
        import platform

        system = platform.system()

        if system == "Linux":
            _setup_linux_media_keys(player)
        elif system == "Darwin":  # macOS
            _setup_macos_media_keys(player)
        elif system == "Windows":
            _setup_windows_media_keys(player)

    except Exception as e:
        logger.error(f"Could not setup media key handler: {e}", exc_info=True)


def _setup_linux_media_keys(player: PlayerController):
    """Setup media keys on Linux using MPRIS."""
    try:
        import dbus
        import dbus.service

        class MPRISPlayer(dbus.service.Object):
            """MPRIS2 D-Bus interface for Linux media keys."""

            def __init__(self, player_controller):
                bus_name = dbus.service.BusName('org.mpris.MediaPlayer2.Harmony', bus=dbus.SessionBus())
                path = '/org/mpris/MediaPlayer2'
                super().__init__(bus_name, path)
                self._player = player_controller

            @dbus.service.method('org.mpris.MediaPlayer2.Player')
            def Play(self):
                self._player.engine.play()

            @dbus.service.method('org.mpris.MediaPlayer2.Player')
            def Pause(self):
                self._player.engine.pause()

            @dbus.service.method('org.mpris.MediaPlayer2.Player')
            def PlayPause(self):
                if self._player.engine.state == PlayerState.PLAYING:
                    self._player.engine.pause()
                else:
                    self._player.engine.play()

            @dbus.service.method('org.mpris.MediaPlayer2.Player')
            def Next(self):
                self._player.engine.play_next()

            @dbus.service.method('org.mpris.MediaPlayer2.Player')
            def Previous(self):
                self._player.engine.play_previous()

            @dbus.service.method('org.mpris.MediaPlayer2.Player')
            def Stop(self):
                self._player.engine.stop()

        MPRISPlayer(player)

    except ImportError:
        print("DBus not available for MPRIS support")


def _setup_macos_media_keys(player: PlayerController):
    """Setup media keys on macOS."""
    # Requires pyobjc and CGEvent tap
    # This is a simplified placeholder
    pass


def _setup_windows_media_keys(player: PlayerController):
    """Setup media keys on Windows."""
    # Requires keyboard or pynput library
    # This is a simplified placeholder
    try:
        from pynput import keyboard

        def on_press(key):
            if key == keyboard.Key.media_play_pause:
                if player.engine.state == PlayerState.PLAYING:
                    player.engine.pause()
                else:
                    player.engine.play()
            elif key == keyboard.Key.media_next:
                player.engine.play_next()
            elif key == keyboard.Key.media_previous:
                player.engine.play_previous()

        # Start listener in a separate thread
        listener = keyboard.Listener(on_press=on_press)
        listener.start()

    except ImportError:
        print("pynput not available for Windows media key support")

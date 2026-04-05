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
from typing import TYPE_CHECKING

from domain.playback import PlaybackState
from PySide6.QtCore import Qt, QObject
from PySide6.QtGui import QKeySequence, QShortcut

# Configure logging
logger = logging.getLogger(__name__)

# Use TYPE_CHECKING to avoid circular import
if TYPE_CHECKING:
    from services.playback.playback_service import PlaybackService

# Module-level listener reference for cleanup
_listener = None


class GlobalHotkeys(QObject):
    """
    Global hotkey manager.

    Note: This implementation uses Qt shortcuts which work when
    the application window has focus. For true global hotkeys
    (working when app is in background), you would need to use
    platform-specific APIs or integrate with MPRIS (Linux) or
    similar systems.
    """

    def __init__(self, player: "PlaybackService", window):
        """
        Initialize global hotkeys.

        Args:
            player: Player controller
            window: Main window to attach shortcuts to
        """
        super().__init__()

        self._player = player
        self._window = window
        self._shortcuts: list[QShortcut] = []

        self._setup_shortcuts()

    def _add_shortcut(self, key: QKeySequence | str | int, callback):
        """Create and keep a strong reference to shortcuts."""
        shortcut = QShortcut(QKeySequence(key), self._window)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Space - Play/Pause
        self._add_shortcut(Qt.Key_Space, self._toggle_play_pause)

        # Ctrl/Cmd + Left - Previous track
        self._add_shortcut("Ctrl+Left", self._player.engine.play_previous)

        # Ctrl/Cmd + Right - Next track
        self._add_shortcut("Ctrl+Right", self._player.engine.play_next)

        # Ctrl/Cmd + Up - Volume up
        self._add_shortcut("Ctrl+Up", self._volume_up)

        # Ctrl/Cmd + Down - Volume down
        self._add_shortcut("Ctrl+Down", self._volume_down)

        # Ctrl/Cmd + F - Toggle favorite
        self._add_shortcut("Ctrl+F", self._toggle_favorite)
        # Ctrl/Cmd + P - Toggle now playing window
        self._add_shortcut("Ctrl+P", self._toggle_now_playing)
        # Esc - Toggle now playing window
        self._add_shortcut(Qt.Key_Escape, self._toggle_now_playing)

        # Ctrl/Cmd + M - Toggle mini mode
        self._add_shortcut("Ctrl+M", self._toggle_mini_mode)

        # Ctrl/Cmd + Q - Quit
        self._add_shortcut("Ctrl+Q", self._quit_application)

        # Ctrl/Cmd + N - New playlist
        self._add_shortcut("Ctrl+N", self._new_playlist)

        # F1 - Help
        self._add_shortcut(Qt.Key_F1, self._show_help)

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._player.engine.state == PlaybackState.PLAYING:
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

    def _toggle_now_playing(self):
        """Toggle now playing window and main window."""
        if hasattr(self._window, '_toggle_now_playing_view'):
            self._window._toggle_now_playing_view()

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

    def _show_help(self):
        """Show help dialog."""
        if hasattr(self._window, 'show_help'):
            self._window.show_help()

    def _quit_application(self):
        """Quit application from main window shortcut."""
        if hasattr(self._window, 'request_quit'):
            self._window.request_quit()
        else:
            self._window.close()


def setup_media_key_handler(player: "PlaybackService"):
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


def _setup_linux_media_keys(player: "PlaybackService"):
    """Setup media keys on Linux using MPRIS."""
    pass


def _setup_macos_media_keys(player: "PlaybackService"):
    """Setup media keys on macOS."""
    # Requires pyobjc and CGEvent tap
    # This is a simplified placeholder
    pass


def _setup_windows_media_keys(player: "PlaybackService"):
    """Setup media keys on Windows."""
    # Requires keyboard or pynput library
    # This is a simplified placeholder
    try:
        from pynput import keyboard

        def on_press(key):
            if key == keyboard.Key.media_play_pause:
                if player.engine.state == PlaybackState.PLAYING:
                    player.engine.pause()
                else:
                    player.engine.play()
            elif key == keyboard.Key.media_next:
                player.engine.play_next()
            elif key == keyboard.Key.media_previous:
                player.engine.play_previous()

        # Start listener in a separate thread
        global _listener
        _listener = keyboard.Listener(on_press=on_press)
        _listener.start()

    except ImportError:
        logger.debug("pynput not available for Windows media key support")


def cleanup():
    """Stop and clean up the Windows media key listener."""
    global _listener
    if _listener:
        _listener.stop()
        _listener = None

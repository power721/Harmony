"""
MPRIS v2 D-Bus interface for Harmony music player (Linux only).

Provides standard MPRIS2 interfaces:
- org.mpris.MediaPlayer2 (basic player identity)
- org.mpris.MediaPlayer2.Player (playback control and metadata)

This module is optional - if the dbus-python library is not available,
MPRIS support is silently skipped.
"""

import logging
import os
import sys
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import QObject

logger = logging.getLogger(__name__)

# Check platform at module level - only import dbus on Linux
_AVAILABLE = False
_dbus = None

if sys.platform == "linux":
    try:
        import dbus
        import dbus.service
        import dbus.mainloop
        import dbus.mainloop.glib

        _AVAILABLE = True
    except ImportError:
        logger.debug("dbus-python not available, MPRIS support disabled")


def _get_dbus():
    """Get dbus module (for lazy import checking)."""
    if not _AVAILABLE:
        raise ImportError("dbus-python not available")
    return dbus

if TYPE_CHECKING:
    pass

# MPRIS2 constants
MPRIS_PREFIX = "org.mpris.MediaPlayer2"
MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_INTERFACE = "org.mpris.MediaPlayer2"
MPRIS_PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
DBUS_PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
TRACK_PREFIX = "/org/mpris/MediaPlayer2/Track/"


def _to_track_id(item) -> str:
    """Build a MPRIS track ID from a PlaylistItem or similar object."""
    if item is None:
        return "/org/mpris/MediaPlayer2/Track/0"
    if hasattr(item, "track_id") and item.track_id:
        return f"{TRACK_PREFIX}{item.track_id}"
    if hasattr(item, "cloud_file_id") and item.cloud_file_id:
        # Use a hash for cloud file IDs to make them valid D-Bus paths
        h = hash(item.cloud_file_id) & 0xFFFFFFFFFFFFFFFF
        return f"{TRACK_PREFIX}{h}"
    return "/org/mpris/MediaPlayer2/Track/0"


def _build_metadata(item) -> dict:
    """
    Build MPRIS Metadata dict from a PlaylistItem.

    Uses xesam: namespace for standard track info and mpris: for MPRIS-specific.
    """
    if item is None:
        return {}

    if not _AVAILABLE:
        return {}

    metadata = {}

    # mpris:trackid (required)
    metadata["mpris:trackid"] = dbus.ObjectPath(_to_track_id(item))

    # xesam:title
    if hasattr(item, "title") and item.title:
        metadata["xesam:title"] = item.title

    # xesam:artist (must be a list of strings)
    artist = getattr(item, "artist", "") or ""
    metadata["xesam:artist"] = dbus.Array([artist], signature="s")

    # xesam:album
    if hasattr(item, "album") and item.album:
        metadata["xesam:album"] = item.album

    # mpris:length in microseconds
    duration = getattr(item, "duration", 0) or 0
    metadata["mpris:length"] = dbus.Int64(int(duration * 1_000_000))

    # mpris:artUrl
    cover_path = getattr(item, "cover_path", None)
    if cover_path and os.path.isfile(cover_path):
        metadata["mpris:artUrl"] = f"file://{os.path.abspath(cover_path)}"

    return metadata


def _playback_state_to_mpris(state) -> str:
    """Convert PlaybackState enum to MPRIS PlaybackStatus string."""
    from domain.playback import PlaybackState

    if state == PlaybackState.PLAYING:
        return "Playing"
    elif state == PlaybackState.PAUSED:
        return "Paused"
    else:
        return "Stopped"


def _mpris_to_playback_state(status: str):
    """Convert MPRIS PlaybackStatus string to PlaybackState enum."""
    from domain.playback import PlaybackState

    mapping = {
        "Playing": PlaybackState.PLAYING,
        "Paused": PlaybackState.PAUSED,
        "Stopped": PlaybackState.STOPPED,
    }
    return mapping.get(status, PlaybackState.STOPPED)


def _play_mode_to_mpris(play_mode) -> tuple:
    """
    Convert PlayMode enum to MPRIS LoopStatus and Shuffle values.

    Returns:
        (LoopStatus, Shuffle) tuple
    """
    from domain.playback import PlayMode

    if play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
        return "Track", False
    elif play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
        return "Playlist", False
    elif play_mode in (PlayMode.RANDOM,):
        return "None", True
    else:
        # SEQUENTIAL
        return "None", False


def _mpris_to_play_mode(loop_status: str, shuffle: bool):
    """
    Convert MPRIS LoopStatus + Shuffle to PlayMode enum.

    Priority: if shuffle is True, return random variant.
    """
    from domain.playback import PlayMode

    if shuffle:
        if loop_status == "Track":
            return PlayMode.RANDOM_TRACK_LOOP
        elif loop_status == "Playlist":
            return PlayMode.RANDOM_LOOP
        else:
            return PlayMode.RANDOM
    else:
        if loop_status == "Track":
            return PlayMode.LOOP
        elif loop_status == "Playlist":
            return PlayMode.PLAYLIST_LOOP
        else:
            return PlayMode.SEQUENTIAL


# Only define MPRIS2Service if dbus is available
if _AVAILABLE:
    class MPRIS2Service(dbus.service.Object):
        """
        MPRIS v2 D-Bus service object.

        Implements both org.mpris.MediaPlayer2 and
        org.mpris.MediaPlayer2.Player interfaces.
        """

        def __init__(self, bus_name: dbus.bus.BusName, controller: "MPRISController"):
            """
            Initialize the MPRIS2 D-Bus service.

            Args:
                bus_name: Registered D-Bus bus name
                controller: MPRISController that bridges to PlaybackService
            """
            super().__init__(bus_name, MPRIS_PATH)
            self._controller = controller

        # ===== org.mpris.MediaPlayer2 =====

        @dbus.service.method(MPRIS_INTERFACE)
        def Raise(self):
            """Bring the player to the front (show window)."""
            self._controller.raise_window()

        @dbus.service.method(MPRIS_INTERFACE)
        def Quit(self):
            """Quit the player."""
            self._controller.quit_app()

        @dbus.service.property(MPRIS_INTERFACE, signature="s")
        def Identity(self):
            """Player name."""
            return "Harmony"

        @dbus.service.property(MPRIS_INTERFACE, signature="s")
        def DesktopEntry(self):
            """Desktop file entry name."""
            # Try common desktop file names
            for name in ("harmony", "music-player", "Harmony"):
                desktop_path = os.path.expanduser(
                    f"~/.local/share/applications/{name}.desktop"
                )
                if os.path.exists(desktop_path):
                    return name
            return "harmony"

        @dbus.service.property(MPRIS_INTERFACE, signature="as")
        def SupportedUriSchemes(self):
            """Supported URI schemes (empty - we handle files internally)."""
            return dbus.Array([], signature="s")

        @dbus.service.property(MPRIS_INTERFACE, signature="as")
        def SupportedMimeTypes(self):
            """Supported MIME types."""
            return dbus.Array(
                [
                    "audio/mpeg",
                    "audio/flac",
                    "audio/ogg",
                    "audio/wav",
                    "audio/aac",
                    "audio/mp4",
                    "audio/opus",
                    "audio/x-m4a",
                ],
                signature="s",
            )

        @dbus.service.property(MPRIS_INTERFACE, signature="b")
        def CanQuit(self):
            """Whether the player can quit."""
            return True

        @dbus.service.property(MPRIS_INTERFACE, signature="b")
        def CanRaise(self):
            """Whether the player can be raised."""
            return True

        @dbus.service.property(MPRIS_INTERFACE, signature="b")
        def HasTrackList(self):
            """Whether the player supports track lists."""
            return False

        # ===== org.mpris.MediaPlayer2.Player =====

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Next(self):
            """Skip to the next track."""
            self._controller.play_next()

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Previous(self):
            """Skip to the previous track."""
            self._controller.play_previous()

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Pause(self):
            """Pause playback."""
            self._controller.pause()

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def PlayPause(self):
            """Toggle play/pause."""
            self._controller.play_pause()

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Stop(self):
            """Stop playback."""
            self._controller.stop()

        @dbus.service.method(MPRIS_PLAYER_INTERFACE)
        def Play(self):
            """Start playback."""
            self._controller.play()

        @dbus.service.method(MPRIS_PLAYER_INTERFACE, in_signature="x")
        def Seek(self, offset):
            """
            Seek forward or backward by offset in microseconds.

            Args:
                offset: Offset in microseconds (negative = backward)
            """
            self._controller.seek(offset)

        @dbus.service.method(MPRIS_PLAYER_INTERFACE, in_signature="ox")
        def SetPosition(self, track_id, position):
            """
            Set the playback position.

            Args:
                track_id: D-Bus object path of the track
                position: Position in microseconds
            """
            self._controller.set_position(track_id, position)

        @dbus.service.method(MPRIS_PLAYER_INTERFACE, in_signature="s")
        def OpenUri(self, uri):
            """
            Open a URI for playback.

            Args:
                uri: URI to open
            """
            logger.debug(f"[MPRIS] OpenUri called: {uri}")
            # Not currently supported - we handle files internally

        # ===== Player Properties =====

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="s")
        def PlaybackStatus(self):
            """Current playback status."""
            return self._controller.get_playback_status()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="s")
        def LoopStatus(self):
            """Current loop status."""
            return self._controller.get_loop_status()

        @LoopStatus.setter
        def LoopStatus(self, value):
            """Set loop status."""
            self._controller.set_loop_status(value)

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="d")
        def Rate(self):
            """Playback rate (1.0 = normal)."""
            return 1.0

        @Rate.setter
        def Rate(self, value):
            """Set playback rate (not supported)."""
            pass

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def Shuffle(self):
            """Shuffle mode."""
            return self._controller.get_shuffle()

        @Shuffle.setter
        def Shuffle(self, value):
            """Set shuffle mode."""
            self._controller.set_shuffle(value)

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="a{sv}")
        def Metadata(self):
            """Current track metadata."""
            return self._controller.get_metadata()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="d")
        def Volume(self):
            """Current volume (0.0 - 1.0)."""
            return self._controller.get_volume()

        @Volume.setter
        def Volume(self, value):
            """Set volume (0.0 - 1.0)."""
            self._controller.set_volume(value)

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="x")
        def Position(self):
            """Current position in microseconds."""
            return self._controller.get_position()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="d")
        def MinimumRate(self):
            """Minimum playback rate."""
            return 1.0

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="d")
        def MaximumRate(self):
            """Maximum playback rate."""
            return 1.0

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def CanGoNext(self):
            """Whether the player can go to the next track."""
            return self._controller.can_go_next()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def CanGoPrevious(self):
            """Whether the player can go to the previous track."""
            return self._controller.can_go_previous()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def CanPlay(self):
            """Whether the player can play."""
            return self._controller.can_play()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def CanPause(self):
            """Whether the player can pause."""
            return self._controller.can_pause()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def CanSeek(self):
            """Whether the player can seek."""
            return self._controller.can_seek()

        @dbus.service.property(MPRIS_PLAYER_INTERFACE, signature="b")
        def CanControl(self):
            """Whether the player can be controlled."""
            return True

        # ===== Signal emission helpers =====

        def emit_properties_changed(self, interface: str, changed: dict):
            """
            Emit PropertiesChanged signal on D-Bus.

            Args:
                interface: D-Bus interface name
                changed: Dict of changed properties
            """
            self.PropertiesChanged(interface, changed, dbus.Array([], signature="s"))

        @dbus.service.signal(DBUS_PROPERTIES_INTERFACE, signature="sa{sv}as")
        def PropertiesChanged(self, interface, changed, invalidated):
            """PropertiesChanged signal."""
            pass

        @dbus.service.signal(MPRIS_PLAYER_INTERFACE, signature="x")
        def Seeked(self, position):
            """
            Seeked signal - emitted when the track position changes
            in a way that is not linear.

            Args:
                position: New position in microseconds
            """
            pass


# End of MPRIS2Service class and _AVAILABLE conditional block


class MPRISController(QObject):
    """
    Controller that bridges MPRIS D-Bus interface with PlaybackService.

    Listens to EventBus signals to keep MPRIS state in sync and
    forwards D-Bus method calls to PlaybackService.

    Usage:
        controller = MPRISController(playback_service, event_bus, main_window)
        controller.start()
        # ... app runs ...
        controller.stop()
    """

    def __init__(
        self,
        playback_service,
        event_bus,
        main_window=None,
        parent=None,
    ):
        """
        Initialize MPRIS controller.

        Args:
            playback_service: The PlaybackService instance
            event_bus: The EventBus instance
            main_window: The MainWindow instance (for Raise/Quit)
            parent: Optional parent QObject
        """
        super().__init__(parent)

        self._playback_service = playback_service
        self._event_bus = event_bus
        self._main_window = main_window

        self._bus = None
        self._bus_name = None
        self._service = None

        # Cached state
        self._last_track_id = None  # To detect track changes for Seeked signal
        self._seeked_emitted_for_position = False

    def start(self):
        """
        Register the MPRIS2 interface on the D-Bus session bus.

        Does nothing if D-Bus is not available or already registered.
        """
        if self._service is not None:
            return

        if not _AVAILABLE:
            logger.debug("[MPRIS] D-Bus not available, skipping MPRIS registration")
            return

        try:
            # Initialize GLib main loop integration for D-Bus
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

            self._bus = dbus.SessionBus()
            self._bus_name = dbus.service.BusName(
                f"{MPRIS_PREFIX}.harmony",
                self._bus,
                allow_replacement=True,
                replace_existing=True,
            )

            self._service = MPRIS2Service(self._bus_name, self)

            # Connect to EventBus signals for state synchronization
            self._event_bus.track_changed.connect(self._on_track_changed)
            self._event_bus.playback_state_changed.connect(self._on_playback_state_changed)
            self._event_bus.position_changed.connect(self._on_position_changed)
            self._event_bus.volume_changed.connect(self._on_volume_changed)
            self._event_bus.play_mode_changed.connect(self._on_play_mode_changed)

            logger.info("[MPRIS] Successfully registered on D-Bus session bus")
        except dbus.exceptions.DBusException as e:
            logger.warning(f"[MPRIS] Failed to register on D-Bus: {e}")
            self._cleanup()
        except Exception as e:
            logger.error(f"[MPRIS] Unexpected error during D-Bus registration: {e}")
            self._cleanup()

    def stop(self):
        """
        Unregister from D-Bus and disconnect signals.
        """
        try:
            if self._event_bus:
                self._event_bus.track_changed.disconnect(self._on_track_changed)
                self._event_bus.playback_state_changed.disconnect(self._on_playback_state_changed)
                self._event_bus.position_changed.disconnect(self._on_position_changed)
                self._event_bus.volume_changed.disconnect(self._on_volume_changed)
                self._event_bus.play_mode_changed.disconnect(self._on_play_mode_changed)
        except Exception as e:
            logger.warning(f"Error disconnecting MPRIS signals: {e}")

        self._cleanup()
        logger.info("[MPRIS] Unregistered from D-Bus")

    def _cleanup(self):
        """Clean up D-Bus resources."""
        self._service = None
        self._bus_name = None
        self._bus = None

    # ===== EventBus signal handlers =====

    def _on_track_changed(self, track_item):
        """Handle track change from EventBus -> update MPRIS metadata."""
        self._last_track_id = _to_track_id(track_item)
        self._seeked_emitted_for_position = False
        if self._service:
            metadata = _build_metadata(track_item)
            self._service.emit_properties_changed(
                MPRIS_PLAYER_INTERFACE,
                {"Metadata": dbus.Dictionary(metadata, signature="sv")},
            )

    def _on_playback_state_changed(self, state_str: str):
        """Handle playback state change from EventBus -> update MPRIS PlaybackStatus."""
        if self._service:
            self._service.emit_properties_changed(
                MPRIS_PLAYER_INTERFACE,
                {"PlaybackStatus": state_str.capitalize()},
            )

    def _on_position_changed(self, position_ms: int):
        """Handle position change from EventBus."""
        # MPRIS Position is read-only; we emit Seeked only on significant jumps.
        # Regular position updates are handled by clients polling the Position property.
        pass

    def _on_volume_changed(self, volume: int):
        """Handle volume change from EventBus -> update MPRIS Volume."""
        if self._service:
            self._service.emit_properties_changed(
                MPRIS_PLAYER_INTERFACE,
                {"Volume": dbus.Double(volume / 100.0)},
            )

    def _on_play_mode_changed(self, mode_int: int):
        """Handle play mode change from EventBus -> update MPRIS LoopStatus and Shuffle."""
        if self._service:
            from domain.playback import PlayMode

            mode = PlayMode(mode_int)
            loop_status, shuffle = _play_mode_to_mpris(mode)
            self._service.emit_properties_changed(
                MPRIS_PLAYER_INTERFACE,
                {
                    "LoopStatus": loop_status,
                    "Shuffle": dbus.Boolean(shuffle),
                },
            )

    # ===== D-Bus method callbacks (called from MPRIS2Service) =====

    def raise_window(self):
        """Raise the main window to front."""
        if self._main_window:
            self._main_window.show()
            self._main_window.raise_()
            self._main_window.activateWindow()

    def quit_app(self):
        """Quit the application."""
        if self._main_window:
            self._main_window.close()

    def play(self):
        """Start or resume playback."""
        self._playback_service.play()

    def pause(self):
        """Pause playback."""
        self._playback_service.pause()

    def play_pause(self):
        """Toggle play/pause."""
        from domain.playback import PlaybackState

        state = self._playback_service.state
        if state == PlaybackState.PLAYING:
            self._playback_service.pause()
        else:
            self._playback_service.play()

    def stop(self):
        """Stop playback."""
        self._playback_service.stop()

    def play_next(self):
        """Play next track."""
        self._playback_service.play_next()

    def play_previous(self):
        """Play previous track."""
        self._playback_service.play_previous()

    def seek(self, offset_us: int):
        """
        Seek by offset in microseconds.

        Args:
            offset_us: Offset in microseconds (negative = backward)
        """
        current_pos = self._playback_service.engine.position()
        new_pos = max(0, current_pos + int(offset_us / 1000))
        self._playback_service.seek(new_pos)

        if self._service:
            self._service.Seeked(dbus.Int64(new_pos * 1000))

    def set_position(self, track_id, position_us: int):
        """
        Set playback position.

        Args:
            track_id: D-Bus object path of the track
            position_us: Position in microseconds
        """
        current_item = self._playback_service.current_track
        if current_item is None:
            return

        expected_id = _to_track_id(current_item)
        if str(track_id) != expected_id:
            logger.debug(
                f"[MPRIS] SetPosition track_id mismatch: "
                f"{track_id} != {expected_id}"
            )
            return

        position_ms = int(position_us / 1000)
        self._playback_service.seek(position_ms)

        if self._service:
            self._service.Seeked(dbus.Int64(position_us))

    def set_volume(self, volume: float):
        """
        Set volume.

        Args:
            volume: Volume level (0.0 - 1.0)
        """
        clamped = max(0.0, min(1.0, volume))
        self._playback_service.set_volume(int(clamped * 100))

    # ===== Property getters (called from MPRIS2Service) =====

    def get_playback_status(self) -> str:
        """Get current playback status string."""
        return _playback_state_to_mpris(self._playback_service.state)

    def get_loop_status(self) -> str:
        """Get current loop status string."""
        loop_status, _ = _play_mode_to_mpris(self._playback_service.play_mode)
        return loop_status

    def set_loop_status(self, value: str):
        """Set loop status from MPRIS."""
        shuffle = self.get_shuffle()
        mode = _mpris_to_play_mode(value, shuffle)
        self._playback_service.set_play_mode(mode)

    def get_shuffle(self) -> bool:
        """Get current shuffle state."""
        _, shuffle = _play_mode_to_mpris(self._playback_service.play_mode)
        return shuffle

    def set_shuffle(self, value: bool):
        """Set shuffle state from MPRIS."""
        loop_status = self.get_loop_status()
        mode = _mpris_to_play_mode(loop_status, value)
        self._playback_service.set_play_mode(mode)

    def get_metadata(self) -> dict:
        """Get current track metadata as MPRIS dict."""
        if not _AVAILABLE:
            return {}
        item = self._playback_service.current_track
        return dbus.Dictionary(_build_metadata(item), signature="sv")

    def get_volume(self) -> float:
        """Get current volume as 0.0-1.0."""
        return self._playback_service.volume / 100.0

    def get_position(self) -> int:
        """Get current position in microseconds."""
        return self._playback_service.engine.position() * 1000

    def can_go_next(self) -> bool:
        """Check if next track is available."""
        playlist = self._playback_service.engine.playlist_items
        return self._playback_service.engine.current_index < (len(playlist) - 1)

    def can_go_previous(self) -> bool:
        """Check if previous track is available."""
        return (
            self._playback_service.engine.current_index > 0
            or self._playback_service.engine.position() > 3000
        )

    def can_play(self) -> bool:
        """Check if playback can start."""
        return self._playback_service.current_track is not None

    def can_pause(self) -> bool:
        """Check if playback can be paused."""
        from domain.playback import PlaybackState

        return (
            self._playback_service.state == PlaybackState.PLAYING
            or self._playback_service.current_track is not None
        )

    def can_seek(self) -> bool:
        """Check if seeking is possible."""
        return self._playback_service.current_track is not None

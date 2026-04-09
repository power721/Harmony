import hashlib
import threading
from pathlib import Path
from typing import Any

from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusObjectPath, QDBusVirtualObject

from app import Bootstrap
from domain import PlaylistItem

MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_NAME = "org.mpris.MediaPlayer2.musicplayer"
ROOT_INTERFACE = "org.mpris.MediaPlayer2"
PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
EMPTY_TRACK_ID = "/org/mpris/MediaPlayer2/track/none"

INTROSPECTION_XML = f"""
<node>
  <interface name="{ROOT_INTERFACE}">
    <method name="Raise"/>
    <method name="Quit"/>
  </interface>
  <interface name="{PLAYER_INTERFACE}">
    <method name="Play"/>
    <method name="Pause"/>
    <method name="Stop"/>
    <method name="PlayPause"/>
    <method name="Next"/>
    <method name="Previous"/>
    <method name="Seek">
      <arg direction="in" type="x" name="Offset"/>
    </method>
    <method name="SetPosition">
      <arg direction="in" type="o" name="TrackId"/>
      <arg direction="in" type="x" name="Position"/>
    </method>
    <signal name="Seeked">
      <arg type="x" name="Position"/>
    </signal>
  </interface>
  <interface name="{PROPERTIES_INTERFACE}">
    <method name="Get">
      <arg direction="in" type="s" name="interface"/>
      <arg direction="in" type="s" name="property"/>
      <arg direction="out" type="v" name="value"/>
    </method>
    <method name="GetAll">
      <arg direction="in" type="s" name="interface"/>
      <arg direction="out" type="a{{sv}}" name="properties"/>
    </method>
    <method name="Set">
      <arg direction="in" type="s" name="interface"/>
      <arg direction="in" type="s" name="property"/>
      <arg direction="in" type="v" name="value"/>
    </method>
    <signal name="PropertiesChanged">
      <arg type="s" name="interface"/>
      <arg type="a{{sv}}" name="changed_properties"/>
      <arg type="as" name="invalidated_properties"/>
    </signal>
  </interface>
</node>
""".strip()


class _PropertyReadOnlyError(RuntimeError):
    pass


def _safe_str(value) -> str:
    return str(value or "")


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _unwrap_dbus_value(value):
    reply_value = getattr(value, "value", None)
    if callable(reply_value):
        try:
            return reply_value()
        except Exception:
            return value
    return value


def _safe_file_uri(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    try:
        return Path(path).expanduser().resolve().as_uri()
    except Exception:
        return ""


def _object_path_string(value: object) -> str:
    if isinstance(value, QDBusObjectPath):
        return value.path()
    return str(value)


def _make_track_object_path(track: PlaylistItem) -> QDBusObjectPath:
    raw = str(track.track_id)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return QDBusObjectPath(f"/org/mpris/MediaPlayer2/track/{digest}")


class MPRISService(QDBusVirtualObject):
    def __init__(self, playback_service, main_window=None, ui_dispatcher=None):
        super().__init__()
        self.playback_service = playback_service
        self._main_window = main_window
        self._ui_dispatcher = ui_dispatcher
        self.bus = None

    def introspect(self, path):
        if path == MPRIS_PATH:
            return INTROSPECTION_XML
        return ""

    def handleMessage(self, message, connection):
        if message.path() != MPRIS_PATH:
            return False

        interface_name = message.interface()
        member = message.member()
        args = message.arguments()

        try:
            if interface_name == ROOT_INTERFACE:
                result = getattr(self, member)(*args)
            elif interface_name == PLAYER_INTERFACE:
                result = getattr(self, member)(*args)
            elif interface_name == PROPERTIES_INTERFACE:
                result = getattr(self, member)(*args)
            else:
                return False
        except _PropertyReadOnlyError as exc:
            connection.send(message.createErrorReply(
                "org.freedesktop.DBus.Error.PropertyReadOnly",
                str(exc),
            ))
            return True
        except Exception as exc:
            connection.send(message.createErrorReply(
                "org.freedesktop.DBus.Error.Failed",
                str(exc),
            ))
            return True

        if message.isReplyRequired():
            reply = message.createReply() if result is None else message.createReply(result)
            connection.send(reply)
        return True

    def _current_track(self) -> PlaylistItem | None:
        return getattr(self.playback_service, "current_track", None)

    def position_us(self) -> int:
        method = getattr(self.playback_service, "position", None)
        ms = method() if callable(method) else 0.0
        return int(_safe_float(ms) * 1000)

    def _position_us(self) -> int:
        return self.position_us()

    def _playback_status(self) -> str:
        status_method = getattr(self.playback_service, "playback_status", None)
        if callable(status_method):
            status = _safe_str(status_method()).lower()
            if status == "playing":
                return "Playing"
            if status == "paused":
                return "Paused"
            if status == "stopped":
                return "Stopped"

        is_playing = bool(getattr(self.playback_service, "is_playing", False))
        is_stopped = bool(getattr(self.playback_service, "is_stopped", False))
        if is_playing:
            return "Playing"
        if is_stopped:
            return "Stopped"
        return "Paused"

    def _metadata(self) -> dict[str, Any]:
        track = self._current_track()
        if not track:
            return {
                "mpris:trackid": QDBusObjectPath(EMPTY_TRACK_ID),
            }
        return self._metadata_for(track)

    def _metadata_for(self, track: PlaylistItem) -> dict[str, Any]:
        title = _safe_str(track.title)
        artist = _safe_str(track.artist)
        album = _safe_str(track.album)
        duration = _safe_float(track.duration)
        cover_path = _safe_str(track.cover_path)
        track_path = _safe_str(track.local_path)

        artists = [artist] if artist else []
        metadata: dict[str, Any] = {
            "mpris:trackid": _make_track_object_path(track),
            "xesam:title": title,
            "xesam:artist": artists,
            "xesam:album": album,
            "mpris:length": int(duration * 1_000_000),
        }

        art_url = _safe_file_uri(cover_path)
        if art_url:
            metadata["mpris:artUrl"] = art_url

        track_url = _safe_file_uri(track_path)
        if track_url:
            metadata["xesam:url"] = track_url

        return metadata

    def root_properties(self) -> dict[str, Any]:
        return {
            "CanQuit": True,
            "CanRaise": self._main_window is not None,
            "HasTrackList": False,
            "Identity": "MusicPlayer",
            "SupportedUriSchemes": ["file", "http", "https"],
            "SupportedMimeTypes": [
                "audio/mpeg",
                "audio/flac",
                "audio/x-flac",
                "audio/ogg",
                "audio/wav",
                "audio/mp4",
                "audio/aac",
            ],
        }

    def player_properties(self) -> dict[str, Any]:
        return {
            "PlaybackStatus": self._playback_status(),
            "LoopStatus": self._loop_status(),
            "Position": self.position_us(),
            "Metadata": self._metadata(),
            "Shuffle": self._shuffle(),
            "CanControl": True,
            "CanGoNext": True,
            "CanGoPrevious": True,
            "CanPlay": True,
            "CanPause": True,
            "CanSeek": bool(getattr(self.playback_service, "can_seek", True)),
            "Rate": 1.0,
            "MinimumRate": 1.0,
            "MaximumRate": 1.0,
            "Volume": self._volume(),
        }

    def _volume(self) -> float:
        return float(getattr(self.playback_service, "volume", 1.0))

    def _loop_status(self) -> str:
        value = str(getattr(self.playback_service, "loop_status", "None"))
        return value if value in ("None", "Track", "Playlist") else "None"

    def _shuffle(self) -> bool:
        return bool(getattr(self.playback_service, "shuffle", False))

    def _dispatch_to_ui(self, fn, *args, **kwargs):
        if callable(self._ui_dispatcher):
            self._ui_dispatcher(fn, *args, **kwargs)
            return
        fn(*args, **kwargs)

    def _send_signal(self, interface_name: str, member: str, args: list[Any]):
        if self.bus is None or not hasattr(self.bus, "send"):
            return
        message = QDBusMessage.createSignal(MPRIS_PATH, interface_name, member)
        message.setArguments(args)
        self.bus.send(message)

    def Raise(self):
        if self._main_window:
            def _raise_window():
                try:
                    self._main_window.showNormal()
                    self._main_window.raise_()
                    self._main_window.activateWindow()
                except Exception:
                    pass

            self._dispatch_to_ui(_raise_window)

    def Quit(self):
        if self._main_window:
            def _quit_window():
                try:
                    self._main_window.close()
                except Exception:
                    pass

            self._dispatch_to_ui(_quit_window)

    def Play(self):
        def _play():
            self.playback_service.play()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_play)

    def Pause(self):
        def _pause():
            self.playback_service.pause()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_pause)

    def Stop(self):
        def _stop():
            self.playback_service.stop()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_stop)

    def PlayPause(self):
        def _play_pause():
            if self._playback_status() == "Playing":
                self.playback_service.pause()
            else:
                self.playback_service.play()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_play_pause)

    def Next(self):
        def _next():
            self.playback_service.play_next()
            self.emit_player_properties(["PlaybackStatus", "Metadata"])
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_next)

    def Previous(self):
        def _previous():
            self.playback_service.play_previous()
            self.emit_player_properties(["PlaybackStatus", "Metadata"])
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_previous)

    def Seek(self, offset):
        def _seek():
            ms = int(offset) // 1000
            self.playback_service.seek(ms)
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_seek)

    def SetPosition(self, track_id, position):
        def _set_position():
            track = self._current_track()
            if not track:
                return

            current_id = _object_path_string(_make_track_object_path(track))
            if _object_path_string(track_id) != current_id:
                return

            ms = int(position) // 1000
            try:
                self.playback_service.seek(ms)
            except TypeError:
                pass
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_set_position)

    def Get(self, interface_name, property_name):
        props = self.GetAll(interface_name)
        return props[property_name]

    def GetAll(self, interface_name):
        if interface_name == ROOT_INTERFACE:
            return self.root_properties()
        if interface_name == PLAYER_INTERFACE:
            return self.player_properties()
        return {}

    def Set(self, interface_name, property_name, value):
        if interface_name == PLAYER_INTERFACE and property_name == "Volume":
            setter = getattr(self.playback_service, "set_volume", None)
            if callable(setter):
                def _set_volume():
                    setter(float(value))
                    self.emit_player_properties(["Volume"])

                self._dispatch_to_ui(_set_volume)
                return

        raise _PropertyReadOnlyError(f"Property {property_name} is read-only")

    def emit_seeked(self, position):
        self._send_signal(PLAYER_INTERFACE, "Seeked", [int(position)])

    def emit_player_properties(self, names=None):
        props = self.player_properties()
        changed = {name: props[name] for name in (names or props.keys()) if name in props}
        self._send_signal(
            PROPERTIES_INTERFACE,
            "PropertiesChanged",
            [PLAYER_INTERFACE, changed, []],
        )

    def emit_root_properties(self, names=None):
        props = self.root_properties()
        changed = {name: props[name] for name in (names or props.keys()) if name in props}
        self._send_signal(
            PROPERTIES_INTERFACE,
            "PropertiesChanged",
            [ROOT_INTERFACE, changed, []],
        )


class MPRISController:
    def __init__(self, playback_service, main_window=None):
        self.playback_service = playback_service
        self._main_window = main_window
        self.ui_dispatcher = None
        self.service = None
        self.bus = None
        self._started = False
        self._service_lock = threading.Lock()

        event_bus = Bootstrap.instance().event_bus
        event_bus.track_changed.connect(self.on_track_changed)
        event_bus.playback_state_changed.connect(self.on_playback_state_changed)
        event_bus.duration_changed.connect(self.on_duration_changed)
        event_bus.volume_changed.connect(self.on_volume_changed)
        event_bus.cover_updated.connect(self.on_cover_updated)

    def _bus_error_message(self, default: str) -> str:
        if self.bus is None or not hasattr(self.bus, "lastError"):
            return default
        last_error = self.bus.lastError()
        if last_error is None:
            return default
        message = getattr(last_error, "message", None)
        if callable(message):
            resolved = message()
            if resolved:
                return resolved
        return default

    def _service_registration_error_message(self) -> str:
        default = "failed to register MPRIS service"
        message = self._bus_error_message(default)
        if message != default:
            return message

        if self.bus is None or not hasattr(self.bus, "interface"):
            return default

        interface = self.bus.interface()
        if interface is None:
            return default

        owner = ""
        service_owner = getattr(interface, "serviceOwner", None)
        if callable(service_owner):
            owner = _unwrap_dbus_value(service_owner(MPRIS_NAME)) or ""

        if not owner:
            return default

        pid = 0
        service_pid = getattr(interface, "servicePid", None)
        if callable(service_pid):
            pid = _unwrap_dbus_value(service_pid(MPRIS_NAME)) or 0

        if pid:
            return f"MPRIS service name already owned by {owner} (pid={pid})"
        return f"MPRIS service name already owned by {owner}"

    def start(self):
        if self._started:
            return

        self.bus = QDBusConnection.sessionBus()
        if hasattr(self.bus, "isConnected") and not self.bus.isConnected():
            raise RuntimeError(self._bus_error_message("QtDBus session bus unavailable"))

        with self._service_lock:
            self.service = MPRISService(
                playback_service=self.playback_service,
                main_window=self._main_window,
                ui_dispatcher=self.ui_dispatcher,
            )
            self.service.bus = self.bus

        if not self.bus.registerService(MPRIS_NAME):
            with self._service_lock:
                self.service = None
            raise RuntimeError(self._service_registration_error_message())

        options = QDBusConnection.VirtualObjectRegisterOption.SubPath
        if hasattr(self.bus, "registerVirtualObject"):
            registered = self.bus.registerVirtualObject(MPRIS_PATH, self.service, options)
        else:
            export_options = (
                QDBusConnection.RegisterOption.ExportAllSlots
                | QDBusConnection.RegisterOption.ExportAllSignals
            )
            registered = self.bus.registerObject(MPRIS_PATH, self.service, export_options)

        if not registered:
            self.bus.unregisterService(MPRIS_NAME)
            with self._service_lock:
                self.service = None
            raise RuntimeError(self._bus_error_message("failed to register MPRIS object"))

        self._started = True

    def stop(self):
        if not self._started:
            return

        if self.bus is not None:
            if hasattr(self.bus, "unregisterObject"):
                self.bus.unregisterObject(MPRIS_PATH)
            self.bus.unregisterService(MPRIS_NAME)

        with self._service_lock:
            self.service = None
        self.bus = None
        self._started = False

    def _get_service(self):
        with self._service_lock:
            return self.service

    def on_playback_state_changed(self, *args):
        service = self._get_service()
        if service:
            service.emit_player_properties(["PlaybackStatus"])

    def on_track_changed(self, *args):
        service = self._get_service()
        if service:
            service.emit_player_properties(["Metadata", "PlaybackStatus"])
            service.emit_seeked(service.position_us())

    def on_metadata_changed(self, *args):
        service = self._get_service()
        if service:
            service.emit_player_properties(["Metadata"])

    def on_duration_changed(self, *args):
        service = self._get_service()
        if service:
            service.emit_player_properties(["Metadata"])

    def on_volume_changed(self, *args):
        service = self._get_service()
        if service:
            service.emit_player_properties(["Volume"])

    def on_cover_updated(self, *args):
        service = self._get_service()
        if service:
            service.emit_player_properties(["Metadata"])

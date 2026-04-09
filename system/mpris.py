import hashlib
import threading
from pathlib import Path
from typing import Any

from PySide6.QtCore import ClassInfo, QObject, Property, Signal, Slot
from PySide6.QtDBus import QDBusAbstractAdaptor, QDBusConnection, QDBusMessage, QDBusObjectPath

from app import Bootstrap
from domain import PlaylistItem

MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_NAME = "org.mpris.MediaPlayer2.musicplayer"
ROOT_INTERFACE = "org.mpris.MediaPlayer2"
PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"
EMPTY_TRACK_ID = "/org/mpris/MediaPlayer2/track/none"
DESKTOP_ENTRY = "harmony"


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


class MPRISService(QObject):
    def __init__(self, playback_service, main_window=None, ui_dispatcher=None):
        super().__init__()
        self.playback_service = playback_service
        self._main_window = main_window
        self._ui_dispatcher = ui_dispatcher
        self.bus = None
        # Keep strong references so the adaptors stay exported for the lifetime
        # of the registered object.
        self.root_adaptor = _RootAdaptor(self)
        self.player_adaptor = _PlayerAdaptor(self)

    def _current_track(self) -> PlaylistItem | None:
        return getattr(self.playback_service, "current_track", None)

    def position_us(self) -> int:
        position_value = getattr(self.playback_service, "position", 0.0)
        ms = position_value() if callable(position_value) else position_value
        return int(_safe_float(ms) * 1000)

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
            "DesktopEntry": DESKTOP_ENTRY,
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

    def _raise(self):
        if self._main_window:
            def _raise_window():
                try:
                    self._main_window.showNormal()
                    self._main_window.raise_()
                    self._main_window.activateWindow()
                except Exception:
                    pass

            self._dispatch_to_ui(_raise_window)

    def Raise(self):
        self._raise()

    def _quit(self):
        if self._main_window:
            def _quit_window():
                try:
                    self._main_window.close()
                except Exception:
                    pass

            self._dispatch_to_ui(_quit_window)

    def Quit(self):
        self._quit()

    def _play(self):
        def _play():
            self.playback_service.play()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_play)

    def Play(self):
        self._play()

    def _pause(self):
        def _pause():
            self.playback_service.pause()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_pause)

    def Pause(self):
        self._pause()

    def _stop(self):
        def _stop():
            self.playback_service.stop()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_stop)

    def Stop(self):
        self._stop()

    def _play_pause(self):
        def _play_pause():
            if self._playback_status() == "Playing":
                self.playback_service.pause()
            else:
                self.playback_service.play()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_play_pause)

    def PlayPause(self):
        self._play_pause()

    def _next(self):
        def _next():
            self.playback_service.play_next()
            self.emit_player_properties(["PlaybackStatus", "Metadata"])
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_next)

    def Next(self):
        self._next()

    def _previous(self):
        def _previous():
            self.playback_service.play_previous()
            self.emit_player_properties(["PlaybackStatus", "Metadata"])
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_previous)

    def Previous(self):
        self._previous()

    def _seek(self, offset):
        def _seek():
            ms = int(offset) // 1000
            self.playback_service.seek(ms)
            self.emit_seeked(self.position_us())

        self._dispatch_to_ui(_seek)

    def Seek(self, offset):
        self._seek(offset)

    def _set_position(self, track_id, position):
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

    def SetPosition(self, track_id, position):
        self._set_position(track_id, position)

    def _set_volume(self, value):
        setter = getattr(self.playback_service, "set_volume", None)
        if not callable(setter):
            return

        def _set_volume():
            setter(float(value))
            self.emit_player_properties(["Volume"])

        self._dispatch_to_ui(_set_volume)

    def emit_seeked(self, position):
        self.player_adaptor.Seeked.emit(int(position))

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


@ClassInfo(**{"D-Bus Interface": ROOT_INTERFACE})
class _RootAdaptor(QDBusAbstractAdaptor):
    def __init__(self, service: MPRISService):
        super().__init__(service)
        self._service = service

    @Property(bool)
    def CanQuit(self):
        return bool(self._service.root_properties()["CanQuit"])

    @Property(bool)
    def CanRaise(self):
        return bool(self._service.root_properties()["CanRaise"])

    @Property(bool)
    def HasTrackList(self):
        return bool(self._service.root_properties()["HasTrackList"])

    @Property(str)
    def Identity(self):
        return str(self._service.root_properties()["Identity"])

    @Property(str)
    def DesktopEntry(self):
        return str(self._service.root_properties()["DesktopEntry"])

    @Property("QStringList")
    def SupportedUriSchemes(self):
        return list(self._service.root_properties()["SupportedUriSchemes"])

    @Property("QStringList")
    def SupportedMimeTypes(self):
        return list(self._service.root_properties()["SupportedMimeTypes"])

    @Slot()
    def Raise(self):
        self._service._raise()

    @Slot()
    def Quit(self):
        self._service._quit()


@ClassInfo(**{"D-Bus Interface": PLAYER_INTERFACE})
class _PlayerAdaptor(QDBusAbstractAdaptor):
    Seeked = Signal("qlonglong")

    def __init__(self, service: MPRISService):
        super().__init__(service)
        self._service = service

    @Property(str)
    def PlaybackStatus(self):
        return str(self._service.player_properties()["PlaybackStatus"])

    @Property(str)
    def LoopStatus(self):
        return str(self._service.player_properties()["LoopStatus"])

    @Property("double")
    def Rate(self):
        return float(self._service.player_properties()["Rate"])

    @Property(bool)
    def Shuffle(self):
        return bool(self._service.player_properties()["Shuffle"])

    @Property("QVariantMap")
    def Metadata(self):
        return dict(self._service.player_properties()["Metadata"])

    def _get_volume(self):
        return float(self._service.player_properties()["Volume"])

    def _set_volume(self, value):
        self._service._set_volume(value)

    @Property("qlonglong")
    def Position(self):
        return int(self._service.player_properties()["Position"])

    @Property("double")
    def MinimumRate(self):
        return float(self._service.player_properties()["MinimumRate"])

    @Property("double")
    def MaximumRate(self):
        return float(self._service.player_properties()["MaximumRate"])

    @Property(bool)
    def CanGoNext(self):
        return bool(self._service.player_properties()["CanGoNext"])

    @Property(bool)
    def CanGoPrevious(self):
        return bool(self._service.player_properties()["CanGoPrevious"])

    @Property(bool)
    def CanPlay(self):
        return bool(self._service.player_properties()["CanPlay"])

    @Property(bool)
    def CanPause(self):
        return bool(self._service.player_properties()["CanPause"])

    @Property(bool)
    def CanSeek(self):
        return bool(self._service.player_properties()["CanSeek"])

    @Property(bool)
    def CanControl(self):
        return bool(self._service.player_properties()["CanControl"])

    @Slot()
    def Play(self):
        self._service._play()

    @Slot()
    def Pause(self):
        self._service._pause()

    @Slot()
    def Stop(self):
        self._service._stop()

    @Slot()
    def PlayPause(self):
        self._service._play_pause()

    @Slot()
    def Next(self):
        self._service._next()

    @Slot()
    def Previous(self):
        self._service._previous()

    @Slot("qlonglong")
    def Seek(self, offset):
        self._service._seek(offset)

    @Slot("QDBusObjectPath", "qlonglong")
    def SetPosition(self, track_id, position):
        self._service._set_position(track_id, position)

    Volume = Property("double", _get_volume, _set_volume)


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

        export_options = QDBusConnection.RegisterOption.ExportAdaptors
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

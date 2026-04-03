import hashlib
import threading
from pathlib import Path
from typing import Any

import dbus
import dbus.mainloop.glib
import dbus.service
from gi.repository import GLib

from app import Bootstrap
from domain import PlaylistItem

MPRIS_PATH = "/org/mpris/MediaPlayer2"
MPRIS_NAME = "org.mpris.MediaPlayer2.musicplayer"


def _safe_str(value) -> str:
    return str(value or "")


def _safe_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_file_uri(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http"):
        return path
    try:
        return Path(path).expanduser().resolve().as_uri()
    except Exception:
        return ""


def _make_track_object_path(track):
    raw = str(track.track_id)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return dbus.ObjectPath(f"/org/mpris/MediaPlayer2/track/{digest}")


class MPRISService(dbus.service.Object):
    def __init__(self, bus, playback_service, main_window=None):
        self.bus = bus
        self.playback_service = playback_service
        self._main_window = main_window

        self.bus_name = dbus.service.BusName(MPRIS_NAME, bus)
        super().__init__(self.bus_name, MPRIS_PATH)

    # ------------------------
    # Helpers
    # ------------------------

    def _current_track(self) -> PlaylistItem:
        return self.playback_service.current_track

    def _position_us(self) -> int:
        method = getattr(self.playback_service, "position", None)
        seconds = method() if callable(method) else 0.0
        return int(_safe_float(seconds) * 1_000_000)

    def _playback_status(self) -> str:
        """
        Prefer playback_service.playback_status() if available:
            -> "playing" / "paused" / "stopped"
        fallback to is_playing bool.
        """
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

    def _metadata(self):
        track = self._current_track()
        if not track:
            return dbus.Dictionary({
                "mpris:trackid": dbus.ObjectPath("/org/mpris/MediaPlayer2/track/none"),
            }, signature="sv")

        return self._metadata_for(track)

    def _metadata_for(self, track: PlaylistItem) -> Any:
        title = _safe_str(track.title)
        artist = _safe_str(track.artist)
        album = _safe_str(track.album)
        duration = _safe_float(track.duration)
        cover_path = _safe_str(track.cover_path)
        track_path = _safe_str(track.local_path)

        artists = [artist] if artist else []
        metadata = {
            "mpris:trackid": _make_track_object_path(track),
            "xesam:title": dbus.String(title),
            "xesam:artist": dbus.Array(artists, signature="s"),
            "xesam:album": dbus.String(album),
            "mpris:length": dbus.Int64(int(duration * 1_000_000)),
        }

        art_url = _safe_file_uri(cover_path)
        if art_url:
            metadata["mpris:artUrl"] = dbus.String(art_url)

        track_url = _safe_file_uri(track_path)
        if track_url:
            metadata["xesam:url"] = dbus.String(track_url)

        return dbus.Dictionary(metadata, signature="sv")

    def _root_properties(self):
        return dbus.Dictionary({
            "CanQuit": dbus.Boolean(True),
            "CanRaise": dbus.Boolean(self._main_window is not None),
            "HasTrackList": dbus.Boolean(True),
            "Identity": dbus.String("MusicPlayer"),
            "SupportedUriSchemes": dbus.Array(["file", "http", "https"], signature="s"),
            "SupportedMimeTypes": dbus.Array(
                [
                    "audio/mpeg",
                    "audio/flac",
                    "audio/x-flac",
                    "audio/ogg",
                    "audio/wav",
                    "audio/mp4",
                    "audio/aac",
                ],
                signature="s"
            ),
        }, signature="sv")

    def _player_properties(self):
        return dbus.Dictionary({
            "PlaybackStatus": dbus.String(self._playback_status()),
            "LoopStatus": dbus.String(self._loop_status()),
            "Position": dbus.Int64(self._position_us()),
            "Metadata": self._metadata(),
            "Shuffle": dbus.Boolean(self._shuffle()),
            "CanControl": dbus.Boolean(True),
            "CanGoNext": dbus.Boolean(True),
            "CanGoPrevious": dbus.Boolean(True),
            "CanPlay": dbus.Boolean(True),
            "CanPause": dbus.Boolean(True),
            "CanSeek": dbus.Boolean(getattr(self.playback_service, "can_seek", True)),
            "Rate": dbus.Double(1.0),
            "MinimumRate": dbus.Double(1.0),
            "MaximumRate": dbus.Double(1.0),
            "Volume": dbus.Double(self._volume()),
        }, signature="sv")

    def _volume(self) -> float:
        return float(getattr(self.playback_service, "volume", 1.0))

    def _loop_status(self):
        value = str(getattr(self.playback_service, "loop_status", "None"))
        return value if value in ("None", "Track", "Playlist") else "None"

    def _shuffle(self) -> bool:
        return bool(getattr(self.playback_service, "shuffle", False))

    @dbus.service.method("org.mpris.MediaPlayer2.TrackList", out_signature="ao")
    def GetTracks(self):
        return dbus.Array(
            [_make_track_object_path(t) for t in self.playback_service.playlist],
            signature="o"
        )

    @dbus.service.method("org.mpris.MediaPlayer2.TrackList", in_signature="ao", out_signature="a{oa{sv}}")
    def GetTracksMetadata(self, track_ids):
        result = {}
        for t in self.playback_service.playlist:
            oid = _make_track_object_path(t)
            if oid in track_ids:
                result[oid] = self._metadata_for(t)
        return dbus.Dictionary(result, signature="oa{sv}")

    @dbus.service.signal("org.mpris.MediaPlayer2.TrackList", signature="aoo")
    def TrackListReplaced(self, tracks, current_track):
        pass

    # ------------------------
    # org.mpris.MediaPlayer2
    # ------------------------

    @dbus.service.method("org.mpris.MediaPlayer2")
    def Raise(self):
        if self._main_window:
            try:
                self._main_window.showNormal()
                self._main_window.raise_()
                self._main_window.activateWindow()
            except Exception:
                pass

    @dbus.service.method("org.mpris.MediaPlayer2")
    def Quit(self):
        if self._main_window:
            try:
                self._main_window.close()
            except Exception:
                pass

    # ------------------------
    # org.mpris.MediaPlayer2.Player
    # ------------------------

    @dbus.service.method("org.mpris.MediaPlayer2.Player")
    def Play(self):
        self.playback_service.play()
        self.emit_player_properties(["PlaybackStatus"])

    @dbus.service.method("org.mpris.MediaPlayer2.Player")
    def Pause(self):
        self.playback_service.pause()
        self.emit_player_properties(["PlaybackStatus"])

    @dbus.service.method("org.mpris.MediaPlayer2.Player")
    def Stop(self):
        self.playback_service.stop()
        self.emit_player_properties(["PlaybackStatus"])

    @dbus.service.method("org.mpris.MediaPlayer2.Player")
    def PlayPause(self):
        if self._playback_status() == "Playing":
            self.Pause()
        else:
            self.Play()

    @dbus.service.method("org.mpris.MediaPlayer2.Player")
    def Next(self):
        self.playback_service.play_next()
        self.emit_player_properties(["PlaybackStatus", "Metadata"])
        self.Seeked(dbus.Int64(self._position_us()))

    @dbus.service.method("org.mpris.MediaPlayer2.Player")
    def Previous(self):
        self.playback_service.play_previous()
        self.emit_player_properties(["PlaybackStatus", "Metadata"])
        self.Seeked(dbus.Int64(self._position_us()))

    @dbus.service.method("org.mpris.MediaPlayer2.Player", in_signature="x")
    def Seek(self, offset):
        ms = int(offset) / 1_000
        self.playback_service.seek(ms)
        self.Seeked(dbus.Int64(self._position_us()))

    @dbus.service.method("org.mpris.MediaPlayer2.Player", in_signature="ox")
    def SetPosition(self, track_id, position):
        track = self._current_track()
        if not track:
            return

        current_id = _make_track_object_path(track)
        print("SetPosition called", track_id, current_id, position)
        if track_id != current_id:
            return

        ms = int(position) / 1_000

        try:
            self.playback_service.seek(ms)
        except TypeError:
            pass

        self.Seeked(dbus.Int64(self._position_us()))

    # ------------------------
    # org.freedesktop.DBus.Properties
    # ------------------------

    @dbus.service.method(
        "org.freedesktop.DBus.Properties",
        in_signature="ss",
        out_signature="v"
    )
    def Get(self, interface_name, property_name):
        props = self.GetAll(interface_name)
        return props[property_name]

    @dbus.service.method(
        "org.freedesktop.DBus.Properties",
        in_signature="s",
        out_signature="a{sv}"
    )
    def GetAll(self, interface_name):
        if interface_name == "org.mpris.MediaPlayer2":
            return self._root_properties()

        if interface_name == "org.mpris.MediaPlayer2.Player":
            return self._player_properties()

        return dbus.Dictionary({}, signature="sv")

    @dbus.service.method(
        "org.freedesktop.DBus.Properties",
        in_signature="ssv"
    )
    def Set(self, interface_name, property_name, value):
        if interface_name == "org.mpris.MediaPlayer2.Player":
            if property_name == "Volume":
                setter = getattr(self.playback_service, "set_volume", None)
                if callable(setter):
                    setter(float(value))
                    self.emit_player_properties(["Volume"])
                    return

        raise dbus.exceptions.DBusException(
            "org.freedesktop.DBus.Error.PropertyReadOnly",
            f"Property {property_name} is read-only"
        )

    # ------------------------
    # Signals
    # ------------------------

    @dbus.service.signal("org.mpris.MediaPlayer2.Player", signature="x")
    def Seeked(self, position):
        pass

    @dbus.service.signal("org.freedesktop.DBus.Properties", signature="sa{sv}as")
    def PropertiesChanged(self, interface_name, changed_properties, invalidated_properties):
        pass

    # ------------------------
    # Emit helpers
    # ------------------------

    def emit_player_properties(self, names=None):
        all_props = self._player_properties()

        if names:
            changed = dbus.Dictionary(
                {k: all_props[k] for k in names if k in all_props},
                signature="sv"
            )
        else:
            changed = all_props

        self.PropertiesChanged(
            "org.mpris.MediaPlayer2.Player",
            changed,
            dbus.Array([], signature="s"),
        )

    def emit_root_properties(self, names=None):
        all_props = self._root_properties()

        if names:
            changed = dbus.Dictionary(
                {k: all_props[k] for k in names if k in all_props},
                signature="sv"
            )
        else:
            changed = all_props

        self.PropertiesChanged(
            "org.mpris.MediaPlayer2",
            changed,
            dbus.Array([], signature="s"),
        )


class MPRISController:
    def __init__(self, playback_service, main_window=None):
        self.playback_service = playback_service
        self._main_window = main_window
        self.loop = None
        self.loop_thread = None
        self.service = None
        self.bus = None
        self._started = False

        event_bus = Bootstrap.instance().event_bus
        event_bus.track_changed.connect(self.on_track_changed)
        event_bus.playback_state_changed.connect(self.on_playback_state_changed)
        event_bus.duration_changed.connect(self.on_duration_changed)
        event_bus.volume_changed.connect(self.on_volume_changed)
        event_bus.cover_updated.connect(self.on_cover_updated)

    def start(self):
        if self._started:
            return

        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        self.bus = dbus.SessionBus()

        self.service = MPRISService(
            self.bus,
            self.playback_service,
            self._main_window
        )

        self.loop = GLib.MainLoop()
        self.loop_thread = threading.Thread(
            target=self.loop.run,
            daemon=True,
            name="MPRIS-GLibLoop"
        )
        self.loop_thread.start()
        self._emit_tracklist()

        self._started = True
    def stop(self):
        if not self._started:
            return

        try:
            if self.loop and self.loop.is_running():
                self.loop.quit()
        except Exception:
            pass

        self.service = None
        self.bus = None
        self.loop = None
        self.loop_thread = None
        self._started = False

    def _emit_tracklist(self):
        if not self.service:
            return

        tracks = [
            _make_track_object_path(t)
            for t in self.playback_service.playlist
        ]

        current_track = self.playback_service.current_track
        current_id = (
            _make_track_object_path(current_track)
            if current_track else
            dbus.ObjectPath("/org/mpris/MediaPlayer2/track/none")
        )

        self.service.TrackListReplaced(
            dbus.Array(tracks, signature="o"),
            current_id
        )

    def on_playback_state_changed(self, *args):
        if self.service:
            self.service.emit_player_properties(["PlaybackStatus"])

    def on_track_changed(self, *args):
        if self.service:
            self.service.emit_player_properties(["Metadata", "PlaybackStatus"])
            self.service.Seeked(dbus.Int64(self.service._position_us()))
            self._emit_tracklist()

    def on_metadata_changed(self, *args):
        if self.service:
            self.service.emit_player_properties(["Metadata"])

    def on_duration_changed(self, *args):
        if self.service:
            self.service.emit_player_properties(["Metadata"])

    def on_volume_changed(self, *args):
        if self.service:
            self.service.emit_player_properties(["Volume"])

    def on_cover_updated(self, *args):
        if self.service:
            # 封面在 Metadata 里
            self.service.emit_player_properties(["Metadata"])

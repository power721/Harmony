"""Tests for MpvAudioBackend with a mocked python-mpv module."""

import sys

from infrastructure.audio import mpv_backend


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _FakeTimer:
    def __init__(self, _parent=None):
        self.timeout = _FakeSignal()
        self.interval = 0
        self.started = False

    def setInterval(self, interval: int):
        self.interval = interval

    def start(self):
        self.started = True

    def stop(self):
        self.started = False


class _FakeMPV:
    def __init__(self, **_kwargs):
        self.pause = False
        self.volume = 0
        self.af = ""
        self._commands = []
        self._observers = {}
        self._props = {
            "time-pos": 0.0,
            "duration": 0.0,
            "pause": False,
            "idle-active": True,
            "eof-reached": False,
            "volume": 0,
        }
        self.terminated = False

    def observe_property(self, prop, callback):
        self._observers[prop] = callback

    def command(self, *args):
        self._commands.append(args)
        if args and args[0] == "seek":
            self._props["time-pos"] = float(args[1])
        elif args and args[0] == "stop":
            self._props["idle-active"] = True

    def trigger(self, prop, value):
        self._props[prop] = value
        callback = self._observers[prop]
        callback(prop, value)

    def terminate(self):
        self.terminated = True

    def __getattr__(self, item):
        if item in self._props:
            return self._props[item]
        raise AttributeError(item)


class _FakeMPVModule:
    MPV = _FakeMPV


def test_mpv_backend_basic_flow(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()

    loaded = []
    ended = []
    states = []
    positions = []
    durations = []
    backend.media_loaded.connect(lambda: loaded.append(True))
    backend.end_of_media.connect(lambda: ended.append(True))
    backend.state_changed.connect(states.append)
    backend.position_changed.connect(positions.append)
    backend.duration_changed.connect(durations.append)

    backend.set_source("/tmp/demo.flac")
    backend.play()
    backend.pause()
    backend.seek(4200)
    backend.set_volume(66)
    backend.set_eq_bands([1.0] * 10)

    player = backend._player
    player.trigger("idle-active", False)
    player.trigger("duration", 123.4)
    player.trigger("time-pos", 4.2)
    player.trigger("pause", True)
    player.trigger("eof-reached", True)

    assert backend.get_source_path() == "/tmp/demo.flac"
    assert backend.position() == 4200
    assert backend.get_volume() == 66
    assert backend.supports_eq() is True
    assert "equalizer" in backend._player.af
    assert loaded == [True]
    assert ended == [True]
    assert positions and positions[-1] == 4200
    assert durations and durations[-1] == 123400
    assert states

    backend.stop()
    player.trigger("eof-reached", True)
    assert ended == [True]

    backend.cleanup()
    assert backend._poll_timer.started is False
    assert backend._player.terminated is True


def test_mpv_backend_idle_fallback_and_play_restart_from_eof(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()

    ended = []
    backend.end_of_media.connect(lambda: ended.append(True))

    # Media becomes ready, then idle without explicit stop -> should emit end once.
    player = backend._player
    player.trigger("idle-active", False)
    player.trigger("idle-active", True)
    player.trigger("idle-active", True)
    assert ended == [True]

    # EOF play restart should seek to 0 before unpausing.
    player._props["eof-reached"] = True
    backend.play()
    seek_calls = [c for c in player._commands if c and c[0] == "seek"]
    assert seek_calls

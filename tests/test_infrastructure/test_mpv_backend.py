"""Tests for MpvAudioBackend with a mocked python-mpv module."""

import sys

from infrastructure.audio import mpv_backend
from infrastructure.audio.audio_backend import AudioEffectsState


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

    def isActive(self):
        return self.started


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


def test_import_mpv_module_uses_packaged_lib_when_system_lookup_fails(monkeypatch):
    packaged_lib = "/tmp/AppDir/usr/bin/libmpv.so.2"
    original_find_library = mpv_backend.ctypes.util.find_library
    observed_lookups = []
    fake_module = _FakeMPVModule()

    def fake_find_library(name):
        if name == "mpv":
            return None
        return original_find_library(name)

    def fake_import_module(name):
        assert name == "mpv"
        observed_lookups.append(mpv_backend.ctypes.util.find_library("mpv"))
        return fake_module

    monkeypatch.setattr(mpv_backend.ctypes.util, "find_library", fake_find_library)
    monkeypatch.setattr(mpv_backend, "_find_packaged_libmpv", lambda: packaged_lib)
    monkeypatch.setattr(mpv_backend.importlib, "import_module", fake_import_module)

    module = mpv_backend._import_mpv_module()

    assert module is fake_module
    assert observed_lookups == [packaged_lib]
    assert mpv_backend.ctypes.util.find_library("mpv") is None


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
    backend.set_audio_effects(
        AudioEffectsState(
            enabled=True,
            bass_boost=25.0,
            treble_boost=35.0,
            reverb_level=40.0,
            stereo_enhance=30.0,
        )
    )

    player = backend._player
    player.trigger("idle-active", False)
    player.trigger("duration", 123.4)
    player.trigger("time-pos", 4.2)
    player.trigger("pause", True)
    # Set position near end to trigger EOF (within 0.5s of duration)
    player.trigger("time-pos", 123.0)
    player.trigger("eof-reached", True)

    assert backend.get_source_path() == "/tmp/demo.flac"
    # Position is now 123.0s (near end) after the time-pos trigger
    assert backend.position() == 123000
    assert backend.get_volume() == 66
    assert backend.supports_eq() is True
    assert backend.supports_audio_effects() is True
    assert "equalizer" in backend._player.af
    assert "aecho" in backend._player.af
    assert "extrastereo" in backend._player.af
    assert loaded == [True]
    assert ended == [True]
    # Last position is 123000 (near end), not 4200
    assert positions and positions[-1] == 123000
    assert durations and durations[-1] == 123400
    assert states

    backend.stop()
    player.trigger("eof-reached", True)
    assert ended == [True]

    backend.cleanup()
    assert backend._poll_timer.started is False
    assert backend._player.terminated is True


def test_mpv_backend_can_disable_all_audio_effects(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()
    backend.set_eq_bands([3.0] * 10)
    assert "equalizer" in backend._player.af

    backend.set_audio_effects(AudioEffectsState(enabled=False))
    assert backend._player.af == ""


def test_mpv_backend_idle_fallback_and_play_restart_from_eof(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()

    ended = []
    backend.end_of_media.connect(lambda: ended.append(True))

    # Media becomes ready, then transient idle without EOF evidence -> should NOT end.
    player = backend._player
    player.trigger("idle-active", False)
    player.trigger("idle-active", True)
    assert ended == []

    # Stale EOF flag alone should not trigger idle fallback end.
    player._props["eof-reached"] = True
    player._props["duration"] = 180.0
    player._props["time-pos"] = 3.0
    player.trigger("idle-active", True)
    assert ended == []

    # Near-end timeline should trigger end.
    player._props["time-pos"] = 179.8
    player.trigger("idle-active", True)
    assert ended == [True]

    # EOF play restart should seek to 0 before unpausing.
    player._props["eof-reached"] = True
    backend.play()
    seek_calls = [c for c in player._commands if c and c[0] == "seek"]
    assert seek_calls


def test_mpv_backend_poll_timer_only_runs_when_active_media(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()
    player = backend._player

    # No media active -> no polling loop.
    assert backend._poll_timer.started is False

    # Media becomes active -> polling starts.
    player.trigger("idle-active", False)
    assert backend._poll_timer.started is True

    # Explicit stop should stop polling immediately.
    backend.stop()
    assert backend._poll_timer.started is False


def test_mpv_seek_executes_when_timeline_ready_even_if_media_loaded_not_observed(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()
    player = backend._player

    # Simulate a delayed/missed idle transition callback state update:
    # backend still thinks media isn't ready, but mpv timeline is active.
    backend._media_ready = False
    player._props["idle-active"] = False
    player._props["duration"] = 180.0

    backend.seek(92000)

    # Seek should run immediately instead of being stuck in pending state.
    assert backend._pending_seek_ms is None
    assert backend.position() == 92000


def test_mpv_seek_does_not_use_stale_timeline_when_idle_active(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()
    player = backend._player

    # Simulate stale values from previous track while new media is still idle.
    backend._media_ready = False
    player._props["idle-active"] = True
    player._props["duration"] = 215.0
    player._props["time-pos"] = 12.0

    backend.seek(1500)

    # Should defer seek until media becomes active; no immediate seek command.
    assert backend._pending_seek_ms == 1500
    seek_calls = [c for c in player._commands if c and c[0] == "seek"]
    assert seek_calls == []


def test_mpv_backend_ignores_eof_signal_when_not_near_end(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()
    player = backend._player

    ended = []
    backend.end_of_media.connect(lambda: ended.append(True))

    player.trigger("idle-active", False)
    player.trigger("duration", 180.0)
    player.trigger("time-pos", 2.0)
    player.trigger("eof-reached", True)

    assert ended == []


def test_mpv_backend_marks_media_loaded_on_duration_update_after_active_replace(monkeypatch):
    monkeypatch.setattr(mpv_backend, "QTimer", _FakeTimer)
    monkeypatch.setitem(sys.modules, "mpv", _FakeMPVModule())

    backend = mpv_backend.MpvAudioBackend()
    player = backend._player

    loaded = []
    backend.media_loaded.connect(lambda: loaded.append(True))

    # Simulate previous track already active; replacing source may not produce
    # a fresh idle-active transition in some mpv environments.
    player._props["idle-active"] = False
    backend._media_ready = True

    backend.set_source("/tmp/next.ogg")
    assert backend._media_ready is False

    # New track metadata arrives while mpv still reports active timeline.
    player.trigger("duration", 210.0)

    assert backend._media_ready is True
    assert loaded == [True]

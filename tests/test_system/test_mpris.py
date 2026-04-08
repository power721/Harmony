import importlib.util
import sys
import types
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MPRIS_PATH = PROJECT_ROOT / "system" / "mpris.py"


class _FakeDbusObject:
    def __init__(self, *_args, **_kwargs):
        pass


class _FakeBusName:
    def __init__(self, *_args, **_kwargs):
        pass


class _FakeLoop:
    def __init__(self):
        self.running = False

    def run(self):
        self.running = True

    def quit(self):
        self.running = False

    def is_running(self):
        return self.running


class _FakeThread:
    def __init__(self, target=None, **_kwargs):
        self._target = target

    def start(self):
        if self._target is not None:
            self._target()


class _FakeSignal:
    def connect(self, _callback):
        pass


class _FakeEventBus:
    def __init__(self):
        self.track_changed = _FakeSignal()
        self.playback_state_changed = _FakeSignal()
        self.duration_changed = _FakeSignal()
        self.volume_changed = _FakeSignal()
        self.cover_updated = _FakeSignal()


class _FakeBootstrapInstance:
    def __init__(self):
        self.event_bus = _FakeEventBus()


class _FakeBootstrap:
    @classmethod
    def instance(cls):
        return _FakeBootstrapInstance()


def _identity_decorator(*_args, **_kwargs):
    def decorator(fn):
        return fn

    return decorator


def _load_mpris_module(monkeypatch):
    fake_dbus = types.ModuleType("dbus")
    fake_dbus.ObjectPath = str
    fake_dbus.Dictionary = lambda value=None, signature=None: dict(value or {})
    fake_dbus.String = str
    fake_dbus.Array = lambda value, signature=None: list(value)
    fake_dbus.Int64 = int
    fake_dbus.Boolean = bool
    fake_dbus.Double = float
    fake_dbus.SessionBus = lambda: object()
    fake_dbus.exceptions = types.SimpleNamespace(DBusException=RuntimeError)
    fake_dbus.mainloop = types.SimpleNamespace(
        glib=types.SimpleNamespace(DBusGMainLoop=lambda set_as_default=False: None)
    )
    fake_dbus.service = types.SimpleNamespace(
        Object=_FakeDbusObject,
        BusName=_FakeBusName,
        method=_identity_decorator,
        signal=_identity_decorator,
    )

    fake_gi = types.ModuleType("gi")
    fake_repository = types.ModuleType("gi.repository")
    fake_repository.GLib = types.SimpleNamespace(MainLoop=_FakeLoop)
    fake_gi.repository = fake_repository

    fake_app = types.ModuleType("app")
    fake_app.Bootstrap = _FakeBootstrap

    fake_domain = types.ModuleType("domain")
    fake_domain.PlaylistItem = object

    monkeypatch.setitem(sys.modules, "dbus", fake_dbus)
    monkeypatch.setitem(sys.modules, "dbus.mainloop", fake_dbus.mainloop)
    monkeypatch.setitem(sys.modules, "dbus.mainloop.glib", fake_dbus.mainloop.glib)
    monkeypatch.setitem(sys.modules, "dbus.service", fake_dbus.service)
    monkeypatch.setitem(sys.modules, "gi", fake_gi)
    monkeypatch.setitem(sys.modules, "gi.repository", fake_repository)
    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setitem(sys.modules, "domain", fake_domain)

    spec = importlib.util.spec_from_file_location("mpris_under_test", MPRIS_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_mpris_service_dispatches_playback_commands_via_ui_dispatcher(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    playback_calls = []
    dispatched = []
    property_updates = []

    class PlaybackService:
        def play(self):
            playback_calls.append("play")

    def dispatcher(fn, *args, **kwargs):
        dispatched.append((fn, args, kwargs))

    service = mpris.MPRISService(
        bus=object(),
        playback_service=PlaybackService(),
        ui_dispatcher=dispatcher,
    )
    service.emit_player_properties = lambda names=None: property_updates.append(names)

    service.Play()

    assert playback_calls == []
    assert property_updates == []
    assert len(dispatched) == 1

    fn, args, kwargs = dispatched.pop()
    fn(*args, **kwargs)

    assert playback_calls == ["play"]
    assert property_updates == [["PlaybackStatus"]]


def test_mpris_service_dispatches_window_commands_via_ui_dispatcher(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    window_calls = []
    dispatched = []

    class Window:
        def showNormal(self):
            window_calls.append("showNormal")

        def raise_(self):
            window_calls.append("raise_")

        def activateWindow(self):
            window_calls.append("activateWindow")

    def dispatcher(fn, *args, **kwargs):
        dispatched.append((fn, args, kwargs))

    service = mpris.MPRISService(
        bus=object(),
        playback_service=object(),
        main_window=Window(),
        ui_dispatcher=dispatcher,
    )

    service.Raise()

    assert window_calls == []
    assert len(dispatched) == 1

    fn, args, kwargs = dispatched.pop()
    fn(*args, **kwargs)

    assert window_calls == ["showNormal", "raise_", "activateWindow"]


def test_mpris_controller_passes_ui_dispatcher_to_service(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    captured = {}

    class FakeService:
        def __init__(self, bus, playback_service, main_window=None, ui_dispatcher=None):
            captured["bus"] = bus
            captured["playback_service"] = playback_service
            captured["main_window"] = main_window
            captured["ui_dispatcher"] = ui_dispatcher

        def TrackListReplaced(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(mpris, "MPRISService", FakeService)
    monkeypatch.setattr(mpris.threading, "Thread", _FakeThread)
    monkeypatch.setattr(mpris.GLib, "MainLoop", _FakeLoop)

    playback_service = types.SimpleNamespace(playlist=[], current_track=None)
    controller = mpris.MPRISController(playback_service=playback_service)
    controller._main_window = object()
    controller.ui_dispatcher = object()

    controller.start()

    assert captured["playback_service"] is playback_service
    assert captured["main_window"] is controller._main_window
    assert captured["ui_dispatcher"] is controller.ui_dispatcher

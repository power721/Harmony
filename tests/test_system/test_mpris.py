import importlib.util
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MPRIS_MODULE_PATH = PROJECT_ROOT / "system" / "mpris.py"


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


def _load_mpris_module(monkeypatch):
    fake_app = types.ModuleType("app")
    fake_app.Bootstrap = _FakeBootstrap

    fake_domain = types.ModuleType("domain")
    fake_domain.PlaylistItem = object

    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setitem(sys.modules, "domain", fake_domain)

    spec = importlib.util.spec_from_file_location("mpris_under_test", MPRIS_MODULE_PATH)
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


def test_mpris_service_handles_ui_dispatcher_failure(monkeypatch, caplog):
    mpris = _load_mpris_module(monkeypatch)

    called = []

    class PlaybackService:
        def play(self):
            called.append("play")

    def dispatcher(_fn, *_args, **_kwargs):
        raise RuntimeError("dispatcher failed")

    service = mpris.MPRISService(
        playback_service=PlaybackService(),
        ui_dispatcher=dispatcher,
    )

    service.Play()

    assert called == []
    assert "UI dispatch failed" in caplog.text


def test_mpris_service_returns_player_properties_without_tracklist(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    playback_service = types.SimpleNamespace(
        current_track=None,
        is_playing=False,
        is_stopped=True,
        can_seek=True,
        volume=0.5,
        loop_status="None",
        shuffle=False,
        position=lambda: 321.0,
    )

    service = mpris.MPRISService(playback_service=playback_service)
    props = service.player_properties()

    assert "Metadata" in props
    assert "CanControl" in props
    assert "Position" in props
    assert props["Position"] == 321000
    assert service.root_properties()["HasTrackList"] is False


def test_mpris_service_root_properties_include_desktop_entry(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    service = mpris.MPRISService(playback_service=object())

    assert service.root_properties()["DesktopEntry"] == "harmony"


def test_mpris_player_adaptor_declares_int64_position_and_writable_volume(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    service = mpris.MPRISService(playback_service=object())
    adaptor = service.player_adaptor
    meta_object = adaptor.metaObject()

    properties = {}
    for index in range(meta_object.propertyOffset(), meta_object.propertyCount()):
        prop = meta_object.property(index)
        properties[prop.name()] = prop

    assert properties["Position"].typeName() == "qlonglong"
    assert properties["Position"].isReadable() is True
    assert properties["Volume"].isWritable() is True


def test_mpris_player_adaptor_declares_int64_seek_signatures(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    service = mpris.MPRISService(playback_service=object())
    adaptor = service.player_adaptor
    meta_object = adaptor.metaObject()

    methods = {
        bytes(meta_object.method(index).methodSignature()).decode(): meta_object.method(index)
        for index in range(meta_object.methodOffset(), meta_object.methodCount())
    }

    assert "Seek(qlonglong)" in methods
    assert "SetPosition(QDBusObjectPath,qlonglong)" in methods


def test_mpris_controller_passes_ui_dispatcher_to_service(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    captured = {}

    class FakeBus:
        def registerService(self, _name):
            return True

        def registerObject(self, _path, _service, _options):
            return True

    class FakeService:
        def __init__(self, playback_service, main_window=None, ui_dispatcher=None):
            captured["playback_service"] = playback_service
            captured["main_window"] = main_window
            captured["ui_dispatcher"] = ui_dispatcher

    monkeypatch.setattr(mpris, "MPRISService", FakeService)
    monkeypatch.setattr(mpris.QDBusConnection, "sessionBus", staticmethod(lambda: FakeBus()))

    playback_service = types.SimpleNamespace(playlist=[], current_track=None)
    controller = mpris.MPRISController(playback_service=playback_service)
    controller._main_window = object()
    controller.ui_dispatcher = object()

    controller.start()

    assert captured["playback_service"] is playback_service
    assert captured["main_window"] is controller._main_window
    assert captured["ui_dispatcher"] is controller.ui_dispatcher


def test_mpris_controller_track_change_uses_stable_service_reference(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    controller = mpris.MPRISController.__new__(mpris.MPRISController)
    controller._service_lock = mpris.threading.Lock()
    controller.playback_service = types.SimpleNamespace(current_track=None)

    class FakeService:
        def __init__(self):
            self.seeked = []

        def emit_player_properties(self, _names):
            controller.service = None

        def emit_seeked(self, value):
            self.seeked.append(value)

        def position_us(self):
            return 123

    fake_service = FakeService()
    controller.service = fake_service

    mpris.MPRISController.on_track_changed(controller)

    assert fake_service.seeked == [123]


def test_mpris_controller_start_raises_when_service_registration_fails(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    class FakeBus:
        def isConnected(self):
            return True

        def registerService(self, _name):
            return False

        def lastError(self):
            return types.SimpleNamespace(message=lambda: "name already owned")

    monkeypatch.setattr(mpris.QDBusConnection, "sessionBus", staticmethod(lambda: FakeBus()))

    controller = mpris.MPRISController(
        playback_service=types.SimpleNamespace(playlist=[], current_track=None),
    )

    with pytest.raises(RuntimeError, match="name already owned"):
        controller.start()


def test_mpris_controller_start_reports_owner_when_service_name_is_taken(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    class FakeInterface:
        def serviceOwner(self, name):
            assert name == mpris.MPRIS_NAME
            return ":1.2032"

        def servicePid(self, name):
            assert name == mpris.MPRIS_NAME
            return 381574

    class FakeBus:
        def isConnected(self):
            return True

        def registerService(self, _name):
            return False

        def lastError(self):
            return types.SimpleNamespace(message=lambda: "")

        def interface(self):
            return FakeInterface()

    monkeypatch.setattr(mpris.QDBusConnection, "sessionBus", staticmethod(lambda: FakeBus()))

    controller = mpris.MPRISController(
        playback_service=types.SimpleNamespace(playlist=[], current_track=None),
    )

    with pytest.raises(RuntimeError, match=r"already owned by :1\.2032 \(pid=381574\)"):
        controller.start()


def test_mpris_controller_start_unwraps_qdbus_reply_owner_and_pid(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    class FakeReply:
        def __init__(self, value):
            self._value = value

        def value(self):
            return self._value

    class FakeInterface:
        def serviceOwner(self, name):
            assert name == mpris.MPRIS_NAME
            return FakeReply(":1.2032")

        def servicePid(self, name):
            assert name == mpris.MPRIS_NAME
            return FakeReply(381574)

    class FakeBus:
        def isConnected(self):
            return True

        def registerService(self, _name):
            return False

        def lastError(self):
            return types.SimpleNamespace(message=lambda: "")

        def interface(self):
            return FakeInterface()

    monkeypatch.setattr(mpris.QDBusConnection, "sessionBus", staticmethod(lambda: FakeBus()))

    controller = mpris.MPRISController(
        playback_service=types.SimpleNamespace(playlist=[], current_track=None),
    )

    with pytest.raises(RuntimeError, match=r"already owned by :1\.2032 \(pid=381574\)"):
        controller.start()

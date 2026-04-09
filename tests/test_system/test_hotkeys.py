import sys
import types
from types import SimpleNamespace

import system.hotkeys as hotkeys


def test_setup_media_key_handler_uses_mpris_controller_on_linux(monkeypatch):
    class FakeBootstrap:
        @classmethod
        def instance(cls):
            return SimpleNamespace(mpris_controller=object())

    fake_app = types.ModuleType("app")
    fake_app.Bootstrap = FakeBootstrap

    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    assert hotkeys.setup_media_key_handler(player=object()) is True


def test_setup_media_key_handler_returns_false_when_linux_mpris_unavailable(monkeypatch):
    class FakeBootstrap:
        @classmethod
        def instance(cls):
            return SimpleNamespace(mpris_controller=None)

    fake_app = types.ModuleType("app")
    fake_app.Bootstrap = FakeBootstrap

    monkeypatch.setitem(sys.modules, "app", fake_app)
    monkeypatch.setattr("platform.system", lambda: "Linux")

    assert hotkeys.setup_media_key_handler(player=object()) is False


def test_setup_media_key_handler_replaces_existing_windows_listener(monkeypatch):
    listeners = []

    class FakeListener:
        def __init__(self, on_press):
            self.on_press = on_press
            self.started = False
            self.stopped = False
            listeners.append(self)

        def start(self):
            self.started = True

        def stop(self):
            self.stopped = True

    fake_keyboard = types.SimpleNamespace(
        Key=types.SimpleNamespace(
            media_play_pause="play_pause",
            media_next="next",
            media_previous="previous",
        ),
        Listener=FakeListener,
    )
    fake_pynput = types.ModuleType("pynput")
    fake_pynput.keyboard = fake_keyboard

    monkeypatch.setitem(sys.modules, "pynput", fake_pynput)
    monkeypatch.setattr("platform.system", lambda: "Windows")

    player = SimpleNamespace(
        engine=SimpleNamespace(
            state=None,
            pause=lambda: None,
            play=lambda: None,
            play_next=lambda: None,
            play_previous=lambda: None,
        )
    )

    hotkeys._listener = None
    assert hotkeys.setup_media_key_handler(player) is True
    first_listener = hotkeys._listener

    assert hotkeys.setup_media_key_handler(player) is True

    assert first_listener.stopped is True
    assert hotkeys._listener is listeners[-1]
    assert hotkeys._listener.started is True


def test_cleanup_stops_windows_listener_and_clears_reference():
    class FakeListener:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    listener = FakeListener()
    hotkeys._listener = listener

    hotkeys.cleanup()

    assert listener.stopped is True
    assert hotkeys._listener is None

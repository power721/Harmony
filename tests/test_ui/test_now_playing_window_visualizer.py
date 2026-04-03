"""Integration-style tests for NowPlayingWindow visualizer wiring (stubbed)."""

from types import SimpleNamespace

from ui.windows.now_playing_window import NowPlayingWindow


class _StubSignal:
    def __init__(self):
        self._callbacks = []
        self.connect_calls = 0
        self.disconnect_calls = 0

    def connect(self, callback):
        self.connect_calls += 1
        self._callbacks.append(callback)

    def emit(self, payload):
        for callback in list(self._callbacks):
            callback(payload)

    def disconnect(self, callback):
        self.disconnect_calls += 1
        for index, cb in enumerate(list(self._callbacks)):
            if cb == callback:
                self._callbacks.pop(index)
                break


class _DummyVisualizer:
    def __init__(self):
        self.visible = None
        self.frames = []

    def show(self):
        self.visible = True

    def hide(self):
        self.visible = False

    def update_frame(self, frame):
        self.frames.append(frame)


class _DummyBackend:
    def __init__(self, supports: bool):
        self._supports = supports

    def supports_visualizer(self) -> bool:
        return self._supports


def _build_window(*, backend, signal=None):
    engine = SimpleNamespace(
        backend=backend,
        visualizer_frame=signal or _StubSignal(),
    )
    playback = SimpleNamespace(engine=engine)

    window = NowPlayingWindow.__new__(NowPlayingWindow)
    window._playback = playback
    window._visualizer_widget = _DummyVisualizer()
    window._visualizer_signal = None
    window._visualizer_signal_connected = False
    window._visualizer_supported = False
    window._lyrics_thread = None
    window.closed = SimpleNamespace(emit=lambda *_, **__: None)
    return window, engine


def test_refresh_visualizer_hides_when_backend_lacks_support():
    backend = _DummyBackend(False)
    window, _ = _build_window(backend=backend)
    window._visualizer_widget.show()

    window._refresh_visualizer_visibility()

    assert window._visualizer_widget.visible is False


def test_refresh_visualizer_shows_when_backend_supports():
    backend = _DummyBackend(True)
    window, _ = _build_window(backend=backend)

    window._refresh_visualizer_visibility()

    assert window._visualizer_widget.visible is True


def test_refresh_visualizer_handles_missing_interface():
    class _BackendWithoutMethod:
        pass

    window, _ = _build_window(backend=_BackendWithoutMethod())
    window._visualizer_widget.show()

    window._refresh_visualizer_visibility()

    assert window._visualizer_widget.visible is False


def test_connect_visualizer_signal_routes_frames():
    backend = _DummyBackend(True)
    signal = _StubSignal()
    window, engine = _build_window(backend=backend, signal=signal)

    window._connect_visualizer_signal()

    payload = {"mode": "spectrum", "bins": [0.1, 0.2, 0.3]}
    engine.visualizer_frame.emit(payload)
    assert window._visualizer_widget.frames == [payload]


def test_connect_visualizer_signal_is_idempotent():
    backend = _DummyBackend(True)
    signal = _StubSignal()
    window, _ = _build_window(backend=backend, signal=signal)

    window._connect_visualizer_signal()
    window._connect_visualizer_signal()

    assert signal.connect_calls == 1
    assert window._visualizer_signal_connected is True
    assert signal._callbacks.count(window._visualizer_widget.update_frame) == 1


def test_close_event_disconnects_visualizer_signal():
    backend = _DummyBackend(True)
    signal = _StubSignal()
    window, engine = _build_window(backend=backend, signal=signal)
    event = SimpleNamespace(accept=lambda: None)

    window._connect_visualizer_signal()
    assert window._visualizer_signal_connected is True
    first_payload = {"mode": "spectrum", "bins": [0.1]}
    engine.visualizer_frame.emit(first_payload)
    assert window._visualizer_widget.frames == [first_payload]

    window.closeEvent(event)

    assert signal.disconnect_calls == 1
    assert window._visualizer_signal_connected is False
    second_payload = {"mode": "spectrum", "bins": [0.5]}
    engine.visualizer_frame.emit(second_payload)
    assert window._visualizer_widget.frames == [first_payload]


def test_close_event_disconnect_is_idempotent():
    backend = _DummyBackend(True)
    signal = _StubSignal()
    window, _ = _build_window(backend=backend, signal=signal)
    event = SimpleNamespace(accept=lambda: None)

    window._connect_visualizer_signal()

    window.closeEvent(event)
    window.closeEvent(event)

    assert signal.disconnect_calls == 1

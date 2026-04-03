"""Integration-style tests for NowPlayingWindow visualizer wiring (stubbed)."""

from types import SimpleNamespace

from ui.windows.now_playing_window import NowPlayingWindow


class _StubSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, payload):
        for callback in list(self._callbacks):
            callback(payload)


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

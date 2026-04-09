# QtDBus MPRIS Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Linux MPRIS backend with `PySide6.QtDBus` so AppImage builds no longer depend on host `dbus-python` / `PyGObject`, while preserving the current root/player MPRIS behavior and intentionally removing `TrackList`.

**Architecture:** Keep `Bootstrap.start_mpris(main_window, ui_dispatcher)` and `MPRISController` as the app-facing integration points, but rebuild the runtime detection and D-Bus export layer around `QtDBus`. The new controller should own the session bus registration and expose one Qt-based D-Bus object implementing `org.mpris.MediaPlayer2` and `org.mpris.MediaPlayer2.Player`, with all UI-affecting actions still routed through `ui_dispatcher`.

**Tech Stack:** Python 3.12, PySide6, QtDBus, pytest

---

### Task 1: Replace Linux runtime readiness checks with QtDBus-only detection

**Files:**
- Modify: `app/bootstrap.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_app/test_plugin_bootstrap.py`

- [ ] **Step 1: Write the failing bootstrap readiness tests**

```python
def test_linux_mpris_runtime_is_ready_when_qtdbus_is_available(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_can_import_linux_mpris_runtime",
        lambda: (True, None),
    )

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is True
    assert reason is None


def test_linux_mpris_runtime_reports_qtdbus_failure(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        bootstrap_module,
        "_can_import_linux_mpris_runtime",
        lambda: (False, "QtDBus session bus unavailable"),
    )

    ready, reason = bootstrap_module._ensure_linux_mpris_runtime()

    assert ready is False
    assert reason == "QtDBus session bus unavailable"
```

- [ ] **Step 2: Run the bootstrap tests to verify they fail against the old fallback logic**

Run: `uv run pytest tests/test_app/test_plugin_bootstrap.py::test_linux_mpris_runtime_is_ready_when_qtdbus_is_available tests/test_app/test_plugin_bootstrap.py::test_linux_mpris_runtime_reports_qtdbus_failure -v`
Expected: FAIL because `app/bootstrap.py` still probes `dbus` / `gi` and host Python module roots.

- [ ] **Step 3: Replace Linux runtime probing with QtDBus + session bus detection**

```python
def _can_import_linux_mpris_runtime() -> tuple[bool, Optional[str]]:
    try:
        from PySide6.QtDBus import QDBusConnection
    except ImportError as exc:
        return False, str(exc)

    bus = QDBusConnection.sessionBus()
    if not bus.isConnected():
        return False, "QtDBus session bus unavailable"
    return True, None


def _ensure_linux_mpris_runtime() -> tuple[bool, Optional[str]]:
    if sys.platform != "linux":
        return True, None
    return _can_import_linux_mpris_runtime()
```

- [ ] **Step 4: Update the bootstrap warning text to match the new runtime contract**

```python
logger.warning(
    "MPRIS disabled: Linux QtDBus runtime unavailable (%s).",
    self._mpris_disabled_reason,
)
```

- [ ] **Step 5: Remove the obsolete optional Linux dependency**

```toml
[project.optional-dependencies]
dev = [
    "pyinstaller>=6.19.0",
    "pytest>=7.0.0",
    "ruff>=0.1.0",
]
```

- [ ] **Step 6: Run bootstrap packaging-adjacent tests**

Run: `uv run pytest tests/test_app/test_plugin_bootstrap.py -v`
Expected: PASS with no references to host `dbus-python` / `gi` fallback.

### Task 2: Rebuild `system/mpris.py` around QtDBus while preserving root/player behavior

**Files:**
- Modify: `system/mpris.py`
- Test: `tests/test_system/test_mpris.py`

- [ ] **Step 1: Write the failing unit tests for the retained MPRIS surface**

```python
def test_mpris_service_dispatches_playback_commands_via_ui_dispatcher(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    playback_calls = []
    dispatched = []

    class PlaybackService:
        def play(self):
            playback_calls.append("play")

    def dispatcher(fn, *args, **kwargs):
        dispatched.append((fn, args, kwargs))

    service = mpris.MPRISService(
        playback_service=PlaybackService(),
        ui_dispatcher=dispatcher,
    )

    service.Play()

    assert playback_calls == []
    assert len(dispatched) == 1


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
    )

    service = mpris.MPRISService(playback_service=playback_service)
    props = service.player_properties()

    assert "Metadata" in props
    assert "CanControl" in props
    assert "Position" in props
    assert service.root_properties()["HasTrackList"] is False
```

- [ ] **Step 2: Run the MPRIS unit tests to verify they fail against the old dbus-python implementation**

Run: `uv run pytest tests/test_system/test_mpris.py -v`
Expected: FAIL because the current module imports `dbus` / `gi`, exposes `TrackList`, and uses GLib loop/thread primitives.

- [ ] **Step 3: Replace `dbus-python` service types with a QtDBus-exported QObject**

```python
from PySide6.QtCore import QObject, Property, Signal, Slot
from PySide6.QtDBus import QDBusConnection


class MPRISService(QObject):
    seeked = Signal(int)
    properties_changed = Signal(str, "QVariantMap", list)

    def __init__(self, playback_service, main_window=None, ui_dispatcher=None):
        super().__init__()
        self.playback_service = playback_service
        self._main_window = main_window
        self._ui_dispatcher = ui_dispatcher

    @Slot()
    def Play(self):
        def _play():
            self.playback_service.play()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_play)

    @Slot()
    def Pause(self):
        def _pause():
            self.playback_service.pause()
            self.emit_player_properties(["PlaybackStatus"])

        self._dispatch_to_ui(_pause)

    def root_properties(self) -> dict[str, object]:
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

    def player_properties(self) -> dict[str, object]:
        return {
            "PlaybackStatus": self._playback_status(),
            "Metadata": self._metadata(),
            "Position": self._position_us(),
            "LoopStatus": self._loop_status(),
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
```

- [ ] **Step 4: Move bus registration into the controller and remove the GLib loop thread**

```python
class MPRISController:
    def start(self):
        if self._started:
            return

        self.bus = QDBusConnection.sessionBus()
        self.service = MPRISService(
            playback_service=self.playback_service,
            main_window=self._main_window,
            ui_dispatcher=self.ui_dispatcher,
        )

        if not self.bus.registerService(MPRIS_NAME):
            raise RuntimeError(self.bus.lastError().message())

        if not self.bus.registerObject(MPRIS_PATH, self.service):
            self.bus.unregisterService(MPRIS_NAME)
            raise RuntimeError(self.bus.lastError().message())

        self._started = True
```

- [ ] **Step 5: Remove the obsolete `TrackList` API and emission paths**

```python
def _root_properties(self):
    return {
        "HasTrackList": False,
        "CanQuit": True,
        "CanRaise": self._main_window is not None,
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


def on_track_changed(self, *args):
    service = self._get_service()
    if service:
        service.emit_player_properties(["Metadata", "PlaybackStatus"])
        service.emit_seeked(service.position_us())
```

- [ ] **Step 6: Implement a QtDBus-compatible `PropertiesChanged` emission path**

```python
def emit_player_properties(self, names=None):
    props = self.player_properties()
    changed = {name: props[name] for name in names or props.keys() if name in props}
    self.properties_changed.emit(
        "org.mpris.MediaPlayer2.Player",
        changed,
        [],
    )
```

- [ ] **Step 7: Run the MPRIS unit tests**

Run: `uv run pytest tests/test_system/test_mpris.py -v`
Expected: PASS with no imports from `dbus` / `gi` and no `TrackList` assertions remaining.

### Task 3: Update focused tests around controller startup and bus registration failures

**Files:**
- Modify: `tests/test_system/test_mpris.py`
- Modify: `tests/test_app/test_plugin_bootstrap.py`

- [ ] **Step 1: Add a failing startup test for session bus registration failure**

```python
def test_mpris_controller_start_raises_when_service_registration_fails(monkeypatch):
    mpris = _load_mpris_module(monkeypatch)

    class FakeBus:
        def isConnected(self):
            return True

        def registerService(self, _name):
            return False

        def lastError(self):
            return types.SimpleNamespace(message=lambda: "name already owned")

    monkeypatch.setattr(mpris.QDBusConnection, "sessionBus", lambda: FakeBus())

    controller = mpris.MPRISController(playback_service=types.SimpleNamespace(playlist=[], current_track=None))

    with pytest.raises(RuntimeError, match="name already owned"):
        controller.start()
```

- [ ] **Step 2: Run the failing startup test**

Run: `uv run pytest tests/test_system/test_mpris.py::test_mpris_controller_start_raises_when_service_registration_fails -v`
Expected: FAIL until the new controller handles QtDBus registration paths.

- [ ] **Step 3: Implement clean startup/shutdown around QtDBus registration**

```python
def stop(self):
    if not self._started:
        return

    if self.bus is not None:
        self.bus.unregisterObject(MPRIS_PATH)
        self.bus.unregisterService(MPRIS_NAME)

    with self._service_lock:
        self.service = None
    self.bus = None
    self._started = False
```

- [ ] **Step 4: Run focused controller tests**

Run: `uv run pytest tests/test_system/test_mpris.py::test_mpris_controller_passes_ui_dispatcher_to_service tests/test_system/test_mpris.py::test_mpris_controller_start_raises_when_service_registration_fails tests/test_system/test_mpris.py::test_mpris_controller_track_change_uses_stable_service_reference -v`
Expected: PASS

### Task 4: Run the final focused regression suite

**Files:**
- Test: `tests/test_system/test_mpris.py`
- Test: `tests/test_app/test_plugin_bootstrap.py`
- Test: `tests/test_release_build.py`

- [ ] **Step 1: Run the full targeted regression set**

Run: `uv run pytest tests/test_system/test_mpris.py tests/test_app/test_plugin_bootstrap.py tests/test_release_build.py -v`
Expected: PASS with Linux MPRIS runtime now expressed in terms of `QtDBus`, no host Python D-Bus fallback, and AppImage D-Bus session setup still covered.

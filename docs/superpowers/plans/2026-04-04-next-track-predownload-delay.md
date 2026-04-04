# Next Track Predownload Delay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delay next-track predownload by 10 seconds after the current track starts, cancel stale pending work on track change, and prevent duplicate predownload attempts for the same immediate next track.

**Architecture:** Move the 10-second delay into a single scheduling path inside `PlaybackService`. `_on_track_changed()` and metadata-complete callbacks should schedule a single pending timer instead of directly starting preload. When the timer fires, re-validate that the stored `cloud_file_id` is still the immediate next track, then dispatch the existing QQ or cloud preload logic without an extra nested delay.

**Tech Stack:** Python, PySide6 `QTimer`, pytest, unittest.mock

---

### Task 1: Make the track-change regression tests fail against the new scheduling entry point

**Files:**
- Modify: `tests/test_services/test_queue_service.py`
- Test: `tests/test_services/test_queue_service.py`

- [ ] **Step 1: Change the existing `PlaybackService._on_track_changed()` tests to expect the delayed scheduler hook**

In `tests/test_services/test_queue_service.py`, update the two existing `PlaybackService._on_track_changed()` tests so they stub `_schedule_next_track_preload` instead of `_preload_next_cloud_track`:

```python
def test_playback_service_on_track_changed_schedules_queue_save():
    """Track switches should schedule queue persistence for restart restore."""
    service = PlaybackService.__new__(PlaybackService)
    service._engine = type("Engine", (), {})()
    service._engine.current_playlist_item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=42,
        local_path="/tmp/demo.mp3",
        title="demo",
    )
    service._engine.state = PlaybackState.PLAYING
    service._event_bus = type("Bus", (), {"emit_track_change": lambda *args, **kwargs: None})()
    service._history_repo = type("History", (), {"add": lambda *args, **kwargs: None})()
    service._track_repo = None
    service._schedule_next_track_preload_called = 0
    service._schedule_save_queue_called = 0

    def _schedule_preload():
        service._schedule_next_track_preload_called += 1

    def _schedule_save():
        service._schedule_save_queue_called += 1

    service._schedule_next_track_preload = _schedule_preload
    service._schedule_save_queue = _schedule_save

    PlaybackService._on_track_changed(service, {"id": 42})

    assert service._schedule_next_track_preload_called == 1
    assert service._schedule_save_queue_called == 1
```

Apply the same stub replacement in `test_playback_service_on_track_changed_skips_save_when_stopped`, but keep the final assertion that queue save count stays `0`.

- [ ] **Step 2: Run the targeted regression tests and verify the scheduler assertion fails**

Run: `uv run pytest tests/test_services/test_queue_service.py -v -k "on_track_changed"`

Expected: FAIL because `_on_track_changed()` still calls `_preload_next_cloud_track()` instead of `_schedule_next_track_preload()`.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_services/test_queue_service.py
git commit -m "test: expect delayed preload scheduling on track change"
```

---

### Task 2: Add focused delay, cancellation, and deduplication tests for pending next-track preload

**Files:**
- Create: `tests/test_services/test_playback_service_preload_delay.py`
- Test: `tests/test_services/test_playback_service_preload_delay.py`

- [ ] **Step 1: Write the new failing scheduler tests**

Create `tests/test_services/test_playback_service_preload_delay.py` with:

```python
from domain.playback import PlayMode, PlaybackState
from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from services.playback import playback_service as playback_service_module
from services.playback.playback_service import PlaybackService


class FakeSignal:
    def __init__(self):
        self._callback = None

    def connect(self, callback):
        self._callback = callback

    def emit(self):
        if self._callback:
            self._callback()


class FakeTimer:
    def __init__(self):
        self.timeout = FakeSignal()
        self.started_intervals = []
        self.stop_calls = 0
        self.single_shot = None
        self.active = False

    def setSingleShot(self, value):
        self.single_shot = value

    def start(self, interval_ms):
        self.started_intervals.append(interval_ms)
        self.active = True

    def stop(self):
        self.stop_calls += 1
        self.active = False

    def isActive(self):
        return self.active

    def fire(self):
        self.active = False
        self.timeout.emit()


class FakeEngine:
    def __init__(self):
        self.state = PlaybackState.PLAYING
        self.play_mode = PlayMode.SEQUENTIAL
        self._next_item = None

    def get_next_item(self):
        return self._next_item


def make_service(monkeypatch):
    timer_factory_calls = []

    def build_timer():
        timer = FakeTimer()
        timer_factory_calls.append(timer)
        return timer

    monkeypatch.setattr(playback_service_module, "QTimer", build_timer)

    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine()
    service._pending_next_preload_cloud_file_id = None
    service._next_preload_timer = None
    service._preload_online_track_calls = []
    service._preload_cloud_track_calls = []
    service._preload_online_track = (
        lambda item: service._preload_online_track_calls.append(item.cloud_file_id)
    )
    service._preload_cloud_track = (
        lambda item: service._preload_cloud_track_calls.append(item.cloud_file_id)
    )
    return service, timer_factory_calls


def test_schedule_next_track_preload_starts_single_shot_10_second_timer(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = PlaylistItem(
        source=TrackSource.QQ,
        cloud_file_id="qq-next",
        title="Next Song",
        needs_download=True,
    )

    PlaybackService._schedule_next_track_preload(service)

    assert service._pending_next_preload_cloud_file_id == "qq-next"
    assert len(timers) == 1
    assert timers[0].single_shot is True
    assert timers[0].started_intervals == [10000]


def test_schedule_next_track_preload_reuses_existing_pending_target(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = PlaylistItem(
        source=TrackSource.QQ,
        cloud_file_id="qq-next",
        title="Next Song",
        needs_download=True,
    )

    PlaybackService._schedule_next_track_preload(service)
    PlaybackService._schedule_next_track_preload(service)

    assert len(timers) == 1
    assert timers[0].stop_calls == 0
    assert timers[0].started_intervals == [10000]


def test_schedule_next_track_preload_replaces_previous_target(monkeypatch):
    service, timers = make_service(monkeypatch)
    first = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="cloud-a",
        title="A",
        needs_download=True,
    )
    second = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="cloud-b",
        title="B",
        needs_download=True,
    )

    service._engine._next_item = first
    PlaybackService._schedule_next_track_preload(service)

    service._engine._next_item = second
    PlaybackService._schedule_next_track_preload(service)

    assert service._pending_next_preload_cloud_file_id == "cloud-b"
    assert timers[0].stop_calls == 1
    assert timers[0].started_intervals == [10000, 10000]


def test_next_track_preload_timeout_skips_when_target_is_no_longer_next(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="cloud-a",
        title="A",
        needs_download=True,
    )
    PlaybackService._schedule_next_track_preload(service)

    service._engine._next_item = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="cloud-b",
        title="B",
        needs_download=True,
    )
    timers[0].fire()

    assert service._preload_cloud_track_calls == []
    assert service._preload_online_track_calls == []


def test_next_track_preload_timeout_dispatches_current_target_once(monkeypatch):
    service, timers = make_service(monkeypatch)
    service._engine._next_item = PlaylistItem(
        source=TrackSource.QQ,
        cloud_file_id="qq-next",
        title="Next Song",
        needs_download=True,
    )
    PlaybackService._schedule_next_track_preload(service)

    timers[0].fire()

    assert service._pending_next_preload_cloud_file_id is None
    assert service._preload_online_track_calls == ["qq-next"]
    assert service._preload_cloud_track_calls == []
```

- [ ] **Step 2: Run the new scheduler test file and verify it fails for missing methods/fields**

Run: `uv run pytest tests/test_services/test_playback_service_preload_delay.py -v`

Expected: FAIL with `AttributeError` for `_schedule_next_track_preload` and missing pending-timer state.

- [ ] **Step 3: Commit the new failing scheduler coverage**

```bash
git add tests/test_services/test_playback_service_preload_delay.py
git commit -m "test: cover delayed next-track preload scheduling"
```

---

### Task 3: Implement single-timer next-track preload scheduling in `PlaybackService`

**Files:**
- Modify: `services/playback/playback_service.py`
- Modify: `tests/test_services/test_queue_service.py`
- Create: `tests/test_services/test_playback_service_preload_delay.py`
- Test: `tests/test_services/test_queue_service.py`
- Test: `tests/test_services/test_playback_service_preload_delay.py`
- Test: `tests/test_playback_service_cloud_next.py`

- [ ] **Step 1: Add pending-preload timer state in `PlaybackService.__init__`**

In `services/playback/playback_service.py`, after the existing preload scheduling fields, add:

```python
        # Delayed next-track preload scheduling
        self._next_preload_timer = None
        self._pending_next_preload_cloud_file_id: Optional[str] = None
```

- [ ] **Step 2: Add helper methods for candidate selection, timer creation, cancellation, scheduling, and timeout dispatch**

In `services/playback/playback_service.py`, near `_preload_next_cloud_track()`, add:

```python
    def _get_next_preload_candidate(self) -> Optional[PlaylistItem]:
        """Return the immediate next item that is still eligible for preload."""
        if self._engine.state == PlaybackState.STOPPED:
            return None

        if self._engine.play_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            return None

        next_item = self._engine.get_next_item()
        if not next_item:
            return None

        if not next_item.needs_download:
            return None

        if next_item.local_path and Path(next_item.local_path).exists():
            return None

        return next_item

    def _ensure_next_preload_timer(self):
        if self._next_preload_timer is None:
            self._next_preload_timer = QTimer()
            self._next_preload_timer.setSingleShot(True)
            self._next_preload_timer.timeout.connect(self._on_next_track_preload_timeout)

    def _cancel_pending_next_track_preload(self):
        if getattr(self, "_next_preload_timer", None) is not None:
            self._next_preload_timer.stop()
        self._pending_next_preload_cloud_file_id = None

    def _dispatch_preload_for_item(self, item: PlaylistItem):
        if item.source == TrackSource.QQ:
            self._preload_online_track(item)
        elif item.is_cloud:
            self._preload_cloud_track(item)

    def _schedule_next_track_preload(self):
        next_item = self._get_next_preload_candidate()
        if not next_item or not next_item.cloud_file_id:
            self._cancel_pending_next_track_preload()
            return

        timer = getattr(self, "_next_preload_timer", None)
        pending_id = getattr(self, "_pending_next_preload_cloud_file_id", None)
        if timer is not None and timer.isActive() and pending_id == next_item.cloud_file_id:
            return

        self._cancel_pending_next_track_preload()
        self._ensure_next_preload_timer()
        self._pending_next_preload_cloud_file_id = next_item.cloud_file_id
        logger.info(
            f"[PlaybackService] Scheduling next-track preload in 10 seconds: {next_item.cloud_file_id}"
        )
        self._next_preload_timer.start(10000)

    def _on_next_track_preload_timeout(self):
        target_id = getattr(self, "_pending_next_preload_cloud_file_id", None)
        self._pending_next_preload_cloud_file_id = None
        if not target_id:
            return

        next_item = self._get_next_preload_candidate()
        if not next_item or next_item.cloud_file_id != target_id:
            return

        self._dispatch_preload_for_item(next_item)
```

- [ ] **Step 3: Route all current-track transitions through the scheduler and stop the timer during shutdown**

In `services/playback/playback_service.py`, make these call-site changes:

1. In `_on_track_changed()` replace:
```python
            self._preload_next_cloud_track()
```
with:
```python
            self._schedule_next_track_preload()
```

2. In `_on_metadata_processed()` replace:
```python
        self._preload_next_cloud_track()
```
with:
```python
        self._schedule_next_track_preload()
```

3. In `begin_shutdown()` add:
```python
        self._cancel_pending_next_track_preload()
```

4. Refactor `_preload_next_cloud_track()` to reuse the new helper:
```python
    def _preload_next_cloud_track(self):
        """Preload the next track in the queue (cloud or online)."""
        next_item = self._get_next_preload_candidate()
        if not next_item:
            return

        self._dispatch_preload_for_item(next_item)
```

- [ ] **Step 4: Remove the nested 10-second delay from `_preload_cloud_track()` so the outer scheduler is the only delay**

In `services/playback/playback_service.py`, replace the trailing `start_preload()` / `QTimer.singleShot(10000, start_preload)` block inside `_preload_cloud_track()` with immediate handoff:

```python
        logger.info(
            f"[PlaybackService] Starting preload for cloud track (attempt {attempts + 1}): {item.title}"
        )

        with self._preload_scheduled_lock:
            self._scheduled_preloads.discard(item.cloud_file_id)

        service.set_download_dir(self._config.get_cloud_download_dir())
        service.download_file(cloud_file, account)
```

Keep the earlier guards for max attempts, concurrent limit, `_scheduled_preloads`, and `service.is_downloading(item.cloud_file_id)` unchanged so cloud preloads still deduplicate correctly.

- [ ] **Step 5: Run the focused tests and verify they pass**

Run: `uv run pytest tests/test_services/test_queue_service.py tests/test_services/test_playback_service_preload_delay.py tests/test_playback_service_cloud_next.py -v`

Expected: PASS for all targeted regressions.

- [ ] **Step 6: Run a broader playback regression slice**

Run: `uv run pytest tests/test_services/test_playback_service_online_failures.py tests/test_services/test_queue_service.py tests/test_services/test_playback_service_preload_delay.py tests/test_playback_service_cloud_next.py -v`

Expected: PASS with no new preload-related failures.

- [ ] **Step 7: Commit the implementation**

```bash
git add services/playback/playback_service.py tests/test_services/test_queue_service.py tests/test_services/test_playback_service_preload_delay.py
git commit -m "修复下一首预下载延迟"
```

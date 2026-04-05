# Cover Thread Lifecycle Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make cover-loading threads in `MiniPlayer` and `NowPlayingWindow` follow the same stale-result invalidation and shutdown cleanup rules.

**Architecture:** Keep `threading.Thread` for short-lived cover work, but gate every UI update behind a request version/token. Both windows should explicitly invalidate pending cover results during close and clear their thread reference without blocking the UI thread.

**Tech Stack:** Python, PySide6 signals, pytest, unittest.mock, threading

---

### Task 1: Add failing MiniPlayer tests for stale-result filtering and close cleanup

**Files:**
- Modify: `tests/test_ui/test_mini_player_thread_cleanup.py`
- Test: `tests/test_ui/test_mini_player_thread_cleanup.py`

- [ ] **Step 1: Add a failing stale-result test for the mini player**

```python
def test_on_cover_loaded_ignores_stale_result():
    fake = SimpleNamespace(
        _cover_load_version=2,
        _show_cover=MagicMock(),
    )

    MiniPlayer._on_cover_loaded(fake, "/tmp/stale.png", 1)

    fake._show_cover.assert_not_called()


def test_on_cover_loaded_applies_current_result():
    fake = SimpleNamespace(
        _cover_load_version=3,
        _show_cover=MagicMock(),
    )

    MiniPlayer._on_cover_loaded(fake, "/tmp/current.png", 3)

    fake._show_cover.assert_called_once_with("/tmp/current.png")
```

- [ ] **Step 2: Add a failing close-event cleanup test for the mini player**

```python
def test_invalidate_cover_load_bumps_version_and_clears_thread():
    fake = SimpleNamespace(
        _cover_load_version=5,
        _cover_thread=object(),
    )

    MiniPlayer._invalidate_cover_load(fake)

    assert fake._cover_load_version == 6
    assert fake._cover_thread is None


def test_close_event_calls_cover_invalidation_and_lyrics_cleanup():
    event = MagicMock()
    fake = SimpleNamespace(
        _invalidate_cover_load=MagicMock(),
        _stop_lyrics_thread=MagicMock(),
        closed=SimpleNamespace(emit=MagicMock()),
    )

    MiniPlayer.closeEvent(fake, event)

    fake._invalidate_cover_load.assert_called_once()
    fake._stop_lyrics_thread.assert_called_once_with(wait_ms=1000, cleanup_signals=True)
    event.accept.assert_called_once()
```

- [ ] **Step 3: Run the mini-player cleanup tests and confirm they fail**

Run: `uv run pytest tests/test_ui/test_mini_player_thread_cleanup.py -v`

Expected: FAIL because `MiniPlayer` does not yet expose `_on_cover_loaded` with version gating and does not invalidate `_cover_load_version` on close.

### Task 2: Implement MiniPlayer cover-load versioning

**Files:**
- Modify: `ui/windows/mini_player.py`
- Modify: `tests/test_ui/test_mini_player_thread_cleanup.py`
- Test: `tests/test_ui/test_mini_player_thread_cleanup.py`

- [ ] **Step 1: Promote the mini-player cover signal to carry a version**

```python
class MiniPlayer(QWidget):
    _cover_loaded = Signal(str, int)

    def __init__(self, player: PlaybackService, parent=None):
        super().__init__(parent)
        self._cover_load_version = 0
        self._cover_thread: Optional[threading.Thread] = None
```

- [ ] **Step 2: Gate cover application behind the active version**

```python
    def _load_cover_async(self, track_dict: dict):
        self._cover_load_version += 1
        version = self._cover_load_version

        def worker():
            cover_path = load_cover()
            self._cover_loaded.emit(cover_path or "", version)

        thread = threading.Thread(target=worker, daemon=True)
        self._cover_thread = thread
        thread.start()

    def _on_cover_loaded(self, cover_path: str, version: int):
        if version != self._cover_load_version:
            return
        self._show_cover(cover_path)
```

- [ ] **Step 3: Add a small invalidation helper and use it in `closeEvent`**

```python
    def _invalidate_cover_load(self):
        self._cover_load_version += 1
        self._cover_thread = None

    def closeEvent(self, event):
        self._invalidate_cover_load()
        self._stop_lyrics_thread(wait_ms=1000, cleanup_signals=True)
        self.closed.emit()
        event.accept()
```

- [ ] **Step 4: Re-run the mini-player tests**

Run: `uv run pytest tests/test_ui/test_mini_player_thread_cleanup.py -v`

Expected: PASS

### Task 3: Add and satisfy close-time invalidation tests for NowPlayingWindow

**Files:**
- Modify: `tests/test_ui/test_now_playing_window_thread_cleanup.py`
- Modify: `ui/windows/now_playing_window.py`
- Test: `tests/test_ui/test_now_playing_window_thread_cleanup.py`

- [ ] **Step 1: Add a failing close-event test for the now playing window**

```python
def test_invalidate_cover_load_bumps_version_and_clears_thread():
    fake = SimpleNamespace(
        _cover_load_version=8,
        _cover_thread=object(),
    )

    NowPlayingWindow._invalidate_cover_load(fake)

    assert fake._cover_load_version == 9
    assert fake._cover_thread is None


def test_close_event_calls_cover_invalidation_and_cleanup():
    event = MagicMock()
    fake = SimpleNamespace(
        _invalidate_cover_load=MagicMock(),
        _save_window_settings=MagicMock(),
        _stop_lyrics_thread=MagicMock(),
        closed=SimpleNamespace(emit=MagicMock()),
    )

    NowPlayingWindow.closeEvent(fake, event)

    fake._invalidate_cover_load.assert_called_once()
    fake._save_window_settings.assert_called_once()
    fake._stop_lyrics_thread.assert_called_once_with(wait_ms=800, cleanup_signals=True)
    event.accept.assert_called_once()
```

- [ ] **Step 2: Add the same invalidation helper pattern to the window**

```python
    def _invalidate_cover_load(self):
        self._cover_load_version += 1
        self._cover_thread = None

    def closeEvent(self, event):
        self._save_window_settings()
        self._invalidate_cover_load()
        self._stop_lyrics_thread(wait_ms=800, cleanup_signals=True)
        self.closed.emit()
        event.accept()
```

- [ ] **Step 3: Keep the existing current-result guard and clear the thread on completion**

```python
    def _on_cover_loaded(self, cover_path: str, version: int):
        if version != self._cover_load_version:
            return
        self._cover_thread = None
        self._current_cover_path = cover_path
```

- [ ] **Step 4: Run the now-playing cleanup tests**

Run: `uv run pytest tests/test_ui/test_now_playing_window_thread_cleanup.py tests/test_ui/test_now_playing_window_seek_sync.py -v`

Expected: PASS

### Task 4: Final verification and commit

**Files:**
- Modify: `ui/windows/mini_player.py`
- Modify: `ui/windows/now_playing_window.py`
- Modify: `tests/test_ui/test_mini_player_thread_cleanup.py`
- Modify: `tests/test_ui/test_now_playing_window_thread_cleanup.py`

- [ ] **Step 1: Run the combined thread-lifecycle verification set**

Run: `uv run pytest tests/test_ui/test_mini_player_thread_cleanup.py tests/test_ui/test_now_playing_window_thread_cleanup.py tests/test_ui/test_now_playing_window_seek_sync.py -v`

Expected: PASS

- [ ] **Step 2: Run Ruff on the touched files**

Run: `uv run ruff check ui/windows/mini_player.py ui/windows/now_playing_window.py tests/test_ui/test_mini_player_thread_cleanup.py tests/test_ui/test_now_playing_window_thread_cleanup.py`

Expected: PASS

- [ ] **Step 3: Commit only the lifecycle cleanup**

```bash
git add ui/windows/mini_player.py ui/windows/now_playing_window.py tests/test_ui/test_mini_player_thread_cleanup.py tests/test_ui/test_now_playing_window_thread_cleanup.py
git commit -m "统一封面线程清理"
```

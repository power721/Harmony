uv add pynput

---

分析结果：网络歌曲播放 UI 卡顿原因

根本原因：封面下载在 UI 线程上同步执行。

阻塞调用链

当切歌时，信号在 UI 线程触发，调用链如下：

MainWindow._on_track_changed()          [UI 线程]
  -> _extract_cover_color()             [UI 线程]
    -> PlaybackService.get_track_cover() [UI 线程]
      -> CoverService.get_cover()        [UI 线程]
        -> CoverService._fetch_online_cover()  [UI 线程 - 阻塞!]

具体阻塞点

1. (主因) 封面在线获取阻塞 UI 线程 — main_window.py:1213

_extract_cover_color() 在 UI 线程直接调用 get_track_cover()，最终进入 CoverService._fetch_online_cover()（cover_service.py:286），其中有两处阻塞：

  • 第 312 行：as_completed(futures, timeout=15) — 等待多个在线源搜索，最多阻塞 15 秒
  • 第 348 行：http_client.get_content(result.cover_url, timeout=5) — 同步下载封面图片，最多阻塞 5 秒

UI 线程最多可能冻结 20 秒。

2. (次因) 歌词下载 — 已经是后台线程，但不是直接原因

歌词加载通过 LyricsLoader（QThread）在后台执行，不会直接阻塞 UI。但 LyricsService._get_online_lyrics() 内部的 as_completed(futures, timeout=15) 同样有 15 秒超时，会导致歌词显示延迟。

为什么只在网络歌曲时明显

本地歌曲通常有内嵌封面（embedded cover），在 get_cover() 的第 112 行就命中返回了，不会走到 _fetch_online_cover()。而网络歌曲没有内嵌封面也没有缓存，必然触发在线搜索。

修复方向

将 _extract_cover_color() 中的封面获取移到后台线程执行，获取完成后通过信号回调更新 UI。目前颜色提取（ColorWorker）已经是在 QThreadPool 中异步执行的，只需要把前面的 get_track_cover() 也包进去
即可。

---

I found the root cause:

  • In main.py (line 180-187), the stylesheet is set with font-family: "Noto Color Emoji", "Inter", "Noto Sans SC" for QWidget and QMenu.
  • But then theme.apply_global_stylesheet() (line 195) calls app.setStyleSheet(themed_qss) which completely overwrites the previous stylesheet.
  • styles.qss has QMenu styling but does NOT include font-family, so the emoji font setting is lost.

The button (QPushButton) inherits from the application font set via setFont(), but QMenu on Windows uses native rendering and falls back to the system emoji font when no explicit font-family 
is in the active stylesheet.

The fix: add font-family to styles.qss so it survives the theme stylesheet override.

⏺ Edit ./ui/styles.qss
      3     * Dark theme inspired by Spotify
      4     */
      5    
      6 +  /* Global Font */                                                                                                                                                                   
      7 +  QWidget {                                                                                                                                                                           
      8 +      font-family: "Noto Color Emoji", "Inter", "Noto Sans SC";                                                                                                                       
      9 +  }                                                                                                                                                                                   
     10 +                                                                                                                                                                                      
     11    /* Main Window */
     12    QMainWindow {
     13        background-color: %background%;

Now add font-family to the QMenu section:

⏺ Edit ./ui/styles.qss
    219        color: %text%;
    220        border: 1px solid %border%;
    221        padding: 4px;
    222 +      font-family: "Noto Color Emoji", "Inter", "Noto Sans SC";                                                                                                                       
    223    }
    224    
    225    QMenu::item {

Now remove the redundant initial stylesheet in main.py since it gets overwritten anyway:

⏺ Read lines 168-192 in ./main.py
    Read 25 lines

⏺ Edit ./main.py
    177            "Noto Color Emoji"
    178        ])
    179        qt_app.setFont(font)
    180 -      qt_app.setStyleSheet("""                                                                                                                                                        
    181 -          QWidget {                                                                                                                                                                   
    182 -              font-family: "Noto Color Emoji", "Inter", "Noto Sans SC";                                                                                                               
    183 -          }                                                                                                                                                                           
    184 -          QMenu {                                                                                                                                                                     
    185 -              font-family: "Noto Color Emoji", "Inter", "Noto Sans SC";                                                                                                               
    186 -          }                                                                                                                                                                           
    187 -      """)                                                                                                                                                                            
    180    
    181        # Create application with dependency injection
    182        app = Application.create(qt_app)

---
# Bug Report - Harmony Music Player

**Date:** 2026-03-31
**Scope:** Full codebase review
**Total Bugs Found:** 20 (verified against source code)

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|------------|
| CRITICAL | 3 | `addEntries` API misuse, invalid QPainter, MPRIS never starts |
| HIGH | 5 | Cache key error, race condition, leftover file, duplicate call, signal race |
| MEDIUM | 9 | Wrong log message, architecture violation, JSON error handling, memory leak, thread cleanup, etc. |
| LOW | 3 | Hardcoded constants, wrong docstring, redundant import |

---

## CRITICAL (Will crash at runtime)

### Bug 1: `QComboBox.addEntries()` does not exist

**File:** `ui/widgets/equalizer_widget.py:133`

```python
self._preset_combo.addEntries([p.name for p in self.PRESETS])
```

**Problem:** `QComboBox` does not have an `addEntries()` method. This will raise `AttributeError` at runtime when the equalizer widget is initialized, crashing the application.

**Fix:**

```python
self._preset_combo.addItems([p.name for p in self.PRESETS])
```

---

### Bug 2: Invalid `QPainter()` object created without device

**File:** `ui/widgets/artist_card.py:200`

```python
# Draw circular clip
path = QPainter()  # BUG: should be QPainterPath(), and is never used
painter.setClipRect(0, 0, size, size)
```

**Problem:** Creates a `QPainter()` without a paint device, assigned to variable `path` but never used. This will produce Qt warnings/errors at runtime. The variable name suggests it should be a `QPainterPath`, not a `QPainter`. Line 201's `setClipRect` is also redundant since `setClipPath` is called on line 207.

**Fix:** Remove line 200 and line 201 entirely (the `setClipPath` on line 207 already does the clipping correctly).

---

### Bug 3: MPRIS controller never starts on Linux

**File:** `app/bootstrap.py:437`

```python
def start_mpris(self, main_window=None):
    import sys
    if sys.platform == "linux" and self._mpris_controller is not None:  # Always None!
        self._mpris_controller._main_window = main_window
        self._mpris_controller.start()
```

**Problem:** `self._mpris_controller` is only initialized when the `mpris_controller` **property** (line 417) is accessed. But `start_mpris` accesses the private field `self._mpris_controller` directly, which is always `None` on first call. The MPRIS D-Bus service will never start on Linux, breaking media key support and D-Bus integration.

**Fix:**

```python
def start_mpris(self, main_window=None):
    import sys
    if sys.platform == "linux":
        controller = self.mpris_controller  # Access property to trigger lazy init
        if controller is not None:
            controller._main_window = main_window
            controller.start()
```

---

## HIGH (Logic errors / Data corruption)

### Bug 4: `CoverPixmapCache.make_key()` does not handle None arguments

**File:** `infrastructure/cache/pixmap_cache.py:23-26`

```python
@classmethod
def make_key(cls, artist: str, album: str) -> str:
    raw = f"{artist}:{album}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()
```

**Problem:** When `artist` or `album` is `None`, `f"{None}:{album}"` produces the string `"none:xxx"` as a cache key, causing cache collisions and incorrect cover art display. The sibling method `make_key_from_path()` in the same file already handles `None` correctly.

**Fix:**

```python
@classmethod
def make_key(cls, artist: str, album: str) -> str:
    artist = artist or ""
    album = album or ""
    raw = f"{artist}:{album}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()
```

---

### Bug 5: Race condition in `DBWriteWorker.submit()` thread restart

**File:** `infrastructure/database/db_write_worker.py:141-143`

```python
def submit(self, func: Callable, *args, **kwargs) -> Future:
    future = Future()
    # Ensure worker thread is running
    if not self._thread or not self._thread.is_alive():
        logger.warning("[DBWriteWorker] Thread not alive, restarting...")
        self._start()
    self._queue.put((func, args, kwargs, future))
    return future
```

**Problem:** The check-then-act pattern is not atomic. Multiple threads could simultaneously see the thread as not alive and both call `_start()`, creating multiple worker threads. This violates the single-writer guarantee that the `DBWriteWorker` is designed to enforce.

**Fix:**

```python
def __init__(self, db_path: str):
    # ... existing code ...
    self._start_lock = threading.Lock()

def submit(self, func: Callable, *args, **kwargs) -> Future:
    future = Future()
    with self._start_lock:
        if not self._thread or not self._thread.is_alive():
            logger.warning("[DBWriteWorker] Thread not alive, restarting...")
            self._start()
    self._queue.put((func, args, kwargs, future))
    return future
```

---

### Bug 6: Cancelled download leaves incomplete file on disk

**File:** `services/cloud/download_service.py:153-156`

```python
with open(dest_path, 'wb') as f:
    for chunk in response.iter_content(chunk_size=8192):
        if self._cancelled:
            return False  # Incomplete file left on disk!
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)
```

**Problem:** When a download is cancelled, the function returns `False` without deleting the partially written file. On the next attempt, the file's existence may be mistakenly interpreted as a completed download, causing playback of a corrupt/truncated file.

**Fix:**

```python
with open(dest_path, 'wb') as f:
    for chunk in response.iter_content(chunk_size=8192):
        if self._cancelled:
            f.close()
            if Path(dest_path).exists():
                Path(dest_path).unlink()
            return False
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)
```

---

### Bug 7: Duplicate call to `_update_favorite_button_style`

**File:** `ui/widgets/player_controls.py:1020-1021`

```python
# Reset favorite button style
self._update_favorite_button_style(False)
self._update_favorite_button_style(False)  # Duplicate call
```

**Problem:** Copy-paste error. The same method is called twice consecutively with identical arguments.

**Fix:** Remove line 1021.

---

### Bug 8: Sleep timer signal race condition in track mode

**File:** `services/playback/sleep_timer_service.py:131-141`

```python
def _on_track_finished(self):
    self._remaining -= 1                    # Decrement first
    self.remaining_changed.emit(self._remaining)
    if self._remaining <= 0:
        try:
            self._event_bus.track_finished.disconnect(self._on_track_finished)  # Disconnect after
        except RuntimeError:
            pass
```

**Problem:** The signal is disconnected AFTER the decrement. If multiple `track_finished` events are queued in the Qt event loop, this handler can be called multiple times before the disconnect takes effect, causing `_remaining` to go negative. Should disconnect first, then decrement.

**Fix:**

```python
def _on_track_finished(self):
    # Disconnect immediately to prevent re-entry
    try:
        self._event_bus.track_finished.disconnect(self._on_track_finished)
    except RuntimeError:
        return  # Already disconnected, skip

    self._remaining -= 1
    self.remaining_changed.emit(self._remaining)

    if self._remaining <= 0:
        if not self._config.fade_out:
            self._playback_service._engine.set_prevent_auto_next(True)
        self._trigger_action()
    else:
        # Re-connect for next track
        self._event_bus.track_finished.connect(self._on_track_finished)
```

---

## MEDIUM (Defensive programming / Architecture issues)

### Bug 9: Wrong error log message in QuarkDriveService

**File:** `services/cloud/quark_service.py:427`

```python
except Exception as e:
    logger.error(f"Quark cookie validation error: {e}", exc_info=True)
```

**Problem:** This code is in the `download_file()` method, but the log message says "cookie validation error". This will mislead debugging efforts.

**Fix:**

```python
logger.error(f"Quark download file error: {e}", exc_info=True)
```

---

### Bug 10: Service layer directly accesses DatabaseManager private method

**File:** `services/library/file_organization_service.py:200`

```python
conn = self._db._get_connection()
cursor = conn.cursor()
cursor.execute("SELECT account_id FROM cloud_files WHERE file_id = ?", (cloud_file_id,))
```

**Problem:** The service layer directly calls `self._db._get_connection()`, a private method of the infrastructure layer. This violates the project's strict access control rules (services should only access repositories, not infrastructure internals). It also introduces a thread-safety risk since `_get_connection()` returns thread-local connections.

**Fix:** Add a proper method in `CloudRepository` to look up `account_id` by `file_id`, and call that from the service.

---

### Bug 11: Missing JSON parse error handling in QuarkService / BaiduService

**Files:**
- `services/cloud/quark_service.py` (lines 87, 120, 138, 194, 264)
- `services/cloud/baidu_service.py` (lines 91-93, 130-131, 259-261, 382-384)

```python
data = response.json()  # No try-catch for JSONDecodeError
```

**Problem:** Multiple `response.json()` calls lack `try-except json.JSONDecodeError` handling. When cloud service APIs return non-JSON responses (e.g., HTML error pages, empty responses), the application will crash with an unhandled exception.

**Fix:** Wrap all `response.json()` calls:

```python
try:
    data = response.json()
except (json.JSONDecodeError, ValueError) as e:
    logger.error(f"Invalid JSON response: {e}")
    return None
```

---

### Bug 12: `CloudDownloadService` starts worker outside lock

**File:** `services/cloud/download_service.py:293-295`

```python
with self._downloads_lock:
    if file_id in self._active_downloads:
        return False
    self._active_downloads[file_id] = worker
self.download_started.emit(file_id)  # Outside lock
worker.start()                        # Outside lock
```

**Problem:** `worker.start()` is called outside the lock. Between releasing the lock and starting the worker, another thread could observe the worker in `_active_downloads` but it would not yet be running.

**Fix:** Move `worker.start()` inside the lock:

```python
with self._downloads_lock:
    if file_id in self._active_downloads:
        return False
    self._active_downloads[file_id] = worker
    worker.start()
self.download_started.emit(file_id)
```

---

### Bug 13: `MessageDialog._show()` does not call `deleteLater()`

**File:** `ui/dialogs/message_dialog.py:216`

```python
@staticmethod
def _show(parent, dialog_type, title, text, buttons, default_button):
    dialog = MessageDialog(parent, dialog_type)
    # ... setup ...
    dialog.exec()
    return dialog._result  # dialog never cleaned up
```

**Problem:** The dialog object is created but never cleaned up after `exec()` returns. This is a memory leak that accumulates with each dialog shown.

**Fix:**

```python
dialog.exec()
result = dialog._result
dialog.deleteLater()
return result
```

---

### Bug 14: Multiple dialogs have QThread lifecycle issues

**Files:**
- `ui/dialogs/organize_files_dialog.py:377-384` - Thread not connected to `finished.connect(deleteLater)`
- `ui/dialogs/base_rename_dialog.py:268` - Same issue
- `ui/dialogs/base_cover_download_dialog.py:598-600` - Calls `terminate()` directly instead of `requestInterruption()` + `wait()`

**Problem:**
1. Threads started without `finished.connect(thread.deleteLater)` will leak if the dialog is closed before the thread completes.
2. `base_cover_download_dialog.py` calls `terminate()` directly, which is dangerous and can cause crashes or data corruption.

**Fix:**

```python
# For all thread starts, add:
self._worker.finished.connect(self._worker.deleteLater)

# For base_cover_download_dialog.py, replace terminate():
if self._download_thread and self._download_thread.isRunning():
    self._download_thread.requestInterruption()
    if not self._download_thread.wait(1000):
        self._download_thread.terminate()
        self._download_thread.wait()
```

---

### Bug 15: `MiniPlayer._on_seek_end` does not validate `_current_duration > 0`

**File:** `ui/windows/mini_player.py:398-404`

```python
def _on_seek_end(self):
    if hasattr(self, "_current_duration"):
        position_ms = int(
            (self._progress_slider.value() / 1000) * self._current_duration * 1000
        )
        self._player.engine.seek(position_ms)
    self._is_seeking = False
```

**Problem:** Only checks if the attribute exists, but not if `_current_duration > 0`. When duration is 0 (e.g., before metadata is loaded), the seek calculation produces meaningless results.

**Fix:**

```python
if hasattr(self, "_current_duration") and self._current_duration > 0:
```

---

### Bug 16: `PlaylistItem.from_dict` has inconsistent `needs_metadata` default

**File:** `domain/playlist_item.py:174-175`

```python
needs_metadata=data.get("needs_metadata", True),
```

**Problem:** `from_dict()` defaults `needs_metadata` to `True` for all sources. But `from_track()` sets it to `False` for local tracks (`TrackSource.LOCAL`). When a local track is restored from a dictionary (e.g., from saved queue state), it will incorrectly be marked as needing metadata extraction.

**Fix:**

```python
# Determine needs_metadata based on source if not provided
if "needs_metadata" in data:
    needs_metadata = data["needs_metadata"]
else:
    needs_metadata = source != TrackSource.LOCAL

# Then use needs_metadata in the constructor
```

---

### Bug 17: EventBus signals not disconnected on widget destruction

**Files:**
- `ui/views/history_list_view.py:434` - `bus.favorite_changed.connect(self._on_favorite_changed)`
- `ui/views/online_music_view.py:434` - Same pattern

**Problem:** These views connect to the global EventBus singleton's signals but never disconnect them when the widget is destroyed. After the widget is garbage collected, the signal may still fire and attempt to call a method on a deleted object, potentially causing a segfault.

**Fix:** Override `closeEvent` or use `destroyed` signal to disconnect:

```python
def closeEvent(self, event):
    try:
        EventBus.instance().favorite_changed.disconnect(self._on_favorite_changed)
    except RuntimeError:
        pass
    super().closeEvent(event)
```

---

## LOW (Code quality / Minor issues)

### Bug 18: `ThemeManager` uses hardcoded strings instead of `SettingKey` constants

**File:** `system/theme.py:188, 195, 236, 237, 250, 251`

```python
theme_name = self._config.get('ui.theme', 'dark')       # Should be SettingKey.UI_THEME
custom_theme_data = self._config.get('ui.theme.custom')  # Should be SettingKey.UI_THEME_CUSTOM
```

**Problem:** Uses hardcoded string keys like `'ui.theme'` instead of `SettingKey.UI_THEME` constants defined in `ConfigManager`. Violates DRY principle and is inconsistent with the pattern used elsewhere in the codebase.

**Fix:** Import and use `SettingKey` constants.

---

### Bug 19: `artist_repository.rebuild_with_albums()` docstring says returns Dict, actually returns int

**File:** `repositories/artist_repository.py`

```python
def rebuild_with_albums(self) -> int:
    """
    Returns:
        Dict with 'albums' and 'artists' counts   # <-- Wrong
    """
    return albums_count + artists_count  # Actually returns int
```

**Problem:** Docstring is misleading. The return type annotation `int` is correct, but the docstring claims it returns a `Dict`.

**Fix:** Update docstring to: `Returns: Total count of albums and artists created/updated`.

---

### Bug 20: Redundant `import os` inside function in `BaiduDriveService`

**File:** `services/cloud/baidu_service.py:580`

```python
import os  # os is already imported at the top of the file (line 4)
if os.path.exists(dest_path):
    return True
```

**Problem:** `os` is already imported at module level. The in-function import is redundant.

**Fix:** Remove the `import os` line inside the function.
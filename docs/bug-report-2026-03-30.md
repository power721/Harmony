# Harmony Bug Report

> Generated: 2026-03-30
> Scope: Full codebase audit of all Python source files

---

## Summary

| Severity | Count |
|----------|-------|
| Critical | 3     |
| High     | 6     |
| Medium   | 4     |
| Low      | 5     |
| **Total**| **18**|

---

## Critical Bugs

### BUG-01: Duplicate Widget Addition in ArtistView

- **File**: `ui/views/artist_view.py`
- **Lines**: 412-413
- **Category**: UI Layout Bug

`self._cover_label` is added to the layout twice:

```python
layout.addWidget(self._cover_label, 0, Qt.AlignVCenter)
layout.addWidget(self._cover_label, 0, Qt.AlignVCenter)  # DUPLICATE
```

In Qt, calling `addWidget` on the same widget twice causes the widget to be reparented/moved. The first `addWidget` call is effectively invalidated, and depending on the layout implementation this can produce visual glitches, warnings, or inconsistent layout behavior.

**Fix**: Remove the second `addWidget` call.

---

### BUG-02: Direct Database Write Bypassing Write Worker

- **File**: `services/playback/playback_service.py`
- **Lines**: 1528-1534
- **Category**: Architecture Violation / Race Condition

The code directly accesses `self._db._get_connection()` (a private method) and performs a raw SQL `UPDATE` + `commit()`, completely bypassing the `DBWriteWorker` that serializes all database writes:

```python
conn = self._db._get_connection()
cursor = conn.cursor()
cursor.execute(
    "UPDATE tracks SET cloud_file_id = ? WHERE id = ?",
    (file_id, existing_by_path.id)
)
conn.commit()
```

This violates the project's concurrency model: all writes must go through `DBWriteWorker` to prevent `"database is locked"` errors. Since `_get_connection()` returns a thread-local connection (different from the write worker's connection), this write can conflict with other concurrent writes.

**Fix**: Use `self._db.update_track(existing_by_path.id, cloud_file_id=file_id)` instead.

---

### BUG-03: DBWriteWorker Never Stopped on Application Exit

- **File**: `infrastructure/database/db_write_worker.py`
- **Lines**: 161-166 (stop method), `app/application.py` line 126-133 (quit method)
- **Category**: Resource Leak

`DBWriteWorker.stop()` exists but is never called anywhere in the codebase. On application quit, `Application.quit()` only stops the cache cleaner, then calls `qt_app.quit()`. The write worker thread continues running as a daemon thread, which means:

- Pending write operations in the queue may be discarded
- The database connection is not cleanly closed
- Data written just before exit may be lost

```python
# Application.quit() does NOT call db cleanup:
def quit(self):
    cache_cleaner = self._bootstrap.cache_cleaner_service
    if cache_cleaner:
        cache_cleaner.stop()
    self._qt_app.quit()
    # Missing: self._bootstrap.db._write_worker.stop()
```

**Fix**: Call `write_worker.stop()` and `write_worker.wait_idle()` in the application shutdown path.

---

## High Severity Bugs

### BUG-04: Type Comparison Error in Quark Cloud Service

- **File**: `services/cloud/quark_service.py`
- **Line**: 201
- **Category**: Type Error / Logic Error

`file_type_num` is obtained from `item.get('file_type', 0)` which returns an integer, but is compared to the string `'audio'`:

```python
file_type_num = item.get('file_type', 0)  # Returns int
# ...
elif category == 2 or file_type_num == 'audio':  # int == str → always False
    file_type = 'audio'
```

This condition branch `file_type_num == 'audio'` is **always False**, which means when `category != 2` but the file is actually audio, it will be misclassified as `'other'`.

**Fix**: Compare against the correct integer value (e.g., `file_type_num == 1`), or determine the actual numeric code Quark API uses for audio files.

---

### BUG-05: SHA1 Hash Index Out of Bounds

- **File**: `services/cloud/qqmusic/crypto.py`
- **Line**: 34
- **Category**: Off-by-one Error

SHA1 produces a 40-character hex string (indices 0-39). The `part1_indexes` array contains index `40`, which is out of bounds:

```python
part1_indexes = [23, 14, 6, 36, 16, 40, 7, 19]
part1 = ''.join(sha1_hash[i] if i < 40 else '' for i in part1_indexes)
```

The `if i < 40` guard prevents a crash, but silently produces a 7-character `part1` instead of the expected 8 characters. This generates invalid signatures that may cause API authentication failures.

**Fix**: Change index `40` to `39` (or the intended valid index).

---

### BUG-06: Sleep Timer Directly Modifies Private Engine State

- **File**: `services/playback/sleep_timer_service.py`
- **Lines**: 200-208
- **Category**: Encapsulation Violation

The sleep timer service reaches through two layers of encapsulation to directly modify the audio engine's private `_current_index` attribute:

```python
self._playback_service._engine._current_index = current_index + 1  # Line 204
self._playback_service._engine._current_index = -1                  # Line 208
```

This bypasses any validation, side effects, or signals that the engine's public API should trigger when the current index changes. Other components relying on index-change notifications will not be updated.

**Fix**: Use the playback service's public API to advance the queue (e.g., `self._playback_service.next()` or expose a `set_queue_index` method).

---

### BUG-07: Incorrect Type Annotation for `cloud_file_id`

- **File**: `infrastructure/database/sqlite_manager.py`
- **Lines**: 1361, 1369, 1390
- **Category**: Type Error

The `cloud_file_id` parameter is annotated as `int` but is always passed string values (`song_mid`, `file_id`, etc.):

```python
def update_track(
    self, track_id: int, title: str = None, artist: str = None, album: str = None,
    cloud_file_id: int = None  # Should be str
) -> bool:
```

All callers pass strings:
- `handlers.py:620`: `self._db.update_track(existing_by_path.id, cloud_file_id=file_id)` — `file_id` is str
- `handlers.py:883`: `self._db.update_track(existing_by_path.id, cloud_file_id=song_mid)` — `song_mid` is str

While Python doesn't enforce type annotations at runtime, this is misleading and will cause false errors in any type checker (mypy, pyright).

**Fix**: Change `cloud_file_id: int = None` to `cloud_file_id: str = None` in all three method signatures.

---

### BUG-08: IndexError on Empty Spotify Artists List

- **File**: `services/sources/cover_sources.py`
- **Lines**: 490, 519
- **Category**: Exception Handling

The code assumes the `artists` list always has at least one element:

```python
artist=album_info.get("artists", [{}])[0].get("name", "")
```

The fallback `[{}]` only applies when the `"artists"` key is **missing**. If the Spotify API returns `"artists": []` (empty list), `[0]` raises `IndexError`. This is inside a `try/except Exception` block so it won't crash the app, but it silently aborts the entire search for that API call.

**Fix**: Add a length check: `(album_info.get("artists") or [{}])[0].get("name", "")` or handle empty lists explicitly.

---

### BUG-09: Null Pointer Dereference in Organize Files Dialog

- **File**: `ui/dialogs/organize_files_dialog.py`
- **Lines**: 343-351
- **Category**: Null Pointer / Crash

The code calls `.setText()` on table items without null checks:

```python
new_path_item = self.preview_table.item(row, 2)
new_path_item.setText(preview['new_audio_path'])  # Crash if item is None

lyrics_item = self.preview_table.item(row, 3)
lyrics_item.setText(t("yes"))  # Crash if item is None
```

`QTableWidget.item()` returns `None` if no item exists at the specified row/column. If the preview list has more entries than table rows, or if items weren't properly initialized, this causes an `AttributeError: 'NoneType' object has no attribute 'setText'`.

**Fix**: Add null checks before calling `.setText()`.

---

## Medium Severity Bugs

### BUG-10: Bare `except` Clause Catches SystemExit/KeyboardInterrupt

- **File**: `system/config.py`
- **Line**: 801
- **Category**: Exception Handling

```python
try:
    import json
    history = json.loads(history)
except:  # Catches ALL exceptions, including SystemExit, KeyboardInterrupt
    history = []
```

A bare `except:` clause prevents the application from being cleanly interrupted (Ctrl+C) during JSON parsing of search history.

**Fix**: Use `except (ValueError, TypeError):` or `except Exception:`.

---

### BUG-11: CoverLoadWorker Only Catches RuntimeError

- **File**: `ui/views/queue_view.py`
- **Lines**: 176-187
- **Category**: Exception Handling

```python
def run(self):
    try:
        cover_path = _resolve_cover_path(self.track)
        qimage = None
        if cover_path:
            qimage = QImage(cover_path)  # Can raise OSError, ValueError, etc.
        try:
            self.callback_signal.emit(self.track_id, cover_path, qimage)
        except RuntimeError:
            pass
    except RuntimeError:  # Only catches RuntimeError
        pass
```

`QImage(cover_path)` can raise `OSError`, `ValueError`, or other exceptions when the image file is corrupted or inaccessible. These will propagate uncaught, terminating the worker thread silently and potentially leaving stale state.

**Fix**: Change outer `except RuntimeError` to `except Exception`.

---

### BUG-12: Thread Wait Without Result Check in Lyrics Panel

- **File**: `ui/windows/components/lyrics_panel.py`
- **Lines**: 339-343
- **Category**: Race Condition

```python
if self._lyrics_download_thread and isValid(
    self._lyrics_download_thread
) and self._lyrics_download_thread.isRunning():
    self._lyrics_download_thread.quit()
    self._lyrics_download_thread.wait(100)  # Doesn't check if wait succeeded
```

If the thread doesn't stop within 100ms, the code proceeds to create a new worker that may conflict with the still-running old one. Both workers could emit signals concurrently, causing data corruption in the lyrics display.

**Fix**: Check the return value of `wait()`, and if it fails, call `terminate()` then `wait()`.

---

### BUG-13: `priority_score` Fallthrough for Combined Version Markers

- **File**: `utils/dedup.py`
- **Lines**: 101-147
- **Category**: Logic Error

The `priority_score` property doesn't handle all combinations of version markers. For example, a track with both `is_live=True` and `has_special_version=True` (e.g., "Live remix") falls through all conditions to the fallback score of 50:

```python
# None of these match is_live=True + has_special_version=True:
if self.is_live and not self.has_instrumental and not self.has_harmony and not self.has_special_version: ...
if self.has_special_version and not self.is_live and not self.has_instrumental and not self.has_harmony: ...
# ...
return 50  # Fallback - lower than individual scores (Live=80, Special=70)
```

This means a "Live Remix" version gets a lower priority (50) than a plain "Live" (80) or plain "Remix" (70), which can cause deduplication to incorrectly prefer the combined version over a cleaner version.

**Fix**: Add explicit conditions for the `is_live + has_special_version` combination, or use an additive scoring system.

---

## Low Severity Bugs

### BUG-14: STOP Icon Mapped to `play.svg`

- **File**: `ui/icons.py`
- **Line**: 57
- **Category**: Logic Error

```python
STOP = "play.svg"  # Should be a stop icon
```

`IconName.STOP` is mapped to `play.svg` instead of a dedicated stop icon. There is no `stop.svg` in the icons directory, and `IconName.STOP` is currently unused in the codebase, making this a latent bug that would surface if anyone uses `IconName.STOP`.

**Fix**: Either create a `stop.svg` icon and update the mapping, or remove the unused constant.

---

### BUG-15: Ternary Expression Used as Statement

- **File**: `ui/dialogs/cloud_login_dialog.py`
- **Line**: 266
- **Category**: Code Quality / Readability

```python
self._poll_timer.start(2000) if self._qr_token else None
```

This uses a ternary expression as a statement purely for its side effect. While it works (`.start()` is called when `_qr_token` is truthy), the pattern is confusing and non-idiomatic.

**Fix**: Use a normal `if` statement: `if self._qr_token: self._poll_timer.start(2000)`

---

### BUG-16: Deprecated `exec_()` Method Used (11 occurrences)

- **Category**: Deprecated API
- **Locations**:
  - `ui/windows/main_window.py`: lines 919, 928
  - `ui/widgets/player_controls.py`: line 1174
  - `ui/views/playlist_view.py`: line 724
  - `ui/views/queue_view.py`: line 1534
  - `ui/views/library_view.py`: line 1417
  - `ui/views/album_view.py`: line 583
  - `ui/views/artist_view.py`: line 860
  - `ui/dialogs/settings_dialog.py`: line 1194
  - `ui/dialogs/lyrics_download_dialog.py`: line 463
  - `ui/dialogs/input_dialog.py`: line 169

`exec_()` is deprecated in PySide6; the correct method is `exec()`. While `exec_()` still works as an alias in current PySide6, it may be removed in future versions.

**Fix**: Replace all `dialog.exec_()` with `dialog.exec()`.

---

### BUG-17: Redundant `import re` Inside Loop

- **File**: `services/cloud/baidu_service.py`
- **Lines**: 177, 182
- **Category**: Code Quality

`import re` is called twice inside a loop body, despite `re` already being imported at the module level (line 8):

```python
for hist_response in response.history + [response]:
    if 'BDUSS=' in set_cookie:
        import re  # Redundant
        match = re.search(r'BDUSS=([^;]+)', set_cookie)
    if 'STOKEN=' in set_cookie:
        import re  # Redundant (again)
        match = re.search(r'STOKEN=([^;]+)', set_cookie)
```

While Python caches imports so the performance impact is negligible, the redundancy is confusing and suggests copy-paste errors.

**Fix**: Remove the inline `import re` statements.

---

### BUG-18: Schema Version Not Matching Migration Count

- **File**: `infrastructure/database/sqlite_manager.py`
- **Lines**: 675-951
- **Category**: Logic Error / Performance

`CURRENT_SCHEMA_VERSION` is hardcoded to `2`, but there are 6+ migration blocks. All migrations run unconditionally on every startup (using `PRAGMA table_info` checks), and the schema version is only used for a log message. While the migrations are idempotent, this causes unnecessary PRAGMA queries on every application launch.

**Fix**: Increment `CURRENT_SCHEMA_VERSION` to match the migration count and gate migrations based on version numbers.

---

## Appendix: Files Audited

All `.py` files in the following directories were read and reviewed:

- `app/` (2 files)
- `domain/` (9 files)
- `infrastructure/` (6 files)
- `repositories/` (11 files)
- `services/` (28 files)
- `system/` (5 files)
- `ui/` (40 files)
- `utils/` (6 files)
- `main.py`
# Bug Report - Harmony Music Player

> Generated: 2026-03-27
> Scope: Full codebase review (196 Python files)

---

## CRITICAL (data corruption / crashes)

### Bug 0 - Artist Navigation Failure - Fixed (2026-03-27)

**Issue:** Clicking artist names in playback controls failed silently.

**Root Cause:** The `track_artists` junction table referenced artist IDs that didn't exist in the `artists` table. This occurred because:
1. Multi-artist migration script was run multiple times
2. Each run created NEW artist entries with different IDs
3. The `track_artists` table still referenced OLD artist IDs

**Example:**
```
Artists table ID range: 190597 - 191120
track_artists artist_id range: 183090 - 190596  # No overlap!
```

**Fix:**
1. Created `scripts/fix_artist_ids.py` to detect and repair ID mismatches
2. Re-ran `scripts/migrate_multi_artist.py` to properly populate tables

**Verification:**
```sql
-- Artist IDs now match
SELECT MIN(id), MAX(id) FROM artists;
-- Result: 191121 - 191767

SELECT MIN(artist_id), MAX(artist_id) FROM track_artists;
-- Result: 191121 - 191767

-- Artists have correct track counts
SELECT name, song_count FROM artists WHERE name = 'A-Lin';
-- Result: A-Lin | 30
```

---

### Bug 1 - `playlist_item.py:70` - Online track source hardcoded to QQ

```python
source=TrackSource.QQ,  # Hardcoded!
```

When `from_track()` detects an online track via `not track.path`, it unconditionally sets `source=TrackSource.QQ`, even for QUARK/BAIDU tracks that haven't been downloaded yet. This misclassifies track sources.

**Fix:** use `source=track.source` instead.

---

### Bug 2 - `qr_login.py:137/140` - Double `pop("musicid")` causes data loss

```python
musicid=int(cookies.pop("musicid", 0) or 0),       # line 137: removes musicid
str_musicid=cookies.pop("str_musicid", str(cookies.pop("musicid", ""))),  # line 140: musicid already gone!
```

The first `pop` removes `musicid` from the dict; the second `pop` always returns `""`. `str_musicid` will always be empty when `str_musicid` key isn't present in cookies.

**Fix:** save musicid before popping.

---

### Bug 3 - `tripledes.py:383-384` - Wrong bitmask in DES key schedule

```python
c = (...) & 0xFFFFFFF0  # Clears lower 4 bits
d = (...) & 0xFFFFFFF0  # Should be 0x0FFFFFFF to keep lower 28 bits
```

DES C/D registers are 28-bit values. `0xFFFFFFF0` zeros the bottom 4 bits; the correct mask is `0x0FFFFFFF` to keep only the lower 28 bits. This corrupts the key schedule and would break standard DES decryption. (May be compensated elsewhere in this custom implementation if QRC decryption currently works.)

---

### Bug 4 - `audio_engine.py:387-409` - Race condition + unused lock body

```python
def remove_playlist_item_by_cloud_id(self, cloud_file_id: str):
    with self._playlist_lock:
        i = self._cloud_file_id_to_index.get(cloud_file_id)
        if i is not None and 0 <= i < len(self._playlist):
            item = self._playlist[i]
            if item.cloud_file_id == cloud_file_id:
                pass  # <-- does nothing, lock released below
    if i is not None:  # Race: playlist may have changed after lock release
        self.remove_track(i)  # i may now be invalid
```

The `pass` does nothing; the actual `remove_track(i)` runs outside the lock, allowing another thread to modify the playlist in between. Also, if the `if` condition at line 400 is False but `.get()` returned a value, `i` is non-None but the removal is incorrect.

---

### Bug 5 - `sqlite_manager.py` - Multiple write operations bypass DBWriteWorker

Methods that use direct `self._get_connection()` for writes instead of `self._submit_write()`:

- `create_cloud_account()` (line 1872)
- `update_cloud_account_token()` (line 1981)
- `update_cloud_account_folder()` (line 2009)
- `update_cloud_account_playing_state()` (line 2030)
- `delete_cloud_account()` (line 2205)
- `cache_cloud_files()` (line 2225)
- `delete_setting()` (line 2486)

SQLite has single-writer limitation. These can cause "database is locked" errors when called concurrently with other writes.

---

### Bug 6 - `library_service.py:76-78` - `cursor.rowcount` wrong for SELECT

```python
cursor.execute("SELECT COUNT(*) as count FROM albums")
albums_count = cursor.fetchone()["count"] if cursor.rowcount > 0 else 0
```

`cursor.rowcount` is undefined for SELECT statements in SQLite (returns -1). The counts will always be 0.

**Fix:** `result = cursor.fetchone(); albums_count = result["count"] if result else 0`

---

## HIGH (functional bugs)

### Bug 7 - `album_rename_dialog.py:155` - Import at bottom of file

```python
# Line 89: QLineEdit(self._album.artist)  -- used here
# Line 155: from PySide6.QtWidgets import QLineEdit  -- imported here
```

`QLineEdit` is imported at the end of the file after being used in class methods. While Python executes all module-level code sequentially on import (so it works at runtime), this is extremely fragile and breaks IDE analysis. Any circular import could cause a `NameError`.

---

### Bug 8 - `qqmusic_qr_login_dialog.py:385/493` - Duplicate `closeEvent()`

```python
def closeEvent(self, event):  # line 385 -- unreachable
    ...
def closeEvent(self, event):  # line 493 -- overrides first
    ...
```

The second definition silently overrides the first. They happen to be identical, but this is a maintenance hazard.

---

### Bug 9 - `album_repository.py:217` / `artist_repository.py:253` - String split without validation

```python
[(cover, name.split("|")[0], name.split("|")[1])
 for name, cover in existing_covers.items()]
```

Keys are constructed as `f"{name}|{artist}"`. If an album name or artist name contains `"|"`, `split("|")` produces more than 2 elements and `[1]` gets the wrong part.

**Fix:** use `split("|", 1)` for a single split.

---

### Bug 10 - `playlist_utils.py:57` - `hasattr` check always False

```python
if hasattr(parent, "window()") and parent.window():
    parent.window()._nav_playlists.click()
```

`hasattr(parent, "window()")` checks for an attribute literally named `"window()"` (with parentheses), which never exists. Should be `hasattr(parent, "window")`. The "create playlist" navigation never works.

---

### Bug 11 - `cloud.py:55-57` - Missing `updated_at` initialization in CloudFile

```python
def __post_init__(self):
    if self.created_at is None:
        self.created_at = datetime.now()
    # updated_at is never initialized! CloudAccount does it correctly.
```

`CloudFile.updated_at` remains `None` while `CloudAccount` properly initializes both timestamps.

---

### Bug 12 - `handlers.py:620,876` / `file_organization_service.py:189` - Architecture violation: direct `_get_connection()` bypassing repository

```python
conn = self._db._get_connection()  # Accessing private method
cursor = conn.cursor()
cursor.execute("UPDATE tracks SET cloud_file_id = ? WHERE id = ?", ...)
conn.commit()
```

Services directly access DatabaseManager internals instead of going through repositories, violating the layered architecture and potentially causing thread-safety issues.

---

### Bug 13 - `cover_service.py:476` - Debug print left in production

```python
print(f'Cache path: {cache_path}')
```

This `print()` fires on every cover save. Should be `logger.debug()` or removed.

---

### Bug 14 - `dedup.py:50-75` - Incomplete priority scoring

```python
if self.has_special_version and not self.is_live and not self.has_instrumental and not self.has_harmony:
    return 70
if self.has_instrumental and not self.is_live and not self.has_harmony:
    return 60
```

A track with `has_special_version=True` AND `has_instrumental=True` falls through to the fallback score of 50, which is lower than either flag alone (70 or 60). The priority logic is incomplete for combined flags.

---

### Bug 15 - `client.py:269` - Inconsistent JSON serialization

```python
# With sign:
json_str = json.dumps(request_data, separators=(',', ':'), ensure_ascii=False)
# Without sign:
data_to_send = json.dumps(request_data).encode('utf-8')  # Different formatting!
```

The unsigned path uses default JSON formatting (with spaces), which may cause API compatibility issues.

---

## MEDIUM (robustness / thread safety)

### Bug 16 - `audio_engine.py:578-620` - Race in `play_next()`/`play_previous()`

`current_index` is captured inside the lock but used outside it. Between lock releases, the playlist can be modified, making the saved index invalid.

---

### Bug 17 - `sqlite_manager.py:899` - Direct access to `_write_worker._conn`

```python
return self._do_add_track(track_data, conn=self._write_worker._conn)
```

Accesses private `_conn` directly. Should call `_write_worker._get_connection()` to ensure initialization.

---

### Bug 18 - `mini_lyrics_widget.py:55-58` - Missing last-line handling

```python
for i in range(len(self.lines) - 1):
    if self.lines[i].time <= t < self.lines[i + 1].time:
        self.current_index = i
        break
```

`lyrics_widget.py` has an empty-lines guard but `mini_lyrics_widget.py` does not. Also, `mini_lyrics_widget` never updates `current_index` if time is past the last line.

---

### Bug 19 - `hotkeys.py:237,270` - `print()` instead of `logger`

```python
print("DBus not available for MPRIS support")
print("pynput not available for Windows media key support")
```

Should use `logger.debug()` for consistency with the rest of the codebase.

---

### Bug 20 - `crypto.py:94` / `tripledes.py:445` - `print()` instead of `logger`

```python
print(f"QRC decryption failed: {e}")
```

Same issue - debug output bypasses logging configuration.

---

### Bug 21 - `play_history_service.py:62` - Return type annotation mismatch

```python
def add_history(self, track_id: int) -> int:
    """Returns: True if added successfully"""  # Docstring says bool
    return self._history_repo.add(track_id)    # Annotation says int
```

Type annotation says `int`, docstring says `True` (bool).

---

### Bug 22 - `qqmusic_service.py:136` - Missing None check on `result['body']`

```python
songs = result['body'].get('item_song', [])
```

If `result['body']` is `None`, this raises `AttributeError`. Should check `isinstance(body, dict)`.

---

### Bug 23 - `client.py:271-279` - Missing exception handling in `_make_request`

`response.json()` and `response.raise_for_status()` can both throw, but neither is wrapped in try-except.

---

### Bug 24 - `player_controls.py:945-947` - Using `threading.Thread` to emit Qt signals

```python
thread = threading.Thread(target=worker)
thread.start()
# worker emits self._cover_loaded.emit()
```

Qt signals should only be emitted from QThread or properly connected via `Qt.QueuedConnection`. Using raw `threading.Thread` risks thread-safety violations.

---

## Summary

| Severity | Count | Key Issues |
|----------|-------|-----------|
| CRITICAL | 6 | Track source corruption, double-pop data loss, DES mask, race condition, DB write bypass, wrong rowcount |
| HIGH | 9 | Bottom-of-file import, duplicate method, split without validation, always-false hasattr, missing init, architecture violations, debug print, incomplete scoring, JSON inconsistency |
| MEDIUM | 9 | Race conditions, private member access, missing None checks, print vs logger, type mismatch |
| **Total** | **24** | |

## Recommended Fix Priority

1. **Bug 6** (`library_service.py` rowcount) - silently returns wrong data every time
2. **Bug 1** (`playlist_item.py` hardcoded QQ source) - corrupts track sources for QUARK/BAIDU
3. **Bug 5** (DB writes bypassing write worker) - causes intermittent "database is locked" errors
4. **Bug 2** (`qr_login.py` double pop) - breaks `str_musicid` for QQ login
5. **Bug 10** (`playlist_utils.py` always-false hasattr) - playlist navigation from dialog never works
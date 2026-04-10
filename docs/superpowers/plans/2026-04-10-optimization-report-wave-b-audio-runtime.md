# Optimization Report Wave B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the audio runtime, mpv backend, HTTP download, cache, and cleanup items from the report with isolated commits per report item.

**Architecture:** This wave focuses on runtime safety without changing the public playback model. Locking, lookup, and cleanup fixes stay inside infrastructure modules, while verification relies on focused infrastructure tests rather than broad UI flows.

**Tech Stack:** Python 3.11+, PySide6, python-mpv, requests, pytest, uv, git

---

## File Map

- Modify: `infrastructure/audio/audio_engine.py`
- Modify: `infrastructure/audio/mpv_backend.py`
- Modify: `infrastructure/network/http_client.py`
- Modify: `infrastructure/cache/image_cache.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Test: `tests/test_infrastructure/test_audio_engine.py`
- Test: `tests/test_infrastructure/test_audio_engine_play_race.py`
- Test: `tests/test_infrastructure/test_audio_engine_play_next_race.py`
- Test: `tests/test_infrastructure/test_audio_engine_play_after_download_race.py`
- Test: `tests/test_infrastructure/test_mpv_backend.py`
- Test: `tests/test_infrastructure/test_http_client.py`
- Test: `tests/test_infrastructure/test_http_client_atexit.py`
- Test: `tests/test_infrastructure/test_image_cache.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_cleanup.py`

### Task 1: Audio Engine Locking And Playlist Access

**Files:**
- Modify: `infrastructure/audio/audio_engine.py`
- Test: `tests/test_infrastructure/test_audio_engine.py`
- Test: `tests/test_infrastructure/test_audio_engine_play_race.py`
- Test: `tests/test_infrastructure/test_audio_engine_play_next_race.py`
- Test: `tests/test_infrastructure/test_audio_engine_play_after_download_race.py`

- [ ] **Step 1: Add coverage for report items 1.2, 2.6, 3.4, and 3.7**

```python
def test_play_current_track_uses_snapshot_values_after_unlock(...): ...
def test_cloud_file_index_rebuilds_on_partial_failure(...): ...
def test_update_playlist_item_uses_cloud_file_index_first(...): ...
def test_playlist_items_returns_immutable_snapshot(...): ...
```

- [ ] **Step 2: Run the focused infrastructure tests**

Run:
- `uv run pytest tests/test_infrastructure/test_audio_engine.py -v`
- `uv run pytest tests/test_infrastructure/test_audio_engine_play_race.py -v`
- `uv run pytest tests/test_infrastructure/test_audio_engine_play_next_race.py -v`
- `uv run pytest tests/test_infrastructure/test_audio_engine_play_after_download_race.py -v`

Expected: FAIL where lock snapshots, atomic index updates, or snapshot semantics are missing.

- [ ] **Step 3: Implement the runtime fixes**

```python
with self._playlist_lock:
    current_index = self._current_index
    current_item = self._playlist[current_index]
    local_path = current_item.local_path

index = self._cloud_file_id_to_index.get(cloud_file_id)
if index is None:
    index = self._find_index_by_scan(cloud_file_id)

def playlist_items(self) -> tuple[PlaylistItem, ...]:
    with self._playlist_lock:
        return tuple(self._playlist)
```

- [ ] **Step 4: Re-run the focused infrastructure tests**

Run:
- `uv run pytest tests/test_infrastructure/test_audio_engine.py -v`
- `uv run pytest tests/test_infrastructure/test_audio_engine_play_race.py -v`
- `uv run pytest tests/test_infrastructure/test_audio_engine_play_next_race.py -v`
- `uv run pytest tests/test_infrastructure/test_audio_engine_play_after_download_race.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add infrastructure/audio/audio_engine.py tests/test_infrastructure/test_audio_engine.py tests/test_infrastructure/test_audio_engine_play_race.py
git commit -m "优化 1.2 播放列表锁外访问"

git add infrastructure/audio/audio_engine.py tests/test_infrastructure/test_audio_engine.py
git commit -m "优化 2.6 云文件索引原子更新"

git add infrastructure/audio/audio_engine.py tests/test_infrastructure/test_audio_engine.py
git commit -m "优化 3.4 播放列表索引查找"

git add infrastructure/audio/audio_engine.py tests/test_infrastructure/test_audio_engine.py
git commit -m "优化 3.7 播放列表快照返回"
```

### Task 2: Audio Engine Temp File Lifecycle

**Files:**
- Modify: `infrastructure/audio/audio_engine.py`
- Test: `tests/test_infrastructure/test_audio_engine.py`

- [ ] **Step 1: Add a regression test for report item 1.3**

```python
def test_cleanup_temp_files_prunes_and_shutdown_always_cleans(...): ...
```

- [ ] **Step 2: Run the focused test**

Run: `uv run pytest tests/test_infrastructure/test_audio_engine.py -k "temp_files or shutdown" -v`
Expected: FAIL before the cleanup thresholds and shutdown semantics are fixed.

- [ ] **Step 3: Lower the thresholds and make shutdown cleanup unconditional**

```python
MAX_TEMP_FILES = 50
PRUNE_TARGET = 30

def shutdown(self):
    ...
    self.cleanup_temp_files(force=True)
```

- [ ] **Step 4: Re-run the focused test**

Run: `uv run pytest tests/test_infrastructure/test_audio_engine.py -k "temp_files or shutdown" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/audio/audio_engine.py tests/test_infrastructure/test_audio_engine.py
git commit -m "优化 1.3 临时文件清理"
```

### Task 3: mpv Backend Locking, Filter Stability, And Observer Cleanup

**Files:**
- Modify: `infrastructure/audio/mpv_backend.py`
- Test: `tests/test_infrastructure/test_mpv_backend.py`

- [ ] **Step 1: Add coverage for report items 2.7, 3.12, and 4.3**

```python
def test_media_ready_flag_is_guarded_by_lock(...): ...
def test_apply_filters_skips_unchanged_filter_chain(...): ...
def test_cleanup_unobserves_or_logs_and_stops_player(...): ...
```

- [ ] **Step 2: Run the mpv backend tests**

Run: `uv run pytest tests/test_infrastructure/test_mpv_backend.py -v`
Expected: FAIL where locking or redundant filter rebuilds are not yet fixed.

- [ ] **Step 3: Implement the backend changes**

```python
self._media_ready_lock = threading.Lock()

with self._media_ready_lock:
    self._media_ready = True

if new_filter_chain != self._last_filter_chain:
    self._player.af = new_filter_chain
```

- [ ] **Step 4: Re-run the mpv backend tests**

Run: `uv run pytest tests/test_infrastructure/test_mpv_backend.py -v`
Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add infrastructure/audio/mpv_backend.py tests/test_infrastructure/test_mpv_backend.py
git commit -m "优化 2.7 mpv媒体就绪同步"

git add infrastructure/audio/mpv_backend.py tests/test_infrastructure/test_mpv_backend.py
git commit -m "优化 3.12 滤波链重建"

git add infrastructure/audio/mpv_backend.py tests/test_infrastructure/test_mpv_backend.py
git commit -m "优化 4.3 mpv观察回调清理"
```

### Task 4: HTTP Download Safety And Error Context

**Files:**
- Modify: `infrastructure/network/http_client.py`
- Test: `tests/test_infrastructure/test_http_client.py`
- Test: `tests/test_infrastructure/test_http_client_atexit.py`

- [ ] **Step 1: Add coverage for report items 4.1 and 5.4**

```python
def test_download_uses_temp_file_and_atomic_rename(...): ...
def test_download_logs_timeout_connection_and_http_errors_separately(...): ...
```

- [ ] **Step 2: Run the focused HTTP tests**

Run:
- `uv run pytest tests/test_infrastructure/test_http_client.py -v`
- `uv run pytest tests/test_infrastructure/test_http_client_atexit.py -v`

Expected: FAIL before temp-file cleanup and error taxonomy are implemented.

- [ ] **Step 3: Implement the HTTP changes**

```python
with tempfile.NamedTemporaryFile(delete=False, dir=target.parent) as tmp_file:
    ...
os.replace(tmp_path, target_path)

except requests.Timeout:
    logger.warning(...)
except requests.ConnectionError:
    logger.warning(...)
except requests.HTTPError:
    logger.warning(...)
```

- [ ] **Step 4: Re-run the focused HTTP tests**

Run:
- `uv run pytest tests/test_infrastructure/test_http_client.py -v`
- `uv run pytest tests/test_infrastructure/test_http_client_atexit.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add infrastructure/network/http_client.py tests/test_infrastructure/test_http_client.py tests/test_infrastructure/test_http_client_atexit.py
git commit -m "优化 4.1 下载临时文件清理"

git add infrastructure/network/http_client.py tests/test_infrastructure/test_http_client.py
git commit -m "优化 5.4 HTTP错误上下文"
```

### Task 5: Cache And Connection Cleanup

**Files:**
- Modify: `infrastructure/cache/image_cache.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Test: `tests/test_infrastructure/test_image_cache.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_cleanup.py`

- [ ] **Step 1: Add coverage for report items 3.6 and 4.2**

```python
def test_enforce_limits_returns_early_when_cache_under_budget(...): ...
def test_close_shuts_down_all_tracked_sqlite_connections(...): ...
```

- [ ] **Step 2: Run the focused cleanup tests**

Run:
- `uv run pytest tests/test_infrastructure/test_image_cache.py -v`
- `uv run pytest tests/test_infrastructure/test_sqlite_manager_cleanup.py -v`

Expected: FAIL where traversal is unconditional or connections remain open.

- [ ] **Step 3: Implement the cache and connection changes**

```python
total_size = fast_total_size(cache_dir)
if total_size <= self.max_size_bytes:
    return

for thread_id, conn in list(self._connections.items()):
    conn.close()
    del self._connections[thread_id]
```

- [ ] **Step 4: Re-run the focused cleanup tests**

Run:
- `uv run pytest tests/test_infrastructure/test_image_cache.py -v`
- `uv run pytest tests/test_infrastructure/test_sqlite_manager_cleanup.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add infrastructure/cache/image_cache.py tests/test_infrastructure/test_image_cache.py
git commit -m "优化 3.6 图片缓存限制执行"

git add infrastructure/database/sqlite_manager.py tests/test_infrastructure/test_sqlite_manager_cleanup.py
git commit -m "优化 4.2 SQLite连接池清理"
```

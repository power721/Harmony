# Optimization Report Wave A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the repository and database focused report items with one report item per commit, prioritizing correctness in queries, transactions, schema, and repository-side validation.

**Architecture:** This wave keeps fixes close to repository and database boundaries. Query and schema optimizations stay in repositories and `sqlite_manager`, while validation remains at repository/service edges so UI code does not gain new persistence responsibilities.

**Tech Stack:** Python 3.11+, SQLite, pytest, uv, git

---

## File Map

- Modify: `repositories/track_repository.py`
- Modify: `repositories/album_repository.py`
- Modify: `repositories/artist_repository.py`
- Modify: `repositories/genre_repository.py`
- Modify: `repositories/cloud_repository.py`
- Modify: `repositories/favorite_repository.py`
- Modify: `repositories/queue_repository.py`
- Modify: `repositories/history_repository.py`
- Modify: `repositories/playlist_repository.py`
- Modify: `repositories/base_repository.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Modify: `infrastructure/database/db_write_worker.py`
- Modify: `services/cloud/cache_paths.py`
- Modify: `services/library/file_organization_service.py`
- Modify: `services/playback/queue_service.py`
- Modify: `utils/file_helpers.py`
- Modify: `domain/genre.py`
- Test: `tests/test_repositories/test_track_repository.py`
- Test: `tests/test_repositories/test_album_repository.py`
- Test: `tests/test_repositories/test_artist_repository.py`
- Test: `tests/test_repositories/test_genre_repository.py`
- Test: `tests/test_repositories/test_cloud_repository.py`
- Test: `tests/test_repositories/test_favorite_repository.py`
- Test: `tests/test_repositories/test_history_repository.py`
- Test: `tests/test_repositories/test_playlist_repository.py`
- Test: `tests/test_repositories/test_queue_repository.py`
- Test: `tests/test_infrastructure/test_db_write_worker.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_migration.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_cleanup.py`
- Test: `tests/test_utils/test_file_helpers.py`
- Test: `tests/test_domain/test_genre_id.py`

### Task 1: Track Repository Read Path And Shared Provider Normalization

**Files:**
- Modify: `repositories/track_repository.py`
- Modify: `repositories/favorite_repository.py`
- Modify: `repositories/queue_repository.py`
- Test: `tests/test_repositories/test_track_repository.py`
- Test: `tests/test_repositories/test_favorite_repository.py`
- Test: `tests/test_repositories/test_queue_repository.py`

- [ ] **Step 1: Add focused coverage for report items 1.1, 6.1, and 10.1**

```python
def test_get_all_does_not_update_tracks_during_row_hydration(...): ...
def test_shared_online_provider_normalization_handles_blank_and_online(...): ...
def test_search_returns_empty_list_for_blank_query(...): ...
```

- [ ] **Step 2: Run focused repository tests**

Run:
- `uv run pytest tests/test_repositories/test_track_repository.py -k "hydration or search" -v`
- `uv run pytest tests/test_repositories/test_favorite_repository.py -k "provider" -v`
- `uv run pytest tests/test_repositories/test_queue_repository.py -k "provider" -v`

Expected: at least the new read-time write assertion fails before the fix.

- [ ] **Step 3: Implement the repository changes**

```python
def _normalize_online_provider_id(value: object) -> str | None: ...

def _row_to_track(self, row):
    online_provider_id = infer_only_from_row_values(...)
    return Track(..., online_provider_id=online_provider_id)

def search(self, query: str, ...):
    if not query or not query.strip():
        return []
```

- [ ] **Step 4: Re-run the focused repository tests**

Run:
- `uv run pytest tests/test_repositories/test_track_repository.py -k "hydration or search" -v`
- `uv run pytest tests/test_repositories/test_favorite_repository.py -k "provider" -v`
- `uv run pytest tests/test_repositories/test_queue_repository.py -k "provider" -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add repositories/track_repository.py tests/test_repositories/test_track_repository.py
git commit -m "优化 1.1 曲目仓储读时写入"

git add repositories/track_repository.py repositories/favorite_repository.py repositories/queue_repository.py tests/test_repositories/test_track_repository.py tests/test_repositories/test_favorite_repository.py tests/test_repositories/test_queue_repository.py
git commit -m "优化 6.1 在线来源归一化复用"

git add repositories/track_repository.py tests/test_repositories/test_track_repository.py
git commit -m "优化 10.1 仓储输入校验"
```

### Task 2: Genre Identity Determinism

**Files:**
- Modify: `domain/genre.py`
- Test: `tests/test_domain/test_genre_id.py`

- [ ] **Step 1: Add a regression test for report item 1.5**

```python
def test_unnamed_genre_uses_stable_fallback_id():
    first = Genre(name="")
    second = Genre(name=None)
    assert first.id == "unknown"
    assert second.id == "unknown"
```

- [ ] **Step 2: Run the domain test**

Run: `uv run pytest tests/test_domain/test_genre_id.py -v`
Expected: FAIL before the change because unnamed genres currently depend on `id(self)`.

- [ ] **Step 3: Replace the non-deterministic fallback**

```python
@property
def id(self) -> str:
    if self.name:
        return self._named_id
    return "unknown"
```

- [ ] **Step 4: Re-run the domain test**

Run: `uv run pytest tests/test_domain/test_genre_id.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/genre.py tests/test_domain/test_genre_id.py
git commit -m "优化 1.5 流派ID回退"
```

### Task 3: Aggregate Repository Query Efficiency

**Files:**
- Modify: `repositories/album_repository.py`
- Modify: `repositories/artist_repository.py`
- Modify: `repositories/genre_repository.py`
- Test: `tests/test_repositories/test_album_repository.py`
- Test: `tests/test_repositories/test_artist_repository.py`
- Test: `tests/test_repositories/test_genre_repository.py`

- [ ] **Step 1: Add coverage for report items 3.1, 3.2, and 3.3**

```python
def test_album_repository_caches_table_presence(...): ...
def test_genre_repository_uses_joined_cover_lookup(...): ...
def test_artist_refresh_uses_single_scan_contract(...): ...
```

- [ ] **Step 2: Run the repository tests**

Run:
- `uv run pytest tests/test_repositories/test_album_repository.py -v`
- `uv run pytest tests/test_repositories/test_artist_repository.py -v`
- `uv run pytest tests/test_repositories/test_genre_repository.py -v`

Expected: coverage establishes current behavior and exposes inefficient paths during implementation.

- [ ] **Step 3: Implement the query-path changes**

```python
self._cache_table_exists = self._cache_table_exists or self._check_cache_table_once()

SELECT g.name, t.cover_path
FROM genres g
LEFT JOIN (
    SELECT genre, cover_path, ROW_NUMBER() OVER (...) AS rownum
    FROM tracks
) t ON ...

SELECT artist, COUNT(*), COUNT(DISTINCT album), MAX(cover_path)
FROM tracks
GROUP BY artist
```

- [ ] **Step 4: Re-run the repository tests**

Run:
- `uv run pytest tests/test_repositories/test_album_repository.py -v`
- `uv run pytest tests/test_repositories/test_artist_repository.py -v`
- `uv run pytest tests/test_repositories/test_genre_repository.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add repositories/album_repository.py repositories/artist_repository.py repositories/genre_repository.py tests/test_repositories/test_album_repository.py tests/test_repositories/test_artist_repository.py tests/test_repositories/test_genre_repository.py
git commit -m "优化 3.1 缓存表存在性检查"

git add repositories/genre_repository.py tests/test_repositories/test_genre_repository.py
git commit -m "优化 3.2 流派封面查询"

git add repositories/artist_repository.py tests/test_repositories/test_artist_repository.py
git commit -m "优化 3.3 艺术家刷新查询"
```

### Task 4: Transaction Safety, Cloud Updates, And Batch APIs

**Files:**
- Modify: `repositories/album_repository.py`
- Modify: `repositories/artist_repository.py`
- Modify: `repositories/genre_repository.py`
- Modify: `repositories/history_repository.py`
- Modify: `repositories/playlist_repository.py`
- Modify: `repositories/cloud_repository.py`
- Modify: `repositories/favorite_repository.py`
- Test: `tests/test_repositories/test_album_repository.py`
- Test: `tests/test_repositories/test_artist_repository.py`
- Test: `tests/test_repositories/test_genre_repository.py`
- Test: `tests/test_repositories/test_history_repository.py`
- Test: `tests/test_repositories/test_playlist_repository.py`
- Test: `tests/test_repositories/test_cloud_repository.py`
- Test: `tests/test_repositories/test_favorite_repository.py`

- [ ] **Step 1: Add coverage for report items 5.2, 6.2, and 7.3**

```python
def test_refresh_rolls_back_on_failure(...): ...
def test_update_account_playing_state_only_updates_requested_columns(...): ...
def test_favorite_repository_supports_batch_add_and_remove(...): ...
```

- [ ] **Step 2: Run the focused repository tests**

Run:
- `uv run pytest tests/test_repositories/test_album_repository.py -k "rollback" -v`
- `uv run pytest tests/test_repositories/test_artist_repository.py -k "rollback" -v`
- `uv run pytest tests/test_repositories/test_genre_repository.py -k "rollback" -v`
- `uv run pytest tests/test_repositories/test_cloud_repository.py -k "playing_state" -v`
- `uv run pytest tests/test_repositories/test_favorite_repository.py -k "batch" -v`

Expected: FAIL where rollback or batch APIs are missing.

- [ ] **Step 3: Implement the transaction and API changes**

```python
try:
    cursor.execute(...)
    conn.commit()
except Exception:
    conn.rollback()
    raise

updates = []
params = []
for key, column in mapping.items():
    if key in kwargs:
        updates.append(f"{column} = ?")
        params.append(kwargs[key])
```

- [ ] **Step 4: Re-run the focused repository tests**

Run:
- `uv run pytest tests/test_repositories/test_album_repository.py -k "rollback" -v`
- `uv run pytest tests/test_repositories/test_artist_repository.py -k "rollback" -v`
- `uv run pytest tests/test_repositories/test_genre_repository.py -k "rollback" -v`
- `uv run pytest tests/test_repositories/test_cloud_repository.py -k "playing_state" -v`
- `uv run pytest tests/test_repositories/test_favorite_repository.py -k "batch" -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add repositories/album_repository.py repositories/artist_repository.py repositories/genre_repository.py repositories/history_repository.py repositories/playlist_repository.py tests/test_repositories/test_album_repository.py tests/test_repositories/test_artist_repository.py tests/test_repositories/test_genre_repository.py tests/test_repositories/test_history_repository.py tests/test_repositories/test_playlist_repository.py
git commit -m "优化 5.2 仓储事务回滚"

git add repositories/cloud_repository.py tests/test_repositories/test_cloud_repository.py
git commit -m "优化 6.2 云账户播放状态更新"

git add repositories/favorite_repository.py tests/test_repositories/test_favorite_repository.py
git commit -m "优化 7.3 收藏批量操作"
```

### Task 5: Database Schema, Migration, And Text Search Hardening

**Files:**
- Modify: `infrastructure/database/sqlite_manager.py`
- Modify: `repositories/base_repository.py`
- Modify: `repositories/genre_repository.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_migration.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_cleanup.py`
- Test: `tests/test_repositories/test_genre_repository.py`

- [ ] **Step 1: Add coverage for report items 3.5, 7.1, 7.2, 7.4, 7.5, and 7.6**

```python
def test_migrations_create_missing_indexes_once(...): ...
def test_schema_creates_unique_cache_indexes(...): ...
def test_wal_mode_is_verified_after_enable(...): ...
def test_genre_refresh_uses_upsert_contract(...): ...
def test_fts_query_normalizes_unicode_terms(...): ...
```

- [ ] **Step 2: Run the database-focused tests**

Run:
- `uv run pytest tests/test_infrastructure/test_sqlite_manager_migration.py -v`
- `uv run pytest tests/test_infrastructure/test_sqlite_manager_cleanup.py -v`
- `uv run pytest tests/test_repositories/test_genre_repository.py -k "refresh or upsert" -v`

Expected: FAIL where duplicate index creation, missing indexes, or refresh semantics are not yet fixed.

- [ ] **Step 3: Implement the schema and migration changes**

```python
INDEX_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path)",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_unique ON albums(name, artist)",
)

journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
assert str(journal_mode).lower() == "wal"

INSERT OR REPLACE INTO genres (...)
```

- [ ] **Step 4: Re-run the database-focused tests**

Run:
- `uv run pytest tests/test_infrastructure/test_sqlite_manager_migration.py -v`
- `uv run pytest tests/test_infrastructure/test_sqlite_manager_cleanup.py -v`
- `uv run pytest tests/test_repositories/test_genre_repository.py -k "refresh or upsert" -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add infrastructure/database/sqlite_manager.py tests/test_infrastructure/test_sqlite_manager_migration.py
git commit -m "优化 3.5 索引创建路径"

git add infrastructure/database/sqlite_manager.py tests/test_infrastructure/test_sqlite_manager_migration.py
git commit -m "优化 7.1 数据库索引"

git add infrastructure/database/sqlite_manager.py tests/test_infrastructure/test_sqlite_manager_migration.py
git commit -m "优化 7.2 缓存表唯一约束"

git add infrastructure/database/sqlite_manager.py repositories/base_repository.py tests/test_infrastructure/test_sqlite_manager_migration.py
git commit -m "优化 7.4 WAL模式校验"

git add repositories/genre_repository.py tests/test_repositories/test_genre_repository.py
git commit -m "优化 7.5 流派刷新UPSERT"

git add infrastructure/database/sqlite_manager.py tests/test_infrastructure/test_sqlite_manager_migration.py
git commit -m "优化 7.6 FTS查询安全"
```

### Task 6: Worker Backpressure And Service-Side Validation

**Files:**
- Modify: `infrastructure/database/db_write_worker.py`
- Modify: `utils/file_helpers.py`
- Modify: `services/cloud/cache_paths.py`
- Modify: `services/library/file_organization_service.py`
- Modify: `services/playback/queue_service.py`
- Test: `tests/test_infrastructure/test_db_write_worker.py`
- Test: `tests/test_utils/test_file_helpers.py`
- Test: `tests/test_services/test_queue_service.py`

- [ ] **Step 1: Add focused coverage for report items 1.4, 10.3, and 10.4**

```python
def test_db_write_worker_put_timeout_sets_future_error(...): ...
def test_calculate_target_path_requires_existing_writable_directory(...): ...
def test_queue_service_handles_empty_tracks_when_restoring_mode(...): ...
```

- [ ] **Step 2: Run the focused tests**

Run:
- `uv run pytest tests/test_infrastructure/test_db_write_worker.py -v`
- `uv run pytest tests/test_utils/test_file_helpers.py -v`
- `uv run pytest tests/test_services/test_queue_service.py -v`

Expected: FAIL before the fixes where timeouts and validation are missing.

- [ ] **Step 3: Implement the worker and validation changes**

```python
try:
    self._queue.put(job, timeout=5.0)
except queue.Full as exc:
    future.set_exception(exc)

if not target_dir.exists() or not os.access(target_dir, os.W_OK):
    raise ValueError("target_dir must exist and be writable")
```

- [ ] **Step 4: Re-run the focused tests**

Run:
- `uv run pytest tests/test_infrastructure/test_db_write_worker.py -v`
- `uv run pytest tests/test_utils/test_file_helpers.py -v`
- `uv run pytest tests/test_services/test_queue_service.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add infrastructure/database/db_write_worker.py tests/test_infrastructure/test_db_write_worker.py
git commit -m "优化 1.4 数据库写队列溢出处理"

git add utils/file_helpers.py tests/test_utils/test_file_helpers.py
git commit -m "优化 10.3 文件路径校验"

git add services/cloud/cache_paths.py services/library/file_organization_service.py services/playback/queue_service.py tests/test_services/test_queue_service.py
git commit -m "优化 10.4 服务层输入校验"
```

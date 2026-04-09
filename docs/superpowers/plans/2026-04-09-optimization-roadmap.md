# Optimization Roadmap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the highest-risk data consistency and performance issues identified during the repository audit, then reduce architecture duplication in playback, downloads, QQ integration, and aggregate refresh flows.

**Architecture:** Start with correctness in the library data path so album/artist/genre pages and queue metadata stop drifting from `tracks`. Then remove read-time writes and duplicate download/database pathways that currently amplify lock contention and maintenance cost. Keep the existing layered architecture, but move call sites toward repositories/services as the single source of truth instead of direct `DatabaseManager` usage and UI-owned orchestration.

**Tech Stack:** Python 3.11+, PySide6, SQLite, pytest, uv

---

## File Map

**Core library consistency**
- Modify: `services/library/library_service.py`
- Modify: `repositories/track_repository.py`
- Modify: `ui/dialogs/edit_media_info_dialog.py`
- Test: `tests/test_services/test_library_service.py`
- Test: `tests/test_repositories/test_track_repository.py`

**Aggregate refresh performance**
- Modify: `repositories/album_repository.py`
- Modify: `repositories/artist_repository.py`
- Modify: `repositories/genre_repository.py`
- Modify: `services/library/library_service.py`
- Test: `tests/test_services/test_library_service.py`
- Test: `tests/test_repositories/test_track_repository.py`

**Database access consolidation**
- Modify: `infrastructure/database/sqlite_manager.py`
- Modify: `app/bootstrap.py`
- Modify: `ui/windows/main_window.py`
- Modify: `ui/widgets/player_controls.py`
- Test: `tests/test_app/test_bootstrap.py`
- Test: `tests/test_ui/test_main_window_components.py`
- Test: `tests/test_ui/test_player_controls_cleanup.py`

**Download and QQ integration cleanup**
- Modify: `services/download/download_manager.py`
- Modify: `services/playback/handlers.py`
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_client.py`
- Modify: `plugins/builtin/qqmusic/lib/online_detail_view.py`
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Test: `tests/test_services/test_download_manager_cleanup.py`
- Test: `tests/test_ui/test_online_music_view_async.py`
- Test: `tests/test_ui/test_online_views_architecture.py`

**Cloud and main window decomposition**
- Modify: `ui/views/cloud/cloud_drive_view.py`
- Modify: `ui/windows/main_window.py`
- Test: `tests/test_ui/test_cloud_views.py`
- Test: `tests/test_ui/test_plugin_sidebar_integration.py`
- Test: `tests/test_ui/test_window_title_sync.py`

---

### Task 1: Fix Metadata Update Consistency

**Files:**
- Modify: `services/library/library_service.py`
- Modify: `repositories/track_repository.py`
- Modify: `ui/dialogs/edit_media_info_dialog.py`
- Test: `tests/test_services/test_library_service.py`
- Test: `tests/test_repositories/test_track_repository.py`

- [ ] **Step 1: Write failing service tests for aggregate refresh and artist sync after metadata edits**

```python
def test_update_track_metadata_refreshes_aggregates_when_artist_album_or_genre_changes(library_service, mock_track_repo):
    original = Track(id=1, path="/tmp/a.mp3", title="Song", artist="Old Artist", album="Old Album", genre="Old")
    updated = Track(id=1, path="/tmp/a.mp3", title="Song", artist="New Artist", album="New Album", genre="New")
    mock_track_repo.get_by_id.return_value = original
    mock_track_repo.update.return_value = True
    mock_track_repo.get_by_id.side_effect = [original, updated]

    result = library_service.update_track_metadata(
        1,
        artist="New Artist",
        album="New Album",
        genre="New",
    )

    assert result is True
    library_service._album_repo.refresh.assert_called_once()
    library_service._artist_repo.refresh.assert_called_once()
    library_service._genre_repo.refresh.assert_called_once()
    mock_track_repo.sync_track_artists.assert_called_once_with(1, "New Artist")


def test_update_track_metadata_skips_refresh_when_only_title_changes(library_service, mock_track_repo):
    original = Track(id=1, path="/tmp/a.mp3", title="Old", artist="Artist", album="Album", genre="Genre")
    mock_track_repo.get_by_id.return_value = original
    mock_track_repo.update.return_value = True

    result = library_service.update_track_metadata(1, title="New")

    assert result is True
    library_service._album_repo.refresh.assert_not_called()
    library_service._artist_repo.refresh.assert_not_called()
    library_service._genre_repo.refresh.assert_not_called()
    mock_track_repo.sync_track_artists.assert_not_called()
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `uv run pytest tests/test_services/test_library_service.py -k "update_track_metadata" -v`
Expected: FAIL because the current implementation only updates `tracks` and never refreshes aggregates or `track_artists`.

- [ ] **Step 3: Implement minimal correctness fix in the service layer**

```python
def update_track_metadata(...):
    track = self._track_repo.get_by_id(track_id)
    if not track:
        return False

    old_artist = track.artist
    old_album = track.album
    old_genre = track.genre

    if title is not None:
        track.title = title
    if artist is not None:
        track.artist = artist
    if album is not None:
        track.album = album
    if genre is not None:
        track.genre = genre
    if cloud_file_id is not None:
        track.cloud_file_id = cloud_file_id

    updated = self._track_repo.update(track)
    if not updated:
        return False

    artist_changed = old_artist != track.artist
    album_changed = old_album != track.album
    genre_changed = old_genre != track.genre

    if artist_changed:
        self._track_repo.sync_track_artists(track_id, track.artist or "")

    if artist_changed or album_changed or genre_changed:
        self.refresh_albums_artists(immediate=True)

    return True
```

- [ ] **Step 4: Add repository coverage for artist-sync semantics**

```python
def test_update_then_sync_track_artists_rebuilds_junction_rows(track_repo):
    track_id = track_repo.add(Track(path="/tmp/a.mp3", title="Song", artist="A", album="Album"))

    track = track_repo.get_by_id(track_id)
    track.artist = "A, B"
    assert track_repo.update(track) is True
    assert track_repo.sync_track_artists(track_id, "A, B") is True

    assert track_repo.get_track_artist_names(track_id) == ["A", "B"]
```

- [ ] **Step 5: Run the updated tests**

Run:
- `uv run pytest tests/test_services/test_library_service.py -k "update_track_metadata" -v`
- `uv run pytest tests/test_repositories/test_track_repository.py -k "sync_track_artists" -v`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/library/library_service.py repositories/track_repository.py ui/dialogs/edit_media_info_dialog.py tests/test_services/test_library_service.py tests/test_repositories/test_track_repository.py
git commit -m "修复元数据更新后的聚合同步"
```

---

### Task 2: Remove Read-Time Writes From Track Hydration

**Files:**
- Modify: `repositories/track_repository.py`
- Test: `tests/test_repositories/test_track_repository.py`

- [ ] **Step 1: Write a failing regression test for `_row_to_track()` purity**

```python
def test_get_by_id_does_not_write_back_normalized_online_provider(track_repo, monkeypatch):
    track_id = track_repo.add(
        Track(
            path="online://qqmusic/track/abc",
            title="Song",
            artist="Artist",
            album="Album",
            source=TrackSource.ONLINE,
            cloud_file_id="abc",
        )
    )

    conn = track_repo._get_connection()
    original_execute = conn.cursor().execute
    writes = []

    def recording_execute(sql, *args, **kwargs):
        if sql.strip().upper().startswith("UPDATE TRACKS"):
            writes.append(sql)
        return original_execute(sql, *args, **kwargs)

    monkeypatch.setattr(conn.cursor(), "execute", recording_execute)
    track_repo.get_by_id(track_id)

    assert writes == []
```

- [ ] **Step 2: Run the repository test**

Run: `uv run pytest tests/test_repositories/test_track_repository.py -k "does_not_write_back" -v`
Expected: FAIL because `_row_to_track()` currently updates `tracks` during reads.

- [ ] **Step 3: Move normalization to explicit migration/write paths**

```python
def _row_to_track(self, row: sqlite3.Row) -> Track:
    source_value = row["source"] if "source" in row.keys() else "Local"
    normalized_provider_id = self._infer_online_provider_id(
        source_value,
        row["path"] if "path" in row.keys() else "",
        row["online_provider_id"] if "online_provider_id" in row.keys() else None,
    )

    return Track(
        ...,
        source=TrackSource.from_value(source_value),
        online_provider_id=normalized_provider_id,
    )
```

Use migrations or explicit repair helpers for persistence fixes. Do not mutate DB state inside hydration.

- [ ] **Step 4: Run the repository suite for the file**

Run: `uv run pytest tests/test_repositories/test_track_repository.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/track_repository.py tests/test_repositories/test_track_repository.py
git commit -m "移除读路径中的隐式写回"
```

---

### Task 3: Cut N+1 Inserts From Bulk Track Import

**Files:**
- Modify: `repositories/track_repository.py`
- Test: `tests/test_repositories/test_track_repository.py`

- [ ] **Step 1: Write a focused performance-shape regression test**

```python
def test_batch_add_creates_artist_links_for_multiple_tracks_without_per_artist_lookup(track_repo, monkeypatch):
    tracks = [
        Track(path=f"/tmp/{i}.mp3", title=f"S{i}", artist="Artist A, Artist B", album="Album")
        for i in range(5)
    ]

    execute_calls = []
    conn = track_repo._get_connection()
    cursor = conn.cursor()
    original_execute = cursor.execute

    def recording_execute(sql, params=()):
        execute_calls.append(sql.strip().split()[0].upper())
        return original_execute(sql, params)

    monkeypatch.setattr(cursor, "execute", recording_execute)
    added = track_repo.batch_add(tracks)

    assert added == 5
    assert execute_calls.count("SELECT") < 10
```

- [ ] **Step 2: Run the focused test**

Run: `uv run pytest tests/test_repositories/test_track_repository.py -k "batch_add_creates_artist_links" -v`
Expected: FAIL or reveal the current query explosion.

- [ ] **Step 3: Replace per-artist `SELECT id` loops with batched maps**

```python
artist_names = sorted({name for track in tracks for name in split_artists_aware(track.artist, known_artists)})
cursor.executemany(
    """
    INSERT INTO artists (name, normalized_name) VALUES (?, ?)
    ON CONFLICT(name) DO UPDATE SET normalized_name = excluded.normalized_name
    """,
    [(name, normalize_artist_name(name)) for name in artist_names],
)

cursor.execute(
    f"SELECT id, name FROM artists WHERE name IN ({','.join('?' for _ in artist_names)})",
    artist_names,
)
artist_id_map = {row['name']: row['id'] for row in cursor.fetchall()}
```

Then `executemany()` the `track_artists` rows instead of inserting one-by-one.

- [ ] **Step 4: Run bulk-import tests**

Run:
- `uv run pytest tests/test_repositories/test_track_repository.py -k "batch_add" -v`
- `uv run pytest tests/test_services/test_library_service.py -k "bulk" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/track_repository.py tests/test_repositories/test_track_repository.py tests/test_services/test_library_service.py
git commit -m "优化批量导入的艺术家关联写入"
```

---

### Task 4: Replace Full Aggregate Rebuilds With Scoped Refresh Paths

**Files:**
- Modify: `repositories/album_repository.py`
- Modify: `repositories/artist_repository.py`
- Modify: `repositories/genre_repository.py`
- Modify: `services/library/library_service.py`
- Test: `tests/test_services/test_library_service.py`

- [ ] **Step 1: Add service-level tests for scoped refresh**

```python
def test_add_track_uses_debounced_scoped_refresh(library_service, mock_album_repo, mock_artist_repo, mock_genre_repo):
    track = Track(path="/tmp/a.mp3", title="Song", artist="Artist", album="Album", genre="Genre")
    library_service._track_repo.add.return_value = 1

    library_service.add_track(track)

    assert library_service._refresh_timer.isSingleShot()
```

Also add tests that deletions and artist/album changes invoke only affected aggregate upserts or deletes rather than unconditional `DELETE FROM albums` / `DELETE FROM genres`.

- [ ] **Step 2: Run the targeted tests**

Run: `uv run pytest tests/test_services/test_library_service.py -k "refresh" -v`
Expected: FAIL for new scoped behaviors.

- [ ] **Step 3: Introduce repository APIs for targeted aggregate maintenance**

```python
class SqliteAlbumRepository(...):
    def refresh_album(self, album_name: str, artist: str) -> None: ...
    def delete_if_empty(self, album_name: str, artist: str) -> None: ...


class SqliteArtistRepository(...):
    def refresh_artist(self, artist_name: str) -> None: ...
    def delete_if_empty(self, artist_name: str) -> None: ...


class SqliteGenreRepository(...):
    def refresh_genre(self, genre_name: str) -> None: ...
    def delete_if_empty(self, genre_name: str) -> None: ...
```

Keep existing `refresh()` as a rebuild fallback for repair/admin flows, but stop using it in hot paths.

- [ ] **Step 4: Route hot paths through scoped refresh**

```python
def _refresh_track_aggregates(self, *, old_track: Track | None, new_track: Track | None) -> None:
    affected_albums = {(t.album, t.artist) for t in (old_track, new_track) if t and t.album}
    affected_artists = {t.artist for t in (old_track, new_track) if t and t.artist}
    affected_genres = {t.genre for t in (old_track, new_track) if t and t.genre}

    for album_name, artist_name in affected_albums:
        self._album_repo.refresh_album(album_name, artist_name)
        self._album_repo.delete_if_empty(album_name, artist_name)
    for artist_name in affected_artists:
        self._artist_repo.refresh_artist(artist_name)
        self._artist_repo.delete_if_empty(artist_name)
    for genre_name in affected_genres:
        self._genre_repo.refresh_genre(genre_name)
        self._genre_repo.delete_if_empty(genre_name)
```

- [ ] **Step 5: Run affected tests**

Run:
- `uv run pytest tests/test_services/test_library_service.py -q`
- `uv run pytest tests/test_repositories/test_track_repository.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add services/library/library_service.py repositories/album_repository.py repositories/artist_repository.py repositories/genre_repository.py tests/test_services/test_library_service.py
git commit -m "将聚合表刷新改为按范围更新"
```

---

### Task 5: Collapse Duplicate Online Download Worker Registries

**Files:**
- Modify: `services/download/download_manager.py`
- Modify: `services/playback/handlers.py`
- Test: `tests/test_services/test_download_manager_cleanup.py`

- [ ] **Step 1: Add a failing test that `OnlineTrackHandler` delegates to `DownloadManager`**

```python
def test_online_track_handler_uses_download_manager(monkeypatch, handler, playlist_item):
    fake_manager = SimpleNamespace(download_track=MagicMock(return_value=True))
    monkeypatch.setattr("services.playback.handlers.DownloadManager.instance", lambda: fake_manager)

    handler.download_track(playlist_item)

    fake_manager.download_track.assert_called_once_with(playlist_item)
```

- [ ] **Step 2: Run the focused test**

Run: `uv run pytest tests/test_services/test_download_manager_cleanup.py -k "online_track_handler_uses_download_manager" -v`
Expected: FAIL because the handler currently owns its own worker map.

- [ ] **Step 3: Remove duplicated worker registry from playback handler**

```python
def download_track(self, item: PlaylistItem):
    manager = DownloadManager.instance()
    manager.download_track(item)
```

Keep playback-specific success/failure reactions wired via signals from `DownloadManager`, not via a second thread pool.

- [ ] **Step 4: Run download cleanup tests**

Run: `uv run pytest tests/test_services/test_download_manager_cleanup.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/download/download_manager.py services/playback/handlers.py tests/test_services/test_download_manager_cleanup.py
git commit -m "统一在线下载线程编排"
```

---

### Task 6: Consolidate QQ HTTP and Image Loading

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_client.py`
- Modify: `plugins/builtin/qqmusic/lib/online_detail_view.py`
- Modify: `plugins/builtin/qqmusic/lib/online_music_view.py`
- Test: `tests/test_ui/test_online_music_view_async.py`

- [ ] **Step 1: Add tests for request reuse and stale worker cleanup**

```python
def test_online_music_view_cancels_stale_search_results(qtbot, monkeypatch):
    ...
    assert latest_request_id == view._search_request_id
    assert old_worker.isInterruptionRequested()


def test_qqmusic_client_uses_shared_http_client(monkeypatch):
    session = Mock()
    client = QQMusicClient(http_client=session)
    client._http_get("https://example.com")
    session.get.assert_called_once()
```

- [ ] **Step 2: Run the focused tests**

Run:
- `uv run pytest tests/test_ui/test_online_music_view_async.py -k "stale or shared_http" -v`

Expected: FAIL for interruption/shared reuse behaviors that do not exist yet.

- [ ] **Step 3: Implement a shared request path**

```python
class QQMusicClient:
    def __init__(..., http_client=None):
        self._http_client = http_client or requests.Session()
```

Extract image fetch logic to a single helper used by album card loads, detail cover loads, and full-size dialog loads.

- [ ] **Step 4: Interrupt or retire stale workers before replacing them**

```python
def _replace_worker(self, attr_name: str, worker: QThread):
    old_worker = getattr(self, attr_name, None)
    if old_worker and old_worker.isRunning():
        old_worker.requestInterruption()
        old_worker.quit()
    setattr(self, attr_name, worker)
```

Use that helper for `_search_worker`, `_completion_worker`, and `_hotkey_worker`.

- [ ] **Step 5: Run QQ UI tests**

Run: `uv run pytest tests/test_ui/test_online_music_view_async.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add plugins/builtin/qqmusic/lib/qqmusic_client.py plugins/builtin/qqmusic/lib/online_detail_view.py plugins/builtin/qqmusic/lib/online_music_view.py tests/test_ui/test_online_music_view_async.py
git commit -m "收敛QQ网络与异步图片加载"
```

---

### Task 7: Move UI Off Direct `DatabaseManager` Access

**Files:**
- Modify: `app/bootstrap.py`
- Modify: `ui/windows/main_window.py`
- Modify: `ui/widgets/player_controls.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Test: `tests/test_app/test_bootstrap.py`
- Test: `tests/test_ui/test_main_window_components.py`

- [ ] **Step 1: Add a failing architecture test for repository/service-based access**

```python
def test_main_window_playlist_add_uses_library_service_not_database_manager(monkeypatch, qapp):
    ...
    assert fake_library_service.add_track_to_playlist.call_count == 2
    assert fake_db.add_track_to_playlist.call_count == 0
```

- [ ] **Step 2: Run the focused test**

Run: `uv run pytest tests/test_ui/test_main_window_components.py -k "uses_library_service_not_database_manager" -v`
Expected: FAIL because `MainWindow` still calls `self._db.add_track_to_playlist(...)`.

- [ ] **Step 3: Swap UI call sites to services/repositories**

```python
if self._library_service.add_track_to_playlist(playlist.id, track_id):
    added_count += 1
```

For `PlayerControls`, pass explicit lookup callables or service interfaces instead of reaching through `self._player.db`.

- [ ] **Step 4: Remove dead `DatabaseManager` CRUD duplication once call sites are migrated**

```python
class DatabaseManager:
    # keep schema init, migrations, connection lifecycle
    # remove duplicate track CRUD that is now fully owned by repositories
```

- [ ] **Step 5: Run app/UI tests**

Run:
- `uv run pytest tests/test_app/test_bootstrap.py -q`
- `uv run pytest tests/test_ui/test_main_window_components.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/bootstrap.py ui/windows/main_window.py ui/widgets/player_controls.py infrastructure/database/sqlite_manager.py tests/test_app/test_bootstrap.py tests/test_ui/test_main_window_components.py
git commit -m "收敛UI对数据库管理器的直接依赖"
```

---

### Task 8: Decompose Main Window and Cloud Batch Download Hot Paths

**Files:**
- Modify: `ui/windows/main_window.py`
- Modify: `ui/views/cloud/cloud_drive_view.py`
- Test: `tests/test_ui/test_cloud_views.py`
- Test: `tests/test_ui/test_plugin_sidebar_integration.py`

- [ ] **Step 1: Add a focused regression test for view restoration without full list scans**

```python
def test_restore_view_state_uses_targeted_lookup(monkeypatch, qapp):
    ...
    fake_library_service.get_album_by_name.assert_called_once_with("Album", "Artist")
    fake_library_service.get_albums.assert_not_called()
```

- [ ] **Step 2: Run the focused tests**

Run:
- `uv run pytest tests/test_ui/test_plugin_sidebar_integration.py -k "restore_view_state" -v`
- `uv run pytest tests/test_ui/test_cloud_views.py -k "batch_download" -v`

Expected: FAIL because restore paths currently load full collections and cloud batch download is serialized.

- [ ] **Step 3: Replace list scans with targeted lookups**

```python
album = self._library_service.get_album_by_name(name, artist)
artist = self._library_service.get_artist_by_name(name)
genre = self._library_service.get_genre_by_name(name)
```

- [ ] **Step 4: Introduce bounded concurrency for cloud batch download**

```python
self._max_parallel_downloads = 3
self._active_downloads = {}
while self._download_queue and len(self._active_downloads) < self._max_parallel_downloads:
    self._start_download(self._download_queue.popleft())
```

Keep cancellation and UI status updates centralized.

- [ ] **Step 5: Run cloud/UI tests**

Run:
- `uv run pytest tests/test_ui/test_cloud_views.py -q`
- `uv run pytest tests/test_ui/test_plugin_sidebar_integration.py -q`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add ui/windows/main_window.py ui/views/cloud/cloud_drive_view.py tests/test_ui/test_cloud_views.py tests/test_ui/test_plugin_sidebar_integration.py
git commit -m "优化视图恢复与云盘批量下载"
```

---

## Self-Review

**Spec coverage**
- Data consistency after metadata edits: covered in Task 1.
- Read-path writes and lock amplification: covered in Task 2.
- Import/query performance issues: covered in Task 3 and Task 4.
- Duplicate download and HTTP orchestration: covered in Task 5 and Task 6.
- Main window / cloud view maintainability issues: covered in Task 7 and Task 8.

**Placeholder scan**
- No `TODO` / `TBD` placeholders left.
- Each task includes exact files, commands, and concrete implementation direction.

**Type consistency**
- `LibraryService` remains the public application service for library-facing UI work.
- `SqliteTrackRepository.sync_track_artists()` is used consistently as the junction-table sync point.
- `DownloadManager` is the intended single online download orchestrator after Task 5.

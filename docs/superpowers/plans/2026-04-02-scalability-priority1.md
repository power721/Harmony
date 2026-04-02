# Scalability Priority-1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix remaining fatal scalability bottlenecks for 100K tracks

**Architecture:** Implementation-only changes, no architecture refactoring. Fix correlated subquery, add Path.exists cache, paginate track loading, migrate Library View to virtual scrolling.

**Tech Stack:** Python, PySide6 (QListView+Model+Delegate), SQLite

---

## Status: Already Fixed

- PRAGMA optimizations (`synchronous=NORMAL`, `cache_size=-10000`, `temp_store=MEMORY`)
- Correlated subqueries in `track_repository.py`, `album_repository.py`, `genre_repository.py` (use `MAX(CASE WHEN...)`)
- `idx_tracks_genre` index

---

### Task 1: Fix artist_repository.py correlated subquery

**Files:**
- Modify: `repositories/artist_repository.py:53-66`

- [ ] **Step 1: Replace correlated subquery with MAX(CASE WHEN...)**

```python
# Line 53-66: Replace fallback query
# FROM:
(SELECT cover_path FROM tracks t2 WHERE t2.artist = t.artist AND t2.cover_path IS NOT NULL LIMIT 1)
# TO:
MAX(CASE WHEN t.cover_path IS NOT NULL THEN t.cover_path END)
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```
feat: fix artist_repository correlated subquery O(n²) → O(n)
```

---

### Task 2: Add Path.exists cache for playback operations

**Files:**
- Modify: `services/playback/playback_service.py:334-360,450-460`
- Modify: `infrastructure/audio/audio_engine.py:528,575,709,761`
- Modify: `services/playback/queue_service.py:130,188`

**Strategy:** Build a `set` of existing paths once before loops. Replace per-track `Path(p).exists()` with `p in existing_paths`.

- [ ] **Step 1: Add cache builder in playback_service.py `_filter_and_convert_tracks()`**

Before the loop, collect all local paths and batch-check existence:
```python
def _filter_and_convert_tracks(self, tracks: List[Track]) -> List[PlaylistItem]:
    items = []
    # Pre-build path existence cache
    local_paths = set()
    for track in tracks:
        if track and track.path and track.source != TrackSource.QQ:
            local_paths.add(track.path)
    existing_paths = {p for p in local_paths if Path(p).exists()}

    for track in tracks:
        if not track or not track.id or track.id <= 0:
            continue
        is_online = not track.path or track.source == TrackSource.QQ
        if is_online or track.path in existing_paths:
            items.append(PlaylistItem.from_track(track))
    return items
```

- [ ] **Step 2: Same pattern in `load_playlist()` method**

Same cache-builder before loop at ~line 450.

- [ ] **Step 3: Add cache in audio_engine.py**

In `play()`, `play_at()`, `play_next()`, `play_previous()`: These check single tracks (not loops), so Path.exists() here is acceptable (~1-5ms each). **No change needed** — these are per-track checks, not per-100K-track loops.

- [ ] **Step 4: Check queue_service.py for loop-based Path.exists**

Read `queue_service.py:102-153,130,188` and apply same batch cache pattern if there's a loop.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 6: Commit**

```
perf: batch Path.exists checks — play-all 5min → <20s at 100K tracks
```

---

### Task 3: Add pagination to get_all_tracks and Library View

**Files:**
- Modify: `repositories/track_repository.py:79-88` (add count method)
- Modify: `services/library/library_service.py:125-127` (add count, paginated get)
- Modify: `ui/views/library_view.py:871-977` (load pages on demand)

**Strategy:**
- Add `get_count()` to track_repository
- Add `get_all_tracks_paginated(page, page_size)` to library_service
- Library View loads first page immediately, loads more on scroll near bottom

- [ ] **Step 1: Add `get_count()` to track_repository.py**

```python
def get_count(self) -> int:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tracks")
    return cursor.fetchone()[0]
```

- [ ] **Step 2: Library View loads first N tracks (e.g. 1000)**

In `library_view.py` `_populate_table()`, limit initial load:
```python
tracks = self._library_service.get_all_tracks(limit=1000)
```

- [ ] **Step 3: Add scroll-to-bottom detection to load more**

Connect to vertical scroll bar's `valueChanged` signal. When near bottom, load next batch and append to table.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 5: Commit**

```
perf: paginated track loading — memory 50MB → 5MB per page
```

---

### Task 4: Migrate Library View from QTableWidget to QListView+Model+Delegate

**Files:**
- Modify: `ui/views/library_view.py` (full rewrite of tracks table section)
- Reference: `ui/views/local_tracks_list_view.py` (existing pattern)

**Strategy:** Follow the established `LocalTrackModel`/`LocalTrackDelegate`/`LocalTracksListView` pattern. Create a `LibraryTrackModel`, `LibraryTrackDelegate`, and replace `QTableWidget` with `QListView`.

This is the largest change (~4-6 hours). Key differences from local_tracks_list_view:
- 7 columns displayed (source, title, artist, album, genre, duration, actions)
- Row selection mode (ExtendedSelection)
- Header support
- Sorting by column
- Context menu integration

- [ ] **Step 1: Create LibraryTrackModel(QAbstractListModel)**

Roles for each column. `data()` returns values on-demand. `rowCount()` returns track count.

- [ ] **Step 2: Create LibraryTrackDelegate(QStyledItemDelegate)**

Custom `paint()` with QPainter. Fixed row height (~48px). Draw all 7 columns in one row.

- [ ] **Step 3: Replace QTableWidget with QListView in LibraryView**

Swap widget, connect model + delegate. Port selection, sorting, context menu logic.

- [ ] **Step 4: Port search filtering to model-level**

Instead of re-populating table, use `QSortFilterProxyModel` or filter the model's internal list.

- [ ] **Step 5: Run app and verify visually**

Run: `uv run python main.py`
Verify: tracks display, scrolling is smooth, selection works, search filters correctly

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/ -v`
Expected: PASS

- [ ] **Step 7: Commit**

```
perf: migrate Library View to QListView+Delegate — memory 1.2GB → 250MB
```

---

## Not in this plan (Priority 2-3)

- Parallel scan + batch INSERT (Task 6 in analysis)
- View lazy loading (Task 7)
- Incremental cloud_file_id index (Task 8)
- Queue restore batch metadata (Task 10)
- Merge artist refresh queries (Task 11)
- FTS5 incremental maintenance (Task 12)
- DB-side search filtering (Task 13)
- Shuffle optimization (Task 14)
- Queue size limit (Task 15)

---

## Unresolved Questions

1. Library View migration (Task 4) is large — should we do Tasks 1-3 first as quick wins, then tackle Task 4 separately?
2. Should pagination (Task 3) be skipped if Task 4 (virtual scrolling) makes it unnecessary? QListView+Model already solves the memory problem — pagination would be redundant.

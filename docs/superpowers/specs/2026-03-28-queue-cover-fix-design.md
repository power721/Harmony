# Queue Cover Loading Performance Fix

## Problem
QueueItemDelegate uses row-based keys for cover tracking, causing:
- `_requested_covers` grows forever (rows shift on insert/remove)
- Stale covers overwrite fresh ones (version tracked but never checked)
- Lambda captures `track` by reference (race condition)

## Scope
Fix-in-place in `ui/views/queue_view.py`. No architectural changes.

## Changes

### 1. Stable ID keys
- `_requested_covers: set[str]` — uses `_get_cover_cache_key(track)` as ID
- `_cover_versions: dict[str, int]` — same ID
- CoverLoadWorker stores `track_id: str` instead of `row: int`
- Signal: `Signal(str, object, object)` (was `Signal(int, object, object)`)

### 2. Fix lambda capture
- `lambda t=track: self._resolve_cover_path(t)` — default param capture-by-value
- Worker no longer takes a lambda; receives `track_id` + `track_copy: dict`
- CoverLoadWorker resolves cover internally via `_resolve_cover_path`

### 3. Version check works
- `_on_cover_loaded`: compare worker version vs `_cover_versions[track_id]`
- Reject stale results (version mismatch)
- Clear `track_id` from `_requested_covers` on completion

### 4. Animation repaint scoped
- `_advance_animation`: use `viewport().update(index_rect)` instead of `parent._list_view.update(idx)`
- Only repaints the index area (30px wide)

### 5. Preload ±3 instead of ±5
- Reduce worker churn during fast scrolling

## Not changed
- CoverPixmapCache (Qt QPixmapCache already LRU, 128MB limit)
- File structure (stays in queue_view.py)
- Model doesn't own covers

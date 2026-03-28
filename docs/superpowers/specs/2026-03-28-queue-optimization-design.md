# Queue Performance Optimization Design

## Problem

`queue_view.py` (1611 lines) has critical performance issues:

1. **setStyleSheet on every state change** — full style tree recalc per item
2. **Raw `threading.Thread` per item** — 500 items = 500 threads
3. **QListWidget + QWidget items** — no virtualization, no lazy loading
4. **No in-memory cover cache** — repeated disk reads + decode on UI thread
5. **Full rebuild on any change** — `clear()` + recreate all widgets

## Solution

Three-phase optimization, all in this iteration.

## Phase 1: Infrastructure

### CoverPixmapCache (`infrastructure/cache/pixmap_cache.py`, new)

- Wraps `QPixmapCache` (Qt built-in LRU, key=string, limit=128MB)
- Key = MD5(`artist:album`) or MD5(cover path)
- API: `get(key) -> QPixmap | None`, `set(key, pixmap)`
- QImage decode happens in worker thread; `QPixmap.fromImage()` on UI thread

### QThreadPool replacement

- Replace `threading.Thread(daemon=True)` in `QueueItemWidget` with `QRunnable` + `QThreadPool.globalInstance()`
- Worker does `QImage(path)` in background, emits signal to UI thread for `QPixmap.fromImage()` + cache store
- Reuse `CoverLoadWorker` pattern from `PlayerControls`, extract as shared class

### setStyleSheet → QProperty driven

- `QueueItemWidget` uses `setProperty("selected", True/False)` + `setProperty("current", True/False)`
- Global QSS (`styles.qss`) adds `QueueItemWidget[selected="true"]` / `QueueItemWidget[current="true"]` rules
- State change: `self.style().unpolish(self)` + `self.style().polish(self)` — no full style tree reparse
- `refresh_theme()` no longer calls `setStyleSheet`, just unpolish/polish

## Phase 2: Lazy Loading

### Viewport-driven cover loading

- Cover load request fires only when item enters viewport (delegate `paint()`)
- Fast scroll skips: version number / row validation discards stale results
- Completed cover emits signal → model updates row → `dataChanged` → delegate repaints that row only

## Phase 3: Delegate Architecture

### QueueTrackModel (QAbstractListModel)

- Replaces `QListWidget`
- Internal state: `list[PlaylistItem]`, selection `set[int]`, `current_index: int`
- Roles: `TrackRole`, `CoverRole`, `IsSelectedRole`, `IsCurrentRole`, etc.
- Incremental ops: `insert_items(pos, items)`, `move_items(src, dst)`, `remove_items(indices)`, `set_current(index)`, `toggle_selection(index)`
- `data(role)` returns title/artist/cover pixmap/duration/selected/current
- Drag-drop: `flags()` + `supportedDropActions()` + `mimeTypes()` + `dropMimeData()`

### QueueItemDelegate (QStyledItemDelegate)

- Replaces `QueueItemWidget`
- `sizeHint()` → fixed height 72px
- `paint()` → index(30px) | cover(64x64) | title+artist | duration
- Selection/current state read from model roles, different colors
- Placeholder icon when cover not yet loaded
- Editing (rename/media info) stays in popup dialogs, not inline

### QueueView shell

- `QListWidget` → `QListView`
- Set model + delegate
- `ExtendedSelection` + `InternalMove` drag-drop
- Signals: `selectionModel().selectionChanged`, `clicked`, `doubleClicked`
- Context menu, status bar, header unchanged

### Incremental updates (no more full rebuild)

| Event | Before | After |
|-------|--------|-------|
| tracks_added | clear() + rebuild all | insert_rows() |
| track_removed | clear() + rebuild all | remove_rows() |
| track_moved | clear() + rebuild all | move_rows() |
| current changed | clear() + rebuild all | set_current() + dataChanged 1 row |
| theme switch | refresh_theme() per item | delegate re-reads theme palette |

### Public interface unchanged

`QueueView` public API, signals (`track_requested`, `queue_reordered`), Bootstrap injection all stay the same. Upper UI unaware of internal change.

## File Changes

| File | Op | Notes |
|------|----|-------|
| `infrastructure/cache/pixmap_cache.py` | New | QPixmapCache wrapper |
| `ui/views/queue_view.py` | Rewrite | Contains QueueTrackModel + QueueItemDelegate + QueueView |
| `ui/styles.qss` | Edit | Add QueueItem selector rules |
| `services/metadata/cover_service.py` | Tweak | Return path, let caller handle decode |
| `tests/test_queue_view.py` | New | Model/Delegate unit tests |

No changes to: `queue_service.py`, `queue_repository.py`, `domain/`, `Bootstrap`.

## Tests

- `QueueTrackModel`: CRUD, selection, data() per role
- `QueueItemDelegate`: sizeHint, offscreen paint no crash
- Existing `test_queue_selection_fix.py` still passes

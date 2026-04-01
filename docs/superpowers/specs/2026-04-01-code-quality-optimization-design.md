# Code Quality Optimization Design

**Date**: 2026-04-01
**Scope**: P0 + P1 from code quality report
**Strategy**: Critical path first

---

## Problem

1. `DatabaseManager` (3551 lines) duplicates ~80% of Repository operations — two parallel data access layers
2. Services (e.g. PlaybackService) bypass Repository layer, calling `self._db.*` directly (47+ call sites)
3. `online_music_view.py` (3213 lines) is a God class
4. UI layer directly imports `HttpClient` from infrastructure (5 files)
5. Bare `except:` in `ui/icons.py:230`, missing file I/O error handling in 5 locations
6. No tests for core modules (playback_service, sqlite_manager, audio_engine)
7. CI builds but never runs pytest

---

## Step 1 — DatabaseManager → Repository Migration

### Goal

Eliminate the parallel data access layer. All CRUD logic lives in repositories. `DatabaseManager` becomes a thin infrastructure component.

### What stays in DatabaseManager

- `__init__()` / `_get_connection()` — connection management
- `_init_database()` / `_run_migrations()` — schema management
- `_submit_write()` / `_submit_write_async()` — write queue (exposed to BaseRepository)

### What moves

| DatabaseManager methods | Target Repository |
|---|---|
| Track CRUD (add/get/search/delete/update, 15 methods) | TrackRepository |
| Playlist CRUD (create/get/rename/delete, 10 methods) | PlaylistRepository |
| Favorite operations (add/remove/is_favorite/get, 6 methods) | FavoriteRepository |
| History operations (add/get/get_most_played, 4 methods) | HistoryRepository |
| Queue operations (save/load/clear/update, 6 methods) | QueueRepository |
| Cloud operations (account+file CRUD, 20 methods) | CloudRepository |
| Settings operations (get/set/delete, 4 methods) | SettingsRepository |
| Album/Genre/Artist refresh+query (12 methods) | AlbumRepository, GenreRepository, ArtistRepository |

### BaseRepository changes

- Add `submit_write()` method that delegates to DBWriteWorker
- Repositories use it for all writes (instead of raw cursor.execute for writes)
- Reads stay as direct cursor.execute (already thread-safe via WAL)

### Service layer changes

- `PlaybackService`: replace 47+ `self._db.*` calls with repository calls
- `FileOrganizationService`: same pattern
- Any other service using `db_manager` directly: switch to injected repository

### Execution order within this step

1. Extend BaseRepository with write-queue access
2. Migrate methods group-by-group (tracks first, then playlists, favorites, etc.)
3. Update callers (services) to use repositories
4. Remove migrated methods from DatabaseManager
5. Run tests after each group

---

## Step 2 — online_music_view.py Split

Split 3213-line God class into focused components:

- `OnlineMusicView` — main container/layout, delegates to sub-components
- `OnlineSearchDelegate` — search input, results display
- `OnlineRecommendDelegate` — recommendation playlists display
- `OnlineDetailDelegate` — detail page display

Follow existing patterns from other views that use delegates/strategies.

---

## Step 3 — UI → HttpClient Decoupling

Create `services/search/search_service.py` wrapping HttpClient search calls.

Affected files:
- `ui/workers/batch_cover_worker.py`
- `ui/strategies/album_search_strategy.py`
- `ui/strategies/track_search_strategy.py`
- `ui/strategies/artist_search_strategy.py`
- `ui/controllers/cover_controller.py`

UI calls SearchService instead of HttpClient directly.

---

## Step 4 — Quick Fixes

### Bare except (ui/icons.py:230)

```python
except:  →  except Exception:
```

### File I/O error handling

Add try/except to:
- `services/library/playlist_service.py` — M3U export/import (lines 166, 199)
- `system/i18n.py` — JSON loading (lines 29-30, 37-38)
- `services/metadata/metadata_service.py` — cover write (line 298)

### print() → logger

- `ui/windows/main_window.py:1714`
- `services/cloud/qqmusic/tripledes.py:445`

---

## Step 5 — Tests

Write unit tests for:
- `TrackRepository` — newly migrated methods from DatabaseManager
- `FavoriteRepository` — newly migrated methods
- `QueueRepository` — newly migrated methods
- `PlaybackService` — verify it correctly uses repositories (mock repos)

---

## Step 6 — CI Integration

Add pytest step to `.github/workflows/build.yml` before the build step.

---

## Risk Mitigation

- Run `uv run pytest tests/` after each step
- Step 1 is the highest-risk (touches core data flow) — migrate incrementally, one domain at a time
- Each migration group is independently testable

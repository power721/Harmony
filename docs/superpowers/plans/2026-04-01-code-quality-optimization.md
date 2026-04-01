# Code Quality Optimization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix P0+P1 issues from code quality report — migrate DB access from services to repositories, fix error handling, add tests, integrate CI.

**Architecture:** Eliminate dual data access layer. Services use repositories only. DatabaseManager becomes connection manager + migration runner.

---

## Task 1: Add missing methods to repositories

**Files:**
- Modify: `repositories/queue_repository.py` — add `update_local_path`
- Modify: `repositories/album_repository.py` — add `update_on_track_added/updated/deleted`
- Modify: `repositories/artist_repository.py` — add `update_on_track_added/updated/deleted`

- [ ] Migrate SQL from `sqlite_manager.py` into each repository

## Task 2: Inject repos into PlaybackService + handlers

**Files:**
- Modify: `services/playback/playback_service.py` — constructor + all `self._db.*` calls (~47)
- Modify: `services/playback/handlers.py` — all `self._db.*` calls (~30)
- Modify: `app/bootstrap.py` — inject repos

- [ ] Add `favorite_repo`, `queue_repo`, `cloud_repo`, `history_repo`, `album_repo`, `artist_repo` to PlaybackService.__init__
- [ ] Replace all `self._db.get_track()` → `self._track_repo.get_by_id()` etc.
- [ ] Replace all `self._db.is_favorite/add_favorite/remove_favorite` → `self._favorite_repo.*`
- [ ] Replace all `self._db.save_play_queue/load_play_queue/clear_play_queue` → `self._queue_repo.*`
- [ ] Replace all `self._db.get_cloud_account/get_cloud_file_by_file_id` → `self._cloud_repo.*`
- [ ] Replace all `self._db.add_play_history` → `self._history_repo.add`
- [ ] Replace all `self._db.add_track/update_track/update_track_path/update_track_cover_path` → `self._track_repo.*`
- [ ] Replace all `self._db.get_playlist_tracks` → `self._track_repo.get_playlist_tracks`
- [ ] Replace all `self._db.get_favorites` → `self._favorite_repo.get_favorites`
- [ ] Replace all `self._db.update_albums_on_track_added` etc. → `self._album_repo.*` / `self._artist_repo.*`
- [ ] Remove `from infrastructure.database import DatabaseManager` from service files
- [ ] Same replacements in `handlers.py` (pass repos through constructor)
- [ ] Update Bootstrap to inject all repos into PlaybackService

## Task 3: Fix other services using DatabaseManager

**Files:**
- Modify: `services/download/download_manager.py` (2 calls)
- Modify: `services/library/file_organization_service.py` (3 calls)

- [ ] Replace `self._db.*` with repo calls

## Task 4: Quick fixes

**Files:**
- Modify: `ui/icons.py:230` — bare `except:` → `except Exception:`
- Modify: `system/i18n.py` — add try/except around `json.load()`
- Modify: `services/library/playlist_service.py` — add try/except around file I/O
- Modify: `services/metadata/metadata_service.py` — add try/except around cover write
- Modify: `ui/windows/main_window.py:1714` — `print()` → `logger.debug()`
- Modify: `services/cloud/qqmusic/tripledes.py:445` — `print()` → `logger.debug()`

- [ ] Fix each file

## Task 5: CI integration

**Files:**
- Modify: `.github/workflows/build.yml`

- [ ] Add `uv run pytest tests/` step after install, before build

## Task 6: Run tests and verify

- [ ] `uv run pytest tests/` passes

# Review Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the actionable bugs from `docs/代码审查报告_Bug_Report_2026-04-04.md` with one verified commit per bug.

**Architecture:** Keep existing layered boundaries intact while correcting unsafe query handling, worker lifecycle cleanup, repository usage, and playback loading behavior. Each bug is handled as an isolated TDD cycle so every commit maps cleanly to one review item.

**Tech Stack:** Python, PySide6, pytest, sqlite3, uv

---

### Task 1: FTS Search Input Hardening

**Files:**
- Modify: `infrastructure/database/sqlite_manager.py`
- Test: `tests/test_repositories/test_track_repository.py`

- [ ] Step 1: Add a failing repository test for unsafe FTS operators falling back to literal matching or safe fallback.
- [ ] Step 2: Run `uv run pytest tests/test_repositories/test_track_repository.py -k search_tracks -v` and confirm the new test fails for the current implementation.
- [ ] Step 3: Implement minimal FTS query sanitization and keep parameterized `MATCH` usage.
- [ ] Step 4: Re-run `uv run pytest tests/test_repositories/test_track_repository.py -k search_tracks -v` and confirm all targeted search tests pass.
- [ ] Step 5: Commit only the search hardening change.

### Task 2: Download Worker Cleanup Race

**Files:**
- Modify: `services/download/download_manager.py`
- Test: `tests/test_services/test_download_manager_cleanup.py`

- [ ] Step 1: Add a failing test that proves timed-out worker shutdown still releases registry entries and schedules Qt cleanup.
- [ ] Step 2: Run `uv run pytest tests/test_services/test_download_manager_cleanup.py -k stop_worker -v` and confirm the new test fails.
- [ ] Step 3: Update `_stop_worker()` so registry cleanup is unconditional and invalid/stale workers are also removed.
- [ ] Step 4: Re-run `uv run pytest tests/test_services/test_download_manager_cleanup.py -v` and confirm the suite passes.
- [ ] Step 5: Commit only the download manager cleanup fix.

### Task 3: Metadata Thread Lifecycle Verification

**Files:**
- Modify: `services/playback/handlers.py`
- Test: `tests/test_services/test_playback_handlers_cleanup.py`

- [ ] Step 1: Verify whether the report describes a real leak by adding coverage around thread tracking and any missing cleanup entrypoints.
- [ ] Step 2: Run `uv run pytest tests/test_services/test_playback_handlers_cleanup.py -v` and confirm the new or adjusted test fails if a real gap exists.
- [ ] Step 3: Implement the smallest fix needed for the actual gap, or record that the report item is already satisfied if no code change is warranted.
- [ ] Step 4: Re-run `uv run pytest tests/test_services/test_playback_handlers_cleanup.py -v`.
- [ ] Step 5: Commit only if a real bug fix was required for this item.

### Task 4: DBWriteWorker Failure Escalation

**Files:**
- Modify: `infrastructure/database/db_write_worker.py`
- Test: `tests/test_infrastructure/test_db_write_worker.py`

- [ ] Step 1: Add a failing test for repeated task failures causing the worker to stop instead of looping forever.
- [ ] Step 2: Run `uv run pytest tests/test_infrastructure/test_db_write_worker.py -v` and confirm the new test fails.
- [ ] Step 3: Implement bounded consecutive-failure handling without breaking future exception propagation.
- [ ] Step 4: Re-run `uv run pytest tests/test_infrastructure/test_db_write_worker.py -v`.
- [ ] Step 5: Commit only the worker failure handling fix.

### Task 5: Remove Direct Database Calls From PlaybackService

**Files:**
- Modify: `services/playback/playback_service.py`
- Possibly modify: `repositories/album_repository.py`
- Possibly modify: `repositories/artist_repository.py`
- Test: `tests/test_services/` playback-related coverage

- [ ] Step 1: Add a failing test that captures the current architecture violation or missing repository-level refresh/update path after cloud-track insert.
- [ ] Step 2: Run the targeted pytest command for the new playback test and confirm failure.
- [ ] Step 3: Move the album/artist cache update behind repository methods or remove the direct DB call if repository refresh already covers the required behavior.
- [ ] Step 4: Re-run the targeted playback tests and any repository tests touched by the change.
- [ ] Step 5: Commit only the architecture fix.

### Task 6: LyricsLoader Safe Signal Emission

**Files:**
- Modify: `services/lyrics/lyrics_loader.py`
- Test: `tests/test_qthread_fix.py` or a focused service test

- [ ] Step 1: Add a failing test that simulates interruption or invalid loader state before result/error emission.
- [ ] Step 2: Run the focused pytest command for the lyrics loader test and confirm failure.
- [ ] Step 3: Guard all signal emissions with interruption and object-validity checks.
- [ ] Step 4: Re-run the focused lyrics loader tests.
- [ ] Step 5: Commit only the lyrics loader safety fix.

### Task 7: Local Single-Track Playback Load Scope

**Files:**
- Modify: `services/playback/playback_service.py`
- Test: playback service tests

- [ ] Step 1: Add a failing test proving `play_local_track()` does not need to iterate the full library when a single track is requested.
- [ ] Step 2: Run the targeted playback test and confirm failure.
- [ ] Step 3: Implement a bounded playlist loading strategy that preserves play/shuffle behavior.
- [ ] Step 4: Re-run the targeted playback tests.
- [ ] Step 5: Commit only the playback loading optimization.

### Task 8: Cloud Download Error Reporting

**Files:**
- Modify: `services/playback/handlers.py`
- Test: playback handler tests

- [ ] Step 1: Add a failing test that verifies `download_track()` emits user-visible download errors for missing account or cloud file cases.
- [ ] Step 2: Run the targeted handler tests and confirm failure.
- [ ] Step 3: Emit `EventBus.download_error` consistently for validation failures before returning.
- [ ] Step 4: Re-run the targeted handler tests.
- [ ] Step 5: Commit only the cloud download error reporting fix.

### Task 9: Final Verification

**Files:**
- Verify all modified files from Tasks 1-8

- [ ] Step 1: Run each targeted test suite touched by the fixes.
- [ ] Step 2: Run one broader regression command covering repositories, infrastructure, and playback services touched by this work.
- [ ] Step 3: Review commit list and confirm one commit per implemented bug fix.

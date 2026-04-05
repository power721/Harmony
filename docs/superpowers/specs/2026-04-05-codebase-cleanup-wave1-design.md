# Codebase Cleanup Wave 1 Design

## Summary

This design covers a focused cleanup wave across playback, library, repository, UI window lifecycle, and repository-wide lint debt. The work is intentionally decomposed into four independent implementation tracks so each track can be validated and committed separately:

1. Remove the remaining `db_manager` compatibility layer from the affected playback and online UI code paths.
2. Fix `LibraryService` duplicate method definitions and unresolved `Album`/`Artist` type annotations in `TrackRepository`.
3. Strengthen `threading.Thread` lifecycle handling in the mini player and now playing windows.
4. Run a significant but bounded lint convergence pass, split across multiple commits.

The goal is to improve architectural consistency and stability without expanding this wave into unrelated refactors.

## Goals

- Eliminate the remaining direct `db_manager` compatibility seams in the listed files.
- Ensure library and repository code passes targeted lint checks without duplicate or undefined-name issues.
- Make cover-loading thread behavior consistent with existing shutdown and stale-result handling practices.
- Reduce repository-wide Ruff debt substantially while keeping behavior changes low risk and reviewable.

## Non-Goals

- Do not replace repository-level `db_manager` construction inside bootstrap in this wave.
- Do not rewrite Python `threading.Thread` cover loaders into `QThread` unless a blocker is found.
- Do not attempt a full repository lint cleanup to zero errors in this wave.
- Do not fold unrelated architecture refactors into these commits.

## Current Problems

### 1. Residual `db_manager` compatibility layer

`PlaybackService` still accepts a deprecated `db_manager` constructor argument even though its real dependencies are already explicit repositories and services. `OnlineMusicView` and `OnlineDetailView` still accept and store `db_manager`, and they directly call favorite mutation methods through that database object. This leaves UI code with a back door into infrastructure instead of going through service boundaries.

### 2. Library and repository type debt

`LibraryService` defines `refresh_albums_artists` twice, creating override ambiguity and making intent harder to reason about. `TrackRepository` still uses `Album` and `Artist` annotations in ways Ruff reports as undefined names (`F821`), which weakens static confidence in repository APIs.

### 3. Weak thread lifecycle symmetry

`MiniPlayer` and `NowPlayingWindow` both use raw `threading.Thread` for cover loading. They keep some thread references, but the stale-result and close-time invalidation strategy is inconsistent compared with the more deliberate cleanup used for lyrics threads.

### 4. Large lint backlog

Current Ruff output shows hundreds of issues, including a large automatically fixable subset. Without a bounded strategy, the lint pass risks becoming noisy, hard to review, and mixed with behavior changes.

## Architecture

This cleanup wave keeps the existing layered architecture and tightens the boundaries that are already present:

- UI code should orchestrate through application services, not direct database access.
- Playback should depend on explicit repositories and services, not a legacy compatibility argument.
- Repository and service signatures should be statically valid and unambiguous.
- Background cover loading should use a consistent stale-result invalidation model across windows.
- Lint cleanup should be staged by risk and module adjacency, not run as an indiscriminate rewrite.

## Design

### Track A: Remove remaining `db_manager` compatibility usage

#### Files in scope

- `services/playback/playback_service.py`
- `app/bootstrap.py`
- `ui/views/online_music_view.py`
- `ui/views/online_detail_view.py`
- `ui/windows/main_window.py`
- Related targeted tests

#### PlaybackService changes

`PlaybackService` will stop accepting `db_manager` entirely. The constructor signature, type hints, docstring, and stored `_db` attribute will be removed. The service already receives the repositories it needs, so this change makes the interface reflect the real dependency graph.

`Bootstrap.playback_service` will stop passing `db_manager=self.db` when constructing the service.

#### Online views changes

`OnlineMusicView` and `OnlineDetailView` will stop accepting `db_manager` and will remove their `_db` field. Favorite add/remove flows will be redirected through `Bootstrap.instance().favorites_service`, while online track creation remains routed through `library_service.add_online_track(...)`.

The UI sequence becomes:

1. Ensure the online track exists in the library via `library_service`.
2. Add or remove favorite status via `favorites_service`.
3. Update any local UI state that mirrors favorite status.

For removals, the implementation should prefer resolving the stored library track via `library_service.get_track_by_cloud_file_id(...)` and then removing by `track_id` when possible. This keeps favorite mutations aligned with how the online views first materialize the track in the local library.

#### Rationale

This keeps UI components on the service layer and removes the remaining architectural exception that would otherwise encourage future direct database calls.

### Track B: Fix LibraryService duplicate definitions and repository type annotations

#### Files in scope

- `services/library/library_service.py`
- `repositories/track_repository.py`
- Related tests

#### LibraryService changes

`LibraryService` will expose a single `refresh_albums_artists(immediate: bool = False)` method. The earlier duplicate zero-argument definition will be removed. All existing call sites can continue to use the consolidated API because `immediate` defaults to `False`.

#### TrackRepository changes

`TrackRepository` will adopt a consistent type-annotation strategy for `Album` and `Artist` that Ruff can resolve cleanly. The preferred approach is:

- add `TYPE_CHECKING` imports for `Album` and `Artist` at module scope
- keep runtime imports inside methods only where object construction requires them or where circular imports need to be avoided
- update annotations so they no longer trigger `F821`

#### Rationale

This resolves concrete static-analysis issues without changing repository behavior or broadening the service API surface.

### Track C: Harden cover-loading thread lifecycle

#### Files in scope

- `ui/windows/mini_player.py`
- `ui/windows/now_playing_window.py`
- Related targeted tests if practical

#### Strategy

This wave keeps `threading.Thread` for cover loading to avoid an unnecessary threading-model rewrite. Instead, both windows will share the same lifecycle rules:

- keep an explicit reference to the active cover thread
- increment a cover-load version/token every time a new async cover request starts
- emit the version/token with the background completion signal
- ignore results that do not match the current version/token
- invalidate pending cover results during window shutdown and clear references consistently

No blocking `join()` or hard thread stopping will be introduced on the UI thread. The thread work is short-lived; the correct safety boundary here is stale-result invalidation and reference cleanup rather than forced termination.

#### Rationale

This aligns cover loading with the project's existing preference for cooperative cleanup and avoids use-after-close style UI updates from older background tasks.

### Track D: Significant but bounded Ruff convergence

#### Files in scope

- repository-wide, but staged in multiple commits

#### Strategy

This track is explicitly not "make Ruff zero in one pass." It is a convergence wave with bounded risk:

1. Run safe automatic fixes first.
2. Commit those automatic fixes separately.
3. Triage remaining violations by category and module.
4. Manually fix low-risk, high-signal issues in adjacent or high-value modules.
5. Stop after a clear, measurable reduction rather than forcing a risky cleanup marathon.

Expected priority order:

- issues in files touched by Tracks A-C
- undefined-name and unused-import debt that is mechanically clear
- low-risk unused variable/import cleanup in stable modules
- avoid large import-order rewrites or behavior-coupled lint changes unless needed for local correctness

#### Commit policy

Track D should be split into multiple commits, for example:

- safe auto-fix batch
- bootstrap/type-forward-reference cleanup batch
- unused-import and unused-variable cleanup batch

The exact commit splits can adjust to what the codebase reveals, but each commit must remain reviewable and behavior-light.

## Data Flow and Dependency Rules

- UI favorites mutations must flow through `FavoritesService`.
- Online track persistence must flow through `LibraryService`.
- `PlaybackService` should only depend on explicit repositories and supporting services.
- Repository type annotations must be statically resolvable.
- Background cover-loading completion must be gated by the current request version before mutating UI state.

## Error Handling

- If an online track cannot be materialized into the library, the favorite add operation should fail gracefully and avoid partial UI updates.
- Favorite removal should no-op safely when no corresponding library track is found.
- Cover-loading background exceptions should continue to be logged and must not crash UI threads.
- Close-time cleanup should invalidate stale work instead of blocking the window shutdown path.

## Testing Strategy

### Track A

- Add or adjust targeted tests for online view favorite actions so service-based favorite mutation is exercised without direct `db_manager` access.
- Re-run:
  - `tests/test_ui/test_online_music_view_focus.py`
  - `tests/test_ui/test_online_detail_view_actions.py`
  - `tests/test_playback_service_cloud_next.py`

### Track B

- Add or adjust focused tests around `LibraryService.refresh_albums_artists(immediate=...)`.
- Run targeted Ruff checks on:
  - `services/library/library_service.py`
  - `repositories/track_repository.py`

### Track C

- Prefer targeted tests that verify stale async cover results do not overwrite newer ones.
- If practical, add close/shutdown-path coverage for invalidating pending results.
- At minimum, run targeted UI tests and local Ruff checks on both window modules.

### Track D

- Run repository-wide Ruff before and after each lint batch to quantify convergence.
- Re-run affected targeted tests for any module touched by manual lint cleanup.

## Implementation and Commit Boundaries

This design requires separate implementation tracks and separate commits:

1. Remove remaining `db_manager` compatibility usage.
2. Fix `LibraryService` duplicate definitions and `TrackRepository` type annotations.
3. Harden cover-loading thread lifecycle handling.
4. Perform multiple lint convergence commits.

No commit should mix one of the first three tracks with a broad lint sweep.

## Risks and Mitigations

### Favorite behavior drift in online views

Risk: changing from direct database access to `FavoritesService` could subtly change event emission or removal semantics.

Mitigation: use the existing `FavoritesService` API specifically because it already encapsulates favorite-change event emission. Prefer removing by resolved `track_id` where the online track has already been materialized.

### Hidden reliance on duplicate LibraryService method behavior

Risk: a call site may have implicitly depended on the later override only.

Mitigation: keep the surviving method signature backward-compatible with `immediate: bool = False`.

### Background cover updates after window close

Risk: stale worker completion could update UI after shutdown.

Mitigation: introduce a consistent request-version invalidation rule and clear references during `closeEvent`.

### Lint cleanup causing noisy or behavior-coupled changes

Risk: a repository-wide lint pass can become difficult to review and easy to regress.

Mitigation: stage safe auto-fix separately, then hand-fix only bounded low-risk categories in multiple commits.

## Success Criteria

- `PlaybackService`, `OnlineMusicView`, and `OnlineDetailView` no longer expose or store the deprecated `db_manager` compatibility argument.
- Online favorites actions route through `FavoritesService`.
- `LibraryService` contains one unambiguous `refresh_albums_artists` definition.
- `TrackRepository` no longer raises Ruff `F821` for `Album`/`Artist` annotations.
- `MiniPlayer` and `NowPlayingWindow` use the same stale-result and shutdown invalidation model for cover-loading threads.
- Repository-wide Ruff errors are materially reduced through multiple low-risk commits, without claiming full cleanup in this wave.

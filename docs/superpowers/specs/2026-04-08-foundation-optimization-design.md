# Foundation Optimization Design

**Date:** 2026-04-08

## Goal

Implement all still-valid low-risk foundation optimizations from `docs/optimization_report.md`, excluding `plugins/builtin/qqmusic`, and deliver them as separate commits with focused verification.

## Scope

This design covers only optimizations that meet all of the following conditions:

- Still reproducible in the current codebase
- Do not require cross-cutting architectural refactors
- Can be verified with targeted existing or small new tests
- Can be committed independently without coupling unrelated changes

## Explicitly Included

### Domain

- Cache `Album.id`
- Cache `Artist.id`
- Preserve `Genre`'s current per-instance unique ID behavior for empty names while avoiding repeated recomputation for named genres

### Repositories

- Remove the extra cover lookup query in `SqliteAlbumRepository.get_by_name()`
- Remove the extra cover lookup query in `SqliteArtistRepository.get_by_name()`
- Remove `ORDER BY RANDOM()` cover selection from `SqliteGenreRepository`

### Services

- Reduce redundant local lyrics file open attempts in `LyricsService._get_local_lyrics()`

### Infrastructure

- Add a bounded queue to `DBWriteWorker`
- Add HTTP retry configuration to `HttpClient`
- Throttle `HttpClient.download()` progress callbacks
- Make `ImageCache` writes atomic
- Add a size limit and eviction cleanup to `ImageCache`

## Explicitly Excluded

These items are intentionally not part of this round:

- Anything under `plugins/builtin/qqmusic`
- Report items that are already obsolete, including the `SingleFlight` unbounded-cache claim
- High-coupling or behavior-heavy refactors such as `__slots__`, timezone normalization across domain models, `PlaylistItem` responsibility extraction, UI thread offloading, and cloud-service thread-safety rework

## Constraints

- Keep behavior stable unless the optimization itself requires a narrow, testable change
- Do not fold unrelated cleanup into optimization commits
- Respect the current dirty worktree and avoid touching unrelated files
- Use one commit per optimization item

## Planned Commit Sequence

1. Cache domain IDs in `Album`, `Artist`, and `Genre`
2. Optimize `SqliteAlbumRepository.get_by_name()`
3. Optimize `SqliteArtistRepository.get_by_name()`
4. Remove random-order genre cover selection
5. Optimize local lyrics file loading
6. Bound `DBWriteWorker` queue growth
7. Add `HttpClient` retry behavior
8. Throttle `HttpClient.download()` progress callbacks
9. Make `ImageCache` writes atomic
10. Add `ImageCache` size limiting and eviction

## Verification Strategy

Run the smallest relevant tests before each commit:

- Domain: `tests/test_domain/test_album.py`, `tests/test_domain/test_artist.py`, `tests/test_domain/test_genre_id.py`
- Album repository: `tests/test_repositories/test_album_repository.py`
- Artist repository: `tests/test_repositories/test_artist_repository.py`
- Genre repository: `tests/test_repositories/test_genre_repository.py`
- Lyrics service: targeted lyrics service tests for local file loading
- DB worker: `tests/test_infrastructure/test_db_write_worker.py`
- HTTP client: `tests/test_infrastructure/test_http_client.py`, plus related focused tests if needed
- Image cache: `tests/test_infrastructure/test_image_cache.py` and related cache tests

After the final optimization commit, run an aggregated regression pass covering the touched foundation modules.

## Risks And Mitigations

- Query rewrites may change returned cover selection.
  Mitigation: keep result semantics broad where current behavior is already non-deterministic, and assert stable invariants in tests.

- Queue bounding may introduce backpressure where callers previously assumed unbounded submission.
  Mitigation: keep the initial limit conservative and verify submit behavior explicitly.

- Cache eviction may conflict with tests that assume persistence.
  Mitigation: make limits configurable through class attributes and test with temporary directories.

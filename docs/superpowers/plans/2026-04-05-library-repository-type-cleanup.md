# Library Service And TrackRepository Type Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the duplicate `LibraryService.refresh_albums_artists` definition and eliminate unresolved `Album`/`Artist` type annotations in `SqliteTrackRepository`.

**Architecture:** `LibraryService` should expose one unambiguous refresh entry point with optional immediate behavior. `SqliteTrackRepository` should keep runtime imports only where object construction needs them, while module-scope type imports make forward annotations statically resolvable.

**Tech Stack:** Python, pytest, Ruff, unittest.mock, repository/service layer

---

### Task 1: Lock the duplicate-definition cleanup with a focused structural test

**Files:**
- Modify: `tests/test_services/test_library_service.py`
- Test: `tests/test_services/test_library_service.py`

- [ ] **Step 1: Add a failing test that asserts the service defines `refresh_albums_artists` once**

```python
import inspect


def test_refresh_albums_artists_defined_once():
    source = inspect.getsource(LibraryService)
    assert source.count("def refresh_albums_artists(") == 1


def test_refresh_albums_artists_debounces_by_default(library_service, mock_album_repo, mock_artist_repo):
    library_service._refresh_timer = Mock()

    library_service.refresh_albums_artists()

    library_service._refresh_timer.start.assert_called_once_with(500)
    mock_album_repo.refresh.assert_not_called()
    mock_artist_repo.refresh.assert_not_called()
```

- [ ] **Step 2: Run the focused tests to verify the structural assertion fails first**

Run: `uv run pytest tests/test_services/test_library_service.py::TestLibraryService::test_refresh_albums_artists tests/test_services/test_library_service.py::test_refresh_albums_artists_defined_once tests/test_services/test_library_service.py::test_refresh_albums_artists_debounces_by_default -v`

Expected: FAIL because the source still contains two `refresh_albums_artists` definitions.

### Task 2: Consolidate `LibraryService.refresh_albums_artists`

**Files:**
- Modify: `services/library/library_service.py`
- Modify: `tests/test_services/test_library_service.py`
- Test: `tests/test_services/test_library_service.py`

- [ ] **Step 1: Remove the earlier zero-argument duplicate and keep the debounced/immediate version**

```python
    def refresh_albums_artists(self, immediate: bool = False):
        """
        Refresh albums and artists tables.

        Args:
            immediate: If True, refresh immediately; otherwise debounce
        """
        if immediate:
            self._refresh_timer.stop()
            self._do_refresh()
        else:
            self._refresh_albums_artist_async()
```

- [ ] **Step 2: Keep the async helper as the default code path**

```python
    def _refresh_albums_artist_async(self):
        """Refresh albums and artists tables asynchronously (debounced)."""
        self._refresh_timer.start(500)
```

- [ ] **Step 3: Run the library-service tests**

Run: `uv run pytest tests/test_services/test_library_service.py -v`

Expected: PASS

### Task 3: Reproduce the repository type failures with Ruff

**Files:**
- Modify: `repositories/track_repository.py`
- Test: `repositories/track_repository.py`

- [ ] **Step 1: Run Ruff against the target files before changing annotations**

Run: `uv run ruff check services/library/library_service.py repositories/track_repository.py`

Expected: FAIL with `F821` errors on `Album` and `Artist` annotations in `repositories/track_repository.py`.

- [ ] **Step 2: Add module-scope type-only imports for `Album` and `Artist`**

```python
from typing import Dict, List, Optional, TYPE_CHECKING

from domain.track import Track, TrackId, TrackSource
from repositories.base_repository import BaseRepository

if TYPE_CHECKING:
    from domain.album import Album
    from domain.artist import Artist
    from infrastructure.database import DatabaseManager
```

- [ ] **Step 3: Keep the return annotations but make them resolvable**

```python
    def get_albums(self, use_cache: bool = True) -> List["Album"]:
        ...

    def get_artists(self, use_cache: bool = True) -> List["Artist"]:
        ...

    def get_artist_by_name(self, artist_name: str) -> Optional["Artist"]:
        ...

    def get_artist_albums(self, artist_name: str) -> List["Album"]:
        ...

    def get_album_by_name(self, album_name: str, artist: str = None) -> Optional["Album"]:
        ...
```

- [ ] **Step 4: Run the repository tests and focused Ruff check**

Run: `uv run pytest tests/test_repositories/test_track_repository.py -v`

Expected: PASS

Run: `uv run ruff check services/library/library_service.py repositories/track_repository.py`

Expected: PASS

### Task 4: Final verification and commit

**Files:**
- Modify: `services/library/library_service.py`
- Modify: `repositories/track_repository.py`
- Modify: `tests/test_services/test_library_service.py`

- [ ] **Step 1: Run the combined verification command**

Run: `uv run pytest tests/test_services/test_library_service.py tests/test_repositories/test_track_repository.py -v`

Expected: PASS

- [ ] **Step 2: Re-run Ruff for the touched files**

Run: `uv run ruff check services/library/library_service.py repositories/track_repository.py tests/test_services/test_library_service.py`

Expected: PASS

- [ ] **Step 3: Commit only the service/repository cleanup**

```bash
git add services/library/library_service.py repositories/track_repository.py tests/test_services/test_library_service.py
git commit -m "修复库服务类型问题"
```

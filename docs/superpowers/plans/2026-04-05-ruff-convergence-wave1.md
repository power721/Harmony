# Ruff Convergence Wave 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a significant first-pass reduction in repository-wide Ruff debt through multiple low-risk commits, without trying to force the repository to zero issues in one wave.

**Architecture:** The lint work is staged by risk. First take safe mechanical fixes, then clean obvious forward-reference and unused-import debt in stable modules, then tackle a bounded UI import/unused-variable batch. Each batch must remain behavior-light and separately reviewable.

**Tech Stack:** Ruff, pytest, Python type annotations, import cleanup

---

### Task 1: Capture a baseline and land the safe auto-fix batch

**Files:**
- Modify: `domain/online_music.py`
- Modify: `infrastructure/database/db_write_worker.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Modify: `infrastructure/fonts/font_loader.py`
- Modify: `ui/windows/now_playing_window.py`
- Modify: `utils/dedup.py`
- Modify: `utils/helpers.py`
- Test: repository-wide Ruff baseline

- [ ] **Step 1: Record the current Ruff baseline**

Run: `uv run ruff check . --statistics`

Expected: FAIL with the current repository-wide baseline count and category breakdown.

- [ ] **Step 2: Run the safe automatic fixes**

Run: `uv run ruff check . --fix`

Expected: FAIL with remaining non-fixable issues, while removing the safe auto-fix subset.

- [ ] **Step 3: Review and keep only safe mechanical edits in the low-risk files**

```python
# Example kept edits from the auto-fix batch
from typing import Callable, Optional

from domain.cloud import CloudAccount, CloudFile
from domain.playlist import Playlist
from domain.track import Track, TrackSource
from infrastructure.database.db_write_worker import get_write_worker
```

```python
from typing import List, Tuple
```

```text
If Ruff auto-fixes files outside the batch list, inspect them immediately and restore them before this commit.
```

- [ ] **Step 4: Re-run baseline commands after the auto-fix batch**

Run: `uv run ruff check . --statistics`

Expected: FAIL with a materially lower total than the starting baseline.

- [ ] **Step 5: Commit the safe auto-fix batch**

```bash
git add domain/online_music.py infrastructure/database/db_write_worker.py infrastructure/database/sqlite_manager.py infrastructure/fonts/font_loader.py ui/windows/now_playing_window.py utils/dedup.py utils/helpers.py
git commit -m "收敛一批安全lint问题"
```

### Task 2: Clean forward references and obvious import debt in bootstrap/domain modules

**Files:**
- Modify: `app/bootstrap.py`
- Modify: `domain/playlist_item.py`
- Modify: `tests/test_app/test_bootstrap.py`
- Test: `tests/test_app/test_bootstrap.py`

- [ ] **Step 1: Reproduce the focused failures for bootstrap and playlist item**

Run: `uv run ruff check app/bootstrap.py domain/playlist_item.py`

Expected: FAIL with `F821` on forward references such as `ThemeManager`, `OnlineMusicService`, `OnlineDownloadService`, `QQMusicClient`, `PlayQueueItem`, plus any adjacent unused imports.

- [ ] **Step 2: Add module-scope type-only imports that make the forward references explicit**

```python
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from domain.playback import PlayQueueItem
    from services.online import OnlineMusicService
    from services.online.download_service import OnlineDownloadService
    from services.online.cache_cleaner_service import CacheCleanerService
    from services.playback.sleep_timer_service import SleepTimerService
    from system.theme import ThemeManager
```

- [ ] **Step 3: Remove adjacent unused imports revealed in the same files**

```python
                try:
                    import dbus
                    import dbus.mainloop.glib
                    ready = True
                except ImportError:
                    ready = False
```

- [ ] **Step 4: Run focused Ruff and the bootstrap regression test**

Run: `uv run ruff check app/bootstrap.py domain/playlist_item.py`

Expected: PASS

Run: `uv run pytest tests/test_app/test_bootstrap.py -v`

Expected: PASS

- [ ] **Step 5: Commit the forward-reference cleanup**

```bash
git add app/bootstrap.py domain/playlist_item.py tests/test_app/test_bootstrap.py
git commit -m "清理前向类型引用"
```

### Task 3: Land a bounded UI and entrypoint cleanup batch

**Files:**
- Modify: `main.py`
- Modify: `ui/windows/main_window.py`
- Modify: `tests/test_ui/test_main_window_components.py`
- Test: `tests/test_ui/test_main_window_components.py`

- [ ] **Step 1: Reproduce the focused UI lint failures**

Run: `uv run ruff check main.py ui/windows/main_window.py`

Expected: FAIL with `E402`, `F401`, and `F841` issues concentrated around import placement and unused locals.

- [ ] **Step 2: Move module imports to the top and remove unused symbols**

```python
from PySide6.QtCore import Qt, Signal, QSettings, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMenu,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
```

```python
        self._lyrics_controller = LyricsController(
            lyrics_panel=panel,
            event_bus=self._event_bus,
            player=self._playback,
        )
```

- [ ] **Step 3: Remove dead locals in the current-track selection branch**

```python
            artist = track_dict.get("artist", "") if track_dict else ""
            path = track_dict.get("path", "") if track_dict else ""
            source = track_dict.get("source_type", "") or track_dict.get("source", "")
```

- [ ] **Step 4: Run focused Ruff and the main-window component tests**

Run: `uv run ruff check main.py ui/windows/main_window.py`

Expected: PASS

Run: `uv run pytest tests/test_ui/test_main_window_components.py -v`

Expected: PASS

- [ ] **Step 5: Commit the UI cleanup batch**

```bash
git add main.py ui/windows/main_window.py tests/test_ui/test_main_window_components.py
git commit -m "清理主窗口lint问题"
```

### Task 4: Final convergence check

**Files:**
- Modify: `app/bootstrap.py`
- Modify: `domain/playlist_item.py`
- Modify: `domain/online_music.py`
- Modify: `infrastructure/database/db_write_worker.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Modify: `infrastructure/fonts/font_loader.py`
- Modify: `main.py`
- Modify: `ui/windows/main_window.py`
- Modify: `ui/windows/now_playing_window.py`
- Modify: `utils/dedup.py`
- Modify: `utils/helpers.py`

- [ ] **Step 1: Re-run the repository-wide Ruff baseline**

Run: `uv run ruff check . --statistics`

Expected: FAIL or PASS depending on remaining debt, but with a clearly lower total than the initial baseline and no regressions in touched files.

- [ ] **Step 2: Run the regression tests that cover the touched modules**

Run: `uv run pytest tests/test_app/test_bootstrap.py tests/test_ui/test_main_window_components.py tests/test_ui/test_now_playing_window_thread_cleanup.py -v`

Expected: PASS

- [ ] **Step 3: Record the remaining high-risk categories before stopping this wave**

```text
Remaining debt after this wave:
- large import-order / module-structure issues outside touched files
- deeper undefined-name clusters in unrelated packages
- behavior-coupled lint cleanup not justified by this wave
```

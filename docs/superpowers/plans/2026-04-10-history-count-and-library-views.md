# History Count And Library Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix play history counting and add toggleable sidebar/library views for Most Played and Recently Added.

**Architecture:** Keep the change inside the existing library/history/sidebar/settings flow. Fix the history UPSERT at the repository layer, expose recently-added reads from the track/library service layer, and extend the existing `LibraryView` special-mode pattern plus `MainWindow` sidebar routing. View visibility is controlled by dedicated config flags surfaced in a new Settings "Views" tab. Defaults are: `Albums=True`, `Cloud=True`, `Genres=False`, `Most Played=False`, `Recently Added=False`.

**Tech Stack:** Python, PySide6, SQLite, pytest

---

### Task 1: Fix History Counting In The Repository

**Files:**
- Modify: `repositories/history_repository.py`
- Test: `tests/test_repositories/test_history_repository.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_add_increments_play_count(history_repo, populated_db):
    history_repo.add(track_id=1)
    history_repo.add(track_id=1)

    history = history_repo.get_recent(limit=10)

    assert len(history) == 1
    assert history[0].play_count == 2


def test_get_most_played_orders_by_play_count(history_repo, populated_db):
    history_repo.add(track_id=1)
    history_repo.add(track_id=1)
    history_repo.add(track_id=2)

    tracks = history_repo.get_most_played(limit=10)

    assert [track.id for track in tracks[:2]] == [1, 2]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_repositories/test_history_repository.py -k "increments_play_count or get_most_played_orders_by_play_count" -v`
Expected: FAIL because `play_count` is not incremented and `PlayHistory` objects are not populated with the stored count.

- [ ] **Step 3: Write minimal implementation**

```python
cursor.execute(
    """
    INSERT INTO play_history (track_id, played_at, play_count)
    VALUES (?, CURRENT_TIMESTAMP, 1)
    ON CONFLICT(track_id) DO UPDATE SET
        played_at = CURRENT_TIMESTAMP,
        play_count = play_history.play_count + 1
    """,
    (track_id,),
)
```

```python
PlayHistory(
    id=row["id"],
    track_id=row["track_id"],
    played_at=...,
    play_count=row["play_count"] if "play_count" in row.keys() else 1,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_repositories/test_history_repository.py -k "increments_play_count or get_most_played_orders_by_play_count" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/history_repository.py tests/test_repositories/test_history_repository.py
git commit -m "修复播放历史计数"
```

### Task 2: Expose Recently Added Data From The Library Layer

**Files:**
- Modify: `repositories/track_repository.py`
- Modify: `services/library/library_service.py`
- Test: `tests/test_repositories/test_track_repository.py`
- Test: `tests/test_services/test_library_service.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_get_recently_added_returns_newest_created_at_first(track_repo):
    older = Track(path="/music/older.mp3", title="Older", created_at=datetime(2026, 4, 1, 8, 0, 0))
    newer = Track(path="/music/newer.mp3", title="Newer", created_at=datetime(2026, 4, 2, 8, 0, 0))
    track_repo.add(older)
    track_repo.add(newer)

    tracks = track_repo.get_recently_added(limit=10)

    assert [track.title for track in tracks[:2]] == ["Newer", "Older"]
```

```python
def test_get_recently_added_tracks_delegates_to_track_repo(library_service, mock_track_repo):
    mock_track_repo.get_recently_added.return_value = [Track(id=1, title="New")]

    result = library_service.get_recently_added_tracks(limit=25)

    assert [track.title for track in result] == ["New"]
    mock_track_repo.get_recently_added.assert_called_once_with(25)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_repositories/test_track_repository.py -k "get_recently_added" tests/test_services/test_library_service.py -k "get_recently_added_tracks" -v`
Expected: FAIL because the repository/service methods do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def get_recently_added(self, limit: int = 100) -> List[Track]:
    cursor.execute(
        """
        SELECT * FROM tracks
        ORDER BY datetime(COALESCE(created_at, CURRENT_TIMESTAMP)) DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    )
    return [self._row_to_track(row) for row in cursor.fetchall()]
```

```python
def get_recently_added_tracks(self, limit: int = 100) -> List[Track]:
    return self._track_repo.get_recently_added(limit)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_repositories/test_track_repository.py -k "get_recently_added" tests/test_services/test_library_service.py -k "get_recently_added_tracks" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/track_repository.py services/library/library_service.py tests/test_repositories/test_track_repository.py tests/test_services/test_library_service.py
git commit -m "增加最近添加数据接口"
```

### Task 3: Add Config Flags And A Dedicated Views Settings Tab

**Files:**
- Modify: `system/config.py`
- Modify: `ui/dialogs/settings_dialog.py`
- Modify: `translations/en.json`
- Modify: `translations/zh.json`
- Test: `tests/test_ui/test_main_window_components.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_sidebar_page_constants_include_toggleable_library_views(qapp, mock_config):
    ThemeManager.instance(mock_config)

    assert Sidebar.PAGE_MOST_PLAYED == 102
    assert Sidebar.PAGE_RECENTLY_ADDED == 103
```

```python
def test_sidebar_omits_disabled_optional_views(qapp, mock_config):
    ThemeManager.instance(mock_config)
    mock_config.get_cloud_drive_visible.return_value = False
    mock_config.get_most_played_visible.return_value = False
    mock_config.get_recently_added_visible.return_value = False
    mock_config.get_albums_visible.return_value = False
    mock_config.get_genres_visible.return_value = False

    sidebar = Sidebar(config_manager=mock_config)

    page_ids = [page for page, _ in sidebar._nav_buttons]
    assert Sidebar.PAGE_CLOUD not in page_ids
    assert Sidebar.PAGE_ALBUMS not in page_ids
    assert Sidebar.PAGE_GENRES not in page_ids
    assert Sidebar.PAGE_MOST_PLAYED not in page_ids
    assert Sidebar.PAGE_RECENTLY_ADDED not in page_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_main_window_components.py -k "toggleable_library_views or omits_disabled_optional_views" -v`
Expected: FAIL because the config helpers, settings tab controls, and sidebar visibility logic do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class SettingKey:
    UI_SHOW_ALBUMS = "ui.show_albums"
    UI_SHOW_GENRES = "ui.show_genres"
    UI_SHOW_CLOUD = "ui.show_cloud"
    UI_SHOW_MOST_PLAYED = "ui.show_most_played"
    UI_SHOW_RECENTLY_ADDED = "ui.show_recently_added"
```

```python
def get_albums_visible(self) -> bool:
    return bool(self.get(SettingKey.UI_SHOW_ALBUMS, True))
```

```python
def get_genres_visible(self) -> bool:
    return bool(self.get(SettingKey.UI_SHOW_GENRES, False))


def get_most_played_visible(self) -> bool:
    return bool(self.get(SettingKey.UI_SHOW_MOST_PLAYED, False))


def get_recently_added_visible(self) -> bool:
    return bool(self.get(SettingKey.UI_SHOW_RECENTLY_ADDED, False))
```

```python
views_tab = QWidget()
views_layout = QVBoxLayout(views_tab)
self._show_albums_checkbox = QCheckBox(t("view_show_albums"))
self._show_genres_checkbox = QCheckBox(t("view_show_genres"))
self._show_cloud_checkbox = QCheckBox(t("view_show_cloud"))
self._show_most_played_checkbox = QCheckBox(t("view_show_most_played"))
self._show_recently_added_checkbox = QCheckBox(t("view_show_recently_added"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_main_window_components.py -k "toggleable_library_views or omits_disabled_optional_views" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add system/config.py ui/dialogs/settings_dialog.py translations/en.json translations/zh.json tests/test_ui/test_main_window_components.py
git commit -m "增加视图开关设置"
```

### Task 4: Extend Sidebar, MainWindow, And LibraryView With The New Modes

**Files:**
- Modify: `ui/windows/components/sidebar.py`
- Modify: `ui/windows/main_window.py`
- Modify: `ui/views/library_view.py`
- Test: `tests/test_ui/test_library_view.py`
- Test: `tests/test_ui/test_main_window_components.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_library_view_show_most_played_uses_list_view(qapp, mock_theme_config, sample_tracks):
    view, _, _, history_service = _build_library_view(mock_theme_config, sample_tracks)
    history_service.get_most_played.return_value = sample_tracks

    view.show_most_played()
    qapp.processEvents()

    history_service.get_most_played.assert_called_once_with(limit=100)
    assert view.get_current_view() == "most_played"
```

```python
def test_library_view_show_recently_added_uses_list_view(qapp, mock_theme_config, sample_tracks):
    view, library_service, _, _ = _build_library_view(mock_theme_config, sample_tracks)
    library_service.get_recently_added_tracks.return_value = sample_tracks

    view.show_recently_added()
    qapp.processEvents()

    library_service.get_recently_added_tracks.assert_called_once_with(limit=100)
    assert view.get_current_view() == "recently_added"
```

```python
def test_sidebar_requests_new_special_pages_through_main_window(qapp):
    # Build MainWindow with mocked show handlers and verify routing
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_library_view.py -k "most_played or recently_added" tests/test_ui/test_main_window_components.py -k "new_special_pages" -v`
Expected: FAIL because the new modes, sidebar pages, and routing helpers do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
self._current_view = "most_played"
self._title_label.setText(t("most_played"))
self._stacked_widget.setCurrentWidget(self._all_tracks_list_view)
self._source_filter.setVisible(False)
self._load_most_played()
```

```python
def _load_most_played(self):
    tracks = self._play_history_service.get_most_played(limit=100)
    favorite_ids = self._favorites_service.get_all_favorite_track_ids()
    self._all_tracks_list_view.load_tracks(tracks, favorite_ids)
```

```python
if page_index == Sidebar.PAGE_MOST_PLAYED:
    self._show_most_played()
elif page_index == Sidebar.PAGE_RECENTLY_ADDED:
    self._show_recently_added()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_library_view.py -k "most_played or recently_added" tests/test_ui/test_main_window_components.py -k "new_special_pages" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/windows/components/sidebar.py ui/windows/main_window.py ui/views/library_view.py tests/test_ui/test_library_view.py tests/test_ui/test_main_window_components.py
git commit -m "补充最多播放和最近添加视图"
```

### Task 5: Verify The Integrated Behavior

**Files:**
- Modify: `tests/test_ui/test_main_window_components.py`
- Modify: `tests/test_ui/test_library_view.py`
- Modify: `tests/test_repositories/test_history_repository.py`

- [ ] **Step 1: Run the focused verification suite**

Run: `uv run pytest tests/test_repositories/test_history_repository.py tests/test_repositories/test_track_repository.py -k "get_recently_added or play_count or most_played" tests/test_services/test_library_service.py -k "recently_added" tests/test_ui/test_library_view.py -k "history or most_played or recently_added" tests/test_ui/test_main_window_components.py -k "Sidebar or special_pages" -v`
Expected: PASS

- [ ] **Step 2: Run a second focused UI/settings verification**

Run: `uv run pytest tests/test_ui/test_library_view.py tests/test_ui/test_main_window_components.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_repositories/test_history_repository.py tests/test_repositories/test_track_repository.py tests/test_services/test_library_service.py tests/test_ui/test_library_view.py tests/test_ui/test_main_window_components.py
git commit -m "完善视图与播放历史验证"
```

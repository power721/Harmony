# Playlist Folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-class one-level playlist folders with top-level ungrouped playlists, tree navigation, folder CRUD, and drag-and-drop reordering/moves without breaking existing playlist playback flows.

**Architecture:** Persist folders as their own SQLite table and attach playlists to folders through a nullable `folder_id`, with `position` columns controlling per-container ordering. Keep folder semantics in the repository/service layers, surface a typed tree to the UI, and encapsulate tree rendering plus drag-drop behavior in a dedicated widget so `PlaylistView` only coordinates selection, actions, and right-side content loading.

**Tech Stack:** Python 3.11, PySide6, SQLite, pytest, pytest-qt

---

## File Map

- Create: `domain/playlist_folder.py`
  - Folder and tree dataclasses used by repository/service/UI.
- Create: `tests/test_services/test_playlist_service.py`
  - Service-level validation and event tests for folder operations.
- Create: `ui/widgets/playlist_tree_widget.py`
  - Tree widget that renders folder/playlist nodes and emits structured drag-drop actions.
- Create: `tests/test_ui/test_playlist_tree_widget.py`
  - Focused drag-drop and node behavior tests for the tree widget.
- Modify: `domain/playlist.py`
  - Add `folder_id` and `position` to `Playlist`.
- Modify: `domain/__init__.py`
  - Export folder/tree dataclasses.
- Modify: `infrastructure/database/sqlite_manager.py`
  - Create/migrate `playlist_folders`, `playlists.folder_id`, and `playlists.position`.
- Modify: `repositories/playlist_repository.py`
  - Folder CRUD, tree loading, move/reorder operations, and row mapping.
- Modify: `services/library/playlist_service.py`
  - Folder validation, tree API, and `playlist_structure_changed` emission.
- Modify: `system/event_bus.py`
  - Add `playlist_structure_changed`.
- Modify: `ui/views/playlist_view.py`
  - Replace flat playlist list with tree widget, add folder actions, keep right-side playback behavior unchanged.
- Modify: `ui/widgets/__init__.py`
  - Re-export `PlaylistTreeWidget` if this package already serves as the widget import surface.
- Modify: `translations/en.json`
  - Add folder action strings and error messages.
- Modify: `translations/zh.json`
  - Add folder action strings and error messages.
- Modify: `tests/test_domain/test_playlist.py`
  - Cover new playlist fields.
- Modify: `tests/test_infrastructure/test_sqlite_manager_migration.py`
  - Cover fresh-schema and legacy-schema migration behavior.
- Modify: `tests/test_repositories/test_playlist_repository.py`
  - Cover folder CRUD, tree loading, and move/reorder semantics.
- Modify: `tests/test_repositories/test_track_repository.py`
  - Update temporary schema fixture for the new playlist columns/table.
- Modify: `tests/test_system/test_event_bus.py`
  - Assert the new structure-change signal exists and emits.
- Modify: `tests/test_ui/test_playlist_view.py`
  - Integration coverage for tree rendering, folder click behavior, folder actions, and selection persistence.

### Task 1: Add Domain Models and Database Migration

**Files:**
- Create: `domain/playlist_folder.py`
- Modify: `domain/playlist.py`
- Modify: `domain/__init__.py`
- Modify: `infrastructure/database/sqlite_manager.py`
- Test: `tests/test_domain/test_playlist.py`
- Test: `tests/test_infrastructure/test_sqlite_manager_migration.py`

- [ ] **Step 1: Write the failing domain and migration tests**

```python
# tests/test_domain/test_playlist.py
def test_playlist_supports_folder_and_position():
    playlist = Playlist(name="Road Trip", folder_id=7, position=3)
    assert playlist.folder_id == 7
    assert playlist.position == 3


# tests/test_infrastructure/test_sqlite_manager_migration.py
def test_init_database_creates_playlist_folder_schema():
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        db = DatabaseManager(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(playlists)")
        playlist_columns = {row[1] for row in cursor.fetchall()}
        assert "folder_id" in playlist_columns
        assert "position" in playlist_columns

        cursor.execute("PRAGMA table_info(playlist_folders)")
        folder_columns = {row[1] for row in cursor.fetchall()}
        assert {"id", "name", "position", "created_at"} <= folder_columns

        cursor.execute("PRAGMA index_list(playlist_folders)")
        folder_indexes = {row[1] for row in cursor.fetchall()}
        assert "idx_playlist_folders_name_nocase" in folder_indexes

        conn.close()
        db.close()
    finally:
        os.unlink(db_path)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_domain/test_playlist.py::test_playlist_supports_folder_and_position tests/test_infrastructure/test_sqlite_manager_migration.py::test_init_database_creates_playlist_folder_schema -v`

Expected: FAIL because `Playlist` does not accept `folder_id` / `position` and the database schema does not create folder-related columns/tables yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# domain/playlist.py
@dataclass(slots=True)
class Playlist:
    id: Optional[int] = None
    name: str = ""
    folder_id: Optional[int] = None
    position: int = 0
    created_at: Optional[datetime] = None


# domain/playlist_folder.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .playlist import Playlist


@dataclass(slots=True)
class PlaylistFolder:
    id: Optional[int] = None
    name: str = ""
    position: int = 0
    created_at: Optional[datetime] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


@dataclass(slots=True)
class PlaylistFolderGroup:
    folder: PlaylistFolder
    playlists: list[Playlist] = field(default_factory=list)


@dataclass(slots=True)
class PlaylistTree:
    root_playlists: list[Playlist] = field(default_factory=list)
    folders: list[PlaylistFolderGroup] = field(default_factory=list)
```

```python
# domain/__init__.py
from .playlist import Playlist
from .playlist_folder import PlaylistFolder, PlaylistFolderGroup, PlaylistTree

__all__ = [
    "Playlist",
    "PlaylistFolder",
    "PlaylistFolderGroup",
    "PlaylistTree",
]
```

```python
# infrastructure/database/sqlite_manager.py
cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlist_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("""
    CREATE UNIQUE INDEX IF NOT EXISTS idx_playlist_folders_name_nocase
    ON playlist_folders(name COLLATE NOCASE)
""")

cursor.execute("PRAGMA table_info(playlists)")
playlist_columns = {row[1] for row in cursor.fetchall()}
if "folder_id" not in playlist_columns:
    cursor.execute("ALTER TABLE playlists ADD COLUMN folder_id INTEGER")
if "position" not in playlist_columns:
    cursor.execute("ALTER TABLE playlists ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_playlists_folder_position
    ON playlists(folder_id, position)
""")
cursor.execute("""
    WITH ordered AS (
        SELECT id, ROW_NUMBER() OVER (ORDER BY id) - 1 AS row_num
        FROM playlists
        WHERE folder_id IS NULL
    )
    UPDATE playlists
    SET position = (SELECT row_num FROM ordered WHERE ordered.id = playlists.id)
    WHERE id IN (SELECT id FROM ordered)
      AND position = 0
""")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_domain/test_playlist.py::test_playlist_supports_folder_and_position tests/test_infrastructure/test_sqlite_manager_migration.py::test_init_database_creates_playlist_folder_schema -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add domain/playlist.py domain/playlist_folder.py domain/__init__.py infrastructure/database/sqlite_manager.py tests/test_domain/test_playlist.py tests/test_infrastructure/test_sqlite_manager_migration.py
git commit -m "添加播放列表文件夹基础模型"
```

### Task 2: Implement Repository Folder CRUD and Tree Loading

**Files:**
- Modify: `repositories/playlist_repository.py`
- Modify: `tests/test_repositories/test_playlist_repository.py`
- Modify: `tests/test_repositories/test_track_repository.py`

- [ ] **Step 1: Write the failing repository tests**

```python
# tests/test_repositories/test_playlist_repository.py
def test_create_folder_and_get_all_folders(playlist_repo):
    folder_id = playlist_repo.create_folder("Workout")
    folders = playlist_repo.get_all_folders()

    assert folder_id > 0
    assert [folder.name for folder in folders] == ["Workout"]
    assert folders[0].position == 0


def test_get_playlist_tree_groups_root_and_folder_playlists(playlist_repo):
    root_id = playlist_repo.add(Playlist(name="Root", position=0))
    folder_id = playlist_repo.create_folder("Mood")
    nested_id = playlist_repo.add(Playlist(name="Chill", folder_id=folder_id, position=0))

    tree = playlist_repo.get_playlist_tree()

    assert [p.name for p in tree.root_playlists] == ["Root"]
    assert [group.folder.name for group in tree.folders] == ["Mood"]
    assert [p.name for p in tree.folders[0].playlists] == ["Chill"]


def test_rename_folder_updates_name(playlist_repo):
    folder_id = playlist_repo.create_folder("Old Name")

    assert playlist_repo.rename_folder(folder_id, "New Name") is True
    assert [folder.name for folder in playlist_repo.get_all_folders()] == ["New Name"]


def test_get_folder_by_name_is_case_insensitive(playlist_repo):
    playlist_repo.create_folder("Workout")
    folder = playlist_repo.get_folder_by_name("workout")

    assert folder is not None
    assert folder.name == "Workout"
```

```python
# tests/test_repositories/test_track_repository.py
cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlist_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS playlists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        folder_id INTEGER,
        position INTEGER NOT NULL DEFAULT 0,
        description TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_repositories/test_playlist_repository.py::test_create_folder_and_get_all_folders tests/test_repositories/test_playlist_repository.py::test_get_playlist_tree_groups_root_and_folder_playlists tests/test_repositories/test_playlist_repository.py::test_rename_folder_updates_name -v`

Expected: FAIL because `SqlitePlaylistRepository` does not expose folder CRUD or tree APIs yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# repositories/playlist_repository.py
def _row_to_playlist(self, row) -> Playlist:
    return Playlist(
        id=row["id"],
        name=row["name"],
        folder_id=row["folder_id"] if "folder_id" in row.keys() else None,
        position=row["position"] if "position" in row.keys() else 0,
    )


def _row_to_folder(self, row) -> PlaylistFolder:
    return PlaylistFolder(
        id=row["id"],
        name=row["name"],
        position=row["position"],
    )


def create_folder(self, name: str) -> int:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_folders")
    position = int(cursor.fetchone()[0])
    cursor.execute(
        "INSERT INTO playlist_folders (name, position) VALUES (?, ?)",
        (name, position),
    )
    conn.commit()
    return cursor.lastrowid


def get_folder(self, folder_id: int) -> Optional[PlaylistFolder]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playlist_folders WHERE id = ?", (folder_id,))
    row = cursor.fetchone()
    return self._row_to_folder(row) if row else None


def get_folder_by_name(self, name: str) -> Optional[PlaylistFolder]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM playlist_folders WHERE name = ? COLLATE NOCASE",
        (name,),
    )
    row = cursor.fetchone()
    return self._row_to_folder(row) if row else None


def get_all_folders(self) -> list[PlaylistFolder]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playlist_folders ORDER BY position, id")
    return [self._row_to_folder(row) for row in cursor.fetchall()]


def rename_folder(self, folder_id: int, name: str) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE playlist_folders SET name = ? WHERE id = ?", (name, folder_id))
    conn.commit()
    return cursor.rowcount > 0


def get_playlist_tree(self) -> PlaylistTree:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playlist_folders ORDER BY position, id")
    folders = [PlaylistFolderGroup(folder=self._row_to_folder(row)) for row in cursor.fetchall()]
    folder_map = {group.folder.id: group for group in folders}

    cursor.execute("SELECT * FROM playlists ORDER BY folder_id IS NOT NULL, folder_id, position, id")
    root_playlists: list[Playlist] = []
    for row in cursor.fetchall():
        playlist = self._row_to_playlist(row)
        if playlist.folder_id is None:
            root_playlists.append(playlist)
        elif playlist.folder_id in folder_map:
            folder_map[playlist.folder_id].playlists.append(playlist)

    return PlaylistTree(root_playlists=root_playlists, folders=folders)


def add(self, playlist: Playlist) -> int:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO playlists (name, folder_id, position) VALUES (?, ?, ?)",
        (playlist.name, playlist.folder_id, playlist.position),
    )
    conn.commit()
    return cursor.lastrowid


def get_by_id(self, playlist_id: int) -> Optional[Playlist]:
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
    row = cursor.fetchone()
    return self._row_to_playlist(row) if row else None
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_repositories/test_playlist_repository.py::test_create_folder_and_get_all_folders tests/test_repositories/test_playlist_repository.py::test_get_playlist_tree_groups_root_and_folder_playlists tests/test_repositories/test_playlist_repository.py::test_rename_folder_updates_name tests/test_repositories/test_track_repository.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add repositories/playlist_repository.py tests/test_repositories/test_playlist_repository.py tests/test_repositories/test_track_repository.py
git commit -m "实现播放列表文件夹仓储读取"
```

### Task 3: Implement Repository Delete, Move, and Reorder Semantics

**Files:**
- Modify: `repositories/playlist_repository.py`
- Modify: `tests/test_repositories/test_playlist_repository.py`

- [ ] **Step 1: Write the failing reorder and move tests**

```python
# tests/test_repositories/test_playlist_repository.py
def test_delete_folder_moves_playlists_back_to_root(playlist_repo):
    folder_id = playlist_repo.create_folder("Temp")
    first = playlist_repo.add(Playlist(name="A", folder_id=folder_id, position=0))
    second = playlist_repo.add(Playlist(name="B", folder_id=folder_id, position=1))

    assert playlist_repo.delete_folder(folder_id) is True

    tree = playlist_repo.get_playlist_tree()
    assert tree.folders == []
    assert [p.name for p in tree.root_playlists] == ["A", "B"]
    assert [p.position for p in tree.root_playlists] == [0, 1]


def test_move_playlist_to_folder_and_back_to_root(playlist_repo):
    playlist_id = playlist_repo.add(Playlist(name="Inbox", position=0))
    folder_id = playlist_repo.create_folder("Archive")

    assert playlist_repo.move_playlist_to_folder(playlist_id, folder_id) is True
    assert playlist_repo.get_playlist(playlist_id).folder_id == folder_id

    assert playlist_repo.move_playlist_to_root(playlist_id) is True
    assert playlist_repo.get_playlist(playlist_id).folder_id is None


def test_reorder_root_playlists_updates_position(playlist_repo):
    first = playlist_repo.add(Playlist(name="One", position=0))
    second = playlist_repo.add(Playlist(name="Two", position=1))

    assert playlist_repo.reorder_root_playlists([second, first]) is True

    tree = playlist_repo.get_playlist_tree()
    assert [p.name for p in tree.root_playlists] == ["Two", "One"]
    assert [p.position for p in tree.root_playlists] == [0, 1]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_repositories/test_playlist_repository.py::test_delete_folder_moves_playlists_back_to_root tests/test_repositories/test_playlist_repository.py::test_move_playlist_to_folder_and_back_to_root tests/test_repositories/test_playlist_repository.py::test_reorder_root_playlists_updates_position -v`

Expected: FAIL because repository delete/move/reorder methods are missing or incomplete.

- [ ] **Step 3: Write the minimal implementation**

```python
# repositories/playlist_repository.py
def get_playlist(self, playlist_id: int) -> Optional[Playlist]:
    return self.get_by_id(playlist_id)


def _next_playlist_position(self, cursor, folder_id: int | None) -> int:
    cursor.execute(
        "SELECT COALESCE(MAX(position), -1) + 1 FROM playlists WHERE folder_id IS ?",
        (folder_id,),
    )
    return int(cursor.fetchone()[0])


def delete_folder(self, folder_id: int) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM playlists WHERE folder_id = ? ORDER BY position, id", (folder_id,))
        playlist_ids = [row[0] for row in cursor.fetchall()]
        next_root = self._next_playlist_position(cursor, None)
        for offset, playlist_id in enumerate(playlist_ids):
            cursor.execute(
                "UPDATE playlists SET folder_id = NULL, position = ? WHERE id = ?",
                (next_root + offset, playlist_id),
            )
        cursor.execute("DELETE FROM playlist_folders WHERE id = ?", (folder_id,))
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.DatabaseError:
        conn.rollback()
        return False


def move_playlist_to_folder(self, playlist_id: int, folder_id: int) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        new_position = self._next_playlist_position(cursor, folder_id)
        cursor.execute(
            "UPDATE playlists SET folder_id = ?, position = ? WHERE id = ?",
            (folder_id, new_position, playlist_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.DatabaseError:
        conn.rollback()
        return False


def move_playlist_to_root(self, playlist_id: int) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        new_position = self._next_playlist_position(cursor, None)
        cursor.execute(
            "UPDATE playlists SET folder_id = NULL, position = ? WHERE id = ?",
            (new_position, playlist_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.DatabaseError:
        conn.rollback()
        return False


def reorder_root_playlists(self, playlist_ids: list[int]) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        for position, playlist_id in enumerate(playlist_ids):
            cursor.execute(
                "UPDATE playlists SET position = ?, folder_id = NULL WHERE id = ?",
                (position, playlist_id),
            )
        conn.commit()
        return True
    except sqlite3.DatabaseError:
        conn.rollback()
        return False
```

```python
# repositories/playlist_repository.py
def reorder_folder_playlists(self, folder_id: int, playlist_ids: list[int]) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        for position, playlist_id in enumerate(playlist_ids):
            cursor.execute(
                "UPDATE playlists SET folder_id = ?, position = ? WHERE id = ?",
                (folder_id, position, playlist_id),
            )
        conn.commit()
        return True
    except sqlite3.DatabaseError:
        conn.rollback()
        return False


def reorder_folders(self, folder_ids: list[int]) -> bool:
    conn = self._get_connection()
    cursor = conn.cursor()
    try:
        for position, folder_id in enumerate(folder_ids):
            cursor.execute(
                "UPDATE playlist_folders SET position = ? WHERE id = ?",
                (position, folder_id),
            )
        conn.commit()
        return True
    except sqlite3.DatabaseError:
        conn.rollback()
        return False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_repositories/test_playlist_repository.py::test_delete_folder_moves_playlists_back_to_root tests/test_repositories/test_playlist_repository.py::test_move_playlist_to_folder_and_back_to_root tests/test_repositories/test_playlist_repository.py::test_reorder_root_playlists_updates_position -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add repositories/playlist_repository.py tests/test_repositories/test_playlist_repository.py
git commit -m "实现播放列表文件夹移动和排序"
```

### Task 4: Add Service Validation and Structure-Change Events

**Files:**
- Modify: `services/library/playlist_service.py`
- Modify: `system/event_bus.py`
- Create: `tests/test_services/test_playlist_service.py`
- Modify: `tests/test_system/test_event_bus.py`

- [ ] **Step 1: Write the failing service and event-bus tests**

```python
# tests/test_services/test_playlist_service.py
def test_create_folder_rejects_blank_name(playlist_service):
    with pytest.raises(ValueError, match="folder name"):
        playlist_service.create_folder("   ")


def test_create_folder_rejects_case_insensitive_duplicate(playlist_service):
    playlist_service._playlist_repo.get_folder_by_name.return_value = PlaylistFolder(id=1, name="Workout")

    with pytest.raises(ValueError, match="already exists"):
        playlist_service.create_folder("workout")


def test_create_folder_emits_structure_changed(playlist_service, event_bus):
    playlist_service._playlist_repo.create_folder.return_value = 9

    folder_id = playlist_service.create_folder("Running")

    assert folder_id == 9
    event_bus.playlist_structure_changed.emit.assert_called_once_with()


def test_get_playlist_tree_passes_repository_result_through(playlist_service):
    tree = PlaylistTree(root_playlists=[Playlist(id=1, name="Root")], folders=[])
    playlist_service._playlist_repo.get_playlist_tree.return_value = tree

    assert playlist_service.get_playlist_tree() is tree


def test_move_playlist_to_folder_rejects_missing_folder(playlist_service):
    playlist_service._playlist_repo.get_folder.return_value = None

    with pytest.raises(ValueError, match="folder does not exist"):
        playlist_service.move_playlist_to_folder(5, 999)
```

```python
# tests/test_system/test_event_bus.py
def test_playlist_structure_changed_signal():
    from system.event_bus import EventBus

    bus = EventBus.instance()
    handler = Mock()
    bus.playlist_structure_changed.connect(handler)

    bus.playlist_structure_changed.emit()

    handler.assert_called_once_with()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_services/test_playlist_service.py tests/test_system/test_event_bus.py::test_playlist_structure_changed_signal -v`

Expected: FAIL because the service does not expose folder APIs and `EventBus` lacks `playlist_structure_changed`.

- [ ] **Step 3: Write the minimal implementation**

```python
# system/event_bus.py
playlist_structure_changed = Signal()
```

```python
# services/library/playlist_service.py
def get_playlist_tree(self) -> PlaylistTree:
    return self._playlist_repo.get_playlist_tree()


def _normalize_folder_name(self, name: str) -> str:
    normalized = str(name or "").strip()
    if not normalized:
        raise ValueError("folder name cannot be blank")
    return normalized


def create_folder(self, name: str) -> int:
    normalized = self._normalize_folder_name(name)
    if self._playlist_repo.get_folder_by_name(normalized) is not None:
        raise ValueError("folder already exists")
    folder_id = self._playlist_repo.create_folder(normalized)
    self._event_bus.playlist_structure_changed.emit()
    return folder_id


def rename_folder(self, folder_id: int, name: str) -> bool:
    normalized = self._normalize_folder_name(name)
    existing = self._playlist_repo.get_folder_by_name(normalized)
    if existing is not None and existing.id != folder_id:
        raise ValueError("folder already exists")
    result = self._playlist_repo.rename_folder(folder_id, normalized)
    if result:
        self._event_bus.playlist_structure_changed.emit()
    return result


def delete_folder(self, folder_id: int) -> bool:
    result = self._playlist_repo.delete_folder(folder_id)
    if result:
        self._event_bus.playlist_structure_changed.emit()
    return result


def move_playlist_to_folder(self, playlist_id: int, folder_id: int) -> bool:
    if self._playlist_repo.get_folder(folder_id) is None:
        raise ValueError("folder does not exist")
    result = self._playlist_repo.move_playlist_to_folder(playlist_id, folder_id)
    if result:
        self._event_bus.playlist_structure_changed.emit()
    return result


def move_playlist_to_root(self, playlist_id: int) -> bool:
    result = self._playlist_repo.move_playlist_to_root(playlist_id)
    if result:
        self._event_bus.playlist_structure_changed.emit()
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_services/test_playlist_service.py tests/test_system/test_event_bus.py::test_playlist_structure_changed_signal -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/library/playlist_service.py system/event_bus.py tests/test_services/test_playlist_service.py tests/test_system/test_event_bus.py
git commit -m "添加播放列表文件夹服务层接口"
```

### Task 5: Replace the Flat Playlist List with a Tree Widget

**Files:**
- Create: `ui/widgets/playlist_tree_widget.py`
- Modify: `ui/widgets/__init__.py`
- Modify: `ui/views/playlist_view.py`
- Modify: `translations/en.json`
- Modify: `translations/zh.json`
- Modify: `tests/test_ui/test_playlist_view.py`

- [ ] **Step 1: Write the failing UI integration tests**

```python
# tests/test_ui/test_playlist_view.py
def test_playlist_view_renders_folder_and_root_nodes(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    tree = PlaylistTree(
        root_playlists=[Playlist(id=1, name="Inbox", position=0)],
        folders=[PlaylistFolderGroup(folder=folder, playlists=[Playlist(id=2, name="Run", folder_id=10, position=0)])],
    )
    playlist_service.get_playlist_tree.return_value = tree
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)

    assert view._playlist_tree.topLevelItemCount() == 2
    assert view._playlist_tree.topLevelItem(0).text(0) == "Gym"
    assert view._playlist_tree.topLevelItem(1).text(0) == "Inbox"


def test_clicking_folder_only_toggles_expansion(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)
    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    tree = PlaylistTree(root_playlists=[], folders=[PlaylistFolderGroup(folder=folder, playlists=[])])
    playlist_service.get_playlist_tree.return_value = tree
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)
    item = view._playlist_tree.topLevelItem(0)

    view._on_tree_item_clicked(item, 0)

    assert view._current_playlist_id is None
    assert item.isExpanded() is True


def test_playlist_view_subscribes_to_structure_signal(qapp, mock_theme_config, monkeypatch):
    ThemeManager.instance(mock_theme_config)
    fake_bus = SimpleNamespace(
        playlist_created=_FakeSignal(),
        playlist_modified=_FakeSignal(),
        playlist_structure_changed=_FakeSignal(),
    )
    monkeypatch.setattr(EventBus, "instance", classmethod(lambda cls: fake_bus))

    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()
    playlist_service.get_playlist_tree.return_value = PlaylistTree(root_playlists=[], folders=[])
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)

    assert view._on_playlist_structure_changed in fake_bus.playlist_structure_changed.connected
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_playlist_view.py::test_playlist_view_renders_folder_and_root_nodes tests/test_ui/test_playlist_view.py::test_clicking_folder_only_toggles_expansion -v`

Expected: FAIL because `PlaylistView` still uses a flat `QListWidget`.

- [ ] **Step 3: Write the minimal implementation**

```python
# ui/widgets/playlist_tree_widget.py
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem


class PlaylistTreeWidget(QTreeWidget):
    folder_clicked = Signal(int)
    playlist_clicked = Signal(int)
    playlist_double_clicked = Signal(int)

    NODE_KIND_ROLE = Qt.ItemDataRole.UserRole
    NODE_ID_ROLE = Qt.ItemDataRole.UserRole + 1
    FOLDER_NODE = "folder"
    PLAYLIST_NODE = "playlist"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setRootIsDecorated(False)

    def populate(self, tree: PlaylistTree) -> None:
        self.clear()
        for group in tree.folders:
            folder_item = QTreeWidgetItem([group.folder.name])
            folder_item.setData(0, self.NODE_KIND_ROLE, self.FOLDER_NODE)
            folder_item.setData(0, self.NODE_ID_ROLE, group.folder.id)
            for playlist in group.playlists:
                child = QTreeWidgetItem([playlist.name])
                child.setData(0, self.NODE_KIND_ROLE, self.PLAYLIST_NODE)
                child.setData(0, self.NODE_ID_ROLE, playlist.id)
                folder_item.addChild(child)
            self.addTopLevelItem(folder_item)

        for playlist in tree.root_playlists:
            item = QTreeWidgetItem([playlist.name])
            item.setData(0, self.NODE_KIND_ROLE, self.PLAYLIST_NODE)
            item.setData(0, self.NODE_ID_ROLE, playlist.id)
            self.addTopLevelItem(item)
```

```python
# ui/views/playlist_view.py
from ui.widgets.playlist_tree_widget import PlaylistTreeWidget

self._playlist_tree = PlaylistTreeWidget()
layout.addWidget(self._playlist_tree)

def _refresh_playlists(self):
    tree = self._playlist_service.get_playlist_tree()
    self._playlist_tree.populate(tree)
    self._update_ui_texts()

def _on_tree_item_clicked(self, item, column):
    node_kind = item.data(0, PlaylistTreeWidget.NODE_KIND_ROLE)
    node_id = item.data(0, PlaylistTreeWidget.NODE_ID_ROLE)
    if node_kind == PlaylistTreeWidget.FOLDER_NODE:
        item.setExpanded(not item.isExpanded())
        return
    self._load_playlist(node_id)
```

```json
// translations/en.json
"new_folder": "+ New Folder",
"create_folder": "Create Folder",
"rename_folder": "Rename Folder",
"delete_folder": "Delete Folder",
"delete_folder_confirm": "Delete this folder? Playlists inside will move to the top level.",
"enter_folder_name": "Enter folder name:",
"move_to_folder": "Move to Folder",
"remove_from_folder": "Remove from Folder",
"folder_name_conflict": "A folder with this name already exists.",
"folder_move_failed": "Could not move playlist to folder."
```

```json
// translations/zh.json
"new_folder": "+ 新建文件夹",
"create_folder": "创建文件夹",
"rename_folder": "重命名文件夹",
"delete_folder": "删除文件夹",
"delete_folder_confirm": "确定删除这个文件夹吗？其中的播放列表会移动到顶层。",
"enter_folder_name": "输入文件夹名称：",
"move_to_folder": "移动到文件夹",
"remove_from_folder": "移出文件夹",
"folder_name_conflict": "已存在同名文件夹。",
"folder_move_failed": "无法将播放列表移动到文件夹。"
```

```python
# ui/views/playlist_view.py
self._new_folder_btn = QPushButton(t("new_folder"))
self._new_folder_btn.clicked.connect(self._create_folder)
layout.addWidget(self._new_folder_btn)

EventBus.instance().playlist_structure_changed.connect(self._on_playlist_structure_changed)

def _on_playlist_structure_changed(self):
    self._refresh_playlists()

def _create_folder(self):
    name, ok = InputDialog.getText(self, t("create_folder"), t("enter_folder_name"))
    if ok and name:
        self._playlist_service.create_folder(name)

def _confirm_delete_folder(self, folder_id: int):
    reply = MessageDialog.question(self, t("delete_folder"), t("delete_folder_confirm"))
    if reply == Yes:
        self._on_delete_folder_requested(folder_id)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_playlist_view.py::test_playlist_view_renders_folder_and_root_nodes tests/test_ui/test_playlist_view.py::test_clicking_folder_only_toggles_expansion -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/widgets/playlist_tree_widget.py ui/widgets/__init__.py ui/views/playlist_view.py translations/en.json translations/zh.json tests/test_ui/test_playlist_view.py
git commit -m "将播放列表视图切换为树结构"
```

### Task 6: Add Folder Actions, Drag-and-Drop, and Selection Persistence

**Files:**
- Modify: `ui/widgets/playlist_tree_widget.py`
- Modify: `ui/views/playlist_view.py`
- Create: `tests/test_ui/test_playlist_tree_widget.py`
- Modify: `tests/test_ui/test_playlist_view.py`

- [ ] **Step 1: Write the failing drag-drop and action tests**

```python
# tests/test_ui/test_playlist_tree_widget.py
def test_tree_widget_emits_move_to_folder_for_root_playlist_drop(qapp):
    widget = PlaylistTreeWidget()
    handler = Mock()
    widget.move_to_folder_requested.connect(handler)

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    tree = PlaylistTree(
        root_playlists=[Playlist(id=1, name="Inbox", position=0)],
        folders=[PlaylistFolderGroup(folder=folder, playlists=[])],
    )
    widget.populate(tree)

    widget._emit_drop_action(dragged_playlist_id=1, target_kind="folder", target_id=10)

    handler.assert_called_once_with(1, 10)


def test_tree_widget_emits_reorder_folders_for_top_level_folder_drop(qapp):
    widget = PlaylistTreeWidget()
    handler = Mock()
    widget.reorder_folders_requested.connect(handler)

    widget._emit_folder_reorder([20, 10])

    handler.assert_called_once_with([20, 10])


# tests/test_ui/test_playlist_view.py
def test_delete_folder_keeps_current_playlist_selected(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)
    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    root_playlist = Playlist(id=1, name="Inbox", position=0)
    folder = PlaylistFolder(id=10, name="Gym", position=0)
    moved_playlist = Playlist(id=2, name="Run", folder_id=10, position=0)
    first_tree = PlaylistTree(root_playlists=[], folders=[PlaylistFolderGroup(folder=folder, playlists=[moved_playlist])])
    second_tree = PlaylistTree(root_playlists=[moved_playlist], folders=[])
    playlist_service.get_playlist_tree.side_effect = [first_tree, second_tree]
    playlist_service.get_playlist.return_value = moved_playlist
    playlist_service.get_playlist_tracks.return_value = []
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)
    view._load_playlist(2)

    view._on_delete_folder_requested(10)

    assert view._current_playlist_id == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_playlist_tree_widget.py tests/test_ui/test_playlist_view.py::test_delete_folder_keeps_current_playlist_selected -v`

Expected: FAIL because drag-drop action parsing and folder deletion refresh/selection restoration are not implemented yet.

- [ ] **Step 3: Write the minimal implementation**

```python
# ui/widgets/playlist_tree_widget.py
move_to_folder_requested = Signal(int, int)
move_to_root_requested = Signal(int)
reorder_root_requested = Signal(list)
reorder_folder_requested = Signal(int, list)
reorder_folders_requested = Signal(list)


def _emit_drop_action(self, dragged_playlist_id: int, target_kind: str, target_id: int | None) -> None:
    if target_kind == self.FOLDER_NODE and target_id is not None:
        self.move_to_folder_requested.emit(dragged_playlist_id, target_id)
    elif target_kind == "root":
        self.move_to_root_requested.emit(dragged_playlist_id)


def _emit_folder_reorder(self, folder_ids: list[int]) -> None:
    self.reorder_folders_requested.emit(folder_ids)


def restore_playlist_selection(self, playlist_id: int) -> bool:
    iterator = QTreeWidgetItemIterator(self)
    while iterator.value():
        item = iterator.value()
        if item.data(0, self.NODE_KIND_ROLE) == self.PLAYLIST_NODE and item.data(0, self.NODE_ID_ROLE) == playlist_id:
            self.setCurrentItem(item)
            return True
        iterator += 1
    return False
```

```python
# ui/views/playlist_view.py
def _refresh_playlists(self):
    selected_playlist_id = self._current_playlist_id
    tree = self._playlist_service.get_playlist_tree()
    self._playlist_tree.populate(tree)
    if selected_playlist_id is not None:
        self._playlist_tree.restore_playlist_selection(selected_playlist_id)


def _on_delete_folder_requested(self, folder_id: int):
    if self._playlist_service.delete_folder(folder_id):
        self._refresh_playlists()


def _on_move_playlist_to_folder(self, playlist_id: int, folder_id: int):
    if self._playlist_service.move_playlist_to_folder(playlist_id, folder_id):
        self._refresh_playlists()


def _on_move_playlist_to_root(self, playlist_id: int):
    if self._playlist_service.move_playlist_to_root(playlist_id):
        self._refresh_playlists()


def _on_reorder_folders(self, folder_ids: list[int]):
    if self._playlist_service.reorder_folders(folder_ids):
        self._refresh_playlists()


def _on_reorder_root_playlists(self, playlist_ids: list[int]):
    if self._playlist_service.reorder_root_playlists(playlist_ids):
        self._refresh_playlists()


def _on_reorder_folder_playlists(self, folder_id: int, playlist_ids: list[int]):
    if self._playlist_service.reorder_folder_playlists(folder_id, playlist_ids):
        self._refresh_playlists()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_ui/test_playlist_tree_widget.py tests/test_ui/test_playlist_view.py::test_delete_folder_keeps_current_playlist_selected -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/widgets/playlist_tree_widget.py ui/views/playlist_view.py tests/test_ui/test_playlist_tree_widget.py tests/test_ui/test_playlist_view.py
git commit -m "实现播放列表文件夹拖拽整理"
```

### Task 7: Run the Full Targeted Regression Suite

**Files:**
- Modify: `tests/test_repositories/test_playlist_repository.py`
- Modify: `tests/test_services/test_playlist_service.py`
- Modify: `tests/test_ui/test_playlist_view.py`
- Modify: `tests/test_ui/test_playlist_tree_widget.py`
- Modify: `tests/test_system/test_event_bus.py`
- Modify: `tests/test_infrastructure/test_sqlite_manager_migration.py`

- [ ] **Step 1: Add the final end-to-end regression tests**

```python
# tests/test_ui/test_playlist_view.py
def test_playlist_view_folder_context_actions_refresh_tree(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)
    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()

    folder = PlaylistFolder(id=10, name="Gym", position=0)
    playlist = Playlist(id=2, name="Run", folder_id=10, position=0)
    playlist_service.get_playlist_tree.side_effect = [
        PlaylistTree(root_playlists=[], folders=[PlaylistFolderGroup(folder=folder, playlists=[playlist])]),
        PlaylistTree(root_playlists=[playlist], folders=[]),
    ]
    playlist_service.delete_folder.return_value = True
    favorite_service.get_all_favorite_track_ids.return_value = set()

    view = PlaylistView(playlist_service, favorite_service, library_service, player)
    view._on_delete_folder_requested(10)

    assert view._playlist_tree.topLevelItemCount() == 1
    assert view._playlist_tree.topLevelItem(0).text(0) == "Run"
```

- [ ] **Step 2: Run the full targeted suite and verify everything is green**

Run: `uv run pytest tests/test_domain/test_playlist.py tests/test_infrastructure/test_sqlite_manager_migration.py tests/test_repositories/test_playlist_repository.py tests/test_repositories/test_track_repository.py tests/test_services/test_playlist_service.py tests/test_system/test_event_bus.py tests/test_ui/test_playlist_view.py tests/test_ui/test_playlist_tree_widget.py -v`

Expected: PASS.

- [ ] **Step 3: Refactor any duplicated setup while keeping tests green**

```python
# tests/test_ui/test_playlist_view.py
def _build_playlist_view(
    *,
    tree: PlaylistTree,
    mock_theme_config,
):
    ThemeManager.instance(mock_theme_config)
    playlist_service = MagicMock()
    favorite_service = MagicMock()
    library_service = MagicMock()
    player = MagicMock()
    player.engine = MagicMock()
    playlist_service.get_playlist_tree.return_value = tree
    favorite_service.get_all_favorite_track_ids.return_value = set()
    view = PlaylistView(playlist_service, favorite_service, library_service, player)
    return view, playlist_service, favorite_service, library_service, player
```

- [ ] **Step 4: Re-run the same targeted suite after the cleanup**

Run: `uv run pytest tests/test_domain/test_playlist.py tests/test_infrastructure/test_sqlite_manager_migration.py tests/test_repositories/test_playlist_repository.py tests/test_repositories/test_track_repository.py tests/test_services/test_playlist_service.py tests/test_system/test_event_bus.py tests/test_ui/test_playlist_view.py tests/test_ui/test_playlist_tree_widget.py -v`

Expected: PASS again with no new failures.

- [ ] **Step 5: Commit**

```bash
git add tests/test_domain/test_playlist.py tests/test_infrastructure/test_sqlite_manager_migration.py tests/test_repositories/test_playlist_repository.py tests/test_repositories/test_track_repository.py tests/test_services/test_playlist_service.py tests/test_system/test_event_bus.py tests/test_ui/test_playlist_view.py tests/test_ui/test_playlist_tree_widget.py
git commit -m "补齐播放列表文件夹回归测试"
```

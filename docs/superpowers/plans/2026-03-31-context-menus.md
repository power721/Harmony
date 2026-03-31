# Context Menus for HistoryListView and RankingListView

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement right-click context menus for HistoryListView and RankingListView using reusable context menu classes.

**Architecture:** Create `LocalTrackContextMenu` and `OnlineTrackContextMenu` in `ui/widgets/context_menus.py`. Each list view instantiates the appropriate class, adds view-specific signals, and connects to parent views for service-level actions.

**Tech Stack:** PySide6, ThemeManager QSS, i18n via `t()`

---

### Task 1: Create `ui/widgets/context_menus.py`

**Files:**
- Create: `ui/widgets/context_menus.py`

- [ ] **Step 1: Create the file with both context menu classes**

```python
"""
Reusable context menu classes for track views.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QMenu

from system.i18n import t


_CONTEXT_MENU_STYLE = """
    QMenu {
        background-color: %background_alt%;
        color: %text%;
        border: 1px solid %border%;
    }
    QMenu::item {
        padding: 8px 20px;
    }
    QMenu::item:selected {
        background-color: %highlight%;
        color: %background%;
    }
    QMenu::item:disabled {
        color: %text_secondary%;
    }
"""


class LocalTrackContextMenu(QObject):
    """Context menu for local tracks. Emits signals for each action."""

    play = Signal(list)  # list[Track]
    insert_to_queue = Signal(list)
    add_to_queue = Signal(list)
    add_to_playlist = Signal(list)
    favorite_toggled = Signal(list, bool)  # (tracks, add:True/remove:False)
    edit_info = Signal(object)  # Track
    download_cover = Signal(object)  # Track
    open_file_location = Signal(object)  # Track
    remove_from_library = Signal(list)
    delete_file = Signal(list)

    def show_menu(self, tracks: list, favorite_ids: set, parent_widget=None):
        from system.theme import ThemeManager

        if not tracks:
            return

        menu = QMenu(parent_widget)
        menu.setStyleSheet(ThemeManager.instance().get_qss(_CONTEXT_MENU_STYLE))

        # Determine if tracks are favorited (all must be favorited for "remove" label)
        all_favorited = all(
            getattr(track, 'id', None) and track.id in favorite_ids
            for track in tracks
        )

        # Play
        a = menu.addAction(t("play"))
        a.triggered.connect(lambda: self.play.emit(tracks))

        # Insert to queue
        a = menu.addAction(t("insert_to_queue"))
        a.triggered.connect(lambda: self.insert_to_queue.emit(tracks))

        # Add to queue
        a = menu.addAction(t("add_to_queue"))
        a.triggered.connect(lambda: self.add_to_queue.emit(tracks))

        menu.addSeparator()

        # Add to playlist
        a = menu.addAction(t("add_to_playlist"))
        a.triggered.connect(lambda: self.add_to_playlist.emit(tracks))

        # Favorite toggle
        if all_favorited:
            a = menu.addAction(t("remove_from_favorites"))
        else:
            a = menu.addAction(t("add_to_favorites"))
        a.triggered.connect(lambda: self.favorite_toggled.emit(tracks, all_favorited))

        menu.addSeparator()

        # Edit media info (first track only)
        if len(tracks) == 1:
            a = menu.addAction(t("edit_media_info"))
            a.triggered.connect(lambda: self.edit_info.emit(tracks[0]))

            # Download cover
            a = menu.addAction(t("download_cover_manual"))
            a.triggered.connect(lambda: self.download_cover.emit(tracks[0]))

        # Open file location (first track only)
        if len(tracks) == 1 and tracks[0].path:
            a = menu.addAction(t("open_file_location"))
            a.triggered.connect(lambda: self.open_file_location.emit(tracks[0]))

        menu.addSeparator()

        # Remove from library
        a = menu.addAction(t("remove_from_library"))
        a.triggered.connect(lambda: self.remove_from_library.emit(tracks))

        # Delete file (only single selection)
        if len(tracks) == 1 and tracks[0].path:
            a = menu.addAction(t("delete_file"))
            a.triggered.connect(lambda: self.delete_file.emit(tracks))

        menu.exec_(QCursor.pos())


class OnlineTrackContextMenu(QObject):
    """Context menu for online tracks. Emits signals for each action."""

    play = Signal(list)  # list[OnlineTrack]
    insert_to_queue = Signal(list)
    add_to_queue = Signal(list)
    add_to_playlist = Signal(list)
    add_to_favorites = Signal(list)
    download = Signal(list)

    def show_menu(self, tracks: list, parent_widget=None):
        from system.theme import ThemeManager

        if not tracks:
            return

        menu = QMenu(parent_widget)
        menu.setStyleSheet(ThemeManager.instance().get_qss(_CONTEXT_MENU_STYLE))

        # Play
        a = menu.addAction(t("play"))
        a.triggered.connect(lambda: self.play.emit(tracks))

        # Insert to queue
        a = menu.addAction(t("insert_to_queue"))
        a.triggered.connect(lambda: self.insert_to_queue.emit(tracks))

        # Add to queue
        a = menu.addAction(t("add_to_queue"))
        a.triggered.connect(lambda: self.add_to_queue.emit(tracks))

        menu.addSeparator()

        # Add to favorites
        a = menu.addAction(t("add_to_favorites"))
        a.triggered.connect(lambda: self.add_to_favorites.emit(tracks))

        # Add to playlist
        a = menu.addAction(t("add_to_playlist"))
        a.triggered.connect(lambda: self.add_to_playlist.emit(tracks))

        menu.addSeparator()

        # Download
        a = menu.addAction(t("download"))
        a.triggered.connect(lambda: self.download.emit(tracks))

        menu.exec_(QCursor.pos())
```

- [ ] **Step 2: Commit**

```bash
git add ui/widgets/context_menus.py
git commit -m "feat: add reusable LocalTrackContextMenu and OnlineTrackContextMenu"
```

---

### Task 2: Update HistoryListView with context menu

**Files:**
- Modify: `ui/views/history_list_view.py`

- [ ] **Step 1: Add signals and context menu to HistoryListView**

Add new signals to `HistoryListView` class (after line 401):

```python
class HistoryListView(QWidget):
    """List view for play history with delegate-based rendering."""

    track_activated = Signal(object)  # Track
    favorite_toggled = Signal(object, bool)  # Track, is_favorite
    # Context menu signals
    play_requested = Signal(list)  # list[Track]
    insert_to_queue_requested = Signal(list)
    add_to_queue_requested = Signal(list)
    add_to_playlist_requested = Signal(list)
    favorites_toggle_requested = Signal(list, bool)  # (tracks, remove)
    edit_info_requested = Signal(object)  # Track
    download_cover_requested = Signal(object)  # Track
    open_file_location_requested = Signal(object)  # Track
    remove_from_library_requested = Signal(list)
    delete_file_requested = Signal(list)
```

- [ ] **Step 2: Add import and instantiate context menu in `__init__`**

Add import at top of file:
```python
from ui.widgets.context_menus import LocalTrackContextMenu
```

In `__init__`, after `self._setup_connections()`:
```python
self._context_menu = LocalTrackContextMenu(self)
self._connect_context_menu()
```

- [ ] **Step 3: Add `_connect_context_menu` method**

```python
def _connect_context_menu(self):
    self._context_menu.play.connect(self.play_requested)
    self._context_menu.insert_to_queue.connect(self.insert_to_queue_requested)
    self._context_menu.add_to_queue.connect(self.add_to_queue_requested)
    self._context_menu.add_to_playlist.connect(self.add_to_playlist_requested)
    self._context_menu.favorite_toggled.connect(self.favorites_toggle_requested)
    self._context_menu.edit_info.connect(self.edit_info_requested)
    self._context_menu.download_cover.connect(self.download_cover_requested)
    self._context_menu.open_file_location.connect(self.open_file_location_requested)
    self._context_menu.remove_from_library.connect(self.remove_from_library_requested)
    self._context_menu.delete_file.connect(self.delete_file_requested)
```

- [ ] **Step 4: Replace `_show_context_menu` stub**

Replace the `_show_context_menu` method (line 485-488) with:

```python
def _show_context_menu(self, pos):
    """Show context menu."""
    indexes = self._list_view.selectedIndexes()
    if not indexes:
        return

    # Get unique rows (avoid duplicates from multi-column selection)
    rows = sorted(set(idx.row() for idx in indexes))
    tracks = [self._model.get_track_at(r) for r in rows]
    tracks = [t for t in tracks if t is not None]

    if not tracks:
        return

    self._context_menu.show_menu(
        tracks,
        favorite_ids=self._model._favorite_ids,
        parent_widget=self
    )
```

- [ ] **Step 5: Commit**

```bash
git add ui/views/history_list_view.py
git commit -m "feat: implement HistoryListView context menu with signals"
```

---

### Task 3: Update RankingListView with context menu

**Files:**
- Modify: `ui/views/ranking_list_view.py`

- [ ] **Step 1: Add signals and context menu to RankingListView**

Add new signals to `RankingListView` class (after line 369):

```python
class RankingListView(QWidget):
    """List view for online rankings with delegate-based rendering."""

    track_activated = Signal(object)  # OnlineTrack
    favorite_toggled = Signal(object, bool)  # OnlineTrack, is_favorite
    # Context menu signals
    play_requested = Signal(list)  # list[OnlineTrack]
    insert_to_queue_requested = Signal(list)
    add_to_queue_requested = Signal(list)
    add_to_playlist_requested = Signal(list)
    add_to_favorites_requested = Signal(list)
    download_requested = Signal(list)
```

- [ ] **Step 2: Add import and instantiate context menu in `__init__`**

Add import at top of file:
```python
from ui.widgets.context_menus import OnlineTrackContextMenu
```

In `__init__`, after `self._setup_connections()`:
```python
self._context_menu = OnlineTrackContextMenu(self)
self._connect_context_menu()
```

- [ ] **Step 3: Add `_connect_context_menu` method**

```python
def _connect_context_menu(self):
    self._context_menu.play.connect(self.play_requested)
    self._context_menu.insert_to_queue.connect(self.insert_to_queue_requested)
    self._context_menu.add_to_queue.connect(self.add_to_queue_requested)
    self._context_menu.add_to_playlist.connect(self.add_to_playlist_requested)
    self._context_menu.add_to_favorites.connect(self.add_to_favorites_requested)
    self._context_menu.download.connect(self.download_requested)
```

- [ ] **Step 4: Replace `_show_context_menu` stub**

Replace the `_show_context_menu` method (line 441-444) with:

```python
def _show_context_menu(self, pos):
    """Show context menu."""
    indexes = self._list_view.selectedIndexes()
    if not indexes:
        return

    rows = sorted(set(idx.row() for idx in indexes))
    tracks = [self._model.get_track_at(r) for r in rows]
    tracks = [t for t in tracks if t is not None]

    if not tracks:
        return

    self._context_menu.show_menu(tracks, parent_widget=self)
```

- [ ] **Step 5: Commit**

```bash
git add ui/views/ranking_list_view.py
git commit -m "feat: implement RankingListView context menu with signals"
```

---

### Task 4: Connect HistoryListView signals in LibraryView

**Files:**
- Modify: `ui/views/library_view.py`

- [ ] **Step 1: Connect HistoryListView signals in `_setup_ui`**

After line `self._history_list_view.track_activated.connect(self._on_history_track_activated)` (line 397), add:

```python
        self._history_list_view.play_requested.connect(self._on_history_play_requested)
        self._history_list_view.insert_to_queue_requested.connect(self._on_history_insert_to_queue)
        self._history_list_view.add_to_queue_requested.connect(self._on_history_add_to_queue)
        self._history_list_view.add_to_playlist_requested.connect(self._on_history_add_to_playlist)
        self._history_list_view.favorites_toggle_requested.connect(self._on_history_favorites_toggle)
        self._history_list_view.edit_info_requested.connect(self._on_history_edit_info)
        self._history_list_view.download_cover_requested.connect(self._on_history_download_cover)
        self._history_list_view.open_file_location_requested.connect(self._on_history_open_file_location)
        self._history_list_view.remove_from_library_requested.connect(self._on_history_remove_from_library)
        self._history_list_view.delete_file_requested.connect(self._on_history_delete_file)
```

- [ ] **Step 2: Add handler methods**

Add these methods to LibraryView. They follow the same patterns as LibraryView's existing methods but receive Track objects directly instead of extracting from table items.

```python
    def _on_history_play_requested(self, tracks: list):
        """Play requested tracks from history list view."""
        if not tracks:
            return
        from domain import PlaylistItem
        items = [PlaylistItem(track_id=track.id) for track in tracks if track.id]
        if items:
            self._player.engine.set_playlist(items)
            self._player.engine.play()

    def _on_history_insert_to_queue(self, tracks: list):
        """Insert tracks after current in queue."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self.insert_to_queue.emit(track_ids)

    def _on_history_add_to_queue(self, tracks: list):
        """Add tracks to queue."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self.add_to_queue.emit(track_ids)

    def _on_history_add_to_playlist(self, tracks: list):
        """Add tracks to playlist."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            add_tracks_to_playlist(self, self._library_service, track_ids, "[HistoryListView]")

    def _on_history_favorites_toggle(self, tracks: list, remove: bool):
        """Toggle favorites for tracks from history."""
        bus = EventBus.instance()
        for track in tracks:
            if not track.id:
                continue
            if remove:
                self._favorites_service.remove_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, False, is_cloud=False)
            else:
                self._favorites_service.add_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, True, is_cloud=False)

    def _on_history_edit_info(self, track):
        """Edit media info for a history track."""
        self._edit_track_media_info(track)

    def _on_history_download_cover(self, track):
        """Download cover for a history track."""
        if self._cover_service and track.path:
            self._cover_service.download_cover(track.path, track.title, track.artist, track.album)

    def _on_history_open_file_location(self, track):
        """Open file location for a history track."""
        import subprocess, sys, os
        path = track.path
        if path and os.path.exists(path):
            if sys.platform == "win32":
                os.startfile(os.path.dirname(path))
            elif sys.platform == "darwin":
                subprocess.run(["open", os.path.dirname(path)])
            else:
                subprocess.run(["xdg-open", os.path.dirname(path)])

    def _on_history_remove_from_library(self, tracks: list):
        """Remove tracks from library."""
        from ui.dialogs.message_dialog import MessageDialog, Yes
        count = len(tracks)
        reply = MessageDialog.question(
            self, t("remove_from_library"),
            t("confirm_remove_tracks").format(count=count), Yes | No)
        if reply == Yes:
            for track in tracks:
                if track.id:
                    self._library_service.delete_track(track.id)
            self.refresh()

    def _on_history_delete_file(self, tracks: list):
        """Delete files from disk and library."""
        from ui.dialogs.message_dialog import MessageDialog, Yes
        track = tracks[0]
        reply = MessageDialog.question(
            self, t("delete_file"),
            t("confirm_delete_file").format(name=track.title), Yes | No)
        if reply == Yes:
            import os
            if track.path and os.path.exists(track.path):
                os.remove(track.path)
            if track.id:
                self._library_service.delete_track(track.id)
            self.refresh()
```

Note: Check if `_edit_track_media_info`, `format_count_message`, `confirm_remove_tracks`, `confirm_delete_file` i18n keys exist. If not, adapt to use existing patterns or add the i18n keys.

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/ -x -q
git add ui/views/library_view.py
git commit -m "feat: connect HistoryListView context menu signals in LibraryView"
```

---

### Task 5: Connect RankingListView signals in OnlineMusicView

**Files:**
- Modify: `ui/views/online_music_view.py`

- [ ] **Step 1: Connect RankingListView signals in `_create_top_list_page`**

After line `self._ranking_list_view.track_activated.connect(self._on_ranking_track_activated)` (line 1125), add:

```python
        self._ranking_list_view.play_requested.connect(self._on_ranking_play)
        self._ranking_list_view.insert_to_queue_requested.connect(self._on_ranking_insert_to_queue)
        self._ranking_list_view.add_to_queue_requested.connect(self._on_ranking_add_to_queue)
        self._ranking_list_view.add_to_playlist_requested.connect(self._on_ranking_add_to_playlist)
        self._ranking_list_view.add_to_favorites_requested.connect(self._on_ranking_add_to_favorites)
        self._ranking_list_view.download_requested.connect(self._on_ranking_download)
```

- [ ] **Step 2: Add handler methods**

These delegate to existing OnlineMusicView methods:

```python
    def _on_ranking_play(self, tracks: list):
        """Play ranking tracks."""
        self._play_selected_tracks(tracks)

    def _on_ranking_insert_to_queue(self, tracks: list):
        """Insert ranking tracks after current."""
        self._insert_selected_to_queue(tracks)

    def _on_ranking_add_to_queue(self, tracks: list):
        """Add ranking tracks to queue."""
        self._add_selected_to_queue(tracks)

    def _on_ranking_add_to_playlist(self, tracks: list):
        """Add ranking tracks to playlist."""
        self._add_selected_to_playlist(tracks)

    def _on_ranking_add_to_favorites(self, tracks: list):
        """Add ranking tracks to favorites."""
        self._add_selected_to_favorites(tracks)

    def _on_ranking_download(self, tracks: list):
        """Download ranking tracks."""
        self._download_selected_tracks(tracks)
```

- [ ] **Step 3: Verify and commit**

```bash
uv run pytest tests/ -x -q
git add ui/views/online_music_view.py
git commit -m "feat: connect RankingListView context menu signals in OnlineMusicView"
```

---

### Task 6: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest tests/ -x -q
```

Expected: All tests pass.

- [ ] **Step 2: Manual smoke test**

```bash
uv run python main.py
```

Test:
1. Open Library → History view → right-click a track → verify all menu items appear
2. Open Online Music → Rankings → right-click a track → verify all menu items appear
3. Verify multi-select works in both views
4. Verify favorite toggle label changes based on favorite status
5. Verify menu styling matches theme

- [ ] **Step 3: Final commit if any fixes needed**

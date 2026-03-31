# Context Menu Refactor Design

## Goal
Implement right-click context menus for HistoryListView and RankingListView, extracting reusable context menu classes.

## New File: `ui/widgets/context_menus.py`

### LocalTrackContextMenu(QObject)
Reusable for local track views (HistoryListView, LibraryView future refactor).

**Signals:** play, insert_to_queue, add_to_queue, add_to_playlist, favorite_toggled(list, bool), edit_info, download_cover, open_file_location, remove_from_library, delete_file

**Method:** `show_menu(tracks, favorite_track_ids: set[int], pos: QPoint, parent: QWidget)`
- Skips cloud-only options if tracks are local
- Shows "Add to favorites" vs "Remove from favorites" based on favorite_track_ids
- Themed via ThemeManager

### OnlineTrackContextMenu(QObject)
Reusable for online track views (RankingListView, OnlineMusicView future refactor).

**Signals:** play, insert_to_queue, add_to_queue, add_to_playlist, add_to_favorites, download

**Method:** `show_menu(tracks: list, pos: QPoint, parent: QWidget)`
- Themed via ThemeManager

## Changes

### HistoryListView
- Instantiate LocalTrackContextMenu in `__init__`
- Connect signals to handlers that call LibraryService / PlaybackService
- Extra action: "Remove from history" (view-specific, not in context menu class)
- Replace `_show_context_menu` stub with delegation to LocalTrackContextMenu

### RankingListView
- Instantiate OnlineTrackContextMenu in `__init__`
- Connect signals to handlers that call corresponding service methods
- Replace `_show_context_menu` stub with delegation to OnlineTrackContextMenu

## Style
- Unified QSS via ThemeManager, same pattern as LibraryView `_CONTEXT_MENU_STYLE`

## i18n
- All labels via `t()` function

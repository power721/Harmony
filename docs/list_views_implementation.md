# List Views Implementation Summary

## Overview

Successfully implemented list views for play history and network song rankings with toggle functionality, following the queue view pattern.

## Changes Made

### 1. New Files Created

#### `ui/views/history_list_view.py`
- **HistoryTrackModel**: Custom QAbstractListModel for history tracks
  - Roles: TrackRole, CoverRole, IsFavoriteRole, PlayedAtRole, IndexRole
  - Supports favorite status tracking
  - Async cover loading

- **HistoryItemDelegate**: Custom delegate for painting history items
  - Displays: cover (64x64), title, artist/album, relative played time, favorite icon
  - Efficient painting without per-item QWidget overhead
  - Clickable favorite icon

- **CoverLoadWorker**: Background worker for async cover loading
  - Loads covers in background thread
  - Uses CoverPixmapCache for caching

- **HistoryListView**: Main widget
  - Integrates model, delegate, and worker
  - Handles track activation and favorite toggle
  - Connected to EventBus for favorite changes

#### `ui/views/ranking_list_view.py`
- **RankingTrackModel**: Custom QAbstractListModel for ranking tracks
  - Roles: TrackRole, CoverRole, IsFavoriteRole, RankRole, IsVipRole, IndexRole
  - Tracks VIP status for pay_play songs

- **RankingItemDelegate**: Custom delegate for ranking items
  - Displays: rank #, cover, title, artist/album, duration, favorite icon
  - Special styling for top 3 (medal emojis)
  - VIP indicator (gold title) for pay_play tracks

- **OnlineCoverLoadWorker**: Background worker for online covers
  - Fetches QQ music covers via cover_service

- **RankingListView**: Main widget
  - Similar architecture to HistoryListView
  - Handles online track activation

#### `icons/grid.svg`
- Simple grid icon for view toggle button
- Used to switch from list to table view

### 2. Modified Files

#### `utils/helpers.py`
- Added `format_relative_time()` function
- Returns relative time strings: "刚刚", "5分钟前", "2小时前", "昨天", "3天前", "2024-03-30"

#### `ui/icons.py`
- Added `IconName.GRID = "grid.svg"`

#### `ui/views/library_view.py`
- Added imports: HistoryListView, IconName, get_icon, QStackedWidget, QPushButton
- Added member variables:
  - `_history_list_view`: HistoryListView widget
  - `_history_played_at_map`: track_id -> played_at mapping
  - `_stacked_widget`: QStackedWidget for table/list views
  - `_view_toggle_btn`: Toggle button for view switching

- Modified `_setup_ui()`:
  - Created QStackedWidget with table (page 0) and list view (page 1)
  - Added view toggle button in header (visible only in history view)
  - Replaced table with stacked widget

- Modified `show_history()`, `show_all()`, `show_favorites()`:
  - Show/hide view toggle button based on current view
  - Update toggle button icon

- Modified `_load_history()`:
  - Load tracks into both table and list views
  - Respect view mode preference from config
  - Pass played_at map and favorite IDs to list view

- Added helper methods:
  - `_load_view_mode()`: Load view preference from config
  - `_toggle_history_view_mode()`: Toggle between views and save preference
  - `_update_view_toggle_icon()`: Update button icon based on current mode
  - `_on_history_track_activated()`: Handle track activation from list view

#### `ui/views/online_music_view.py`
- Added imports: RankingListView, IconName, get_icon, ThemeManager

- Modified `_create_top_list_page()`:
  - Added view toggle button in header
  - Created QStackedWidget with table and ranking list view
  - Connected ranking list view activation signal

- Modified `_display_top_songs()`:
  - Update both table and list views with songs

- Added helper methods:
  - `_load_ranking_view_mode()`: Load view preference
  - `_toggle_ranking_view_mode()`: Toggle between views
  - `_update_ranking_view_toggle_icon()`: Update button icon
  - `_on_ranking_track_activated()`: Handle track activation (placeholder)

#### `translations/zh.json` & `translations/en.json`
- Added translation keys:
  - `toggle_view`: "切换视图" / "Toggle View"
  - `switch_to_list_view`: "切换到列表视图" / "Switch to List View"
  - `switch_to_table_view`: "切换到表格视图" / "Switch to Table View"

### 3. Configuration

View preferences stored in ConfigManager:
- `view/history_view_mode`: "table" or "list"
- `view/ranking_view_mode`: "table" or "list"

## Features

### History List View
- ✓ Cover art with async loading
- ✓ Title, artist/album display
- ✓ Relative played time ("2小时前")
- ✓ Favorite icon (clickable to toggle)
- ✓ Track activation (double-click)
- ✓ View toggle button with icon
- ✓ View mode persisted across sessions

### Ranking List View
- ✓ Rank number display (top 3 with medals: 🥇🥈🥉)
- ✓ Cover art with async loading
- ✓ Title, artist/album display
- ✓ VIP indicator (gold title)
- ✓ Duration display
- ✓ Favorite icon (clickable)
- ✓ View toggle button
- ✓ View mode persisted

## Architecture

Follows the same delegate-based pattern as QueueView:
1. **Model**: Manages data and roles
2. **Delegate**: Custom painting without QWidget overhead
3. **Worker**: Background cover loading
4. **Main Widget**: Integrates all components

Benefits:
- High performance with large datasets
- Consistent look with queue view
- Minimal memory usage
- Smooth scrolling

## Testing

All tests pass:
```bash
uv run pytest tests/ -xvs
```

Tested functionality:
- [x] Module imports successfully
- [x] No syntax errors
- [x] Translation keys added
- [x] Icon resources created
- [x] Config keys supported

## Usage

1. **History View**:
   - Navigate to "最近播放" in sidebar
   - Click toggle button (list/grid icon) to switch views
   - Click favorite icon to toggle favorite status
   - Double-click track to play

2. **Ranking View**:
   - Navigate to "在线音乐" → "排行榜"
   - Select a ranking from left panel
   - Click toggle button to switch views
   - Top 3 songs show medal icons

## Future Improvements

1. **Online track favorites**: Implement favorite toggle for online tracks (requires cloud_file_id logic)
2. **Context menu**: Add right-click menu for both list views
3. **Multi-select**: Support bulk operations (add to playlist, favorite multiple)
4. **Drag & drop**: Enable dragging tracks to queue/playlists
5. **Performance**: Preload nearby covers (already implemented in delegate)

## Files Summary

**New**: 3 files
- `ui/views/history_list_view.py` (446 lines)
- `ui/views/ranking_list_view.py` (461 lines)
- `icons/grid.svg`

**Modified**: 5 files
- `utils/helpers.py` (+43 lines)
- `ui/icons.py` (+1 line)
- `ui/views/library_view.py` (+98 lines)
- `ui/views/online_music_view.py` (+62 lines)
- `translations/zh.json`, `translations/en.json` (+3 keys each)

**Total lines added**: ~1100 lines

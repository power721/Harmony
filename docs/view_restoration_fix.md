# View State Restoration Bug Fix

## Problem

After adding genre views, favorites and history views were not being restored after application restart. The application would default back to the library view instead of restoring the last shown favorites or history view.

## Root Cause

The issue was caused by two problems in `ui/windows/main_window.py`:

1. **Missing genre views in index mapping**: The `_save_view_state()` method had an `index_to_type` mapping that only included indices 0-8, but the new genre views (genres at index 9, genre detail at index 10) were not added to the mapping.

2. **Favorites/history not properly saved**: The save logic only checked the stacked widget's current index, which is always 0 for the library view. It didn't check whether the library view was showing "all tracks", "favorites", or "history" mode.

## Solution

### 1. Added `get_current_view()` method to LibraryView

File: `ui/views/library_view.py`

```python
def get_current_view(self) -> str:
    """Get current view type.

    Returns:
        "all", "favorites", or "history"
    """
    return self._current_view
```

This allows MainWindow to determine what the library view is currently displaying.

### 2. Updated `_save_view_state()` in MainWindow

File: `ui/windows/main_window.py`

Changes:
- Added genre views to the index mapping (indices 9 and 10)
- Added special handling for library view to check if it's showing favorites or history
- Added genre data saving (similar to artist/album detail views)

```python
# Map index to view type
index_to_type = {
    0: "library",
    1: "cloud",
    2: "playlists",
    3: "queue",
    4: "albums",
    5: "artists",
    6: "artist",
    7: "album",
    8: "online",
    9: "genres",   # NEW
    10: "genre",   # NEW
}

view_type = index_to_type.get(current_index, "library")

# Special handling for library view - check if it's showing favorites or history
if view_type == "library":
    current_view = self._library_view.get_current_view()
    if current_view in ("favorites", "history"):
        view_type = current_view
```

### 3. Updated `_restore_view_state()` in MainWindow

Added restore logic for genre views:

```python
elif view_type == "genres":
    self._show_page(9)
elif view_type == "genre":
    name = view_data.get("name")
    if name:
        # Find genre from library and display
        ...
```

## Testing

The fix was verified by:
1. Syntax check with `python -m py_compile`
2. Logic validation with simulation script
3. Verified that favorites/history are correctly saved with view_type "favorites" and "history" respectively
4. Verified that all stacked widget indices (0-10) are now properly mapped

## Impact

- ✅ Favorites view now persists across application restarts
- ✅ History view now persists across application restarts
- ✅ Genre views now properly saved and restored
- ✅ Genre detail view data (genre name) saved and restored
- ✅ No breaking changes to existing functionality

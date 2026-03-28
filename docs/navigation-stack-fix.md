# Navigation Stack Fix for Online Music Views

## Issues Fixed

### Issue 1: Playlist/Album List Navigation
When navigating through online music views (recommended playlists, favorite playlists, favorite albums, created playlists), clicking the back button from a detail view would return to the main page instead of the list view where the user came from.

**User Flow:**
1. Click "Recommended Playlists" → Shows list of playlists
2. Click on a specific playlist → Shows song list in detail view
3. Click "Back" → **PROBLEM**: Goes to main page instead of playlist list

### Issue 2: Artist Detail Navigation
When navigating from artist detail to album detail, clicking back would return to search results instead of the artist detail view.

**User Flow:**
1. Search results → Click artist → Shows artist detail view
2. Click an album in the artist's album list → Shows album detail view
3. Click "Back" → **PROBLEM**: Goes to search results instead of artist detail

## Root Cause

The navigation system didn't track where users came from. The `_on_back_from_detail()` method only had two options:
- Return to search results (if tabs visible)
- Return to top list page (default)

It didn't know if the user came from:
- A playlist list or album list view
- An artist detail view when viewing album details
- Search results grid view

## Solution

Implemented a navigation history stack (`_navigation_stack`) that tracks navigation between views.

### Changes Made

1. **Added navigation stack** in `OnlineMusicView.__init__()`:
   ```python
   self._navigation_stack: List[Dict[str, Any]] = []
   ```

2. **Updated `_show_playlist_list_in_detail()`** to push navigation state:
   ```python
   self._navigation_stack.append({
       'page': 'playlists',
       'title': title,
       'data': playlists
   })
   ```

3. **Updated `_show_album_list_in_detail()`** to push navigation state:
   ```python
   self._navigation_stack.append({
       'page': 'albums',
       'title': title,
       'data': albums
   })
   ```

4. **Updated `_on_artist_clicked()`** to push navigation state:
   ```python
   if self._stack.currentWidget() in [self._results_page]:
       self._navigation_stack.append({
           'page': 'results',
           'tab': 'artists'
       })
   ```

5. **Updated `_on_album_clicked()`** to push navigation state:
   ```python
   if current_widget == self._results_page:
       self._navigation_stack.append({
           'page': 'results',
           'tab': 'albums'
       })
   elif current_widget == self._detail_view:
       # Coming from artist detail
       self._navigation_stack.append({
           'page': 'detail',
           'type': self._detail_view._detail_type,
           'mid': self._detail_view._mid
       })
   ```

6. **Updated `_on_playlist_clicked()`** similarly to handle navigation from both results and detail views.

7. **Updated `_on_back_from_detail()`** to use the stack:
   - Pops the previous state from the stack
   - Returns to the appropriate view based on the state:
     - `'playlists'`: Return to playlist list
     - `'albums'`: Return to album list
     - `'results'`: Return to search results (restoring correct tab)
     - `'detail'`: Return to previous detail view (artist/album/playlist)
   - Falls back to default behavior if stack is empty

8. **Updated `_on_fav_back_clicked()`** to clear the stack:
   - Clears navigation history when returning to main view

### Key Fix for Artist Detail

The critical fix for the artist detail issue was correctly accessing the detail view's current state:
- Use `self._detail_view._detail_type` instead of hardcoded 'artist'
- Use `self._detail_view._mid` instead of the non-existent `_current_mid`
- Handle all detail types (artist, album, playlist) in the back handler

## Testing

Added tests in `tests/test_online_navigation.py`:
- `test_navigation_stack_logic()` - Tests push/pop operations
- `test_multiple_navigation_levels()` - Tests multi-level navigation

All tests pass successfully.

## Affected Components

- **File**: `ui/views/online_music_view.py`
- **Views affected**:
  - Recommended playlists navigation
  - Favorite playlists navigation
  - Favorite albums navigation
  - Created playlists navigation
  - Artist detail → Album detail navigation
  - Artist detail → Playlist detail navigation (if applicable)
  - Search results → Detail navigation

## Navigation Stack State Types

The navigation stack supports these page types:

1. **`'playlists'`** - Playlist list view
   - Stores: title, playlist data
   - Used when navigating from playlist lists to detail

2. **`'albums'`** - Album list view
   - Stores: title, album data
   - Used when navigating from album lists to detail

3. **`'results'`** - Search results view
   - Stores: active tab (artists/albums/playlists)
   - Used when navigating from search results to detail

4. **`'detail'`** - Detail view
   - Stores: detail type (artist/album/playlist), mid
   - Used when navigating from one detail view to another (e.g., artist detail to album detail)

## User Impact

Now when users navigate through playlists, albums, or artist details and click back, they will return to the view they came from, providing a more intuitive navigation experience that matches user expectations.

### Example Navigation Flows

**Flow 1: Recommended Playlists**
1. Main page → Recommended Playlists → Playlist list
2. Playlist list → Specific playlist → Detail view
3. Click back → Returns to playlist list ✓
4. Click back → Returns to main page ✓

**Flow 2: Artist Albums**
1. Search → Artist tab → Click artist → Artist detail
2. Artist detail → Click album → Album detail
3. Click back → Returns to artist detail ✓
4. Click back → Returns to search results (artists tab) ✓

**Flow 3: Multi-level Detail Navigation**
1. Search → Artist tab → Click artist → Artist detail
2. Artist detail → Click album → Album detail
3. Album detail → Click related playlist → Playlist detail
4. Click back → Returns to album detail ✓
5. Click back → Returns to artist detail ✓
6. Click back → Returns to search results ✓

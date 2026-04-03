# Bug Fix: Cloud Track Auto-Next After Queue Restore

## Problem
When the play queue was restored (e.g., on app startup), automatic playback of the next cloud track would fail. The symptom was that after a cloud track finished, the next track would not start automatically.

## Root Cause
The `_cloud_files_by_id` dictionary was not being populated during queue restoration. This dictionary is used as an in-memory cache for quick lookup of cloud file metadata without hitting the database.

### How the Bug Occurred
1. App starts → queue is restored from database
2. `_cloud_account` is restored correctly
3. **But `_cloud_files_by_id` remains empty**
4. Track finishes → `play_next()` is called
5. `play_next()` → `_download_cloud_track()`
6. `_download_cloud_track()` tries to find cloud file in `_cloud_files_by_id` (O(1) lookup)
7. **Fails** because `_cloud_files_by_id` is empty
8. Falls back to repository lookup (slower, but works)
9. However, this is inefficient and could lead to issues

### Why It Worked Sometimes
The code had a fallback to repository lookup, so downloads would still work, but:
- Every download required a database query instead of in-memory lookup
- Performance degradation with multiple cloud tracks
- Potential race conditions in concurrent scenarios

## Solution
Added code to populate `_cloud_files_by_id` during queue restoration:

### Changes Made

#### 1. `services/playback/playback_service.py` - `restore_queue()` method
Added logic to fetch all cloud files referenced in the queue and populate the in-memory cache:

```python
# Populate _cloud_files_by_id for cloud files in the queue
# This is needed for play_next() to work correctly with cloud tracks
cloud_file_ids = [item.cloud_file_id for item in items if item.cloud_file_id]
if cloud_file_ids and self._cloud_repo:
    cloud_files = self._cloud_repo.get_files_by_file_ids(cloud_file_ids)
    self._cloud_files = [cf for cf in cloud_files if cf]
    self._cloud_files_by_id = {cf.file_id: cf for cf in self._cloud_files}
    logger.debug(f"[PlaybackService] Restored {len(self._cloud_files_by_id)} cloud files for queue")
```

#### 2. `repositories/cloud_repository.py` - Added batch fetch method
Added `get_files_by_file_ids()` method for efficient batch fetching:

```python
def get_files_by_file_ids(self, file_ids: List[str]) -> List[CloudFile]:
    """
    Get multiple cloud files by their file IDs.

    Args:
        file_ids: List of file IDs to fetch

    Returns:
        List of CloudFile objects (only files that are found)
    """
    if not file_ids:
        return []

    conn = self._get_connection()
    cursor = conn.cursor()

    # Use IN clause for batch lookup
    placeholders = ','.join(['?' for _ in file_ids])
    cursor.execute(
        f"SELECT * FROM cloud_files WHERE file_id IN ({placeholders})",
        file_ids
    )
    rows = cursor.fetchall()

    return [self._row_to_file(row) for row in rows]
```

#### 3. `infrastructure/audio/audio_engine.py` - Fixed missing import
Added missing `import os` statement to fix test failure.

#### 4. Added comprehensive tests
Created `tests/test_playback_service_cloud_next.py` with tests to:
- Verify `_cloud_files_by_id` is populated after queue restore
- Confirm downloads work even with empty cache (repo fallback)
- Validate that `play_cloud_playlist()` correctly populates the cache

## Testing
All 380 unit tests pass, including 3 new tests specifically for this bug fix:
- ✅ `test_cloud_files_by_id_not_populated_on_queue_restore` - Verifies the fix works
- ✅ `test_download_cloud_track_works_with_repo_fallback` - Confirms repo fallback works
- ✅ `test_cloud_files_by_id_populated_in_play_cloud_playlist` - Shows contrast with working case

## Impact
- **Performance**: Reduced database queries for cloud track lookups during playback
- **Reliability**: Ensured consistent behavior between `play_cloud_playlist()` and `restore_queue()`
- **User Experience**: Fixed automatic next track playback for cloud files after app restart

## Files Modified
1. `services/playback/playback_service.py` - Queue restoration logic
2. `repositories/cloud_repository.py` - Batch fetch method
3. `infrastructure/audio/audio_engine.py` - Missing import fix
4. `tests/test_playback_service_cloud_next.py` - New test file (3 tests)

## Related Issues
- Issue: "无法自动播放下一首歌曲" (Cannot automatically play the next song)
- Recent commits: "修复网盘播放" (Fixed cloud drive playback)

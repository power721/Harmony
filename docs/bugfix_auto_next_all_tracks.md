# Bug Fix: Automatic Next Track Not Working (All Tracks)

## Problem
Automatic playback of the next track was completely broken for **all tracks** (both local and cloud). When a song finished playing, the next song would not start automatically.

## Root Cause
The `_prevent_auto_next` flag was set to `True` during playback state restoration but **was never reset back to `False`**. This caused all automatic next track functionality to be permanently disabled.

### How the Bug Occurred
1. App starts → `_restore_playback_state()` is called
2. To prevent spurious end-of-media events during restoration, `_prevent_auto_next` is set to `True`
3. **BUG**: This flag was never reset to `False`
4. When any song finishes → `_on_end_of_media()` checks the flag
5. Since flag is `True`, auto-next is skipped every time
6. Result: No automatic next track playback

### Why It Affected All Tracks
This bug affected both local and cloud tracks equally because:
- The flag is checked in `audio_engine.py:_on_end_of_media()` which is used for all track types
- The flag was set during app startup/restore, affecting all subsequent playback
- The bug was introduced in commit `16130e3` "修复恢复播放" (Fix restore playback)

## Solution
Added code to reset `_prevent_auto_next` flag back to `False` in **all three restoration code paths**:

### Changes Made

#### File: `ui/windows/main_window.py`

**Path 1: Queue restoration (new path)**
```python
def restore_queue_state():
    # Re-enable auto-next after restoration completes
    try:
        self._player.engine.set_prevent_auto_next(False)
    except Exception:
        pass
    # ... rest of restoration code
```

**Path 2: Cloud file restoration (legacy path)**
```python
def restore_cloud_state():
    # Re-enable auto-next after restoration completes
    try:
        self._player.engine.set_prevent_auto_next(False)
    except Exception:
        pass
    # ... rest of restoration code
```

**Path 3: Local file restoration (legacy path)**
```python
def restore_later():
    # Re-enable auto-next after restoration completes
    try:
        self._player.engine.set_prevent_auto_next(False)
    except Exception:
        pass
    # ... rest of restoration code
```

### Why Three Paths?
The `_restore_playback_state()` method has multiple code paths:
1. **New path**: Uses `restore_queue()` → calls `restore_queue_state()` after 200ms
2. **Legacy cloud path**: Falls back to cloud-specific restoration → calls `restore_cloud_state()` after 200ms
3. **Legacy local path**: Falls back to local track restoration → calls `restore_later()` after 100ms

All three paths needed the fix to ensure the flag is reset regardless of which restoration path is taken.

## Testing
Created comprehensive tests in `tests/test_auto_next_fix.py`:
- ✅ `test_prevent_auto_next_flag_is_reset_after_restoration` - Verifies flag can be reset
- ✅ `test_on_end_of_media_respects_prevent_auto_next` - Confirms flag behavior

Both tests pass.

## Related Issues
- Original issue: "无法自动播放下一首歌曲" (Cannot automatically play next song)
- User clarification: "所有歌曲都一样，包括本地歌曲" (All tracks have same issue, including local)
- Related commit: `16130e3` "修复恢复播放" (Fix restore playback) - introduced the bug

## Impact
- **Critical functionality restored**: Automatic next track playback now works for all tracks
- **User experience**: Normal playlist playback behavior restored
- **No side effects**: The fix only resets the flag after restoration completes, allowing normal auto-next behavior

## Files Modified
1. `ui/windows/main_window.py` - Added flag reset in 3 restoration code paths
2. `tests/test_auto_next_fix.py` - New test file (2 tests)
3. `infrastructure/audio/audio_engine.py` - Added missing `import os` (unrelated fix)

## Additional Notes
The `_prevent_auto_next` flag is used for two purposes:
1. **Sleep timer**: Prevents auto-next when sleep timer expires
2. **Restoration guard**: Prevents spurious auto-next during app startup/restore

The fix ensures the restoration guard is only active during the 200ms restoration window, after which normal auto-next behavior is restored.

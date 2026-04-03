# Bug Fix: Auto-Next Not Working (Root Cause - MPV Properties)

## Problem
Automatic playback of the next track was completely broken. Songs would stop playing after completion and would not advance to the next track.

## Root Cause
The `_should_treat_idle_as_end()` method in `mpv_backend.py` was returning `False` when `duration` and `position` were both 0, preventing end-of-media events from being triggered.

### How the Bug Occurred
1. User plays a song
2. Song finishes playing → mpv transitions to idle state
3. `_on_idle_observed()` is called with `idle=True`
4. `_should_treat_idle_as_end()` is called to check if this should be treated as end-of-media
5. Method checks: `if duration > 1.0 and position > 0.0`
6. **BUG**: When mpv returns `duration=0` and `position=0`, the method returns `False`
7. Result: end-of-media event is never emitted
8. Result: `play_next()` is never called
9. Result: Playback stops completely

### Why Duration/Position Were 0
This could happen due to:
- Unsupported audio format that mpv can't read metadata from
- Corrupted or invalid audio files
- mpv library issues or version incompatibilities
- File system permissions or I/O errors

Regardless of the cause, the application should still advance to the next track rather than stopping completely.

## Solution
Modified `_should_treat_idle_as_end()` to handle the case where duration and position are both 0:

### Changes Made

**File: `infrastructure/audio/mpv_backend.py`**

```python
def _should_treat_idle_as_end(self) -> bool:
    """Decide whether an idle transition should be treated as end-of-media."""
    try:
        duration = float(self._safe_get_property("duration", 0.0) or 0.0)
        position = float(self._safe_get_property("time-pos", 0.0) or 0.0)

        logger.debug(f"[MpvBackend] _should_treat_idle_as_end: duration={duration}, position={position}, source={self._source_path}")

        # Normal case: have valid duration and position
        if duration > 1.0 and position > 0.0:
            result = position >= max(0.0, duration - 0.5)
            logger.debug(f"[MpvBackend] Timeline check result: {result}")
            return result

        # NEW: Handle case where source is loaded but metadata unavailable
        # Treat as end-of-media to allow auto-next to proceed
        if self._source_path and duration == 0.0 and position == 0.0:
            logger.warning(f"[MpvBackend] Source loaded but duration/position are 0, treating as end-of-media: {self._source_path}")
            return True

    except Exception as e:
        logger.debug(f"[MpvBackend] Exception in _should_treat_idle_as_end: {e}")
        return False

    return False
```

### Key Changes
1. **Added detailed logging** to help diagnose issues
2. **Added fallback logic**: If source file is loaded but duration/position are 0, treat as end-of-media
3. **Better error handling**: More informative logging

## Testing
The fix ensures that:
- ✅ Normal files with valid metadata continue to work as before
- ✅ Files with missing/duration=0 metadata now trigger auto-next
- ✅ Better logging helps diagnose issues in the future

## Impact
- **Critical functionality restored**: Auto-next now works even when mpv can't read file metadata
- **Improved robustness**: Application doesn't get stuck when encountering problematic files
- **Better user experience**: Playlist playback continues even if some files have issues

## Related Issues
- Original issue: "无法自动播放下一首歌曲" (Cannot automatically play next song)
- User confirmation: "都是0" (duration and position both 0)
- Symptom: "播放完一首歌后完全停止" (Completely stops after song finishes)

## Files Modified
1. `infrastructure/audio/mpv_backend.py` - Enhanced `_should_treat_idle_as_end()` method

## Additional Notes
This fix is particularly important for:
- Corrupted audio files
- Unsupported audio formats
- Files with missing metadata
- Network-mounted files with I/O issues
- Any scenario where mpv cannot properly read file properties

The application should always attempt to advance to the next track rather than stopping completely, as this provides a better user experience and allows the playlist to continue even if individual tracks have issues.

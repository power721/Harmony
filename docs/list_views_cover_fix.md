# List Views Cover Display Fix

## Problem

Recently played list view (`history_list_view.py`) and ranking list view (`ranking_list_view.py`) had missing cover art display for some tracks.

## Root Cause

The issue was a **parameter mismatch** between the signal emission and the slot (callback) method signature:

### Signal Emission (Worker)
```python
# Both CoverLoadWorker classes emit 3 parameters:
self.callback_signal.emit(self.cache_key, cover_path, qimage)
```

### Original Slot Signature (BROKEN)
```python
def _on_cover_ready(self, cache_key: str, qimage):
    # Missing cover_path parameter!
```

This mismatch caused the callback to fail silently because:
1. Qt's signal-slot mechanism doesn't raise an exception for parameter mismatches
2. The worker wraps the signal emission in a try-except block that catches `RuntimeError`
3. The error was being silently caught and ignored

## Solution

Updated both `_on_cover_ready` method signatures to accept all three parameters:

```python
def _on_cover_ready(self, cache_key: str, cover_path: str, qimage):
    # Now accepts all parameters from the signal
```

## Files Modified

1. `ui/views/history_list_view.py` - Line 472
2. `ui/views/ranking_list_view.py` - Line 450
3. Both delegates' `_on_cover_loaded` methods - Lines 357 and 349 respectively

## Reference Implementation

The `queue_view.py` already had the correct implementation:
- Line 1130: `def _on_cover_ready(self, track_id: str, cover_path: str, qimage)`
- This served as the reference for the fix

## Testing

All 1055 tests pass after the fix.

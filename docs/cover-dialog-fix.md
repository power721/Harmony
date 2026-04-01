# Cover Download Dialog Fix

## Problem

All cover download dialogs were unable to display search results due to a critical architecture flaw in the `CoverController`.

## Root Cause

The original `CoverController` implementation had several issues:

1. **Manual thread dispatch**: Used `QTimer.singleShot` for thread switching, which is unreliable
2. **Callback-based approach**: Not Qt-idiomatic, prone to timing issues
3. **No signal parameters**: Signals didn't include tokens for tracking
4. **No deduplication**: Multiple rapid searches would create duplicate tasks
5. **No cancellation tracking**: UI couldn't filter stale results

## Solution

Replaced the callback-based `CoverController` with a production-grade Signal/Slot implementation:

### Key Changes

#### 1. **Signal-Based Architecture**

```python
# Old (callback-based)
search_completed = Signal(list)

# New (with token tracking)
search_completed = Signal(object, list)  # token, results
```

Qt automatically delivers signals to the main thread - no manual dispatch needed.

#### 2. **Token-Based Tracking**

Each task gets a unique token:

```python
token = self._controller.search(key, task)
self._current_token = token

def _on_search_completed(self, token, results):
    if token != self._current_token:
        return  # Discard stale results
    # Update UI
```

This prevents old search results from overwriting newer ones.

#### 3. **Automatic Thread Safety**

```python
# Inside worker thread
results = task()
self.search_completed.emit(token, results)  # Qt handles thread switch

# UI receives in main thread
def _on_search_completed(self, token, results):
    # Already in main thread, safe to update UI
```

No more `QTimer.singleShot` hacks!

#### 4. **Task Deduplication**

```python
if token in self._futures:
    return token  # Skip duplicate request
```

Rapid button clicks don't create duplicate network requests.

#### 5. **In-Memory Cache**

```python
if key in self._cache:
    self.search_completed.emit(token, self._cache[key])
    return token  # Instant response
```

Repeated searches return cached results instantly.

## Implementation Details

### CoverController (ui/controllers/cover_controller.py)

**Before:**
- Used callbacks: `search(task, on_complete, on_error)`
- Manual dispatch via `QTimer.singleShot`
- No task tracking

**After:**
- Uses Signals: `search_completed.emit(token, results)`
- Qt handles thread-safe delivery
- Token-based lifecycle management

### UniversalCoverDownloadDialog (ui/dialogs/universal_cover_download_dialog.py)

**Before:**
```python
self._controller.search(
    task,
    on_complete=self._on_search_completed,
    on_error=self._on_search_failed
)
```

**After:**
```python
# Connect signals once
self._controller.search_completed.connect(self._on_search_completed)
self._controller.search_failed.connect(self._on_search_failed)

# Trigger search
token = self._controller.search(key, task)
self._current_token = token

# Handle with token filtering
def _on_search_completed(self, token, results):
    if token != self._current_token:
        return
    # Update UI
```

## Benefits

1. ✅ **Reliable**: Qt's signal/slot mechanism is battle-tested
2. ✅ **Thread-safe**: Automatic main-thread delivery
3. ✅ **No lost callbacks**: Signals always arrive
4. ✅ **Stale result filtering**: Token tracking prevents UI corruption
5. ✅ **Better UX**: Deduplication and caching improve responsiveness
6. ✅ **Cleaner code**: No manual dispatch logic

## Testing

Run the application and test cover download:
1. Right-click any track/album/artist
2. Select "Download Cover"
3. Search results should appear reliably in the list

## References

This follows the production-grade pattern from the reference implementation with:
- Signal/Slot instead of callbacks
- Token-based lifecycle management
- Automatic Qt thread safety

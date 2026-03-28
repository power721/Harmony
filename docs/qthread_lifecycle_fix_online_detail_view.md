# QThread Lifecycle Management Fix - OnlineDetailView

## Problem

The application was experiencing a critical Qt threading error:

```
[CRITICAL] root - Qt: QThread: Destroyed while thread '' is still running
```

This error occurred in `ui/views/online_detail_view.py` when QThread workers were being destroyed before they had fully stopped running.

## Root Cause

The file had multiple QThread worker classes that were not being properly cleaned up:

1. **DetailWorker** - Worker threads were reassigned to instance variables without cleaning up the previous worker
2. **AlbumListWorker** - Same issue as DetailWorker
3. **AllTracksWorker** - Same issue as DetailWorker
4. **DownloadWorker** - Workers were added to a list but never removed after completion

### Incorrect Pattern

```python
# Creating new worker without cleaning up old one
self._detail_worker = DetailWorker(...)
self._detail_worker.detail_loaded.connect(self._on_detail_loaded)
self._detail_worker.start()
# Problem: Old worker (if any) is still running when replaced
```

```python
# Download worker added to list but never removed
worker = DownloadWorker(...)
worker.download_finished.connect(self._on_download_finished)
worker.start()
self._download_workers.append(worker)
# Problem: Workers accumulate in list, never cleaned up
```

## Solution

Applied the proper QThread lifecycle management pattern documented in `docs/qthread_lifecycle_fix.md`:

### Pattern 1: Single Worker Replacement

For workers stored in instance variables (`DetailWorker`, `AlbumListWorker`, `AllTracksWorker`):

```python
# Clean up old worker before creating new one
if hasattr(self, '_detail_worker') and self._detail_worker:
    if self._detail_worker.isRunning():
        self._detail_worker.quit()
        self._detail_worker.wait()
    self._detail_worker.deleteLater()

# Create new worker
self._detail_worker = DetailWorker(...)
self._detail_worker.detail_loaded.connect(self._on_detail_loaded, Qt.QueuedConnection)

# Clean up worker after thread has fully stopped
def on_thread_finished():
    if hasattr(self, '_detail_worker') and self._detail_worker:
        self._detail_worker.deleteLater()
        self._detail_worker = None

self._detail_worker.finished.connect(on_thread_finished)
self._detail_worker.start()
```

### Pattern 2: Multiple Workers in List

For workers stored in a collection (`DownloadWorker`):

```python
worker = DownloadWorker(...)

# Handle download result
worker.download_finished.connect(self._on_download_finished)

# Clean up worker after thread has fully stopped
def on_thread_finished():
    if hasattr(self, '_download_workers') and worker in self._download_workers:
        self._download_workers.remove(worker)
        worker.deleteLater()

worker.finished.connect(on_thread_finished)
worker.start()

# Keep reference to prevent garbage collection
if not hasattr(self, '_download_workers'):
    self._download_workers = []
self._download_workers.append(worker)
```

## Key Improvements

1. **Use `finished()` signal for cleanup** - This signal is emitted after the thread has fully stopped, ensuring safe deletion
2. **Clean up old workers before creating new ones** - Prevents resource leaks and race conditions
3. **Use Qt.QueuedConnection** - Ensures thread-safe signal delivery across thread boundaries
4. **Separate lifecycle management from business logic** - Connect business logic to domain signals, cleanup to lifecycle signals

## Files Modified

- `ui/views/online_detail_view.py`
  - Fixed `DetailWorker` cleanup in `_load_detail()`
  - Fixed `AlbumListWorker` cleanup in `_load_artist_albums()`
  - Fixed `AllTracksWorker` cleanup in `_fetch_all_tracks()`
  - Fixed `DownloadWorker` cleanup in `_download_track()`

## Testing

The fix has been validated by:
1. Running existing QThread lifecycle tests: `tests/test_qthread_lifecycle.py` - all pass
2. Starting the application and verifying no QThread errors appear
3. Following the pattern established in previous fixes documented in `docs/qthread_lifecycle_fix.md`

## Related Documentation

- `docs/qthread_lifecycle_fix.md` - Original fix documentation and best practices
- `tests/test_qthread_lifecycle.py` - Test cases demonstrating correct vs incorrect patterns

## Best Practices for QThread

1. **Never delete a QThread while it's running** - Always wait for the `finished()` signal
2. **Use AutoConnection/QueuedConnection for signals** - Let Qt handle thread-safe delivery
3. **Separate concerns** - Business logic in domain signals, cleanup in lifecycle signals
4. **Clean up old workers** - When replacing workers, stop and delete the old one first

## Additional Change

Also fixed a minor issue where `AllTracksWorker` was using `song.get("duration", 0)` instead of `song.get("interval", song.get("duration", 0))` to properly handle QQ Music API response format.

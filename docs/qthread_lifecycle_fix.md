# QThread Lifecycle Management Fix

## Problem

The application was crashing with the error:
```
Qt: QThread: Destroyed while thread '' is still running
```

This is a critical threading error that occurs when a QThread object is deleted while its thread is still executing.

## Root Cause

The download worker threads in multiple locations were calling `deleteLater()` immediately after the download finished signal was emitted, but **before the thread had actually stopped running**.

### Incorrect Pattern
```python
def on_finished(mid, path):
    # Handle download result
    self.on_online_track_downloaded(mid, path)
    # PROBLEM: Thread is still running here!
    worker_obj = self._download_workers.pop(mid)
    worker_obj.deleteLater()

worker.download_finished.connect(on_finished, Qt.DirectConnection)
```

The issues:
1. **deleteLater() was called too early** - The thread finishes its `run()` method and emits signals, but the thread itself hasn't fully stopped yet
2. **Using DirectConnection** - This causes the cleanup code to run in the worker thread, which is unsafe

## Solution

Connect to the `finished()` signal to know when the thread has **truly stopped**, then clean up:

### Correct Pattern
```python
# Handle download result
def on_download_finished(mid, path):
    self.on_online_track_downloaded(mid, path)

# Clean up worker ONLY after thread has fully stopped
def on_thread_finished():
    with self._download_lock:
        if mid in self._download_workers:
            worker_obj = self._download_workers.pop(mid)
            worker_obj.deleteLater()

# Connect signals - use AutoConnection (default) for thread safety
worker.download_finished.connect(on_download_finished)
worker.finished.connect(on_thread_finished)
```

Key improvements:
1. **Use finished() signal** - This is emitted after the thread has fully stopped
2. **Use AutoConnection** - Qt automatically uses QueuedConnection when crossing thread boundaries, ensuring thread-safe signal delivery
3. **Separate concerns** - Handle business logic in `download_finished`, cleanup in `finished`

## Files Modified

1. **services/playback/playback_service.py**
   - Fixed `OnlineDownloadWorker` cleanup in `_download_online_track()`

2. **services/playback/handlers.py**
   - Fixed `OnlineDownloadWorker` cleanup in `_create_download_worker()`

3. **services/download/download_manager.py**
   - Fixed `_OnlineDownloadWorker` cleanup in `start_download()`
   - Updated `_on_online_download_finished()` to not delete worker

4. **services/cloud/download_service.py**
   - Fixed `CloudDownloadWorker` cleanup in `download_file()`
   - Updated `_on_download_completed()` and `_on_download_error()` to not remove worker

## Test Coverage

Created `tests/test_qthread_lifecycle.py` with:
- Test demonstrating the incorrect pattern (causes crash)
- Test demonstrating the correct pattern (works properly)

## Best Practices for QThread

1. **Never delete a QThread while it's running**
   - Always wait for the `finished()` signal before cleanup

2. **Use AutoConnection for signals**
   - Let Qt handle thread-safe signal delivery automatically
   - Avoid DirectConnection unless you have a specific reason

3. **Separate lifecycle management from business logic**
   - Connect business logic to domain-specific signals (e.g., `download_finished`)
   - Connect cleanup to lifecycle signals (e.g., `finished`)

4. **Prefer QThreadPool with QRunnable for short tasks**
   - Qt manages the lifecycle automatically
   - Example: `PlayerControls` uses this pattern correctly

## References

- Qt Documentation: [QThread Class](https://doc.qt.io/qt-6/qthread.html)
- Qt Documentation: [Threads and QObjects](https://doc.qt.io/qt-6/threads-qobject.html)

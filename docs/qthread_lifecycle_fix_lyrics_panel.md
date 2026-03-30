# QThread Lifecycle Management Fix

## Problem

The application was crashing on exit with the error:
```
[CRITICAL] root - Qt: QThread: Destroyed while thread '' is still running
```

## Root Cause

When the MainWindow was closed, worker threads (especially `LyricsLoader` and `LyricsDownloadWorker`) could still be running. The `LyricsController` class managed these threads but had no cleanup method to properly stop them before destruction.

When Qt destroyed the `LyricsController` as part of the widget tree cleanup, if threads were still running, the QThread destructor would fail with the error above.

## Solution

### 1. Added cleanup method to LyricsController

Added a `cleanup()` method in `ui/windows/components/lyrics_panel.py`:

```python
def cleanup(self):
    """Clean up worker threads before destruction."""
    # Clean up lyrics loader thread
    if self._lyrics_thread and isValid(self._lyrics_thread):
        if self._lyrics_thread.isRunning():
            logger.debug("[LyricsController] Stopping lyrics thread")
            self._lyrics_thread.requestInterruption()
            self._lyrics_thread.quit()
            if not self._lyrics_thread.wait(1000):
                logger.warning("[LyricsController] Lyrics thread did not stop gracefully, terminating")
                self._lyrics_thread.terminate()
                self._lyrics_thread.wait()
        try:
            self._lyrics_thread.finished.disconnect()
            self._lyrics_thread.lyrics_ready.disconnect()
        except RuntimeError:
            pass
        self._lyrics_thread.deleteLater()
        self._lyrics_thread = None

    # Clean up lyrics download thread
    if self._lyrics_download_thread and isValid(self._lyrics_download_thread):
        if self._lyrics_download_thread.isRunning():
            logger.debug("[LyricsController] Stopping lyrics download thread")
            self._lyrics_download_thread.quit()
            if not self._lyrics_download_thread.wait(1000):
                logger.warning("[LyricsController] Lyrics download thread did not stop gracefully, terminating")
                self._lyrics_download_thread.terminate()
                self._lyrics_download_thread.wait()
        try:
            self._lyrics_download_thread.finished.disconnect()
            self._lyrics_download_thread.lyrics_downloaded.disconnect()
            self._lyrics_download_thread.download_failed.disconnect()
            self._lyrics_download_thread.cover_downloaded.disconnect()
        except RuntimeError:
            pass
        self._lyrics_download_thread.deleteLater()
        self._lyrics_download_thread = None
```

### 2. Called cleanup from MainWindow.closeEvent

Added cleanup call in `ui/windows/main_window.py`:

```python
# Clean up lyrics controller threads
if hasattr(self, '_lyrics_controller') and self._lyrics_controller:
    try:
        self._lyrics_controller.cleanup()
    except Exception as e:
        logger.error(f"Error cleaning up lyrics controller: {e}")
```

## Thread Cleanup Best Practices

The fix follows Qt best practices for thread cleanup:

1. **Cooperative Cancellation**: Use `requestInterruption()` to signal the thread to stop gracefully
2. **Graceful Shutdown**: Call `quit()` and `wait()` to allow clean shutdown
3. **Force Termination**: Only use `terminate()` as a last resort if the thread doesn't stop
4. **Signal Disconnection**: Disconnect all signals before deleting the thread
5. **Deferred Deletion**: Use `deleteLater()` instead of immediate deletion
6. **Null References**: Set thread references to None after cleanup

## Other QThread Usage

The codebase has other QThread subclasses, but they already have proper cleanup:

### Dialogs
- `OrganizeFilesDialog` - has `closeEvent()` cleanup
- `SettingsDialog` - has `closeEvent()` cleanup
- `LyricsDownloadDialog` - has `closeEvent()` cleanup
- `QQMusicQRLoginDialog` - has `closeEvent()` cleanup
- `BaseCoverDownloadDialog` - has `_cleanup_threads()` method
- `BaseRenameDialog` - has `closeEvent()` cleanup

### Mini Player
- `MiniPlayer` - already has proper cleanup in `closeEvent()`

### Workers
- `BatchArtistCoverWorker` / `BatchAlbumCoverWorker` - stored in dialogs that have cleanup
- `AIEnhanceWorker` - local scope with progress dialog cancellation

## Testing

The fix was verified with:
1. Existing `tests/test_qthread_lifecycle.py` tests pass
2. Manual testing: application closes without QThread errors
3. Created `tests/test_qthread_fix.py` for specific cleanup verification

## Files Modified

- `ui/windows/components/lyrics_panel.py` - Added `cleanup()` method to `LyricsController`
- `ui/windows/main_window.py` - Added cleanup call in `closeEvent()`

## Related Documentation

- `docs/qthread_lifecycle_fix.md` - Previous fix for online detail view
- `tests/test_qthread_lifecycle.py` - Test suite for QThread lifecycle

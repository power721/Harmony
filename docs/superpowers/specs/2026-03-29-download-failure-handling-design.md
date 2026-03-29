# Cloud Song Download Failure Handling

## Problem

Cloud songs that fail to download have no error handling:
- `download_error` signal is emitted but no handler listens
- Failed tracks stay in queue with `needs_download=True`
- Playback stalls at failed tracks (re-emits `track_needs_download` in a loop)
- No visual indication of failure

## Solution

Mark failed downloads as unplayable, auto-skip during playback, and allow manual retry.

## Data Model

`domain/playlist_item.py` — add field:

```python
download_failed: bool = False
```

Update `is_ready`:

```python
@property
def is_ready(self) -> bool:
    return bool(self.local_path) and not self.needs_download and not self.download_failed
```

QueueRepository persistence updated to include `download_failed`.

## Download Failure Flow

1. `CloudDownloadService` emits `download_error` (existing)
2. New: EventBus emits `download_failed(item)` signal
3. `PlaybackService` listens, sets `item.download_failed = True`

## Playback Skip

`PlayerEngine`: when encountering `download_failed=True`:
- Auto-skip, emit `track_finished`
- Do NOT emit `track_needs_download`

## Queue UI

`QueueItemDelegate` for failed items:
- Text color: gray `QColor(128, 128, 128)`
- Duration area: show "下载失败" label
- Cover: gray placeholder icon

## Retry

Right-click context menu on failed items:
- "重试下载" option
- Action: set `download_failed=False`, `needs_download=True`, trigger re-download via CloudDownloadService

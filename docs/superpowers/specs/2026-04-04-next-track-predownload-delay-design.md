# Next Track Predownload Delay

## Problem

The player currently triggers next-track predownload immediately when the current track changes.

This causes two issues:
- Predownload starts too early instead of waiting 10 seconds after playback switches to the current track.
- Repeated track-change or queue-update paths can attempt to schedule the same next-track predownload more than once.

## Goal

Only the immediate next track should be predownloaded, and that predownload should start 10 seconds after the current track begins playback.

If the current track changes during that 10-second window, the previously scheduled predownload must be cancelled.

If the same next track is already scheduled or already downloading, no duplicate predownload should be started.

## Solution

Keep the scheduling logic in `PlaybackService`, because it already knows when the current track changes and how to resolve the current next queue item.

Replace the direct `_preload_next_cloud_track()` call in `_on_track_changed()` with a delayed scheduling flow:

1. Cancel any previously scheduled next-track predownload.
2. Recompute the current next item.
3. Skip scheduling when playback is stopped, loop mode disables predownload, the next item is missing, the next item is already local, or the next item does not need download.
4. Start a 10-second delayed task for that specific `cloud_file_id`.
5. When the delay expires, verify the item is still the immediate next track before dispatching the existing preload logic.

## Scheduling Rules

- Only one delayed predownload task may exist at a time.
- The delayed task stores the target `cloud_file_id` for deduplication and validation.
- Scheduling the same `cloud_file_id` again while it is already pending should be a no-op.
- Scheduling a different next track cancels the previous delayed task and replaces it.
- Executing a delayed task clears the pending-task state before calling the real preload function.

## Download Deduplication

Deduplication should happen in two layers:

1. Scheduling deduplication in `PlaybackService`
   - Prevent duplicate delayed tasks for the same next track.
2. Existing download deduplication in preload paths
   - QQ online tracks continue to use `_online_download_workers`.
   - Cloud tracks continue to use `_scheduled_preloads` and preload attempt limits.

This keeps the change minimal and avoids starting duplicate network work even if multiple code paths converge.

## Validation At Fire Time

The delayed callback must not assume the queued next item is unchanged.

Before starting preload, it should re-check:
- playback is not stopped
- play mode still allows predownload
- the target item still exists
- the target item is still the immediate next track
- the target item still needs download and is not already local

If any check fails, the callback exits without downloading.

## Testing

Add focused service tests for:

- scheduling a 10-second delayed predownload for the immediate next track
- cancelling the previous delayed task when the current track changes within the delay window
- avoiding duplicate scheduling for the same next track
- skipping preload when the delayed target is no longer the immediate next track at execution time

These tests should cover the scheduling layer directly and stub out the actual download methods.

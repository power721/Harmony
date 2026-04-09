# Cloud First-Click Stutter Design

## Problem

The first time the user opens the cloud drive page, the UI stutters before the page becomes responsive. The current flow enters `CloudDriveView.showEvent()`, synchronously loads accounts, auto-selects the account, and immediately fetches the remote file list on the UI thread. Remote listing latency blocks page switching.

## Goal

Keep the first navigation into the cloud page responsive while preserving current account restore, folder restore, and existing file browsing behavior.

## Recommended Approach

Move the initial account/file load off the immediate page-switch path:

- Keep `showEvent()` lightweight.
- Schedule the first cloud refresh asynchronously after the widget is shown.
- For the first load, render the page immediately, show a loading status, and fetch accounts/files without blocking navigation.
- Ignore stale async results if the selected account changes before the worker finishes.
- Preserve existing synchronous behavior for later explicit reload paths unless the async path can be reused safely.

## Data Flow

1. User clicks the cloud sidebar entry.
2. `MainWindow` switches the stacked widget immediately.
3. `CloudDriveView.showEvent()` schedules an initial async refresh once.
4. A background worker loads accounts, resolves the initial selected account, and fetches the current folder listing.
5. The UI thread applies the result, populates the account list, updates current path/account state, and renders the file table.

## Error Handling

- If account loading fails, keep the page visible and show an error status instead of freezing.
- If file loading fails, keep the current page visible and leave the file table empty or unchanged.
- If the view is closed or re-shown during loading, worker completion must not touch invalid UI objects.

## Testing

- Add a regression test proving `showEvent()` no longer calls `_load_accounts()` inline.
- Add a focused test proving the initial load is scheduled only once.
- Keep existing cloud view tests passing around navigation and file refresh behavior.

# Fix Album Covers Feature

## Overview
Added a feature to the Settings dialog (Covers tab) that allows users to fix album covers by automatically finding the first track with a cover for albums without covers.

## Location
Settings dialog → Covers tab → "Fix Album Covers" section

## How It Works

1. **Find Albums Without Covers**: The system queries the database for albums where `cover_path` is NULL or empty.

2. **Find Track Covers**: For each album without a cover, the system:
   - Gets all tracks in that album
   - Searches for the first track with a valid cover path
   - Sets that track's cover as the album cover

3. **Update Database**: The album's `cover_path` field is updated with the found cover path.

## Implementation Details

### Files Modified

1. **repositories/album_repository.py**
   - Added `get_albums_without_cover()` method to query albums without covers

2. **services/library/library_service.py**
   - Added `get_albums_without_cover()` method to expose repository functionality
   - Added `fix_album_covers()` method to orchestrate the fix operation

3. **ui/dialogs/settings_dialog.py**
   - Added "Fix Album Covers" section in the Covers tab
   - Added `_fix_album_covers()` handler method with progress dialog and error handling

4. **translations/zh.json** and **translations/en.json**
   - Added translation keys for all new UI elements

### Translation Keys Added

- `fix_album_covers`: "修复专辑封面" / "Fix Album Covers"
- `fix_album_covers_hint`: Description of what the feature does
- `fix_album_covers_button`: Button text
- `fix_album_covers_confirm`: Confirmation dialog text
- `fix_album_covers_progress`: Progress message
- `fix_album_covers_success`: Success message with stats
- `fix_album_covers_no_missing`: Message when all albums have covers
- `fix_album_covers_failed`: Error message

## User Experience

1. User opens Settings dialog
2. Goes to "Covers" tab
3. Sees new "Fix Album Covers" section with explanation
4. Clicks "Fix Album Covers" button
5. If no albums without covers: sees info message "All albums already have covers"
6. If albums without covers exist:
   - Confirmation dialog shows count of albums to fix
   - Progress dialog shows while processing
   - Success message shows how many albums were fixed
7. Album covers are updated in the UI automatically via EventBus

## Technical Notes

- The operation runs synchronously in the UI thread (not a background worker)
- Progress dialog is indeterminate (cannot cancel)
- Uses existing `AlbumRepository.update_cover_path()` method
- Emits `EventBus.instance().cover_updated.emit(None, True)` to notify UI
- Updates cover status counts after completion

## Testing

The feature has been tested with:
- Repository methods work correctly
- Service method orchestrates the operation properly
- UI components display correctly
- Progress dialog shows during operation
- Success/error messages display appropriately
- EventBus notification triggers UI refresh

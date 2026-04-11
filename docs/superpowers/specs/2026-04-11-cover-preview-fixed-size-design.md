# Cover Preview Fixed Size Design

## Goal

Make the shared cover preview dialog always use a fixed `800x800` window size instead of shrinking to the loaded image size.

## Scope

- Modify `ui/dialogs/cover_preview_dialog.py`
- Modify `tests/test_ui/test_cover_preview_dialog.py`

## Requirements

- The preview window must always be exactly `800x800`.
- The title bar, close button, `Esc` close, and title-bar dragging must stay unchanged.
- Clicking outside the image must still not close the dialog.
- The image must remain aspect-ratio correct and be centered inside the content area.
- The image may scale down to fit the available content area, but the dialog itself must never resize to match the image.

## Design

- Keep `CoverPreviewDialog.MAX_WINDOW_WIDTH` and `MAX_WINDOW_HEIGHT` at `800`.
- Keep the current title-bar layout and dialog shell.
- Remove content-driven window resizing from `_set_pixmap()`.
- Compute the available image area from the fixed dialog size minus title-bar and content padding.
- Scale the pixmap with `KeepAspectRatio` into that fixed content area.
- Keep the content frame centered inside the fixed dialog.

## Testing

- Update the existing size test to assert `dialog.width() == 800` and `dialog.height() == 800`.
- Keep the existing interaction tests for close button, `Esc`, title-bar drag, and parent-window behavior.

## Non-Goals

- No changes to QQ plugin-specific cover URL handling.
- No changes to title-bar styling.
- No changes to preview open/close triggers in detail views.

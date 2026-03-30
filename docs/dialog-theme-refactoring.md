# Dialog Theme Refactoring

## Overview

Refactored lyrics-related dialogs to use themed title bars consistent with the application's design system.

## Changes

### 1. LyricsDownloadDialog

**File**: `ui/dialogs/lyrics_download_dialog.py`

**Changes**:
- Converted to frameless dialog with custom themed title bar
- Added drop shadow effect for depth
- Implemented rounded corners with mask
- Added drag-to-move functionality
- Updated styling to match `EditMediaInfoDialog` pattern

**Visual Improvements**:
- Custom title bar with theme colors
- Rounded corners (12px radius)
- Drop shadow for modern appearance
- Consistent button styling with theme

### 2. LyricsEditDialog (New)

**File**: `ui/dialogs/lyrics_edit_dialog.py`

**Created**: Extracted from `LyricsController.edit_lyrics()`

**Features**:
- Standalone dialog class for lyrics editing
- Frameless design with themed title bar
- Drop shadow effect
- Rounded corners
- Drag-to-move functionality
- Consistent styling with other dialogs
- Static `show_dialog()` method for easy usage

**Benefits**:
- Reusable component
- Better separation of concerns
- Consistent theming across all dialogs
- Easier maintenance

### 3. LyricsController

**File**: `ui/windows/components/lyrics_panel.py`

**Changes**:
- Replaced inline dialog creation with `LyricsEditDialog`
- Simplified `edit_lyrics()` method (reduced from ~110 lines to ~35 lines)
- Better error handling
- Cleaner code organization

## Technical Details

### Theme Integration

Both dialogs follow the same pattern as `EditMediaInfoDialog`:

1. **Frameless Window**:
   ```python
   self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
   self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
   ```

2. **Container Widget**:
   - Outer layout with 0 margins
   - Container widget with rounded corners
   - Object name for styling: `dialogContainer`

3. **Title Label**:
   - Object name: `dialogTitle`
   - Bold font, 15px size
   - Uses theme text color

4. **Drop Shadow**:
   ```python
   shadow = QGraphicsDropShadowEffect(self)
   shadow.setBlurRadius(30)
   shadow.setOffset(0, 8)
   shadow.setColor(QColor(0, 0, 0, 80))
   ```

5. **Rounded Corners**:
   ```python
   def resizeEvent(self, event):
       path = QPainterPath()
       path.addRoundedRect(self.rect(), 12, 12)
       self.setMask(QRegion(path.toFillPolygon().toPolygon()))
   ```

6. **Drag to Move**:
   ```python
   def mousePressEvent(self, event):
       if event.button() == Qt.MouseButton.LeftButton:
           self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

   def mouseMoveEvent(self, event):
       if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
           self.move(event.globalPosition().toPoint() - self._drag_pos)
   ```

### Styling Template

Both dialogs use consistent styling:

```css
QWidget#dialogContainer {
    background-color: %background_alt%;
    color: %text%;
    border: 1px solid %border%;
    border-radius: 12px;
}

QLabel#dialogTitle {
    color: %text%;
    font-size: 15px;
    font-weight: bold;
}
```

Theme variables are automatically replaced by `ThemeManager.instance().get_qss()`.

## Testing

Both dialogs have been tested:
- Import successful
- Theme registration works
- Drag-to-move functional
- Rounded corners applied
- Shadow effect visible

## Future Improvements

None identified. The dialogs now follow the established pattern and are consistent with the rest of the application.

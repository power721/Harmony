# Theme System Hardcoded Color Fixes

## Summary

Fixed all hardcoded colors in delegate and card components to use theme-aware colors from the ThemeManager. This resolves visibility issues in light themes where dark gray hardcoded colors were invisible on white backgrounds.

## Problem

Several UI components were using hardcoded dark gray colors that worked fine in dark themes but became invisible or very hard to see in light themes:

- `#3d3d3d` - dark gray background
- `#666666` - medium gray icon/text color
- `#1db954` - hardcoded highlight green
- `#ffffff` - hardcoded white text
- `#b3b3b3` - hardcoded secondary text color
- `#2a2a2a`, `#3a3a3a` - hardcoded context menu colors

## Solution

Replaced all hardcoded colors with theme-aware colors from the ThemeManager:

### Files Modified

#### 1. `ui/widgets/artist_card.py`
- **Line 228, 233**: Default avatar colors
  - Background: `#3d3d3d` → `theme.text_secondary`
  - Icon: `#666666` → `theme.text`
- **Line 306**: Added `_load_avatar()` call in `refresh_theme()` to reload avatars when theme changes

#### 2. `ui/views/artists_view.py`
- **Line 110, 115**: ArtistDelegate default cover colors
  - Background: `#3d3d3d` → `theme.text_secondary`
  - Icon: `#666666` → `theme.text`
- **Line 189**: Hover border color `#1db954` → `theme.highlight`
- **Line 196, 211**: Text colors now use `theme.text` and `theme.text_secondary`
- **Line 590-607**: Context menu colors now use theme variables
- Added `refresh_theme()` method to ArtistDelegate to regenerate default covers

#### 3. `ui/views/albums_view.py`
- **Line 105, 109**: AlbumDelegate default cover colors
  - Background: `#3d3d3d` → `theme.text_secondary`
  - Icon: `#666666` → `theme.text`
- **Line 182**: Hover background color `QColor(30, 30, 30, 200)` → semi-transparent `theme.background_hover`
- **Line 183**: Hover border color `#1db954` → `theme.highlight`
- **Line 190, 205**: Text colors now use `theme.text` and `theme.text_secondary`
- **Line 590-607**: Context menu colors now use theme variables
- Added `refresh_theme()` method to AlbumDelegate to regenerate default covers

#### 4. `ui/views/online_grid_view.py`
- **Line 126, 138**: OnlineItemDelegate default cover colors
  - Background: `#3d3d3d` → `theme.text_secondary`
  - Icon: `#666666` → `theme.text`
- **Line 317, 333**: Hover border colors now use `theme.highlight_hover`
- **Line 332**: Hover background color `QColor(30, 30, 30, 200)` → semi-transparent `theme.background_hover`
- **Line 340, 369**: Text colors now use `theme.text` and `theme.text_secondary`
- Added `refresh_theme()` method to OnlineItemDelegate to regenerate default covers

## Theme Colors Used

The following theme colors are now used throughout:

- `theme.text` - Primary text color (contrasts with background)
- `theme.text_secondary` - Secondary/muted text color
- `theme.highlight` - Accent/highlight color for borders and emphasis
- `theme.highlight_hover` - Accent color for hover states
- `theme.background` - Main background color
- `theme.background_hover` - Hover state background
- `theme.border` - Border/divider color

## Benefits

1. **Light Theme Support**: All UI elements now properly adapt to light themes
2. **Consistent Theming**: All colors come from a central theme system
3. **Real-time Theme Switching**: Components update immediately when theme changes
4. **Maintainability**: No scattered hardcoded values to track down
5. **Extensibility**: Adding new themes automatically works for all components

## Testing

All theme-related tests pass successfully:
- `test_online_album_card.py` - All 5 tests pass
- `test_theme.py` - All 19 tests pass
- Total: 616 tests pass, 31 pre-existing failures unrelated to theme changes

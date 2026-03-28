# OnlineAlbumCard Theme Implementation

## Summary

Applied theme system to `OnlineAlbumCard` widget following the same pattern used in `RecommendCard`.

## Changes Made

### 1. Removed Static Style Templates
- Removed `_STYLE_COVER_CONTAINER` constant
- Removed `_STYLE_COVER_CONTAINER_HOVER` constant
- Removed `_STYLE_NAME_LABEL` constant

These were using placeholder tokens that required runtime string replacement, which is less efficient.

### 2. Added Pre-computed Stylesheets (H-08 Optimization)
- Added `_style_normal` instance attribute - computed at initialization and theme changes
- Added `_style_hover` instance attribute - computed at initialization and theme changes
- Styles are pre-computed using actual theme colors instead of template tokens

**Benefits:**
- Faster hover transitions (no string replacement on each hover)
- Cleaner code structure
- Matches the pattern used in `RecommendCard` and `AlbumCard`

### 3. Updated `_setup_ui()` Method
- Added pre-computed stylesheet initialization
- Removed unnecessary border-radius style from cover label (QLabel doesn't support border-radius natively - the border-radius on the parent QFrame container provides the rounded corners)
- Updated name label to use `ThemeManager.get_qss()` for consistent styling

### 4. Simplified Event Handlers
- `enterEvent()`: Directly applies pre-computed `_style_hover`
- `leaveEvent()`: Directly applies pre-computed `_style_normal`
- Removed `_apply_hover_style()` and `_apply_normal_style()` helper methods (no longer needed)

### 5. Enhanced `refresh_theme()` Method
- Updates pre-computed stylesheets when theme changes
- Applies appropriate style based on current hover state
- Updates text labels with new theme colors
- Updates default cover with new theme colors

## Files Modified

- `ui/views/online_detail_view.py` - Updated `OnlineAlbumCard` class
- `ui/widgets/artist_card.py` - Removed duplicate class definition
- `tests/test_ui/test_online_album_card.py` - Added comprehensive theme tests

## Testing

Created 5 new tests to verify theme functionality:
1. `test_online_album_card_has_theme_attributes` - Verifies required attributes exist
2. `test_online_album_card_registered_with_theme_manager` - Verifies registration
3. `test_online_album_card_theme_change` - Verifies theme changes update styles
4. `test_online_album_card_hover_styles` - Verifies hover styles are correct
5. `test_online_album_card_refresh_theme` - Verifies refresh_theme method

All tests pass successfully.

## Qt Warning Fix

Fixed Qt stylesheet parsing warning by removing invalid `border-radius` property from QLabel stylesheet.
QLabel does not natively support the `border-radius` CSS property. The rounded corners are already
provided by the parent QFrame container's border-radius styling.

## Pattern Reference

This implementation follows the same pattern as:
- `RecommendCard` (ui/widgets/recommend_card.py)
- `AlbumCard` (ui/widgets/album_card.py)

The key improvement is using pre-computed stylesheets instead of runtime template replacement, which provides:
- Better performance (no string manipulation on each hover)
- Cleaner code (no placeholder replacement logic)
- Consistency with other themed widgets

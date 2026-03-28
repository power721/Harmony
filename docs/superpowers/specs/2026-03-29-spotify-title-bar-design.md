# Spotify-style Title Bar with Dynamic Cover Color

**Date:** 2026-03-29
**Status:** Approved

## Summary

Replace the native OS title bar with a custom Spotify-style frameless title bar. The title bar adapts to all 7 themes and dynamically tints its background based on the dominant color of the current album cover.

## Architecture

```
ui/widgets/title_bar.py          → SpotifyTitleBar widget (new)
services/metadata/color_extractor.py → ColorExtractor service (new)
MainWindow                       → FramelessWindowHint + title bar integration (modify)
```

## Components

### 1. TitleBar Widget (`ui/widgets/title_bar.py`)

- **Height:** 44px fixed
- **Left:** Mac-style decorative traffic lights (red/yellow/green circles, 12x12px)
- **Center:** "Harmony" label; shows current track name when playing
- **Right:** Windows-style minimize (—), maximize (□), close (✕) buttons
- **Close button:** red hover (#e81123)
- **Drag:** mousePressEvent/mouseMoveEvent/mouseReleaseEvent for window dragging
- **Double-click:** toggle maximize/restore
- **Theme-aware:** uses ThemeManager token system (`%background%`, `%text%`, etc.)
- **Dynamic color:** `set_accent_color(QColor)` blends cover color with theme bg
  - Blend ratio: 40% cover color + 60% theme background
  - Smooth transition via QPropertyAnimation (~300ms)
  - Gradient: cover color blend at top → theme bg at bottom
- **Resize grip:** bottom-right corner resize handle on MainWindow

### 2. ColorExtractor (`services/metadata/color_extractor.py`)

- Input: image file path (str)
- Output: dominant QColor
- Algorithm: sample pixels from QImage, simple median-cut or frequency-based clustering
- Threaded: runs in QThread via QRunnable + QThreadPool
- Signal: `color_extracted(QColor)` emitted on completion
- Handles: missing file, corrupt image gracefully → returns None

### 3. MainWindow Integration (modify `ui/windows/main_window.py`)

- Set window flags: `Qt.FramelessWindowHint` (keep other flags)
- Insert TitleBar as first item in main QVBoxLayout (above content_widget)
- Remove native `setWindowTitle()` calls — title bar handles display
- Preserve `_restore_settings()` / `_save_settings()` for geometry
- Add bottom-right resize grip widget

### 4. Dynamic Color Flow

```
track_changed (EventBus)
  → MainWindow gets cover path via LibraryService/PlayerProxy
  → ColorExtractor runs in background thread
  → color_extracted(QColor) signal
  → TitleBar.set_accent_color(color)
  → Gradient background updated with animation
```

### 5. Theme Interaction

- Default state: title bar bg = `theme.background`
- Cover color active: blend 40% cover + 60% theme bg, gradient to theme bg
- Theme switch (`theme_changed` signal): reset to pure theme color; if cover still active, re-blend with new theme bg
- Track with no cover: revert to pure theme color
- TitleBar registered with ThemeManager via `register_widget()`, implements `refresh_theme()`

## Files Changed

| File | Action |
|------|--------|
| `ui/widgets/title_bar.py` | **Create** — TitleBar widget |
| `services/metadata/color_extractor.py` | **Create** — ColorExtractor |
| `ui/windows/main_window.py` | **Modify** — frameless + title bar integration |
| `tests/test_title_bar.py` | **Create** — widget tests |
| `tests/test_color_extractor.py` | **Create** — color extraction tests |

## Out of Scope

- Acrylic/blur effects (future)
- Immersive mode (content extending into title bar)
- Scrolling title for long track names (future)
- Mac-specific native traffic light behavior (functional close/minimize/maximize on Mac)

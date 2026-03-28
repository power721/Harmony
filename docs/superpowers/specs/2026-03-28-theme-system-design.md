# Harmony Theme System Design

## Overview

Token-based QSS theme system for Harmony music player. Users choose from 5 dark presets or create custom themes via a color editor. Theme changes apply in real-time without restart.

## Theme Data Model

```python
@dataclass
class Theme:
    name: str
    display_name: str  # i18n key

    background: str        # main background
    background_alt: str    # secondary background
    background_hover: str  # hover background
    text: str              # primary text
    text_secondary: str    # secondary/muted text
    highlight: str         # accent color
    highlight_hover: str   # accent hover
    selection: str         # selected item
    border: str            # borders/dividers
```

9 color tokens total, format `%token_name%` in QSS.

## Preset Themes (all dark)

| Theme    | Background | Alt BG    | Accent             | Style        |
|----------|------------|-----------|--------------------|--------------|
| Dark     | #121212    | #282828   | #1db954 (green)    | Spotify classic |
| Gold     | #1a1a1a    | #2a2a2a   | #FFD700 (gold)     | Warm luxury  |
| Ocean    | #0d1b2a    | #1b2838   | #00b4d8 (blue)     | Deep calm    |
| Purple   | #1a0a2e    | #2d1b4e   | #9b59b6 (purple)   | Mysterious   |
| Sunset   | #1a0a0a    | #2a1414   | #e74c3c (red)      | Warm bold    |

Each preset defines all 9 tokens with tuned contrast and atmosphere.

## ThemeManager Architecture

Singleton in `system/theme.py`:

```
ThemeManager
├── _presets: dict[str, Theme]        # registered presets
├── _current: Theme                   # active theme
├── theme_changed: Signal(Theme)      # broadcast on change
├── _widgets: WeakSet[QWidget]        # registered widgets
│
├── set_theme(name: str)              # switch to preset
├── set_custom_theme(theme: Theme)    # apply custom theme
├── get_qss(template: str) -> str     # replace %tokens% with colors
├── apply_global_stylesheet()         # regenerate + set on QApplication
├── register_widget(widget)           # subscribe to theme changes
└── _on_widget_refresh(theme)         # call refresh_theme() on all registered
```

### Real-time Switch Flow

```
User selects theme
  -> ThemeManager.set_theme(name)
      -> update _current
      -> apply_global_stylesheet()     # regenerate qt_app stylesheet
      -> emit theme_changed(Theme)
          -> MainWindow.refresh_theme()
          -> each registered widget.refresh_theme()
```

### Key Design Decisions

- **Remove monkey-patch** on `QWidget.setStyleSheet`. Replace with explicit `refresh_theme()` pattern.
- Widgets register via `ThemeManager.instance().register_widget(self)` in `__init__`.
- `WeakSet` ensures auto-cleanup when widgets are destroyed.

## Custom Theme Editor

Located in Settings Dialog -> Appearance tab.

### Layout

```
┌─────────────────────────────────────────┐
│ Presets: [Dark] [Gold] [Ocean] [Purple] [Sunset] │
├─────────────────────────────────────────┤
│ Custom Colors                           │
│                                         │
│ Background       [■ picker]  #121212    │
│ Alt Background   [■ picker]  #282828    │
│ Hover Background [■ picker]  #2a2a2a    │
│ Text             [■ picker]  #ffffff    │
│ Secondary Text   [■ picker]  #b3b3b3    │
│ Highlight        [■ picker]  #1db954    │
│ Highlight Hover  [■ picker]  #1ed760    │
│ Selection        [■ picker]  rgba(...)  │
│ Border           [■ picker]  #3a3a3a    │
│                                         │
│ ┌───────────────────────────┐           │
│ │      Live Preview Area    │           │
│ └───────────────────────────┘           │
│                                         │
│           [Apply]  [Reset]              │
└─────────────────────────────────────────┘
```

### Interaction

- Click preset button -> switch theme, fill editor with preset colors
- Edit any color -> preview updates live
- "Apply" -> save as custom theme + apply + persist to config
- "Reset" -> revert to current preset colors
- Edits are temporary until "Apply" is clicked

## QSS Migration Strategy

### 1. Global stylesheet (`ui/styles.qss`)

Replace all hardcoded hex colors with tokens:

```css
/* Before */ background: #121212;
/* After  */ background: %background%;
```

### 2. Inline QSS templates

Extract inline `setStyleSheet()` strings into class-level template constants:

```python
class PlayerControls(QWidget):
    _STYLE_TEMPLATE = """
    QPushButton {
        background: %background_alt%;
        color: %text%;
        border: 1px solid %border%;
    }
    QPushButton:hover {
        color: %highlight%;
    }
    """

    def refresh_theme(self):
        self.setStyleSheet(
            ThemeManager.instance().get_qss(self._STYLE_TEMPLATE)
        )
```

### 3. Non-standard color mapping

| Original    | Token               | Rationale                        |
|-------------|---------------------|----------------------------------|
| #0a0a0a     | %background%        | Deep variant -> use main BG      |
| #141414     | %background%        | Between BGs -> use main BG       |
| #1a1a1a     | %background_alt%    | Between BGs -> use alt BG        |
| #2a2a2a     | %background_hover%  | Hover shade                      |
| #3a3a3a     | %border%            | Border shade                     |
| #4a4a4a     | %border%            | Slightly brighter border         |

### 4. Exclusions

- Purely decorative gradient endpoints: keep as-is
- Opacity-only variations: keep rgba() with original base, replace only the color portion in templates

## Persistence

| Config Key      | Value                                                        |
|-----------------|--------------------------------------------------------------|
| `ui.theme`      | `"dark"` / `"gold"` / `"ocean"` / `"purple"` / `"sunset"` / `"custom"` |
| `ui.theme.custom` | `{"background": "#1a1a1a", "highlight": "#FFD700", ...}` (custom only) |

- Presets: store name only, colors from built-in definitions
- Custom: store full color dict

## Thread Safety

- ThemeManager operates only on UI thread
- `theme_changed` signal uses Qt signal/slot (inherently thread-safe)
- Widget registration via `WeakSet` (no memory leaks on widget destruction)

## Error Handling

- Color validation: `#RRGGBB` or `rgba(r,g,b,a)` format; invalid values fall back to dark theme defaults
- Missing `styles.qss`: log warning, use empty QSS
- Unknown theme name: fall back to dark

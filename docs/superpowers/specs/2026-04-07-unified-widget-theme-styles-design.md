# Unified Foundation Theme Styles Design

## Overview

This change consolidates the styling of common Qt foundation widgets and project-wide shared wrapper components under the host theme system.

The earlier request named several examples such as `DialogTitleBar`, `QLineEdit`, `QCheckBox`, `QGroupBox`, `QComboBox`, and popup widgets. After inventorying the codebase, the actual scope should be broader: all commonly reused Qt foundation controls plus the project's shared wrapper components should be owned by the theme system.

The goal is to stop defining base styles for these shared building blocks inside individual components. Host widgets and plugins must both receive the same baseline styling from the theme system. Component-level variation remains allowed, but only through theme-owned selectors such as object names and dynamic properties.

## Goals

- Move base styles for common foundation widgets into the theme system.
- Move base styles for shared wrapper components into the theme system.
- Ensure host UI and plugin UI use the same styling source.
- Remove duplicated inline QSS for these foundation widgets and wrappers from dialogs, views, widgets, and plugin components.
- Preserve room for controlled variants through object names or dynamic properties.
- Keep real-time theme switching working for all affected widgets.

## Non-Goals

- No attempt to centralize highly bespoke business widgets whose visuals are their primary value.
- No visual redesign of unrelated custom widgets such as cards, tables, sliders, or artwork containers.
- No plugin-specific theme fork.
- No generic "component style registry" abstraction beyond what is needed to make popups and global QSS work reliably.

## Scope Inventory

The codebase inventory shows that the foundation layer is larger than the initial example list. This change should cover two tiers.

### Tier 1: Common Qt foundation widgets

These are the shared Qt building blocks that appear broadly across host UI and plugins and should have a theme-owned baseline:

- application shell and containers: `QWidget`, `QDialog`, `QMainWindow`, `QFrame`, `QSplitter`, `QScrollArea`, `QStackedWidget`, `QTabWidget`, `QTabBar`
- text and display primitives: `QLabel`, `QProgressBar`
- command controls: `QPushButton`, `QDialogButtonBox`
- text input controls: `QLineEdit`, `QTextEdit`
- selection controls: `QCheckBox`, `QRadioButton`, `QComboBox`, `QSpinBox`
- grouping and layout framing: `QGroupBox`
- item and data views with shared baseline chrome: `QListWidget`, `QListView`, `QTableWidget`, headers, and common `QAbstractItemView` popup surfaces
- menu and popup surfaces: `QMenu`, completer popups, custom hover popups, and frameless `Qt.Popup` dialogs

This tier is the baseline for "all common Qt base widgets" in this repository, not an exhaustive list of every Qt class that exists.

### Tier 2: Project-wide shared wrapper components

These are repository-level reusable components that should also be theme-owned because they are part of the app foundation rather than one-off business presentation:

- `TitleBar`
- `DialogTitleBar`
- `ToggleSwitch`
- shared context menu builders
- shared popup wrappers such as cover hover popups and hotkey popups
- shared dialog shells such as message, input, rename, provider-select, progress, and cover-download dialog scaffolding

These wrappers may still contain structure and behavior, but their shared visual rules should be driven from the same theme layer as Tier 1.

## Current Problems

The repository already has a global stylesheet and token replacement via `ThemeManager`, but foundation widgets and wrappers are still styled in multiple layers:

- global QSS in `ui/styles.qss`
- ad hoc inline `setStyleSheet()` calls inside dialogs and views
- duplicated title bar styling in host and plugin code
- plugin-local popup styles using `get_qss(...)` with their own widget templates

This causes three issues:

1. The same widget class has different visual rules depending on where it is created.
2. Theme updates require touching many files instead of one theme-owned surface.
3. Plugins can drift away from host behavior even though they already route through the host theme bridge.

## Recommended Approach

Use the theme system as the single owner of foundation styles.

### 1. Expand the global theme stylesheet

`ui/styles.qss` becomes the base stylesheet source for foundation widget classes and theme-owned variants.

It should define:

- global base rules for the Tier 1 widget families listed above
- wrapper rules keyed by object names and properties for Tier 2 shared components
- title bar rules keyed by object names such as `#dialogTitleBar`, `#dialogTitle`, `#dialogCloseBtn`, and corresponding main window title bar selectors
- variant selectors keyed by dynamic properties or object names where the app needs approved deviations

Examples of allowed variant hooks:

- `QLineEdit[variant="search"]`
- `QGroupBox[variant="settings"]`
- `QWidget[popupSurface="true"]`
- `QComboBox[compact="true"]`
- `QPushButton[role="primary"]`
- `QDialog[shell="true"]`

The theme file remains token-based, so all colors continue to come from `ThemeManager.get_qss(...)`.

### 2. Keep popup-specific helper entry points inside the theme system

Some surfaces are not reliably covered by application-wide selectors alone because they may be separate top-level widgets, created lazily by Qt, or painted by reusable wrappers. For those cases, the theme system should expose small helper templates owned by `ThemeManager`, for example:

- popup list view style for `QCompleter.popup()`
- generic popup surface style for custom `QWidget` popups
- optional frameless popup dialog wrapper style
- shared wrapper accents such as toggle switch token access if a widget is painted manually rather than styled by QSS

These helpers remain part of the theme system. Components may apply them, but they may not define their own base popup QSS.

This is not a second styling system. It is a delivery mechanism for theme-owned styles in cases where Qt global QSS attachment is insufficient.

### 3. Remove duplicated title bar styling from components

Both host and plugin shared title bar implementations should stop embedding their own QSS templates for:

- `dialogTitleBar`
- `dialogTitle`
- `dialogCloseBtn`

They should only:

- build the widget tree
- assign object names
- refresh icons if needed

The actual styling must come from the global theme stylesheet.

### 4. Make plugin popups use host-owned theme helpers

Plugin code already reaches the host theme bridge through `system.plugins.plugin_sdk_ui`.

Extend that bridge only as needed so plugin popups can consume the same theme-owned popup helpers as host widgets. The plugin must not carry its own popup base style definitions for completers, hotkey popups, hover popups, or title bars.

## Styling Rules

The following rules define what components may and may not do after this change.

### Allowed

- Set object names needed by theme selectors.
- Set dynamic properties needed by theme selectors.
- Apply theme-owned helper QSS returned from `ThemeManager` for popup surfaces that cannot be covered robustly by global QSS.
- Apply highly local styles for non-foundation business widgets or purely content-driven decoration.

### Not Allowed

- Embed base QSS for common foundation widgets or shared wrapper components inside feature component classes.
- Duplicate host style templates in plugins.
- Introduce new per-component styling for foundation widgets when a theme selector or theme helper can express it.

## Host and Plugin Coverage

This change applies to both:

- host code under `ui/`
- built-in plugin UI under `plugins/`

The expected path is:

1. `ThemeManager` owns style templates and global stylesheet expansion.
2. `plugin_sdk_ui` exposes any required theme-owned popup helper accessors.
3. plugin widgets call those host-owned helpers rather than embedding their own base QSS.

This preserves one visual language across host and plugin boundaries.

## Migration Plan

### Theme system changes

- update `ui/styles.qss` with the base rules and approved variant selectors
- add small popup helper accessors in `system/theme.py` if global QSS alone is not enough
- extend plugin theme bridge access only if popup helpers need to be callable from plugins

### Host cleanup

Remove inline base styles from host files that currently define foundation widget QSS locally, such as dialogs, settings pages, library views, album or artist search inputs, equalizer controls, context menus, title bars, dialog shells, and popup widgets.

Those files should instead:

- rely on global styling for normal controls
- set object names or dynamic properties for approved variants
- call theme-owned popup helpers where required

### Plugin cleanup

Remove duplicated base styles from plugin files, especially:

- plugin dialog title bar styling
- plugin search input styling
- plugin combo box styling
- completer popup styling
- hotkey popup and cover hover popup base styling
- plugin menu, dialog shell, and shared wrapper styling where it duplicates host-owned foundation rules

Plugins should use host-owned selectors and popup helpers only.

## Testing

Add focused tests that validate the new ownership model instead of pixel-perfect appearance.

### Theme manager tests

- verify popup helper methods return themed QSS with token replacement
- verify the global stylesheet contains the expected selectors for the foundation widget families and shared wrapper selectors

### Host UI tests

- verify dialog title bars rely on object names and no longer inject local title bar QSS
- verify representative views and shared dialogs still construct and refresh correctly after local base styles are removed
- verify popup widgets still receive themed styles through the theme system
- verify reusable wrapper components such as `ToggleSwitch` and shared menus still follow theme-owned tokens or selectors

### Plugin tests

- verify plugin title bar setup resolves to host-owned styling behavior
- verify plugin completer and popup widgets use theme bridge helpers instead of local hardcoded templates
- verify plugin shared settings or login surfaces inherit the same foundation baselines as host widgets

## Error Handling

- Missing helper access in the plugin bridge should fail during tests rather than silently falling back to plugin-local QSS.
- Unknown dynamic properties simply fall back to the base global selector.
- Theme switching still relies on `ThemeManager.apply_global_stylesheet()` plus registered widget refresh hooks for popup helper reapplication.

## Scope Check

This is a foundation-layer theme cleanup. It is larger than a one-file tweak, but still bounded:

- theme system
- host dialogs, views, and shared widgets that currently override foundation styles
- plugin theme bridge
- built-in plugin UI files that currently duplicate the same control, dialog shell, menu, or popup styling

It should be implemented as one coordinated cleanup with tests, not as a new styling framework.

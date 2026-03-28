# Theme System Implementation Plan

## Overview

Implement token-based QSS theme system with 5 presets + custom editor. Real-time switching without restart.

## Files to Modify

**Core:**
- `system/theme.py` - Theme dataclass (9 colors), ThemeManager with token replacement, widget registration, theme_changed signal
- `system/config.py` - add `ui.theme`, `ui.theme.custom` keys
- `main.py` - remove monkey-patch, use explicit refresh_theme pattern
- `app/bootstrap.py` - theme property unchanged (already correct)
- `ui/styles.qss` - replace all hardcoded hex with %token% format

**Settings:**
- `ui/dialogs/settings_dialog.py` - new appearance tab with preset buttons + custom color editor + live preview
- `translations/en.json` - new theme strings
- `translations/zh.json` - new theme strings

**Inline QSS (37 files) - add _STYLE_TEMPLATE + refresh_theme():**
- `ui/windows/main_window.py`, `ui/windows/mini_player.py`
- `ui/windows/components/sidebar.py`, `ui/windows/components/lyrics_panel.py`
- `ui/widgets/player_controls.py`, `ui/widgets/album_card.py`, `ui/widgets/artist_card.py`, `ui/widgets/recommend_card.py`, `ui/widgets/equalizer_widget.py`
- `ui/views/library_view.py`, `ui/views/queue_view.py`, `ui/views/playlist_view.py`, `ui/views/album_view.py`, `ui/views/artist_view.py`, `ui/views/albums_view.py`, `ui/views/artists_view.py`
- `ui/views/online_music_view.py`, `ui/views/online_detail_view.py`, `ui/views/online_grid_view.py`
- `ui/views/cloud/cloud_drive_view.py`, `ui/views/cloud/file_table.py`, `ui/views/cloud/dialogs.py`, `ui/views/cloud/context_menu.py`
- `ui/dialogs/settings_dialog.py`, `ui/dialogs/add_to_playlist_dialog.py`, `ui/dialogs/edit_media_info_dialog.py`, `ui/dialogs/lyrics_download_dialog.py`, `ui/dialogs/cloud_login_dialog.py`, `ui/dialogs/help_dialog.py`, `ui/dialogs/provider_select_dialog.py`, `ui/dialogs/qqmusic_qr_login_dialog.py`, `ui/dialogs/base_cover_download_dialog.py`, `ui/dialogs/base_rename_dialog.py`, `ui/dialogs/track_cover_download_dialog.py`, `ui/dialogs/organize_files_dialog.py`

**Tests:**
- `tests/test_system/test_theme.py` - unit tests for Theme, ThemeManager

## Implementation Order

### Phase 1: Core Theme System

**Step 1.1: Update system/theme.py**

Replace entire file with new implementation:
- Theme dataclass: name, display_name, background, background_alt, background_hover, text, text_secondary, highlight, highlight_hover, selection, border
- 5 presets: dark, gold, ocean, purple, sunset (with full 9-color palettes)
- ThemeManager: _presets dict, _current Theme, theme_changed Signal(Theme), _widgets WeakSet
- Methods: set_theme(), set_custom_theme(), get_qss(template), apply_global_stylesheet(), register_widget()
- Token replacement: `%background%` -> theme.background, etc.
- Note: Ignore old `ui.highlight_color` key entirely

**Step 1.2: Update system/config.py**

Add to SettingKey class:
```python
UI_THEME = "ui.theme"  # preset name or "custom"
UI_THEME_CUSTOM = "ui.theme.custom"  # dict of custom colors
```

No getter/setter methods needed - ThemeManager reads directly via config.get().

**Step 1.3: Update main.py**

Remove `_patch_set_stylesheet()` function and call.
Keep theme loading logic (lines 201-213) unchanged.

**Step 1.4: Update ui/styles.qss**

Replace all hardcoded colors with tokens:
- #121212 -> %background%
- #282828 -> %background_alt%
- #ffffff -> %text%
- #b3b3b3 -> %text_secondary%
- #1db954 -> %highlight%
- #1ed760 -> %highlight_hover%
- #3a3a3a, #4a4a4a, #404040 -> %border%
- #2a2a2a -> %background_hover%
- Keep gradient endpoints and rgba() as-is

**Step 1.5: Write tests/test_system/test_theme.py**

- test_theme_dataclass_to_dict
- test_theme_manager_singleton
- test_theme_manager_set_preset
- test_theme_manager_set_custom
- test_theme_manager_get_qss_token_replacement
- test_theme_manager_register_widget_refresh

### Phase 2: Settings Dialog Theme Editor

**Step 2.1: Add translation strings**

`translations/en.json`:
```json
"theme_settings": "Theme Settings",
"theme_presets": "Preset Themes:",
"theme_dark": "Dark (Spotify Green)",
"theme_gold": "Gold (Warm Luxury)",
"theme_ocean": "Ocean (Deep Blue)",
"theme_purple": "Purple (Mysterious)",
"theme_sunset": "Sunset (Warm Red)",
"theme_custom": "Custom Theme",
"theme_background": "Background",
"theme_background_alt": "Alt Background",
"theme_background_hover": "Hover Background",
"theme_text": "Text",
"theme_text_secondary": "Secondary Text",
"theme_highlight": "Highlight",
"theme_highlight_hover": "Highlight Hover",
"theme_selection": "Selection",
"theme_border": "Border",
"theme_apply": "Apply Theme",
"theme_reset": "Reset to Preset",
"theme_preview": "Live Preview",
"theme_custom_colors": "Custom Colors",
"theme_saved": "Theme saved successfully",
"theme_preview_text": "Preview - Song Title",
"theme_preview_secondary": "Artist Name • Album"
```

`translations/zh.json` - corresponding Chinese translations.

**Step 2.2: Rewrite ui/dialogs/settings_dialog.py appearance tab**

Replace entire appearance tab (lines 582-673) with:
- Preset theme buttons (5 buttons in horizontal layout)
- Custom colors group with 9 color pickers + hex input fields
- Live preview frame showing mock player controls
- Apply/Reset buttons

Update `_save_settings()`:
- Remove old highlight_color logic (ignore ui.highlight_color)
- Call theme.set_theme() or theme.set_custom_theme()
- Call theme.apply_global_stylesheet()
- Broadcast theme_changed signal

### Phase 3: Inline QSS Migration

For each of the 37 files with inline setStyleSheet:

**Pattern to apply:**

```python
class SomeWidget(QWidget):
    _STYLE_TEMPLATE = """
    QPushButton {
        background: %background_alt%;
        color: %text%;
        border: 1px solid %border%;
    }
    QPushButton:hover {
        background: %background_hover%;
        color: %highlight%;
    }
    """

    def __init__(self, ...):
        ...
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)
        self._apply_styles()

    def refresh_theme(self):
        """Called by ThemeManager when theme changes."""
        self._apply_styles()

    def _apply_styles(self):
        from system.theme import ThemeManager
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))
```

**Color token mapping:**

| Old color | Token | Notes |
|-----------|-------|-------|
| #121212, #0a0a0a, #141414 | %background% | main background |
| #282828, #1a1a1a | %background_alt% | secondary background |
| #2a2a2a, #353535 | %background_hover% | hover states |
| #ffffff | %text% | primary text |
| #b3b3b3, #c0c0c0, #a0a0a0 | %text_secondary% | muted text |
| #1db954 | %highlight% | accent color |
| #1ed760 | %highlight_hover% | accent hover |
| rgba(...) selections | %selection% | selection background |
| #3a3a3a, #4a4a4a, #404040, #606060 | %border% | borders/dividers |

**Priority order (most impactful first):**

1. `ui/widgets/player_controls.py` - always visible
2. `ui/windows/main_window.py` - main app window
3. `ui/windows/components/sidebar.py` - navigation
4. `ui/views/library_view.py` - primary view
5. `ui/views/queue_view.py` - frequently used
6. Remaining 32 files - batch by component type

### Phase 4: Real-time Switching

**Step 4.1: Implement widget refresh mechanism**

In ThemeManager:
```python
def set_theme(self, name: str):
    self._current = self._presets[name]
    self._config.set('ui.theme', name)
    self._config.delete('ui.theme.custom')
    self._apply_and_broadcast()

def set_custom_theme(self, theme: Theme):
    self._current = theme
    self._config.set('ui.theme', 'custom')
    self._config.set('ui.theme.custom', theme.to_dict())
    self._apply_and_broadcast()

def _apply_and_broadcast(self):
    self.apply_global_stylesheet()
    self.theme_changed.emit(self._current)
    # WeakSet auto-iterates, dead widgets auto-removed
    for widget in self._widgets:
        if hasattr(widget, 'refresh_theme'):
            widget.refresh_theme()
```

**Step 4.2: Update main.py theme loading**

Keep existing code but ensure it uses new ThemeManager correctly.

### Phase 5: Testing & Verification

**Step 5.1: Run all tests**

```bash
uv run pytest tests/
```

**Step 5.2: Manual testing checklist**

- [ ] Switch between 5 presets - verify all UI updates immediately
- [ ] Create custom theme - verify persistence across restart
- [ ] Edit custom theme colors - verify live preview updates
- [ ] Apply custom theme - verify all inline QSS widgets refresh
- [ ] Reset custom to preset - verify reverts correctly
- [ ] Check all 37 files with inline QSS - verify colors match theme
- [ ] Test on fresh install (no config) - verify defaults to dark theme

## Unresolved Questions

None. Design is complete.

## Estimated Effort

- Phase 1: Core system - 2-3 hours
- Phase 2: Settings dialog - 2-3 hours
- Phase 3: Inline QSS migration - 6-8 hours (37 files)
- Phase 4: Real-time switching - 1 hour
- Phase 5: Testing - 1-2 hours

Total: 12-17 hours

## Risk Mitigation

1. **Inline QSS volume**: 37 files is large. Prioritize high-impact files first (player controls, main window, sidebar). Lower-priority dialogs can be batched.
2. **Color token coverage**: Some non-standard colors may not map cleanly. Use best approximation, document exceptions.
3. **Widget lifecycle**: WeakSet handles auto-cleanup. Verify no memory leaks with widget destruction.
4. **Backward compat**: Ignore old `ui.highlight_color`. Clean break, no migration code needed.

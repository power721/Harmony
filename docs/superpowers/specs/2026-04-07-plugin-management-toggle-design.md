# Plugin Management Toggle Design

## Overview

This change refines the host-owned plugin management tab in settings.

Current behavior uses one shared enable button and one shared disable button below the plugin list. The list itself is rendered as plain text rows and exposes raw source values such as `builtin` and `external`.

The goal is to make plugin state control local to each plugin row and make plugin source labels translatable.

## Goals

- Give each plugin row its own enabled or disabled toggle control.
- Remove the shared action buttons from the bottom of the plugin tab.
- Translate plugin source labels for built-in and external plugins.
- Preserve the existing install-from-zip and install-from-url actions.
- Keep the implementation scoped to the plugin management tab and its tests.

## Non-Goals

- No switch to a table-based plugin manager UI.
- No plugin uninstall flow in this change.
- No plugin metadata expansion such as descriptions, authors, or icons.
- No change to plugin manager persistence behavior.

## Current State

`ui/dialogs/plugin_management_tab.py` currently:

- renders plugins through `QListWidgetItem` text
- stores the full plugin row dict in item data
- toggles plugin state through two shared buttons
- shows raw `row["source"]` values directly in the list text

This creates two issues:

- enabling or disabling a plugin requires selecting the row and then using a separate control area
- built-in plugins display untranslated source values

## Recommended Approach

Keep `QListWidget` but replace plain text entries with row widgets.

Each row widget should:

- show plugin name prominently
- show version, translated source label, and translated status label as secondary metadata
- show load error text when present
- expose a per-row toggle implemented with a checkbox-style control

The parent tab remains responsible for:

- fetching rows from `plugin_manager.list_plugins()`
- handling toggle callbacks through `plugin_manager.set_plugin_enabled(plugin_id, enabled)`
- refreshing the list after state changes

This keeps the change localized and avoids a broader migration to `QTableWidget`.

## UI Structure

Each plugin row should render as:

- primary line: plugin name
- secondary line: version, translated source, translated status
- optional tertiary line: load error
- right side: enabled toggle

The bottom shared enable and disable buttons should be removed entirely.

The install controls stay below the list unchanged.

## Translation

Add dedicated host translation keys:

- `plugins_source_builtin`
- `plugins_source_external`

The plugin management tab should map known source ids to these keys and fall back to the raw source string only for unexpected values.

## Data Flow

1. `refresh()` requests plugin rows from the manager.
2. For each row, the tab creates a list item and a companion row widget.
3. The row widget emits the desired enabled state when its toggle changes.
4. The tab calls `set_plugin_enabled(plugin_id, enabled)`.
5. The tab refreshes the list so rendered status and persisted state stay in sync.

## Error Handling

- Unknown source ids fall back to raw source text.
- Rows without a plugin id ignore toggle actions.
- Refresh after toggle is authoritative; the UI does not try to maintain speculative local state.

## Testing

Add or update UI tests to verify:

- plugin rows still render correctly with translated source labels
- toggling a row-level control calls `set_plugin_enabled` with the correct plugin id and boolean
- the plugin list refreshes after toggling
- raw source ids are no longer visible for built-in and external plugins

## Scope Check

This design is intentionally small and can be implemented as a single focused change touching:

- plugin management tab UI
- host translations
- plugin management tab tests

# Harmony Plugin System Design

## Overview

This document defines the first production plugin system for Harmony. The goal is to move QQ Music out of the host application and ship it as an installable plugin, while also proving the framework with an LRCLIB built-in plugin.

The design is intentionally conservative:

- Plugins are trusted Python code loaded in-process.
- Plugins are distributed as zip packages.
- The host exposes a stable SDK and registry-based extension points.
- Plugins must depend only on the SDK, not on Harmony internal modules.
- First phase excludes process sandboxing, permission prompts, and dependency resolution.

## Goals

- Introduce a host-owned plugin runtime with discovery, install, load, unload, enable, disable, and uninstall flows.
- Define a stable plugin SDK that QQ Music and future plugins can target.
- Add host extension points for:
  - sidebar pages
  - settings tabs
  - lyrics sources
  - cover sources
  - artist cover sources
  - online music providers
- Migrate `LRCLIBLyricsSource` to a built-in plugin.
- Migrate all QQ Music functionality to a plugin that can be removed from the host repository and published separately.
- Support plugin installation from local zip files and direct URL downloads.
- Add a host-owned `插件` tab to the settings dialog for plugin management.
- Keep the rest of the application functional when the QQ Music plugin is absent.

## Non-Goals

- No process isolation or sandboxing.
- No permission approval UI per capability.
- No plugin dependency graph or dependency solver.
- No marketplace UI in the first phase.
- No backward-compatible migration of existing `qqmusic.*` settings. Users may re-login and reconfigure the plugin.
- No generic arbitrary UI injection such as free-form menu patching or unrestricted access to host internals.

## Current State

QQ Music is currently a cross-cutting feature embedded in host code:

- configuration keys and credential helpers live in `system/config.py`
- host bootstrap wires QQ-specific services in `app/bootstrap.py`
- the settings dialog contains a QQ Music tab in `ui/dialogs/settings_dialog.py`
- the main window and sidebar hardcode the online music page in `ui/windows/main_window.py` and `ui/windows/components/sidebar.py`
- online music UI contains QQ-specific login, recommendation, favorite, completion, and refresh logic in `ui/views/online_music_view.py`
- lyrics, cover, and artist cover sources import QQ-specific helpers directly from `services/lyrics/qqmusic_lyrics.py`
- QQ client and service logic live under `services/cloud/qqmusic/`

This coupling makes independent release impractical. Removing QQ Music today would break bootstrap wiring, settings UI, source registration, and online navigation.

## Architecture Summary

### Recommended Approach

Use a host-owned SDK plus a registry-based plugin runtime.

- The host owns plugin discovery, lifecycle, compatibility checks, and extension point consumption.
- Plugins register capabilities through a stable `PluginContext`.
- The host consumes only registered extensions and never special-cases a plugin after registration.
- Built-in and external plugins follow the same manifest and lifecycle rules.

This is the only approach that satisfies the requirement that QQ Music be removable and separately publishable while remaining extensible for future NetEase, Baidu Drive, and Quark Drive plugins.

### Runtime Layers

```text
Harmony Host
├── Core App
│   ├── playback, library, queue, settings, theme, event bus
│   └── host UI shells (main window, settings dialog, plugin tab)
├── Plugin Runtime
│   ├── PluginManager
│   ├── PluginInstaller
│   ├── PluginRegistry
│   ├── PluginStateStore
│   └── PluginLoader
├── Stable SDK
│   └── harmony_plugin_api/*
└── Plugins
    ├── built-in/lrclib
    ├── built-in/... future host plugins
    └── external/qqmusic, netease, baidu-drive, quark-drive
```

## Host and Plugin Boundary

### Core Rule

Plugins may import only `harmony_plugin_api.*` plus Python standard library and their own bundled modules.

Plugins may not import Harmony internal modules such as:

- `app.*`
- `domain.*`
- `services.*`
- `repositories.*`
- `infrastructure.*`
- `system.*`
- `ui.*`

### Enforcement Strategy

Without sandboxing, import isolation can only be best-effort. First phase uses three layers of enforcement:

1. SDK-only authoring contract for first-party and third-party plugins.
2. Install-time static audit that rejects obvious imports of Harmony internals from plugin source files.
3. Integration tests that verify the QQ Music plugin no longer imports host internals.

This does not provide hard security guarantees, but it is sufficient for a trusted-plugin first phase and keeps the API boundary explicit.

### Stable Host Services

The host exposes a limited set of stable facades through `PluginContext` instead of raw internal services:

- logging
- HTTP client access
- event publication and subscription
- plugin-scoped storage
- plugin-scoped settings
- UI registration helpers
- media bridge services for playback, download handoff, lyrics persistence, and artwork fetch handoff

The host remains free to refactor internal implementations as long as these facades remain stable.

## Plugin Runtime

### Components

#### PluginManager

Responsibilities:

- discover built-in and external plugins
- validate compatibility
- load plugin entrypoints
- call `register()` and `unregister()`
- enable and disable plugins
- keep host startup resilient if a plugin fails

#### PluginInstaller

Responsibilities:

- install from local zip
- install from URL by downloading then delegating to zip install
- validate manifest and package structure
- upgrade an existing external plugin safely
- uninstall external plugins

#### PluginRegistry

Responsibilities:

- keep all runtime extension registrations
- support registration and rollback per plugin
- expose typed accessors for each extension point

#### PluginStateStore

Responsibilities:

- persist enabled and disabled state
- persist install source and version
- persist last load error
- support startup decisions without probing every plugin file first

#### PluginLoader

Responsibilities:

- import plugin entry modules
- instantiate entry classes
- isolate per-plugin registration state

### Lifecycle

```text
discover -> validate -> load -> register extensions -> active
active -> unregister -> disabled
disabled -> load -> register extensions -> active
active/disabled -> uninstall external package
```

Rules:

- plugin import failure must not crash host startup
- partial registration must roll back cleanly
- built-in plugins may be disabled but not uninstalled
- external plugins may be disabled or uninstalled

## Plugin Package Format

### Directories

Built-in plugins:

```text
plugins/builtin/<plugin-id>/
```

External plugins:

```text
data/plugins/external/<plugin-id>/
```

Temporary install workspace:

```text
data/plugins/tmp/
```

Plugin runtime state:

```text
data/plugins/state.json
```

### Zip Layout

```text
<plugin-id>.zip
├── plugin.json
├── plugin_main.py
├── assets/
├── translations/
└── lib/
```

### Manifest

Example:

```json
{
  "id": "qqmusic",
  "name": "QQ Music",
  "version": "1.0.0",
  "api_version": "1",
  "entrypoint": "plugin_main.py",
  "entry_class": "QQMusicPlugin",
  "capabilities": [
    "sidebar",
    "settings_tab",
    "lyrics_source",
    "cover",
    "online_music_provider"
  ],
  "min_app_version": "0.1.0"
}
```

Required fields:

- `id`
- `name`
- `version`
- `api_version`
- `entrypoint`
- `entry_class`
- `capabilities`
- `min_app_version`

Optional first-phase field:

- `max_app_version`

Rejected in first phase:

- dependency declarations
- permission declarations

## SDK Design

### SDK Package

```text
harmony_plugin_api/
├── __init__.py
├── context.py
├── plugin.py
├── manifest.py
├── registry_types.py
├── settings.py
├── storage.py
├── ui.py
├── lyrics.py
├── cover.py
├── online.py
└── media.py
```

### Entry Interface

```python
class HarmonyPlugin:
    plugin_id: str

    def register(self, context: PluginContext) -> None:
        ...

    def unregister(self, context: PluginContext) -> None:
        ...
```

### PluginContext

First-phase context surface:

- `plugin_id`
- `manifest`
- `logger`
- `http`
- `events`
- `storage`
- `settings`
- `ui`
- `services`

### Plugin-Scoped Settings

Plugins do not extend `SettingKey`. They store values under a namespaced prefix:

```text
plugins.<plugin-id>.*
```

Examples:

- `plugins.qqmusic.credential`
- `plugins.qqmusic.quality`
- `plugins.qqmusic.nick`

Benefits:

- no host-level config pollution
- uninstall cleanup is straightforward
- future plugins can coexist without key collisions

### Storage

Each plugin gets private directories:

- data dir
- cache dir
- temp dir

The SDK exposes these paths through `context.storage` instead of having plugins guess host paths.

## Extension Points

### Sidebar Entry

Purpose: allow each music plugin to expose its own first-class navigation entry.

Definition:

- `id`
- `title`
- `icon`
- `order`
- `page_factory(context, parent) -> QWidget`

Implications:

- the host no longer hardcodes a single online music page
- QQ Music registers its own sidebar entry
- future NetEase plugin registers a separate sidebar entry

This matches the requirement to avoid a single shared `在线音乐` host page.

### Settings Tab Extension

Purpose: allow plugins to provide configuration UI in the host settings dialog.

Definition:

- `id`
- `title`
- `order`
- `widget_factory(context, parent) -> QWidget`
- optional lifecycle hooks for save and cancel

Host behavior:

- the settings dialog adds a host-owned `插件` tab for plugin management
- plugin tabs such as `QQ 音乐` are added dynamically from the registry

### Lyrics Source Provider

Purpose: allow plugins to register lyrics sources without editing `LyricsService`.

Definition:

- plugin registers one or more `LyricsSource` implementations through the SDK

Host behavior:

- `LyricsService` collects registered sources from `PluginRegistry`
- source order is registry-driven rather than hardcoded in the host

### Cover Capability

Purpose: allow plugins to contribute artwork lookups.

Definition:

- `register_cover_source(...)`
- `register_artist_cover_source(...)`

Host behavior:

- `CoverService` collects registered cover sources and artist cover sources
- QQ Music plugin provides both track cover and artist cover sources

### Online Music Provider

Purpose: allow a plugin to own an online-music experience end to end.

Definition:

- capability declaration: `online_music_provider`
- provider object registered through the SDK
- provider exposes:
  - root page widget
  - search
  - top lists
  - detail retrieval
  - playback URL lookup
  - lyrics lookup if needed
  - recommendation and favorites capabilities if supported

Host behavior:

- the main window mounts the provider page from the plugin sidebar entry
- playback and download requests are routed back through host bridge services

### Deliberately Excluded Extension Points

The first phase does not support:

- arbitrary menu injection
- arbitrary toolbar injection
- arbitrary patching of host widgets
- direct registration into raw host event bus internals
- direct access to host repositories or services

## Host UI Changes

### Sidebar and Main Window

The host sidebar becomes dynamic:

- core pages remain host-owned
- plugin pages are appended from the registry
- page activation and teardown are handled by the host

Required host refactors:

- remove hardcoded assumptions that online music occupies a fixed page index
- replace fixed QQ and online navigation wiring with registry-driven routing

### Settings Dialog

The settings dialog gains a host-owned `插件` tab.

This tab manages:

- installed plugin list
- version and source display
- enable and disable actions
- install from local zip
- install from URL
- uninstall external plugin
- load error display

Plugin-specific settings remain separate dynamic tabs. For example:

- `插件` tab: host plugin management
- `QQ 音乐` tab: QQ Music plugin login and quality settings

## Compatibility and Failure Handling

### Compatibility Rules

Two compatibility checks are enforced in the first phase:

- `api_version` must match the host-supported plugin API version
- `min_app_version` must be less than or equal to the running Harmony version

If `max_app_version` is present and exceeded:

- the host warns the user
- the host still treats the plugin as installable in the first phase

First phase default: warning only for `max_app_version`.

### Failure Rules

- invalid manifest: reject installation
- missing entrypoint or entry class: reject installation
- import failure: mark plugin as failed and continue host startup
- registration failure: roll back all registrations for that plugin and mark load error
- uninstall failure: keep plugin state unchanged and show the error in the `插件` tab

## Installation, Upgrade, and Removal

### Install From Local Zip

Flow:

1. user selects a zip file in the `插件` tab
2. host extracts into `data/plugins/tmp/`
3. host validates package structure and manifest
4. host performs install-time import audit
5. host copies into `data/plugins/external/<plugin-id>/`
6. host updates `state.json`
7. host optionally enables the plugin immediately

### Install From URL

Flow:

1. user enters a URL in the `插件` tab
2. host downloads the zip into `data/plugins/tmp/`
3. host invokes the same zip install path

The host should show a warning that plugins run trusted Python code and should only be installed from trusted sources.

### Upgrade

Upgrade is an install over an existing external plugin with the same `plugin-id`.

Safe upgrade flow:

1. validate new package in temp directory
2. disable and unload current plugin
3. replace plugin directory only after new package passes validation
4. update state
5. re-enable if it was previously enabled

If upgrade fails after disable:

- keep the old plugin directory untouched when possible
- restore previous state

### Uninstall

Rules:

- only external plugins can be uninstalled
- built-in plugins can only be disabled

Optional uninstall cleanup:

- remove plugin directory
- remove `plugins.<plugin-id>.*` settings
- remove plugin storage directory

Because users accepted re-login and reconfiguration, there is no requirement to preserve or migrate old QQ Music settings.

## Data and DTO Boundaries

QQ Music cannot rely on host internal domain classes if it is to be shipped independently.

The SDK therefore defines plugin-facing DTOs such as:

- `PluginTrack`
- `PluginAlbum`
- `PluginArtist`
- `PluginPlaylist`
- `PluginPlaybackRequest`

Host bridge code converts these DTOs into Harmony internal models only at the integration boundary.

This is required to keep the plugin independently releasable and prevent future host refactors from breaking plugin imports.

## LRCLIB Built-In Plugin Migration

### Scope

Move `LRCLIBLyricsSource` out of host source registration and into a built-in plugin.

### Plugin Capabilities

- `lyrics_source`

### Host Changes

- `LyricsService` stops hardcoding `LRCLIBLyricsSource`
- the built-in LRCLIB plugin registers the source at startup

### Purpose

This is the smallest migration that validates the full plugin path:

- manifest load
- plugin register
- registry consumption
- service integration

It should be completed before the QQ Music migration.

## QQ Music Plugin Migration

### Scope

Move all QQ Music functionality out of the host repository and into a plugin package.

### QQ Plugin Capabilities

- `sidebar`
- `settings_tab`
- `lyrics_source`
- `cover`
- `online_music_provider`

### Code That Moves Into the Plugin

- QQ protocol and API clients from `services/cloud/qqmusic/`
- QQ lyrics and cover helpers from `services/lyrics/qqmusic_lyrics.py`
- QQ lyrics source
- QQ cover source
- QQ artist cover source
- QQ-specific settings UI and QR login UI
- QQ-specific online page logic currently embedded in `ui/views/online_music_view.py`
- QQ-specific recommendation, favorite, completion, and hotkey workers

### Code That Stays in the Host

- plugin runtime
- plugin management UI
- plugin SDK
- host playback, queue, library, and download bridges
- host lyrics and cover aggregators
- host sidebar and settings shells

### Migration Notes

- remove direct QQ imports from `app/bootstrap.py`
- remove QQ-specific fixed tab construction from `ui/dialogs/settings_dialog.py`
- remove QQ-specific fixed page assumptions from `ui/windows/main_window.py`
- replace hardcoded QQ registration in lyrics and cover services with registry-driven source collection
- move plugin settings to `plugins.qqmusic.*`

### Release End State

When the migration is complete:

- the host app starts and runs without QQ Music installed
- installing the QQ Music zip adds a sidebar entry and a settings tab
- uninstalling the QQ Music plugin removes those extensions without breaking host startup

## Future Plugins

This framework is intentionally designed to support additional plugins without special host cases:

- NetEase music plugin as another online music provider
- Baidu Drive plugin
- Quark Drive plugin

The first phase focuses on music and source plugins, but the registry model keeps enough separation to add drive-provider extension points in a separate follow-up design.

## Testing Strategy

### Unit Tests

- manifest parsing and validation
- compatibility checks for `api_version` and `min_app_version`
- install, upgrade, disable, enable, and uninstall flows
- registry rollback on registration failure
- plugin-scoped settings prefix behavior

### Service Tests

- `LyricsService` consumes registered lyrics sources
- `CoverService` consumes registered cover and artist cover sources
- disabling a plugin removes its sources from host aggregation

### UI Tests

- settings dialog shows the host-owned `插件` tab
- plugin management actions update plugin state correctly
- plugin settings tabs appear and disappear dynamically
- plugin sidebar entries appear and disappear dynamically

### Integration Tests

- LRCLIB built-in plugin loads and participates in lyrics search
- QQ Music plugin install adds its sidebar page and settings tab
- host startup succeeds when QQ plugin is absent
- QQ plugin can be disabled and re-enabled without restart corruption

### Regression Guard

Add tests or checks that fail if the QQ plugin imports Harmony internal modules directly.

## Delivery Phases

### Phase 1: Host Plugin Runtime

- add `PluginManager`, `PluginInstaller`, `PluginRegistry`, `PluginStateStore`, `PluginLoader`
- add `harmony_plugin_api`
- add host `插件` tab to settings dialog

### Phase 2: Registry-Driven Consumption

- make lyrics and cover services read from registry
- make main window and sidebar register plugin pages dynamically
- make settings dialog mount plugin tabs dynamically

### Phase 3: LRCLIB Built-In Plugin

- move LRCLIB lyrics source into a built-in plugin
- validate the end-to-end host and plugin flow

### Phase 4: QQ Music Plugin

- move QQ service, UI, sources, and provider logic into a plugin
- remove host direct imports and `qqmusic.*` config helpers

### Phase 5: External Distribution

- package QQ Music as an installable external zip
- verify host works with plugin removed from the repository

## Baseline Quality Note

At the time this design was approved, a baseline run of `uv run pytest tests/` in a fresh worktree was not clean. Existing failures appeared before any plugin-system implementation, including a visible failure in `tests/test_artist_navigation.py::test_artist_navigation` and a later crash around `tests/test_qthread_fix.py::test_main_window_close`.

This does not change the plugin design, but implementation work must treat baseline failures separately from plugin regressions.

## Final Design Decisions

- QQ Music must depend only on the plugin SDK, not on host internals.
- Existing QQ settings do not need migration; users may re-login and reconfigure.
- Each music plugin gets its own sidebar entry instead of contributing into one host-owned online page.
- First phase supports trusted Python plugins only.
- Plugin management lives in a new host-owned `插件` tab inside the existing settings dialog.
- Plugin-specific configuration remains in dynamically registered settings tabs.
- `cover` is a first-class capability and includes both track cover and artist cover source registration.

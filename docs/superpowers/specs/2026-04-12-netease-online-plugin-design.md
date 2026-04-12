# NetEase Online Plugin Design

## Overview

Build a new NetEase online music plugin at `plugins/builtin/netease` that provides the same baseline product shape as the existing QQ Music plugin:

- sidebar page
- settings tab
- online music provider
- logged-in and anonymous browsing
- playback and download support

This plugin is intentionally scoped to online music only. It does not replace the existing built-in `netease_lyrics` and `netease_cover` plugins, and it does not implement NetEase cloud drive features.

Although the first implementation lives under `plugins/builtin/netease`, it must be written with future externalization in mind. The code should stay within plugin boundaries and avoid direct imports from host-private modules such as `services`, `system`, `ui`, or `infrastructure`.

## Goals

- Add a built-in NetEase plugin at `plugins/builtin/netease`.
- Match the QQ Music plugin's baseline user-facing capabilities for online music.
- Support three login flows:
  - cellphone login
  - email login
  - QR code login
- Support logged-in content:
  - daily recommendations
  - liked songs / "I Like"
  - user playlists
  - playlist favorite / unfavorite
  - album favorite / unfavorite
  - artist follow / unfollow
- Support anonymous content:
  - search
  - charts / toplists
  - artist / album / playlist detail
- Support playback, queue insertion, add-to-library, download, and redownload through the existing plugin bridges.
- Keep the plugin portable enough to move from `plugins/builtin/netease` to an external plugin root later with minimal or no code changes.

## Non-Goals

- No NetEase cloud drive support.
- No song upload or cloud matching.
- No comments, MV/video, social features, private messages, podcasts, or other extended NetEase ecosystem features.
- No merge of `netease_lyrics` and `netease_cover` into the new plugin.
- No dependency on `/home/harold/workspace/NeteaseCloudMusicApiEnhanced` as a required local service.
- No Node.js sidecar process.

## Current Context

The repository already has:

- a plugin loader and manifest-based plugin runtime
- a full built-in QQ Music plugin under `plugins/builtin/qqmusic`
- built-in NetEase lyrics and cover plugins:
  - `plugins/builtin/netease_lyrics`
  - `plugins/builtin/netease_cover`

The plugin runtime enforces an import boundary for plugins. Plugins may use `harmony_plugin_api` and plugin context bridges, but may not directly import host-private packages such as:

- `app`
- `domain`
- `services`
- `repositories`
- `infrastructure`
- `system`
- `ui`

This means the new NetEase plugin must own its own UI, client, login flow, mapping logic, and persistence behavior inside the plugin directory.

## Recommended Approach

Implement NetEase as a new built-in plugin that mirrors the product surface of the QQ Music plugin while following external-plugin-safe boundaries.

The plugin should register exactly three capabilities:

- `sidebar`
- `settings_tab`
- `online_music_provider`

It should not register lyrics or cover sources, because those capabilities are already provided by the existing built-in `netease_lyrics` and `netease_cover` plugins.

## Architecture

### Plugin Boundary

`plugins/builtin/netease` is a built-in plugin for now, but it should behave like a future external plugin:

- all functional code lives under the plugin directory
- no direct host-private imports
- no direct imports from `plugins/builtin/qqmusic`
- no assumptions about host-only globals or private runtime singletons

The plugin must interact with the app only through `PluginContext` bridges:

- `context.ui`
- `context.settings`
- `context.storage`
- `context.services`
- `context.runtime`
- `context.http`

### Registration

`plugin_main.py` should register:

- one sidebar entry for the NetEase online page
- one settings tab for NetEase login and preferences
- one online music provider with `provider_id = "netease"`

The manifest should use:

- plugin id: `netease`
- name: `NetEase`
- capabilities: `["sidebar", "settings_tab", "online_music_provider"]`

`requires_restart_on_toggle` should stay `true`, matching the current built-in QQ Music plugin behavior and avoiding partial runtime teardown edge cases for large plugin-owned UI trees.

### Internal Modules

Recommended plugin structure:

```text
plugins/builtin/netease/
├── __init__.py
├── plugin.json
├── plugin_main.py
├── lib/
│   ├── __init__.py
│   ├── adapters.py
│   ├── api.py
│   ├── auth_store.py
│   ├── client.py
│   ├── constants.py
│   ├── errors.py
│   ├── i18n.py
│   ├── login_dialog.py
│   ├── models.py
│   ├── online_detail_view.py
│   ├── online_grid_view.py
│   ├── online_music_view.py
│   ├── online_tracks_list_view.py
│   ├── provider.py
│   ├── qr_login.py
│   └── settings_tab.py
└── translations/
    ├── en.json
    └── zh.json
```

Module responsibilities:

- `api.py`
  - low-level NetEase HTTP endpoint wrappers
  - request params, headers, cookies, csrf extraction
- `client.py`
  - orchestration layer for all NetEase operations
  - login-state validation
  - normalized exceptions
- `auth_store.py`
  - plugin-scoped login persistence
  - cookie storage and cached profile data
- `models.py`
  - typed plugin-local data models for tracks, artists, albums, playlists, and auth state
- `adapters.py`
  - mapping NetEase payloads into normalized dicts / plugin data objects used by the provider and views
- `provider.py`
  - host-facing provider object
  - page creation
  - playback URL lookup
  - download and redownload entrypoints
- `settings_tab.py`
  - quality, download directory, login status, login entrypoints, logout
- `login_dialog.py`
  - cellphone and email login flows
- `qr_login.py`
  - QR code creation and polling
- `online_music_view.py`, `online_detail_view.py`, `online_grid_view.py`, `online_tracks_list_view.py`
  - plugin-owned online browsing UI modeled after the QQ Music product flow
- `i18n.py` and `translations/*`
  - plugin-local strings and localization updates

## Functional Scope

### Login

The first release supports:

- cellphone login
- email login
- QR code login
- login status verification
- logout

Credential persistence must be plugin-scoped. The plugin should store only the data it needs:

- cookie string
- lightweight user profile
- last verified timestamp
- last login method

Recommended settings keys:

- `netease.cookie`
- `netease.user_profile`
- `netease.last_verified_at`
- `netease.last_login_method`
- `netease.quality`
- `netease.download_dir`

### Anonymous Features

Available without login:

- search:
  - songs
  - artists
  - albums
  - playlists
- toplists / charts
- playlist detail
- album detail
- artist detail
- artist albums pagination

### Logged-In Features

Available after successful login:

- daily recommendations
- liked songs entry
- current user's playlist list
- favorite / unfavorite playlist
- favorite / unfavorite album
- follow / unfollow artist

The plugin should treat "liked songs" as a special NetEase playlist-style entry rather than inventing a second host-side favorite model.

## Data Flow

### Login Data Flow

#### Cellphone Login

1. User opens the login dialog from the settings tab or page login affordance.
2. User enters phone number and password or captcha.
3. Plugin validates basic input locally.
4. Plugin hashes password as required by the NetEase API.
5. `api.py` submits the login request.
6. On success, `auth_store.py` persists cookie and user profile.
7. `client.py` immediately verifies login state with a status/profile request.
8. UI refreshes logged-in sections.

#### Email Login

1. User enters email and password.
2. Plugin hashes password.
3. `api.py` submits email login.
4. Success path matches cellphone login: persist, verify, refresh UI.

#### QR Login

1. Plugin requests a QR key.
2. Plugin generates or retrieves the QR image payload.
3. Dialog starts a polling thread owned entirely by the plugin.
4. When login completes, cookie and profile are persisted.
5. Logged-in sections refresh without requiring application restart.

### Online Browsing Flow

1. UI action calls `client.py`.
2. `client.py` delegates to `api.py`.
3. Raw NetEase payloads are normalized through `adapters.py`.
4. View models are rendered in plugin-owned pages.
5. Detail views reuse the same normalized shapes for artist, album, and playlist pages.

### Playback and Download Flow

1. User selects a track from search results, charts, recommendations, or detail pages.
2. Provider uses `provider_id = "netease"` for all host-facing requests.
3. For playback, the provider resolves playback URL information through `client.py`.
4. The provider passes the resolved data through the host media bridge so the existing queue, cache, and library flows remain the source of truth.
5. For downloads, the provider exposes `download_track()` and `redownload_track()` using the standard online provider interface.
6. Downloaded / cached tracks continue to flow through the host's existing media and library integration.

### Lyrics and Cover Flow

The new plugin does not register its own lyrics or cover providers.

Expected behavior:

- the new online provider uses `provider_id = "netease"`
- existing `netease_lyrics` and `netease_cover` plugins remain the source of NetEase lyrics and cover data
- host helpers continue to route lyrics and cover lookups by provider/source id

This preserves separation of responsibilities and avoids duplicate NetEase sources.

## UI Design

### Sidebar Page

The NetEase sidebar page should match the QQ Music plugin's product shape closely enough that users immediately understand the flow.

Main sections:

- search bar
- search tabs:
  - songs
  - artists
  - albums
  - playlists
- toplists / charts area
- logged-in recommendation area
- logged-in favorites / personal area

### Default Home View

Anonymous state:

- toplists visible
- login call-to-action visible
- no personal recommendation sections

Logged-in state:

- toplists visible
- daily recommendations visible
- liked songs visible
- user playlists visible

### Detail View

Use one detail view shell that can render:

- artist detail
- album detail
- playlist detail

Actions:

- follow / unfollow artist
- favorite / unfavorite album
- favorite / unfavorite playlist
- play / queue / add to library / download selected tracks

### Settings Tab

The settings tab should include:

- audio quality selector
- download directory selector
- login status card
- buttons or entrypoints for:
  - cellphone login
  - email login
  - QR code login
  - logout

The tab should be entirely plugin-owned and use plugin-scoped settings only.

## Error Handling

The plugin should define explicit error types in `errors.py`, including:

- `NeteaseAuthExpiredError`
- `NeteaseRequestError`
- `NeteaseRateLimitError`
- `NeteaseLoginError`

Rules:

- login-required requests must fail cleanly and downgrade the UI to logged-out state
- anonymous browsing must keep working even after auth expiry
- request failures should not crash the page
- QR polling timeout or refusal should surface as user-facing status updates, not exceptions escaping to the host

When login expires:

1. `client.py` raises `NeteaseAuthExpiredError`
2. the settings tab and page clear or invalidate cached login state
3. personal sections hide
4. the user is prompted to log in again

## API Coverage

The implementation should be based on Python-side requests modeled after the supported NetEase HTTP endpoints already demonstrated in the reference project, including equivalents for:

- search
- hot search / suggest if needed by the page
- toplist / toplist detail
- playlist detail
- album detail
- artist detail / artist albums
- song playback URL
- lyric lookup helpers when needed for page metadata
- login cellphone
- login email
- QR key / QR create / QR check
- login status
- logout
- recommend songs
- user playlist
- likelist or liked songs equivalent
- playlist subscribe / unsubscribe
- album subscribe / unsubscribe
- artist subscribe / unsubscribe

The reference project is for capability discovery only. The Harmony plugin must implement the necessary requests in Python and must not depend on a locally running Node API service.

## Testing Strategy

Add targeted tests for registration, client behavior, provider behavior, and plugin-safe boundaries.

Recommended tests:

- `tests/test_plugins/test_netease_plugin.py`
  - plugin registers sidebar entry
  - plugin registers settings tab
  - plugin registers online provider
- `tests/test_services/test_netease_client.py`
  - cellphone login payload mapping
  - email login payload mapping
  - QR login polling mapping
  - login-state verification
  - search normalization
  - toplist / detail normalization
  - daily recommendations / liked songs / user playlists normalization
  - auth expiry handling
- `tests/test_services/test_netease_provider.py`
  - provider id is `netease`
  - playback URL info is exposed correctly
  - download and redownload pass provider id through correctly
- `tests/test_ui/test_netease_settings_tab.py`
  - login controls are present
  - status refresh works
  - logout clears state
- `tests/test_ui/test_netease_online_views.py`
  - search results render per tab
  - logged-in sections appear only when authenticated
  - detail actions call the correct client methods
- `tests/test_system/test_plugin_import_guard.py`
  - the NetEase plugin does not import forbidden host-private modules

Recommended verification commands during implementation:

- `uv run pytest tests/test_plugins/test_netease_plugin.py`
- `uv run pytest tests/test_services/test_netease_client.py tests/test_services/test_netease_provider.py`
- `uv run pytest tests/test_ui/test_netease_settings_tab.py tests/test_ui/test_netease_online_views.py`
- `uv run pytest tests/test_system/test_plugin_import_guard.py -k netease`

## Risks and Mitigations

- Import-boundary risk:
  - Keep all implementation inside `plugins/builtin/netease` and rely only on `harmony_plugin_api` plus plugin context bridges.
- Scope growth risk:
  - Explicitly exclude cloud drive, comments, MV/video, and social features from the first release.
- Duplicate NetEase source risk:
  - Do not register lyrics or cover sources from the new plugin.
- Auth fragility risk:
  - Centralize cookie handling, auth verification, and auth-expired downgrades in `client.py` and `auth_store.py`.
- Future externalization risk:
  - Avoid QQ-plugin imports and host-private imports from the start so the directory can later move to an external plugin root with minimal packaging changes.

## File Impact

### Create

- `plugins/builtin/netease/__init__.py`
- `plugins/builtin/netease/plugin.json`
- `plugins/builtin/netease/plugin_main.py`
- `plugins/builtin/netease/lib/__init__.py`
- `plugins/builtin/netease/lib/adapters.py`
- `plugins/builtin/netease/lib/api.py`
- `plugins/builtin/netease/lib/auth_store.py`
- `plugins/builtin/netease/lib/client.py`
- `plugins/builtin/netease/lib/constants.py`
- `plugins/builtin/netease/lib/errors.py`
- `plugins/builtin/netease/lib/i18n.py`
- `plugins/builtin/netease/lib/login_dialog.py`
- `plugins/builtin/netease/lib/models.py`
- `plugins/builtin/netease/lib/online_detail_view.py`
- `plugins/builtin/netease/lib/online_grid_view.py`
- `plugins/builtin/netease/lib/online_music_view.py`
- `plugins/builtin/netease/lib/online_tracks_list_view.py`
- `plugins/builtin/netease/lib/provider.py`
- `plugins/builtin/netease/lib/qr_login.py`
- `plugins/builtin/netease/lib/settings_tab.py`
- `plugins/builtin/netease/translations/en.json`
- `plugins/builtin/netease/translations/zh.json`
- `tests/test_plugins/test_netease_plugin.py`
- `tests/test_services/test_netease_client.py`
- `tests/test_services/test_netease_provider.py`
- `tests/test_ui/test_netease_settings_tab.py`
- `tests/test_ui/test_netease_online_views.py`

### Preserve As-Is

- `plugins/builtin/netease_lyrics/*`
- `plugins/builtin/netease_cover/*`

These existing plugins remain separate built-in integrations and are not merged into the new online plugin.

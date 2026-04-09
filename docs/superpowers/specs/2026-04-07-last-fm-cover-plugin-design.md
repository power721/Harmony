# Last.fm Cover Plugin Design

## Overview

This change moves the host-owned Last.fm album cover source into a built-in plugin.

The goal is to make Last.fm follow the same ownership boundary already used by the new iTunes cover plugin and the existing lyrics plugins. After the migration, the host still queries Last.fm-backed album cover data, but the plugin runtime owns registration and lifecycle.

## Goals

- Move `LastFmCoverSource` into a built-in plugin with manifest id `last_fm_cover`.
- Remove host-owned Last.fm source registration from `CoverService`.
- Preserve current Last.fm album cover search behavior.
- Preserve the current default API key fallback behavior when `LASTFM_API_KEY` is missing or left at the placeholder value.
- Keep Last.fm enabled by default through normal built-in plugin loading.

## Non-Goals

- No new plugin settings tab.
- No new artist-cover source for Last.fm.
- No change to the Last.fm request method, parameters, or matching logic.
- No refactor of unrelated host cover sources beyond removing Last.fm ownership.

## Current State

Last.fm album cover search lives in [`services/sources/cover_sources.py`](/home/harold/workspace/music-player/services/sources/cover_sources.py) as `LastFmCoverSource`.

[`services/metadata/cover_service.py`](/home/harold/workspace/music-player/services/metadata/cover_service.py) still constructs that source directly as a built-in host source, so it does not participate in plugin enable/disable lifecycle.

The current implementation resolves the API key as follows:

- use `LASTFM_API_KEY` when present and not equal to the placeholder value
- otherwise fall back to the built-in default API key

That behavior must remain unchanged after migration.

## Recommended Approach

Create a built-in plugin at `plugins/builtin/last_fm_cover/` and move the Last.fm cover implementation under that directory.

The plugin manifest id should be `last_fm_cover`. The runtime source identifier should remain `lastfm` so returned search results keep the same source label they use today.

## Architecture

### Plugin Layout

Add a built-in plugin directory:

```text
plugins/builtin/last_fm_cover/
├── __init__.py
├── plugin.json
├── plugin_main.py
└── lib/
    ├── __init__.py
    └── cover_source.py
```

### Host Boundary

After migration:

- the host owns `NetEaseCoverSource` as the only built-in album cover source
- the Last.fm implementation lives entirely under `plugins/builtin/last_fm_cover/`
- `CoverService._get_sources()` continues to merge host sources with plugin-registered cover sources

### Plugin Registration

`plugin_main.py` should expose a plugin class with:

- `plugin_id = "last_fm_cover"`
- `register(context)` calling `context.services.register_cover_source(...)`
- `unregister(context)` as a no-op

The manifest should declare:

- `"id": "last_fm_cover"`
- `"capabilities": ["cover"]`

## Runtime Behavior

### Album Cover Search

The plugin cover source should preserve current Last.fm behavior:

- endpoint: `http://ws.audioscrobbler.com/2.0/`
- params: `method=album.getinfo`, `artist`, `album`, `format=json`, plus resolved API key
- API key resolution:
  - use `LASTFM_API_KEY` when present and not equal to `YOUR_LASTFM_API_KEY`
  - otherwise use the current built-in default key
- on a successful album payload, choose the largest available image entry with a non-empty `#text`
- return an empty list on request, JSON, or API errors instead of raising to the host

### Availability Check

The plugin `is_available()` behavior should remain effectively unchanged from today. Because the implementation always has a built-in fallback key, the source continues to report itself as available.

## File Changes

### Create

- `plugins/builtin/last_fm_cover/__init__.py`
- `plugins/builtin/last_fm_cover/plugin.json`
- `plugins/builtin/last_fm_cover/plugin_main.py`
- `plugins/builtin/last_fm_cover/lib/__init__.py`
- `plugins/builtin/last_fm_cover/lib/cover_source.py`
- `tests/test_plugins/test_last_fm_cover_plugin.py`

### Modify

- `services/metadata/cover_service.py`
- `services/sources/cover_sources.py`
- `services/sources/__init__.py`
- `tests/test_services/test_plugin_cover_registry.py`

## Testing

Add or update tests to cover:

- the Last.fm plugin registers one cover source through the plugin context
- the plugin cover source preserves current Last.fm result mapping
- the plugin cover source still falls back to the built-in default API key when the env var is missing or placeholder-valued
- `CoverService._get_builtin_sources()` no longer includes `Last.fm`

Regression commands should focus on the changed area:

- `uv run pytest tests/test_plugins/test_last_fm_cover_plugin.py`
- `uv run pytest tests/test_services/test_plugin_cover_registry.py`

## Risks and Mitigations

- Behavior regression risk in API key selection: preserve the current key-resolution logic exactly, including placeholder detection and built-in fallback key.
- Hidden host dependency risk: remove all host imports and exports of `LastFmCoverSource`.
- Scope creep risk from plugin settings: explicitly keep this migration limited to ownership and registration.

## Scope Check

This design is intentionally narrow. It changes only Last.fm album cover ownership and the associated tests. It does not introduce new UI, new settings, or new cover-matching behavior.

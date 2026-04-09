# iTunes Cover Plugin Design

## Overview

This change moves the host-owned iTunes album cover source and iTunes artist cover source into a built-in plugin.

The goal is to make iTunes follow the same ownership boundary already used by built-in lyrics and QQ Music plugin features. After the migration, the host still queries iTunes-backed cover data, but the plugin runtime owns registration and lifecycle.

## Goals

- Move `ITunesCoverSource` into a built-in plugin with manifest id `itunes_cover`.
- Move `ITunesArtistCoverSource` into the same built-in plugin.
- Remove host-owned iTunes source registration from `CoverService`.
- Preserve existing iTunes search behavior, including enlarged artwork URLs and artist de-duplication.
- Keep iTunes enabled by default through normal built-in plugin loading.

## Non-Goals

- No new plugin settings tab or sidebar page.
- No change to iTunes search endpoints or query parameters.
- No refactor of unrelated host cover sources beyond removing iTunes ownership.

## Current State

iTunes album cover search lives in [`services/sources/cover_sources.py`](/home/harold/workspace/music-player/services/sources/cover_sources.py) as `ITunesCoverSource`.

iTunes artist cover search lives in [`services/sources/artist_cover_sources.py`](/home/harold/workspace/music-player/services/sources/artist_cover_sources.py) as `ITunesArtistCoverSource`.

[`services/metadata/cover_service.py`](/home/harold/workspace/music-player/services/metadata/cover_service.py) still constructs both sources directly as built-in host sources, so they do not participate in plugin enable/disable lifecycle.

## Recommended Approach

Create a built-in plugin at `plugins/builtin/itunes_cover/` and move both iTunes source implementations under that directory.

The plugin manifest id should be `itunes_cover`. The runtime source identifiers should remain iTunes-specific values so result payloads and logging continue to describe the source as iTunes.

## Architecture

### Plugin Layout

Add a built-in plugin directory:

```text
plugins/builtin/itunes_cover/
├── __init__.py
├── plugin.json
├── plugin_main.py
└── lib/
    ├── __init__.py
    ├── artist_cover_source.py
    └── cover_source.py
```

### Host Boundary

After migration:

- the host owns `NetEaseCoverSource` and `LastFmCoverSource` as built-in album cover sources
- the host owns `NetEaseArtistCoverSource` as a built-in artist cover source
- the iTunes implementations live entirely under `plugins/builtin/itunes_cover/`
- `CoverService` continues to merge host sources with plugin-registered cover and artist-cover sources

### Plugin Registration

`plugin_main.py` should expose a plugin class with:

- `plugin_id = "itunes_cover"`
- `register(context)` calling both `context.services.register_cover_source(...)` and `context.services.register_artist_cover_source(...)`
- `unregister(context)` as a no-op

The manifest should declare:

- `"id": "itunes_cover"`
- `"capabilities": ["cover"]`

The existing `cover` plugin capability already covers cover-related registrations, including artist cover sources.

## Runtime Behavior

### Album Cover Search

The plugin album cover source should preserve current iTunes behavior:

- endpoint: `https://itunes.apple.com/search`
- album search using `term = "{artist} {album or title}"`, `media = "music"`, `entity = "album"`, `limit = 5`
- optional album-only retry when `album` is provided
- transform `artworkUrl100` into a larger image by replacing `100x100` with `600x600`
- return an empty list on request or decoding errors instead of raising to the host

### Artist Cover Search

The plugin artist cover source should preserve current iTunes behavior:

- endpoint: `https://itunes.apple.com/search`
- query using `term = artist_name`, `media = "music"`, `entity = "album"`, `limit = limit`
- de-duplicate results by lower-cased artist name
- enlarge `artworkUrl100` to `600x600`
- return an empty list on request or decoding errors instead of raising to the host

## File Changes

### Create

- `plugins/builtin/itunes_cover/__init__.py`
- `plugins/builtin/itunes_cover/plugin.json`
- `plugins/builtin/itunes_cover/plugin_main.py`
- `plugins/builtin/itunes_cover/lib/__init__.py`
- `plugins/builtin/itunes_cover/lib/cover_source.py`
- `plugins/builtin/itunes_cover/lib/artist_cover_source.py`
- `tests/test_plugins/test_itunes_cover_plugin.py`

### Modify

- `services/metadata/cover_service.py`
- `services/sources/cover_sources.py`
- `services/sources/artist_cover_sources.py`
- `services/sources/__init__.py`
- `tests/test_services/test_plugin_cover_registry.py`

## Testing

Add or update tests to cover:

- the iTunes plugin registers both a cover source and an artist cover source
- the plugin album cover source keeps current iTunes result mapping
- the plugin artist cover source de-duplicates artists and enlarges artwork URLs
- `CoverService._get_builtin_sources()` and `_get_builtin_artist_sources()` no longer include iTunes

Regression commands should focus on the changed area:

- `uv run pytest tests/test_plugins/test_itunes_cover_plugin.py`
- `uv run pytest tests/test_services/test_plugin_cover_registry.py`

## Risks and Mitigations

- Plugin load risk: keep the plugin minimal and mirror the existing built-in plugin structure exactly.
- Behavior regression risk in iTunes result mapping: preserve the current request parameters and artwork URL transformation logic.
- Hidden host dependency risk: remove all host imports and exports of the migrated iTunes source classes.

## Scope Check

This design is intentionally narrow. It changes only iTunes cover ownership and associated tests. It does not introduce new plugin UI, new settings, or new cover-matching logic.

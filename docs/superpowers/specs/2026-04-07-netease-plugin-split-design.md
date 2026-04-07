# NetEase Plugin Split Design

## Overview

This change moves the host-owned NetEase integrations out of the built-in source lists and into two built-in plugins:

- a lyrics plugin for NetEase lyrics search and download
- a cover plugin for NetEase album cover and artist cover search

The goal is to make NetEase follow the same ownership boundary already used by the existing built-in lyrics and cover plugins. After the migration, the host still exposes the same end-user behavior, but the plugin runtime owns registration and lifecycle.

## Goals

- Move `NetEaseLyricsSource` into a built-in lyrics plugin.
- Move `NetEaseCoverSource` and `NetEaseArtistCoverSource` into a built-in cover plugin.
- Remove all host-owned NetEase source registration from `LyricsService` and `CoverService`.
- Preserve current NetEase request behavior, result mapping, and source identifiers.
- Keep NetEase enabled by default through normal built-in plugin loading.

## Non-Goals

- No NetEase settings tab.
- No NetEase sidebar page or online music provider.
- No change to NetEase API endpoints, request parameters, or result matching rules.
- No unrelated refactor of non-NetEase host sources or plugin registry behavior.

## Current State

NetEase is still implemented as host-owned sources:

- [`services/sources/lyrics_sources.py`](/home/harold/workspace/music-player/services/sources/lyrics_sources.py) defines `NetEaseLyricsSource`
- [`services/sources/cover_sources.py`](/home/harold/workspace/music-player/services/sources/cover_sources.py) defines `NetEaseCoverSource`
- [`services/sources/artist_cover_sources.py`](/home/harold/workspace/music-player/services/sources/artist_cover_sources.py) defines `NetEaseArtistCoverSource`

The host currently wires those sources directly:

- [`services/lyrics/lyrics_service.py`](/home/harold/workspace/music-player/services/lyrics/lyrics_service.py) constructs `NetEaseLyricsSource` in `_get_builtin_sources()`
- [`services/metadata/cover_service.py`](/home/harold/workspace/music-player/services/metadata/cover_service.py) constructs `NetEaseCoverSource` and `NetEaseArtistCoverSource` in the built-in source helpers

This means NetEase does not participate in plugin enable/disable lifecycle even though the application already supports plugin-provided lyrics, cover, and artist-cover sources.

## Recommended Approach

Create two built-in plugins and migrate NetEase ownership into them:

- `plugins/builtin/netease_lyrics/`
- `plugins/builtin/netease_cover/`

Use a small shared NetEase helper module for request headers, search requests, and field normalization so the lyrics and cover plugins do not duplicate low-level API logic.

The plugin manifest ids should be distinct from the runtime result source identifier:

- plugin ids: `netease_lyrics`, `netease_cover`
- runtime result source: `netease`

This split is intentional:

- manifest ids control plugin discovery, enable state, and plugin management UI
- runtime `source = "netease"` preserves compatibility with existing matching, download, and UI flows

## Architecture

### Plugin Layout

Add built-in plugin directories:

```text
plugins/builtin/netease_lyrics/
├── __init__.py
├── plugin.json
├── plugin_main.py
└── lib/
    ├── __init__.py
    └── lyrics_source.py

plugins/builtin/netease_cover/
├── __init__.py
├── plugin.json
├── plugin_main.py
└── lib/
    ├── __init__.py
    ├── artist_cover_source.py
    └── cover_source.py
```

Add a shared helper package at `plugins/builtin/netease_shared/` for NetEase-specific request and parsing code. This package is not a plugin and should not include `plugin.json`.

The helper must stay narrow:

- request headers
- shared search request helper
- shared field extraction and image URL normalization

It must not own plugin registration or host integration.

### Host Boundary

After migration:

- `LyricsService` no longer owns any built-in NetEase lyrics source
- `CoverService` no longer owns any built-in NetEase album cover or artist cover source
- NetEase behavior enters the app only through plugin registration
- the host still owns orchestration, result merging, matching, caching, and file download

### Plugin Registration

`plugins/builtin/netease_lyrics/plugin_main.py` should expose a plugin class with:

- `plugin_id = "netease_lyrics"`
- `register(context)` calling `context.services.register_lyrics_source(...)`
- `unregister(context)` as a no-op

The manifest should declare:

- `"id": "netease_lyrics"`
- `"capabilities": ["lyrics_source"]`

`plugins/builtin/netease_cover/plugin_main.py` should expose a plugin class with:

- `plugin_id = "netease_cover"`
- `register(context)` calling `context.services.register_cover_source(...)`
- `register(context)` also calling `context.services.register_artist_cover_source(...)`
- `unregister(context)` as a no-op

The manifest should declare:

- `"id": "netease_cover"`
- `"capabilities": ["cover", "artist_cover"]`

Because built-in plugins default to enabled unless persisted otherwise, NetEase remains active after the migration without extra host logic.

## Runtime Behavior

### Source Identity

The migrated plugin sources must preserve current user-visible and runtime identifiers:

- lyrics source display name remains `NetEase`
- cover source display name remains `NetEase`
- artist cover source display name remains `NetEase`
- returned search results keep `source = "netease"`

This preserves compatibility with:

- lyrics download routing in [`services/lyrics/lyrics_service.py`](/home/harold/workspace/music-player/services/lyrics/lyrics_service.py)
- source priority and matching logic in `utils/match_scorer.py`
- existing UI source labels and result handling

### Lyrics Flow

The lyrics plugin should preserve the current NetEase flow:

- search endpoint: `https://music.163.com/api/search/get/web`
- search params: `s`, `type=1`, `limit`
- lyrics endpoint: `https://music.163.com/api/song/lyric`
- first request path prefers YRC when present
- fallback request path returns LRC when YRC is absent

Search results should continue to map:

- `id` from song id
- `title`, `artist`, `album`
- `duration` converted from milliseconds to seconds
- `cover_url` from album picture fields
- `supports_yrc = True`

On request or decoding failures, the plugin should return empty results or `None` instead of raising to the host.

### Cover Flow

The cover plugin should preserve the current NetEase album cover flow:

- use `https://music.163.com/api/search/get/web`
- first perform album search with `type=10`
- then perform song search with `type=1`
- normalize album artwork URLs to request high-resolution images when possible

Album cover search results should continue to map:

- `title`
- `artist`
- `album`
- `duration` when available from song results
- `source = "netease"`
- `id`
- `cover_url`

The host `CoverService` continues to own candidate ranking, downloading, and cache persistence.

### Artist Cover Flow

The cover plugin should also preserve the current NetEase artist cover flow:

- use `https://music.163.com/api/search/get/web`
- search with `type=100`
- keep `source = "netease"`
- normalize artist image URLs to request high-resolution images when possible

Artist cover results should continue to map:

- `id`
- `name`
- `cover_url`
- `album_count`
- `source = "netease"`

## File Changes

### Create

- `plugins/builtin/netease_lyrics/__init__.py`
- `plugins/builtin/netease_lyrics/plugin.json`
- `plugins/builtin/netease_lyrics/plugin_main.py`
- `plugins/builtin/netease_lyrics/lib/__init__.py`
- `plugins/builtin/netease_lyrics/lib/lyrics_source.py`
- `plugins/builtin/netease_cover/__init__.py`
- `plugins/builtin/netease_cover/plugin.json`
- `plugins/builtin/netease_cover/plugin_main.py`
- `plugins/builtin/netease_cover/lib/__init__.py`
- `plugins/builtin/netease_cover/lib/cover_source.py`
- `plugins/builtin/netease_cover/lib/artist_cover_source.py`
- `plugins/builtin/netease_shared/__init__.py`
- `plugins/builtin/netease_shared/common.py`
- `tests/test_plugins/test_netease_lyrics_plugin.py`
- `tests/test_plugins/test_netease_cover_plugin.py`

### Modify

- `services/lyrics/lyrics_service.py`
- `services/metadata/cover_service.py`
- `services/sources/lyrics_sources.py`
- `services/sources/cover_sources.py`
- `services/sources/artist_cover_sources.py`
- `services/sources/__init__.py`
- `tests/test_services/test_plugin_lyrics_registry.py`
- `tests/test_services/test_plugin_cover_registry.py`

## Testing

Add or update tests to cover:

- the NetEase lyrics plugin registers one lyrics source through the plugin context
- the NetEase cover plugin registers one cover source and one artist-cover source
- NetEase lyrics search preserves current result mapping, including `supports_yrc`
- NetEase lyrics download preserves YRC-first and LRC-fallback behavior
- NetEase cover search preserves album-search and song-search result mapping
- NetEase artist cover search preserves current result mapping
- `LyricsService._get_builtin_sources()` no longer includes `NetEase`
- `CoverService._get_builtin_sources()` and `_get_builtin_artist_sources()` no longer include `NetEase`

Regression commands should focus on the changed area:

- `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py`
- `uv run pytest tests/test_plugins/test_netease_cover_plugin.py`
- `uv run pytest tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py`

## Risks and Mitigations

- Duplicate-results risk: if host-owned NetEase source registration is not fully removed, the UI will show repeated NetEase entries. Remove all NetEase source construction from host built-in source lists.
- Compatibility risk from source identifiers: keep plugin manifest ids separate from runtime `source = "netease"`.
- Shared-helper coupling risk: keep the shared NetEase helper limited to pure request and parsing utilities so the two plugins do not depend on each other's plugin classes or context.
- Scope creep risk into online music features: explicitly keep this migration limited to lyrics, album cover, and artist cover ownership.

## Scope Check

This design is intentionally narrow. It changes only NetEase ownership boundaries and the associated tests. It does not add new UI, new plugin settings, or new NetEase online music features.

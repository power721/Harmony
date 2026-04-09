# QQMusic Provider Unification Design

## Overview

This change keeps the built-in QQ Music lyrics and cover plugin sources registered through the host plugin system, but moves their runtime data access behind `QQMusicOnlineProvider`.

The goal is to stop `QQMusicLyricsPluginSource` and `QQMusicCoverPluginSource` from calling `QQMusicPluginAPI` directly. Instead, the provider becomes the single plugin-owned entry point for QQ Music search, lyrics lookup, and cover URL resolution.

This preserves current host-facing source contracts while restoring the intended priority:

- prefer local QQ Music client behavior when available
- keep remote API fallback when local client data is unavailable

## Goals

- Make `QQMusicLyricsPluginSource` use `QQMusicOnlineProvider` instead of `QQMusicPluginAPI`.
- Make `QQMusicCoverPluginSource` use `QQMusicOnlineProvider` instead of `QQMusicPluginAPI`.
- Extend `QQMusicOnlineProvider` with the thin lyrics and cover methods needed by those sources.
- Preserve current plugin registration and host helper contracts.
- Preserve current result source identity as `qqmusic`.
- Prefer local QQ Music client behavior before remote fallback for lyrics and cover resolution.

## Non-Goals

- No change to plugin manifest structure or plugin registration shape.
- No change to `QQMusicArtistCoverPluginSource` in this iteration.
- No change to host service orchestration in `LyricsService` or `CoverService`.
- No broad refactor of `QQMusicPluginClient`, `QQMusicService`, or the legacy online page.
- No attempt to remove remote API fallback entirely.

## Current State

QQ Music is already partially unified around plugin-owned provider code:

- [`plugins/builtin/qqmusic/lib/provider.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/provider.py) exposes `QQMusicOnlineProvider`
- [`plugins/builtin/qqmusic/lib/client.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/client.py) already prefers local QQ Music service search before remote API fallback

But the lyrics and cover source adapters still bypass that provider:

- [`plugins/builtin/qqmusic/lib/lyrics_source.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/lyrics_source.py) instantiates `QQMusicPluginAPI` directly
- [`plugins/builtin/qqmusic/lib/cover_source.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/cover_source.py) instantiates `QQMusicPluginAPI` directly

As a result, plugin source requests for lyrics and album artwork do not follow the same local-first behavior already used by the online provider search path.

## Recommended Approach

Keep the source classes as host-visible adapters and move the data access boundary inward:

- `QQMusicLyricsPluginSource` becomes a mapping layer over `QQMusicOnlineProvider`
- `QQMusicCoverPluginSource` becomes a mapping layer over `QQMusicOnlineProvider`
- `QQMusicOnlineProvider` becomes the only plugin-owned entry point that source adapters call for QQ Music runtime data

This is intentionally narrower than moving host service contracts to the provider directly. The host still discovers and invokes lyrics and cover sources the same way it does now. Only the plugin-internal dependency direction changes.

## Architecture

### Ownership Boundary

After this change:

- host code still registers and calls lyrics and cover sources through plugin service registries
- source objects still expose the same methods expected by host services and online cover helpers
- the provider owns QQ Music runtime lookup decisions inside the plugin

The new dependency direction is:

`QQMusicLyricsPluginSource` -> `QQMusicOnlineProvider`

`QQMusicCoverPluginSource` -> `QQMusicOnlineProvider`

`QQMusicOnlineProvider` -> `QQMusicPluginClient`

`QQMusicPluginClient` -> local QQ Music service first where supported, then remote API fallback

### Why Not Use `QQMusicPluginClient` Directly

Direct source-to-client wiring would also fix the local-first issue, but it would keep QQ Music plugin entry points split across multiple internal abstractions. Using the provider keeps one plugin-owned façade for:

- online page behavior
- search
- playback URL lookup
- lyrics lookup
- cover URL resolution

That gives the plugin one consistent surface for future QQ Music integration work.

## Runtime Behavior

### Lyrics Source Flow

`QQMusicLyricsPluginSource.search()` should:

- build the same search keyword it uses today
- call `QQMusicOnlineProvider.search(..., search_type="song")`
- accept either normalized `{"tracks": [...]}` payloads or an empty result
- map returned track dictionaries into `PluginLyricsResult`

Field mapping should stay compatible with current behavior:

- `song_id` from `mid`
- `title` from `title` or `name`
- `artist` from `artist` or `singer`
- `album` from normalized `album` fields
- `duration` from `duration` or `interval`
- `source = "qqmusic"`
- `cover_url` from provider-level cover resolution

`QQMusicLyricsPluginSource.get_lyrics()` should call a new provider method such as `get_lyrics(song_mid)` and return:

- QRC content first when present
- plain lyric content second
- `None` on failure or when both are missing

This keeps the source contract simple while preserving richer local lyric data when available.

### Cover Source Flow

`QQMusicCoverPluginSource.search()` should:

- keep the current keyword construction
- call `QQMusicOnlineProvider.search(..., search_type="song")`
- map normalized track dictionaries into `PluginCoverResult`

Field mapping should stay compatible with current behavior:

- `item_id` from `mid`
- `title` from `title` or `name`
- `artist` from normalized artist fields
- `album` from normalized album fields
- `duration` from `duration` or `interval`
- `source = "qqmusic"`
- `extra_id` from `album_mid`
- `cover_url` may remain `None` in search results

`QQMusicCoverPluginSource.get_cover_url()` should call a new provider method such as `get_cover_url(mid=None, album_mid=None, size=500)`.

### Provider Lyrics Resolution

`QQMusicOnlineProvider` should expose a thin lyrics method that delegates to plugin-owned internals in this order:

1. Try local QQ Music service lyrics when a client/service path is available.
2. Prefer returned `qrc` content.
3. Fall back to returned `lyric` content.
4. If local lookup is unavailable or empty, fall back to existing remote API lyrics lookup.

The provider should swallow plugin-internal request failures and return `None`, matching current source behavior.

### Provider Cover Resolution

`QQMusicOnlineProvider` should expose a thin cover method that resolves URLs in this order:

1. If `album_mid` is already present, build the `y.gtimg.cn` album cover URL directly.
2. If only `mid` is present, try a local client-backed detail lookup to derive `album_mid`.
3. If local lookup cannot produce an `album_mid`, fall back to the existing remote API cover helper.
4. Return `None` if no path can produce a usable URL.

This keeps cover lookup fast when the track mapping already includes album metadata while preserving current remote fallback.

### Search Normalization

This design assumes search normalization continues to live in the existing provider/client stack. The lyrics and cover sources should not reimplement low-level QQ Music response parsing beyond adapting normalized provider payloads into plugin API result objects.

## File Changes

### Update

- [`plugins/builtin/qqmusic/lib/provider.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/provider.py)
- [`plugins/builtin/qqmusic/lib/lyrics_source.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/lyrics_source.py)
- [`plugins/builtin/qqmusic/lib/cover_source.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/cover_source.py)
- [`tests/test_services/test_qqmusic_plugin_source_adapters.py`](/home/harold/workspace/music-player/tests/test_services/test_qqmusic_plugin_source_adapters.py)

### Likely Additional Test Updates

- [`tests/test_services/test_lyrics_sources_perf_paths.py`](/home/harold/workspace/music-player/tests/test_services/test_lyrics_sources_perf_paths.py)
- [`tests/test_plugins/test_qqmusic_plugin.py`](/home/harold/workspace/music-player/tests/test_plugins/test_qqmusic_plugin.py)

## Testing Strategy

Use TDD and shift tests toward provider delegation.

### Source Adapter Tests

Add or update tests to verify:

- lyrics source search delegates through provider-backed search data
- lyrics source lyric download delegates through provider-backed lyric lookup
- cover source search delegates through provider-backed search data
- cover source cover URL lookup delegates through provider-backed cover lookup

These tests should stop asserting direct use of `QQMusicPluginAPI` from the source classes.

### Provider Tests

Add provider-focused tests to verify:

- provider lyric lookup prefers local QQ Music service `qrc`
- provider lyric lookup falls back from `qrc` to plain lyric
- provider lyric lookup falls back to remote API when local path yields no lyric
- provider cover lookup uses direct album URL generation when `album_mid` exists
- provider cover lookup can derive cover URL from a song `mid` through local detail data
- provider cover lookup falls back to remote helper when local detail lookup does not help

### Regression Scope

Run QQ Music plugin tests that cover:

- provider behavior
- source adapter behavior
- plugin registration
- cover helper integration

## Risks

- `QQMusicOnlineProvider` currently does not expose lyrics or cover methods, so the new API surface must stay narrow and avoid duplicating client logic.
- Local lyric/detail responses may not be shaped exactly like search responses, so provider methods must normalize only what source adapters need.
- Some tests currently patch `QQMusicPluginAPI` directly. Those tests will need to move up one abstraction level so they verify behavior rather than an old implementation detail.

## Open Decisions

The current recommendation is to leave `QQMusicArtistCoverPluginSource` unchanged for now. It already works against normalized artist search payloads, and changing it in the same step would widen the scope without being required by the reported issue.

If later work wants full provider unification for artist cover search too, it can follow the same pattern in a separate change.

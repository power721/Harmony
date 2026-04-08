# QQMusic Plugin Refactor Design

**Date**: 2026-04-08
**Scope**: `plugins/builtin/qqmusic` internal structure and tests
**Strategy**: medium refactor, no host-facing behavior change

---

## Problem

The built-in QQ Music plugin currently works, but its internal structure makes further changes expensive:

- `lib/qqmusic_service.py` is very large and mixes request orchestration, response parsing, and plugin-facing data shaping.
- `lib/qqmusic_client.py` is a low-level HTTP client, but upstream modules still duplicate result normalization and fallback behavior.
- `lib/client.py`, `lib/provider.py`, and `lib/api.py` each contain overlapping normalization, cover resolution, lyric selection, and section-building logic.
- Pure data transformation code is embedded inside runtime classes, which makes the code harder to test and encourages repeated parsing rules.
- Some private paths look legacy or duplicated, but the duplication is spread across several modules, so it is hard to tell which path is authoritative.

The main maintainability issue is not one broken API. It is that transport, orchestration, fallback policy, and result adaptation are interleaved across multiple files.

## Goals

- Keep plugin registration and host-facing interfaces stable.
- Reassign responsibilities inside `plugins/builtin/qqmusic/lib` so each layer has one clear purpose.
- Extract repeated pure transformation logic into small helper modules with focused tests.
- Reduce direct payload parsing inside `provider.py` and `client.py`.
- Remove obviously duplicated or now-redundant private helper paths during the refactor.
- Preserve current runtime behavior for search, detail, lyrics, covers, recommendations, favorites, and downloads.

## Non-Goals

- No redesign of the QQ Music UI views.
- No migration of all plugin data objects to dataclasses.
- No conversion of the plugin stack to async I/O.
- No protocol or contract changes in host plugin registries.
- No broad cleanup outside `plugins/builtin/qqmusic` and its related tests.

## Current State

The plugin currently has four implicit layers, but they overlap:

- [`plugins/builtin/qqmusic/plugin_main.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/plugin_main.py) registers plugin capabilities.
- [`plugins/builtin/qqmusic/lib/provider.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/provider.py) acts as the host-facing online provider, but also contains media lookup details and fallback parsing.
- [`plugins/builtin/qqmusic/lib/client.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/client.py) chooses between QQ Music direct access and remote API fallback, but also owns normalization helpers and section formatting.
- [`plugins/builtin/qqmusic/lib/qqmusic_service.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/qqmusic_service.py) wraps direct QQ Music access, but still mixes transport result decoding with plugin-facing shaping.
- [`plugins/builtin/qqmusic/lib/api.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/api.py) talks to the public remote fallback API, but also performs its own formatting logic that overlaps with `client.py`.

This produces three specific maintenance costs:

1. the same data shape rules exist in more than one file
2. fallback behavior is hard to reason about because selection and shaping are mixed together
3. tests are forced to patch implementation details instead of stable responsibilities

## Recommended Approach

Keep the existing external entry points, but rebuild the plugin internals around a stricter split:

- `provider.py` remains the plugin integration entry point
- `client.py` becomes the orchestration layer only
- `qqmusic_service.py` stays the direct QQ Music business wrapper
- `api.py` stays the remote fallback transport wrapper
- repeated pure logic moves into small helper modules

This is the smallest refactor that materially improves maintainability without turning into a plugin rewrite.

## Architecture

### Target Dependency Direction

After the refactor, the intended dependency flow is:

`plugin_main.py` / source adapters / UI entry points -> `provider.py`

`provider.py` -> `client.py`

`client.py` -> `qqmusic_service.py` / `api.py` / helper modules

`qqmusic_service.py` -> `qqmusic_client.py` / helper modules

`api.py` -> helper modules

Helper modules must stay pure: no context access, no network calls, no Qt dependencies.

### Layer Responsibilities

#### Provider Layer

[`plugins/builtin/qqmusic/lib/provider.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/provider.py) should only own:

- host-visible provider methods
- page creation and download service wiring
- delegation to the client for runtime data access

It should stop owning low-level parsing such as:

- extracting `album_mid` from detail payloads
- choosing between `qrc` and plain lyric payloads
- constructing media fallback decisions inline

#### Orchestration Layer

[`plugins/builtin/qqmusic/lib/client.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/client.py) should become the single place that decides:

- whether direct QQ Music service is available
- whether a remote API fallback should be used
- which normalized shape is returned upward

It should not embed large formatting helpers. Instead it should call dedicated normalizers/builders.

#### Direct QQ Music Service Layer

[`plugins/builtin/qqmusic/lib/qqmusic_service.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/qqmusic_service.py) should keep its public methods, but internally it should focus on:

- invoking `QQMusicClient`
- collecting related QQ Music responses
- returning service-level dictionaries that are already coherent

It should stop duplicating generic list/song formatting logic that can be expressed as pure helpers.

#### Remote Fallback API Layer

[`plugins/builtin/qqmusic/lib/api.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/api.py) should only do:

- HTTP requests to the public fallback API
- minimal extraction of payload roots
- normalization through shared helper functions

That keeps the API wrapper transport-focused instead of becoming another formatting authority.

## New Internal Modules

### `lib/media_helpers.py`

This module should contain pure media-related helpers now spread across runtime classes:

- build album cover URL from `album_mid`
- build artist cover URL from `singer_mid`
- extract `album_mid` from heterogeneous song/detail payloads
- choose lyric content in priority order: `qrc` first, plain lyric second

Expected consumers:

- `provider.py`
- `client.py`
- `api.py`

### `lib/search_normalizers.py`

This module should own result normalization rules that are currently duplicated:

- normalize search songs from direct QQ Music payloads
- normalize search songs from remote API payloads
- normalize detail songs
- normalize top list track payloads
- normalize album, artist, and playlist search entries

Expected result shapes stay compatible with current callers, for example:

- `{"tracks": [...], "total": N}`
- `{"artists": [...], "total": N}`
- `{"albums": [...], "total": N}`
- `{"playlists": [...], "total": N}`

### `lib/section_builders.py`

This module should own section/card building now mixed into `client.py`:

- recommendation section assembly
- favorites section assembly
- cover selection from heterogeneous items

This makes the `client.py` path read like orchestration code rather than a mixture of network policy and UI card formatting.

## File Changes

### Add

- [`plugins/builtin/qqmusic/lib/media_helpers.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/media_helpers.py)
- [`plugins/builtin/qqmusic/lib/search_normalizers.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/search_normalizers.py)
- [`plugins/builtin/qqmusic/lib/section_builders.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/section_builders.py)

### Update

- [`plugins/builtin/qqmusic/lib/provider.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/provider.py)
- [`plugins/builtin/qqmusic/lib/client.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/client.py)
- [`plugins/builtin/qqmusic/lib/qqmusic_service.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/qqmusic_service.py)
- [`plugins/builtin/qqmusic/lib/api.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/lib/api.py)
- [`plugins/builtin/qqmusic/plugin_main.py`](/home/harold/workspace/music-player/plugins/builtin/qqmusic/plugin_main.py) only if import cleanup or construction simplification is needed
- related QQ Music tests under [`tests/`](/home/harold/workspace/music-player/tests/)

### Deletions / Reductions

The refactor should remove duplicated private helpers after the shared modules are introduced. Expected examples:

- `QQMusicOnlineProvider._build_album_cover_url`
- `QQMusicOnlineProvider._extract_album_mid_from_song_detail`
- `QQMusicPluginClient._normalize_detail_song`
- `QQMusicPluginClient._normalize_top_list_track`
- `QQMusicPluginClient._pick_cover`
- `QQMusicPluginAPI._format_song_item`
- any now-unused private formatting path in `qqmusic_service.py` that duplicates the shared normalizers

Deletions should only happen after tests prove the shared helper path is covering the same behavior.

## Runtime Behavior Rules

These rules should not change during the refactor:

- search continues to prefer direct QQ Music service when available, then falls back to remote API
- lyrics continue to prefer richer local data when available, then fall back to remote API
- cover lookup continues to use direct album URL construction when enough metadata is present
- recommendations and favorites still return the same section structure expected by the UI
- downloads still use the provider-owned online download service path

The point is structural cleanup, not a policy rewrite.

## Error Handling Strategy

The refactor should make error boundaries clearer:

- helper modules do not swallow exceptions; they only transform data
- `client.py` handles source selection and fallback when a source request fails or returns no useful data
- `provider.py` remains defensive toward host/UI callers and returns `None`, `[]`, or empty payloads where current behavior already does that

This keeps exception handling at the orchestration boundary instead of scattering it through every formatting helper.

## Testing Strategy

### New Helper Tests

Add unit tests for:

- album and artist cover URL builders
- lyric payload selection priority
- album MID extraction from multiple payload shapes
- search result normalization for song, artist, album, and playlist payloads
- top list and detail song normalization
- recommendation/favorites section assembly and cover selection

### Existing Behavior Tests

Keep and adjust existing QQ Music tests so they assert stable behavior instead of private implementation details:

- [`tests/test_plugins/test_qqmusic_plugin.py`](/home/harold/workspace/music-player/tests/test_plugins/test_qqmusic_plugin.py)
- [`tests/test_services/test_qqmusic_plugin_source_adapters.py`](/home/harold/workspace/music-player/tests/test_services/test_qqmusic_plugin_source_adapters.py)
- [`tests/test_services/test_qqmusic_service_perf_paths.py`](/home/harold/workspace/music-player/tests/test_services/test_qqmusic_service_perf_paths.py)
- other QQ Music provider/UI tests that already cover fallback expectations

### Validation Scope

At minimum, validation should cover:

- helper tests
- QQ Music plugin tests
- QQ Music service/provider tests

The test suite should confirm that the plugin still exposes the same normalized data shapes to its callers after the refactor.

## Risks

- Some duplicated code may differ in subtle edge-case behavior even when it looks equivalent. The new helpers must codify the authoritative behavior before old paths are removed.
- `qqmusic_service.py` is large enough that moving logic out of it can accidentally change data shape if tests do not pin existing outputs.
- `provider.py` currently knows more about lyrics and cover fallback than it should. Moving that logic down must preserve the existing local-first ordering.
- Tests that patch private methods will become brittle during this change and should be rewritten early.

## Design Constraints

- Keep the plugin's host-facing contracts stable.
- Prefer additive extraction before deletion: move logic into helpers, redirect callers, then remove dead private methods.
- Avoid wide UI churn. The main refactor target is the plugin runtime/data path.
- Favor smaller pure modules over introducing another large abstraction class.

## Success Criteria

The refactor is successful when:

- `provider.py`, `client.py`, `qqmusic_service.py`, and `api.py` each have a narrower and more obvious responsibility
- repeated data-shaping logic is centralized in helper modules
- obviously duplicated private methods are deleted
- QQ Music tests still pass with behavior-compatible outputs
- future QQ Music changes can be made by touching one authority per concern instead of three

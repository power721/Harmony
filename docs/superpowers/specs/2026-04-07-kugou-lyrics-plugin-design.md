# Kugou Lyrics Plugin Design

## Overview

This change moves Kugou lyrics support out of the host-owned built-in source list and into a built-in plugin.

The goal is to make Kugou follow the same extension boundary already used by LRCLIB and QQ Music for lyrics registration. After the migration, the host still exposes the same end-user behavior, but Kugou is discovered and loaded through the plugin runtime.

## Goals

- Move Kugou lyrics registration from host code to a built-in plugin.
- Remove `KugouLyricsSource` from host-owned built-in source assembly.
- Preserve existing Kugou lyrics search and download behavior.
- Keep Kugou enabled by default after migration.
- Keep runtime lyrics source identifiers compatible with existing host logic.

## Non-Goals

- No new Kugou settings tab.
- No Kugou sidebar page or online music provider.
- No protocol changes to Kugou lyrics search or download requests.
- No refactor of unrelated host lyrics sources beyond removing Kugou ownership.

## Current State

Kugou is currently implemented as a host-owned lyrics source in [`services/sources/lyrics_sources.py`](/home/harold/workspace/music-player/services/sources/lyrics_sources.py).

[`services/lyrics/lyrics_service.py`](/home/harold/workspace/music-player/services/lyrics/lyrics_service.py) constructs built-in lyrics sources by directly instantiating:

- `NetEaseLyricsSource`
- `KugouLyricsSource`

This means Kugou does not participate in the plugin lifecycle even though the application already supports plugin-provided lyrics sources through the registry.

## Recommended Approach

Create a new built-in plugin at `plugins/builtin/kugou/` and migrate the Kugou implementation into that plugin.

The plugin manifest id should be `kuogo_lyrics`, while the runtime lyrics source identifier should remain `kugou`.

This split is intentional:

- `manifest.id = "kuogo_lyrics"` controls plugin discovery, enable state, and plugin management UI.
- `source_id = "kugou"` and search result `source = "kugou"` preserve compatibility with existing lyrics download and source matching flows.

## Architecture

### Plugin Layout

Add a new built-in plugin directory:

```text
plugins/builtin/kugou/
├── __init__.py
├── plugin.json
├── plugin_main.py
└── lib/
    ├── __init__.py
    └── lyrics_source.py
```

### Host Boundary

After migration:

- the host owns only `NetEaseLyricsSource` as a built-in lyrics source
- the Kugou implementation lives entirely under `plugins/builtin/kugou/`
- `LyricsService._get_sources()` continues to merge host sources with plugin-registered sources

### Plugin Registration

`plugin_main.py` should expose a plugin class with:

- `plugin_id = "kuogo_lyrics"`
- `register(context)` calling `context.services.register_lyrics_source(...)`
- `unregister(context)` as a no-op

The manifest should declare:

- `"id": "kuogo_lyrics"`
- `"capabilities": ["lyrics_source"]`

Because built-in plugins default to enabled unless persisted otherwise, Kugou remains active after the migration without adding special logic.

## Runtime Behavior

### Lyrics Source Identity

The plugin source object should expose:

- `source_id = "kugou"`
- `display_name = "Kugou"`
- `name = "Kugou"`

Each returned `PluginLyricsResult` should set:

- `source = "kugou"`
- `song_id` from Kugou candidate `id`
- `accesskey` from Kugou candidate `accesskey`

This preserves compatibility with `LyricsService.download_lyrics_by_id()` and existing result-to-dict behavior.

### Search Flow

The plugin search flow should preserve the existing request shape:

- endpoint: `https://lyrics.kugou.com/search`
- params: `keyword`, `page`, `pagesize`
- user agent header

The plugin should continue returning an empty list on request or decoding errors instead of raising to the host.

### Download Flow

The plugin lyrics download flow should preserve the current protocol:

- endpoint: `https://lyrics.kugou.com/download`
- params: `id`, `accesskey`, `fmt=krc`, `charset=utf8`
- base64 decode response content
- strip `krc1` header when present
- zlib decompress payload
- decode UTF-8 with `errors="ignore"`

On failure, the plugin should return `None` and log the error.

## File Changes

### Create

- `plugins/builtin/kugou/__init__.py`
- `plugins/builtin/kugou/plugin.json`
- `plugins/builtin/kugou/plugin_main.py`
- `plugins/builtin/kugou/lib/__init__.py`
- `plugins/builtin/kugou/lib/lyrics_source.py`
- `tests/test_plugins/test_kugou_plugin.py`

### Modify

- `services/lyrics/lyrics_service.py`
- `services/sources/lyrics_sources.py`
- `services/sources/__init__.py`
- `tests/test_services/test_lyrics_sources_perf_paths.py`
- `tests/test_services/test_plugin_lyrics_registry.py`

## Testing

Add or update tests to cover:

- Kugou plugin registers one lyrics source through the plugin context.
- Kugou plugin search maps API candidate data into `PluginLyricsResult`.
- `LyricsService._get_builtin_sources()` no longer includes Kugou.
- Existing plugin lyrics registry merging still works when built-in sources are empty.

Regression commands should focus on the changed area:

- `uv run pytest tests/test_plugins/test_kugou_plugin.py`
- `uv run pytest tests/test_services/test_lyrics_sources_perf_paths.py tests/test_services/test_plugin_lyrics_registry.py`

## Risks and Mitigations

- Plugin id typo risk: keep `kuogo_lyrics` limited to plugin manifest and plugin class identity, while preserving runtime source id as `kugou`.
- Behavior regression risk in download flow: preserve the existing decode and decompress logic byte-for-byte where possible.
- Hidden host dependency risk: move all Kugou-specific code under plugin paths and remove host imports of `KugouLyricsSource`.

## Scope Check

This design is intentionally narrow. It changes only Kugou lyrics ownership and the associated tests. It does not introduce new plugin capabilities, new UI, or new persistence rules.

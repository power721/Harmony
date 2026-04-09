# iTunes Cover Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move host-owned iTunes album cover and artist cover sources into a built-in plugin with id `itunes_cover`.

**Architecture:** Add a built-in plugin under `plugins/builtin/itunes_cover/` that registers one album cover source and one artist cover source through the plugin service bridge. Remove direct host ownership from `CoverService` and `services/sources` exports so iTunes cover behavior flows only through plugin loading.

**Tech Stack:** Python 3.11, pytest, `uv`, Harmony plugin runtime

---

## File Map

- Create: `plugins/builtin/itunes_cover/__init__.py`
- Create: `plugins/builtin/itunes_cover/plugin.json`
- Create: `plugins/builtin/itunes_cover/plugin_main.py`
- Create: `plugins/builtin/itunes_cover/lib/__init__.py`
- Create: `plugins/builtin/itunes_cover/lib/cover_source.py`
- Create: `plugins/builtin/itunes_cover/lib/artist_cover_source.py`
- Create: `tests/test_plugins/test_itunes_cover_plugin.py`
- Modify: `services/metadata/cover_service.py`
- Modify: `services/sources/cover_sources.py`
- Modify: `services/sources/artist_cover_sources.py`
- Modify: `services/sources/__init__.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

## Task 1: Lock In Failing Tests

**Files:**
- Create: `tests/test_plugins/test_itunes_cover_plugin.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.itunes_cover.plugin_main import ITunesCoverPlugin


def test_itunes_plugin_registers_cover_and_artist_sources():
    context = Mock()
    plugin = ITunesCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
```

```python
from services.metadata.cover_service import CoverService


def test_builtin_cover_sources_exclude_plugin_owned_sources():
    service = CoverService(http_client=SimpleNamespace(), sources=None)

    names = {source.name for source in service._get_builtin_sources()}
    artist_names = {source.name for source in service._get_builtin_artist_sources()}

    assert "iTunes" not in names
    assert "iTunes" not in artist_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_plugins/test_itunes_cover_plugin.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: FAIL with `ModuleNotFoundError` for `plugins.builtin.itunes_cover` and/or assertions that built-in sources still contain `iTunes`

## Task 2: Add the Built-In Plugin

**Files:**
- Create: `plugins/builtin/itunes_cover/__init__.py`
- Create: `plugins/builtin/itunes_cover/plugin.json`
- Create: `plugins/builtin/itunes_cover/plugin_main.py`
- Create: `plugins/builtin/itunes_cover/lib/__init__.py`
- Create: `plugins/builtin/itunes_cover/lib/cover_source.py`
- Create: `plugins/builtin/itunes_cover/lib/artist_cover_source.py`
- Test: `tests/test_plugins/test_itunes_cover_plugin.py`

- [ ] **Step 1: Write minimal implementation**

```python
class ITunesCoverPlugin:
    plugin_id = "itunes_cover"

    def register(self, context) -> None:
        context.services.register_cover_source(ITunesCoverPluginSource(context.http))
        context.services.register_artist_cover_source(
            ITunesArtistCoverPluginSource(context.http)
        )
```

- [ ] **Step 2: Run plugin tests**

Run: `uv run pytest tests/test_plugins/test_itunes_cover_plugin.py -v`
Expected: PASS

## Task 3: Remove Host Ownership

**Files:**
- Modify: `services/metadata/cover_service.py`
- Modify: `services/sources/cover_sources.py`
- Modify: `services/sources/artist_cover_sources.py`
- Modify: `services/sources/__init__.py`
- Test: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Remove iTunes built-in source wiring**

```python
def _get_builtin_sources(self) -> List["CoverSource"]:
    from services.sources import NetEaseCoverSource, LastFmCoverSource
    return [
        NetEaseCoverSource(self.http_client),
        LastFmCoverSource(self.http_client),
    ]
```

```python
def _get_builtin_artist_sources(self) -> List["ArtistCoverSource"]:
    from services.sources import NetEaseArtistCoverSource
    return [NetEaseArtistCoverSource(self.http_client)]
```

- [ ] **Step 2: Delete host exports for migrated classes and rerun tests**

Run: `uv run pytest tests/test_services/test_plugin_cover_registry.py tests/test_plugins/test_itunes_cover_plugin.py -v`
Expected: PASS

## Task 4: Focused Verification

**Files:**
- Test: `tests/test_plugins/test_itunes_cover_plugin.py`
- Test: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Run focused verification**

Run: `uv run pytest tests/test_plugins/test_itunes_cover_plugin.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: PASS

- [ ] **Step 2: Review diff**

Run: `git diff -- plugins/builtin/itunes_cover services/metadata/cover_service.py services/sources/cover_sources.py services/sources/artist_cover_sources.py services/sources/__init__.py tests/test_plugins/test_itunes_cover_plugin.py tests/test_services/test_plugin_cover_registry.py docs/superpowers/specs/2026-04-07-itunes-cover-plugin-design.md docs/superpowers/plans/2026-04-07-itunes-cover-plugin.md`
Expected: iTunes source ownership moves from host code to plugin code with no unrelated edits

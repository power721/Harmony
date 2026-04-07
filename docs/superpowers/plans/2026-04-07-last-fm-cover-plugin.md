# Last.fm Cover Plugin Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the host-owned Last.fm album cover source into a built-in plugin with id `last_fm_cover` while preserving the current default API key fallback behavior.

**Architecture:** Add a built-in plugin under `plugins/builtin/last_fm_cover/` that registers one album cover source through the plugin service bridge. Remove direct host ownership from `CoverService` and `services/sources` exports so Last.fm cover behavior flows only through plugin loading, but keep the current `LASTFM_API_KEY` resolution and built-in fallback key unchanged inside the plugin implementation.

**Tech Stack:** Python 3.11, pytest, `uv`, Harmony plugin runtime, environment-variable based API key resolution

---

## File Map

- Create: `plugins/builtin/last_fm_cover/__init__.py`
- Create: `plugins/builtin/last_fm_cover/plugin.json`
- Create: `plugins/builtin/last_fm_cover/plugin_main.py`
- Create: `plugins/builtin/last_fm_cover/lib/__init__.py`
- Create: `plugins/builtin/last_fm_cover/lib/cover_source.py`
- Create: `tests/test_plugins/test_last_fm_cover_plugin.py`
- Modify: `services/metadata/cover_service.py`
- Modify: `services/sources/cover_sources.py`
- Modify: `services/sources/__init__.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

## Task 1: Lock In Failing Tests

**Files:**
- Create: `tests/test_plugins/test_last_fm_cover_plugin.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import Mock

from plugins.builtin.last_fm_cover.plugin_main import LastFmCoverPlugin


def test_last_fm_plugin_registers_cover_source():
    context = Mock()
    plugin = LastFmCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
```

```python
from types import SimpleNamespace

from services.metadata.cover_service import CoverService


def test_builtin_cover_sources_exclude_plugin_owned_sources():
    service = CoverService(http_client=SimpleNamespace(), sources=None)

    names = {source.name for source in service._get_builtin_sources()}

    assert "Last.fm" not in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_plugins/test_last_fm_cover_plugin.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: FAIL with `ModuleNotFoundError` for `plugins.builtin.last_fm_cover` and/or an assertion showing `Last.fm` is still present in built-in host sources

## Task 2: Add the Built-In Plugin

**Files:**
- Create: `plugins/builtin/last_fm_cover/__init__.py`
- Create: `plugins/builtin/last_fm_cover/plugin.json`
- Create: `plugins/builtin/last_fm_cover/plugin_main.py`
- Create: `plugins/builtin/last_fm_cover/lib/__init__.py`
- Create: `plugins/builtin/last_fm_cover/lib/cover_source.py`
- Test: `tests/test_plugins/test_last_fm_cover_plugin.py`

- [ ] **Step 1: Write minimal plugin implementation**

```python
from .lib.cover_source import LastFmCoverPluginSource


class LastFmCoverPlugin:
    plugin_id = "last_fm_cover"

    def register(self, context) -> None:
        context.services.register_cover_source(
            LastFmCoverPluginSource(context.http)
        )

    def unregister(self, context) -> None:
        return None
```

```python
import os

from harmony_plugin_api.cover import PluginCoverResult


class LastFmCoverPluginSource:
    source = "lastfm"
    source_id = "lastfm-cover"
    display_name = "Last.fm"
    name = "Last.fm"
    _DEFAULT_API_KEY = "9b0cdcf446cc96dea3e747787ad23575"

    def __init__(self, http_client):
        self._http_client = http_client

    def _get_api_key(self) -> str:
        api_key = os.getenv("LASTFM_API_KEY")
        if not api_key or api_key == "YOUR_LASTFM_API_KEY":
            return self._DEFAULT_API_KEY
        return api_key
```

- [ ] **Step 2: Run plugin tests**

Run: `uv run pytest tests/test_plugins/test_last_fm_cover_plugin.py -v`
Expected: PASS

## Task 3: Remove Host Ownership

**Files:**
- Modify: `services/metadata/cover_service.py`
- Modify: `services/sources/cover_sources.py`
- Modify: `services/sources/__init__.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Remove Last.fm from built-in host source wiring**

```python
def _get_builtin_sources(self) -> List["CoverSource"]:
    from services.sources import NetEaseCoverSource
    return [
        NetEaseCoverSource(self.http_client),
    ]
```

- [ ] **Step 2: Delete host export for `LastFmCoverSource` and rerun tests**

Run: `uv run pytest tests/test_services/test_plugin_cover_registry.py tests/test_plugins/test_last_fm_cover_plugin.py -v`
Expected: PASS

## Task 4: Preserve Last.fm Behavior

**Files:**
- Modify: `tests/test_plugins/test_last_fm_cover_plugin.py`
- Modify: `plugins/builtin/last_fm_cover/lib/cover_source.py`

- [ ] **Step 1: Add a failing behavior test for default API key fallback and result mapping**

```python
from types import SimpleNamespace

from plugins.builtin.last_fm_cover.lib.cover_source import LastFmCoverPluginSource


def test_last_fm_plugin_source_uses_default_api_key_when_env_missing(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=0):
        captured["url"] = url
        captured["params"] = params
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "album": {
                    "name": "Album 1",
                    "artist": "Singer 1",
                    "image": [
                        {"#text": ""},
                        {"#text": "https://example.com/cover-large.jpg"},
                    ],
                }
            },
        )

    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    source = LastFmCoverPluginSource(SimpleNamespace(get=fake_get))

    results = source.search("Song 1", "Singer 1", "Album 1")

    assert captured["url"] == "http://ws.audioscrobbler.com/2.0/"
    assert captured["params"]["api_key"] == "9b0cdcf446cc96dea3e747787ad23575"
    assert results[0].source == "lastfm"
    assert results[0].cover_url == "https://example.com/cover-large.jpg"
```

- [ ] **Step 2: Run the test to verify it fails for the right reason**

Run: `uv run pytest tests/test_plugins/test_last_fm_cover_plugin.py::test_last_fm_plugin_source_uses_default_api_key_when_env_missing -v`
Expected: FAIL until `LastFmCoverPluginSource.search()` preserves the current host behavior

- [ ] **Step 3: Implement the minimal Last.fm search logic in the plugin**

```python
def search(
    self,
    title: str,
    artist: str,
    album: str = "",
    duration: float | None = None,
) -> list[PluginCoverResult]:
    results = []
    params = {
        "method": "album.getinfo",
        "api_key": self._get_api_key(),
        "artist": artist,
        "album": album or title,
        "format": "json",
    }
    response = self._http_client.get(
        "http://ws.audioscrobbler.com/2.0/",
        params=params,
        timeout=5,
    )
    if response.status_code == 200:
        data = response.json()
        album_info = data.get("album")
        if album_info:
            image_url = None
            for image in reversed(album_info.get("image", [])):
                if image.get("#text"):
                    image_url = image["#text"]
                    break
            if image_url:
                results.append(
                    PluginCoverResult(
                        item_id=album_info.get("mbid", ""),
                        title=album_info.get("name", ""),
                        artist=album_info.get("artist", ""),
                        album=album_info.get("name", ""),
                        source="lastfm",
                        cover_url=image_url,
                    )
                )
    return results
```

- [ ] **Step 4: Run plugin tests to verify they pass**

Run: `uv run pytest tests/test_plugins/test_last_fm_cover_plugin.py -v`
Expected: PASS

## Task 5: Focused Verification

**Files:**
- Test: `tests/test_plugins/test_last_fm_cover_plugin.py`
- Test: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Run focused verification**

Run: `uv run pytest tests/test_plugins/test_last_fm_cover_plugin.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: PASS

- [ ] **Step 2: Review diff**

Run: `git diff -- plugins/builtin/last_fm_cover services/metadata/cover_service.py services/sources/cover_sources.py services/sources/__init__.py tests/test_plugins/test_last_fm_cover_plugin.py tests/test_services/test_plugin_cover_registry.py docs/superpowers/specs/2026-04-07-last-fm-cover-plugin-design.md docs/superpowers/plans/2026-04-07-last-fm-cover-plugin.md`
Expected: Last.fm source ownership moves from host code to plugin code with no unrelated edits

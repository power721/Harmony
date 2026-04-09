# NetEase Plugin Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move host-owned NetEase lyrics, album cover, and artist cover sources into two built-in plugins while preserving the current `source="netease"` runtime behavior.

**Architecture:** Add `plugins/builtin/netease_lyrics/` and `plugins/builtin/netease_cover/`, plus a non-plugin shared helper package at `plugins/builtin/netease_shared/` for low-level request and parsing helpers. Remove NetEase ownership from `LyricsService`, `CoverService`, and `services/sources` exports so all NetEase capabilities flow through plugin loading, while keeping the same HTTP endpoints, result fields, and source identifiers.

**Tech Stack:** Python 3.11, pytest, `uv`, Harmony plugin runtime, `harmony_plugin_api`

---

## File Map

- Create: `plugins/builtin/netease_shared/__init__.py`
- Create: `plugins/builtin/netease_shared/common.py`
- Create: `plugins/builtin/netease_lyrics/__init__.py`
- Create: `plugins/builtin/netease_lyrics/plugin.json`
- Create: `plugins/builtin/netease_lyrics/plugin_main.py`
- Create: `plugins/builtin/netease_lyrics/lib/__init__.py`
- Create: `plugins/builtin/netease_lyrics/lib/lyrics_source.py`
- Create: `plugins/builtin/netease_cover/__init__.py`
- Create: `plugins/builtin/netease_cover/plugin.json`
- Create: `plugins/builtin/netease_cover/plugin_main.py`
- Create: `plugins/builtin/netease_cover/lib/__init__.py`
- Create: `plugins/builtin/netease_cover/lib/cover_source.py`
- Create: `plugins/builtin/netease_cover/lib/artist_cover_source.py`
- Create: `tests/test_plugins/test_netease_lyrics_plugin.py`
- Create: `tests/test_plugins/test_netease_cover_plugin.py`
- Modify: `services/lyrics/lyrics_service.py`
- Modify: `services/metadata/cover_service.py`
- Modify: `services/sources/lyrics_sources.py`
- Modify: `services/sources/cover_sources.py`
- Modify: `services/sources/artist_cover_sources.py`
- Modify: `services/sources/__init__.py`
- Modify: `tests/test_services/test_plugin_lyrics_registry.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

## Task 1: Lock In Failing Registration Tests

**Files:**
- Create: `tests/test_plugins/test_netease_lyrics_plugin.py`
- Create: `tests/test_plugins/test_netease_cover_plugin.py`
- Modify: `tests/test_services/test_plugin_lyrics_registry.py`
- Modify: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Write the failing plugin registration tests**

```python
from unittest.mock import Mock

from plugins.builtin.netease_lyrics.plugin_main import NetEaseLyricsPlugin


def test_netease_lyrics_plugin_registers_lyrics_source():
    context = Mock()
    plugin = NetEaseLyricsPlugin()

    plugin.register(context)

    context.services.register_lyrics_source.assert_called_once()
```

```python
from unittest.mock import Mock

from plugins.builtin.netease_cover.plugin_main import NetEaseCoverPlugin


def test_netease_cover_plugin_registers_cover_and_artist_sources():
    context = Mock()
    plugin = NetEaseCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
```

```python
def test_builtin_lyrics_sources_exclude_plugin_owned_sources():
    sources = LyricsService._get_builtin_sources()
    names = {source.name for source in sources}

    assert "NetEase" not in names
```

```python
def test_builtin_cover_sources_exclude_plugin_owned_sources():
    service = CoverService(http_client=SimpleNamespace(), sources=None)

    names = {source.name for source in service._get_builtin_sources()}
    artist_names = {source.name for source in service._get_builtin_artist_sources()}

    assert "NetEase" not in names
    assert "NetEase" not in artist_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py tests/test_plugins/test_netease_cover_plugin.py tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: FAIL with `ModuleNotFoundError` for the new plugins and/or assertions showing built-in host source lists still contain `NetEase`

## Task 2: Add Shared NetEase Helpers

**Files:**
- Create: `plugins/builtin/netease_shared/__init__.py`
- Create: `plugins/builtin/netease_shared/common.py`
- Test: `tests/test_plugins/test_netease_lyrics_plugin.py`
- Test: `tests/test_plugins/test_netease_cover_plugin.py`

- [ ] **Step 1: Write a failing behavior test that depends on shared header and image-url normalization helpers**

```python
from plugins.builtin.netease_shared.common import build_netease_image_url, netease_headers


def test_netease_shared_helpers_normalize_headers_and_image_urls():
    headers = netease_headers()

    assert headers["Referer"] == "https://music.163.com/"
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert build_netease_image_url("https://example.com/cover.jpg", "500y500") == (
        "https://example.com/cover.jpg?param=500y500"
    )
    assert build_netease_image_url("https://example.com/cover.jpg?foo=1", "500y500") == (
        "https://example.com/cover.jpg?foo=1"
    )
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py::test_netease_shared_helpers_normalize_headers_and_image_urls -v`
Expected: FAIL with `ModuleNotFoundError` for `plugins.builtin.netease_shared.common`

- [ ] **Step 3: Write the minimal shared helper implementation**

```python
from __future__ import annotations


def netease_headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36"
        ),
        "Referer": "https://music.163.com/",
    }


def build_netease_image_url(url: str | None, size: str) -> str | None:
    if not url:
        return None
    if "?" in url:
        return url
    return f"{url}?param={size}"
```

- [ ] **Step 4: Run the targeted test to verify it passes**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py::test_netease_shared_helpers_normalize_headers_and_image_urls -v`
Expected: PASS

## Task 3: Add the NetEase Lyrics Plugin

**Files:**
- Create: `plugins/builtin/netease_lyrics/__init__.py`
- Create: `plugins/builtin/netease_lyrics/plugin.json`
- Create: `plugins/builtin/netease_lyrics/plugin_main.py`
- Create: `plugins/builtin/netease_lyrics/lib/__init__.py`
- Create: `plugins/builtin/netease_lyrics/lib/lyrics_source.py`
- Test: `tests/test_plugins/test_netease_lyrics_plugin.py`

- [ ] **Step 1: Extend the failing lyrics plugin test with result mapping and YRC fallback behavior**

```python
from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.netease_lyrics.lib.lyrics_source import NetEaseLyricsPluginSource
from plugins.builtin.netease_lyrics.plugin_main import NetEaseLyricsPlugin


def test_netease_lyrics_plugin_registers_lyrics_source():
    context = Mock()
    plugin = NetEaseLyricsPlugin()

    plugin.register(context)

    context.services.register_lyrics_source.assert_called_once()
    registered = context.services.register_lyrics_source.call_args.args[0]
    assert isinstance(registered, NetEaseLyricsPluginSource)


def test_netease_lyrics_plugin_source_search_maps_results():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "songs": [
                    {
                        "id": 1,
                        "name": "Song 1",
                        "artists": [{"name": "Singer 1"}],
                        "album": {
                            "name": "Album 1",
                            "picUrl": "https://example.com/cover.jpg",
                        },
                        "duration": 225000,
                    }
                ]
            },
        },
    )
    source = NetEaseLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].song_id == "1"
    assert results[0].title == "Song 1"
    assert results[0].artist == "Singer 1"
    assert results[0].album == "Album 1"
    assert results[0].duration == 225.0
    assert results[0].source == "netease"
    assert results[0].cover_url == "https://example.com/cover.jpg"
    assert results[0].supports_yrc is True


def test_netease_lyrics_plugin_source_prefers_yrc_then_falls_back_to_lrc():
    responses = [
        SimpleNamespace(
            status_code=200,
            json=lambda: {"code": 200, "yrc": {}, "lrc": {"lyric": "[00:01.00]line"}},
        )
    ]
    source = NetEaseLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: responses.pop(0))
    )

    lyrics = source.get_lyrics(SimpleNamespace(song_id="1"))

    assert lyrics == "[00:01.00]line"
```

- [ ] **Step 2: Run lyrics plugin tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py -v`
Expected: FAIL with missing plugin files and missing `NetEaseLyricsPluginSource`

- [ ] **Step 3: Write the minimal lyrics plugin implementation**

```python
from .lib.lyrics_source import NetEaseLyricsPluginSource


class NetEaseLyricsPlugin:
    plugin_id = "netease_lyrics"

    def register(self, context) -> None:
        context.services.register_lyrics_source(
            NetEaseLyricsPluginSource(context.http)
        )

    def unregister(self, context) -> None:
        return None
```

```python
{
  "id": "netease_lyrics",
  "name": "NetEase Lyrics",
  "version": "1.0.0",
  "api_version": "1",
  "entrypoint": "plugin_main.py",
  "entry_class": "NetEaseLyricsPlugin",
  "capabilities": ["lyrics_source"],
  "min_app_version": "0.1.0"
}
```

```python
from __future__ import annotations

import logging

from harmony_plugin_api.lyrics import PluginLyricsResult
from plugins.builtin.netease_shared.common import netease_headers

logger = logging.getLogger(__name__)


class NetEaseLyricsPluginSource:
    source_id = "netease"
    display_name = "NetEase"
    name = "NetEase"

    def __init__(self, http_client) -> None:
        self._http_client = http_client

    def search(
        self,
        title: str,
        artist: str,
        limit: int = 10,
    ) -> list[PluginLyricsResult]:
        response = self._http_client.get(
            "https://music.163.com/api/search/get/web",
            params={"s": f"{artist} {title}", "type": "1", "limit": str(limit)},
            headers=netease_headers(),
            timeout=3,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        songs = payload.get("result", {}).get("songs", [])
        return [
            PluginLyricsResult(
                song_id=str(song["id"]),
                title=song.get("name", ""),
                artist=song["artists"][0]["name"] if song.get("artists") else "",
                album=song.get("album", {}).get("name", ""),
                duration=(song.get("duration") / 1000) if song.get("duration") else None,
                source="netease",
                cover_url=song.get("album", {}).get("picUrl"),
                supports_yrc=True,
            )
            for song in songs
        ]

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        try:
            response = self._http_client.get(
                f"https://music.163.com/api/song/lyric?id={result.song_id}&lv=1&kv=0&tv=0&yv=0",
                headers=netease_headers(),
                timeout=3,
            )
            if response.status_code == 200:
                payload = response.json()
                yrc = payload.get("yrc", {}).get("lyric")
                if yrc:
                    return yrc
                lrc = payload.get("lrc", {}).get("lyric")
                if lrc:
                    return lrc
        except Exception:
            logger.exception("Error downloading NetEase lyrics")
        return None
```

- [ ] **Step 4: Run lyrics plugin tests to verify they pass**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py -v`
Expected: PASS

## Task 4: Add the NetEase Cover Plugin

**Files:**
- Create: `plugins/builtin/netease_cover/__init__.py`
- Create: `plugins/builtin/netease_cover/plugin.json`
- Create: `plugins/builtin/netease_cover/plugin_main.py`
- Create: `plugins/builtin/netease_cover/lib/__init__.py`
- Create: `plugins/builtin/netease_cover/lib/cover_source.py`
- Create: `plugins/builtin/netease_cover/lib/artist_cover_source.py`
- Test: `tests/test_plugins/test_netease_cover_plugin.py`

- [ ] **Step 1: Extend the failing cover plugin test with album-cover and artist-cover mapping**

```python
from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.netease_cover.lib.artist_cover_source import (
    NetEaseArtistCoverPluginSource,
)
from plugins.builtin.netease_cover.lib.cover_source import NetEaseCoverPluginSource
from plugins.builtin.netease_cover.plugin_main import NetEaseCoverPlugin


def test_netease_cover_plugin_registers_cover_and_artist_sources():
    context = Mock()
    plugin = NetEaseCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
    assert isinstance(
        context.services.register_cover_source.call_args.args[0],
        NetEaseCoverPluginSource,
    )
    assert isinstance(
        context.services.register_artist_cover_source.call_args.args[0],
        NetEaseArtistCoverPluginSource,
    )


def test_netease_cover_source_search_maps_album_and_song_results():
    responses = [
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": 200,
                "result": {
                    "albums": [
                        {
                            "id": 1,
                            "name": "Album 1",
                            "artist": {"name": "Singer 1"},
                            "picUrl": "https://example.com/album.jpg",
                        }
                    ]
                },
            },
        ),
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": 200,
                "result": {
                    "songs": [
                        {
                            "id": 2,
                            "name": "Song 1",
                            "artists": [{"name": "Singer 1"}],
                            "duration": 180000,
                            "album": {
                                "name": "Album 1",
                                "picUrl": "https://example.com/song.jpg",
                            },
                        }
                    ]
                },
            },
        ),
    ]
    source = NetEaseCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: responses.pop(0))
    )

    results = source.search("Song 1", "Singer 1", "Album 1")

    assert len(results) == 2
    assert results[0].item_id == "1"
    assert results[0].album == "Album 1"
    assert results[0].source == "netease"
    assert results[0].cover_url == "https://example.com/album.jpg?param=500y500"
    assert results[1].item_id == "2"
    assert results[1].duration == 180.0


def test_netease_artist_cover_source_search_maps_results():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "artists": [
                    {
                        "id": 1,
                        "name": "Singer 1",
                        "albumSize": 8,
                        "picUrl": "https://example.com/artist.jpg",
                    }
                ]
            },
        },
    )
    source = NetEaseArtistCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Singer 1", limit=5)

    assert len(results) == 1
    assert results[0].artist_id == "1"
    assert results[0].name == "Singer 1"
    assert results[0].album_count == 8
    assert results[0].source == "netease"
    assert results[0].cover_url == "https://example.com/artist.jpg?param=512y512"
```

- [ ] **Step 2: Run cover plugin tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_netease_cover_plugin.py -v`
Expected: FAIL with missing plugin files and missing NetEase cover source classes

- [ ] **Step 3: Write the minimal cover plugin implementation**

```python
from .lib.artist_cover_source import NetEaseArtistCoverPluginSource
from .lib.cover_source import NetEaseCoverPluginSource


class NetEaseCoverPlugin:
    plugin_id = "netease_cover"

    def register(self, context) -> None:
        context.services.register_cover_source(
            NetEaseCoverPluginSource(context.http)
        )
        context.services.register_artist_cover_source(
            NetEaseArtistCoverPluginSource(context.http)
        )

    def unregister(self, context) -> None:
        return None
```

```python
{
  "id": "netease_cover",
  "name": "NetEase Cover",
  "version": "1.0.0",
  "api_version": "1",
  "entrypoint": "plugin_main.py",
  "entry_class": "NetEaseCoverPlugin",
  "capabilities": ["cover"],
  "min_app_version": "0.1.0"
}
```

```python
from __future__ import annotations

import logging

from harmony_plugin_api.cover import PluginCoverResult
from plugins.builtin.netease_shared.common import (
    build_netease_image_url,
    netease_headers,
)

logger = logging.getLogger(__name__)


class NetEaseCoverPluginSource:
    source = "netease"
    source_id = "netease-cover"
    display_name = "NetEase"
    name = "NetEase"

    def __init__(self, http_client):
        self._http_client = http_client

    def search(
        self,
        title: str,
        artist: str,
        album: str = "",
        duration: float | None = None,
    ) -> list[PluginCoverResult]:
        results: list[PluginCoverResult] = []
        album_response = self._http_client.get(
            "https://music.163.com/api/search/get/web",
            params={"s": f"{artist} {album or title}", "type": 10, "limit": 5},
            headers=netease_headers(),
            timeout=5,
        )
        if album_response.status_code == 200:
            payload = album_response.json()
            for item in payload.get("result", {}).get("albums", []):
                cover_url = build_netease_image_url(
                    item.get("picUrl") or item.get("blurPicUrl"),
                    "500y500",
                )
                if not cover_url:
                    continue
                results.append(
                    PluginCoverResult(
                        item_id=str(item.get("id", "")),
                        title=item.get("name", ""),
                        artist=item.get("artist", {}).get("name", ""),
                        album=item.get("name", ""),
                        source="netease",
                        cover_url=cover_url,
                    )
                )
        song_response = self._http_client.get(
            "https://music.163.com/api/search/get/web",
            params={"s": f"{artist} {title}", "type": 1, "limit": 5},
            headers=netease_headers(),
            timeout=5,
        )
        if song_response.status_code == 200:
            payload = song_response.json()
            for song in payload.get("result", {}).get("songs", []):
                album_info = song.get("album", {})
                cover_url = build_netease_image_url(
                    album_info.get("picUrl") or album_info.get("blurPicUrl"),
                    "500y500",
                )
                if not cover_url:
                    continue
                results.append(
                    PluginCoverResult(
                        item_id=str(song.get("id", "")),
                        title=song.get("name", ""),
                        artist=song["artists"][0]["name"] if song.get("artists") else "",
                        album=album_info.get("name", ""),
                        duration=(song.get("duration") / 1000) if song.get("duration") else None,
                        source="netease",
                        cover_url=cover_url,
                    )
                )
        return results
```

```python
from __future__ import annotations

import logging

from harmony_plugin_api.cover import PluginArtistCoverResult
from plugins.builtin.netease_shared.common import (
    build_netease_image_url,
    netease_headers,
)

logger = logging.getLogger(__name__)


class NetEaseArtistCoverPluginSource:
    source = "netease"
    source_id = "netease-artist-cover"
    display_name = "NetEase"
    name = "NetEase"

    def __init__(self, http_client):
        self._http_client = http_client

    def search(
        self,
        artist_name: str,
        limit: int = 10,
    ) -> list[PluginArtistCoverResult]:
        response = self._http_client.get(
            "https://music.163.com/api/search/get/web",
            params={"s": artist_name, "type": 100, "limit": limit, "offset": 0},
            headers=netease_headers(),
            timeout=5,
        )
        if response.status_code != 200:
            return []
        payload = response.json()
        results: list[PluginArtistCoverResult] = []
        for item in payload.get("result", {}).get("artists", []):
            cover_url = build_netease_image_url(
                item.get("picUrl") or item.get("img1v1Url"),
                "512y512",
            )
            if not cover_url:
                continue
            results.append(
                PluginArtistCoverResult(
                    artist_id=str(item.get("id", "")),
                    name=item.get("name", ""),
                    cover_url=cover_url,
                    album_count=item.get("albumSize", 0),
                    source="netease",
                )
            )
        return results
```

- [ ] **Step 4: Run cover plugin tests to verify they pass**

Run: `uv run pytest tests/test_plugins/test_netease_cover_plugin.py -v`
Expected: PASS

## Task 5: Remove Host Ownership of NetEase Sources

**Files:**
- Modify: `services/lyrics/lyrics_service.py`
- Modify: `services/metadata/cover_service.py`
- Modify: `services/sources/lyrics_sources.py`
- Modify: `services/sources/cover_sources.py`
- Modify: `services/sources/artist_cover_sources.py`
- Modify: `services/sources/__init__.py`
- Test: `tests/test_services/test_plugin_lyrics_registry.py`
- Test: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Remove NetEase from the built-in host source lists**

```python
@classmethod
def _get_builtin_sources(cls) -> List["LyricsSource"]:
    return []
```

```python
def _get_builtin_sources(self) -> List["CoverSource"]:
    return []
```

```python
def _get_builtin_artist_sources(self) -> List["ArtistCoverSource"]:
    return []
```

- [ ] **Step 2: Remove the migrated NetEase source classes from `services/sources` host modules and package exports**

```python
from .base import CoverSource, LyricsSource, ArtistCoverSource
from .cover_sources import MusicBrainzCoverSource, SpotifyCoverSource
from .artist_cover_sources import SpotifyArtistCoverSource

__all__ = [
    "CoverSource",
    "LyricsSource",
    "ArtistCoverSource",
    "MusicBrainzCoverSource",
    "SpotifyCoverSource",
    "SpotifyArtistCoverSource",
]
```

- [ ] **Step 3: Run registry tests to verify host ownership is gone and plugin merging still works**

Run: `uv run pytest tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: PASS

## Task 6: Restore Full NetEase Behavior and Regression Coverage

**Files:**
- Modify: `tests/test_plugins/test_netease_lyrics_plugin.py`
- Modify: `tests/test_plugins/test_netease_cover_plugin.py`
- Modify: `plugins/builtin/netease_lyrics/lib/lyrics_source.py`
- Modify: `plugins/builtin/netease_cover/lib/cover_source.py`
- Modify: `plugins/builtin/netease_cover/lib/artist_cover_source.py`

- [ ] **Step 1: Add failing tests for error handling and NetEase-specific fallbacks**

```python
def test_netease_lyrics_plugin_source_uses_lrc_fallback_request_when_first_call_has_no_lyrics():
    responses = [
        SimpleNamespace(status_code=200, json=lambda: {"code": 200, "yrc": {}, "lrc": {}}),
        SimpleNamespace(status_code=200, json=lambda: {"code": 200, "lrc": {"lyric": "[00:02.00]fallback"}}),
    ]
    source = NetEaseLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: responses.pop(0))
    )

    lyrics = source.get_lyrics(SimpleNamespace(song_id="1"))

    assert lyrics == "[00:02.00]fallback"
```

```python
def test_netease_cover_source_returns_empty_list_on_request_error():
    source = NetEaseCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    )

    assert source.search("Song 1", "Singer 1", "Album 1") == []
```

```python
def test_netease_artist_cover_source_uses_img1v1_url_when_pic_url_missing():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "artists": [
                    {
                        "id": 1,
                        "name": "Singer 1",
                        "albumSize": 8,
                        "img1v1Url": "https://example.com/artist-alt.jpg",
                    }
                ]
            },
        },
    )
    source = NetEaseArtistCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Singer 1", limit=5)

    assert results[0].cover_url == "https://example.com/artist-alt.jpg?param=512y512"
```

- [ ] **Step 2: Run the focused plugin tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py tests/test_plugins/test_netease_cover_plugin.py -v`
Expected: FAIL until the plugins preserve the full host behavior for fallback requests and error handling

- [ ] **Step 3: Implement the remaining NetEase behavior in the plugins**

```python
if response.status_code == 200:
    payload = response.json()
    yrc = payload.get("yrc", {}).get("lyric")
    if yrc:
        return yrc
    lrc = payload.get("lrc", {}).get("lyric")
    if lrc:
        return lrc

fallback = self._http_client.get(
    f"https://music.163.com/api/song/lyric?id={result.song_id}&lv=1&kv=1&tv=-1",
    headers=netease_headers(),
    timeout=3,
)
if fallback.status_code != 200:
    return None
payload = fallback.json()
if payload.get("code") != 200:
    return None
return payload.get("lrc", {}).get("lyric") or payload.get("lyric")
```

```python
try:
    response = self._http_client.get(...)
except Exception as exc:
    logger.debug("NetEase cover search error: %s", exc)
    return []
```

- [ ] **Step 4: Run the focused plugin tests to verify they pass**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py tests/test_plugins/test_netease_cover_plugin.py -v`
Expected: PASS

## Task 7: Final Verification and Diff Review

**Files:**
- Test: `tests/test_plugins/test_netease_lyrics_plugin.py`
- Test: `tests/test_plugins/test_netease_cover_plugin.py`
- Test: `tests/test_services/test_plugin_lyrics_registry.py`
- Test: `tests/test_services/test_plugin_cover_registry.py`

- [ ] **Step 1: Run final focused verification**

Run: `uv run pytest tests/test_plugins/test_netease_lyrics_plugin.py tests/test_plugins/test_netease_cover_plugin.py tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py -v`
Expected: PASS

- [ ] **Step 2: Review the final diff**

Run: `git diff -- plugins/builtin/netease_shared plugins/builtin/netease_lyrics plugins/builtin/netease_cover services/lyrics/lyrics_service.py services/metadata/cover_service.py services/sources/lyrics_sources.py services/sources/cover_sources.py services/sources/artist_cover_sources.py services/sources/__init__.py tests/test_plugins/test_netease_lyrics_plugin.py tests/test_plugins/test_netease_cover_plugin.py tests/test_services/test_plugin_lyrics_registry.py tests/test_services/test_plugin_cover_registry.py docs/superpowers/specs/2026-04-07-netease-plugin-split-design.md docs/superpowers/plans/2026-04-07-netease-plugin-split.md`
Expected: NetEase lyrics, album cover, and artist cover ownership moves from host code to two built-in plugins with a small shared helper package and no unrelated edits

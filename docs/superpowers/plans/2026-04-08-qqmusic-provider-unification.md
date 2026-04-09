# QQMusic Provider Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route QQ Music lyrics and album-cover plugin sources through `QQMusicOnlineProvider` so they prefer local QQ client data before remote API fallback without changing host-facing source contracts.

**Architecture:** Extend `QQMusicOnlineProvider` with two thin methods, `get_lyrics()` and `get_cover_url()`, that reuse the existing plugin client/service stack and only fall back to `QQMusicPluginAPI` when the local path cannot produce data. Then convert `QQMusicLyricsPluginSource` and `QQMusicCoverPluginSource` into provider-backed mapping adapters, leaving plugin registration and helper integration unchanged.

**Tech Stack:** Python 3, PySide6 plugin package, pytest, monkeypatch-based unit tests, `uv`

---

## File Map

- Modify: `plugins/builtin/qqmusic/lib/provider.py`
  Responsibility: add thin provider-owned lyrics and cover lookup methods, with local-first fallback behavior.
- Modify: `plugins/builtin/qqmusic/lib/lyrics_source.py`
  Responsibility: replace direct `QQMusicPluginAPI` usage with `QQMusicOnlineProvider` delegation while preserving `PluginLyricsResult` mapping.
- Modify: `plugins/builtin/qqmusic/lib/cover_source.py`
  Responsibility: replace direct `QQMusicPluginAPI` usage with `QQMusicOnlineProvider` delegation while preserving `PluginCoverResult` mapping and host helper contract.
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`
  Responsibility: cover provider-level `get_lyrics()` and `get_cover_url()` behavior.
- Modify: `tests/test_services/test_qqmusic_plugin_source_adapters.py`
  Responsibility: assert the lyrics and cover sources delegate through the provider instead of the raw API.
- Modify: `tests/test_services/test_lyrics_sources_perf_paths.py`
  Responsibility: keep the lightweight transformed-list regression aligned with provider-backed source wiring.

### Task 1: Add provider-level lyrics resolution

**Files:**
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`
- Modify: `plugins/builtin/qqmusic/lib/provider.py`

- [ ] **Step 1: Write the failing provider lyrics tests**

Add these tests near the existing provider/client tests in `tests/test_plugins/test_qqmusic_plugin.py`:

```python
def test_qqmusic_provider_get_lyrics_prefers_qrc_from_local_service(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    service = Mock()
    service.get_lyrics.return_value = {
        "qrc": "[0,100]word",
        "lyric": "[00:00.00]plain",
    }
    api = Mock()
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicPluginAPI",
        Mock(return_value=api),
    )

    provider = QQMusicOnlineProvider(context)
    monkeypatch.setattr(provider._client, "_can_use_legacy_network", lambda: True)

    assert provider.get_lyrics("song-mid") == "[0,100]word"
    service.get_lyrics.assert_called_once_with("song-mid")
    api.get_lyrics.assert_not_called()


def test_qqmusic_provider_get_lyrics_falls_back_to_public_api(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    service = Mock()
    service.get_lyrics.return_value = {"qrc": None, "lyric": None}
    api = Mock()
    api.get_lyrics.return_value = "[00:00.00]remote"
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicPluginAPI",
        Mock(return_value=api),
    )

    provider = QQMusicOnlineProvider(context)
    monkeypatch.setattr(provider._client, "_can_use_legacy_network", lambda: True)

    assert provider.get_lyrics("song-mid") == "[00:00.00]remote"
    api.get_lyrics.assert_called_once_with("song-mid")
```

- [ ] **Step 2: Run the provider lyrics tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "provider_get_lyrics" -v`

Expected: FAIL with `AttributeError: 'QQMusicOnlineProvider' object has no attribute 'get_lyrics'`

- [ ] **Step 3: Write the minimal provider lyrics implementation**

Update `plugins/builtin/qqmusic/lib/provider.py` by adding `QQMusicPluginAPI` import and this method inside `QQMusicOnlineProvider`:

```python
from .api import QQMusicPluginAPI
```

```python
    def get_lyrics(self, song_mid: str) -> str | None:
        service = self._client._get_service()
        if service is not None and self._client._can_use_legacy_network():
            try:
                lyric_data = service.get_lyrics(song_mid) or {}
            except Exception:
                lyric_data = {}
            qrc = lyric_data.get("qrc")
            if qrc:
                return qrc
            lyric = lyric_data.get("lyric")
            if lyric:
                return lyric

        try:
            return QQMusicPluginAPI(self._context).get_lyrics(song_mid)
        except Exception:
            return None
```

- [ ] **Step 4: Run the provider lyrics tests to verify they pass**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "provider_get_lyrics" -v`

Expected: PASS for both new tests

- [ ] **Step 5: Commit the provider lyrics slice**

Run:

```bash
git add tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/provider.py
git commit -m "添加QQ音乐Provider歌词入口"
```

### Task 2: Add provider-level cover URL resolution

**Files:**
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`
- Modify: `plugins/builtin/qqmusic/lib/provider.py`

- [ ] **Step 1: Write the failing provider cover tests**

Add these tests to `tests/test_plugins/test_qqmusic_plugin.py` after the provider lyrics tests:

```python
def test_qqmusic_provider_get_cover_url_prefers_album_mid(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: default
    context = Mock(settings=settings)
    context.logger = Mock()

    provider = QQMusicOnlineProvider(context)

    assert provider.get_cover_url(album_mid="album-1", size=800) == (
        "https://y.gtimg.cn/music/photo_new/T002R800x800M000album-1.jpg"
    )


def test_qqmusic_provider_get_cover_url_uses_local_song_detail_before_public_api(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    service = Mock()
    service.client.get_song_detail.return_value = {
        "track_info": {"album": {"mid": "album-from-detail"}}
    }
    api = Mock()
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicPluginAPI",
        Mock(return_value=api),
    )

    provider = QQMusicOnlineProvider(context)
    monkeypatch.setattr(provider._client, "_can_use_legacy_network", lambda: True)

    assert provider.get_cover_url(mid="song-1", size=500) == (
        "https://y.gtimg.cn/music/photo_new/T002R500x500M000album-from-detail.jpg"
    )
    api.get_cover_url.assert_not_called()


def test_qqmusic_provider_get_cover_url_falls_back_to_public_api(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    service = Mock()
    service.client.get_song_detail.return_value = {}
    api = Mock()
    api.get_cover_url.return_value = "https://remote/cover.jpg"
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicPluginAPI",
        Mock(return_value=api),
    )

    provider = QQMusicOnlineProvider(context)
    monkeypatch.setattr(provider._client, "_can_use_legacy_network", lambda: True)

    assert provider.get_cover_url(mid="song-1", size=500) == "https://remote/cover.jpg"
    api.get_cover_url.assert_called_once_with(mid="song-1", album_mid=None, size=500)
```

- [ ] **Step 2: Run the provider cover tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "provider_get_cover_url" -v`

Expected: FAIL with `AttributeError: 'QQMusicOnlineProvider' object has no attribute 'get_cover_url'`

- [ ] **Step 3: Write the minimal provider cover implementation**

Add these helpers and method to `plugins/builtin/qqmusic/lib/provider.py`:

```python
    @staticmethod
    def _build_album_cover_url(album_mid: str, size: int) -> str | None:
        if not album_mid:
            return None
        return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{album_mid}.jpg"

    @staticmethod
    def _extract_album_mid_from_song_detail(detail: dict[str, Any] | None) -> str:
        if not isinstance(detail, dict):
            return ""
        track = detail.get("track_info", detail.get("data", detail))
        if not isinstance(track, dict):
            return ""
        album = track.get("album", {})
        if isinstance(album, dict):
            album_mid = album.get("mid") or album.get("albumMid") or album.get("albummid")
            if album_mid:
                return str(album_mid)
        return str(track.get("album_mid") or track.get("albummid") or track.get("albumMid") or "")

    def get_cover_url(
        self,
        mid: str | None = None,
        album_mid: str | None = None,
        size: int = 500,
    ) -> str | None:
        cover_url = self._build_album_cover_url(album_mid or "", size)
        if cover_url:
            return cover_url

        service = self._client._get_service()
        if service is not None and mid and self._client._can_use_legacy_network():
            try:
                detail = service.client.get_song_detail(mid)
            except Exception:
                detail = {}
            local_album_mid = self._extract_album_mid_from_song_detail(detail)
            cover_url = self._build_album_cover_url(local_album_mid, size)
            if cover_url:
                return cover_url

        try:
            return QQMusicPluginAPI(self._context).get_cover_url(mid=mid, album_mid=album_mid, size=size)
        except Exception:
            return None
```

- [ ] **Step 4: Run the provider cover tests to verify they pass**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "provider_get_cover_url" -v`

Expected: PASS for all three new tests

- [ ] **Step 5: Commit the provider cover slice**

Run:

```bash
git add tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/provider.py
git commit -m "添加QQ音乐Provider封面入口"
```

### Task 3: Move lyrics and cover sources onto the provider

**Files:**
- Modify: `tests/test_services/test_qqmusic_plugin_source_adapters.py`
- Modify: `tests/test_services/test_lyrics_sources_perf_paths.py`
- Modify: `plugins/builtin/qqmusic/lib/lyrics_source.py`
- Modify: `plugins/builtin/qqmusic/lib/cover_source.py`

- [ ] **Step 1: Rewrite the source adapter tests to fail against provider delegation**

Update `tests/test_services/test_qqmusic_plugin_source_adapters.py` so the lyrics and cover source tests patch `QQMusicOnlineProvider` methods instead of `QQMusicPluginAPI`. Use tests shaped like:

```python
from plugins.builtin.qqmusic.lib.provider import QQMusicOnlineProvider
```

```python
def test_qqmusic_lyrics_source_search_reads_tracks_payload(monkeypatch):
    captured = {}

    def fake_search(self, keyword, search_type="song", page=1, page_size=30):
        captured.update(
            keyword=keyword,
            search_type=search_type,
            page=page,
            page_size=page_size,
        )
        return {
            "tracks": [
                {
                    "mid": "song-1",
                    "title": "Song 1",
                    "artist": "Singer 1",
                    "album": "Album 1",
                    "album_mid": "album-1",
                    "duration": 180,
                }
            ]
        }

    monkeypatch.setattr(QQMusicOnlineProvider, "search", fake_search)
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "get_cover_url",
        lambda *_args, **_kwargs: "cover-1",
    )

    source = QQMusicLyricsPluginSource(SimpleNamespace())

    results = source.search("Song 1", "Singer 1", limit=7)

    assert captured == {
        "keyword": "Song 1 Singer 1",
        "search_type": "song",
        "page": 1,
        "page_size": 7,
    }
    assert results[0].cover_url == "cover-1"


def test_qqmusic_lyrics_source_get_lyrics_uses_provider(monkeypatch):
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "get_lyrics",
        lambda self, song_mid: f"lyrics:{song_mid}",
    )

    source = QQMusicLyricsPluginSource(SimpleNamespace())

    assert source.get_lyrics_by_song_id("song-1") == "lyrics:song-1"


def test_qqmusic_cover_source_get_cover_url_uses_provider(monkeypatch):
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "get_cover_url",
        lambda self, mid=None, album_mid=None, size=500: f"cover:{album_mid or mid}:{size}",
    )

    source = QQMusicCoverPluginSource(SimpleNamespace())

    assert source.get_cover_url(mid="song-1", album_mid="album-1", size=700) == "cover:album-1:700"
```

Also update `tests/test_services/test_lyrics_sources_perf_paths.py` so it patches `QQMusicOnlineProvider.search` and `QQMusicOnlineProvider.get_cover_url`, not `QQMusicPluginAPI`.

- [ ] **Step 2: Run the source adapter tests to verify they fail**

Run:

```bash
uv run pytest tests/test_services/test_qqmusic_plugin_source_adapters.py -v
uv run pytest tests/test_services/test_lyrics_sources_perf_paths.py -v
```

Expected: FAIL because the current source classes still instantiate and call `QQMusicPluginAPI`

- [ ] **Step 3: Write the minimal source delegation implementation**

Update `plugins/builtin/qqmusic/lib/lyrics_source.py` to use `QQMusicOnlineProvider`:

```python
from .provider import QQMusicOnlineProvider
```

```python
    def __init__(self, context):
        self._context = context
        self._provider = QQMusicOnlineProvider(context)

    def search(self, title: str, artist: str, limit: int = 10) -> list[PluginLyricsResult]:
        try:
            keyword = f"{title} {artist}" if artist else title
            search_payload = self._provider.search(
                keyword,
                search_type="song",
                page=1,
                page_size=limit,
            )
            search_results = search_payload.get("tracks", []) if isinstance(search_payload, dict) else search_payload
            return [
                PluginLyricsResult(
                    song_id=item.get("mid", ""),
                    title=item.get("title", "") or item.get("name", ""),
                    artist=item.get("artist", "") or item.get("singer", ""),
                    album=item.get("album", ""),
                    duration=item.get("duration") or item.get("interval"),
                    source="qqmusic",
                    cover_url=self._provider.get_cover_url(
                        mid=item.get("mid", ""),
                        album_mid=item.get("album_mid", ""),
                        size=500,
                    ),
                )
                for item in search_results
            ]
        except Exception:
            return []

    def get_lyrics(self, result: PluginLyricsResult) -> str | None:
        try:
            return self._provider.get_lyrics(result.song_id)
        except Exception:
            return None
```

Update `plugins/builtin/qqmusic/lib/cover_source.py` similarly:

```python
from .provider import QQMusicOnlineProvider
```

```python
    def __init__(self, context):
        self._context = context
        self._provider = QQMusicOnlineProvider(context)
```

```python
            search_payload = self._provider.search(
                keyword,
                search_type="song",
                page=1,
                page_size=5,
            )
```

```python
    def get_cover_url(
        self,
        mid: str = None,
        album_mid: str = None,
        size: int = 500,
    ):
        return self._provider.get_cover_url(mid=mid, album_mid=album_mid, size=size)
```

- [ ] **Step 4: Run the source adapter tests to verify they pass**

Run:

```bash
uv run pytest tests/test_services/test_qqmusic_plugin_source_adapters.py -v
uv run pytest tests/test_services/test_lyrics_sources_perf_paths.py -v
```

Expected: PASS

- [ ] **Step 5: Commit the source delegation slice**

Run:

```bash
git add tests/test_services/test_qqmusic_plugin_source_adapters.py tests/test_services/test_lyrics_sources_perf_paths.py plugins/builtin/qqmusic/lib/lyrics_source.py plugins/builtin/qqmusic/lib/cover_source.py
git commit -m "统一QQ音乐歌词封面来源入口"
```

### Task 4: Run the focused QQ Music regression suite

**Files:**
- Modify: none
- Verify: `tests/test_plugins/test_qqmusic_plugin.py`
- Verify: `tests/test_services/test_qqmusic_plugin_source_adapters.py`
- Verify: `tests/test_services/test_lyrics_sources_perf_paths.py`
- Verify: `tests/test_system/test_plugin_cover_helpers.py`

- [ ] **Step 1: Run the focused regression commands**

Run:

```bash
uv run pytest tests/test_plugins/test_qqmusic_plugin.py -v
uv run pytest tests/test_services/test_qqmusic_plugin_source_adapters.py -v
uv run pytest tests/test_services/test_lyrics_sources_perf_paths.py -v
uv run pytest tests/test_system/test_plugin_cover_helpers.py -v
```

Expected: PASS on all four commands

- [ ] **Step 2: Inspect the final diff before the last commit**

Run:

```bash
git diff -- plugins/builtin/qqmusic/lib/provider.py plugins/builtin/qqmusic/lib/lyrics_source.py plugins/builtin/qqmusic/lib/cover_source.py tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py tests/test_services/test_lyrics_sources_perf_paths.py
```

Expected: diff only shows provider entry points plus source/test delegation updates required by this plan

- [ ] **Step 3: Create the final integration commit**

Run:

```bash
git add plugins/builtin/qqmusic/lib/provider.py plugins/builtin/qqmusic/lib/lyrics_source.py plugins/builtin/qqmusic/lib/cover_source.py tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py tests/test_services/test_lyrics_sources_perf_paths.py
git commit -m "优化QQ音乐Provider调用链"
```

- [ ] **Step 4: Record the verification commands in the handoff**

Include this exact summary in the final handoff:

```text
Verified with:
- uv run pytest tests/test_plugins/test_qqmusic_plugin.py -v
- uv run pytest tests/test_services/test_qqmusic_plugin_source_adapters.py -v
- uv run pytest tests/test_services/test_lyrics_sources_perf_paths.py -v
- uv run pytest tests/test_system/test_plugin_cover_helpers.py -v
```

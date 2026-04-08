# QQMusic Plugin Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `plugins/builtin/qqmusic` so provider, client, service, and API layers have clearer responsibilities, duplicated normalization/media logic is extracted into helper modules, and host-facing behavior stays compatible.

**Architecture:** Add three pure helper modules under `plugins/builtin/qqmusic/lib`: one for media-related helpers, one for payload normalization, and one for recommendation/favorites section assembly. Then migrate `api.py`, `client.py`, `provider.py`, and `qqmusic_service.py` to call those helpers, delete duplicated private methods, and verify the same normalized payload shapes still reach UI and source-adapter callers.

**Tech Stack:** Python 3, PySide6 plugin package, pytest, monkeypatch/Mock/SimpleNamespace tests, `uv`

---

## File Map

- Create: `plugins/builtin/qqmusic/lib/media_helpers.py`
  Responsibility: pure helpers for cover URLs, lyric selection, and `album_mid` extraction.
- Create: `plugins/builtin/qqmusic/lib/search_normalizers.py`
  Responsibility: pure helpers for QQ Music and remote API payload normalization.
- Create: `plugins/builtin/qqmusic/lib/section_builders.py`
  Responsibility: pure helpers for recommendation/favorites card assembly and cover picking.
- Modify: `plugins/builtin/qqmusic/lib/api.py`
  Responsibility: keep HTTP transport code, delegate payload shaping to shared normalizers/helpers.
- Modify: `plugins/builtin/qqmusic/lib/client.py`
  Responsibility: keep source-selection/fallback logic, delegate normalization and section building to shared helpers.
- Modify: `plugins/builtin/qqmusic/lib/provider.py`
  Responsibility: keep host-facing provider behavior, delegate media extraction/selection to shared helpers.
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_service.py`
  Responsibility: keep QQ Music direct-service orchestration, reuse shared normalizers/helpers for repeated shaping logic.
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`
  Responsibility: provider-level compatibility tests.
- Modify: `tests/test_services/test_qqmusic_plugin_source_adapters.py`
  Responsibility: source-adapter compatibility tests.
- Modify: `tests/test_services/test_qqmusic_service_perf_paths.py`
  Responsibility: service-level payload-shaping regression tests.
- Create: `tests/test_services/test_qqmusic_media_helpers.py`
  Responsibility: unit coverage for media helper functions.
- Create: `tests/test_services/test_qqmusic_search_normalizers.py`
  Responsibility: unit coverage for shared normalizers.
- Create: `tests/test_services/test_qqmusic_section_builders.py`
  Responsibility: unit coverage for section assembly helpers.

### Task 1: Create shared media helpers

**Files:**
- Create: `tests/test_services/test_qqmusic_media_helpers.py`
- Create: `plugins/builtin/qqmusic/lib/media_helpers.py`

- [ ] **Step 1: Write the failing media helper tests**

Create `tests/test_services/test_qqmusic_media_helpers.py` with:

```python
from plugins.builtin.qqmusic.lib.media_helpers import (
    build_album_cover_url,
    build_artist_cover_url,
    extract_album_mid,
    pick_lyric_text,
)


def test_build_album_cover_url_returns_expected_url():
    assert build_album_cover_url("album-1", 500) == (
        "https://y.gtimg.cn/music/photo_new/T002R500x500M000album-1.jpg"
    )


def test_build_artist_cover_url_returns_expected_url():
    assert build_artist_cover_url("artist-1", 300) == (
        "https://y.gtimg.cn/music/photo_new/T001R300x300M000artist-1.jpg"
    )


def test_extract_album_mid_supports_track_info_album():
    payload = {"track_info": {"album": {"mid": "album-from-track"}}}

    assert extract_album_mid(payload) == "album-from-track"


def test_extract_album_mid_supports_flat_album_mid_keys():
    payload = {"data": {"albumMid": "album-from-data"}}

    assert extract_album_mid(payload) == "album-from-data"


def test_pick_lyric_text_prefers_qrc_then_plain_lyric():
    assert pick_lyric_text({"qrc": "[0,100]qrc", "lyric": "[00:00.00]plain"}) == "[0,100]qrc"
    assert pick_lyric_text({"qrc": "", "lyric": "[00:00.00]plain"}) == "[00:00.00]plain"
    assert pick_lyric_text({"qrc": None, "lyric": None}) is None
```

- [ ] **Step 2: Run the media helper tests to verify they fail**

Run: `uv run pytest tests/test_services/test_qqmusic_media_helpers.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'plugins.builtin.qqmusic.lib.media_helpers'`

- [ ] **Step 3: Write the media helper module**

Create `plugins/builtin/qqmusic/lib/media_helpers.py` with:

```python
from __future__ import annotations

from typing import Any, Mapping


def build_album_cover_url(album_mid: str, size: int) -> str | None:
    if not album_mid:
        return None
    return f"https://y.gtimg.cn/music/photo_new/T002R{size}x{size}M000{album_mid}.jpg"


def build_artist_cover_url(singer_mid: str, size: int) -> str | None:
    if not singer_mid:
        return None
    return f"https://y.gtimg.cn/music/photo_new/T001R{size}x{size}M000{singer_mid}.jpg"


def extract_album_mid(detail: Mapping[str, Any] | None) -> str:
    if not isinstance(detail, Mapping):
        return ""
    track = detail.get("track_info", detail.get("data", detail))
    if not isinstance(track, Mapping):
        return ""
    album = track.get("album", {})
    if isinstance(album, Mapping):
        album_mid = album.get("mid") or album.get("albumMid") or album.get("albummid")
        if album_mid:
            return str(album_mid)
    return str(track.get("album_mid") or track.get("albummid") or track.get("albumMid") or "")


def pick_lyric_text(lyric_data: Mapping[str, Any] | None) -> str | None:
    if not isinstance(lyric_data, Mapping):
        return None
    qrc = lyric_data.get("qrc")
    if qrc:
        return str(qrc)
    lyric = lyric_data.get("lyric")
    if lyric:
        return str(lyric)
    return None
```

- [ ] **Step 4: Run the media helper tests to verify they pass**

Run: `uv run pytest tests/test_services/test_qqmusic_media_helpers.py -v`

Expected: PASS with 5 passed

- [ ] **Step 5: Commit the media helper slice**

Run:

```bash
git add tests/test_services/test_qqmusic_media_helpers.py plugins/builtin/qqmusic/lib/media_helpers.py
git commit -m "提取QQ音乐媒体辅助函数"
```

### Task 2: Create shared search normalizers and migrate `api.py`

**Files:**
- Create: `tests/test_services/test_qqmusic_search_normalizers.py`
- Create: `plugins/builtin/qqmusic/lib/search_normalizers.py`
- Modify: `plugins/builtin/qqmusic/lib/api.py`

- [ ] **Step 1: Write the failing search-normalizer tests**

Create `tests/test_services/test_qqmusic_search_normalizers.py` with:

```python
from plugins.builtin.qqmusic.lib.search_normalizers import (
    normalize_album_item,
    normalize_artist_item,
    normalize_detail_song,
    normalize_playlist_item,
    normalize_song_item,
    normalize_top_list_track,
)


def test_normalize_song_item_supports_remote_api_shape():
    song = {
        "mid": "song-1",
        "name": "Song 1",
        "singer": [{"name": "Singer 1"}],
        "album": {"name": "Album 1", "mid": "album-1"},
        "interval": 180,
    }

    assert normalize_song_item(song) == {
        "mid": "song-1",
        "name": "Song 1",
        "title": "Song 1",
        "artist": "Singer 1",
        "singer": "Singer 1",
        "album": "Album 1",
        "album_mid": "album-1",
        "duration": 180,
    }


def test_normalize_detail_song_supports_service_shape():
    song = {
        "mid": "song-1",
        "title": "Song 1",
        "singer": [{"name": "Singer 1"}],
        "album": {"name": "Album 1", "mid": "album-1"},
        "interval": 180,
    }

    assert normalize_detail_song(song) == {
        "mid": "song-1",
        "title": "Song 1",
        "artist": "Singer 1",
        "album": "Album 1",
        "album_mid": "album-1",
        "duration": 180,
    }


def test_normalize_top_list_track_supports_dict_and_object_shapes():
    class _Track:
        mid = "song-2"
        title = "Song 2"
        singer_name = "Singer 2"
        album_name = "Album 2"
        duration = 200

        class album:
            mid = "album-2"

    assert normalize_top_list_track(
        {"mid": "song-1", "title": "Song 1", "artist": [{"name": "Singer 1"}], "album": {"name": "Album 1", "mid": "album-1"}, "interval": 180}
    )["artist"] == "Singer 1"
    assert normalize_top_list_track(_Track())["album_mid"] == "album-2"


def test_normalize_artist_album_and_playlist_items():
    artist = normalize_artist_item({"singerMID": "artist-1", "singerName": "Singer 1", "songNum": 8})
    album = normalize_album_item({"albummid": "album-1", "name": "Album 1", "singer": "Singer 1"})
    playlist = normalize_playlist_item({"dissid": 3, "dissname": "List 1", "nickname": "User 1"})

    assert artist["mid"] == "artist-1"
    assert album["mid"] == "album-1"
    assert playlist["id"] == "3"
```

- [ ] **Step 2: Run the normalizer tests to verify they fail**

Run: `uv run pytest tests/test_services/test_qqmusic_search_normalizers.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'plugins.builtin.qqmusic.lib.search_normalizers'`

- [ ] **Step 3: Write the shared normalizer module**

Create `plugins/builtin/qqmusic/lib/search_normalizers.py` with:

```python
from __future__ import annotations

from typing import Any, Mapping


def _join_artist_names(value: Any) -> str:
    if isinstance(value, list):
        return ", ".join(
            entry.get("name", "")
            for entry in value
            if isinstance(entry, Mapping) and entry.get("name")
        )
    if isinstance(value, Mapping):
        return str(value.get("name", ""))
    return str(value or "")


def normalize_song_item(song: Mapping[str, Any]) -> dict[str, Any]:
    singer_name = _join_artist_names(song.get("singer")) or str(song.get("singerName", ""))
    album_info = song.get("album", {})
    if isinstance(album_info, Mapping):
        album_name = album_info.get("name", "") or song.get("albumName", "")
        album_mid = album_info.get("mid", "") or song.get("albumMid", "")
    else:
        album_name = str(album_info or song.get("albumName", ""))
        album_mid = song.get("albumMid", "")
    title = song.get("name", "") or song.get("songname", "") or song.get("title", "")
    return {
        "mid": song.get("mid", "") or song.get("songmid", "") or song.get("songMid", ""),
        "name": title,
        "title": title,
        "artist": singer_name,
        "singer": singer_name,
        "album": album_name,
        "album_mid": album_mid,
        "duration": song.get("interval", 0) or song.get("duration", 0),
    }


def normalize_detail_song(item: Mapping[str, Any]) -> dict[str, Any]:
    singer_name = _join_artist_names(item.get("singer"))
    album_value = item.get("album", {})
    if isinstance(album_value, Mapping):
        album_name = album_value.get("name", item.get("albumname", ""))
        album_mid = album_value.get("mid", item.get("album_mid", "")) or item.get("albummid", "")
    else:
        album_name = str(album_value or item.get("albumname", ""))
        album_mid = str(item.get("album_mid", item.get("albummid", "")) or "")
    return {
        "mid": item.get("mid", "") or item.get("songmid", ""),
        "title": item.get("title", item.get("name", "")),
        "artist": singer_name,
        "album": album_name,
        "album_mid": album_mid,
        "duration": item.get("interval", item.get("duration", 0)),
    }


def normalize_top_list_track(item: Any) -> dict[str, Any]:
    if isinstance(item, Mapping):
        normalized = normalize_detail_song(item)
        return {
            "mid": normalized["mid"],
            "title": normalized["title"],
            "artist": normalized["artist"],
            "album": normalized["album"],
            "album_mid": normalized["album_mid"],
            "duration": int(normalized["duration"] or 0),
        }
    return {
        "mid": getattr(item, "mid", ""),
        "title": getattr(item, "title", ""),
        "artist": getattr(item, "singer_name", ""),
        "album": getattr(item, "album_name", ""),
        "album_mid": getattr(getattr(item, "album", None), "mid", ""),
        "duration": getattr(item, "duration", 0),
    }


def normalize_artist_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "mid": str(item.get("singerMID", "") or item.get("mid", "")),
        "name": str(item.get("singerName", "") or item.get("name", "")),
        "avatar_url": item.get("singerPic", item.get("avatar", item.get("cover_url", ""))),
        "song_count": int(item.get("songNum", item.get("song_count", item.get("songnum", 0))) or 0),
        "album_count": int(item.get("albumNum", item.get("album_count", item.get("albumnum", 0))) or 0),
        "fan_count": int(item.get("fansNum", item.get("fan_count", item.get("FanNum", 0))) or 0),
    }


def normalize_album_item(item: Mapping[str, Any]) -> dict[str, Any]:
    singer_name = item.get("singer", "")
    if isinstance(singer_name, list):
        singer_name = _join_artist_names(singer_name)
    return {
        "mid": str(item.get("albummid", item.get("albumMID", item.get("mid", "")))),
        "name": item.get("name", item.get("albumname", "")),
        "singer_name": str(singer_name or item.get("singerName", "")),
        "cover_url": item.get("pic", item.get("cover", item.get("cover_url", ""))),
        "song_count": int(item.get("song_num", item.get("song_count", item.get("totalNum", 0))) or 0),
        "publish_date": item.get("publish_date", item.get("pubTime", item.get("publishDate", ""))),
    }


def normalize_playlist_item(item: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("dissid", item.get("id", ""))),
        "mid": item.get("dissMID", item.get("mid", "")),
        "title": item.get("dissname", item.get("title", "")),
        "creator": item.get("nickname", item.get("creator", "")),
        "cover_url": item.get("logo", item.get("imgurl", item.get("cover_url", item.get("cover", "")))),
        "song_count": item.get("songnum", item.get("song_count", 0)),
        "play_count": item.get("listennum", item.get("play_count", 0)),
    }
```

- [ ] **Step 4: Route `api.py` through the shared normalizers**

Update `plugins/builtin/qqmusic/lib/api.py` imports and search-formatting branches:

```python
from .media_helpers import build_album_cover_url, build_artist_cover_url
from .search_normalizers import (
    normalize_album_item,
    normalize_artist_item,
    normalize_playlist_item,
    normalize_song_item,
)
```

```python
        if search_type == "song":
            return {
                "tracks": [normalize_song_item(song) for song in items[:limit]],
                "total": total,
            }
        if search_type == "singer":
            return {
                "artists": [
                    {
                        **normalize_artist_item(item),
                        "avatar_url": (
                            normalize_artist_item(item).get("avatar_url")
                            or build_artist_cover_url(
                                str(item.get("singerMID", item.get("mid", ""))),
                                300,
                            )
                        ),
                    }
                    for item in items[:limit]
                ],
                "total": total,
            }
        if search_type == "album":
            return {
                "albums": [
                    {
                        **normalize_album_item(item),
                        "cover_url": (
                            normalize_album_item(item).get("cover_url")
                            or build_album_cover_url(
                                str(item.get("albummid", item.get("mid", ""))),
                                500,
                            )
                        ),
                    }
                    for item in items[:limit]
                ],
                "total": total,
            }
        return {
            "playlists": [normalize_playlist_item(item) for item in items[:limit]],
            "total": total,
        }
```

Replace `get_artist_cover_url()` with:

```python
    def get_artist_cover_url(self, singer_mid: str, size: int = 300) -> Optional[str]:
        return build_artist_cover_url(singer_mid, size)
```

Delete `_format_song_item()` after all callers are updated.

- [ ] **Step 5: Run the helper and adapter tests**

Run: `uv run pytest tests/test_services/test_qqmusic_search_normalizers.py tests/test_services/test_qqmusic_plugin_source_adapters.py -v`

Expected: PASS with the new helper tests and the existing source-adapter tests still green

- [ ] **Step 6: Commit the normalizer/API slice**

Run:

```bash
git add tests/test_services/test_qqmusic_search_normalizers.py plugins/builtin/qqmusic/lib/search_normalizers.py plugins/builtin/qqmusic/lib/api.py
git commit -m "统一QQ音乐搜索结果归一化"
```

### Task 3: Create section builders and migrate recommendation/favorites assembly

**Files:**
- Create: `tests/test_services/test_qqmusic_section_builders.py`
- Create: `plugins/builtin/qqmusic/lib/section_builders.py`
- Modify: `plugins/builtin/qqmusic/lib/client.py`

- [ ] **Step 1: Write the failing section-builder tests**

Create `tests/test_services/test_qqmusic_section_builders.py` with:

```python
from plugins.builtin.qqmusic.lib.section_builders import build_section, pick_section_cover


def test_pick_section_cover_prefers_track_album_mid():
    items = [{"Track": {"album": {"mid": "album-1"}}}]

    assert pick_section_cover(items) == (
        "https://y.gtimg.cn/music/photo_new/T002R300x300M000album-1.jpg"
    )


def test_pick_section_cover_falls_back_to_cover_url():
    items = [{"cover_url": "https://cover.example/1.jpg"}]

    assert pick_section_cover(items) == "https://cover.example/1.jpg"


def test_build_section_adds_count_only_when_requested():
    recommendation = build_section(
        card_id="guess",
        title="猜你喜欢",
        entry_type="songs",
        items=[{"cover_url": "https://cover.example/1.jpg"}],
    )
    favorites = build_section(
        card_id="fav_songs",
        title="我喜欢的歌曲",
        entry_type="songs",
        items=[{"cover_url": "https://cover.example/1.jpg"}],
        include_count=True,
    )

    assert recommendation["subtitle"] == "1 项"
    assert "count" not in recommendation
    assert favorites["count"] == 1
```

- [ ] **Step 2: Run the section-builder tests to verify they fail**

Run: `uv run pytest tests/test_services/test_qqmusic_section_builders.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'plugins.builtin.qqmusic.lib.section_builders'`

- [ ] **Step 3: Write the section-builder module**

Create `plugins/builtin/qqmusic/lib/section_builders.py` with:

```python
from __future__ import annotations

from typing import Any

from .media_helpers import build_album_cover_url


def pick_section_cover(items: list[dict[str, Any]]) -> str:
    for item in items:
        if not isinstance(item, dict):
            continue
        if isinstance(item.get("Track"), dict):
            album = item["Track"].get("album", {})
            if isinstance(album, dict):
                cover_url = build_album_cover_url(str(album.get("mid", "")), 300)
                if cover_url:
                    return cover_url
        cover_url = item.get("cover_url") or item.get("cover") or item.get("picurl") or item.get("pic")
        if isinstance(cover_url, dict):
            cover_url = cover_url.get("default_url") or cover_url.get("small_url")
        if cover_url:
            return str(cover_url)
        album_mid = item.get("album_mid")
        if album_mid:
            built = build_album_cover_url(str(album_mid), 300)
            if built:
                return built
    return ""


def build_section(
    *,
    card_id: str,
    title: str,
    entry_type: str,
    items: list[dict[str, Any]],
    include_count: bool = False,
) -> dict[str, Any]:
    section = {
        "id": card_id,
        "title": title,
        "subtitle": f"{len(items)} 项",
        "cover_url": pick_section_cover(items),
        "items": items,
        "entry_type": entry_type,
    }
    if include_count:
        section["count"] = len(items)
    return section
```

- [ ] **Step 4: Update `client.py` to use the section builders**

In `plugins/builtin/qqmusic/lib/client.py`, import the helper and replace the two loops in `get_recommendations()` and `get_favorites()`:

```python
from .section_builders import build_section
```

```python
        items: list[dict] = []
        for card_id, title, entry_type, loader in (
            ("home_feed", "首页推荐", "songs", service.get_home_feed),
            ("guess", "猜你喜欢", "songs", service.get_guess_recommend),
            ("radar", "雷达歌单", "songs", service.get_radar_recommend),
            ("songlist", "推荐歌单", "playlists", service.get_recommend_songlist),
            ("newsong", "新歌推荐", "songs", service.get_recommend_newsong),
        ):
            try:
                data = loader() or []
            except Exception:
                data = []
            if data:
                items.append(
                    build_section(
                        card_id=card_id,
                        title=title,
                        entry_type=entry_type,
                        items=data,
                    )
                )
```

```python
                sections.append(
                    build_section(
                        card_id=card_id,
                        title=title,
                        entry_type=entry_type,
                        items=data,
                        include_count=True,
                    )
                )
```

Delete `_pick_cover()` after `client.py` no longer calls it.

- [ ] **Step 5: Run the section-builder and client regression tests**

Run: `uv run pytest tests/test_services/test_qqmusic_section_builders.py tests/test_plugins/test_qqmusic_plugin.py -k "provider or register" -v`

Expected: PASS with the new helper tests and the existing plugin/provider tests still green

- [ ] **Step 6: Commit the section-builder slice**

Run:

```bash
git add tests/test_services/test_qqmusic_section_builders.py plugins/builtin/qqmusic/lib/section_builders.py plugins/builtin/qqmusic/lib/client.py
git commit -m "收敛QQ音乐卡片组装逻辑"
```

### Task 4: Migrate provider and client off duplicated media/normalization helpers

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/provider.py`
- Modify: `plugins/builtin/qqmusic/lib/client.py`
- Modify: `plugins/builtin/qqmusic/lib/api.py`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`
- Modify: `tests/test_services/test_qqmusic_plugin_source_adapters.py`

- [ ] **Step 1: Add compatibility tests for helper-backed provider behavior**

Extend `tests/test_plugins/test_qqmusic_plugin.py` with:

```python
def test_qqmusic_provider_get_lyrics_prefers_qrc_from_local_service(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    service = Mock()
    service.get_lyrics.return_value = {"qrc": "[0,100]word", "lyric": "[00:00.00]plain"}
    api = Mock()
    monkeypatch.setattr("plugins.builtin.qqmusic.lib.client.QQMusicService", Mock(return_value=service))
    monkeypatch.setattr("plugins.builtin.qqmusic.lib.provider.QQMusicPluginAPI", Mock(return_value=api))

    provider = QQMusicOnlineProvider(context)
    monkeypatch.setattr(provider._client, "_can_use_legacy_network", lambda: True)

    assert provider.get_lyrics("song-mid") == "[0,100]word"


def test_qqmusic_provider_get_cover_url_uses_local_song_detail_before_public_api(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    service = Mock()
    service.client.get_song_detail.return_value = {"track_info": {"album": {"mid": "album-from-detail"}}}
    api = Mock()
    monkeypatch.setattr("plugins.builtin.qqmusic.lib.client.QQMusicService", Mock(return_value=service))
    monkeypatch.setattr("plugins.builtin.qqmusic.lib.provider.QQMusicPluginAPI", Mock(return_value=api))

    provider = QQMusicOnlineProvider(context)
    monkeypatch.setattr(provider._client, "_can_use_legacy_network", lambda: True)

    assert provider.get_cover_url(mid="song-1", size=500) == (
        "https://y.gtimg.cn/music/photo_new/T002R500x500M000album-from-detail.jpg"
    )
```

Keep the existing source-adapter tests in `tests/test_services/test_qqmusic_plugin_source_adapters.py`. They should remain green after the refactor without being rewritten around private methods.

- [ ] **Step 2: Run the provider/source-adapter tests to verify the current baseline**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py -v`

Expected: PASS before the refactor, confirming baseline compatibility for provider/source adapters

- [ ] **Step 3: Refactor `provider.py`, `client.py`, and `api.py` to use the shared helpers**

Update imports in `plugins/builtin/qqmusic/lib/provider.py`:

```python
from .media_helpers import build_album_cover_url, extract_album_mid, pick_lyric_text
```

Replace the internal helper methods and inlined selection logic with:

```python
    def get_lyrics(self, song_mid: str) -> str | None:
        service = self._client._get_service()
        if service is not None and self._client._can_use_legacy_network():
            try:
                lyric_data = service.get_lyrics(song_mid) or {}
            except Exception:
                lyric_data = {}
            lyric_text = pick_lyric_text(lyric_data)
            if lyric_text:
                return lyric_text

        try:
            return QQMusicPluginAPI(self._context).get_lyrics(song_mid)
        except Exception:
            return None
```

```python
    def get_cover_url(
        self,
        mid: str | None = None,
        album_mid: str | None = None,
        size: int = 500,
    ) -> str | None:
        cover_url = build_album_cover_url(album_mid or "", size)
        if cover_url:
            return cover_url

        service = self._client._get_service()
        if service is not None and mid and self._client._can_use_legacy_network():
            try:
                detail = service.client.get_song_detail(mid)
            except Exception:
                detail = {}
            cover_url = build_album_cover_url(extract_album_mid(detail), size)
            if cover_url:
                return cover_url

        try:
            return QQMusicPluginAPI(self._context).get_cover_url(mid=mid, album_mid=album_mid, size=size)
        except Exception:
            return None
```

Update `plugins/builtin/qqmusic/lib/client.py` imports:

```python
from .search_normalizers import (
    normalize_album_item,
    normalize_artist_item,
    normalize_detail_song,
    normalize_playlist_item,
    normalize_top_list_track,
)
```

Then replace duplicated formatting branches:

```python
            return {
                "tracks": [normalize_detail_song(item) for item in items if isinstance(item, dict)],
                "total": int(total or 0),
            }
```

```python
                        normalize_artist_item(item)
                        for item in items
                        if isinstance(item, dict)
```

```python
                        normalize_album_item(item)
                        for item in items
                        if isinstance(item, dict)
```

```python
                        normalize_playlist_item(item)
                        for item in items
                        if isinstance(item, dict)
```

```python
                return [normalize_top_list_track(item) for item in data]
```

Delete these now-redundant private methods once callers are removed:

```python
    def _normalize_detail_song(self, item: dict) -> dict:
        ...

    def _normalize_top_list_track(self, item: Any) -> dict[str, Any]:
        ...
```

- [ ] **Step 4: Run the provider/client/source-adapter tests**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py -v`

Expected: PASS with no regressions in provider or source-adapter behavior

- [ ] **Step 5: Commit the provider/client helper migration**

Run:

```bash
git add plugins/builtin/qqmusic/lib/provider.py plugins/builtin/qqmusic/lib/client.py plugins/builtin/qqmusic/lib/api.py tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py
git commit -m "收敛QQ音乐Provider与Client职责"
```

### Task 5: Reuse shared helpers inside `qqmusic_service.py`

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_service.py`
- Modify: `tests/test_services/test_qqmusic_service_perf_paths.py`

- [ ] **Step 1: Add failing service regression tests for helper-backed shaping**

Append these tests to `tests/test_services/test_qqmusic_service_perf_paths.py`:

```python
def test_get_singer_albums_builds_cover_url_from_shared_helper():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_album_list=lambda *_args, **_kwargs: {
            "albumList": [
                {
                    "albumMid": "album-1",
                    "albumName": "Album 1",
                    "singerName": "Singer 1",
                    "totalNum": 10,
                    "publishDate": "2024-01-01",
                }
            ],
            "total": 1,
        }
    )

    result = service.get_singer_albums("singer-1")

    assert result["albums"][0]["cover_url"] == (
        "https://y.gtimg.cn/music/photo_new/T002R300x300M000album-1.jpg"
    )


def test_get_top_list_songs_uses_shared_top_list_normalizer():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_top_list_detail=lambda *_args, **_kwargs: {
            "songInfoList": [
                {
                    "mid": "song-1",
                    "title": "Song 1",
                    "artist": [{"name": "Singer 1"}],
                    "album": {"name": "Album 1", "mid": "album-1"},
                    "interval": 180,
                }
            ]
        },
        query_songs_by_ids=lambda _ids: [],
    )

    songs = service.get_top_list_songs(1)

    assert songs == [
        {
            "mid": "song-1",
            "title": "Song 1",
            "artist": "Singer 1",
            "album": "Album 1",
            "album_mid": "album-1",
            "duration": 180,
        }
    ]
```

- [ ] **Step 2: Run the service regression tests to verify the baseline**

Run: `uv run pytest tests/test_services/test_qqmusic_service_perf_paths.py -v`

Expected: PASS before the refactor, confirming the new tests pin current behavior

- [ ] **Step 3: Replace repeated shaping logic in `qqmusic_service.py` with shared helpers**

Update imports in `plugins/builtin/qqmusic/lib/qqmusic_service.py`:

```python
from .media_helpers import build_album_cover_url
from .search_normalizers import normalize_detail_song, normalize_top_list_track
```

Refactor the repeated song shaping in `get_singer_info()` and `get_singer_info_with_follow_status()` to use a single local append path:

```python
                    normalized_song = normalize_detail_song(
                        {
                            "mid": song_info.get("mid", "") or song_info.get("songmid", ""),
                            "title": song_info.get("name", "") or song_info.get("songname", "") or song_info.get("title", ""),
                            "singer": song_info.get("singer", []),
                            "album": song_info.get("album", {}),
                            "interval": song_info.get("interval", 0) or song_info.get("duration", 0),
                        }
                    )
                    songs.append(
                        {
                            "mid": normalized_song["mid"],
                            "songmid": normalized_song["mid"],
                            "id": song_info.get("id"),
                            "name": normalized_song["title"],
                            "title": normalized_song["title"],
                            "singer": song_info.get("singer", []),
                            "album": {
                                "mid": normalized_song["album_mid"],
                                "name": normalized_song["album"],
                            },
                            "albummid": normalized_song["album_mid"],
                            "albumname": normalized_song["album"],
                            "interval": normalized_song["duration"],
                        }
                    )
```

Refactor album cover generation in `get_singer_albums()`:

```python
                cover_url = build_album_cover_url(album_mid, 300) or ""
```

Refactor `get_top_list_songs()` return shaping:

```python
            return [normalize_top_list_track(song) for song in songs]
```

- [ ] **Step 4: Run the service tests again**

Run: `uv run pytest tests/test_services/test_qqmusic_service_perf_paths.py -v`

Expected: PASS with all existing and new service regression tests green

- [ ] **Step 5: Commit the service cleanup slice**

Run:

```bash
git add plugins/builtin/qqmusic/lib/qqmusic_service.py tests/test_services/test_qqmusic_service_perf_paths.py
git commit -m "收敛QQ音乐服务层格式化逻辑"
```

### Task 6: Final regression and dead-code check

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/provider.py`
- Modify: `plugins/builtin/qqmusic/lib/client.py`
- Modify: `plugins/builtin/qqmusic/lib/api.py`
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_service.py`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`
- Modify: `tests/test_services/test_qqmusic_plugin_source_adapters.py`
- Modify: `tests/test_services/test_qqmusic_service_perf_paths.py`
- Modify: `tests/test_services/test_qqmusic_media_helpers.py`
- Modify: `tests/test_services/test_qqmusic_search_normalizers.py`
- Modify: `tests/test_services/test_qqmusic_section_builders.py`

- [ ] **Step 1: Remove any remaining duplicated private helpers that no longer have callers**

Confirm these methods/functions are deleted if their last caller has moved:

```python
QQMusicOnlineProvider._build_album_cover_url
QQMusicOnlineProvider._extract_album_mid_from_song_detail
QQMusicPluginClient._normalize_detail_song
QQMusicPluginClient._normalize_top_list_track
QQMusicPluginClient._pick_cover
QQMusicPluginAPI._format_song_item
```

If a helper still has a real caller, keep it for now and remove it in a later slice instead of breaking the build.

- [ ] **Step 2: Run the focused QQ Music regression suite**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py tests/test_services/test_qqmusic_service_perf_paths.py tests/test_services/test_qqmusic_media_helpers.py tests/test_services/test_qqmusic_search_normalizers.py tests/test_services/test_qqmusic_section_builders.py -v`

Expected: PASS for the full QQ Music refactor coverage set

- [ ] **Step 3: Run the broader QQ Music/UI regression suite**

Run: `uv run pytest tests/test_ui/test_online_detail_view_actions.py tests/test_ui/test_online_detail_view_thread_cleanup.py tests/test_ui/test_online_music_view_async.py tests/test_ui/test_online_music_view_focus.py tests/test_ui/test_plugin_settings_tab.py tests/test_plugins/test_qqmusic_theme_integration.py -v`

Expected: PASS, confirming the refactor did not break plugin UI integration paths

- [ ] **Step 4: Commit the final cleanup and verification**

Run:

```bash
git add plugins/builtin/qqmusic/lib tests/test_plugins/test_qqmusic_plugin.py tests/test_services/test_qqmusic_plugin_source_adapters.py tests/test_services/test_qqmusic_service_perf_paths.py tests/test_services/test_qqmusic_media_helpers.py tests/test_services/test_qqmusic_search_normalizers.py tests/test_services/test_qqmusic_section_builders.py
git commit -m "优化QQ音乐插件结构"
```

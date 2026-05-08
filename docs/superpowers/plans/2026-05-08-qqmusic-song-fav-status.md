# QQMusic Song Favorite Status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Query QQ Music song favorite status in batch when QQ online song lists load, cache that remote status per list, and drive the QQ context-menu label from the cached remote state instead of local Harmony favorites.

**Architecture:** Add a dedicated `IsSongFanByMid` read path in the QQ client and service layers, adapt it to a `set[str]` for the plugin UI, and thread that remote favorite set through `OnlineDetailView`, `OnlineTracksListView`, and `OnlineTrackContextMenu`. Keep local favorites and QQ remote favorites as separate state so star rendering and right-click QQ actions stop sharing one ambiguous set.

**Tech Stack:** Python, PySide6, pytest, existing QQ Music plugin modules under `plugins/builtin/qqmusic`

---

## File Map

- Modify: `plugins/builtin/qqmusic/lib/qqmusic_client.py`
  - Add batch song favorite status read method for `SongFavRead.IsSongFanByMid`
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_service.py`
  - Add service wrapper that normalizes returned song favorite status by `songMid`
- Modify: `plugins/builtin/qqmusic/lib/plugin_online_music_service.py`
  - Add plugin-facing helper that returns a `set[str]` of remotely favorited song mids
- Modify: `plugins/builtin/qqmusic/lib/context_menus.py`
  - Split local-vs-QQ favorite menu state inputs
- Modify: `plugins/builtin/qqmusic/lib/online_tracks_list_view.py`
  - Store local and QQ favorite sets separately and expose cache update helpers
- Modify: `plugins/builtin/qqmusic/lib/online_detail_view.py`
  - Query QQ favorite status for current list-view page and update cache after toggle actions
- Modify: `tests/test_services/test_qqmusic_client_favorites.py`
  - Add low-level client tests for request payload and `code == 1000`
- Modify: `tests/test_ui/test_online_tracks_list_view.py`
  - Add list-view and context-menu state tests
- Modify: `tests/test_ui/test_online_views_architecture.py`
  - Extend QQ favorite toggle test to verify cache updates

### Task 1: Add QQ client song favorite status read support

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_client.py:756-792`
- Test: `tests/test_services/test_qqmusic_client_favorites.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_services/test_qqmusic_client_favorites.py`:

```python
from plugins.builtin.qqmusic.lib.qqmusic_client import QQMusicClient


def test_get_song_fav_status_uses_song_mid_payload():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        return {"000XOvoA0RVaYt": True}

    client._make_request = fake_make_request

    result = client.get_song_fav_status(["000XOvoA0RVaYt"])

    assert result == {"000XOvoA0RVaYt": True}
    assert captured == {
        "module": "music.musicasset.SongFavRead",
        "method": "IsSongFanByMid",
        "params": {"v_songMid": ["000XOvoA0RVaYt"]},
        "retry": False,
        "use_sign": False,
    }


def test_get_song_fav_status_returns_false_map_for_code_1000():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        assert module == "music.musicasset.SongFavRead"
        assert method == "IsSongFanByMid"
        assert params == {"v_songMid": ["000XOvoA0RVaYt", "001a1b2c3d4e5f"]}
        return {"__qqmusic_code__": 1000}

    client._make_request = fake_make_request

    result = client.get_song_fav_status(["000XOvoA0RVaYt", "001a1b2c3d4e5f"])

    assert result == {
        "000XOvoA0RVaYt": False,
        "001a1b2c3d4e5f": False,
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_qqmusic_client_favorites.py -v`
Expected: FAIL with `AttributeError: 'QQMusicClient' object has no attribute 'get_song_fav_status'`

- [ ] **Step 3: Write minimal implementation**

Add this method in `plugins/builtin/qqmusic/lib/qqmusic_client.py` near the existing song favorite methods:

```python
    def get_song_fav_status(self, song_mids: List[str]) -> Dict[str, bool]:
        """Get QQ Music favorite status for song mids."""
        mids = [str(mid).strip() for mid in song_mids if str(mid).strip()]
        if not mids:
            return {}

        result = self._make_request(
            "music.musicasset.SongFavRead",
            "IsSongFanByMid",
            {"v_songMid": mids},
        )

        if result.get("__qqmusic_code__") == 1000:
            return {mid: False for mid in mids}

        return {str(mid): bool(is_fav) for mid, is_fav in result.items()}
```

Also adjust `_make_request(...)` so `code == 1000` for `music.musicasset.SongFavRead.IsSongFanByMid` is returned in a way the caller can recognize:

```python
        if result.get('code') != 0:
            code = result.get('code')
            if code == 1000 and module == "music.musicasset.SongFavRead" and method == "IsSongFanByMid":
                return {"__qqmusic_code__": 1000}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_qqmusic_client_favorites.py -v`
Expected: PASS for the two new tests and existing playlist favorite tests

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_qqmusic_client_favorites.py plugins/builtin/qqmusic/lib/qqmusic_client.py
git commit -m "支持QQ歌曲收藏状态查询"
```

### Task 2: Add service and plugin adapter methods for QQ favorite mids

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/qqmusic_service.py:1313-1333`
- Modify: `plugins/builtin/qqmusic/lib/plugin_online_music_service.py:157-167`
- Test: `tests/test_services/test_qqmusic_client_favorites.py`

- [ ] **Step 1: Write the failing tests**

Append these tests to `tests/test_services/test_qqmusic_client_favorites.py`:

```python
from plugins.builtin.qqmusic.lib.plugin_online_music_service import PluginOnlineMusicService
from plugins.builtin.qqmusic.lib.qqmusic_service import QQMusicService


def test_qqmusic_service_get_song_fav_status_filters_empty_mids():
    service = QQMusicService({"musicid": "1", "musickey": "secret"})
    service.client.get_song_fav_status = lambda mids: {mid: mid == "fav-mid" for mid in mids}

    result = service.get_song_fav_status(["fav-mid", "", "fav-mid", "plain-mid"])

    assert result == {
        "fav-mid": True,
        "plain-mid": False,
    }


def test_plugin_online_music_service_returns_remote_favorite_mid_set():
    provider = type(
        "ProviderStub",
        (),
        {"get_song_fav_status": lambda self, mids: {"fav-mid": True, "plain-mid": False}},
    )()
    service = PluginOnlineMusicService(context=MagicMock(), credential_provider=provider)

    result = service.get_song_favorite_mids(["fav-mid", "plain-mid"])

    assert result == {"fav-mid"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_services/test_qqmusic_client_favorites.py -v`
Expected: FAIL with missing `get_song_fav_status` on `QQMusicService` and missing `get_song_favorite_mids` on `PluginOnlineMusicService`

- [ ] **Step 3: Write minimal implementation**

Add this method to `plugins/builtin/qqmusic/lib/qqmusic_service.py`:

```python
    def get_song_fav_status(self, song_mids: list[str]) -> dict[str, bool]:
        """Get QQ Music favorite status keyed by song mid."""
        try:
            if not self._credential:
                return {}
            mids = []
            seen = set()
            for mid in song_mids:
                normalized = str(mid).strip()
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                mids.append(normalized)
            if not mids:
                return {}
            result = self.client.get_song_fav_status(mids)
            return {str(mid): bool(is_fav) for mid, is_fav in result.items()}
        except Exception as e:
            logger.error(f"Get song favorite status failed: {e}", exc_info=True)
            return {}
```

Add this method to `plugins/builtin/qqmusic/lib/plugin_online_music_service.py`:

```python
    def get_song_favorite_mids(self, song_mids: list[str]) -> set[str]:
        provider = self._provider
        if provider and hasattr(provider, "get_song_fav_status"):
            result = provider.get_song_fav_status(song_mids)
            if isinstance(result, dict):
                return {
                    str(mid)
                    for mid, is_fav in result.items()
                    if str(mid).strip() and bool(is_fav)
                }
        return set()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_services/test_qqmusic_client_favorites.py -v`
Expected: PASS for the four tests in this file

- [ ] **Step 5: Commit**

```bash
git add tests/test_services/test_qqmusic_client_favorites.py plugins/builtin/qqmusic/lib/qqmusic_service.py plugins/builtin/qqmusic/lib/plugin_online_music_service.py
git commit -m "打通QQ歌曲收藏状态服务"
```

### Task 3: Split local and QQ favorite state in the list view and context menu

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/context_menus.py:23-55`
- Modify: `plugins/builtin/qqmusic/lib/online_tracks_list_view.py:64-130`
- Modify: `plugins/builtin/qqmusic/lib/online_tracks_list_view.py:532-618`
- Test: `tests/test_ui/test_online_tracks_list_view.py`

- [ ] **Step 1: Write the failing tests**

Add these tests to `tests/test_ui/test_online_tracks_list_view.py`:

```python
from unittest.mock import MagicMock, PropertyMock, patch

from domain.online_music import OnlineTrack
from plugins.builtin.qqmusic.lib.context_menus import OnlineTrackContextMenu
from plugins.builtin.qqmusic.lib.online_tracks_list_view import OnlineTracksListView
from tests.test_plugins.qqmusic_test_context import bind_test_context


def test_context_menu_qq_label_uses_remote_favorites_only(monkeypatch):
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)
    bus = MagicMock()
    bus.favorite_changed = MagicMock()
    bus.favorite_changed.connect = MagicMock()
    bus.favorite_changed.disconnect = MagicMock()

    track = OnlineTrack(mid="mid-1", title="Song", duration=180)
    labels = []

    class _Action:
        def __init__(self, text):
            self.text = text
            self.triggered = MagicMock()

    class _Menu:
        def __init__(self, parent=None):
            self.parent = parent

        def addAction(self, text):
            labels.append(text)
            return _Action(text)

        def addSeparator(self):
            return None

        def exec_(self, *_args, **_kwargs):
            return None

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager), \
            patch("plugins.builtin.qqmusic.lib.context_menus.QMenu", _Menu):
        bind_test_context(theme_manager=theme_manager, event_bus=bus)
        menu = OnlineTrackContextMenu()
        menu.show_menu(
            [track],
            favorite_mids={"mid-1"},
            qq_favorite_mids=set(),
            parent_widget=None,
        )

    assert any("QQ" in label for label in labels)
    assert labels[4] != labels[3]


def test_online_tracks_view_load_tracks_stores_qq_favorite_mids():
    app = QApplication.instance() or QApplication([])
    theme_manager = MagicMock()
    theme = MagicMock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.border = "#404040"
    type(theme_manager).current_theme = PropertyMock(return_value=theme)
    bus = MagicMock()
    bus.favorite_changed = MagicMock()
    bus.favorite_changed.connect = MagicMock()
    bus.favorite_changed.disconnect = MagicMock()

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        bind_test_context(theme_manager=theme_manager, event_bus=bus)
        view = OnlineTracksListView()
        tracks = [OnlineTrack(mid="mid-1", title="Song", duration=180)]

        view.load_tracks(tracks, favorite_mids=set(), qq_favorite_mids={"mid-1"})

        assert view._model._favorite_mids == set()
        assert view._model._qq_favorite_mids == {"mid-1"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_online_tracks_list_view.py -v`
Expected: FAIL because `show_menu(...)` and `load_tracks(...)` do not accept `qq_favorite_mids`, and the model does not store `_qq_favorite_mids`

- [ ] **Step 3: Write minimal implementation**

Update `plugins/builtin/qqmusic/lib/context_menus.py`:

```python
    def show_menu(
        self,
        tracks: list,
        favorite_mids: set | None = None,
        qq_favorite_mids: set | None = None,
        parent_widget=None,
    ):
        ...
        all_local_favorited = False
        if favorite_mids:
            all_local_favorited = all(
                getattr(track, "mid", None) and track.mid in favorite_mids
                for track in tracks
            )
        all_qq_favorited = False
        if qq_favorite_mids:
            all_qq_favorited = all(
                getattr(track, "mid", None) and track.mid in qq_favorite_mids
                for track in tracks
            )
        ...
        action = menu.addAction(
            t("remove_from_favorites") if all_local_favorited else t("add_to_favorites")
        )
        action.triggered.connect(lambda: self.favorite_toggled.emit(tracks, all_local_favorited))

        action = menu.addAction(
            t("remove_from_qq_favorites") if all_qq_favorited else t("add_to_qq_favorites")
        )
        action.triggered.connect(lambda: self.qq_fav_toggled.emit(tracks, all_qq_favorited))
```

Update `plugins/builtin/qqmusic/lib/online_tracks_list_view.py`:

```python
        self._favorite_mids: set = set()
        self._qq_favorite_mids: set = set()
```

```python
    def reset_tracks(self, tracks: List[OnlineTrack], favorite_mids: set, qq_favorite_mids: set):
        self.beginResetModel()
        self._tracks = list(tracks)
        self._favorite_mids = set(favorite_mids)
        self._qq_favorite_mids = set(qq_favorite_mids)
        self.endResetModel()
```

```python
    def load_tracks(self, tracks: List[OnlineTrack], favorite_mids: set = None, qq_favorite_mids: set = None):
        self._model.reset_tracks(tracks, favorite_mids or set(), qq_favorite_mids or set())
        self._apply_viewport_bg()
```

```python
        self._context_menu.show_menu(
            tracks,
            favorite_mids=self._model._favorite_mids,
            qq_favorite_mids=self._model._qq_favorite_mids,
            parent_widget=self,
        )
```

Add a cache update helper:

```python
    def set_track_qq_favorite(self, mid: str, is_favorite: bool):
        if is_favorite:
            self._model._qq_favorite_mids.add(mid)
        else:
            self._model._qq_favorite_mids.discard(mid)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_online_tracks_list_view.py -v`
Expected: PASS for the new state tests and the existing hover smoke tests

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_online_tracks_list_view.py plugins/builtin/qqmusic/lib/context_menus.py plugins/builtin/qqmusic/lib/online_tracks_list_view.py
git commit -m "拆分QQ远端收藏状态"
```

### Task 4: Query QQ favorite mids during list load and refresh cache after toggles

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/online_detail_view.py:1573-1579`
- Modify: `plugins/builtin/qqmusic/lib/online_detail_view.py:2001-2013`
- Test: `tests/test_ui/test_online_views_architecture.py`

- [ ] **Step 1: Write the failing tests**

Update `tests/test_ui/test_online_views_architecture.py` with these tests:

```python
def test_online_detail_view_display_songs_loads_remote_qq_favorite_mids():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._detail_type = "album"
    view._use_tracks_list_view = False
    view._songs_table = SimpleNamespace(hide=Mock())
    view._tracks_list_view = SimpleNamespace(show=Mock(), load_tracks=Mock())
    view._service = SimpleNamespace(get_song_favorite_mids=Mock(return_value={"mid-1"}))
    songs = [SimpleNamespace(mid="mid-1"), SimpleNamespace(mid="mid-2"), SimpleNamespace(mid="")]

    OnlineDetailView._display_songs(view, songs)

    view._service.get_song_favorite_mids.assert_called_once_with(["mid-1", "mid-2"])
    view._tracks_list_view.load_tracks.assert_called_once_with(
        songs,
        qq_favorite_mids={"mid-1"},
    )


def test_online_detail_view_qq_favorite_toggle_updates_list_cache():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._service = SimpleNamespace(fav_song=Mock(return_value=True))
    view._tracks_list_view = SimpleNamespace(set_track_qq_favorite=Mock())
    view._notify_favorites_collection_changed = Mock()
    track = SimpleNamespace(id=123, mid="mid-1", title="Song")

    OnlineDetailView._on_list_qq_fav_toggle(view, [track], False)

    view._service.fav_song.assert_called_once_with(123)
    view._tracks_list_view.set_track_qq_favorite.assert_called_once_with("mid-1", True)
    view._notify_favorites_collection_changed.assert_called_once_with("fav_songs")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_online_views_architecture.py -v`
Expected: FAIL because `_display_songs(...)` does not call `get_song_favorite_mids(...)` and `_on_list_qq_fav_toggle(...)` does not update the list cache

- [ ] **Step 3: Write minimal implementation**

Update `plugins/builtin/qqmusic/lib/online_detail_view.py`:

```python
    def _display_songs(self, songs: List[OnlineTrack]):
        """Display songs — use list view for album/recommendations, table for playlist/artist."""
        if self._detail_type == "album" or self._use_tracks_list_view:
            self._songs_table.hide()
            self._tracks_list_view.show()
            mids = []
            seen = set()
            for song in songs:
                mid = str(getattr(song, "mid", "") or "").strip()
                if not mid or mid in seen:
                    continue
                seen.add(mid)
                mids.append(mid)
            qq_favorite_mids = self._service.get_song_favorite_mids(mids) if hasattr(self._service, "get_song_favorite_mids") else set()
            self._tracks_list_view.load_tracks(songs, qq_favorite_mids=qq_favorite_mids)
```

Update `_on_list_qq_fav_toggle(...)`:

```python
    def _on_list_qq_fav_toggle(self, tracks: list, all_favorited: bool):
        """Handle QQ Music favorites toggle from list view context menu."""
        changed = False
        for track in tracks:
            if not track.id:
                logger.warning(f"Cannot toggle QQ favorite for track without id: {track.title}")
                continue
            if all_favorited:
                succeeded = bool(self._service.unfav_song(track.id))
                if succeeded and getattr(track, "mid", None):
                    self._tracks_list_view.set_track_qq_favorite(str(track.mid), False)
            else:
                succeeded = bool(self._service.fav_song(track.id))
                if succeeded and getattr(track, "mid", None):
                    self._tracks_list_view.set_track_qq_favorite(str(track.mid), True)
            changed = succeeded or changed
        if changed:
            self._notify_favorites_collection_changed("fav_songs")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_online_views_architecture.py -v`
Expected: PASS for the two new tests and the existing QQ favorite refresh tests

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_online_views_architecture.py plugins/builtin/qqmusic/lib/online_detail_view.py
git commit -m "接入QQ收藏状态缓存"
```

### Task 5: Full verification and cleanup

**Files:**
- Modify: any touched files above if verification exposes gaps

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
uv run pytest \
  tests/test_services/test_qqmusic_client_favorites.py \
  tests/test_ui/test_online_tracks_list_view.py \
  tests/test_ui/test_online_views_architecture.py -v
```

Expected: all tests PASS

- [ ] **Step 2: Run one broader QQ plugin smoke slice**

Run:

```bash
uv run pytest \
  tests/test_ui/test_online_detail_view_actions.py \
  tests/test_plugins/test_qqmusic_plugin.py -v
```

Expected: PASS, with no regressions in QQ detail actions or plugin integration

- [ ] **Step 3: Review diff for scope discipline**

Run:

```bash
git diff -- plugins/builtin/qqmusic/lib/qqmusic_client.py \
  plugins/builtin/qqmusic/lib/qqmusic_service.py \
  plugins/builtin/qqmusic/lib/plugin_online_music_service.py \
  plugins/builtin/qqmusic/lib/context_menus.py \
  plugins/builtin/qqmusic/lib/online_tracks_list_view.py \
  plugins/builtin/qqmusic/lib/online_detail_view.py \
  tests/test_services/test_qqmusic_client_favorites.py \
  tests/test_ui/test_online_tracks_list_view.py \
  tests/test_ui/test_online_views_architecture.py
```

Expected: only QQ song favorite status plumbing and tests are changed

- [ ] **Step 4: Final commit**

```bash
git add plugins/builtin/qqmusic/lib/qqmusic_client.py \
  plugins/builtin/qqmusic/lib/qqmusic_service.py \
  plugins/builtin/qqmusic/lib/plugin_online_music_service.py \
  plugins/builtin/qqmusic/lib/context_menus.py \
  plugins/builtin/qqmusic/lib/online_tracks_list_view.py \
  plugins/builtin/qqmusic/lib/online_detail_view.py \
  tests/test_services/test_qqmusic_client_favorites.py \
  tests/test_ui/test_online_tracks_list_view.py \
  tests/test_ui/test_online_views_architecture.py
git commit -m "修复QQ歌曲收藏状态"
```

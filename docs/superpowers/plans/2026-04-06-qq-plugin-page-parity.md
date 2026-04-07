# QQ Plugin Page Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the QQ Music plugin page approach the legacy QQ page by restoring high-value search, detail, recommendation/favorites, ranking, and search-polish behaviors inside the plugin runtime.

**Architecture:** Keep `QQMusicRootView` as the plugin entry page, move data normalization into `QQMusicPluginClient`, and reuse host-neutral shared widgets like `OnlineGridView`, `OnlineDetailView`, `OnlineTracksListView`, and `RecommendSection` instead of reintroducing the legacy host view. All playback, queue, and download actions continue to flow through `context.services.media`.

**Tech Stack:** Python 3.11, PySide6, pytest, pytest-qt, `uv`

---

## File Map

- Modify: `plugins/builtin/qqmusic/lib/root_view.py:39-683` — expand the page state model, swap simplified result/detail widgets for shared views, add navigation stack, batch actions, ranking view switching, and search polish
- Modify: `plugins/builtin/qqmusic/lib/client.py:36-195` — normalize paged search payloads, recommendation card metadata, favorites card metadata, and detail payloads
- Modify: `plugins/builtin/qqmusic/lib/provider.py:17-65` — expose paged search and any normalized helper methods the root view needs
- Modify: `tests/test_plugins/test_qqmusic_plugin.py:110-655` — add focused tests for Batch A-D behaviors and update existing assertions to match the richer UI

### Task 1: Batch A Search Results and Detail View Parity

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/root_view.py:39-683`
- Modify: `plugins/builtin/qqmusic/lib/provider.py:23-54`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py:110-470`

- [ ] **Step 1: Write the failing tests for paged results, grid results, and detail batch actions**

```python
def test_root_view_song_search_uses_table_and_pagination(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "Tester", "quality": "320"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "tracks": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210}
        ],
        "total": 61,
        "page": 1,
        "page_size": 30,
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song 1")
    view._run_search()

    assert view._results_stack.currentWidget() is view._songs_page
    assert view._results_table.rowCount() == 1
    assert view._page_label.text() == "1"
    assert view._next_btn.isEnabled() is True
    provider.search.assert_called_once_with("Song 1", "song", page=1, page_size=30)


def test_root_view_artist_search_uses_grid_and_load_more(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "Tester", "quality": "320"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.side_effect = [
        {
            "artists": [{"mid": "artist-1", "name": "Singer 1", "song_count": 12}],
            "total": 61,
            "page": 1,
            "page_size": 30,
        },
        {
            "artists": [{"mid": "artist-2", "name": "Singer 2", "song_count": 8}],
            "total": 61,
            "page": 2,
            "page_size": 30,
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._on_load_more_artists()

    assert view._results_stack.currentWidget() is view._artists_page
    assert provider.search.call_args_list[0].args[:2] == ("Singer", "singer")
    assert provider.search.call_args_list[1].kwargs == {"page": 2, "page_size": 30}


def test_root_view_detail_view_supports_batch_actions(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "Tester", "quality": "flac"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "artists": [{"mid": "artist-1", "name": "Singer 1", "song_count": 12}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "description": "desc",
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 1", "album": "Album 1", "duration": 180},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail_from_grid({"mid": "artist-1", "name": "Singer 1"})
    view._play_all_from_detail_tracks()
    view._add_all_detail_tracks_to_queue()
    view._insert_all_detail_tracks_to_queue()

    assert context.services.media.play_online_track.call_count == 1
    assert context.services.media.add_online_track_to_queue.call_count == 2
    assert context.services.media.insert_online_track_to_queue.call_count == 2
```

- [ ] **Step 2: Run the focused plugin page tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "pagination or load_more or batch_actions" -v`
Expected: FAIL with missing attributes such as `_results_table`, `_page_label`, `_on_load_more_artists`, or missing detail batch methods on `QQMusicRootView`

- [ ] **Step 3: Implement paged search, shared result widgets, and shared detail view**

```python
# plugins/builtin/qqmusic/lib/provider.py
def search(
    self,
    keyword: str,
    search_type: str = "song",
    *,
    page: int = 1,
    page_size: int = 30,
) -> dict[str, Any]:
    return self._client.search(keyword, search_type=search_type, limit=page_size, page=page)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
from domain.online_music import OnlineAlbum, OnlineArtist, OnlinePlaylist, OnlineTrack
from ui.views.online_detail_view import OnlineDetailView
from ui.views.online_grid_view import OnlineGridView

self._navigation_stack: list[dict[str, Any]] = []
self._current_keyword = ""
self._current_page = 1
self._grid_page = 1
self._grid_page_size = 30
self._grid_total = 0
self._current_tracks: list[dict[str, Any]] = []

self._songs_page = QWidget(self._results_page)
self._results_table = QTableWidget(0, 4, self._songs_page)
self._artists_page = OnlineGridView(data_type="singer", parent=self._results_page)
self._albums_page = OnlineGridView(data_type="album", parent=self._results_page)
self._playlists_page = OnlineGridView(data_type="playlist", parent=self._results_page)
self._detail_view = OnlineDetailView(parent=self)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
def _run_search(self) -> None:
    keyword = self._search_input.text().strip()
    if not keyword:
        self._home_stack.setCurrentWidget(self._home_page)
        return
    self._record_search_history(keyword)
    self._current_keyword = keyword
    self._current_page = 1
    self._grid_page = 1
    self._perform_search(page=1)


def _perform_search(self, *, page: int) -> None:
    search_type = self._SEARCH_TYPES[self._search_type_tabs.currentIndex()]
    payload = self._provider.search(
        self._current_keyword,
        search_type,
        page=page,
        page_size=self._grid_page_size,
    )
    self._populate_search_results(search_type, payload, page=page)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
def _show_detail_with_tracks(self, title: str, description: str, songs: list[dict[str, Any]]) -> None:
    tracks = [self._coerce_online_track(song) for song in songs]
    self._detail_tracks = tracks
    self._detail_view.load_songs_directly(songs, title, "")
    self._home_stack.setCurrentWidget(self._detail_page)


def _play_all_from_detail_tracks(self) -> None:
    if not self._detail_tracks:
        return
    first = self._build_playback_request(self._track_to_item(self._detail_tracks[0]))
    self._context.services.media.play_online_track(first)


def _add_all_detail_tracks_to_queue(self) -> None:
    for track in self._detail_tracks:
        self._context.services.media.add_online_track_to_queue(
            self._build_playback_request(self._track_to_item(track))
        )


def _insert_all_detail_tracks_to_queue(self) -> None:
    for track in self._detail_tracks:
        self._context.services.media.insert_online_track_to_queue(
            self._build_playback_request(self._track_to_item(track))
        )
```

- [ ] **Step 4: Run the Batch A test slice and the existing plugin navigation tests**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "search or detail or pagination or load_more or batch_actions" -v`
Expected: PASS for the new Batch A tests and the existing detail navigation tests

- [ ] **Step 5: Commit Batch A**

```bash
git add tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/provider.py plugins/builtin/qqmusic/lib/root_view.py
git commit -m "迁移QQ插件搜索和详情页"
```

### Task 2: Batch B Recommendation and Favorites Card Parity

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/client.py:70-176`
- Modify: `plugins/builtin/qqmusic/lib/root_view.py:72-683`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py:196-540`

- [ ] **Step 1: Write the failing tests for card-based favorites and recommendations**

```python
def test_root_view_loads_recommendation_cards(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "Tester", "quality": "320"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {"id": "guess", "title": "猜你喜欢", "subtitle": "2 项", "cover_url": "", "items": [{"mid": "song-1", "title": "Song 1"}]},
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert view._recommend_section.isHidden() is False
    assert view._recommend_section._cards_layout.count() == 1


def test_root_view_favorite_song_card_opens_detail_view(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "Tester", "quality": "320"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "id": "fav_songs",
            "title": "我喜欢的歌曲",
            "subtitle": "1 首",
            "cover_url": "",
            "items": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
            "entry_type": "songs",
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_favorite_card(provider.get_favorites.return_value[0])

    assert view._home_stack.currentWidget() is view._detail_page


def test_root_view_recommendation_playlist_card_opens_playlist_results(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "Tester", "quality": "320"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {
            "id": "songlist",
            "title": "推荐歌单",
            "subtitle": "1 项",
            "cover_url": "",
            "items": [{"id": "pl-1", "title": "Playlist 1", "creator": "Tester", "song_count": 12}],
            "entry_type": "playlists",
        },
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_recommendation_card(provider.get_recommendations.return_value[0])

    assert view._home_stack.currentWidget() is view._results_page
    assert view._results_stack.currentWidget() is view._playlists_page
```

- [ ] **Step 2: Run the focused card tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "recommendation_cards or favorite_song_card or recommendation_playlist_card" -v`
Expected: FAIL because `_recommend_section`, `_favorites_section`, `_open_favorite_card`, or `_open_recommendation_card` do not yet exist

- [ ] **Step 3: Normalize card payloads in the client and render `RecommendSection` cards in the root view**

```python
# plugins/builtin/qqmusic/lib/client.py
def get_recommendations(self) -> list[dict]:
    service = self._get_service()
    if service is None:
        return []
    cards: list[dict] = []
    for card_id, title, entry_type, loader in (
        ("home_feed", "首页推荐", "songs", service.get_home_feed),
        ("guess", "猜你喜欢", "songs", service.get_guess_recommend),
        ("radar", "雷达歌单", "songs", service.get_radar_recommend),
        ("songlist", "推荐歌单", "playlists", service.get_recommend_songlist),
        ("newsong", "新歌推荐", "songs", service.get_recommend_newsong),
    ):
        data = loader() or []
        if data:
            cards.append(
                {
                    "id": card_id,
                    "title": title,
                    "subtitle": f"{len(data)} 项",
                    "cover_url": self._pick_cover(data),
                    "items": data,
                    "entry_type": entry_type,
                }
            )
    return cards
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
from ui.widgets.recommend_card import RecommendSection

self._favorites_section = RecommendSection(title="我的收藏", parent=self._home_page)
self._recommend_section = RecommendSection(title="推荐内容", parent=self._home_page)
self._favorites_section.recommendation_clicked.connect(self._open_favorite_card)
self._recommend_section.recommendation_clicked.connect(self._open_recommendation_card)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
def _load_logged_in_sections(self) -> None:
    favorites = self._safe_provider_call("get_favorites", [])
    recommendations = self._safe_provider_call("get_recommendations", [])
    self._favorites_section.setHidden(not bool(favorites))
    self._recommend_section.setHidden(not bool(recommendations))
    if favorites:
        self._favorites_section.load_recommendations(favorites)
    if recommendations:
        self._recommend_section.load_recommendations(recommendations)


def _open_favorite_card(self, data: dict[str, Any]) -> None:
    self._open_card_entry(data)


def _open_recommendation_card(self, data: dict[str, Any]) -> None:
    self._open_card_entry(data)
```

- [ ] **Step 4: Run the Batch B tests plus the earlier favorites/recommendation navigation coverage**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "favorite or recommendation" -v`
Expected: PASS for the new card tests and the existing favorites/recommendation navigation expectations after they are updated to card APIs

- [ ] **Step 5: Commit Batch B**

```bash
git add tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/client.py plugins/builtin/qqmusic/lib/root_view.py
git commit -m "迁移QQ插件推荐和收藏卡片"
```

### Task 3: Batch C Ranking View and Batch Song Actions

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/root_view.py:84-683`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py:224-655`

- [ ] **Step 1: Write the failing tests for ranking view switching and ranking batch actions**

```python
def test_root_view_ranking_toggle_switches_between_table_and_list(qtbot):
    settings = Mock()
    state = {"nick": "", "quality": "320", "ranking_view_mode": "table"}
    settings.get.side_effect = lambda key, default=None: state.get(key, default)
    settings.set.side_effect = lambda key, value: state.__setitem__(key, value)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210}]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._toggle_ranking_view_mode()

    assert state["ranking_view_mode"] == "list"
    assert view._ranking_stacked_widget.currentWidget() is view._ranking_list_view


def test_root_view_ranking_batch_queue_actions_use_media_bridge(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "", "quality": "320", "ranking_view_mode": "table"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    tracks = [view._current_tracks[0], view._current_tracks[1]]
    view._add_selected_tracks_to_queue(tracks)
    view._insert_selected_tracks_to_queue(tracks)
    view._download_selected_tracks(tracks)

    assert context.services.media.add_online_track_to_queue.call_count == 2
    assert context.services.media.insert_online_track_to_queue.call_count == 2
    assert context.services.media.cache_remote_track.call_count == 2
```

- [ ] **Step 2: Run the focused ranking tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "ranking_toggle or ranking_batch_queue" -v`
Expected: FAIL because ranking stacked widgets, preference persistence, or bulk action helpers are not implemented

- [ ] **Step 3: Add ranking stacked widgets and shared batch-action helpers**

```python
# plugins/builtin/qqmusic/lib/root_view.py
from ui.views.online_tracks_list_view import OnlineTracksListView

self._ranking_stacked_widget = QStackedWidget(self._home_page)
self._ranking_list_view = OnlineTracksListView(parent=self._home_page)
self._ranking_stacked_widget.addWidget(self._top_tracks_table)
self._ranking_stacked_widget.addWidget(self._ranking_list_view)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
def _toggle_ranking_view_mode(self) -> None:
    current = str(self._context.settings.get("ranking_view_mode", "table"))
    new_value = "list" if current == "table" else "table"
    self._context.settings.set("ranking_view_mode", new_value)
    self._ranking_stacked_widget.setCurrentWidget(
        self._ranking_list_view if new_value == "list" else self._top_tracks_table
    )


def _add_selected_tracks_to_queue(self, tracks: list[dict[str, Any]]) -> None:
    for item in tracks:
        self._context.services.media.add_online_track_to_queue(self._build_playback_request(item))


def _insert_selected_tracks_to_queue(self, tracks: list[dict[str, Any]]) -> None:
    for item in tracks:
        self._context.services.media.insert_online_track_to_queue(self._build_playback_request(item))


def _download_selected_tracks(self, tracks: list[dict[str, Any]]) -> None:
    for item in tracks:
        self._context.services.media.cache_remote_track(self._build_playback_request(item))
```

- [ ] **Step 4: Run the Batch C ranking tests and the existing top-track playback tests**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "ranking or top_track_activation" -v`
Expected: PASS for ranking toggle, ranking batch actions, and top-track playback coverage

- [ ] **Step 5: Commit Batch C**

```bash
git add tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/root_view.py
git commit -m "迁移QQ插件榜单交互"
```

### Task 4: Batch D Search Popup, Completion Coordination, and UI Text Refresh

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/root_view.py:39-683`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py:542-655`

- [ ] **Step 1: Write the failing tests for search popup state, completion debounce state, and home recovery**

```python
def test_root_view_clearing_search_returns_home_sections(qtbot):
    settings = Mock()
    store = {"nick": "Tester", "quality": "320", "search_history": []}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [{"id": "guess", "title": "猜你喜欢", "subtitle": "1 项", "cover_url": "", "items": [{"mid": "song-1"}], "entry_type": "songs"}]
    provider.get_favorites.return_value = [{"id": "fav_songs", "title": "我喜欢的歌曲", "subtitle": "1 首", "cover_url": "", "items": [{"mid": "song-1"}], "entry_type": "songs"}]
    provider.search.return_value = {"tracks": [], "total": 0, "page": 1, "page_size": 30}

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("abc")
    view._run_search()
    view._on_search_text_changed("")

    assert view._home_stack.currentWidget() is view._home_page
    assert view._favorites_section.isHidden() is False
    assert view._recommend_section.isHidden() is False


def test_root_view_completion_updates_prefix_and_model(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {"nick": "", "quality": "320"}.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦"}]
    provider.complete.return_value = [{"hint": "周杰伦 晴天"}, {"hint": "周杰伦 七里香"}]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("周杰伦")
    view._on_search_text_changed("周杰伦")
    view._trigger_completion()

    assert view._completer.completionPrefix() == "周杰伦"
    assert view._completer.model().rowCount() == 2
```

- [ ] **Step 2: Run the focused search-polish tests to verify they fail**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -k "clearing_search_returns_home or completion_updates_prefix" -v`
Expected: FAIL because home recovery, completion coordination, or popup state handling still reflects the simplified implementation

- [ ] **Step 3: Add search state recovery, completion coordination, and `refresh_ui` text updates**

```python
# plugins/builtin/qqmusic/lib/root_view.py
def _on_search_text_changed(self, text: str) -> None:
    keyword = text.strip()
    if not keyword and self._current_keyword:
        self._current_keyword = ""
        self._current_page = 1
        self._grid_page = 1
        self._home_stack.setCurrentWidget(self._home_page)
        self._load_home_sections()
        return
    if keyword:
        self._update_completion(keyword)
```

```python
# plugins/builtin/qqmusic/lib/root_view.py
def refresh_ui(self) -> None:
    self._status.setText(self._build_status_text())
    self._search_input.setPlaceholderText("搜索 QQ 音乐")
    self._search_btn.setText("搜索")
    self._search_type_tabs.setTabText(0, "歌曲")
    self._search_type_tabs.setTabText(1, "歌手")
    self._search_type_tabs.setTabText(2, "专辑")
    self._search_type_tabs.setTabText(3, "歌单")
    self._load_home_sections()
```

- [ ] **Step 4: Run the full focused QQ plugin page test file**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py -v`
Expected: PASS for the QQ plugin page coverage added in Tasks 1-4

- [ ] **Step 5: Commit Batch D**

```bash
git add tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/root_view.py
git commit -m "完善QQ插件页搜索体验"
```

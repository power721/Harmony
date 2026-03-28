# QQ Music Favorites Cards Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 4 favorites sections (收藏歌曲, 创建的歌单, 收藏的歌单, 收藏专辑) to OnlineMusicView above the existing recommend section.

**Architecture:** Add low-level API methods to QQMusicClient, high-level methods to QQMusicService, extend RecommendSection to accept custom titles, add FavWorker QThread, and wire 4 sections into OnlineMusicView.

**Tech Stack:** Python, PySide6, requests, existing QQ Music API client

---

### Task 1: Add favorites API methods to QQMusicClient

**Files:**
- Modify: `services/cloud/qqmusic/client.py` (append 4 methods before `verify_login`)

- [ ] **Step 1: Add `get_fav_song`, `get_created_songlist`, `get_fav_songlist`, `get_fav_album` methods**

Add these 4 methods to `QQMusicClient` before `verify_login` (before line 734):

```python
def get_fav_song(self, euin: str, page: int = 1, num: int = 30) -> Dict:
    """Get user's favorite songs (dirid=201)."""
    params = {
        "disstid": 0,
        "dirid": 201,
        "tag": True,
        "song_begin": num * (page - 1),
        "song_num": num,
        "userinfo": True,
        "orderlist": True,
        "enc_host_uin": euin,
    }
    return self._make_request("music.srfDissInfo.DissInfo", "CgiGetDiss", params)

def get_created_songlist(self, uin: str) -> Dict:
    """Get user's created playlists."""
    params = {"uin": uin}
    return self._make_request("music.musicasset.PlaylistBaseRead", "GetPlaylistByUin", params)

def get_fav_songlist(self, euin: str, page: int = 1, num: int = 30) -> Dict:
    """Get user's favorited external playlists."""
    params = {"uin": euin, "offset": (page - 1) * num, "size": num}
    return self._make_request("music.musicasset.PlaylistFavRead", "CgiGetPlaylistFavInfo", params)

def get_fav_album(self, euin: str, page: int = 1, num: int = 30) -> Dict:
    """Get user's favorited albums."""
    params = {"euin": euin, "offset": (page - 1) * num, "size": num}
    return self._make_request("music.musicasset.AlbumFavRead", "CgiGetAlbumFavInfo", params)
```

- [ ] **Step 2: Run existing tests**

Run: `uv run pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add services/cloud/qqmusic/client.py
git commit -m "feat: add favorites API methods to QQMusicClient"
```

---

### Task 2: Add favorites service methods to QQMusicService

**Files:**
- Modify: `services/cloud/qqmusic/qqmusic_service.py` (append methods before `set_credential`)

- [ ] **Step 1: Add helper methods and 4 favorites methods**

Add these methods to `QQMusicService` before `set_credential` (before line 701):

```python
def _get_euin(self) -> str:
    """Get encrypted UIN from credential."""
    if not self._credential:
        return ""
    return (
        self._credential.get("encrypt_uin")
        or self._credential.get("encryptUin")
        or ""
    )

def _get_uin(self) -> str:
    """Get UIN from credential."""
    if not self._credential:
        return ""
    return str(self._credential.get("musicid", ""))

def get_my_fav_songs(self, page: int = 1, num: int = 30) -> List[Dict[str, Any]]:
    """Get current user's favorite songs."""
    try:
        euin = self._get_euin()
        if not euin:
            return []
        result = self.client.get_fav_song(euin, page=page, num=num)
        if not result:
            return []
        songs = result.get("songlist", []) or []
        tracks = []
        for song in songs:
            song_info = song.get("data", song) if isinstance(song, dict) else song
            if not isinstance(song_info, dict):
                continue
            singer_info = song_info.get("singer", [])
            if isinstance(singer_info, list) and singer_info:
                singer_name = " / ".join(s.get("name", "") for s in singer_info)
            elif isinstance(singer_info, dict):
                singer_name = singer_info.get("name", "")
            else:
                singer_name = ""
            album_info = song_info.get("album", {})
            album_name = album_info.get("name", "") if isinstance(album_info, dict) else ""
            tracks.append({
                "mid": song_info.get("songmid", "") or song_info.get("mid", ""),
                "title": song_info.get("songname", "") or song_info.get("name", "") or song_info.get("title", ""),
                "singer": singer_name,
                "album": album_name,
                "album_mid": album_info.get("mid", "") if isinstance(album_info, dict) else "",
                "duration": song_info.get("interval", 0) or 0,
                "cover_url": (f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_info.get('mid', '')}.jpg"
                              if isinstance(album_info, dict) and album_info.get("mid") else ""),
            })
        return tracks
    except Exception as e:
        logger.error(f"Get favorite songs failed: {e}", exc_info=True)
        return []

def get_my_created_songlists(self) -> List[Dict[str, Any]]:
    """Get current user's created playlists."""
    try:
        uin = self._get_uin()
        if not uin:
            return []
        result = self.client.get_created_songlist(uin)
        if not result:
            return []
        playlists = result.get("playlist", []) or result.get("list", []) or []
        items = []
        for pl in playlists:
            if not isinstance(pl, dict):
                continue
            items.append({
                "id": pl.get("tid", "") or pl.get("dissid", ""),
                "title": pl.get("dissname", "") or pl.get("title", "") or pl.get("name", ""),
                "cover_url": pl.get("logo", "") or pl.get("picurl", "") or pl.get("imgurl", ""),
                "song_count": pl.get("song_cnt", 0) or pl.get("songnum", 0),
                "creator": pl.get("nickname", "") or pl.get("creator", ""),
            })
        return items
    except Exception as e:
        logger.error(f"Get created songlists failed: {e}", exc_info=True)
        return []

def get_my_fav_songlists(self, page: int = 1, num: int = 30) -> List[Dict[str, Any]]:
    """Get current user's favorited external playlists."""
    try:
        euin = self._get_euin()
        if not euin:
            return []
        result = self.client.get_fav_songlist(euin, page=page, num=num)
        if not result:
            return []
        playlists = result.get("playlist", []) or result.get("list", []) or []
        items = []
        for pl in playlists:
            if not isinstance(pl, dict):
                continue
            pl_info = pl.get("diss_info", pl) if "diss_info" in pl else pl
            items.append({
                "id": pl_info.get("tid", "") or pl_info.get("dissid", ""),
                "title": pl_info.get("dissname", "") or pl_info.get("title", "") or pl_info.get("name", ""),
                "cover_url": pl_info.get("logo", "") or pl_info.get("picurl", "") or pl_info.get("imgurl", ""),
                "song_count": pl_info.get("song_cnt", 0) or pl_info.get("songnum", 0),
                "creator": pl_info.get("nickname", "") or pl_info.get("creator", ""),
            })
        return items
    except Exception as e:
        logger.error(f"Get favorite songlists failed: {e}", exc_info=True)
        return []

def get_my_fav_albums(self, page: int = 1, num: int = 30) -> List[Dict[str, Any]]:
    """Get current user's favorited albums."""
    try:
        euin = self._get_euin()
        if not euin:
            return []
        result = self.client.get_fav_album(euin, page=page, num=num)
        if not result:
            return []
        albums = result.get("albumList", []) or result.get("list", []) or []
        items = []
        for album in albums:
            if not isinstance(album, dict):
                continue
            album_mid = album.get("albumMid", "") or album.get("mid", "")
            items.append({
                "mid": album_mid,
                "title": album.get("albumName", "") or album.get("name", ""),
                "cover_url": (f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg"
                              if album_mid else ""),
                "singer_name": album.get("singerName", "") or album.get("singer_name", ""),
                "song_count": album.get("totalNum", 0) or 0,
            })
        return items
    except Exception as e:
        logger.error(f"Get favorite albums failed: {e}", exc_info=True)
        return []
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add services/cloud/qqmusic/qqmusic_service.py
git commit -m "feat: add favorites service methods to QQMusicService"
```

---

### Task 3: Make RecommendSection support custom title

**Files:**
- Modify: `ui/widgets/recommend_card.py` (change `RecommendSection.__init__`)

- [ ] **Step 1: Add `title` parameter to `RecommendSection.__init__`**

In `ui/widgets/recommend_card.py`, change `RecommendSection.__init__` (line 201):

```python
def __init__(self, title: str = None, parent=None):
    super().__init__(parent)
    self._cards: List[RecommendCard] = []
    self._custom_title = title
    self._setup_ui()
```

Change the title label setup in `_setup_ui` (line 216):

```python
self._title_label = QLabel(self._custom_title if self._custom_title else t("recommendations"))
```

Update `refresh_ui` (line 351-354):

```python
def refresh_ui(self):
    """Refresh UI for language changes."""
    if hasattr(self, '_title_label'):
        if self._custom_title:
            self._title_label.setText(self._custom_title)
        else:
            self._title_label.setText(t("recommendations"))
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add ui/widgets/recommend_card.py
git commit -m "feat: allow custom title in RecommendSection"
```

---

### Task 4: Add i18n keys for favorites

**Files:**
- Modify: `system/i18n.py` (add Chinese/English keys)

- [ ] **Step 1: Add translation keys**

Find the translation dicts (zh and en) in `system/i18n.py` and add:

Chinese dict:
```python
"fav_songs": "收藏歌曲",
"created_playlists": "创建的歌单",
"fav_playlists": "收藏的歌单",
"fav_albums": "收藏专辑",
```

English dict:
```python
"fav_songs": "Favorite Songs",
"created_playlists": "My Playlists",
"fav_playlists": "Favorite Playlists",
"fav_albums": "Favorite Albums",
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 3: Commit**

```bash
git add system/i18n.py
git commit -m "feat: add i18n keys for favorites sections"
```

---

### Task 5: Add FavWorker QThread and wire into OnlineMusicView

**Files:**
- Modify: `ui/views/online_music_view.py`

- [ ] **Step 1: Add `FavWorker` class after `RecommendWorker` (after line 215)**

```python
class FavWorker(QThread):
    """Background worker for loading favorites."""

    fav_ready = Signal(str, list)  # (fav_type, list of items)

    def __init__(self, qqmusic_service, fav_type: str, page: int = 1, num: int = 30):
        super().__init__()
        self._qqmusic_service = qqmusic_service
        self._fav_type = fav_type
        self._page = page
        self._num = num

    def run(self):
        try:
            if not self._qqmusic_service:
                self.fav_ready.emit(self._fav_type, [])
                return
            result = []
            if self._fav_type == "fav_songs":
                result = self._qqmusic_service.get_my_fav_songs(page=self._page, num=self._num)
            elif self._fav_type == "created_playlists":
                result = self._qqmusic_service.get_my_created_songlists()
            elif self._fav_type == "fav_playlists":
                result = self._qqmusic_service.get_my_fav_songlists(page=self._page, num=self._num)
            elif self._fav_type == "fav_albums":
                result = self._qqmusic_service.get_my_fav_albums(page=self._page, num=self._num)
            self.fav_ready.emit(self._fav_type, result)
        except Exception as e:
            logger.error(f"Get favorites {self._fav_type} failed: {e}")
            self.fav_ready.emit(self._fav_type, [])
```

- [ ] **Step 2: Add favorites state in `OnlineMusicView.__init__` (after line 384)**

After `self._recommendations_loaded = False`:

```python
# Favorites state
self._fav_workers: List[FavWorker] = []
self._fav_loaded = False
```

- [ ] **Step 3: Add 4 RecommendSection widgets in `_setup_ui` (between search_bar and recommend_section, lines 413-418)**

Replace the existing recommend section creation block (lines 415-418) with 4 fav sections + the recommend section:

```python
# Favorites sections (shown when logged in, above recommendations)
self._fav_songs_section = RecommendSection(title=t("fav_songs"), parent=self)
self._fav_songs_section.recommendation_clicked.connect(self._on_fav_songs_clicked)
self._fav_songs_section.hide()
layout.addWidget(self._fav_songs_section)

self._created_playlists_section = RecommendSection(title=t("created_playlists"), parent=self)
self._created_playlists_section.recommendation_clicked.connect(self._on_playlist_clicked)
self._created_playlists_section.hide()
layout.addWidget(self._created_playlists_section)

self._fav_playlists_section = RecommendSection(title=t("fav_playlists"), parent=self)
self._fav_playlists_section.recommendation_clicked.connect(self._on_playlist_clicked)
self._fav_playlists_section.hide()
layout.addWidget(self._fav_playlists_section)

self._fav_albums_section = RecommendSection(title=t("fav_albums"), parent=self)
self._fav_albums_section.recommendation_clicked.connect(self._on_fav_album_clicked)
self._fav_albums_section.hide()
layout.addWidget(self._fav_albums_section)

# Recommendations section (shown when logged in)
self._recommend_section = RecommendSection(self)
self._recommend_section.recommendation_clicked.connect(self._on_recommendation_clicked)
layout.addWidget(self._recommend_section)
```

Note: 创建的歌单 and 收藏的歌单 both use `_on_playlist_clicked` (opens detail view).

- [ ] **Step 4: Add `_load_favorites` and `_on_fav_ready` methods (after `_load_recommendations`)**

```python
def _load_favorites(self):
    """Load user's favorites (songs, created playlists, fav playlists, fav albums)."""
    if self._fav_loaded:
        return

    euin = ""
    if self._qqmusic_service and self._qqmusic_service._credential:
        euin = (
            self._qqmusic_service._credential.get("encrypt_uin")
            or self._qqmusic_service._credential.get("encryptUin")
            or ""
        )
    if not euin:
        return

    self._fav_loaded = True
    self._fav_songs_section.show_loading()
    self._created_playlists_section.show_loading()
    self._fav_playlists_section.show_loading()
    self._fav_albums_section.show_loading()

    for fav_type in ["fav_songs", "created_playlists", "fav_playlists", "fav_albums"]:
        worker = FavWorker(self._qqmusic_service, fav_type)
        worker.fav_ready.connect(self._on_fav_ready)
        self._fav_workers.append(worker)
        worker.start()

def _on_fav_ready(self, fav_type: str, data: list):
    """Handle favorites data ready."""
    if fav_type == "fav_songs":
        cards = []
        for track in data[:30]:
            cards.append({
                "id": track.get("mid", ""),
                "title": track.get("title", ""),
                "cover_url": track.get("cover_url", ""),
                "fav_type": "fav_song",
                "raw_data": track,
            })
        self._fav_songs_section.load_recommendations(cards)

    elif fav_type == "created_playlists":
        cards = []
        for pl in data[:30]:
            cards.append({
                "id": pl.get("id", ""),
                "title": pl.get("title", ""),
                "cover_url": pl.get("cover_url", ""),
                "fav_type": "created_playlist",
                "raw_data": pl,
            })
        self._created_playlists_section.load_recommendations(cards)

    elif fav_type == "fav_playlists":
        cards = []
        for pl in data[:30]:
            cards.append({
                "id": pl.get("id", ""),
                "title": pl.get("title", ""),
                "cover_url": pl.get("cover_url", ""),
                "fav_type": "fav_playlist",
                "raw_data": pl,
            })
        self._fav_playlists_section.load_recommendations(cards)

    elif fav_type == "fav_albums":
        cards = []
        for album in data[:30]:
            cards.append({
                "id": album.get("mid", ""),
                "title": album.get("title", ""),
                "cover_url": album.get("cover_url", ""),
                "fav_type": "fav_album",
                "raw_data": album,
            })
        self._fav_albums_section.load_recommendations(cards)
```

- [ ] **Step 5: Add click handlers for favorites sections**

```python
def _on_fav_songs_clicked(self, data: Dict[str, Any]):
    """Handle favorite songs section click - show all fav songs in table."""
    worker = FavWorker(self._qqmusic_service, "fav_songs", page=1, num=100)
    worker.fav_ready.connect(lambda ft, tracks: self._show_fav_songs_in_table(tracks))
    worker.start()

def _show_fav_songs_in_table(self, tracks: list):
    """Show favorite songs in the results table."""
    from domain.online_music import OnlineTrack, OnlineSinger, AlbumInfo

    self._current_tracks = []
    for t_data in tracks:
        singer = OnlineSinger(mid="", name=t_data.get("singer", ""))
        album = AlbumInfo(mid=t_data.get("album_mid", ""), name=t_data.get("album", ""))
        track = OnlineTrack(
            mid=t_data.get("mid", ""),
            title=t_data.get("title", ""),
            singer=[singer],
            album=album,
            duration=t_data.get("duration", 0),
        )
        self._current_tracks.append(track)

    self._populate_songs_table(self._results_table, self._current_tracks)
    self._results_info.setText(f"{t('fav_songs')} - {len(self._current_tracks)} {t('songs')}")
    self._tabs.show()
    self._is_top_list_view = False
    self._stack.setCurrentWidget(self._results_page)

def _on_fav_album_clicked(self, data: Dict[str, Any]):
    """Handle favorite album card click - open album detail."""
    album_mid = data.get("id", "")
    title = data.get("title", "")
    singer_name = ""
    raw = data.get("raw_data")
    if isinstance(raw, dict):
        singer_name = raw.get("singer_name", "")
    if album_mid:
        self._detail_view.load_album(album_mid, title, singer_name)
        self._stack.setCurrentWidget(self._detail_view)
```

Note: 创建的歌单 and 收藏的歌单 click both use `_on_playlist_clicked` which already exists.

- [ ] **Step 6: Call `_load_favorites` in the login flow**

In `_setup_ui`, modify the existing credential check (around line 458):

```python
if self._service._has_qqmusic_credential():
    self._load_recommendations()
    self._load_favorites()
```

In `_on_credentials_obtained`, add favorites reload:

```python
def _on_credentials_obtained(self, credential: dict):
    """Handle credentials obtained from login dialog."""
    logger.info("QQ Music credentials obtained, refreshing service...")
    self._refresh_qqmusic_service()
    self._update_login_status()
    # Reload favorites with new credentials
    self._fav_loaded = False
    self._load_favorites()
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add ui/views/online_music_view.py
git commit -m "feat: add 4 favorites sections to OnlineMusicView"
```

---

### Task 6: Verify end-to-end

**Files:** None (manual verification)

- [ ] **Step 1: Run app and verify**

Run: `uv run python main.py`
Verify:
1. With QQ Music logged in: 4 favorites sections appear above recommendations (收藏歌曲, 创建的歌单, 收藏的歌单, 收藏专辑)
2. 收藏歌曲: clicking shows all favorite songs in table
3. 创建的歌单: clicking playlist card opens detail view
4. 收藏的歌单: clicking playlist card opens detail view
5. 收藏专辑: clicking album card opens detail view
6. Without login: no favorites sections shown
7. Existing recommendations still work

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -x -q`
Expected: all pass

- [ ] **Step 3: Final commit if any fixes needed**

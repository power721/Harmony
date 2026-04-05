# DB Manager Compatibility Removal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining `db_manager` compatibility layer from playback and online UI code paths without changing favorite behavior.

**Architecture:** `PlaybackService` should depend only on explicit repositories and services. `OnlineMusicView` and `OnlineDetailView` should use `LibraryService` and `FavoritesService` through `Bootstrap`, not direct database access. Main-window wiring should reflect the narrowed constructor signatures.

**Tech Stack:** Python, PySide6, pytest, unittest.mock, application bootstrap services

---

### Task 1: Lock the public constructor and favorite-service boundaries with tests

**Files:**
- Modify: `tests/test_app/test_bootstrap.py`
- Modify: `tests/test_playback_service_cloud_next.py`
- Create: `tests/test_ui/test_online_views_architecture.py`
- Test: `tests/test_app/test_bootstrap.py`
- Test: `tests/test_playback_service_cloud_next.py`
- Test: `tests/test_ui/test_online_views_architecture.py`

- [ ] **Step 1: Write the failing tests**

```python
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import app.bootstrap as bootstrap_module
from services.playback.playback_service import PlaybackService
from ui.views.online_music_view import OnlineMusicView
from ui.views.online_detail_view import OnlineDetailView


def test_playback_service_constructor_does_not_accept_db_manager():
    params = inspect.signature(PlaybackService.__init__).parameters
    assert "db_manager" not in params


def test_online_views_do_not_accept_db_manager():
    assert "db_manager" not in inspect.signature(OnlineMusicView.__init__).parameters
    assert "db_manager" not in inspect.signature(OnlineDetailView.__init__).parameters


def test_online_music_view_add_selected_to_favorites_uses_favorites_service(monkeypatch):
    favorites_service = Mock()
    bootstrap = SimpleNamespace(
        library_service=Mock(),
        favorites_service=favorites_service,
    )
    monkeypatch.setattr(
        bootstrap_module.Bootstrap,
        "instance",
        classmethod(lambda cls: bootstrap),
    )

    view = OnlineMusicView.__new__(OnlineMusicView)
    view._db = None
    view._add_online_track_to_library = Mock(return_value=42)
    monkeypatch.setattr("ui.views.online_music_view.MessageDialog.information", Mock())

    track = SimpleNamespace(mid="qq-mid")

    OnlineMusicView._add_selected_to_favorites(view, [track])

    favorites_service.add_favorite.assert_called_once_with(track_id=42)


def test_online_detail_view_remove_favorite_uses_services(monkeypatch):
    favorites_service = Mock()
    library_service = Mock()
    library_service.get_track_by_cloud_file_id.return_value = SimpleNamespace(id=7)
    bootstrap = SimpleNamespace(
        library_service=library_service,
        favorites_service=favorites_service,
    )
    monkeypatch.setattr(
        bootstrap_module.Bootstrap,
        "instance",
        classmethod(lambda cls: bootstrap),
    )

    view = OnlineDetailView.__new__(OnlineDetailView)
    view._db = None
    track = SimpleNamespace(mid="qq-mid")

    OnlineDetailView._remove_track_from_favorites(view, track)

    favorites_service.remove_favorite.assert_called_once_with(track_id=7)
```

- [ ] **Step 1.5: Remove `db_manager` from the PlaybackService cloud-next fixture**

```python
    @pytest.fixture
    def mock_deps(self):
        return {
            "config_manager": mock_config,
            "cover_service": Mock(),
            "online_download_service": Mock(),
            "event_bus": Mock(),
            "track_repo": Mock(),
            "favorite_repo": Mock(),
            "queue_repo": Mock(),
            "cloud_repo": Mock(),
            "history_repo": Mock(),
            "album_repo": Mock(),
            "artist_repo": Mock(),
        }
```

- [ ] **Step 2: Run the tests to verify they fail for the current compatibility layer**

Run: `uv run pytest tests/test_app/test_bootstrap.py tests/test_ui/test_online_views_architecture.py -v`

Expected: FAIL because `PlaybackService`, `OnlineMusicView`, and `OnlineDetailView` still expose `db_manager`, and the online favorite actions still call `_db` methods.

- [ ] **Step 3: Update the bootstrap test to assert the narrowed PlaybackService call**

```python
def test_playback_service_wires_download_manager_dependencies(monkeypatch):
    fake_playback = object()
    fake_manager = MagicMock()
    playback_cls = MagicMock(return_value=fake_playback)

    monkeypatch.setattr(
        bootstrap_module,
        "PlaybackService",
        playback_cls,
    )

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._config = object()
    bootstrap._cover_service = object()
    bootstrap._online_download_service = object()
    bootstrap._event_bus = object()
    bootstrap._track_repo = object()
    bootstrap._favorite_repo = object()
    bootstrap._queue_repo = object()
    bootstrap._cloud_repo = object()
    bootstrap._history_repo = object()
    bootstrap._album_repo = object()
    bootstrap._artist_repo = object()

    assert bootstrap.playback_service is fake_playback

    kwargs = playback_cls.call_args.kwargs
    assert "db_manager" not in kwargs
    assert kwargs["track_repo"] is bootstrap._track_repo
```

- [ ] **Step 4: Run the focused test file again and confirm the bootstrap assertion still fails before implementation**

Run: `uv run pytest tests/test_app/test_bootstrap.py::test_playback_service_wires_download_manager_dependencies -v`

Expected: FAIL because `Bootstrap.playback_service` still passes `db_manager=self.db`.

### Task 2: Remove `db_manager` from PlaybackService and bootstrap wiring

**Files:**
- Modify: `services/playback/playback_service.py`
- Modify: `app/bootstrap.py`
- Test: `tests/test_app/test_bootstrap.py`
- Test: `tests/test_playback_service_cloud_next.py`

- [ ] **Step 1: Remove the deprecated constructor argument from PlaybackService**

```python
class PlaybackService(QObject):
    def __init__(
        self,
        config_manager: ConfigManager = None,
        cover_service: "CoverService" = None,
        online_download_service: "OnlineDownloadService" = None,
        event_bus: EventBus = None,
        track_repo: "SqliteTrackRepository" = None,
        favorite_repo: "SqliteFavoriteRepository" = None,
        queue_repo: "SqliteQueueRepository" = None,
        cloud_repo: "SqliteCloudRepository" = None,
        history_repo: "SqliteHistoryRepository" = None,
        album_repo: "SqliteAlbumRepository" = None,
        artist_repo: "SqliteArtistRepository" = None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config_manager
        self._cover_service = cover_service
        self._online_download_service = online_download_service
        self._track_repo = track_repo
```

- [ ] **Step 2: Remove the compatibility documentation and `_db` assignment**

```python
        Args:
            config_manager: Configuration manager for settings
            cover_service: Cover service for album art
            online_download_service: Service for downloading online tracks (QQ Music)
            event_bus: Event bus for event publishing (defaults to singleton)
            track_repo: Track repository
            favorite_repo: Favorite repository
            queue_repo: Queue repository
            cloud_repo: Cloud repository
            history_repo: History repository
            album_repo: Album repository
            artist_repo: Artist repository
            parent: Optional parent QObject
```

- [ ] **Step 3: Stop bootstrap from passing `db_manager=self.db`**

```python
        if self._playback_service is None:
            self._playback_service = PlaybackService(
                config_manager=self.config,
                cover_service=self.cover_service,
                online_download_service=self.online_download_service,
                event_bus=self.event_bus,
                track_repo=self.track_repo,
                favorite_repo=self.favorite_repo,
                queue_repo=self.queue_repo,
                cloud_repo=self.cloud_repo,
                history_repo=self.history_repo,
                album_repo=self.album_repo,
                artist_repo=self.artist_repo,
            )
```

- [ ] **Step 4: Run PlaybackService-focused tests**

Run: `uv run pytest tests/test_app/test_bootstrap.py tests/test_playback_service_cloud_next.py -v`

Expected: PASS

### Task 3: Remove `db_manager` from online views and route favorites through services

**Files:**
- Modify: `ui/views/online_music_view.py`
- Modify: `ui/views/online_detail_view.py`
- Modify: `ui/windows/main_window.py`
- Modify: `tests/test_playback_service_cloud_next.py`
- Test: `tests/test_ui/test_online_views_architecture.py`
- Test: `tests/test_ui/test_online_music_view_focus.py`
- Test: `tests/test_ui/test_online_detail_view_actions.py`

- [ ] **Step 1: Narrow both online view constructors**

```python
class OnlineMusicView(QWidget):
    def __init__(
        self,
        config_manager=None,
        qqmusic_service=None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config_manager
        self._qqmusic_service = qqmusic_service
```

```python
class OnlineDetailView(QWidget):
    def __init__(
        self,
        config_manager=None,
        qqmusic_service=None,
        parent=None,
    ):
        super().__init__(parent)
        self._config = config_manager
        self._service = OnlineMusicService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service,
        )
```

- [ ] **Step 2: Update nested and top-level construction sites**

```python
        self._detail_view = OnlineDetailView(
            config_manager=self._config,
            qqmusic_service=self._qqmusic_service,
            parent=self,
        )
```

```python
        self._online_music_view = OnlineMusicView(
            self._config,
            qqmusic_service,
        )
```

- [ ] **Step 3: Replace direct `_db` favorite mutations with `FavoritesService`**

```python
    def _add_selected_to_favorites(self, tracks: List[OnlineTrack]):
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        favorites_service = bootstrap.favorites_service

        for track in tracks:
            track_id = self._add_online_track_to_library(track)
            if track_id:
                favorites_service.add_favorite(track_id=track_id)
```

```python
    def _remove_track_from_favorites(self, track: OnlineTrack):
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        library_track = bootstrap.library_service.get_track_by_cloud_file_id(track.mid)
        if library_track:
            bootstrap.favorites_service.remove_favorite(track_id=library_track.id)
```

- [ ] **Step 4: Update the existing constructor smoke test to use the new signature**

```python
with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
    view = OnlineMusicView(config_manager=None, qqmusic_service=None)
```

- [ ] **Step 5: Run the online-view test set**

Run: `uv run pytest tests/test_ui/test_online_views_architecture.py tests/test_ui/test_online_music_view_focus.py tests/test_ui/test_online_detail_view_actions.py -v`

Expected: PASS

### Task 4: Final verification and commit

**Files:**
- Modify: `app/bootstrap.py`
- Modify: `services/playback/playback_service.py`
- Modify: `ui/views/online_music_view.py`
- Modify: `ui/views/online_detail_view.py`
- Modify: `ui/windows/main_window.py`
- Modify: `tests/test_app/test_bootstrap.py`
- Modify: `tests/test_playback_service_cloud_next.py`
- Modify: `tests/test_ui/test_online_music_view_focus.py`
- Create: `tests/test_ui/test_online_views_architecture.py`

- [ ] **Step 1: Run the full verification command for this track**

Run: `uv run pytest tests/test_app/test_bootstrap.py tests/test_playback_service_cloud_next.py tests/test_ui/test_online_views_architecture.py tests/test_ui/test_online_music_view_focus.py tests/test_ui/test_online_detail_view_actions.py -v`

Expected: PASS

- [ ] **Step 2: Run a focused Ruff check on the touched files**

Run: `uv run ruff check app/bootstrap.py services/playback/playback_service.py ui/views/online_music_view.py ui/views/online_detail_view.py ui/windows/main_window.py tests/test_app/test_bootstrap.py tests/test_playback_service_cloud_next.py tests/test_ui/test_online_music_view_focus.py tests/test_ui/test_online_views_architecture.py`

Expected: PASS

- [ ] **Step 3: Commit only the compatibility-removal changes**

```bash
git add app/bootstrap.py services/playback/playback_service.py ui/views/online_music_view.py ui/views/online_detail_view.py ui/windows/main_window.py tests/test_app/test_bootstrap.py tests/test_playback_service_cloud_next.py tests/test_ui/test_online_music_view_focus.py tests/test_ui/test_online_views_architecture.py tests/test_ui/test_online_detail_view_actions.py
git commit -m "移除剩余db兼容层"
```

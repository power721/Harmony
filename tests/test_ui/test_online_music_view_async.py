"""Async request coordination tests for OnlineMusicView."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from domain.online_music import OnlineTrack, SearchResult, SearchType
from plugins.builtin.qqmusic.lib import i18n as plugin_i18n
from plugins.builtin.qqmusic.lib.online_music_view import DownloadWorker, OnlineMusicView
import plugins.builtin.qqmusic.lib.online_music_view as online_music_view
from tests.test_plugins.qqmusic_test_context import bind_test_context


def _make_view_for_search_callbacks():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._search_request_id = 0
    view._current_search_type = SearchType.SONG
    view._current_page = 1
    view._current_result = None
    view._current_tracks = []
    view._stack = Mock()
    view._results_page = object()
    view._results_stack = Mock()
    view._songs_page = object()
    view._singers_page = object()
    view._albums_page = object()
    view._playlists_page = object()
    view._results_info = Mock()
    view._page_label = Mock()
    view._prev_btn = Mock()
    view._next_btn = Mock()
    view._display_tracks = Mock()
    view._display_artists = Mock()
    view._display_albums = Mock()
    view._display_playlists = Mock()
    return view


def _make_view_for_completion_callbacks():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._completion_request_id = 0
    view._completer = Mock()
    view._search_input = Mock()
    view._search_input.text.return_value = "current"
    view._search_input.hasFocus.return_value = True
    return view


def _make_view_for_hotkey_callbacks():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._hotkey_request_id = 0
    view._hotkeys = []
    view._hotkey_popup = None
    view._config = None
    view._search_input = Mock()
    view._search_input.text.return_value = ""
    view._search_input.hasFocus.return_value = False
    return view


def test_stale_search_completion_is_ignored():
    """Older search results should not overwrite the UI after a newer request starts."""
    view = _make_view_for_search_callbacks()
    view._search_request_id = 2
    stale_result = SearchResult(
        keyword="old",
        search_type=SearchType.SONG,
        tracks=[OnlineTrack(mid="old", title="Old Song")],
        total=1,
    )

    OnlineMusicView._on_search_completed(view, stale_result, 1)

    assert view._current_result is None
    assert view._current_tracks == []
    view._display_tracks.assert_not_called()
    view._stack.setCurrentWidget.assert_not_called()


def test_current_search_completion_updates_ui():
    """Current search results should still update the UI normally."""
    view = _make_view_for_search_callbacks()
    view._search_request_id = 3
    result = SearchResult(
        keyword="new",
        search_type=SearchType.SONG,
        tracks=[OnlineTrack(mid="new", title="New Song")],
        total=1,
    )

    OnlineMusicView._on_search_completed(view, result, 3)

    assert view._current_result is result
    assert view._current_tracks == result.tracks
    view._display_tracks.assert_called_once_with(result.tracks)
    view._stack.setCurrentWidget.assert_called_once_with(view._results_page)


def test_stale_completion_results_are_ignored():
    """Older completion suggestions should not overwrite the current query."""
    view = _make_view_for_completion_callbacks()
    view._completion_request_id = 4

    OnlineMusicView._on_completion_ready(view, [{"hint": "old"}], 3)

    view._completer.setModel.assert_not_called()
    view._completer.complete.assert_not_called()


def test_current_completion_results_update_completer():
    """Current completion suggestions should still update the completer."""
    view = _make_view_for_completion_callbacks()
    view._completion_request_id = 5

    OnlineMusicView._on_completion_ready(view, [{"hint": "current song"}], 5)

    view._completer.setModel.assert_called_once()
    view._completer.setCompletionPrefix.assert_called_once_with("current")
    view._completer.complete.assert_called_once()


def test_stale_hotkey_results_are_ignored():
    """Older hotkey results should not replace newer state."""
    view = _make_view_for_hotkey_callbacks()
    view._hotkey_request_id = 7

    OnlineMusicView._on_hotkey_ready(view, [{"k": "old"}], 6)

    assert view._hotkeys == []


def test_current_hotkey_results_update_state():
    """Current hotkey results should still refresh cached hotkeys."""
    view = _make_view_for_hotkey_callbacks()
    view._hotkey_request_id = 8
    hotkeys = [{"k": "new"}]

    OnlineMusicView._on_hotkey_ready(view, hotkeys, 8)

    assert view._hotkeys == hotkeys


def test_update_login_status_prefers_plugin_namespaced_nick():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = Mock()
    view._service._has_qqmusic_credential.return_value = True
    view._refresh_qqmusic_service = Mock()
    view._config = Mock()
    view._config.get_plugin_setting.return_value = "Plugin Nick"
    view._login_status_label = Mock()
    view._login_btn = Mock()
    view._recommend_section = Mock()
    view._load_recommendations = Mock()

    OnlineMusicView._update_login_status(view)

    view._config.get_plugin_setting.assert_called_once_with("qqmusic", "nick", "")
    view._login_status_label.setText.assert_called_once()


def test_update_login_status_renders_nick_as_profile_link():
    plugin_i18n.set_language("en")
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = Mock()
    view._service._has_qqmusic_credential.return_value = True
    view._refresh_qqmusic_service = Mock()
    view._config = Mock()
    view._config.get_plugin_setting.return_value = "A&B<Nick>"
    view._login_status_label = Mock()
    view._login_btn = Mock()
    view._recommend_section = Mock()
    view._load_recommendations = Mock()

    OnlineMusicView._update_login_status(view)

    view._login_status_label.setText.assert_called_once_with(
        'Logged in as <a href="https://y.qq.com/n/ryqq_v2/profile/">A&amp;B&lt;Nick&gt;</a>'
    )


def test_refresh_login_status_renders_nick_as_profile_link():
    plugin_i18n.set_language("en")
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = Mock()
    view._service._has_qqmusic_credential.return_value = True
    view._config = Mock()
    view._config.get_plugin_setting.return_value = "Tester"
    view._login_status_label = Mock()
    view._login_btn = Mock()

    OnlineMusicView._refresh_login_status(view)

    view._login_status_label.setText.assert_called_once_with(
        'Logged in as <a href="https://y.qq.com/n/ryqq_v2/profile/">Tester</a>'
    )


def test_format_login_status_text_uses_theme_text_color_for_profile_link(monkeypatch):
    plugin_i18n.set_language("en")
    view = OnlineMusicView.__new__(OnlineMusicView)
    monkeypatch.setattr(
        online_music_view,
        "current_theme",
        lambda: SimpleNamespace(text="#abcdef"),
    )

    result = OnlineMusicView._format_login_status_text(view, "Tester")

    assert result == (
        'Logged in as '
        '<a href="https://y.qq.com/n/ryqq_v2/profile/" '
        'style="color: #abcdef; text-decoration: none;">Tester</a>'
    )


def test_refresh_theme_refreshes_login_status_markup(monkeypatch):
    view = OnlineMusicView.__new__(OnlineMusicView)
    view.setStyleSheet = Mock()
    view._online_music_title = Mock()
    view._login_status_label = Mock()
    view._search_input = Mock()
    search_style = Mock()
    view._search_input.style.return_value = search_style
    view._tabs = Mock()
    view._rankings_title = Mock()
    view._top_list_title = Mock()
    view._fav_back_btn = Mock()
    view._results_info = Mock()
    view._top_songs_table = Mock()
    view._results_table = Mock()
    view._page_label = Mock()
    view._completer = None
    view._hotkey_popup = None
    view._refresh_login_status = Mock()
    monkeypatch.setattr(online_music_view, "get_qss", lambda style: style)

    OnlineMusicView.refresh_theme(view)

    view._refresh_login_status.assert_called_once_with()


def test_on_login_clicked_clears_plugin_namespaced_credential():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = Mock()
    view._service._has_qqmusic_credential.return_value = True
    view._config = Mock()
    view._update_login_status = Mock()

    with patch("plugins.builtin.qqmusic.lib.online_music_view.MessageDialog.information"):
        OnlineMusicView._on_login_clicked(view)

    view._config.set_plugin_setting.assert_any_call("qqmusic", "credential", None)
    view._config.set_plugin_setting.assert_any_call("qqmusic", "nick", "")


def test_show_login_dialog_uses_plugin_local_dialog(monkeypatch):
    class _Signal:
        def __init__(self):
            self.connected = None

        def connect(self, callback):
            self.connected = callback

    view = OnlineMusicView.__new__(OnlineMusicView)
    view._on_credentials_obtained = Mock()
    dialog = Mock()
    dialog.credentials_obtained = _Signal()
    dialog_ctor = Mock(return_value=dialog)
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_music_view.create_qqmusic_login_dialog",
        dialog_ctor,
    )

    OnlineMusicView._show_login_dialog(view)

    dialog_ctor.assert_called_once_with(None, view)
    assert dialog.credentials_obtained.connected == view._on_credentials_obtained
    dialog.exec.assert_called_once_with()


def test_open_qqmusic_profile_link_uses_fixed_profile_url(monkeypatch):
    opened_urls = []

    def _fake_open_url(url):
        opened_urls.append(url.toString())
        return True

    monkeypatch.setattr(online_music_view.QDesktopServices, "openUrl", _fake_open_url)
    view = OnlineMusicView.__new__(OnlineMusicView)

    OnlineMusicView._open_qqmusic_profile_link(view, "https://ignored.example/")

    assert opened_urls == ["https://y.qq.com/n/ryqq_v2/profile/"]


def test_refresh_qqmusic_service_prefers_plugin_secret(monkeypatch):
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._config = Mock()
    view._config.get_plugin_secret.return_value = '{"musicid":"1","musickey":"secret"}'
    view._service = Mock()
    view._download_service = Mock()
    view._detail_view = None

    class _FakeQQMusicService:
        def __init__(self, credential):
            self.credential = credential

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_music_view.create_qqmusic_service",
        lambda credential: _FakeQQMusicService(credential),
    )

    OnlineMusicView._refresh_qqmusic_service(view)

    view._config.get_plugin_secret.assert_called_once_with("qqmusic", "credential", "")
    assert view._qqmusic_service.credential["musicid"] == "1"


def test_on_artist_clicked_accepts_dict_payload():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._stack = Mock()
    view._results_page = object()
    view._results_stack = Mock()
    view._singers_page = object()
    view._detail_view = Mock()
    view._navigation_stack = []

    OnlineMusicView._on_artist_clicked(
        view,
        {"mid": "artist-mid", "name": "Artist A"},
    )

    view._detail_view.load_artist.assert_called_once_with("artist-mid", "Artist A")


def test_display_playlists_uses_total_for_load_more_when_page_size_mismatch():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._grid_total = 302
    view._grid_page = 1
    view._grid_page_size = 30
    view._playlists_page = Mock()

    playlists = [{"id": "p1"} for _ in range(20)]  # API may return 20 despite num=30

    OnlineMusicView._display_playlists(view, playlists, is_append=False)

    view._playlists_page.set_has_more.assert_called_once_with(True)


def test_online_music_view_syncs_plugin_language_from_context_events(qtbot):
    plugin_i18n.set_language("en")
    theme_manager = Mock()
    theme = Mock()
    theme.background = "#101010"
    theme.background_alt = "#1a1a1a"
    theme.background_hover = "#202020"
    theme.text = "#ffffff"
    theme.text_secondary = "#b3b3b3"
    theme.highlight = "#1db954"
    theme.highlight_hover = "#1ed760"
    theme.border = "#404040"
    theme_manager.current_theme = theme
    theme_manager.get_qss.side_effect = lambda qss: qss
    theme_manager.register_widget = Mock()
    config = Mock()
    config.get_plugin_secret.return_value = ""
    config.get.side_effect = lambda key, default=None: {
        "view/ranking_view_mode": "table",
    }.get(key, default)
    config.get_search_history.return_value = []
    config.get_online_music_download_dir.return_value = "data/online_cache"

    class _Signal:
        def __init__(self):
            self._callbacks = []

        def connect(self, cb):
            self._callbacks.append(cb)

        def emit(self, value):
            for cb in list(self._callbacks):
                cb(value)

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        context = bind_test_context(theme_manager=theme_manager, language="zh")
        context.events.language_changed = _Signal()
        view = OnlineMusicView(config_manager=config, qqmusic_service=None, plugin_context=context)
        qtbot.addWidget(view)

        assert plugin_i18n.get_language() == "zh"

        context.events.language_changed.emit("en")

        assert plugin_i18n.get_language() == "en"


class _FakeSignal:
    def __init__(self):
        self.connected = None

    def connect(self, cb):
        self.connected = cb


class _FakeWorker:
    def __init__(self, running=True):
        self._running = running
        self.request_interruption_called = False
        self.quit_called = False
        self.wait_called = False
        self.started = False
        self.top_list_loaded = _FakeSignal()
        self.top_songs_loaded = _FakeSignal()
        self.finished = _FakeSignal()
        self.delete_later_called = False

    def isRunning(self):
        return self._running

    def requestInterruption(self):
        self.request_interruption_called = True
        self._running = False

    def quit(self):
        self.quit_called = True

    def wait(self, _timeout):
        self.wait_called = True
        return True

    def start(self):
        self.started = True
        self._running = True

    def deleteLater(self):
        self.delete_later_called = True


class _FakeAsyncWorker(_FakeWorker):
    def __init__(self, running=True):
        super().__init__(running=running)
        self.search_completed = _FakeSignal()
        self.search_failed = _FakeSignal()
        self.completion_ready = _FakeSignal()
        self.hotkey_ready = _FakeSignal()


def test_load_top_lists_stops_existing_worker_cooperatively():
    """Top-list reload should stop old worker via interruption/quit/wait before starting new one."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._service = object()
    old_worker = _FakeWorker(running=True)
    new_worker = _FakeWorker(running=False)
    view._top_list_worker = old_worker
    view._on_top_lists_loaded = Mock()

    with patch.object(online_music_view, "isValid", return_value=True), patch.object(
        online_music_view, "TopListWorker", return_value=new_worker
    ):
        OnlineMusicView._load_top_lists(view)

    assert old_worker.request_interruption_called is True
    assert old_worker.quit_called is True
    assert old_worker.wait_called is True
    assert view._top_list_worker is new_worker
    assert new_worker.top_list_loaded.connected == view._on_top_lists_loaded
    assert new_worker.started is True


def test_load_hotkeys_stops_existing_worker_cooperatively():
    """Hotkey reload should stop the old worker before replacing it."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._qqmusic_service = object()
    view._hotkey_request_id = 0
    old_worker = _FakeAsyncWorker(running=True)
    new_worker = _FakeAsyncWorker(running=False)
    view._hotkey_worker = old_worker
    view._on_hotkey_ready = Mock()

    with patch.object(online_music_view, "isValid", return_value=True), patch.object(
        online_music_view, "HotkeyWorker", return_value=new_worker
    ):
        OnlineMusicView._load_hotkeys(view)

    assert old_worker.request_interruption_called is True
    assert old_worker.quit_called is True
    assert old_worker.wait_called is True
    assert view._hotkey_worker is new_worker
    assert new_worker.hotkey_ready.connected is not None
    assert new_worker.started is True


def test_trigger_completion_stops_existing_worker_cooperatively():
    """Completion requests should stop the previous worker before launching a new one."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._qqmusic_service = object()
    view._completion_request_id = 0
    view._search_input = Mock()
    view._search_input.text.return_value = "hello"
    old_worker = _FakeAsyncWorker(running=True)
    new_worker = _FakeAsyncWorker(running=False)
    view._completion_worker = old_worker
    view._on_completion_ready = Mock()

    with patch.object(online_music_view, "isValid", return_value=True), patch.object(
        online_music_view, "CompletionWorker", return_value=new_worker
    ):
        OnlineMusicView._trigger_completion(view)

    assert old_worker.request_interruption_called is True
    assert old_worker.quit_called is True
    assert old_worker.wait_called is True
    assert view._completion_worker is new_worker
    assert new_worker.completion_ready.connected is not None
    assert new_worker.started is True


def test_do_search_stops_existing_worker_cooperatively():
    """New searches should stop the previous search worker before replacing it."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._search_request_id = 0
    view._service = object()
    view._current_keyword = "hello"
    view._current_search_type = SearchType.SONG
    view._current_page = 1
    old_worker = _FakeAsyncWorker(running=True)
    new_worker = _FakeAsyncWorker(running=False)
    view._search_worker = old_worker
    view._on_search_completed = Mock()
    view._on_search_failed = Mock()

    with patch.object(online_music_view, "isValid", return_value=True), patch.object(
        online_music_view, "SearchWorker", return_value=new_worker
    ):
        OnlineMusicView._do_search(view)

    assert old_worker.request_interruption_called is True
    assert old_worker.quit_called is True
    assert old_worker.wait_called is True
    assert view._search_worker is new_worker
    assert new_worker.search_completed.connected is not None
    assert new_worker.search_failed.connected is not None
    assert new_worker.started is True


def test_show_login_dialog_passes_plugin_context_and_refresh_callback(monkeypatch):
    class _Signal:
        def __init__(self):
            self.connected = None

        def connect(self, callback):
            self.connected = callback

    dialog = Mock()
    dialog.credentials_obtained = _Signal()
    create_dialog = Mock(return_value=dialog)
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_music_view.create_qqmusic_login_dialog",
        create_dialog,
    )

    view = OnlineMusicView.__new__(OnlineMusicView)
    view._plugin_context = "plugin-context"
    view._on_credentials_obtained = Mock()

    OnlineMusicView._show_login_dialog(view)

    create_dialog.assert_called_once()
    args, kwargs = create_dialog.call_args
    assert args[0] == "plugin-context"
    assert args[1] is view
    assert kwargs == {}
    assert dialog.credentials_obtained.connected == view._on_credentials_obtained
    dialog.exec.assert_called_once_with()


def test_on_credentials_obtained_fetches_missing_nick_from_service():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._plugin_context = Mock()
    view._config = Mock()
    view._config.get_plugin_setting.return_value = ""
    view._update_login_status = Mock()
    view._load_favorites = Mock()
    view._fav_loaded = True

    fresh_service = Mock()
    fresh_service.client.verify_login.return_value = {"valid": True, "nick": "Tester", "uin": 1}
    view._refresh_qqmusic_service = Mock(return_value=fresh_service)

    OnlineMusicView._on_credentials_obtained(view, {"musicid": "1", "musickey": "secret"})

    view._config.set_plugin_setting.assert_any_call("qqmusic", "nick", "Tester")
    assert view._fav_loaded is False
    view._refresh_qqmusic_service.assert_called_once_with({"musicid": "1", "musickey": "secret"})
    view._update_login_status.assert_called_once_with()
    view._load_favorites.assert_called_once_with()


def test_on_credentials_obtained_refreshes_service_from_emitted_credential(monkeypatch):
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._plugin_context = Mock()
    view._config = Mock()
    view._config.get_plugin_setting.return_value = "Existing Nick"
    view._config.get_plugin_secret.return_value = ""
    view._service = Mock()
    view._download_service = Mock()
    view._detail_view = None
    view._update_login_status = Mock()
    view._load_favorites = Mock()
    view._fav_loaded = True

    class _FakeQQMusicService:
        def __init__(self, credential):
            self.credential = credential
            self.client = Mock()

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_music_view.create_qqmusic_service",
        lambda credential: _FakeQQMusicService(credential),
    )

    OnlineMusicView._on_credentials_obtained(view, {"musicid": "9", "musickey": "new-secret"})

    assert view._qqmusic_service.credential == {"musicid": "9", "musickey": "new-secret"}
    view._update_login_status.assert_called_once_with()
    view._load_favorites.assert_called_once_with()


def test_build_track_metadata_uses_unified_fields():
    """Track metadata helper should populate standard online playback fields."""
    from domain.online_music import AlbumInfo, OnlineSinger

    view = OnlineMusicView.__new__(OnlineMusicView)
    track = OnlineTrack(
        mid="song-mid",
        title="Song",
        singer=[OnlineSinger(name="Singer")],
        album=AlbumInfo(mid="album-mid", name="Album"),
        duration=210,
    )

    metadata = OnlineMusicView._build_track_metadata(view, track)

    assert metadata == {
        "title": "Song",
        "artist": "Singer",
        "album": "Album",
        "duration": 210,
        "provider_id": "qqmusic",
        "album_mid": "album-mid",
        "cover_url": "https://y.qq.com/music/photo_new/T002R300x300M000album-mid.jpg",
    }


def test_build_tracks_payload_keeps_order_and_metadata():
    """Payload builder should preserve track order and include built metadata."""
    from domain.online_music import AlbumInfo, OnlineSinger

    view = OnlineMusicView.__new__(OnlineMusicView)
    tracks = [
        OnlineTrack(
            mid="m1",
            title="Song 1",
            singer=[OnlineSinger(name="Singer 1")],
            album=AlbumInfo(mid="a1", name="Album 1"),
            duration=101,
        ),
        OnlineTrack(
            mid="m2",
            title="Song 2",
            singer=[OnlineSinger(name="Singer 2")],
            album=AlbumInfo(mid="a2", name="Album 2"),
            duration=202,
        ),
    ]

    payload = OnlineMusicView._build_tracks_payload(view, tracks)

    assert [item[0] for item in payload] == ["m1", "m2"]
    assert payload[0][1]["title"] == "Song 1"
    assert payload[1][1]["title"] == "Song 2"


def test_download_worker_passes_provider_id_to_gateway():
    download_service = Mock()
    download_service.download.return_value = "/tmp/song.mp3"
    worker = DownloadWorker(
        download_service,
        "song-mid",
        "Song",
        provider_id="qqmusic",
    )
    captured = []
    worker.download_finished.connect(
        lambda song_mid, local_path: captured.append((song_mid, local_path))
    )

    worker.run()

    download_service.download.assert_called_once_with(
        "song-mid",
        "Song",
        provider_id="qqmusic",
    )
    assert captured == [("song-mid", "/tmp/song.mp3")]


def test_attach_download_worker_cleanup_clears_single_worker_reference():
    """Single download worker references should be released after finish."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    worker = _FakeWorker(running=False)
    view._download_worker = worker

    OnlineMusicView._attach_download_worker_cleanup(view, worker, single_attr="_download_worker")

    worker.finished.connected()

    assert view._download_worker is None
    assert worker.delete_later_called is True


def test_attach_download_worker_cleanup_removes_batch_worker_reference():
    """Batch download worker references should be removed after finish."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    worker = _FakeWorker(running=False)
    view._download_workers = [worker]

    OnlineMusicView._attach_download_worker_cleanup(view, worker, list_attr="_download_workers")

    worker.finished.connected()

    assert view._download_workers == []
    assert worker.delete_later_called is True

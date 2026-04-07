import threading
import time
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import QApplication, QListWidget, QWidget

from plugins.builtin.qqmusic.lib.client import QQMusicPluginClient
from plugins.builtin.qqmusic.lib import i18n as plugin_i18n
from plugins.builtin.qqmusic.lib.online_music_view import OnlineMusicView
from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog
from plugins.builtin.qqmusic.lib.provider import QQMusicOnlineProvider
from plugins.builtin.qqmusic.lib.root_view import HomeSectionsWorker
from plugins.builtin.qqmusic.lib.root_view import QQMusicRootView
from plugins.builtin.qqmusic.lib.qr_login import QQMusicQRLogin, QRLoginType
from plugins.builtin.qqmusic.plugin_main import QQMusicPlugin
from plugins.builtin.qqmusic.lib.settings_tab import QQMusicSettingsTab
from system.event_bus import EventBus
from system.i18n import get_language, set_language
from system.i18n import t
from system.theme import ThemeManager


@pytest.fixture(autouse=True)
def reset_theme_manager():
    ThemeManager._instance = None
    config = Mock()
    config.get.return_value = "dark"
    ThemeManager.instance(config)
    yield
    ThemeManager._instance = None


def test_qqmusic_plugin_registers_expected_capabilities():
    context = Mock()
    plugin = QQMusicPlugin()

    plugin.register(context)

    assert context.ui.register_sidebar_entry.call_count == 1
    sidebar_spec = context.ui.register_sidebar_entry.call_args.args[0]
    assert sidebar_spec.icon_path.endswith("sidebar_icon.svg")
    assert sidebar_spec.icon_name is None
    assert context.ui.register_settings_tab.call_count == 1
    assert context.services.register_lyrics_source.call_count == 1
    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
    assert context.services.register_online_music_provider.call_count == 1


def test_qqmusic_provider_create_page_uses_legacy_online_music_view(monkeypatch):
    context = Mock()
    context.settings.get.side_effect = lambda key, default=None: default
    created = {}

    def _capture_view(config_manager=None, qqmusic_service=None, plugin_context=None, parent=None):
        created["config_manager"] = config_manager
        created["qqmusic_service"] = qqmusic_service
        created["plugin_context"] = plugin_context
        created["parent"] = parent
        return Mock(spec=OnlineMusicView)

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.provider.OnlineMusicView",
        _capture_view,
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.provider.create_qqmusic_service",
        lambda credential: {"credential": credential},
    )

    provider = QQMusicOnlineProvider(context)
    page = provider.create_page(context, parent="host-parent")

    assert page is not None
    assert created["parent"] == "host-parent"
    assert created["plugin_context"] is context
    assert created["config_manager"].get_search_history() == []
    assert created["config_manager"].get_plugin_secret("qqmusic", "credential", "") == ""
    assert created["qqmusic_service"] is None


def test_qqmusic_provider_create_page_passes_adapter_with_download_dir(monkeypatch):
    settings = Mock()
    store = {
        "credential": "",
        "quality": "320",
        "search_history": [],
        "online_music_download_dir": "data/online_cache",
    }
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    context = Mock(settings=settings)
    context.logger = Mock()
    captured = {}

    def _capture_view(*, config_manager=None, qqmusic_service=None, plugin_context=None, parent=None):
        captured["config_manager"] = config_manager
        captured["qqmusic_service"] = qqmusic_service
        captured["plugin_context"] = plugin_context
        captured["parent"] = parent
        return Mock(spec=OnlineMusicView)

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.provider.OnlineMusicView",
        _capture_view,
    )

    provider = QQMusicOnlineProvider(context)
    page = provider.create_page(context, parent=None)

    assert page is not None
    assert captured["config_manager"].get_online_music_download_dir() == "data/online_cache"
    assert captured["plugin_context"] is context
    assert captured["qqmusic_service"] is None


def test_qqmusic_plugin_uses_private_translations_not_global(monkeypatch):
    import system.i18n as global_i18n

    original = global_i18n._translations.get("zh", {}).get("qqmusic_page_title")
    global_i18n._translations.setdefault("zh", {})["qqmusic_page_title"] = "全局错误文案"
    plugin_i18n.set_language("zh")

    try:
        assert plugin_i18n.t("qqmusic_page_title") == "QQ 音乐"
    finally:
        if original is None:
            global_i18n._translations["zh"].pop("qqmusic_page_title", None)
        else:
            global_i18n._translations["zh"]["qqmusic_page_title"] = original


def test_qqmusic_provider_config_adapter_tracks_search_history_and_plugin_settings():
    settings = Mock()
    store = {"search_history": ["A"], "credential": {"musicid": "1"}, "quality": "320"}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)

    adapter = QQMusicOnlineProvider._create_legacy_config_adapter(Mock(settings=settings))

    adapter.add_search_history("B")
    adapter.add_search_history("A")
    adapter.remove_search_history_item("B")

    assert adapter.get_search_history() == ["A"]
    assert adapter.get_plugin_secret("qqmusic", "credential", "") == {"musicid": "1"}
    assert adapter.get_plugin_setting("qqmusic", "quality", "") == "320"


def test_qqmusic_provider_config_adapter_exposes_download_dir():
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "online_music_download_dir": "data/online_cache",
    }.get(key, default)

    adapter = QQMusicOnlineProvider._create_legacy_config_adapter(Mock(settings=settings))

    assert adapter.get_online_music_download_dir() == "data/online_cache"


def test_qqmusic_settings_tab_reads_and_saves_quality(qtbot):
    settings = Mock()
    settings.get.return_value = "flac"
    context = Mock(settings=settings)

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    assert tab._quality_combo.currentData() == "flac"

    tab._quality_combo.setCurrentIndex(0)
    tab._save()

    settings.set.assert_called_once_with("quality", tab._quality_combo.currentData())
    assert hasattr(tab, "_account_group")
    assert hasattr(tab, "_quality_group")


def test_qqmusic_settings_tab_exposes_section_hint_labels(qtbot):
    settings = Mock()
    settings.get.return_value = "320"
    context = Mock(settings=settings)

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    assert hasattr(tab, "_account_hint_label")
    assert hasattr(tab, "_quality_hint_label")
    assert tab._account_hint_label.wordWrap() is True
    assert tab._quality_hint_label.wordWrap() is True


def test_qqmusic_settings_tab_opens_login_dialog(monkeypatch, qtbot):
    settings = Mock()
    settings.get.return_value = "320"
    context = Mock(settings=settings)

    dialog = Mock()
    dialog_ctor = Mock(return_value=dialog)
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.settings_tab.QQMusicLoginDialog",
        dialog_ctor,
    )

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    tab._open_login_dialog()

    dialog_ctor.assert_called_once_with(context, tab)
    dialog.exec.assert_called_once_with()




def test_plugin_local_qr_login_client_builds_session():
    client = QQMusicQRLogin()

    https_adapter = client._session.get_adapter("https://u.y.qq.com/cgi-bin/musicu.fcg")

    assert https_adapter._pool_connections == 20
    assert https_adapter._pool_maxsize == 20
    assert https_adapter._pool_block is True


def test_plugin_login_dialog_uses_local_qr_client(qtbot):
    dialog = QQMusicLoginDialog()
    qtbot.addWidget(dialog)

    assert isinstance(dialog._client, QQMusicQRLogin)


def test_plugin_login_dialog_auto_starts_qr_loading(monkeypatch, qtbot):
    start_calls = []

    def _capture_start(self, login_type=None):
        start_calls.append(login_type)

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        _capture_start,
    )

    dialog = QQMusicLoginDialog()
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: len(start_calls) == 1)

    assert start_calls[0] == QRLoginType.QQ


def test_plugin_login_dialog_can_switch_between_qq_and_wechat_qr(monkeypatch, qtbot):
    settings = Mock()
    context = Mock(settings=settings)
    start_calls = []

    def _capture_start(self, login_type=None):
        start_calls.append(login_type)

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicLoginDialog._start_login",
        _capture_start,
    )

    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)
    qtbot.waitUntil(lambda: len(start_calls) == 1)

    dialog._wx_login_btn.click()
    dialog._qq_login_btn.click()

    assert start_calls[1:] == [QRLoginType.WX, QRLoginType.QQ]


def test_plugin_login_dialog_persists_credentials_and_nick(qtbot):
    settings = Mock()
    context = Mock(settings=settings)
    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)

    dialog._handle_login_success({"musicid": "1", "musickey": "secret", "nick": "Tester"})

    settings.set.assert_any_call("credential", {"musicid": "1", "musickey": "secret", "nick": "Tester"})
    settings.set.assert_any_call("nick", "Tester")


def test_plugin_login_dialog_does_not_fallback_to_uid_for_nick(qtbot):
    settings = Mock()
    context = Mock(settings=settings)
    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)

    dialog._handle_login_success({"musicid": "1", "musickey": "secret"})

    settings.set.assert_any_call("credential", {"musicid": "1", "musickey": "secret"})
    settings.set.assert_any_call("nick", "")


def test_plugin_login_dialog_fetches_missing_nick_from_verify_login(monkeypatch, qtbot):
    settings = Mock()
    context = Mock(settings=settings)
    dialog = QQMusicLoginDialog(context)
    qtbot.addWidget(dialog)

    service = Mock()
    service.client.verify_login.return_value = {"valid": True, "nick": "Tester", "uin": 1}
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.login_dialog.QQMusicService",
        Mock(return_value=service),
    )

    dialog._handle_login_success({"musicid": "1", "musickey": "secret"})

    settings.set.assert_any_call("nick", "Tester")


def test_plugin_login_dialog_reject_stops_worker(qtbot):
    dialog = QQMusicLoginDialog()
    qtbot.addWidget(dialog)
    worker = Mock()
    dialog._worker = worker

    dialog.reject()

    worker.stop.assert_called_once_with()
    worker.wait.assert_called_once_with(1000)
    assert dialog._worker is None


def test_plugin_login_dialog_exposes_legacy_style_support_widgets(qtbot):
    dialog = QQMusicLoginDialog()
    qtbot.addWidget(dialog)

    assert hasattr(dialog, "_subtitle_label")
    assert hasattr(dialog, "_qr_frame")
    assert hasattr(dialog, "_cancel_btn")
    assert dialog._status_label.wordWrap() is True
    assert dialog.minimumWidth() >= 420


def test_plugin_client_normalizes_legacy_top_list_dict_tracks(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)

    service = Mock()
    service.get_top_list_songs.return_value = [
        {
            "mid": "song-1",
            "title": "Song 1",
            "singer": [{"name": "Singer 1"}],
            "album": {"name": "Album 1", "mid": "album-mid-1"},
            "interval": 210,
        }
    ]
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )

    client = QQMusicPluginClient(context)

    tracks = client.get_top_list_tracks(26)

    assert tracks == [
        {
            "mid": "song-1",
            "title": "Song 1",
            "artist": "Singer 1",
            "album": "Album 1",
            "album_mid": "album-mid-1",
            "duration": 210,
        }
    ]


def test_plugin_client_extracts_cover_from_nested_recommendation_payloads(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)

    service = Mock()
    service.get_home_feed.return_value = [
        {
            "Track": {
                "mid": "song-1",
                "title": "Song 1",
                "album": {"mid": "album-mid-1"},
            }
        }
    ]
    service.get_guess_recommend.return_value = []
    service.get_radar_recommend.return_value = []
    service.get_recommend_songlist.return_value = [
        {
            "Playlist": {
                "basic": {
                    "id": "pl-1",
                    "title": "Playlist 1",
                    "cover_url": "http://example.com/playlist-cover.jpg",
                }
            }
        }
    ]
    service.get_recommend_newsong.return_value = []
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )

    client = QQMusicPluginClient(context)

    recommendations = client.get_recommendations()

    assert recommendations[0]["cover_url"].endswith("T002R300x300M000album-mid-1.jpg")
    assert recommendations[1]["cover_url"] == "http://example.com/playlist-cover.jpg"


def test_plugin_client_exposes_detail_status_and_qq_actions(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)

    service = Mock()
    service.get_singer_info_with_follow_status.return_value = {
        "name": "Singer 1",
        "songs": [],
        "follow_status": True,
    }
    service.get_album_info_with_fav_status.return_value = {
        "name": "Album 1",
        "songs": [],
        "fav_status": True,
    }
    service.get_playlist_info_with_fav_status.return_value = {
        "name": "Playlist 1",
        "songs": [],
        "fav_status": True,
    }
    service.follow_singer.return_value = True
    service.unfollow_singer.return_value = True
    service.fav_album.return_value = True
    service.unfav_album.return_value = True
    service.fav_playlist.return_value = True
    service.unfav_playlist.return_value = True
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )

    client = QQMusicPluginClient(context)
    monkeypatch.setattr(client, "_can_use_legacy_network", lambda: True)

    assert client.get_artist_detail("artist-1")["follow_status"] is True
    assert client.get_album_detail("album-1")["is_faved"] is True
    assert client.get_playlist_detail("playlist-1")["is_faved"] is True
    assert client.follow_artist("artist-1") is True
    assert client.unfollow_artist("artist-1") is True
    assert client.fav_album("album-1") is True
    assert client.unfav_album("album-1") is True
    assert client.fav_playlist("playlist-1") is True
    assert client.unfav_playlist("playlist-1") is True


def test_plugin_client_prefers_public_api_for_top_lists_and_hotkeys(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)

    service = Mock()
    api = Mock()
    api.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    api.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    api.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    api.complete.return_value = [{"hint": "周杰伦 晴天"}]
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicPluginAPI",
        Mock(return_value=api),
    )

    client = QQMusicPluginClient(context)

    assert client.get_top_lists() == [{"id": 26, "title": "热歌榜"}]
    assert client.get_top_list_tracks(26) == [{"mid": "song-1", "title": "Song 1"}]
    assert client.get_hotkeys() == [{"title": "周杰伦", "query": "周杰伦"}]
    assert client.complete("周杰伦") == [{"hint": "周杰伦 晴天"}]

    service.get_top_lists.assert_not_called()
    service.get_top_list_songs.assert_not_called()
    service.get_hotkey.assert_not_called()
    service.complete.assert_not_called()


def test_plugin_client_skips_private_legacy_calls_when_network_unreachable(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)

    service = Mock()
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicService",
        Mock(return_value=service),
    )

    client = QQMusicPluginClient(context)
    monkeypatch.setattr(client, "_can_use_legacy_network", lambda: False)

    assert client.get_recommendations() == []
    assert client.get_favorites() == []

    service.get_home_feed.assert_not_called()
    service.get_my_fav_songs.assert_not_called()


def test_qqmusic_settings_tab_clears_plugin_credentials(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "nick": "Tester",
    }.get(key, default)
    context = Mock(settings=settings)

    tab = QQMusicSettingsTab(context)
    qtbot.addWidget(tab)

    tab._clear_credentials()

    settings.set.assert_any_call("credential", None)
    settings.set.assert_any_call("nick", "")


def test_root_view_search_populates_results(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    provider = Mock()
    provider.search_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song 1")
    view._run_search()

    assert view._results_list.count() == 1
    assert "Song 1" in view._results_list.item(0).text()
    provider.search_tracks.assert_called_once_with("Song 1")


def test_root_view_initializes_home_sections(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [
        {"id": 26, "title": "热歌榜"},
        {"id": 27, "title": "新歌榜"},
    ]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert view._home_stack.currentWidget() is view._home_page
    assert view._search_type_tabs.count() == 4
    assert view._search_type_tabs.isHidden() is True
    assert view._top_list_widget.count() == 2
    assert view._top_tracks_table.columnCount() == 5
    assert view._top_tracks_table.rowCount() == 1
    assert view._ranking_title_label.text() == "热歌榜"
    provider.get_top_lists.assert_called_once_with()
    provider.get_top_list_tracks.assert_called_once_with(26)


def test_root_view_supports_multi_type_search(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "artists": [
            {"mid": "artist-1", "name": "Singer 1", "song_count": 12},
        ]
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()

    assert view._home_stack.currentWidget() is view._results_page
    assert view._results_stack.currentWidget() is view._artists_page
    assert view._artists_list.count() == 1
    assert "Singer 1" in view._artists_list.item(0).text()
    provider.search.assert_called_once_with("Singer 1", "singer", page=1, page_size=30)


def test_root_view_switching_search_tab_requeries_current_keyword(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.side_effect = [
        {"tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}], "total": 1, "page": 1, "page_size": 30},
        {"albums": [{"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"}], "total": 1, "page": 1, "page_size": 30},
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()

    view._search_input.setText("Singer 1")
    view._run_search()
    view._search_type_tabs.setCurrentIndex(2)

    assert provider.search.call_args_list[0].args[:2] == ("Singer 1", "song")
    assert provider.search.call_args_list[1].args[:2] == ("Singer 1", "album")
    assert view._results_stack.currentWidget() is view._albums_page


def test_root_view_song_search_uses_table_and_pagination(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-x", "title": "Song X", "artist": "Singer X"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "tracks": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        ],
        "total": 61,
        "page": 1,
        "page_size": 30,
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song 1")
    view._run_search()

    results_table = getattr(view, "_results_table", None)
    page_label = getattr(view, "_page_label", None)
    next_btn = getattr(view, "_next_btn", None)

    assert results_table is not None
    assert page_label is not None
    assert next_btn is not None
    assert results_table.columnCount() == 5
    assert view._results_stack.currentWidget() is view._songs_page
    assert results_table.rowCount() == 1
    assert page_label.text() == "1"
    assert next_btn.isEnabled() is True
    assert "Song 1" in view._results_info_label.text()
    assert "61" in view._results_info_label.text()
    assert view._pagination_widget.isHidden() is False
    provider.search.assert_called_once_with("Song 1", "song", page=1, page_size=30)


def test_root_view_artist_search_uses_grid_and_load_more(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-x", "title": "Song X", "artist": "Singer X"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
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

    assert hasattr(view, "_on_load_more_artists")
    view._on_load_more_artists()

    assert view._results_stack.currentWidget() is view._artists_page
    assert view._pagination_widget.isHidden() is True
    assert provider.search.call_args_list[0].args[:2] == ("Singer", "singer")
    assert provider.search.call_args_list[1].kwargs == {"page": 2, "page_size": 30}


def test_root_view_loads_logged_in_sections(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {"title": "每日推荐", "subtitle": "猜你想听"},
    ]
    provider.get_favorites.return_value = [
        {"title": "我喜欢的歌曲", "count": 42},
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert "Tester" in view._status.text()
    assert view._recommend_list.count() == 1
    assert view._favorites_list.count() == 1
    assert view._recommend_section.isHidden() is False
    assert view._favorites_section.isHidden() is False
    assert view._recommend_group.isHidden() is True
    assert view._favorites_group.isHidden() is True


def test_home_sections_worker_parallelizes_home_requests():
    provider = Mock()
    release = threading.Event()
    started = {
        "top_lists": threading.Event(),
        "hotkeys": threading.Event(),
        "favorites": threading.Event(),
        "recommendations": threading.Event(),
    }

    def _slow_list(name, value):
        def _inner():
            started[name].set()
            release.wait(0.5)
            return value
        return _inner

    provider.get_top_lists.side_effect = _slow_list("top_lists", [{"id": 26, "title": "热歌榜"}])
    provider.get_hotkeys.side_effect = _slow_list("hotkeys", [{"title": "周杰伦"}])
    provider.get_favorites.side_effect = _slow_list("favorites", [{"title": "收藏"}])
    provider.get_recommendations.side_effect = _slow_list("recommendations", [{"title": "推荐"}])
    provider.get_top_list_tracks.return_value = []

    worker = HomeSectionsWorker(
        provider,
        load_private=True,
        logged_in=True,
        history=["林俊杰"],
    )

    runner = threading.Thread(target=worker.run)
    runner.start()

    assert started["top_lists"].wait(0.2) is True
    time.sleep(0.05)
    started_count = sum(1 for event in started.values() if event.is_set())
    release.set()
    runner.join(timeout=1)

    assert started_count == 4


def test_root_view_home_payload_prefills_initial_ranking_tracks(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    payload = {
        "top_lists": [{"id": 26, "title": "热歌榜"}],
        "top_tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210}],
        "top_tracks_id": "26",
        "hotkeys": [],
        "history": [],
        "favorites": [],
        "recommendations": [],
        "logged_in": False,
        "load_private": False,
    }

    view._on_home_sections_loaded(payload)

    assert view._top_tracks_table.rowCount() == 1
    provider.get_top_list_tracks.assert_not_called()


def test_root_view_home_payload_does_not_show_hotkey_popup_without_search_focus(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()
    view._hotkey_popup = view._hotkey_popup or None
    view._show_hotkey_popup()
    assert view._hotkey_popup is not None
    view._on_app_focus_changed(view._search_input, view._login_btn)

    view._on_home_sections_loaded(
        {
            "top_lists": [],
            "top_tracks": [],
            "top_tracks_id": "",
            "hotkeys": [{"title": "周杰伦", "query": "周杰伦"}],
            "history": [],
            "favorites": [],
            "recommendations": [],
            "logged_in": False,
            "load_private": False,
        }
    )

    assert view._hotkey_popup.isVisible() is False


def test_root_view_show_does_not_auto_open_hotkey_popup(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()

    qtbot.waitUntil(lambda: view._search_input.hasFocus(), timeout=1000)

    assert view._hotkey_popup is None or view._hotkey_popup.isVisible() is False


def test_root_view_internal_collection_lists_are_hidden(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()

    assert view._artists_list.isHidden() is True
    assert view._albums_list.isHidden() is True
    assert view._playlists_list.isHidden() is True


def test_root_view_ranking_table_uses_legacy_column_layout(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210}]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    header = view._top_tracks_table.horizontalHeader()
    assert header.stretchLastSection() is False
    assert header.sectionResizeMode(0) == header.ResizeMode.Fixed
    assert header.sectionResizeMode(4) == header.ResizeMode.Fixed
    assert view._top_tracks_table.columnWidth(0) == 50
    assert view._top_tracks_table.columnWidth(4) == 80


def test_root_view_public_home_payload_does_not_clear_private_sections(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._favorites_cache = [{"title": "我喜欢的歌曲", "subtitle": "1 首", "items": [{"mid": "song-1"}]}]
    view._recommendations_cache = [{"title": "猜你喜欢", "subtitle": "1 项", "items": [{"mid": "song-1"}]}]
    view._apply_logged_in_sections_from_cache()

    view._on_home_sections_loaded(
        {
            "top_lists": [],
            "top_tracks": [],
            "top_tracks_id": "",
            "hotkeys": [],
            "history": [],
            "favorites": [],
            "recommendations": [],
            "logged_in": True,
            "load_private": False,
        }
    )

    assert view._favorites_section.isHidden() is False
    assert view._recommend_section.isHidden() is False
    assert view._favorites_list.count() == 1


def test_root_view_ranking_context_menu_uses_translated_labels(monkeypatch, qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    labels = []

    class _FakeSignal:
        def connect(self, *_args, **_kwargs):
            return None

    class _FakeAction:
        def __init__(self):
            self.triggered = _FakeSignal()

    class _FakeMenu:
        def __init__(self, *_args, **_kwargs):
            pass

        def setStyleSheet(self, *_args, **_kwargs):
            return None

        def addAction(self, text):
            labels.append(text)
            return _FakeAction()

        def addSeparator(self):
            return None

        def exec(self, *_args, **_kwargs):
            return None

    monkeypatch.setattr("plugins.builtin.qqmusic.lib.root_view.QMenu", _FakeMenu)
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.t",
        lambda key, default=None: f"tr:{key}",
    )

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view._top_tracks_table.selectRow(0)
    monkeypatch.setattr(view, "sender", lambda: view._top_tracks_table)

    view._show_track_context_menu(view._top_tracks_table.visualItemRect(view._top_tracks_table.item(0, 0)).center())

    assert labels == [
        "tr:play",
        "tr:insert_to_queue",
        "tr:add_to_queue",
        "tr:add_to_favorites",
        "tr:add_to_playlist",
        "tr:download",
    ]


def test_root_view_detail_toggle_texts_use_translation_keys(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.t",
        lambda key, default=None: f"tr:{key}",
    )

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._show_detail(
        {"title": "Singer 1", "songs": [], "follow_status": True},
        detail_type="artist",
        source_id="artist-1",
    )
    assert view._detail_follow_btn.text() == "tr:qqmusic_followed"

    view._show_detail(
        {"title": "Album 1", "songs": [], "is_faved": True},
        detail_type="album",
        source_id="album-1",
    )
    assert view._detail_fav_btn.text() == "tr:qqmusic_remove_from_favorites"


def test_root_view_syncs_language_from_context_and_listens_for_changes(qtbot):
    plugin_i18n.set_language("en")
    store = {"nick": "", "quality": "320"}
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    context = Mock(settings=settings)
    context.services.media = Mock()
    context.events = EventBus.instance()
    context.language = "zh"
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert plugin_i18n.get_language() == "zh"

    context.events.language_changed.emit("en")

    assert plugin_i18n.get_language() == "en"


def test_root_view_show_event_uses_async_home_loader_for_embedded_page(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    started = {}

    class _FakeWorker:
        def __init__(self, *_args, **_kwargs):
            self.home_loaded = Mock(connect=Mock())
            self.failed = Mock(connect=Mock())
            self.finished = Mock(connect=Mock())

        def start(self):
            started["started"] = True

        def isRunning(self):
            return False

        def deleteLater(self):
            started["deleted"] = True

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.HomeSectionsWorker",
        _FakeWorker,
    )

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    assert provider.get_top_lists.call_count == 0

    view.showEvent(QShowEvent())
    qtbot.waitUntil(lambda: started.get("started") is True, timeout=1000)

    assert provider.get_top_lists.call_count == 0


def test_root_view_embedded_init_does_not_block_on_logged_in_sections(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    provider.get_recommendations.return_value = [{"title": "推荐"}]
    provider.get_favorites.return_value = [{"title": "收藏"}]
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    provider.get_favorites.assert_not_called()
    provider.get_recommendations.assert_not_called()
    assert view._favorites_section.isHidden() is True
    assert view._recommend_section.isHidden() is True


def test_root_view_embedded_init_lazy_builds_grid_pages(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    grid_ctor = Mock()
    tracks_list_ctor = Mock()
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.OnlineGridView",
        grid_ctor,
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.OnlineTracksListView",
        tracks_list_ctor,
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.QTimer.singleShot",
        lambda *_args, **_kwargs: None,
    )

    parent = QWidget()
    QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    grid_ctor.assert_not_called()
    tracks_list_ctor.assert_not_called()


def test_root_view_embedded_init_lazy_builds_detail_ui(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    import plugins.builtin.qqmusic.lib.root_view as root_view_module
    original_single_shot = root_view_module.QTimer.singleShot
    root_view_module.QTimer.singleShot = lambda *_args, **_kwargs: None

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    assert view._detail_ui_built is False
    root_view_module.QTimer.singleShot = original_single_shot


def test_root_view_embedded_init_schedules_public_home_prefetch(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    scheduled = []

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)
    monkeypatch.setattr(
        view,
        "_schedule_home_sections_load",
        lambda **kwargs: scheduled.append(kwargs),
    )
    view._public_home_prefetch_scheduled = False
    view._schedule_public_home_prefetch()

    assert scheduled == [{"load_private": False, "force": True}]


def test_root_view_embedded_logged_in_init_schedules_private_home_prefetch(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    calls = []
    def _capture(delay, callback):
        calls.append(delay)
        return None

    monkeypatch.setattr("plugins.builtin.qqmusic.lib.root_view.QTimer.singleShot", _capture)

    parent = QWidget()
    QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    assert 600 in calls


def test_root_view_embedded_init_lazy_builds_results_ui(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    import plugins.builtin.qqmusic.lib.root_view as root_view_module
    original_single_shot = root_view_module.QTimer.singleShot
    root_view_module.QTimer.singleShot = lambda *_args, **_kwargs: None

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    assert view._results_ui_built is False
    root_view_module.QTimer.singleShot = original_single_shot


def test_root_view_embedded_search_builds_results_ui(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    view._search_input.setText("Song 1")
    view._run_search()

    assert view._results_ui_built is True
    assert view._results_table.rowCount() == 1


def test_root_view_show_event_loads_private_sections_after_public_prefetch(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    scheduled = []
    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)
    view._home_sections_loaded = True
    view._private_home_loaded = False

    monkeypatch.setattr(
        view,
        "_schedule_private_sections_load",
        lambda **kwargs: scheduled.append(kwargs),
    )

    view.showEvent(QShowEvent())

    assert scheduled == [{"force": False}]


def test_root_view_top_list_change_uses_async_track_loader(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    started = {}

    class _FakeWorker:
        def __init__(self, *_args, **_kwargs):
            self.tracks_loaded = Mock(connect=Mock())
            self.failed = Mock(connect=Mock())
            self.finished = Mock(connect=Mock())

        def start(self):
            started["started"] = True

        def isRunning(self):
            return False

        def deleteLater(self):
            started["deleted"] = True

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.TopListTracksWorker",
        _FakeWorker,
    )

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    provider.get_top_list_tracks.reset_mock()

    view._on_top_list_changed(0)

    assert started.get("started") is True
    provider.get_top_list_tracks.assert_not_called()


def test_root_view_top_list_async_load_shows_placeholder_rows(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    class _FakeWorker:
        def __init__(self, *_args, **_kwargs):
            self.tracks_loaded = Mock(connect=Mock())
            self.failed = Mock(connect=Mock())
            self.finished = Mock(connect=Mock())

        def start(self):
            return None

        def isRunning(self):
            return False

        def deleteLater(self):
            return None

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.TopListTracksWorker",
        _FakeWorker,
    )
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.QTimer.singleShot",
        lambda *_args, **_kwargs: None,
    )

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    view._load_top_list_tracks_async(26)

    assert view._top_tracks_table.rowCount() == 10


def test_root_view_async_home_load_shows_placeholder_cards_for_private_sections(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    provider.get_recommendations.return_value = [{"title": "推荐"}]
    provider.get_favorites.return_value = [{"title": "收藏"}]
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    class _FakeWorker:
        def __init__(self, *_args, **_kwargs):
            self.home_loaded = Mock(connect=Mock())
            self.failed = Mock(connect=Mock())
            self.finished = Mock(connect=Mock())

        def start(self):
            return None

        def isRunning(self):
            return False

        def deleteLater(self):
            return None

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.HomeSectionsWorker",
        _FakeWorker,
    )

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    view._start_home_sections_worker(load_private=True, force=True)

    assert view._favorites_section.isHidden() is False
    assert view._recommend_section.isHidden() is False
    assert len(view._favorites_section._cards) == 5
    assert len(view._recommend_section._cards) == 5


def test_root_view_async_home_load_shows_top_list_placeholders(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [{"mid": "song-1", "title": "Song 1"}]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    class _FakeWorker:
        def __init__(self, *_args, **_kwargs):
            self.home_loaded = Mock(connect=Mock())
            self.failed = Mock(connect=Mock())
            self.finished = Mock(connect=Mock())

        def start(self):
            return None

        def isRunning(self):
            return False

        def deleteLater(self):
            return None

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.root_view.HomeSectionsWorker",
        _FakeWorker,
    )

    parent = QWidget()
    view = QQMusicRootView(context, provider, parent=parent)
    qtbot.addWidget(parent)

    view._start_home_sections_worker(load_private=False, force=True)

    assert view._top_list_widget.count() == 8
    assert view._top_tracks_table.rowCount() == 10


def test_root_view_loads_recommendation_cards(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {
            "id": "guess",
            "title": "猜你喜欢",
            "subtitle": "2 项",
            "cover_url": "",
            "items": [{"mid": "song-1", "title": "Song 1"}],
            "entry_type": "songs",
        },
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    recommend_section = getattr(view, "_recommend_section", None)
    assert recommend_section is not None
    assert recommend_section.isHidden() is False
    assert len(recommend_section._cards) == 1


def test_root_view_favorite_song_card_opens_detail_view(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-x", "title": "Song X", "artist": "Singer X"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "id": "fav_songs",
            "title": "我喜欢的歌曲",
            "subtitle": "1 首",
            "cover_url": "",
            "items": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "cover_url": "http://example/song-cover.jpg"}],
            "entry_type": "songs",
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view._search_input.setText("abc")
    view._run_search()
    assert view._search_type_tabs.isHidden() is False

    assert hasattr(view, "_open_favorite_card")
    view._open_favorite_card(provider.get_favorites.return_value[0])

    assert view._home_stack.currentWidget() is view._detail_page
    assert view._detail_title.text() == "我喜欢的歌曲"
    assert view._detail_tracks[0]["cover_url"] == "http://example/song-cover.jpg"
    assert hasattr(view, "_detail_tracks_view")
    assert view._detail_tracks_stack.currentWidget() is view._detail_tracks_view
    assert view._detail_cover_url == "http://example/song-cover.jpg"
    assert view._search_type_tabs.isHidden() is True


def test_root_view_recommendation_playlist_card_opens_playlist_results(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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

    assert hasattr(view, "_open_recommendation_card")
    view._open_recommendation_card(provider.get_recommendations.return_value[0])

    assert view._home_stack.currentWidget() is view._results_page
    assert view._results_stack.currentWidget() is view._playlists_page


def test_root_view_recommendation_playlist_card_handles_nested_playlist_payload(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
            "items": [
                {
                    "Playlist": {
                        "basic": {"id": "pl-1", "title": "Playlist 1", "cover_url": "http://example/cover.jpg"},
                        "content": {"song_count": 12},
                    }
                }
            ],
            "entry_type": "playlists",
        },
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_recommendation_card(provider.get_recommendations.return_value[0])

    assert view._results_stack.currentWidget() is view._playlists_page
    assert len(view._playlists_page._items) == 1


def test_root_view_recommendation_song_card_handles_nested_track_payload(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {
            "id": "radar",
            "title": "雷达歌单",
            "subtitle": "1 项",
            "cover_url": "",
            "items": [
                {
                    "Track": {
                        "mid": "song-1",
                        "title": "Song 1",
                        "singer": [{"name": "Singer 1"}],
                        "album": {"name": "Album 1", "mid": "album-mid-1"},
                    }
                }
            ],
            "entry_type": "songs",
        },
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_recommendation_card(provider.get_recommendations.return_value[0])

    assert view._home_stack.currentWidget() is view._detail_page
    assert view._detail_tracks_list.count() == 1
    assert "Singer 1" in view._detail_tracks_list.item(0).text()
    assert view._detail_cover_url.endswith("T002R300x300M000album-mid-1.jpg")


def test_root_view_song_actions_use_media_bridge(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "flac",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210}
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song 1")
    view._run_search()
    view._results_list.setCurrentRow(0)

    view._play_selected_song()
    view._add_selected_song_to_queue()
    view._insert_selected_song_to_queue()
    view._download_selected_song()

    assert media.play_online_track.call_count == 1
    assert media.add_online_track_to_queue.call_count == 1
    assert media.insert_online_track_to_queue.call_count == 1
    assert media.cache_remote_track.call_count == 1


def test_root_view_build_playback_request_normalizes_nested_song_fields(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "flac",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    request = view._build_playback_request(
        {
            "mid": "song-1",
            "title": "Song 1",
            "singer": [{"name": "Singer 1"}, {"name": "Singer 2"}],
            "album": {"name": "Album 1", "mid": "album-mid-1"},
            "interval": 210,
        }
    )

    assert request.metadata["artist"] == "Singer 1, Singer 2"
    assert request.metadata["album"] == "Album 1"
    assert request.metadata["duration"] == 210.0
    assert request.metadata["cover_url"].endswith("T002R300x300M000album-mid-1.jpg")


def test_root_view_top_track_activation_uses_media_bridge(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [
        {"id": 26, "title": "热歌榜"},
    ]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210}
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._play_top_track(0, 0)

    media.play_online_track.assert_called_once()
    media.add_online_track_to_queue.assert_not_called()


def test_root_view_top_track_activation_queues_remaining_top_tracks(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [
        {"id": 26, "title": "热歌榜"},
    ]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
        {"mid": "song-3", "title": "Song 3", "artist": "Singer 3", "album": "Album 3", "duration": 200},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._play_top_track(1, 0)

    media.play_online_track.assert_called_once()
    assert media.add_online_track_to_queue.call_count == 1


def test_root_view_ranking_list_activation_queues_remaining_top_tracks(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "ranking_view_mode": "list",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [
        {"id": 26, "title": "热歌榜"},
    ]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
        {"mid": "song-3", "title": "Song 3", "artist": "Singer 3", "album": "Album 3", "duration": 200},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._on_ranking_track_activated(view._ranking_tracks[1])

    media.play_online_track.assert_called_once()
    assert media.add_online_track_to_queue.call_count == 1


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
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert hasattr(view, "_toggle_ranking_view_mode")
    assert getattr(view, "_ranking_stacked_widget", None) is not None
    initial_tooltip = view._ranking_view_toggle_btn.toolTip()
    view._toggle_ranking_view_mode()

    assert state["ranking_view_mode"] == "list"
    assert view._ranking_stacked_widget.currentWidget() is view._ranking_list_view
    assert view._ranking_view_toggle_btn.toolTip() != initial_tooltip


def test_root_view_ranking_batch_queue_actions_use_media_bridge(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "ranking_view_mode": "table",
    }.get(key, default)
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

    assert hasattr(view, "_add_selected_tracks_to_queue")
    assert hasattr(view, "_insert_selected_tracks_to_queue")
    assert hasattr(view, "_download_selected_tracks")

    tracks = [view._top_track_item(0), view._top_track_item(1)]
    view._add_selected_tracks_to_queue(tracks)
    view._insert_selected_tracks_to_queue(tracks)
    view._download_selected_tracks(tracks)

    assert context.services.media.add_online_track_to_queue.call_count == 2
    assert context.services.media.insert_online_track_to_queue.call_count == 2
    assert context.services.media.cache_remote_track.call_count == 2


def test_root_view_ranking_favorite_toggle_adds_to_favorites(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "ranking_view_mode": "list",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    bootstrap = Mock()
    bootstrap.library_service.add_online_track.return_value = 301
    bootstrap.favorites_service = Mock()
    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", Mock(return_value=bootstrap))

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view._ranking_list_view.set_track_favorite = Mock()

    view._on_ranking_favorite_toggled(view._ranking_tracks[0], True)

    bootstrap.favorites_service.add_favorite.assert_called_once_with(track_id=301)
    view._ranking_list_view.set_track_favorite.assert_called_once_with("song-1", True)


def test_root_view_ranking_favorite_toggle_removes_existing_favorite(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "ranking_view_mode": "list",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = [{"id": 26, "title": "热歌榜"}]
    provider.get_top_list_tracks.return_value = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
    ]
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    bootstrap = Mock()
    bootstrap.library_service.get_track_by_cloud_file_id.return_value = Mock(id=401)
    bootstrap.favorites_service = Mock()
    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", Mock(return_value=bootstrap))

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view._ranking_list_view.set_track_favorite = Mock()

    view._on_ranking_favorite_toggled(view._ranking_tracks[0], False)

    bootstrap.favorites_service.remove_favorite.assert_called_once_with(track_id=401)
    view._ranking_list_view.set_track_favorite.assert_called_once_with("song-1", False)


def test_root_view_ranking_list_loads_initial_favorite_mids(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "ranking_view_mode": "list",
    }.get(key, default)
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

    bootstrap = Mock()
    bootstrap.favorites_service.get_all_favorite_track_ids.return_value = {11}
    bootstrap.library_service.get_tracks_by_ids.return_value = [Mock(cloud_file_id="song-2")]
    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", Mock(return_value=bootstrap))

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    favorite_mids = view._ranking_list_view._model._favorite_mids

    assert favorite_mids == {"song-2"}


def test_root_view_selected_tracks_from_ranking_list_supports_multi_select(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "ranking_view_mode": "list",
    }.get(key, default)
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

    selection_model = view._ranking_list_view._list_view.selectionModel()
    selection_model.select(
        view._ranking_list_view._model.index(0),
        selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
    )
    selection_model.select(
        view._ranking_list_view._model.index(1),
        selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
    )

    assert hasattr(view, "_selected_tracks_from_tracks_view")
    tracks = view._selected_tracks_from_tracks_view(view._ranking_list_view)

    assert [track["mid"] for track in tracks] == ["song-1", "song-2"]


def test_root_view_selected_tracks_from_results_table_supports_multi_select(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
        ],
        "total": 2,
        "page": 1,
        "page_size": 30,
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song")
    view._run_search()
    view._results_table.setSelectionMode(view._results_table.SelectionMode.MultiSelection)
    view._results_table.selectRow(0)
    view._results_table.selectRow(1)

    assert hasattr(view, "_selected_tracks_from_table")
    tracks = view._selected_tracks_from_table(view._results_table)

    assert [track["mid"] for track in tracks] == ["song-1", "song-2"]


def test_root_view_song_buttons_use_multi_selected_results_tracks(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
        ],
        "total": 2,
        "page": 1,
        "page_size": 30,
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song")
    view._run_search()
    selection_model = view._results_table.selectionModel()
    selection_model.select(
        view._results_table.model().index(0, 0),
        selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
    )
    selection_model.select(
        view._results_table.model().index(1, 0),
        selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
    )

    view._add_selected_song_to_queue()
    view._insert_selected_song_to_queue()
    view._download_selected_song()

    assert context.services.media.add_online_track_to_queue.call_count == 2
    assert context.services.media.insert_online_track_to_queue.call_count == 2
    assert context.services.media.cache_remote_track.call_count == 2


def test_root_view_play_button_plays_first_selected_result_and_queues_rest(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
        ],
        "total": 2,
        "page": 1,
        "page_size": 30,
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Song")
    view._run_search()
    selection_model = view._results_table.selectionModel()
    selection_model.select(
        view._results_table.model().index(0, 0),
        selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
    )
    selection_model.select(
        view._results_table.model().index(1, 0),
        selection_model.SelectionFlag.Select | selection_model.SelectionFlag.Rows,
    )

    view._play_selected_song()

    context.services.media.play_online_track.assert_called_once()
    assert context.services.media.add_online_track_to_queue.call_count == 1


def test_root_view_add_selected_to_favorites_uses_bootstrap_services(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    bootstrap = Mock()
    bootstrap.library_service.add_online_track.side_effect = [101, 102]
    bootstrap.favorites_service = Mock()
    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", Mock(return_value=bootstrap))

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    tracks = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
    ]

    view._add_selected_to_favorites(tracks)

    assert bootstrap.library_service.add_online_track.call_count == 2
    assert bootstrap.favorites_service.add_favorite.call_count == 2


def test_root_view_add_selected_to_playlist_uses_playlist_helper(qtbot, monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []

    bootstrap = Mock()
    bootstrap.library_service.add_online_track.side_effect = [201, 202]
    monkeypatch.setattr("app.bootstrap.Bootstrap.instance", Mock(return_value=bootstrap))
    playlist_adder = Mock()
    monkeypatch.setattr("utils.playlist_utils.add_tracks_to_playlist", playlist_adder)

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    tracks = [
        {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        {"mid": "song-2", "title": "Song 2", "artist": "Singer 2", "album": "Album 2", "duration": 180},
    ]

    view._add_selected_to_playlist(tracks)

    playlist_adder.assert_called_once()


def test_root_view_artist_detail_navigation(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "artists": [{"mid": "artist-1", "name": "Singer 1", "song_count": 12}],
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1", "duration": 210},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._artists_list.setCurrentRow(0)

    view._open_artist_detail(view._artists_list.item(0))

    assert view._home_stack.currentWidget() is view._detail_page
    assert hasattr(view, "_detail_info_section")
    assert hasattr(view, "_detail_songs_section")
    assert view._detail_type_label.text() == t("artist")
    assert view._detail_title.text() == "Singer 1"
    assert view._detail_stats_label.text() == f"12 {t('songs')}"
    assert view._detail_tracks_list.count() == 1
    provider.get_artist_detail.assert_called_once_with("artist-1")
    view._go_back_from_detail()
    assert view._results_stack.currentWidget() is view._artists_page


def test_root_view_artist_detail_exposes_follow_toggle(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "follow_status": False,
    }
    provider.follow_artist.return_value = True

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))

    assert view._detail_follow_btn.isHidden() is False

    view._detail_follow_btn.click()

    provider.follow_artist.assert_called_once_with("artist-1")
    assert view._detail_follow_btn.text() == t("qqmusic_followed", "Following")


def test_root_view_album_detail_exposes_qq_favorite_toggle(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "albums": [{"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"}],
    }
    provider.get_album_detail.return_value = {
        "title": "Album 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "is_faved": False,
    }
    provider.fav_album.return_value = True

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Album 1")
    view._search_type_tabs.setCurrentIndex(2)
    view._run_search()
    view._open_album_detail(view._albums_list.item(0))

    assert view._detail_fav_btn.isHidden() is False
    assert view._detail_type_label.text() == t("album")
    assert "Singer 1" in view._detail_meta_label.text()

    view._detail_fav_btn.click()

    provider.fav_album.assert_called_once_with("album-1")
    assert view._detail_fav_btn.text() == t("qqmusic_remove_from_favorites", "Remove from QQ Favorites")


def test_root_view_playlist_detail_exposes_qq_favorite_toggle(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "playlists": [{"id": "playlist-1", "title": "Playlist 1", "creator": "Tester"}],
    }
    provider.get_playlist_detail.return_value = {
        "title": "Playlist 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "is_faved": False,
    }
    provider.fav_playlist.return_value = True

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Playlist 1")
    view._search_type_tabs.setCurrentIndex(3)
    view._run_search()
    view._open_playlist_detail(view._playlists_list.item(0))

    assert view._detail_fav_btn.isHidden() is False
    assert view._detail_type_label.text() == t("playlists")

    view._detail_fav_btn.click()

    provider.fav_playlist.assert_called_once_with("playlist-1")
    assert view._detail_fav_btn.text() == t("qqmusic_remove_from_favorites", "Remove from QQ Favorites")


def test_root_view_artist_detail_shows_related_albums_and_opens_album_detail(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
    }
    provider.get_artist_albums.return_value = [
        {"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"},
    ]
    provider.get_album_detail.return_value = {
        "title": "Album 1",
        "songs": [{"mid": "song-2", "title": "Song 2", "artist": "Singer 1"}],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))

    assert hasattr(view, "_detail_albums_list")
    assert view._detail_albums_list.count() == 1

    view._open_album_from_detail(view._detail_albums_list.item(0))

    assert view._detail_title.text() == "Album 1"


def test_root_view_back_from_album_detail_restores_artist_detail(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
    }
    provider.get_artist_albums.return_value = [
        {"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"},
    ]
    provider.get_album_detail.return_value = {
        "title": "Album 1",
        "songs": [{"mid": "song-2", "title": "Song 2", "artist": "Singer 1"}],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))
    view._open_album_from_detail(view._detail_albums_list.item(0))
    view._go_back_from_detail()

    assert view._detail_title.text() == "Singer 1"
    assert view._detail_albums_list.count() == 1


def test_root_view_album_and_playlist_detail_navigation(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.side_effect = [
        {"albums": [{"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"}]},
        {"albums": [{"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"}]},
        {"playlists": [{"id": "playlist-1", "title": "Playlist 1", "creator": "Tester"}]},
        {"playlists": [{"id": "playlist-1", "title": "Playlist 1", "creator": "Tester"}]},
    ]
    provider.get_album_detail.return_value = {
        "title": "Album 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
    }
    provider.get_playlist_detail.return_value = {
        "title": "Playlist 1",
        "songs": [{"mid": "song-2", "title": "Song 2", "artist": "Singer 2"}],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Album 1")
    view._search_type_tabs.setCurrentIndex(2)
    view._run_search()
    view._open_album_detail(view._albums_list.item(0))
    assert view._detail_title.text() == "Album 1"
    view._go_back_from_detail()
    assert view._results_stack.currentWidget() is view._albums_page

    view._search_input.setText("Playlist 1")
    view._search_type_tabs.setCurrentIndex(3)
    view._run_search()
    view._open_playlist_detail(view._playlists_list.item(0))
    assert view._detail_title.text() == "Playlist 1"
    view._go_back_from_detail()
    assert view._results_stack.currentWidget() is view._playlists_page


def test_root_view_detail_actions_use_media_bridge(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "flac",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "artists": [{"mid": "artist-1", "name": "Singer 1", "song_count": 12}],
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"}],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))
    view._detail_tracks_list.setCurrentRow(0)

    view._play_selected_detail_track()
    view._add_selected_detail_track_to_queue()
    view._insert_selected_detail_track_to_queue()
    view._download_selected_detail_track()

    assert media.play_online_track.call_count == 1
    assert media.add_online_track_to_queue.call_count == 1
    assert media.insert_online_track_to_queue.call_count == 1
    assert media.cache_remote_track.call_count == 1


def test_root_view_detail_view_supports_batch_actions(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "flac",
    }.get(key, default)
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

    assert hasattr(view, "_open_artist_detail_from_grid")
    assert hasattr(view, "_play_all_from_detail_tracks")
    assert hasattr(view, "_add_all_detail_tracks_to_queue")
    assert hasattr(view, "_insert_all_detail_tracks_to_queue")

    view._open_artist_detail_from_grid({"mid": "artist-1", "name": "Singer 1"})
    view._play_all_from_detail_tracks()
    view._add_all_detail_tracks_to_queue()
    view._insert_all_detail_tracks_to_queue()

    assert context.services.media.play_online_track.call_count == 1
    assert context.services.media.add_online_track_to_queue.call_count == 3
    assert context.services.media.insert_online_track_to_queue.call_count == 2


def test_root_view_detail_has_visible_all_track_action_buttons(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))

    assert hasattr(view, "_detail_play_all_btn")
    assert hasattr(view, "_detail_queue_all_btn")
    assert hasattr(view, "_detail_insert_all_btn")
    assert view._detail_play_all_btn.isHidden() is False
    assert view._detail_queue_all_btn.isHidden() is False
    assert view._detail_insert_all_btn.isHidden() is False


def test_root_view_detail_all_track_buttons_use_all_tracks(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))

    view._detail_play_all_btn.click()
    view._detail_queue_all_btn.click()
    view._detail_insert_all_btn.click()

    assert context.services.media.play_online_track.call_count == 1
    assert context.services.media.add_online_track_to_queue.call_count == 3
    assert context.services.media.insert_online_track_to_queue.call_count == 2


def test_root_view_detail_tracks_support_multi_select(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))
    view._detail_tracks_list.setSelectionMode(view._detail_tracks_list.SelectionMode.MultiSelection)
    view._detail_tracks_list.item(0).setSelected(True)
    view._detail_tracks_list.item(1).setSelected(True)

    assert hasattr(view, "_selected_detail_tracks")
    tracks = view._selected_detail_tracks()

    assert [track["mid"] for track in tracks] == ["song-1", "song-2"]


def test_root_view_detail_actions_use_selected_tracks_when_multi_selected(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
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
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))
    view._detail_tracks_list.item(0).setSelected(True)
    view._detail_tracks_list.item(1).setSelected(True)

    view._add_selected_detail_track_to_queue()
    view._insert_selected_detail_track_to_queue()
    view._download_selected_detail_track()

    assert context.services.media.add_online_track_to_queue.call_count == 2
    assert context.services.media.insert_online_track_to_queue.call_count == 2
    assert context.services.media.cache_remote_track.call_count == 2


def test_root_view_detail_back_returns_to_previous_page(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {
            "title": "猜你喜欢",
            "subtitle": "1 项",
            "items": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        },
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_recommendation_section(view._recommend_list.item(0))
    view._detail_back_btn.click()

    assert view._home_stack.currentWidget() is view._home_page


def test_root_view_favorites_navigation(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "title": "我喜欢的歌曲",
            "count": 1,
            "items": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"}],
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_favorite_section(view._favorites_list.item(0))

    assert view._home_stack.currentWidget() is view._detail_page
    assert view._detail_tracks_list.count() == 1


def test_root_view_recommendation_navigation(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = [
        {
            "title": "猜你喜欢",
            "subtitle": "1 项",
            "cover_url": "http://example.com/card-cover.jpg",
            "items": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"}],
        },
    ]
    provider.get_favorites.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_recommendation_section(view._recommend_list.item(0))

    assert view._home_stack.currentWidget() is view._detail_page
    assert view._detail_tracks_list.count() == 1
    assert view._detail_tracks_stack.currentWidget() is view._detail_tracks_view
    assert view._detail_title.text() == "猜你喜欢"
    assert view._detail_cover_url == "http://example.com/card-cover.jpg"


def test_root_view_artist_detail_uses_tracks_list_view(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "artists": [{"mid": "artist-1", "name": "Singer 1", "song_count": 2}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
            {"mid": "song-2", "title": "Song 2", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))

    assert view._detail_tracks_stack.currentWidget() is view._detail_tracks_view


def test_root_view_artist_detail_shows_related_albums_grid(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "artists": [{"mid": "artist-1", "name": "Singer 1", "song_count": 2, "album_count": 1}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_artist_detail.return_value = {
        "title": "Singer 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"}],
    }
    provider.get_artist_albums.return_value = [
        {"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1", "publish_date": "2024-01-01"},
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Singer 1")
    view._search_type_tabs.setCurrentIndex(1)
    view._run_search()
    view._open_artist_detail(view._artists_list.item(0))

    assert hasattr(view, "_detail_albums_grid")
    assert view._detail_albums_grid.isHidden() is False
    assert len(view._detail_albums_grid._items) == 1


def test_root_view_album_detail_uses_tracks_list_view(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "albums": [{"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_album_detail.return_value = {
        "title": "Album 1",
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Album 1")
    view._search_type_tabs.setCurrentIndex(2)
    view._run_search()
    view._open_album_detail(view._albums_list.item(0))

    assert view._detail_tracks_stack.currentWidget() is view._detail_tracks_view


def test_root_view_album_detail_shows_extra_meta_line(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "albums": [{"mid": "album-1", "name": "Album 1", "singer_name": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_album_detail.return_value = {
        "title": "Album 1",
        "songs": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"}],
        "company": "QQ Music",
        "language": "国语",
        "album_type": "录音室专辑",
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Album 1")
    view._search_type_tabs.setCurrentIndex(2)
    view._run_search()
    view._open_album_detail(view._albums_list.item(0))

    assert hasattr(view, "_detail_extra_label")
    assert "QQ Music" in view._detail_extra_label.text()
    assert "国语" in view._detail_extra_label.text()
    assert "录音室专辑" in view._detail_extra_label.text()


def test_root_view_playlist_detail_uses_tracks_list_view(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.search.return_value = {
        "playlists": [{"id": "playlist-1", "title": "Playlist 1", "creator": "Tester"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_playlist_detail.return_value = {
        "title": "Playlist 1",
        "songs": [
            {"mid": "song-1", "title": "Song 1", "artist": "Singer 1", "album": "Album 1"},
        ],
    }

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("Playlist 1")
    view._search_type_tabs.setCurrentIndex(3)
    view._run_search()
    view._open_playlist_detail(view._playlists_list.item(0))

    assert view._detail_tracks_stack.currentWidget() is view._detail_tracks_view


def test_root_view_show_hotkey_popup_does_not_sync_fetch_hotkeys_when_history_exists(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view._hotkeys_cache = []
    view._hotkeys_list.clear()
    view._search_input.setFocus()
    initial_calls = provider.get_hotkeys.call_count

    view._show_hotkey_popup()

    assert provider.get_hotkeys.call_count == initial_calls
    assert view._hotkey_popup is not None
    assert view._hotkey_popup.count() == 1


def test_root_view_favorites_playlist_navigation(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "title": "我收藏的歌单",
            "count": 1,
            "items": [{"id": "pl-1", "title": "Playlist 1", "creator": "Tester", "song_count": 12}],
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view._search_input.setText("abc")
    view._run_search()
    assert view._search_type_tabs.isHidden() is False

    view._open_favorite_section(view._favorites_list.item(0))

    assert view._home_stack.currentWidget() is view._results_page
    assert view._results_stack.currentWidget() is view._playlists_page
    assert view._playlists_list.count() == 1
    assert len(view._playlists_page._items) == 1
    assert view._search_type_tabs.isHidden() is True


def test_root_view_collection_album_navigation_loads_visible_grid(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "title": "我收藏的专辑",
            "count": 1,
            "items": [{"mid": "album-1", "title": "Album 1", "singer_name": "Singer 1"}],
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_favorite_section(view._favorites_list.item(0))

    assert view._results_stack.currentWidget() is view._albums_page
    assert len(view._albums_page._items) == 1


def test_root_view_followed_singers_collection_opens_artist_grid(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "title": "我关注的歌手",
            "count": 1,
            "items": [{"mid": "artist-1", "name": "Singer 1", "fan_count": 10, "cover_url": "http://example/avatar.jpg"}],
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._open_favorite_section(view._favorites_list.item(0))

    assert view._results_stack.currentWidget() is view._artists_page
    assert len(view._artists_page._items) == 1


def test_root_view_collection_back_button_returns_home(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "Tester",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = True
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.search.return_value = {
        "tracks": [{"mid": "song-1", "title": "Song 1", "artist": "Singer 1"}],
        "total": 1,
        "page": 1,
        "page_size": 30,
    }
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = [
        {
            "title": "我收藏的歌单",
            "count": 1,
            "items": [{"id": "pl-1", "title": "Playlist 1", "creator": "Tester", "song_count": 12}],
        },
    ]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("abc")
    view._run_search()
    assert view._search_type_tabs.isHidden() is False

    view._open_favorite_section(view._favorites_list.item(0))

    assert hasattr(view, "_results_back_btn")
    assert view._results_back_btn.isHidden() is False
    assert "我收藏的歌单" in view._results_info_label.text()
    assert view._search_type_tabs.isHidden() is True

    view._go_back_from_results()

    assert view._home_stack.currentWidget() is view._home_page
    assert view._results_back_btn.isHidden() is True


def test_root_view_loads_hotkeys_and_completion(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [
        {"title": "周杰伦"},
        {"title": "林俊杰"},
    ]
    provider.complete.return_value = [
        {"hint": "周杰伦 晴天"},
        {"hint": "周杰伦 七里香"},
    ]
    provider.search_tracks.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert view._hotkeys_list.count() == 2

    view._update_completion("周杰伦")
    model = view._completer.model()
    assert model.rowCount() == 2


def test_root_view_async_home_load_refreshes_hotkey_popup_when_search_is_focused(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()
    view._search_input.setFocus()
    view._show_hotkey_popup()

    payload = {
        "top_lists": [],
        "top_tracks": [],
        "top_tracks_id": "",
        "hotkeys": [{"title": "周杰伦", "query": "周杰伦"}],
        "history": [],
        "favorites": [],
        "recommendations": [],
        "logged_in": False,
        "load_private": False,
    }

    view._on_home_sections_loaded(payload)

    assert view._hotkey_popup is not None
    assert view._hotkey_popup.isVisible() is True
    assert view._hotkey_popup.count() == 1


def test_root_view_completion_is_debounced(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = [{"hint": "周杰伦 晴天"}]

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("周杰伦")

    assert provider.complete.call_count == 0
    qtbot.waitUntil(lambda: provider.complete.call_count == 1)


def test_root_view_stale_completion_results_are_ignored(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
    }.get(key, default)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert hasattr(view, "_on_completion_ready")
    view._completion_request_id = 2
    view._on_completion_ready([{"hint": "old"}], 1)

    model = view._completer.model()
    assert model is None or model.rowCount() == 0


def test_root_view_hotkey_popup_shows_and_escape_hides(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()

    assert hasattr(view, "_show_hotkey_popup")
    assert hasattr(view, "_on_escape_pressed")
    view._show_hotkey_popup()

    assert view._hotkey_popup is not None
    assert view._hotkey_popup.isVisible() is True
    assert bool(view._hotkey_popup.windowFlags() & Qt.Popup) is False
    assert bool(view._hotkey_popup.windowFlags() & Qt.Tool) is False

    view._on_escape_pressed()

    assert view._hotkey_popup.isVisible() is False


def test_root_view_focusing_search_after_suppression_shows_hotkey_popup(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()

    view._on_app_focus_changed(view._search_input, view._login_btn)
    assert view._suppress_hotkey_popup is True

    view._request_search_popup()

    assert view._hotkey_popup is not None
    assert view._hotkey_popup.isVisible() is True


def test_click_outside_search_clears_focus_and_hides_popup(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()
    view._search_input.setFocus()
    view._show_hotkey_popup()

    qtbot.waitUntil(lambda: view._hotkey_popup.isVisible())

    qtbot.mouseClick(view._home_stack, Qt.LeftButton)

    qtbot.waitUntil(lambda: not view._hotkey_popup.isVisible())


def test_search_focus_loss_hides_popup(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()
    view._search_input.setFocus()
    view._show_hotkey_popup()

    qtbot.waitUntil(lambda: view._hotkey_popup.isVisible())
    view._on_app_focus_changed(view._search_input, view._login_btn)

    qtbot.waitUntil(lambda: not view._hotkey_popup.isVisible())


def test_root_view_clear_search_history_updates_store_and_popup(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰", "周杰伦"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()
    view._show_hotkey_popup()

    assert hasattr(view, "_clear_search_history")
    view._clear_search_history()

    assert store["search_history"] == []
    assert view._history_list.count() == 0
    assert view._hotkey_popup.count() == 1


def test_root_view_delete_search_history_item_updates_store_and_popup(qtbot):
    settings = Mock()
    store = {"nick": "", "quality": "320", "search_history": ["林俊杰", "周杰伦"]}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = [{"title": "周杰伦", "query": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)
    view.show()
    view._show_hotkey_popup()

    assert hasattr(view, "_delete_search_history_item")
    view._delete_search_history_item("林俊杰")

    assert store["search_history"] == ["周杰伦"]
    assert view._history_list.count() == 1
def test_root_view_records_search_history_and_can_reuse_it(qtbot):
    settings = Mock()
    store = {}
    settings.get.side_effect = lambda key, default=None: store.get(key, default)
    settings.set.side_effect = lambda key, value: store.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []
    provider.search_tracks.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("周杰伦")
    view._run_search()

    assert store["search_history"] == ["周杰伦"]
    assert view._history_list.count() == 1

    view._open_history_search(view._history_list.item(0))
    assert provider.search_tracks.call_count >= 2


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
    provider.get_recommendations.return_value = [
        {
            "id": "guess",
            "title": "猜你喜欢",
            "subtitle": "1 项",
            "cover_url": "",
            "items": [{"mid": "song-1"}],
            "entry_type": "songs",
        },
    ]
    provider.get_favorites.return_value = [
        {
            "id": "fav_songs",
            "title": "我喜欢的歌曲",
            "subtitle": "1 首",
            "cover_url": "",
            "items": [{"mid": "song-1"}],
            "entry_type": "songs",
        },
    ]
    provider.search.return_value = {"tracks": [], "total": 0, "page": 1, "page_size": 30}

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._search_input.setText("abc")
    view._run_search()
    view._on_search_text_changed("")

    assert view._home_stack.currentWidget() is view._home_page
    assert view._favorites_section.isHidden() is False
    assert view._recommend_section.isHidden() is False


def test_root_view_login_toggle_updates_status(monkeypatch, qtbot):
    settings = Mock()
    state = {"nick": "", "credential": None, "quality": "320"}
    settings.get.side_effect = lambda key, default=None: state.get(key, default)
    settings.set.side_effect = lambda key, value: state.__setitem__(key, value)
    media = Mock()
    context = Mock(settings=settings)
    context.services.media = media
    provider = Mock()
    provider.is_logged_in.side_effect = lambda: bool(state["nick"] or state["credential"])
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    dialog = Mock()
    dialog.exec.side_effect = lambda: state.update({"nick": "Tester", "credential": {"musicid": "1"}})
    monkeypatch.setattr("plugins.builtin.qqmusic.lib.root_view.QQMusicLoginDialog", Mock(return_value=dialog))

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    view._handle_login_toggle()
    assert "Tester" in view._status.text()

    view._handle_login_toggle()
    assert state["nick"] == ""


def test_root_view_refresh_ui_reloads_sections(qtbot):
    settings = Mock()
    state = {"nick": "", "quality": "320", "search_history": []}
    settings.get.side_effect = lambda key, default=None: state.get(key, default)
    settings.set.side_effect = lambda key, value: state.__setitem__(key, value)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.side_effect = lambda: bool(state["nick"])
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.side_effect = lambda: [{"title": "推荐", "subtitle": "1 项", "items": []}] if state["nick"] else []
    provider.get_favorites.side_effect = lambda: [{"title": "收藏", "count": 1, "items": []}] if state["nick"] else []
    provider.get_hotkeys.return_value = [{"title": "周杰伦"}]
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    state["nick"] = "Tester"
    view._favorites_cache = [{"title": "收藏", "count": 1, "items": []}]
    view._recommendations_cache = [{"title": "推荐", "subtitle": "1 项", "items": []}]
    view.refresh_ui()

    assert "Tester" in view._status.text()
    assert view._recommend_section.isHidden() is False
    assert view._favorites_section.isHidden() is False
    assert view._recommend_group.isHidden() is True
    assert view._favorites_group.isHidden() is True
    provider.get_recommendations.assert_not_called()
    provider.get_favorites.assert_not_called()


def test_root_view_applies_theme_styles_on_init(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "nick": "",
        "quality": "320",
        "search_history": [],
        "ranking_view_mode": "table",
    }.get(key, default)
    context = Mock(settings=settings)
    context.services.media = Mock()
    provider = Mock()
    provider.is_logged_in.return_value = False
    provider.get_top_lists.return_value = []
    provider.get_top_list_tracks.return_value = []
    provider.get_recommendations.return_value = []
    provider.get_favorites.return_value = []
    provider.get_hotkeys.return_value = []
    provider.complete.return_value = []

    view = QQMusicRootView(context, provider)
    qtbot.addWidget(view)

    assert view.styleSheet()
    assert view._search_input.styleSheet()
    assert view._search_type_tabs.styleSheet()
    assert view._results_table.styleSheet()
    assert view._top_tracks_table.styleSheet()
    assert view._ranking_view_toggle_btn.styleSheet()
    assert view._top_list_widget.styleSheet()
    assert view._ranking_list_view.styleSheet()
    assert view._detail_ui_built is False
    assert view._completer.popup().styleSheet()

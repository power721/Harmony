from unittest.mock import Mock

from plugins.builtin.qqmusic.lib import i18n as plugin_i18n
from plugins.builtin.qqmusic.lib.client import QQMusicPluginClient
from plugins.builtin.qqmusic.lib.models import OnlineArtist
from plugins.builtin.qqmusic.lib.online_music_view import OnlineMusicView
from plugins.builtin.qqmusic.lib.plugin_online_music_service import PluginOnlineMusicService
from plugins.builtin.qqmusic.lib.provider import QQMusicOnlineProvider
from plugins.builtin.qqmusic.lib.runtime_bridge import (
    bind_context,
    clear_context,
    create_online_download_service,
    create_online_music_service,
)
from plugins.builtin.qqmusic.plugin_main import QQMusicPlugin


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


def test_runtime_bridge_uses_plugin_online_core_services():
    context = Mock()
    context.http = Mock()
    context.settings = Mock()
    context.runtime = Mock()
    config = Mock()
    config.get_online_music_download_dir.return_value = "data/online_cache"
    bind_context(context)
    try:
        service = create_online_music_service(
            config_manager=config,
            credential_provider=None,
        )
        download_service = create_online_download_service(
            config_manager=config,
            credential_provider=None,
            online_music_service=service,
        )
    finally:
        clear_context(context)

    assert service.__class__.__module__.startswith(
        "plugins.builtin.qqmusic.lib.plugin_online_music_service"
    )
    assert download_service.__class__.__module__.startswith(
        "plugins.builtin.qqmusic.lib.plugin_online_download_service"
    )
    context.runtime.create_online_music_service.assert_not_called()
    context.runtime.create_online_download_service.assert_not_called()


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


def test_qqmusic_provider_download_track_delegates_to_plugin_service(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "online_music_download_dir": "data/online_cache",
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    created = {}

    class _DownloadService:
        def __init__(self):
            self.set_download_dir = Mock()
            self.download = Mock(return_value="/tmp/song.ogg")
            self.pop_last_download_quality = Mock(return_value="ogg_320")

    download_service = _DownloadService()

    def _create_service(**kwargs):
        created.update(kwargs)
        return download_service

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.provider.create_online_download_service",
        _create_service,
    )

    provider = QQMusicOnlineProvider(context)
    result = provider.download_track("song-mid", "flac", target_dir="/tmp/online-cache")

    assert result == {"local_path": "/tmp/song.ogg", "quality": "ogg_320"}
    assert created["config_manager"].get_online_music_download_dir() == "data/online_cache"
    assert created["credential_provider"] is provider._client
    download_service.set_download_dir.assert_called_once_with("/tmp/online-cache")
    download_service.download.assert_called_once_with(
        "song-mid",
        quality="flac",
        progress_callback=None,
        force=False,
    )
    download_service.pop_last_download_quality.assert_called_once_with("song-mid")


def test_qqmusic_provider_exposes_download_quality_options():
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: default
    context = Mock(settings=settings)
    context.logger = Mock()
    provider = QQMusicOnlineProvider(context)

    options = provider.get_download_qualities("song-mid")

    assert options
    assert all("value" in item and "label" in item for item in options)


def test_qqmusic_provider_redownload_calls_download_with_force(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "online_music_download_dir": "data/online_cache",
    }.get(key, default)
    context = Mock(settings=settings)
    context.logger = Mock()

    class _DownloadService:
        def __init__(self):
            self.set_download_dir = Mock()
            self.download = Mock(return_value="/tmp/song.flac")
            self.pop_last_download_quality = Mock(return_value="flac")

    download_service = _DownloadService()
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.provider.create_online_download_service",
        lambda **_kwargs: download_service,
    )

    provider = QQMusicOnlineProvider(context)
    result = provider.redownload_track(
        "song-mid",
        "flac",
        target_dir="/tmp/online-cache",
    )

    assert result == {"local_path": "/tmp/song.flac", "quality": "flac"}
    download_service.download.assert_called_once_with(
        "song-mid",
        quality="flac",
        progress_callback=None,
        force=True,
    )


def test_qqmusic_plugin_uses_private_translations_not_global(monkeypatch):
    import system.i18n as global_i18n

    original = global_i18n._translations.get("zh", {}).get("qqmusic_page_title")
    global_i18n._translations.setdefault("zh", {})["qqmusic_page_title"] = "全局错误文案"
    plugin_i18n.set_language("zh")

    try:
        assert plugin_i18n.t("qqmusic_page_title") == "QQ音乐"
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

    adapter = QQMusicOnlineProvider._create_config_adapter(Mock(settings=settings))

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

    adapter = QQMusicOnlineProvider._create_config_adapter(Mock(settings=settings))

    assert adapter.get_online_music_download_dir() == "data/online_cache"


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


def test_plugin_client_search_falls_back_to_public_api_when_legacy_empty(monkeypatch):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "credential": {"musicid": "1", "musickey": "secret"},
    }.get(key, default)
    context = Mock(settings=settings)

    api = Mock()
    api.search.return_value = {
        "tracks": [{"mid": "api-song", "title": "API Song"}],
        "total": 1,
    }
    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.client.QQMusicPluginAPI",
        Mock(return_value=api),
    )

    client = QQMusicPluginClient(context)
    monkeypatch.setattr(client, "_can_use_legacy_network", lambda: True)
    monkeypatch.setattr(
        client,
        "_search_legacy",
        lambda keyword, search_type, page, limit: {"tracks": [], "total": 0},
    )

    result = client.search("keyword", search_type="song", limit=20, page=1)

    assert result["tracks"][0]["mid"] == "api-song"
    api.search.assert_called_once_with("keyword", search_type="song", limit=20, page=1)


def test_plugin_online_music_service_converts_singer_payload_to_models(monkeypatch):
    context = Mock()
    context.settings = Mock()
    service = PluginOnlineMusicService(context)
    monkeypatch.setattr(
        service,
        "_client_adapter",
        Mock(
            search=Mock(
                return_value={
                    "artists": [
                        {
                            "mid": "artist-mid",
                            "name": "Artist A",
                            "avatar_url": "https://example.com/a.jpg",
                            "song_count": 12,
                        }
                    ],
                    "total": 1,
                }
            )
        ),
    )

    result = service.search("artist", search_type="singer", page=1, page_size=30)

    assert len(result.artists) == 1
    assert isinstance(result.artists[0], OnlineArtist)
    assert result.artists[0].mid == "artist-mid"
    assert result.artists[0].name == "Artist A"


def test_plugin_online_music_service_strips_em_tags_in_search_results(monkeypatch):
    context = Mock()
    context.settings = Mock()
    service = PluginOnlineMusicService(context)
    monkeypatch.setattr(
        service,
        "_client_adapter",
        Mock(
            search=Mock(
                return_value={
                    "tracks": [
                        {
                            "mid": "song-mid",
                            "title": "<em>晴天</em>",
                            "artist": "周<em>杰伦</em>",
                            "album": "<em>叶惠美</em>",
                            "duration": 269,
                        }
                    ],
                    "total": 1,
                }
            )
        ),
    )

    result = service.search("晴天", search_type="song", page=1, page_size=30)

    assert result.tracks[0].title == "晴天"
    assert result.tracks[0].singer_name == "周杰伦"
    assert result.tracks[0].album_name == "叶惠美"

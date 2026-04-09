"""Architecture guards for online views and playback constructor contracts."""

import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch

from plugins.builtin.qqmusic.lib.online_detail_view import OnlineDetailView
from plugins.builtin.qqmusic.lib.online_detail_view import DownloadWorker as DetailDownloadWorker
from plugins.builtin.qqmusic.lib.online_music_view import OnlineMusicView
from services.playback.playback_service import PlaybackService


def test_constructors_do_not_accept_db_manager():
    """Constructor signatures should not expose deprecated db_manager."""
    assert "db_manager" not in inspect.signature(PlaybackService.__init__).parameters
    assert "db_manager" not in inspect.signature(OnlineMusicView.__init__).parameters
    assert "db_manager" not in inspect.signature(OnlineDetailView.__init__).parameters


def test_online_music_view_add_to_favorites_uses_favorites_service():
    """OnlineMusicView favorite add path should call favorites_service, not _db."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._ranking_list_view = SimpleNamespace(set_track_favorite=Mock())
    view._add_online_track_to_library = Mock(return_value=123)
    view._db = None
    track = SimpleNamespace(mid="m1")
    bootstrap = SimpleNamespace(
        favorites_service=SimpleNamespace(add_favorite=Mock()),
        library_service=SimpleNamespace(),
    )

    with patch("plugins.builtin.qqmusic.lib.online_music_view.bootstrap", return_value=bootstrap):
        with patch("plugins.builtin.qqmusic.lib.online_music_view.MessageDialog.information"):
            with patch("plugins.builtin.qqmusic.lib.online_music_view.t", return_value="{count}"):
                OnlineMusicView._add_selected_to_favorites(view, [track])

    bootstrap.favorites_service.add_favorite.assert_called_once_with(track_id=123)


def test_online_music_view_remove_favorite_uses_favorites_service():
    """OnlineMusicView favorite remove path should call favorites_service, not _db."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._ranking_list_view = SimpleNamespace(set_track_favorite=Mock())
    view._db = None
    track = SimpleNamespace(mid="m1")
    library_track = SimpleNamespace(id=321)
    bootstrap = SimpleNamespace(
        favorites_service=SimpleNamespace(remove_favorite=Mock()),
        library_service=SimpleNamespace(get_track_by_cloud_file_id=Mock(return_value=library_track)),
    )

    with patch("plugins.builtin.qqmusic.lib.online_music_view.bootstrap", return_value=bootstrap):
        OnlineMusicView._on_ranking_favorite_toggled(view, track, False)

    bootstrap.favorites_service.remove_favorite.assert_called_once_with(track_id=321)


def test_online_music_view_remove_favorite_falls_back_to_cloud_file_id():
    """OnlineMusicView should remove by cloud_file_id when no library track exists."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._ranking_list_view = SimpleNamespace(set_track_favorite=Mock())
    track = SimpleNamespace(mid="m-fallback")
    bootstrap = SimpleNamespace(
        favorites_service=SimpleNamespace(remove_favorite=Mock()),
        library_service=SimpleNamespace(get_track_by_cloud_file_id=Mock(return_value=None)),
    )

    with patch("plugins.builtin.qqmusic.lib.online_music_view.bootstrap", return_value=bootstrap):
        OnlineMusicView._on_ranking_favorite_toggled(view, track, False)

    bootstrap.favorites_service.remove_favorite.assert_called_once_with(cloud_file_id="m-fallback")
    view._ranking_list_view.set_track_favorite.assert_called_once_with("m-fallback", False)


def test_online_detail_view_favorites_flow_uses_favorites_service():
    """OnlineDetailView add/remove favorites should go through FavoritesService."""
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._add_online_track_to_library = Mock(return_value=456)
    view._db = None
    track = SimpleNamespace(mid="m2")
    library_track = SimpleNamespace(id=654)
    bootstrap = SimpleNamespace(
        favorites_service=SimpleNamespace(add_favorite=Mock(), remove_favorite=Mock()),
        library_service=SimpleNamespace(get_track_by_cloud_file_id=Mock(return_value=library_track)),
    )

    with patch("plugins.builtin.qqmusic.lib.online_detail_view.bootstrap", return_value=bootstrap):
        with patch("plugins.builtin.qqmusic.lib.online_detail_view.show_information"):
            with patch("plugins.builtin.qqmusic.lib.online_detail_view.t", return_value="{count}"):
                OnlineDetailView._add_tracks_to_favorites(view, [track])
        OnlineDetailView._remove_track_from_favorites(view, track)

    bootstrap.favorites_service.add_favorite.assert_called_once_with(track_id=456)
    bootstrap.favorites_service.remove_favorite.assert_called_once_with(track_id=654)


def test_online_detail_view_follow_click_requests_followed_singers_refresh():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._detail_type = "artist"
    view._mid = "artist-mid"
    view._is_followed = False
    view._service = SimpleNamespace(follow_singer=Mock(return_value=True))
    view._update_follow_btn_style = Mock()
    view._notify_favorites_collection_changed = Mock()

    OnlineDetailView._on_follow_clicked(view)

    view._service.follow_singer.assert_called_once_with("artist-mid")
    view._notify_favorites_collection_changed.assert_called_once_with("followed_singers")


def test_online_detail_view_album_favorite_click_requests_refresh():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._detail_type = "album"
    view._mid = "album-mid"
    view._is_faved = False
    view._service = SimpleNamespace(fav_album=Mock(return_value=True))
    view._update_fav_btn_style = Mock()
    view._notify_favorites_collection_changed = Mock()

    OnlineDetailView._on_fav_clicked(view)

    view._service.fav_album.assert_called_once_with("album-mid")
    view._notify_favorites_collection_changed.assert_called_once_with("fav_albums")


def test_online_detail_view_album_unfavorite_click_requests_refresh():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._detail_type = "album"
    view._mid = "album-mid"
    view._is_faved = True
    view._service = SimpleNamespace(unfav_album=Mock(return_value=True))
    view._update_fav_btn_style = Mock()
    view._notify_favorites_collection_changed = Mock()

    OnlineDetailView._on_fav_clicked(view)

    view._service.unfav_album.assert_called_once_with("album-mid")
    view._notify_favorites_collection_changed.assert_called_once_with("fav_albums")


def test_online_detail_view_playlist_unfavorite_click_requests_refresh():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._detail_type = "playlist"
    view._mid = "12345"
    view._is_faved = True
    view._service = SimpleNamespace(unfav_playlist=Mock(return_value=True))
    view._update_fav_btn_style = Mock()
    view._notify_favorites_collection_changed = Mock()

    OnlineDetailView._on_fav_clicked(view)

    view._service.unfav_playlist.assert_called_once_with(12345)
    view._notify_favorites_collection_changed.assert_called_once_with("fav_playlists")


def test_online_detail_view_qq_favorite_toggle_requests_song_refresh():
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._service = SimpleNamespace(fav_song=Mock(return_value=True))
    view._notify_favorites_collection_changed = Mock()
    track = SimpleNamespace(id=123, title="Song")

    OnlineDetailView._on_list_qq_fav_toggle(view, [track], False)

    view._service.fav_song.assert_called_once_with(123)
    view._notify_favorites_collection_changed.assert_called_once_with("fav_songs")


def test_online_music_view_add_online_track_to_library_passes_provider_id():
    """OnlineMusicView should persist QQMusic tracks with the provider id."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._get_cover_url = Mock(return_value="https://cover")
    track = SimpleNamespace(
        mid="m1",
        title="Song 1",
        singer_name="Artist 1",
        album_name="Album 1",
        duration=123,
    )
    bootstrap = SimpleNamespace(
        library_service=SimpleNamespace(add_online_track=Mock(return_value=111)),
    )

    with patch("plugins.builtin.qqmusic.lib.online_music_view.bootstrap", return_value=bootstrap):
        result = OnlineMusicView._add_online_track_to_library(view, track)

    assert result == 111
    bootstrap.library_service.add_online_track.assert_called_once_with(
        provider_id="qqmusic",
        song_mid="m1",
        title="Song 1",
        artist="Artist 1",
        album="Album 1",
        duration=123.0,
        cover_url="https://cover",
    )


def test_online_detail_view_add_online_track_to_library_passes_provider_id():
    """OnlineDetailView should persist QQMusic tracks with the provider id."""
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._get_cover_url = Mock(return_value="https://cover")
    track = SimpleNamespace(
        mid="m2",
        title="Song 2",
        singer_name="Artist 2",
        album_name="Album 2",
        duration=234,
    )
    bootstrap = SimpleNamespace(
        library_service=SimpleNamespace(add_online_track=Mock(return_value=222)),
    )

    with patch("plugins.builtin.qqmusic.lib.online_detail_view.bootstrap", return_value=bootstrap):
        result = OnlineDetailView._add_online_track_to_library(view, track)

    assert result == 222
    bootstrap.library_service.add_online_track.assert_called_once_with(
        provider_id="qqmusic",
        song_mid="m2",
        title="Song 2",
        artist="Artist 2",
        album="Album 2",
        duration=234.0,
        cover_url="https://cover",
    )


def test_online_detail_view_download_track_passes_provider_id_to_cache_and_worker():
    """OnlineDetailView download path should propagate provider id to cache checks and worker."""
    view = OnlineDetailView.__new__(OnlineDetailView)
    view._download_service = SimpleNamespace(is_cached=Mock(return_value=False))
    track = SimpleNamespace(mid="m3", title="Song 3")
    captured = {}

    class _FakeSignal:
        def connect(self, callback):
            captured["callback"] = callback

    class _FakeWorker:
        def __init__(self, download_service, song_mid, song_title, provider_id=""):
            captured["download_service"] = download_service
            captured["song_mid"] = song_mid
            captured["song_title"] = song_title
            captured["provider_id"] = provider_id
            self.download_finished = _FakeSignal()
            self.finished = _FakeSignal()

        def start(self):
            captured["started"] = True

        def deleteLater(self):
            captured["deleted"] = True

    with patch("plugins.builtin.qqmusic.lib.online_detail_view.DownloadWorker", _FakeWorker):
        OnlineDetailView._download_track(view, track)

    view._download_service.is_cached.assert_called_once_with("m3", provider_id="qqmusic")
    assert captured["song_mid"] == "m3"
    assert captured["song_title"] == "Song 3"
    assert captured["provider_id"] == "qqmusic"
    assert captured["started"] is True


def test_online_detail_download_worker_passes_provider_id_to_service():
    """Detail-view download worker should pass provider id to the download service."""
    download_service = Mock()
    download_service.download.return_value = "/tmp/song.mp3"
    worker = DetailDownloadWorker(
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


def test_online_music_view_remote_favorites_refresh_invalidates_cache():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._fav_loaded = True
    view._load_favorites = Mock()

    OnlineMusicView._on_favorites_collection_changed(view, "fav_albums")

    assert view._fav_loaded is False
    view._load_favorites.assert_called_once_with()


def test_online_music_view_refreshes_active_fav_songs_view_after_reload():
    view = OnlineMusicView.__new__(OnlineMusicView)
    detail_view = object()
    view._active_favorites_card_type = "fav_songs"
    view._fav_data = {"fav_songs": [{"mid": "song-mid"}]}
    view._detail_view = detail_view
    view._stack = SimpleNamespace(currentWidget=lambda: detail_view)
    view._show_fav_songs_in_table = Mock()

    OnlineMusicView._refresh_active_favorites_view(view)

    view._show_fav_songs_in_table.assert_called_once_with([{"mid": "song-mid"}])


def test_online_music_view_back_from_followed_singers_uses_refreshed_favorites_data():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._navigation_stack = [{"page": "results", "tab": "artists"}]
    view._active_favorites_card_type = "followed_singers"
    view._fav_data = {"followed_singers": [{"mid": "artist-new"}]}
    view._show_singer_list_in_detail = Mock()

    with patch("plugins.builtin.qqmusic.lib.online_music_view.t", return_value="followed_singers"):
        OnlineMusicView._on_back_from_detail(view)

    view._show_singer_list_in_detail.assert_called_once_with(
        "followed_singers",
        [{"mid": "artist-new"}],
        push_navigation=False,
    )


def test_online_music_view_show_fav_songs_in_table_preserves_song_id():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._detail_view = SimpleNamespace(load_songs_directly=Mock())
    view._stack = SimpleNamespace(setCurrentWidget=Mock())

    with patch("plugins.builtin.qqmusic.lib.online_music_view.t", side_effect=lambda value: value):
        OnlineMusicView._show_fav_songs_in_table(view, [{
            "id": 12345,
            "mid": "song-mid",
            "title": "Song 1",
            "singer": "Singer 1",
            "album": "Album 1",
            "album_mid": "album-1",
            "duration": 180,
            "cover_url": "https://cover",
        }])

    songs, title, cover_url = view._detail_view.load_songs_directly.call_args.args
    assert songs == [
        {
            "id": 12345,
            "mid": "song-mid",
            "songmid": "song-mid",
            "title": "Song 1",
            "songname": "Song 1",
            "name": "Song 1",
            "singer": [{"mid": "", "name": "Singer 1"}],
            "album": {"mid": "album-1", "name": "Album 1"},
            "interval": 180,
        }
    ]
    assert title == "fav_songs"
    assert cover_url == "https://cover"


def test_online_music_view_display_favorites_cards_keeps_section_hidden_off_main_page():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._fav_data = {
        "fav_songs": [],
        "created_playlists": [],
        "fav_playlists": [],
        "fav_albums": [],
        "followed_singers": [],
    }
    section = SimpleNamespace(
        load_recommendations=Mock(),
        hide=Mock(),
    )
    view._favorites_section = section
    view._stack = SimpleNamespace(currentWidget=lambda: object())
    view._top_list_page = object()
    view._active_favorites_card_type = "fav_songs"
    view._get_random_cover = Mock(return_value="")

    with patch("plugins.builtin.qqmusic.lib.online_music_view.t", side_effect=lambda value: value):
        OnlineMusicView._display_favorites_cards(view)

    section.load_recommendations.assert_called_once()
    section.hide.assert_called_once_with()

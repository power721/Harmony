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

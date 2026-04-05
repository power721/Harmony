"""Architecture guards for online views and playback constructor contracts."""

import inspect
from types import SimpleNamespace
from unittest.mock import Mock, patch

from ui.views.online_detail_view import OnlineDetailView
from ui.views.online_music_view import OnlineMusicView
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

    with patch("app.bootstrap.Bootstrap.instance", return_value=bootstrap):
        with patch("ui.views.online_music_view.MessageDialog.information"):
            with patch("ui.views.online_music_view.t", return_value="{count}"):
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

    with patch("app.bootstrap.Bootstrap.instance", return_value=bootstrap):
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

    with patch("app.bootstrap.Bootstrap.instance", return_value=bootstrap):
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

    with patch("app.bootstrap.Bootstrap.instance", return_value=bootstrap):
        with patch("ui.views.online_detail_view.MessageDialog.information"):
            with patch("ui.views.online_detail_view.t", return_value="{count}"):
                OnlineDetailView._add_tracks_to_favorites(view, [track])
        OnlineDetailView._remove_track_from_favorites(view, track)

    bootstrap.favorites_service.add_favorite.assert_called_once_with(track_id=456)
    bootstrap.favorites_service.remove_favorite.assert_called_once_with(track_id=654)

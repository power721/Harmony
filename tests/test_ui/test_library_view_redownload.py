from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from domain.history import PlayHistory
from domain.track import Track, TrackSource
from ui.views.library_view import LibraryView

from tests.test_ui.test_library_view import qapp, mock_theme_config, reset_theme_singleton


def test_history_redownload_completion_refreshes_updated_track_path(
    qapp,
    mock_theme_config,
    reset_theme_singleton,
    monkeypatch,
):
    from system.theme import ThemeManager
    import services.download.download_manager as download_manager_module

    ThemeManager.instance(mock_theme_config)

    old_track = Track(
        id=2,
        path="/music/old.mp3",
        title="Two",
        artist="Artist 2",
        cloud_file_id="song-mid",
        source=TrackSource.QQ,
    )
    new_track = Track(
        id=2,
        path="/music/new.ogg",
        title="Two",
        artist="Artist 2",
        cloud_file_id="song-mid",
        source=TrackSource.QQ,
    )

    library_service = MagicMock()
    library_service.get_track_count.return_value = 1
    library_service.get_all_tracks.return_value = [old_track]
    library_service.search_tracks.return_value = [old_track]
    library_service.get_search_track_count.return_value = 1
    library_service.get_tracks_by_ids.side_effect = [[old_track], [new_track]]

    favorites_service = MagicMock()
    favorites_service.get_all_favorite_track_ids.return_value = set()
    favorites_service.get_favorites.return_value = []

    history_service = MagicMock()
    history_service.get_history.return_value = [
        PlayHistory(track_id=2, played_at=datetime(2026, 4, 2, 12, 0, 0))
    ]

    engine = MagicMock()
    engine.current_track_changed = MagicMock()
    engine.current_track_pending = MagicMock()
    engine.state_changed = MagicMock()
    engine.state = None

    player = MagicMock()
    player.engine = engine

    config_manager = MagicMock()
    config_manager.get.return_value = None

    view = LibraryView(
        library_service,
        favorites_service,
        history_service,
        player,
        config_manager=config_manager,
    )
    view.show_history()
    qapp.processEvents()

    fake_manager = SimpleNamespace(
        download_completed=SimpleNamespace(disconnect=MagicMock()),
        download_failed=SimpleNamespace(disconnect=MagicMock()),
    )
    monkeypatch.setattr(
        download_manager_module.DownloadManager,
        "instance",
        classmethod(lambda cls: fake_manager),
    )

    view._on_redownload_completed("song-mid", "/music/new.ogg")
    qapp.processEvents()

    assert view._history_list_view._model.get_track_at(0).path == "/music/new.ogg"

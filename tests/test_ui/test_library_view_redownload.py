from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

import app.bootstrap as bootstrap_module
import services.download.download_manager as download_manager_module
from domain.history import PlayHistory
from domain.track import Track, TrackSource
from system.i18n import t
from ui.dialogs.redownload_dialog import RedownloadDialog
from ui.views.library_view import LibraryView


def _init_theme():
    from system.theme import ThemeManager

    ThemeManager._instance = None
    config = MagicMock()
    config.get.return_value = "dark"
    ThemeManager.instance(config)


def _build_view():
    library_service = MagicMock()
    library_service.get_track_count.return_value = 1
    library_service.get_all_tracks.return_value = []
    library_service.search_tracks.return_value = []
    library_service.get_search_track_count.return_value = 0
    library_service.get_tracks_by_ids.return_value = []

    favorites_service = MagicMock()
    favorites_service.get_all_favorite_track_ids.return_value = set()
    favorites_service.get_favorites.return_value = []

    history_service = MagicMock()
    history_service.get_history.return_value = []

    engine = MagicMock()
    engine.current_track_changed = MagicMock()
    engine.current_track_pending = MagicMock()
    engine.state_changed = MagicMock()
    engine.state = None

    player = MagicMock()
    player.engine = engine

    view = LibraryView(
        library_service,
        favorites_service,
        history_service,
        player,
        config_manager=MagicMock(),
    )
    return view, library_service, history_service


def test_redownload_online_track_uses_provider_quality_and_manager(monkeypatch, qapp):
    _init_theme()

    manager = MagicMock()
    manager.download_completed = MagicMock(connect=MagicMock(), disconnect=MagicMock())
    manager.download_failed = MagicMock(connect=MagicMock(), disconnect=MagicMock())
    manager.redownload_online_track.return_value = True
    monkeypatch.setattr(
        download_manager_module.DownloadManager,
        "instance",
        classmethod(lambda cls: manager),
    )

    online_download_service = MagicMock()
    online_download_service.get_download_qualities.return_value = [
        {"value": "flac", "label": "FLAC"},
        {"value": "320", "label": "320"},
    ]
    monkeypatch.setattr(
        bootstrap_module.Bootstrap,
        "instance",
        classmethod(lambda cls: SimpleNamespace(online_download_service=online_download_service)),
    )
    monkeypatch.setattr(
        "ui.views.library_view.RedownloadDialog.show_dialog",
        MagicMock(return_value="flac"),
    )

    view, _, _ = _build_view()
    track = Track(
        id=2,
        title="Two",
        cloud_file_id="song-mid",
        source=TrackSource.ONLINE,
        online_provider_id="qqmusic",
    )
    view._redownload_online_track(track)
    qapp.processEvents()

    online_download_service.get_download_qualities.assert_called_once_with(
        "song-mid",
        provider_id="qqmusic",
    )
    manager.redownload_online_track.assert_called_once_with(
        song_mid="song-mid",
        title="Two",
        provider_id="qqmusic",
        quality="flac",
    )
    assert view._status_label.text() == t("redownload")


def test_redownload_dialog_returns_selected_quality_when_enabled(qapp):
    _init_theme()

    dialog = RedownloadDialog(
        "Two",
        current_quality="320",
        quality_options=[{"value": "flac", "label": "FLAC"}, {"value": "320", "label": "320"}],
    )
    dialog._quality_combo.setCurrentIndex(0)
    assert dialog.get_quality() == "flac"


def test_history_redownload_completion_updates_status_for_pending_song(monkeypatch, qapp):
    _init_theme()

    manager = MagicMock()
    manager.download_completed = MagicMock(connect=MagicMock(), disconnect=MagicMock())
    manager.download_failed = MagicMock(connect=MagicMock(), disconnect=MagicMock())
    monkeypatch.setattr(
        download_manager_module.DownloadManager,
        "instance",
        classmethod(lambda cls: manager),
    )

    old_track = Track(
        id=2,
        path="/music/old.mp3",
        title="Two",
        artist="Artist 2",
        cloud_file_id="song-mid",
        source=TrackSource.ONLINE,
        online_provider_id="qqmusic",
    )
    new_track = Track(
        id=2,
        path="/music/new.ogg",
        title="Two",
        artist="Artist 2",
        cloud_file_id="song-mid",
        source=TrackSource.ONLINE,
        online_provider_id="qqmusic",
    )

    view, library_service, history_service = _build_view()
    library_service.get_all_tracks.return_value = [old_track]
    library_service.search_tracks.return_value = [old_track]
    library_service.get_search_track_count.return_value = 1
    library_service.get_tracks_by_ids.side_effect = [[old_track], [new_track]]
    history_service.get_history.return_value = [
        PlayHistory(track_id=2, played_at=datetime(2026, 4, 2, 12, 0, 0))
    ]
    view.show_history()
    qapp.processEvents()

    view._pending_redownload_mids.add("song-mid")
    view._on_redownload_completed("song-mid", "/music/new.ogg")
    qapp.processEvents()

    assert view._status_label.text() == t("download_complete")

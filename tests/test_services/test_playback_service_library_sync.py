"""PlaybackService library synchronization regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from domain.track import TrackSource
from services.playback.playback_service import PlaybackService


def test_save_cloud_track_to_library_refreshes_repositories(monkeypatch):
    """Cloud metadata persistence should go through repositories, not direct DB calls."""
    from services.metadata import metadata_service
    from services.lyrics import lyrics_service

    service = PlaybackService.__new__(PlaybackService)
    service._cloud_account = None
    service._engine = SimpleNamespace(current_playlist_item=None)
    service._cover_service = None
    service._track_repo = SimpleNamespace(
        get_by_cloud_file_id=Mock(return_value=None),
        get_by_path=Mock(return_value=None),
        add=Mock(return_value=11),
    )
    service._album_repo = SimpleNamespace(refresh=Mock())
    service._artist_repo = SimpleNamespace(refresh=Mock())
    service._db = SimpleNamespace(
        update_albums_on_track_added=Mock(),
        update_artists_on_track_added=Mock(),
    )
    service._event_bus = SimpleNamespace(tracks_added=SimpleNamespace(emit=Mock()))

    monkeypatch.setattr(
        metadata_service.MetadataService,
        "extract_metadata",
        staticmethod(
            lambda _path: {
                "title": "Cloud Song",
                "artist": "Cloud Artist",
                "album": "Cloud Album",
                "duration": 123.0,
            }
        ),
    )
    monkeypatch.setattr(
        lyrics_service.LyricsService,
        "lyrics_file_exists",
        staticmethod(lambda _path: False),
    )

    PlaybackService._save_cloud_track_to_library(
        service,
        "cloud-file-1",
        "/tmp/cloud-song.mp3",
        TrackSource.QUARK,
    )

    service._track_repo.add.assert_called_once()
    service._album_repo.refresh.assert_called_once()
    service._artist_repo.refresh.assert_called_once()
    service._db.update_albums_on_track_added.assert_not_called()
    service._db.update_artists_on_track_added.assert_not_called()

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


def test_play_cloud_playlist_uses_non_online_track_lookup_for_cached_cloud_files():
    """Cloud playlists should not hydrate metadata from unrelated online tracks sharing the same file id."""
    class _Engine:
        def __init__(self):
            self.items = None
            self.play_at_index = None

        def load_playlist_items(self, items):
            self.items = list(items)

        def is_shuffle_mode(self):
            return False

        def play_at(self, index):
            self.play_at_index = index

    cached_cloud_track = SimpleNamespace(
        id=7,
        path="/tmp/cloud-song.mp3",
        title="Cloud Song",
        artist="Cloud Artist",
        album="Cloud Album",
        duration=123.0,
        cover_path="/tmp/cloud.jpg",
    )
    class _TrackRepo:
        def get_by_cloud_file_ids(self, cloud_file_ids):
            return {
                "shared-id": SimpleNamespace(
                    id=99,
                    path="online://qqmusic/track/shared-id",
                    title="Wrong Online Song",
                    artist="Wrong Artist",
                    album="Wrong Album",
                    duration=300.0,
                    cover_path="wrong.jpg",
                    cloud_file_id="shared-id",
                    online_provider_id="qqmusic",
                )
            }

        def get_by_non_online_cloud_file_ids(self, cloud_file_ids):
            return {"shared-id": cached_cloud_track}

    track_repo = _TrackRepo()

    service = PlaybackService.__new__(PlaybackService)
    service._track_repo = track_repo
    service._engine = _Engine()
    service._downloaded_files = {}
    service._config = Mock()
    service._process_metadata_async = Mock()
    service._set_source = Mock()
    service.save_queue = Mock()
    service._get_cached_path = Mock(return_value="/tmp/cloud-song.mp3")

    account = SimpleNamespace(id=1, provider="quark")
    cloud_file = SimpleNamespace(
        file_id="shared-id",
        name="song.mp3",
        file_type="audio",
        size=1,
        duration=0.0,
        parent_id="0",
        mime_type="audio/mpeg",
        metadata=None,
    )

    PlaybackService.play_cloud_playlist(
        service,
        cloud_files=[cloud_file],
        start_index=0,
        account=account,
    )

    assert service._engine.items is not None
    assert service._engine.items[0].title == "Cloud Song"
    assert service._engine.items[0].track_id == 7

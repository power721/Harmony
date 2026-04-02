"""
Tests for queue service edge cases and regressions.
"""

import threading

from domain.playback import PlayMode
from domain.playlist_item import PlaylistItem
from domain.track import Track, TrackSource
from services.playback.playback_service import PlaybackService
from services.playback.queue_service import QueueService


class FakeQueueRepo:
    def __init__(self):
        self.saved_items = []
        self.clear_calls = 0

    def save(self, items):
        self.saved_items = list(items)
        return True

    def clear(self):
        self.saved_items = []
        self.clear_calls += 1
        return True


class FakeConfig:
    def __init__(self):
        self.values = {}
        self.deleted_keys = []

    def set(self, key, value):
        self.values[key] = value

    def delete(self, key):
        self.deleted_keys.append(key)


class FakeEngine:
    def __init__(self, items=None, current_index=-1, play_mode=PlayMode.SEQUENTIAL):
        self.playlist_items = list(items or [])
        self.current_index = current_index
        self.play_mode = play_mode


class FakeTrackRepo:
    def __init__(self, tracks_by_cloud_id=None):
        self._tracks_by_cloud_id = tracks_by_cloud_id or {}

    def get_by_ids(self, track_ids):
        return []

    def get_by_cloud_file_ids(self, cloud_file_ids):
        return {
            cloud_file_id: self._tracks_by_cloud_id[cloud_file_id]
            for cloud_file_id in cloud_file_ids
            if cloud_file_id in self._tracks_by_cloud_id
        }

    def get_by_paths(self, paths):
        return {}


class FakePagedTrackRepo(FakeTrackRepo):
    def __init__(self, pages):
        super().__init__()
        self._pages = pages
        self.get_all_calls = []

    def get_track_count(self, source=None):
        return sum(len(page) for page in self._pages)

    def get_all(self, limit=0, offset=0, source=None):
        self.get_all_calls.append((limit, offset, source))
        if limit <= 0:
            merged = []
            for page in self._pages:
                merged.extend(page)
            return merged[offset:]

        merged = []
        for page in self._pages:
            merged.extend(page)
        return merged[offset:offset + limit]


def test_enrich_metadata_batch_preserves_cached_qq_file(temp_dir):
    """QQ items with an existing cached file should remain ready after enrichment."""
    cached_path = temp_dir / "downloaded.mp3"
    cached_path.write_text("cached")

    track_repo = FakeTrackRepo(
        tracks_by_cloud_id={
            "song_mid_123": Track(
                id=9,
                path=str(cached_path),
                title="Downloaded Song",
                artist="Online Artist",
                source=TrackSource.QQ,
                cloud_file_id="song_mid_123",
            )
        }
    )
    service = QueueService(
        queue_repo=FakeQueueRepo(),
        config_manager=FakeConfig(),
        engine=FakeEngine(),
        track_repo=track_repo,
    )
    item = PlaylistItem(
        source=TrackSource.QQ,
        track_id=9,
        cloud_file_id="song_mid_123",
        local_path=str(cached_path),
        title="Downloaded Song",
        needs_download=False,
    )

    restored = service._enrich_metadata_batch([item])[0]

    assert restored.local_path == str(cached_path)
    assert restored.needs_download is False


def test_save_clears_persisted_queue_when_engine_playlist_is_empty():
    """Saving an empty queue should clear stale persisted queue state."""
    repo = FakeQueueRepo()
    config = FakeConfig()
    service = QueueService(
        queue_repo=repo,
        config_manager=config,
        engine=FakeEngine(items=[]),
    )

    service.save()

    assert repo.clear_calls == 1
    assert repo.saved_items == []
    assert set(config.deleted_keys) == {"queue_current_index", "queue_play_mode"}


def test_playback_service_save_queue_clears_persisted_state_when_empty():
    """PlaybackService.save_queue should also clear stale queue persistence."""
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine(items=[])
    service._queue_repo = FakeQueueRepo()
    service._config = FakeConfig()

    PlaybackService.save_queue(service)

    assert service._queue_repo.clear_calls == 1
    assert set(service._config.deleted_keys) == {"queue_current_index", "queue_play_mode"}


def test_play_local_library_reads_tracks_in_pages(monkeypatch):
    """Library playback should page through repository reads instead of one unbounded load."""
    pages = [
        [Track(id=1, path="/tmp/1.mp3", title="One", source=TrackSource.LOCAL)],
        [Track(id=2, path="/tmp/2.mp3", title="Two", source=TrackSource.LOCAL)],
        [Track(id=3, path="/tmp/3.mp3", title="Three", source=TrackSource.LOCAL)],
    ]
    repo = FakePagedTrackRepo(pages)

    class PlaybackEngine:
        def __init__(self):
            self.loaded_items = None

        def load_playlist_items(self, items):
            self.loaded_items = list(items)

        def is_shuffle_mode(self):
            return False

        def play(self):
            return None

    service = PlaybackService.__new__(PlaybackService)
    service._track_repo = repo
    service._engine = PlaybackEngine()
    service._set_source = lambda source: None
    service.LIBRARY_PAGE_SIZE = 2

    monkeypatch.setattr(
        service,
        "_filter_and_convert_tracks",
        lambda tracks: [PlaylistItem.from_track(track) for track in tracks],
    )

    PlaybackService.play_local_library(service)

    assert repo.get_all_calls == [
        (2, 0, None),
        (2, 2, None),
    ]
    assert [item.track_id for item in service._engine.loaded_items] == [1, 2, 3]

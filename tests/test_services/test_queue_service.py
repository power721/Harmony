"""
Tests for queue service edge cases and regressions.
"""

import threading

from domain.playback import PlayMode, PlaybackState
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


class FakeConfigWithBatch(FakeConfig):
    def __init__(self):
        super().__init__()
        self.set_many_calls = []

    def set(self, key, value):
        raise AssertionError("save_queue should prefer set_many when available")

    def set_many(self, pairs):
        self.set_many_calls.append(dict(pairs))
        self.values.update(pairs)


class FakeEngine:
    def __init__(self, items=None, current_index=-1, play_mode=PlayMode.SEQUENTIAL):
        self.playlist_items = list(items or [])
        self.current_index = current_index
        self.play_mode = play_mode


class FakeRestoreEngine(FakeEngine):
    def __init__(self):
        super().__init__(items=[], current_index=-1, play_mode=PlayMode.SEQUENTIAL)
        self.restored_state = None
        self.loaded_track_index = None

    def load_playlist_items(self, items):
        self.playlist_items = list(items)

    def restore_state(self, mode, index):
        self.play_mode = mode
        self.current_index = index
        self.restored_state = (mode, index)

    def load_track_at(self, index):
        self.loaded_track_index = index


class FakeTimer:
    def __init__(self):
        self.stop_called = False

    def stop(self):
        self.stop_called = True


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

    def get_by_id(self, track_id):
        return None

    def get_by_path(self, path):
        return None


class FakeBatchRestoreTrackRepo:
    def __init__(self, track_by_id):
        self._track_by_id = track_by_id
        self.get_by_ids_calls = []

    def get_by_ids(self, track_ids):
        self.get_by_ids_calls.append(list(track_ids))
        return [self._track_by_id[track_id] for track_id in track_ids if track_id in self._track_by_id]

    def get_by_cloud_file_ids(self, cloud_file_ids):
        return {}

    def get_by_paths(self, paths):
        return {}

    def get_by_id(self, track_id):
        raise AssertionError("restore_queue should use batch enrichment, not get_by_id")

    def get_by_cloud_file_id(self, cloud_file_id):
        raise AssertionError("restore_queue should use batch enrichment, not get_by_cloud_file_id")

    def get_by_path(self, path):
        raise AssertionError("restore_queue should use batch enrichment, not get_by_path")


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


def test_queue_service_save_prefers_batch_config_writes():
    """QueueService.save should use set_many when the config supports it."""
    item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=5,
        local_path="/tmp/queue.mp3",
        title="queue",
    )
    repo = FakeQueueRepo()
    config = FakeConfigWithBatch()
    service = QueueService(
        queue_repo=repo,
        config_manager=config,
        engine=FakeEngine(items=[item], current_index=0),
    )

    service.save()

    assert len(config.set_many_calls) == 1
    assert config.values["queue_current_index"] == 0
    assert config.values["queue_play_mode"] == PlayMode.SEQUENTIAL.value


def test_playback_service_save_queue_clears_persisted_state_when_empty():
    """PlaybackService.save_queue should also clear stale queue persistence."""
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine(items=[])
    service._queue_repo = FakeQueueRepo()
    service._config = FakeConfig()

    PlaybackService.save_queue(service)

    assert service._queue_repo.clear_calls == 1
    assert set(service._config.deleted_keys) == {
        "queue_current_index",
        "queue_play_mode",
        "queue_current_track_id",
        "queue_current_cloud_file_id",
        "queue_current_local_path",
    }


def test_playback_service_begin_shutdown_stops_pending_saves():
    """Shutdown should stop pending queue save timer and disable async saves."""
    service = PlaybackService.__new__(PlaybackService)
    service._is_shutting_down = False
    service._pending_save = True
    service._save_queue_timer = FakeTimer()

    PlaybackService.begin_shutdown(service)

    assert service._is_shutting_down is True
    assert service._pending_save is False
    assert service._save_queue_timer.stop_called is True


def test_playback_service_save_queue_skips_after_shutdown_unless_forced():
    """Queue save should be ignored after shutdown, unless explicitly forced."""
    item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=1,
        local_path="/tmp/demo.mp3",
        title="demo",
    )
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine(items=[item], current_index=0)
    service._queue_repo = FakeQueueRepo()
    service._config = FakeConfig()
    service._is_shutting_down = True

    PlaybackService.save_queue(service)
    assert service._queue_repo.saved_items == []
    assert service._config.values == {}

    PlaybackService.save_queue(service, force=True)
    assert len(service._queue_repo.saved_items) == 1
    assert service._config.values["queue_current_index"] == 0


def test_playback_service_on_track_changed_schedules_queue_save():
    """Track switches should schedule queue persistence for restart restore."""
    service = PlaybackService.__new__(PlaybackService)
    service._engine = type("Engine", (), {})()
    service._engine.current_playlist_item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=42,
        local_path="/tmp/demo.mp3",
        title="demo",
    )
    service._engine.state = PlaybackState.PLAYING
    service._engine.play_mode = PlayMode.SEQUENTIAL
    service._event_bus = type("Bus", (), {"emit_track_change": lambda *args, **kwargs: None})()
    service._history_repo = type("History", (), {"add": lambda *args, **kwargs: None})()
    service._track_repo = None
    service._schedule_next_track_preload_called = 0
    service._schedule_save_queue_called = 0

    def _fail_preload():
        raise AssertionError("PlaybackService._on_track_changed did not switch to _schedule_next_track_preload")

    service._preload_next_cloud_track = _fail_preload

    def _schedule_next_preload():
        service._schedule_next_track_preload_called += 1

    def _schedule_save():
        service._schedule_save_queue_called += 1

    service._schedule_next_track_preload = _schedule_next_preload
    service._schedule_save_queue = _schedule_save

    PlaybackService._on_track_changed(service, {"id": 42})

    assert service._schedule_save_queue_called == 1
    assert service._schedule_next_track_preload_called == 1


def test_playback_service_on_track_changed_skips_save_when_stopped():
    """Restore-time track changes in stopped state should not overwrite saved index."""
    service = PlaybackService.__new__(PlaybackService)
    service._engine = type("Engine", (), {})()
    service._engine.current_playlist_item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=7,
        local_path="/tmp/stop.mp3",
        title="stop",
    )
    service._engine.state = PlaybackState.STOPPED
    service._event_bus = type("Bus", (), {"emit_track_change": lambda *args, **kwargs: None})()
    service._history_repo = type("History", (), {"add": lambda *args, **kwargs: None})()
    service._track_repo = None
    service._schedule_next_track_preload_called = 0
    service._schedule_save_queue_called = 0

    def _schedule_next_preload():
        service._schedule_next_track_preload_called += 1

    def _schedule_save():
        service._schedule_save_queue_called += 1

    service._schedule_next_track_preload = _schedule_next_preload
    service._schedule_save_queue = _schedule_save

    PlaybackService._on_track_changed(service, {"id": 7})

    assert service._schedule_save_queue_called == 0
    assert service._schedule_next_track_preload_called == 1


def test_playback_service_save_queue_persists_current_track_identity():
    """Queue save should persist current track identity for robust restore."""
    item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=99,
        local_path="/tmp/keep.mp3",
        title="keep",
    )
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine(items=[item], current_index=0)
    service._queue_repo = FakeQueueRepo()
    service._config = FakeConfig()
    service._is_shutting_down = False

    PlaybackService.save_queue(service)

    assert service._config.values["queue_current_track_id"] == 99
    assert service._config.values["queue_current_cloud_file_id"] == ""
    assert service._config.values["queue_current_local_path"] == "/tmp/keep.mp3"


def test_playback_service_save_queue_prefers_batch_config_writes():
    """Queue save should persist settings with set_many when available."""
    item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=8,
        local_path="/tmp/batch.mp3",
        title="batch",
    )
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeEngine(items=[item], current_index=0)
    service._queue_repo = FakeQueueRepo()
    service._config = FakeConfigWithBatch()
    service._is_shutting_down = False

    PlaybackService.save_queue(service)

    assert len(service._config.set_many_calls) == 1
    assert service._config.values["queue_current_index"] == 0
    assert service._config.values["queue_current_track_id"] == 8
    assert service._config.values["queue_current_local_path"] == "/tmp/batch.mp3"


def test_playback_service_restore_queue_prefers_current_track_identity_over_index():
    """Restore should match saved track identity even if saved index drifts."""
    first = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=1,
        local_path="/tmp/1.mp3",
        title="one",
    )
    second = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=2,
        local_path="/tmp/2.mp3",
        title="two",
    )
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeRestoreEngine()
    service._queue_repo = type(
        "Repo",
        (),
        {"load": lambda self: [first.to_play_queue_item(0), second.to_play_queue_item(1)]},
    )()
    service._track_repo = FakeTrackRepo()
    service._config = type(
        "Cfg",
        (),
        {
            "get": lambda self, key, default=None: {
                "queue_current_index": 1,  # drifted index points to second
                "queue_play_mode": PlayMode.SEQUENTIAL.value,
                "queue_current_track_id": 1,  # identity should win (first)
                "queue_current_cloud_file_id": "",
                "queue_current_local_path": "/tmp/1.mp3",
            }.get(key, default)
        },
    )()
    service._set_source = lambda source: None
    service._cloud_repo = type("CloudRepo", (), {"get_account_by_id": lambda self, _id: None})()
    service._cloud_account = None

    restored = PlaybackService.restore_queue(service)

    assert restored is True
    assert service._engine.current_index == 0
    assert service._engine.loaded_track_index == 0


def test_playback_service_restore_queue_uses_batch_metadata_enrichment():
    """Restore should enrich local queue items using batch repository lookups."""
    queue_item = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=10,
        local_path="/tmp/missing.mp3",
        title="old-title",
    )
    track_repo = FakeBatchRestoreTrackRepo(
        {
            10: Track(
                id=10,
                path="/tmp/missing.mp3",
                title="new-title",
                artist="new-artist",
                album="new-album",
                duration=123.0,
                source=TrackSource.LOCAL,
            )
        }
    )
    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeRestoreEngine()
    service._queue_repo = type(
        "Repo",
        (),
        {"load": lambda self: [queue_item.to_play_queue_item(0)]},
    )()
    service._track_repo = track_repo
    service._config = type(
        "Cfg",
        (),
        {
            "get": lambda self, key, default=None: {
                "queue_current_index": 0,
                "queue_play_mode": PlayMode.SEQUENTIAL.value,
                "queue_current_track_id": 10,
                "queue_current_cloud_file_id": "",
                "queue_current_local_path": "/tmp/missing.mp3",
            }.get(key, default)
        },
    )()
    service._set_source = lambda source: None
    service._cloud_repo = type("CloudRepo", (), {"get_account_by_id": lambda self, _id: None})()
    service._cloud_account = None

    restored = PlaybackService.restore_queue(service)

    assert restored is True
    assert track_repo.get_by_ids_calls == [[10]]
    assert service._engine.playlist_items[0].title == "new-title"
    assert service._engine.playlist_items[0].artist == "new-artist"


def test_playback_service_restore_queue_batch_lookup_deduplicates_ids():
    """Batch metadata enrichment should deduplicate repeated lookup keys."""
    first = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=10,
        local_path="/tmp/missing-1.mp3",
        title="old-1",
    )
    second = PlaylistItem(
        source=TrackSource.LOCAL,
        track_id=10,
        local_path="/tmp/missing-2.mp3",
        title="old-2",
    )
    track_repo = FakeBatchRestoreTrackRepo(
        {
            10: Track(
                id=10,
                path="/tmp/missing-1.mp3",
                title="new-title",
                artist="new-artist",
                album="new-album",
                duration=123.0,
                source=TrackSource.LOCAL,
            )
        }
    )

    service = PlaybackService.__new__(PlaybackService)
    service._engine = FakeRestoreEngine()
    service._queue_repo = type(
        "Repo",
        (),
        {"load": lambda self: [first.to_play_queue_item(0), second.to_play_queue_item(1)]},
    )()
    service._track_repo = track_repo
    service._config = type(
        "Cfg",
        (),
        {
            "get": lambda self, key, default=None: {
                "queue_current_index": 0,
                "queue_play_mode": PlayMode.SEQUENTIAL.value,
                "queue_current_track_id": 10,
                "queue_current_cloud_file_id": "",
                "queue_current_local_path": "/tmp/missing-1.mp3",
            }.get(key, default)
        },
    )()
    service._set_source = lambda source: None
    service._cloud_repo = type("CloudRepo", (), {"get_account_by_id": lambda self, _id: None})()
    service._cloud_account = None

    restored = PlaybackService.restore_queue(service)

    assert restored is True
    assert track_repo.get_by_ids_calls == [[10]]


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

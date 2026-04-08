from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from infrastructure.audio.audio_engine import PlayerEngine


class _FakeBackend:
    def __init__(self):
        self.set_source_calls = []
        self.play_calls = 0
        self._source_path = ""

    def cleanup(self):
        return None

    def set_source(self, path: str):
        self.set_source_calls.append(path)
        self._source_path = path

    def play(self):
        self.play_calls += 1

    def get_source_path(self) -> str:
        return self._source_path

    def is_playing(self) -> bool:
        return False

    def is_paused(self) -> bool:
        return False


class _TrackingLock:
    def __init__(self):
        self._lock = threading.RLock()
        self.depth = 0

    @property
    def is_held(self) -> bool:
        return self.depth > 0

    def __enter__(self):
        self._lock.acquire()
        self.depth += 1
        return self

    def __exit__(self, exc_type, exc, tb):
        self.depth -= 1
        self._lock.release()


def _build_engine_with_item(item: PlaylistItem) -> PlayerEngine:
    engine = PlayerEngine.__new__(PlayerEngine)
    engine._playlist_lock = threading.RLock()
    engine._playlist = [item]
    engine._current_index = 0
    engine._backend = _FakeBackend()
    engine.current_track_changed = SimpleNamespace(emit=lambda _x: None)
    engine._pending_seek = 0
    engine._pending_play = False
    engine._media_loaded_flag = False
    engine._temp_files = []
    return engine


def test_play_after_download_extracts_metadata_outside_playlist_lock(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        file_path = str(Path(tmp) / "song.mp3")
        Path(file_path).write_bytes(b"demo")

        item = PlaylistItem(
            source=TrackSource.QUARK,
            cloud_file_id="fid_3",
            local_path="",
            title="Pending",
            needs_download=True,
            needs_metadata=True,
        )
        engine = _build_engine_with_item(item)
        tracking_lock = _TrackingLock()
        engine._playlist_lock = tracking_lock
        engine.update_track_path = lambda _i, _p: None

        def fake_extract_metadata(_path: str):
            assert tracking_lock.is_held is False
            return {"title": "Resolved", "artist": "Artist", "album": "Album"}

        monkeypatch.setattr(
            "services.metadata.metadata_service.MetadataService.extract_metadata",
            fake_extract_metadata,
        )

        PlayerEngine.play_after_download(engine, 0, file_path)

        assert engine._backend.set_source_calls == [file_path]
        assert engine._pending_play is True

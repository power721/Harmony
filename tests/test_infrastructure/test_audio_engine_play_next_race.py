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
        self.set_source_calls: list[str] = []
        self.play_calls = 0
        self._source_path = ""

    def set_source(self, path: str):
        self.set_source_calls.append(path)
        self._source_path = path

    def play(self):
        self.play_calls += 1

    def cleanup(self):
        return None

    def get_source_path(self) -> str:
        return self._source_path

    def stop(self):
        return None


class _PostUnlockMutatingLock:
    def __init__(self, mutate):
        self._lock = threading.RLock()
        self._mutate = mutate
        self._armed = True

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._lock.release()
        if self._armed:
            self._armed = False
            self._mutate()


def _build_engine(items: list[PlaylistItem], current_index: int) -> PlayerEngine:
    engine = PlayerEngine.__new__(PlayerEngine)
    engine._playlist_lock = threading.RLock()
    engine._playlist = items
    engine._original_playlist = items.copy()
    engine._current_index = current_index
    engine._play_mode = None
    engine._backend = _FakeBackend()
    engine._cloud_file_id_to_index = {}
    engine.current_track_changed = SimpleNamespace(emit=lambda _x: None)
    engine.current_track_pending = SimpleNamespace(emit=lambda _x: None)
    engine.track_needs_download = SimpleNamespace(emit=lambda _x: None)
    engine.error_occurred = SimpleNamespace(emit=lambda _x: None)
    engine.playlist_changed = SimpleNamespace(emit=lambda: None)
    engine._media_loaded_flag = False
    engine._temp_files = []
    return engine


def test_play_next_does_not_load_replaced_next_track_after_unlock():
    with tempfile.TemporaryDirectory() as tmp:
        current_path = str(Path(tmp) / "current.mp3")
        next_path = str(Path(tmp) / "next.mp3")
        replacement_path = str(Path(tmp) / "replacement.mp3")
        Path(current_path).write_bytes(b"current")
        Path(next_path).write_bytes(b"next")
        Path(replacement_path).write_bytes(b"replacement")

        items = [
            PlaylistItem(source=TrackSource.LOCAL, local_path=current_path, title="Current"),
            PlaylistItem(source=TrackSource.LOCAL, local_path=next_path, title="Next"),
        ]
        engine = _build_engine(items, current_index=0)

        def replace_next_track():
            engine._playlist[1] = PlaylistItem(
                source=TrackSource.LOCAL,
                local_path=replacement_path,
                title="Replacement",
            )

        engine._playlist_lock = _PostUnlockMutatingLock(replace_next_track)

        PlayerEngine.play_next(engine)

        assert engine._backend.set_source_calls == []
        assert engine._backend.play_calls == 0

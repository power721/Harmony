"""Regression tests for redundant seek(0) on track load paths."""

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
        self.seek_calls = []
        self.play_calls = 0
        self._source_path = ""

    def cleanup(self):
        return None

    def set_source(self, path: str):
        self.set_source_calls.append(path)
        self._source_path = path

    def seek(self, position_ms: int):
        self.seek_calls.append(position_ms)

    def play(self):
        self.play_calls += 1

    def get_source_path(self) -> str:
        return self._source_path

    def is_playing(self) -> bool:
        return False

    def is_paused(self) -> bool:
        return False


def _build_engine_with_item(item: PlaylistItem) -> PlayerEngine:
    engine = PlayerEngine.__new__(PlayerEngine)
    engine._playlist_lock = threading.RLock()
    engine._playlist = [item]
    engine._current_index = 0
    engine._backend = _FakeBackend()
    engine.current_track_changed = SimpleNamespace(emit=lambda _x: None)
    engine._pending_seek = 0
    engine._pending_play = False
    engine._media_loaded_flag = False  # Add media loaded flag
    return engine


def test_load_track_does_not_force_seek_zero_for_new_source():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = str(Path(tmp) / "song.mp3")
        Path(file_path).write_bytes(b"demo")

        item = PlaylistItem(
            source=TrackSource.QUARK,
            cloud_file_id="fid_1",
            local_path=file_path,
            title="Song",
            needs_download=False,
        )
        engine = _build_engine_with_item(item)

        PlayerEngine._load_track(engine, 0)

        assert engine._backend.set_source_calls == [file_path]
        # Regression guard: set_source already resets to start; no extra seek(0).
        assert engine._backend.seek_calls == []


def test_play_after_download_does_not_force_seek_zero():
    with tempfile.TemporaryDirectory() as tmp:
        file_path = str(Path(tmp) / "song.mp3")
        Path(file_path).write_bytes(b"demo")

        item = PlaylistItem(
            source=TrackSource.QUARK,
            cloud_file_id="fid_2",
            local_path="",
            title="Song",
            needs_download=True,
        )
        engine = _build_engine_with_item(item)
        engine.update_track_path = lambda _i, _p: None

        PlayerEngine.play_after_download(engine, 0, file_path)

        assert engine._backend.set_source_calls == [file_path]
        assert engine._backend.seek_calls == []
        # After fix: play_after_download sets _pending_play instead of calling play directly
        # This prevents race condition where play() is called before media is loaded
        assert engine._pending_play is True
        assert engine._backend.play_calls == 0  # play() not called directly anymore


def test_play_after_download_reloads_when_current_index_already_advanced():
    with tempfile.TemporaryDirectory() as tmp:
        previous_path = str(Path(tmp) / "previous.mp3")
        next_path = str(Path(tmp) / "next.mp3")
        Path(previous_path).write_bytes(b"previous")
        Path(next_path).write_bytes(b"next")

        current_item = PlaylistItem(
            source=TrackSource.QQ,
            cloud_file_id="song_1",
            local_path=previous_path,
            title="Previous",
            needs_download=False,
        )
        next_item = PlaylistItem(
            source=TrackSource.QQ,
            cloud_file_id="song_2",
            local_path="",
            title="Next",
            needs_download=True,
        )

        engine = PlayerEngine.__new__(PlayerEngine)
        engine._playlist_lock = threading.RLock()
        engine._playlist = [current_item, next_item]
        engine._current_index = 1
        engine._backend = _FakeBackend()
        engine._backend._source_path = previous_path
        engine.current_track_changed = SimpleNamespace(emit=lambda _x: None)
        engine._pending_seek = 0
        engine._pending_play = False
        engine._media_loaded_flag = False

        PlayerEngine.play_after_download(engine, 1, next_path)

        assert engine._backend.set_source_calls == [next_path]
        assert engine._pending_play is True


def test_seek_clamps_negative_position_to_zero():
    engine = PlayerEngine.__new__(PlayerEngine)
    engine._backend = _FakeBackend()

    PlayerEngine.seek(engine, -250)

    assert engine._backend.seek_calls == [0]

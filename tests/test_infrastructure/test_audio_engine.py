"""
Tests for PlayerEngine queue update edge cases.
"""

import logging
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from infrastructure.audio.audio_engine import PlayerEngine


def test_update_playlist_item_updates_all_duplicate_cloud_ids():
    """Updating one cloud_file_id should keep duplicate queue entries in sync."""
    engine = PlayerEngine.__new__(PlayerEngine)
    engine._playlist_lock = threading.RLock()
    engine._playlist = [
        PlaylistItem(source=TrackSource.QQ, cloud_file_id="song_mid_123", title="A", needs_download=True),
        PlaylistItem(source=TrackSource.QQ, cloud_file_id="song_mid_123", title="B", needs_download=True),
    ]
    engine._cloud_file_id_to_index = {"song_mid_123": 0}

    updated_index = PlayerEngine.update_playlist_item(
        engine,
        cloud_file_id="song_mid_123",
        local_path="/tmp/downloaded.mp3",
        needs_download=False,
    )

    assert updated_index == 0
    assert engine._playlist[0].local_path == "/tmp/downloaded.mp3"
    assert engine._playlist[0].needs_download is False
    assert engine._playlist[1].local_path == "/tmp/downloaded.mp3"
    assert engine._playlist[1].needs_download is False


class _FakeBackend:
    def __init__(self):
        self.set_source_calls = []
        self.play_calls = 0
        self._source_path = ""

    def set_source(self, path: str):
        self.set_source_calls.append(path)
        self._source_path = path

    def play(self):
        self.play_calls += 1

    def get_source_path(self) -> str:
        return self._source_path


class _SignalRecorder:
    def __init__(self):
        self.calls = []

    def emit(self, payload):
        self.calls.append(payload)


def _build_engine(items: list[PlaylistItem], current_index: int) -> PlayerEngine:
    engine = PlayerEngine.__new__(PlayerEngine)
    engine._playlist_lock = threading.RLock()
    engine._playlist = items
    engine._original_playlist = items.copy()
    engine._current_index = current_index
    engine._play_mode = None
    engine._backend = _FakeBackend()
    engine._cloud_file_id_to_index = {}
    engine.current_track_changed = _SignalRecorder()
    engine.current_track_pending = _SignalRecorder()
    engine.track_needs_download = _SignalRecorder()
    engine.error_occurred = SimpleNamespace(emit=lambda _x: None)
    engine.playlist_changed = SimpleNamespace(emit=lambda: None)
    engine._media_loaded_flag = False
    return engine


def test_play_next_skips_missing_local_track_and_plays_following_track():
    with tempfile.TemporaryDirectory() as tmp:
        current_path = str(Path(tmp) / "current.mp3")
        playable_next_path = str(Path(tmp) / "next.mp3")
        Path(current_path).write_bytes(b"current")
        Path(playable_next_path).write_bytes(b"next")

        items = [
            PlaylistItem(source=TrackSource.LOCAL, local_path=current_path, title="Current"),
            PlaylistItem(source=TrackSource.LOCAL, local_path=str(Path(tmp) / "missing.mp3"), title="Missing"),
            PlaylistItem(source=TrackSource.LOCAL, local_path=playable_next_path, title="Playable"),
        ]
        engine = _build_engine(items, current_index=0)

        PlayerEngine.play_next(engine)

        assert engine.current_index == 2
        assert engine._backend.set_source_calls == [playable_next_path]
        assert engine._backend.play_calls == 1


def test_play_at_emits_pending_signal_for_online_track_needing_download():
    item = PlaylistItem(
        source=TrackSource.QQ,
        cloud_file_id="song_mid_456",
        local_path="",
        title="Pending Song",
        needs_download=True,
    )
    engine = _build_engine([item], current_index=-1)

    PlayerEngine.play_at(engine, 0)

    assert len(engine.current_track_pending.calls) == 1
    assert engine.current_track_pending.calls[0]["cloud_file_id"] == "song_mid_456"
    assert engine.current_track_changed.calls == []
    assert len(engine.track_needs_download.calls) == 1
    assert engine.track_needs_download.calls[0].cloud_file_id == "song_mid_456"


def test_del_logs_backend_cleanup_failure_and_still_cleans_temp_files(caplog):
    """Destructor should continue temp cleanup even if backend cleanup fails."""

    class _FailingBackend:
        def cleanup(self):
            raise RuntimeError("backend cleanup failed")

    engine = PlayerEngine.__new__(PlayerEngine)
    engine._backend = _FailingBackend()
    temp_cleanup_calls = []
    engine.cleanup_temp_files = lambda: temp_cleanup_calls.append("cleaned")

    with caplog.at_level(logging.ERROR, logger="infrastructure.audio.audio_engine"):
        PlayerEngine.__del__(engine)

    assert temp_cleanup_calls == ["cleaned"]
    assert "Error cleaning up backend" in caplog.text

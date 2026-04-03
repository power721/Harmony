"""
Tests for PlayerEngine queue update edge cases.
"""

import threading

from PySide6.QtCore import QObject

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from infrastructure.audio.audio_engine import PlayerEngine


class _FakeSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


def test_update_playlist_item_updates_all_duplicate_cloud_ids():
    """Updating one cloud_file_id should keep duplicate queue entries in sync."""
    engine = PlayerEngine.__new__(PlayerEngine)
    QObject.__init__(engine)
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


def test_engine_reemits_backend_visualizer_frame():
    """PlayerEngine should re-emit backend visualizer frames through its own signal."""
    engine = PlayerEngine.__new__(PlayerEngine)
    QObject.__init__(engine)
    backend = type("BackendStub", (), {})()
    backend.visualizer_frame = _FakeSignal()
    engine._backend = backend

    emitted_frames = []
    engine.visualizer_frame.connect(emitted_frames.append)

    engine._wire_visualizer_signal()

    sample_frame = {"mode": "spectrum", "bins": [0.1, 0.5], "timestamp_ms": 123}
    backend.visualizer_frame.emit(sample_frame)

    assert emitted_frames == [sample_frame]

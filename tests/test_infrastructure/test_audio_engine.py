"""
Tests for PlayerEngine queue update edge cases.
"""

import threading

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

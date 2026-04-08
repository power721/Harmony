"""Regression tests for online download failure handling."""

from __future__ import annotations

import sqlite3
import threading
from unittest.mock import Mock

from domain.playlist_item import PlaylistItem
from domain.track import Track
from domain.track import TrackSource
from services.playback.playback_service import PlaybackService


def test_cloud_download_error_ignores_online_track():
    service = PlaybackService.__new__(PlaybackService)
    online_item = PlaylistItem(
        source=TrackSource.ONLINE,
        online_provider_id="qqmusic",
        cloud_file_id="song_mid_404",
        title="VIP Song",
        needs_download=True,
    )

    service._engine = Mock()
    service._engine.playlist_items = [online_item]
    service._engine.current_playlist_item = online_item
    service._schedule_save_queue = Mock()

    PlaybackService._on_cloud_download_error(service, "song_mid_404", "404 not found")

    service._engine.update_playlist_item.assert_not_called()
    service._engine.play_next.assert_not_called()
    service._schedule_save_queue.assert_not_called()


def test_cloud_download_error_still_handles_real_cloud_track():
    service = PlaybackService.__new__(PlaybackService)
    cloud_item = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="cloud_file_404",
        title="Cloud Song",
        needs_download=True,
    )

    service._engine = Mock()
    service._engine.playlist_items = [cloud_item]
    service._engine.current_playlist_item = cloud_item
    service._schedule_save_queue = Mock()

    PlaybackService._on_cloud_download_error(service, "cloud_file_404", "network error")

    service._engine.update_playlist_item.assert_called_once_with(
        cloud_file_id="cloud_file_404",
        needs_download=True,
        download_failed=True,
    )
    service._engine.play_next.assert_called_once()
    service._schedule_save_queue.assert_called_once()


def test_cleanup_download_workers_stops_running_worker_without_terminate():
    """Worker cleanup should use cooperative stop and avoid force terminate."""
    service = PlaybackService.__new__(PlaybackService)
    worker = Mock()
    worker.isRunning.return_value = True
    worker.wait.return_value = False  # Simulate timeout
    service._online_download_lock = threading.Lock()
    service._online_download_workers = {"song_mid_1": worker}

    from services.playback import playback_service as playback_module
    original_is_valid = playback_module.isValid
    playback_module.isValid = lambda _obj: True
    try:
        PlaybackService.cleanup_download_workers(service)
    finally:
        playback_module.isValid = original_is_valid

    worker.requestInterruption.assert_called_once()
    worker.quit.assert_called_once()
    worker.wait.assert_called_once_with(1000)
    worker.terminate.assert_not_called()
    assert service._online_download_workers == {}


def test_save_online_track_to_library_reuses_existing_path_track_on_unique_conflict(tmp_path):
    service = PlaybackService.__new__(PlaybackService)
    local_path = tmp_path / "song.mp3"
    local_path.write_bytes(b"data")
    playlist_item = PlaylistItem(
        source=TrackSource.ONLINE,
        online_provider_id="qqmusic",
        cloud_file_id="song_mid_123",
        title="Online Song",
        needs_download=True,
    )
    existing_cloud = Track(
        id=1,
        path="online://qqmusic/track/song_mid_123",
        source=TrackSource.ONLINE,
        cloud_file_id="song_mid_123",
        online_provider_id="qqmusic",
    )
    existing_path = Track(
        id=2,
        path=str(local_path),
        title="Cached Song",
        source=TrackSource.LOCAL,
    )

    service._engine = Mock()
    service._engine.playlist_items = [playlist_item]
    service._track_repo = Mock()
    service._track_repo.get_by_cloud_file_id.return_value = existing_cloud
    service._track_repo.update_path.side_effect = sqlite3.IntegrityError("UNIQUE constraint failed: tracks.path")
    service._track_repo.get_by_path.return_value = existing_path
    service._track_repo.update.return_value = True

    track_id = PlaybackService._save_online_track_to_library(
        service,
        "song_mid_123",
        str(local_path),
    )

    assert track_id == 2
    assert existing_path.cloud_file_id == "song_mid_123"
    assert existing_path.online_provider_id == "qqmusic"
    assert existing_path.source == TrackSource.ONLINE
    service._track_repo.update.assert_called_once_with(existing_path)

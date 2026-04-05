"""Regression tests for QQ online download failure handling."""

from __future__ import annotations

import threading
from unittest.mock import Mock

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from services.playback.playback_service import PlaybackService


def test_cloud_download_error_ignores_qq_online_track():
    service = PlaybackService.__new__(PlaybackService)
    qq_item = PlaylistItem(
        source=TrackSource.QQ,
        cloud_file_id="song_mid_404",
        title="VIP Song",
        needs_download=True,
    )

    service._engine = Mock()
    service._engine.playlist_items = [qq_item]
    service._engine.current_playlist_item = qq_item
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

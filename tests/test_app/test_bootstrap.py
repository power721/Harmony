from unittest.mock import MagicMock

import app.bootstrap as bootstrap_module
import services.download.download_manager as download_manager_module


def test_playback_service_wires_download_manager_dependencies(monkeypatch):
    """PlaybackService creation should configure DownloadManager callbacks."""
    fake_playback = object()
    fake_manager = MagicMock()

    monkeypatch.setattr(
        download_manager_module.DownloadManager,
        "instance",
        classmethod(lambda cls: fake_manager),
    )
    monkeypatch.setattr(
        bootstrap_module,
        "PlaybackService",
        MagicMock(return_value=fake_playback),
    )

    bootstrap = bootstrap_module.Bootstrap(":memory:")
    bootstrap._db = object()
    bootstrap._config = object()
    bootstrap._cover_service = object()
    bootstrap._online_download_service = object()
    bootstrap._event_bus = object()
    bootstrap._track_repo = object()
    bootstrap._favorite_repo = object()
    bootstrap._queue_repo = object()
    bootstrap._cloud_repo = object()
    bootstrap._history_repo = object()
    bootstrap._album_repo = object()
    bootstrap._artist_repo = object()

    assert bootstrap.playback_service is fake_playback
    bootstrap_module.PlaybackService.assert_called_once()
    _, kwargs = bootstrap_module.PlaybackService.call_args
    assert "db_manager" not in kwargs

    fake_manager.set_dependencies.assert_called_once_with(
        config=bootstrap._config,
        playback_service=fake_playback,
        cloud_repo=bootstrap._cloud_repo,
    )

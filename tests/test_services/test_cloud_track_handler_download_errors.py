"""CloudTrackHandler download validation regression tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from services.playback.handlers import CloudTrackHandler
import services.playback.handlers as handlers_module


def test_download_track_emits_error_when_cloud_file_is_missing(monkeypatch):
    """Missing cloud file should surface through EventBus instead of failing silently."""
    fake_bus = SimpleNamespace(download_error=SimpleNamespace(emit=Mock()))
    fake_service = SimpleNamespace(
        set_download_dir=Mock(),
        download_file=Mock(),
    )

    monkeypatch.setattr(
        handlers_module.EventBus,
        "instance",
        classmethod(lambda cls: fake_bus),
    )
    monkeypatch.setattr(
        handlers_module.CloudDownloadService,
        "instance",
        classmethod(lambda cls: fake_service),
        raising=False,
    )

    handler = CloudTrackHandler.__new__(CloudTrackHandler)
    handler._cloud_account = SimpleNamespace(id=1)
    handler._cloud_repo = SimpleNamespace(get_file_by_file_id=Mock(return_value=None))
    handler._cloud_files_by_id = {}
    handler._config = SimpleNamespace(get_cloud_download_dir=Mock(return_value="/tmp/cloud"))

    item = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="missing-file",
        title="Missing File",
    )

    CloudTrackHandler.download_track(handler, item)

    fake_bus.download_error.emit.assert_called_once_with(
        "missing-file",
        "CloudFile not found: missing-file",
    )
    fake_service.download_file.assert_not_called()


def test_download_track_emits_error_when_cloud_account_is_missing(monkeypatch):
    """Missing cloud account should also surface through EventBus."""
    fake_bus = SimpleNamespace(download_error=SimpleNamespace(emit=Mock()))
    fake_service = SimpleNamespace(
        set_download_dir=Mock(),
        download_file=Mock(),
    )

    monkeypatch.setattr(
        handlers_module.EventBus,
        "instance",
        classmethod(lambda cls: fake_bus),
    )
    monkeypatch.setattr(
        handlers_module.CloudDownloadService,
        "instance",
        classmethod(lambda cls: fake_service),
        raising=False,
    )

    handler = CloudTrackHandler.__new__(CloudTrackHandler)
    handler._cloud_account = None
    handler._cloud_repo = SimpleNamespace(get_account_by_id=Mock(return_value=None))
    handler._cloud_files_by_id = {}
    handler._config = SimpleNamespace(get_cloud_download_dir=Mock(return_value="/tmp/cloud"))

    item = PlaylistItem(
        source=TrackSource.QUARK,
        cloud_file_id="file-1",
        cloud_account_id=99,
        title="No Account",
    )

    CloudTrackHandler.download_track(handler, item)

    fake_bus.download_error.emit.assert_called_once_with(
        "file-1",
        "No cloud account configured",
    )
    fake_service.download_file.assert_not_called()

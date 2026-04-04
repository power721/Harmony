"""Tests for PlaybackService.scan_directory performance-sensitive behavior."""

from __future__ import annotations

from services.playback.playback_service import PlaybackService
import services.playback.playback_service as playback_module
from services.metadata import MetadataService


class _FakePath:
    def __init__(self):
        self.rglob_calls = []

    def exists(self):
        return True

    def is_dir(self):
        return True

    def rglob(self, pattern):
        self.rglob_calls.append(pattern)
        return []


def test_scan_directory_traverses_tree_once(monkeypatch):
    """Directory scan should do one tree walk and filter by suffix in memory."""
    service = PlaybackService.__new__(PlaybackService)
    service._track_repo = None

    fake_path = _FakePath()
    monkeypatch.setattr(playback_module, "Path", lambda _directory: fake_path)
    monkeypatch.setattr(MetadataService, "SUPPORTED_FORMATS", [".mp3", ".flac"])

    added = PlaybackService.scan_directory(service, "/music")

    assert added == 0
    assert fake_path.rglob_calls == ["*"]

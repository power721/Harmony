"""Architecture tests for LyricsController data access boundaries."""

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.dialogs.lyrics_edit_dialog as lyrics_edit_dialog_module
from ui.windows.components.lyrics_panel import LyricsController
from services.lyrics.lyrics_loader import LyricsDownloadWorker


def test_lyrics_controller_constructor_does_not_require_db_manager():
    """LyricsController should depend on services instead of DatabaseManager."""
    params = inspect.signature(LyricsController.__init__).parameters
    assert "db_manager" not in params


def test_lyrics_controller_download_does_not_accept_cover_flag():
    """Lyrics download flow should no longer expose a cover-download parameter."""
    params = inspect.signature(LyricsController._download_lyrics_for_song).parameters
    assert "download_cover" not in params


def test_lyrics_download_worker_constructor_does_not_accept_cover_dependencies():
    """Lyrics download worker should no longer receive cover-download inputs."""
    params = inspect.signature(LyricsDownloadWorker.__init__).parameters
    assert "download_cover" not in params
    assert "cover_service" not in params


def test_edit_lyrics_reads_local_track_from_library_service(monkeypatch):
    """Editing local-track lyrics should fetch track info via LibraryService."""
    monkeypatch.setattr(
        lyrics_edit_dialog_module.LyricsEditDialog,
        "show_dialog",
        staticmethod(lambda *args, **kwargs: None),
    )
    library_service = SimpleNamespace(
        get_track=MagicMock(return_value=SimpleNamespace(
            path="/tmp/a.mp3",
            title="Song",
            artist="Artist",
        ))
    )
    fake_controller = SimpleNamespace(
        _library_service=library_service,
        _playback=SimpleNamespace(
            engine=SimpleNamespace(current_track={"id": 1}),
            current_track_id=1,
        ),
        _panel=SimpleNamespace(set_lyrics=MagicMock(), set_no_lyrics=MagicMock()),
    )

    LyricsController.edit_lyrics(fake_controller)

    library_service.get_track.assert_called_once_with(1)

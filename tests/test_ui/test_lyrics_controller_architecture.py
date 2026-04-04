"""Architecture tests for LyricsController data access boundaries."""

import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.dialogs.lyrics_edit_dialog as lyrics_edit_dialog_module
from ui.windows.components.lyrics_panel import LyricsController


def test_lyrics_controller_constructor_does_not_require_db_manager():
    """LyricsController should depend on services instead of DatabaseManager."""
    params = inspect.signature(LyricsController.__init__).parameters
    assert "db_manager" not in params


def test_on_cover_downloaded_uses_library_service_instead_of_db():
    """Cover update should query and update tracks through LibraryService."""
    track = SimpleNamespace(id=123)
    library_service = SimpleNamespace(
        get_track_by_path=MagicMock(return_value=track),
        update_track_cover_path=MagicMock(return_value=True),
    )
    current_item = SimpleNamespace(track_id=None, local_path="/tmp/a.mp3", cover_path=None)
    fake_controller = SimpleNamespace(
        _lyrics_download_path="/tmp/a.mp3",
        _library_service=library_service,
        _playback=SimpleNamespace(current_track=current_item),
        _event_bus=SimpleNamespace(metadata_updated=SimpleNamespace(emit=MagicMock())),
        cover_downloaded=SimpleNamespace(emit=MagicMock()),
    )

    LyricsController._on_cover_downloaded(fake_controller, "/tmp/cover.jpg")

    library_service.get_track_by_path.assert_called_once_with("/tmp/a.mp3")
    library_service.update_track_cover_path.assert_called_once_with(123, "/tmp/cover.jpg")


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

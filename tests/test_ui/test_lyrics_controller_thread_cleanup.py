"""LyricsController thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.windows.components.lyrics_panel as lyrics_panel_module
from ui.windows.components.lyrics_panel import LyricsController


def test_stop_lyrics_loader_thread_uses_cooperative_shutdown(monkeypatch):
    """Lyrics loader stop should avoid force terminate."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    fake = SimpleNamespace(_lyrics_thread=fake_thread)
    monkeypatch.setattr(lyrics_panel_module, "isValid", lambda _obj: True)

    LyricsController._stop_lyrics_loader_thread(fake, wait_ms=250, cleanup_signals=False)

    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(250)
    fake_thread.terminate.assert_not_called()


def test_stop_lyrics_download_thread_cleanup_disconnects_and_clears_reference(monkeypatch):
    """Download thread cleanup should disconnect, delete, and clear reference."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=False),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(),
        finished=SimpleNamespace(disconnect=MagicMock()),
        lyrics_downloaded=SimpleNamespace(disconnect=MagicMock()),
        download_failed=SimpleNamespace(disconnect=MagicMock()),
        cover_downloaded=SimpleNamespace(disconnect=MagicMock()),
        deleteLater=MagicMock(),
    )
    fake = SimpleNamespace(_lyrics_download_thread=fake_thread)
    monkeypatch.setattr(lyrics_panel_module, "isValid", lambda _obj: True)

    LyricsController._stop_lyrics_download_thread(fake, wait_ms=1000, cleanup_signals=True)

    fake_thread.finished.disconnect.assert_called_once()
    fake_thread.lyrics_downloaded.disconnect.assert_called_once()
    fake_thread.download_failed.disconnect.assert_called_once()
    fake_thread.cover_downloaded.disconnect.assert_called_once()
    fake_thread.deleteLater.assert_called_once()
    assert fake._lyrics_download_thread is None

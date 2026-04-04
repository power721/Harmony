"""MiniPlayer thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.windows.mini_player as mini_player_module
from ui.windows.mini_player import MiniPlayer


def test_stop_lyrics_thread_uses_cooperative_shutdown(monkeypatch):
    """Stopping lyrics thread should not force-terminate the QThread."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=True),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        terminate=MagicMock(),
    )
    fake = SimpleNamespace(_lyrics_thread=fake_thread)
    monkeypatch.setattr(mini_player_module, "isValid", lambda _obj: True)

    MiniPlayer._stop_lyrics_thread(fake, wait_ms=250, cleanup_signals=False)

    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(250)
    fake_thread.terminate.assert_not_called()


def test_stop_lyrics_thread_cleanup_disconnects_and_clears_reference(monkeypatch):
    """Cleanup mode should disconnect signals, delete thread, and clear reference."""
    fake_thread = SimpleNamespace(
        isRunning=MagicMock(return_value=False),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(),
        finished=SimpleNamespace(disconnect=MagicMock()),
        lyrics_ready=SimpleNamespace(disconnect=MagicMock()),
        deleteLater=MagicMock(),
    )
    fake = SimpleNamespace(_lyrics_thread=fake_thread)
    monkeypatch.setattr(mini_player_module, "isValid", lambda _obj: True)

    MiniPlayer._stop_lyrics_thread(fake, wait_ms=1000, cleanup_signals=True)

    fake_thread.finished.disconnect.assert_called_once()
    fake_thread.lyrics_ready.disconnect.assert_called_once()
    fake_thread.deleteLater.assert_called_once()
    assert fake._lyrics_thread is None

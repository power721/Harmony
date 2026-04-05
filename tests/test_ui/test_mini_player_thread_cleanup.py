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


def test_on_cover_loaded_ignores_stale_result():
    """Stale cover result should be ignored based on version token."""
    fake = SimpleNamespace(
        _cover_load_version=3,
        _cover_thread=object(),
        _show_cover=MagicMock(),
    )

    MiniPlayer._on_cover_loaded(fake, "/tmp/stale.jpg", 2)

    fake._show_cover.assert_not_called()
    assert fake._cover_thread is not None


def test_on_cover_loaded_applies_current_result():
    """Current cover result should be applied and clear worker reference."""
    fake = SimpleNamespace(
        _cover_load_version=4,
        _cover_thread=object(),
        _show_cover=MagicMock(),
    )

    MiniPlayer._on_cover_loaded(fake, "/tmp/current.jpg", 4)

    fake._show_cover.assert_called_once_with("/tmp/current.jpg")
    assert fake._cover_thread is None


def test_invalidate_cover_load_bumps_version_and_clears_thread():
    """Invalidating cover load should reject pending results and drop thread ref."""
    fake = SimpleNamespace(
        _cover_load_version=5,
        _cover_thread=object(),
    )

    MiniPlayer._invalidate_cover_load(fake)

    assert fake._cover_load_version == 6
    assert fake._cover_thread is None


def test_close_event_invalidates_cover_and_cleans_lyrics():
    """Closing MiniPlayer should invalidate cover work and cleanup lyrics thread."""
    event = SimpleNamespace(accept=MagicMock())
    fake = SimpleNamespace(
        _invalidate_cover_load=MagicMock(),
        _stop_lyrics_thread=MagicMock(),
        closed=SimpleNamespace(emit=MagicMock()),
    )

    MiniPlayer.closeEvent(fake, event)

    fake._invalidate_cover_load.assert_called_once_with()
    fake._stop_lyrics_thread.assert_called_once_with(wait_ms=1000, cleanup_signals=True)
    fake.closed.emit.assert_called_once_with()
    event.accept.assert_called_once_with()

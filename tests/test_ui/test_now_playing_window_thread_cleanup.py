"""NowPlayingWindow thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.windows.now_playing_window as now_playing_module
from ui.windows.now_playing_window import NowPlayingWindow


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
    monkeypatch.setattr(now_playing_module, "isValid", lambda _obj: True)

    NowPlayingWindow._stop_lyrics_thread(fake, wait_ms=300, cleanup_signals=False)

    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(300)
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
    monkeypatch.setattr(now_playing_module, "isValid", lambda _obj: True)

    NowPlayingWindow._stop_lyrics_thread(fake, wait_ms=1000, cleanup_signals=True)

    fake_thread.finished.disconnect.assert_called_once()
    fake_thread.lyrics_ready.disconnect.assert_called_once()
    fake_thread.deleteLater.assert_called_once()
    assert fake._lyrics_thread is None


def test_invalidate_cover_load_bumps_version_and_clears_thread():
    """Invalidating cover load should reject pending results and drop thread ref."""
    fake = SimpleNamespace(
        _cover_load_version=2,
        _cover_thread=object(),
    )

    NowPlayingWindow._invalidate_cover_load(fake)

    assert fake._cover_load_version == 3
    assert fake._cover_thread is None


def test_close_event_invalidates_cover_saves_settings_and_cleans_lyrics():
    """Closing now-playing should save state, invalidate cover, and stop lyrics thread."""
    event = SimpleNamespace(accept=MagicMock())
    fake = SimpleNamespace(
        _save_window_settings=MagicMock(),
        _invalidate_cover_load=MagicMock(),
        _disconnect_runtime_signals=MagicMock(),
        _stop_lyrics_thread=MagicMock(),
        closed=SimpleNamespace(emit=MagicMock()),
    )

    NowPlayingWindow.closeEvent(fake, event)

    fake._save_window_settings.assert_called_once_with()
    fake._invalidate_cover_load.assert_called_once_with()
    fake._disconnect_runtime_signals.assert_called_once_with()
    fake._stop_lyrics_thread.assert_called_once_with(wait_ms=800, cleanup_signals=True)
    fake.closed.emit.assert_called_once_with()
    event.accept.assert_called_once_with()


def _make_runtime_signal_owner():
    engine = SimpleNamespace(
        current_track_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
        current_track_pending=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
        position_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
        duration_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
        state_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
        play_mode_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
        volume_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock()),
    )
    bus = SimpleNamespace(
        favorite_changed=SimpleNamespace(connect=MagicMock(), disconnect=MagicMock())
    )
    fake = SimpleNamespace(
        _playback=SimpleNamespace(engine=engine),
        _runtime_signals_connected=False,
        _on_track_changed=object(),
        _on_pending_track_changed=object(),
        _on_position_changed=object(),
        _on_duration_changed=object(),
        _on_state_changed=object(),
        _on_play_mode_changed=object(),
        _on_volume_changed_from_engine=object(),
        _on_favorite_changed=object(),
    )
    return fake, engine, bus


def test_connect_runtime_signals_is_idempotent(monkeypatch):
    """Reusable now-playing windows should not duplicate runtime signal subscriptions."""
    fake, engine, bus = _make_runtime_signal_owner()
    monkeypatch.setattr(now_playing_module.EventBus, "instance", lambda: bus)

    NowPlayingWindow._connect_runtime_signals(fake)
    NowPlayingWindow._connect_runtime_signals(fake)

    assert fake._runtime_signals_connected is True
    assert engine.current_track_changed.connect.call_count == 1
    assert engine.current_track_pending.connect.call_count == 1
    assert engine.position_changed.connect.call_count == 1
    assert engine.duration_changed.connect.call_count == 1
    assert engine.state_changed.connect.call_count == 1
    assert engine.play_mode_changed.connect.call_count == 1
    assert engine.volume_changed.connect.call_count == 1
    assert bus.favorite_changed.connect.call_count == 1


def test_disconnect_runtime_signals_is_idempotent(monkeypatch):
    """Reusable now-playing windows should only disconnect owned runtime signals once."""
    fake, engine, bus = _make_runtime_signal_owner()
    fake._runtime_signals_connected = True
    monkeypatch.setattr(now_playing_module.EventBus, "instance", lambda: bus)

    NowPlayingWindow._disconnect_runtime_signals(fake)
    NowPlayingWindow._disconnect_runtime_signals(fake)

    assert fake._runtime_signals_connected is False
    assert engine.current_track_changed.disconnect.call_count == 1
    assert engine.current_track_pending.disconnect.call_count == 1
    assert engine.position_changed.disconnect.call_count == 1
    assert engine.duration_changed.disconnect.call_count == 1
    assert engine.state_changed.disconnect.call_count == 1
    assert engine.play_mode_changed.disconnect.call_count == 1
    assert engine.volume_changed.disconnect.call_count == 1
    assert bus.favorite_changed.disconnect.call_count == 1

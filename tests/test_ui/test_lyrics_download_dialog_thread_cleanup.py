"""LyricsDownloadDialog thread cleanup behavior tests."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import ui.dialogs.lyrics_download_dialog as dialog_module
from ui.dialogs.lyrics_download_dialog import LyricsDownloadDialog


def _make_fake_thread(**attrs):
    class FakeThread:
        pass

    thread = FakeThread()
    for name, value in attrs.items():
        setattr(thread, name, value)
    return thread


def test_stop_search_thread_detaches_running_thread_from_dialog(monkeypatch):
    """Closing with an active search thread should detach it from the dialog lifecycle."""
    fake_thread = _make_fake_thread(
        isRunning=MagicMock(side_effect=[True, True]),
        cancel=MagicMock(),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(return_value=False),
        search_completed=SimpleNamespace(disconnect=MagicMock()),
        search_failed=SimpleNamespace(disconnect=MagicMock()),
        search_progress=SimpleNamespace(disconnect=MagicMock()),
        finished=SimpleNamespace(disconnect=MagicMock()),
        deleteLater=MagicMock(),
    )
    fake = SimpleNamespace(
        _search_thread=fake_thread,
        _on_search_completed=MagicMock(),
        _on_search_failed=MagicMock(),
        _on_search_progress=MagicMock(),
        _on_search_thread_finished=MagicMock(),
    )
    monkeypatch.setattr(dialog_module, "isValid", lambda _obj: True)
    dialog_module._ACTIVE_LYRICS_SEARCH_THREADS.clear()

    LyricsDownloadDialog._stop_search_thread(fake, wait_ms=250, cleanup_signals=True)

    fake_thread.cancel.assert_called_once()
    fake_thread.requestInterruption.assert_called_once()
    fake_thread.quit.assert_called_once()
    fake_thread.wait.assert_called_once_with(250)
    fake_thread.search_completed.disconnect.assert_called_once()
    fake_thread.search_failed.disconnect.assert_called_once()
    fake_thread.search_progress.disconnect.assert_called_once()
    fake_thread.finished.disconnect.assert_called_once()
    fake_thread.deleteLater.assert_not_called()
    assert fake._search_thread is None
    assert fake_thread in dialog_module._ACTIVE_LYRICS_SEARCH_THREADS


def test_stop_search_thread_cleans_up_finished_thread(monkeypatch):
    """Finished search threads should be deleted immediately and not retained."""
    fake_thread = _make_fake_thread(
        isRunning=MagicMock(return_value=False),
        cancel=MagicMock(),
        requestInterruption=MagicMock(),
        quit=MagicMock(),
        wait=MagicMock(),
        search_completed=SimpleNamespace(disconnect=MagicMock()),
        search_failed=SimpleNamespace(disconnect=MagicMock()),
        search_progress=SimpleNamespace(disconnect=MagicMock()),
        finished=SimpleNamespace(disconnect=MagicMock()),
        deleteLater=MagicMock(),
    )
    fake = SimpleNamespace(
        _search_thread=fake_thread,
        _on_search_completed=MagicMock(),
        _on_search_failed=MagicMock(),
        _on_search_progress=MagicMock(),
        _on_search_thread_finished=MagicMock(),
    )
    monkeypatch.setattr(dialog_module, "isValid", lambda _obj: True)
    dialog_module._ACTIVE_LYRICS_SEARCH_THREADS.clear()

    LyricsDownloadDialog._stop_search_thread(fake, wait_ms=250, cleanup_signals=True)

    fake_thread.cancel.assert_not_called()
    fake_thread.requestInterruption.assert_not_called()
    fake_thread.quit.assert_not_called()
    fake_thread.wait.assert_not_called()
    fake_thread.search_completed.disconnect.assert_called_once()
    fake_thread.search_failed.disconnect.assert_called_once()
    fake_thread.search_progress.disconnect.assert_called_once()
    fake_thread.finished.disconnect.assert_called_once()
    fake_thread.deleteLater.assert_called_once()
    assert fake._search_thread is None
    assert fake_thread not in dialog_module._ACTIVE_LYRICS_SEARCH_THREADS

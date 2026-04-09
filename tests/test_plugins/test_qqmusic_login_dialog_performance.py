from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.login_dialog import QQMusicLoginDialog


def test_restart_login_stops_previous_thread_without_waiting():
    dialog = QQMusicLoginDialog.__new__(QQMusicLoginDialog)
    old_thread = Mock()
    dialog._login_thread = old_thread
    dialog._retired_login_threads = []
    dialog._start_login = Mock()

    QQMusicLoginDialog._restart_login(dialog)

    old_thread.stop.assert_called_once_with()
    old_thread.wait.assert_not_called()
    dialog._start_login.assert_called_once_with()
    assert dialog._retired_login_threads == [old_thread]


def test_dispatch_thread_event_ignores_stale_thread():
    dialog = QQMusicLoginDialog.__new__(QQMusicLoginDialog)
    active_thread = object()
    stale_thread = object()
    callback = Mock()
    dialog._login_thread = active_thread

    assert (
        QQMusicLoginDialog._dispatch_thread_event(
            dialog,
            stale_thread,
            callback,
            "stale-value",
        )
        is False
    )
    callback.assert_not_called()

    assert (
        QQMusicLoginDialog._dispatch_thread_event(
            dialog,
            active_thread,
            callback,
            "fresh-value",
        )
        is True
    )
    callback.assert_called_once_with("fresh-value")

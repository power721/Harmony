"""Focus behavior tests for OnlineMusicView search input."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from plugins.builtin.qqmusic.lib.online_music_view import OnlineMusicView
from tests.test_plugins.qqmusic_test_context import bind_test_context


def test_click_outside_search_input_clears_focus(qtbot):
    """Clicking outside search input should clear its focus."""
    theme_manager = MagicMock()
    theme_manager.get_qss.side_effect = lambda qss: qss
    theme_manager.register_widget = MagicMock()
    theme_manager.current_theme = MagicMock(highlight="#1db954")

    with patch("system.theme.ThemeManager.instance", return_value=theme_manager):
        context = bind_test_context(theme_manager=theme_manager)
        view = OnlineMusicView(config_manager=None, qqmusic_service=None, plugin_context=context)
        view._top_lists_loaded = True  # Avoid loading top list workers in this test.
        qtbot.addWidget(view)
        view.show()
        view.raise_()
        view.activateWindow()
        qtbot.waitExposed(view)

        view._search_input.setFocus(Qt.OtherFocusReason)
        qtbot.waitUntil(lambda: view._search_input.hasFocus())

        qtbot.mouseClick(view._stack, Qt.LeftButton)

        qtbot.waitUntil(lambda: not view._search_input.hasFocus())
        assert view._tabs.cursor().shape() == Qt.PointingHandCursor


def test_ranking_track_activation_plays_selected_track():
    """Ranking list activation should play the whole current list from the selected track."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    track_a = SimpleNamespace(mid="a", title="Song A")
    track_b = SimpleNamespace(mid="b", title="Song B")
    emitted = []
    view._current_tracks = [track_a, track_b]
    view.play_online_tracks = SimpleNamespace(
        emit=lambda start_index, tracks: emitted.append((start_index, tracks))
    )
    view._build_tracks_payload = lambda tracks: [(track.mid, {}) for track in tracks]

    OnlineMusicView._on_ranking_track_activated(view, track_b)

    assert emitted == [(1, [("a", {}), ("b", {})])]


def test_play_selected_tracks_plays_current_list_from_first_selected_track():
    """Play should use the full current list and start from the first selected song."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    track_a = SimpleNamespace(mid="a", title="Song A")
    track_b = SimpleNamespace(mid="b", title="Song B")
    track_c = SimpleNamespace(mid="c", title="Song C")
    emitted = []
    view._current_tracks = [track_a, track_b, track_c]
    view.play_online_tracks = SimpleNamespace(
        emit=lambda start_index, tracks: emitted.append((start_index, tracks))
    )
    view._build_tracks_payload = lambda tracks: [(track.mid, {}) for track in tracks]

    OnlineMusicView._play_selected_tracks(view, [track_b, track_c])

    assert emitted == [(1, [("a", {}), ("b", {}), ("c", {})])]


def test_search_result_double_click_plays_current_list_from_clicked_row():
    """Search result activation should play the whole current list from the clicked row."""
    view = OnlineMusicView.__new__(OnlineMusicView)
    track_a = SimpleNamespace(mid="a", title="Song A")
    track_b = SimpleNamespace(mid="b", title="Song B")
    emitted = []
    view._current_tracks = [track_a, track_b]
    view._is_top_list_view = False
    view.play_online_tracks = SimpleNamespace(
        emit=lambda start_index, tracks: emitted.append((start_index, tracks))
    )
    view._build_tracks_payload = lambda tracks: [(track.mid, {}) for track in tracks]

    OnlineMusicView._on_track_double_clicked(view, SimpleNamespace(row=lambda: 1))

    assert emitted == [(1, [("a", {}), ("b", {})])]

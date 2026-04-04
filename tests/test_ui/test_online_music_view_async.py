"""Async request coordination tests for OnlineMusicView."""

from unittest.mock import Mock

from domain.online_music import OnlineTrack, SearchResult, SearchType
from ui.views.online_music_view import OnlineMusicView


def _make_view_for_search_callbacks():
    view = OnlineMusicView.__new__(OnlineMusicView)
    view._search_request_id = 0
    view._current_search_type = SearchType.SONG
    view._current_page = 1
    view._current_result = None
    view._current_tracks = []
    view._stack = Mock()
    view._results_page = object()
    view._results_stack = Mock()
    view._songs_page = object()
    view._singers_page = object()
    view._albums_page = object()
    view._playlists_page = object()
    view._results_info = Mock()
    view._page_label = Mock()
    view._prev_btn = Mock()
    view._next_btn = Mock()
    view._display_tracks = Mock()
    view._display_artists = Mock()
    view._display_albums = Mock()
    view._display_playlists = Mock()
    return view


def test_stale_search_completion_is_ignored():
    """Older search results should not overwrite the UI after a newer request starts."""
    view = _make_view_for_search_callbacks()
    view._search_request_id = 2
    stale_result = SearchResult(
        keyword="old",
        search_type=SearchType.SONG,
        tracks=[OnlineTrack(mid="old", title="Old Song")],
        total=1,
    )

    OnlineMusicView._on_search_completed(view, stale_result, 1)

    assert view._current_result is None
    assert view._current_tracks == []
    view._display_tracks.assert_not_called()
    view._stack.setCurrentWidget.assert_not_called()


def test_current_search_completion_updates_ui():
    """Current search results should still update the UI normally."""
    view = _make_view_for_search_callbacks()
    view._search_request_id = 3
    result = SearchResult(
        keyword="new",
        search_type=SearchType.SONG,
        tracks=[OnlineTrack(mid="new", title="New Song")],
        total=1,
    )

    OnlineMusicView._on_search_completed(view, result, 3)

    assert view._current_result is result
    assert view._current_tracks == result.tracks
    view._display_tracks.assert_called_once_with(result.tracks)
    view._stack.setCurrentWidget.assert_called_once_with(view._results_page)

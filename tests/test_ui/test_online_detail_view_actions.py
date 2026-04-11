"""Tests for OnlineDetailView action button visibility based on page count."""

import os
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager
from plugins.builtin.qqmusic.lib.online_detail_view import OnlineDetailView
from tests.test_plugins.qqmusic_test_context import bind_test_context


def _app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _init_theme_manager():
    ThemeManager._instance = None
    config = MagicMock()
    config.get.return_value = "dark"
    ThemeManager.instance(config)


def _create_detail_view(*, logged_in: bool) -> OnlineDetailView:
    _app()
    _init_theme_manager()
    context = bind_test_context()
    if logged_in:
        context.settings.set("credential", {"musicid": "1", "musickey": "secret"})
    view = OnlineDetailView()
    view._load_detail = MagicMock()
    return view


def test_all_actions_hidden_when_only_one_page():
    """All-pages action buttons should be hidden when there is only one page."""
    _app()
    _init_theme_manager()
    bind_test_context()
    view = OnlineDetailView()

    view._total_pages = 1
    view._update_pagination()

    assert view._play_all_btn.isHidden()
    assert view._insert_all_queue_btn.isHidden()
    assert view._add_all_queue_btn.isHidden()


def test_all_actions_visible_when_multiple_pages():
    """All-pages action buttons should be visible when there are multiple pages."""
    _app()
    _init_theme_manager()
    bind_test_context()
    view = OnlineDetailView()

    view._total_pages = 1
    view._update_pagination()
    view._total_pages = 2
    view._update_pagination()

    assert not view._play_all_btn.isHidden()
    assert not view._insert_all_queue_btn.isHidden()
    assert not view._add_all_queue_btn.isHidden()


def test_play_tracks_plays_current_page_from_first_selected_track():
    """Detail view play should use the full current page starting at the first selected track."""
    view = OnlineDetailView.__new__(OnlineDetailView)
    track_a = SimpleNamespace(mid="a", title="Song A")
    track_b = SimpleNamespace(mid="b", title="Song B")
    track_c = SimpleNamespace(mid="c", title="Song C")
    emitted = []
    view._tracks = [track_a, track_b, track_c]
    view.play_all = SimpleNamespace(
        emit=lambda tracks, index: emitted.append((tracks, index))
    )

    OnlineDetailView._play_tracks(view, [track_b, track_c])

    assert emitted == [([track_a, track_b, track_c], 1)]


def test_parse_songs_keeps_album_mid_for_flat_search_payload():
    """Album detail fallback search payload should still preserve album MID for cover resolution."""
    view = OnlineDetailView.__new__(OnlineDetailView)

    tracks = OnlineDetailView._parse_songs(
        view,
        [
            {
                "mid": "song-1",
                "title": "Song 1",
                "artist": "Singer 1",
                "singer": "Singer 1",
                "album": "Album 1",
                "album_mid": "album-1",
                "duration": 180,
            }
        ],
    )

    assert len(tracks) == 1
    assert tracks[0].album is not None
    assert tracks[0].album.name == "Album 1"
    assert tracks[0].album.mid == "album-1"


@pytest.mark.parametrize(
    ("loader_name", "args"),
    [
        ("load_artist", ("artist-1", "Artist 1")),
        ("load_album", ("album-1", "Album 1", "Singer 1")),
        ("load_playlist", ("playlist-1", "Playlist 1", "User 1")),
    ],
)
def test_detail_actions_hidden_when_not_logged_in(loader_name, args):
    """Unauthenticated detail pages should not show QQ social action buttons."""
    view = _create_detail_view(logged_in=False)

    getattr(view, loader_name)(*args)

    assert view._follow_btn.isHidden()
    assert view._fav_btn.isHidden()


def test_artist_follow_button_visible_when_logged_in():
    """Logged-in artist detail should still show the follow button."""
    view = _create_detail_view(logged_in=True)
    view.show()
    _app().processEvents()

    view.load_artist("artist-1", "Artist 1")
    _app().processEvents()

    assert view._follow_btn.isVisibleTo(view)
    assert view._fav_btn.isHidden()


def test_online_detail_view_cover_click_uses_shared_preview(monkeypatch):
    """Cover clicks should use the shared preview dialog with upgraded QQ cover URLs."""
    calls = []

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_detail_view.show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = OnlineDetailView.__new__(OnlineDetailView)
    view._cover_url = "https://y.gtimg.cn/music/photo_new/T002R300x300M000albummid.jpg"
    view._name_label = SimpleNamespace(text=lambda: "Album Name")

    OnlineDetailView._on_cover_clicked(view, None)

    assert calls == [
        (
            view,
            "https://y.gtimg.cn/music/photo_new/T002R800x800M000albummid.jpg",
            "Album Name",
            None,
        )
    ]


@pytest.mark.parametrize(
    ("source_url", "expected_url"),
    [
        (
            "https://y.gtimg.cn/music/photo_new/T002R500x500M000albummid.jpg",
            "https://y.gtimg.cn/music/photo_new/T002R800x800M000albummid.jpg",
        ),
        (
            "https://y.qq.com/music/photo_new/T002R300x300M000albummid.jpg",
            "https://y.qq.com/music/photo_new/T002R800x800M000albummid.jpg",
        ),
    ],
)
def test_online_detail_view_cover_click_upgrades_more_qq_cover_url_variants(
    monkeypatch,
    source_url,
    expected_url,
):
    """QQ cover clicks should normalize multiple photo_new URL variants to 800px previews."""
    calls = []

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_detail_view.show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = OnlineDetailView.__new__(OnlineDetailView)
    view._cover_url = source_url
    view._name_label = SimpleNamespace(text=lambda: "Album Name")

    OnlineDetailView._on_cover_clicked(view, None)

    assert len(calls) == 1
    assert calls[0][1] == expected_url
    assert calls[0][2] == "Album Name"
    assert calls[0][3] is None

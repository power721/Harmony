from types import SimpleNamespace
from unittest.mock import MagicMock

from domain.playback import PlaybackState
from ui.windows.main_window import MainWindow
from ui.windows.mini_player import MiniPlayer
from ui.windows.now_playing_window import NowPlayingWindow


def test_main_window_track_change_updates_window_title_immediately():
    fake = SimpleNamespace()
    fake._library_view = SimpleNamespace(_select_track_by_id=MagicMock())
    fake._queue_view = SimpleNamespace(_select_track_by_id=MagicMock())
    fake._lyrics_controller = None
    fake._lyrics_panel = SimpleNamespace(set_no_lyrics=MagicMock())
    fake._title_bar = SimpleNamespace(
        set_track_title=MagicMock(),
        clear_track_title=MagicMock(),
        clear_accent_color=MagicMock(),
    )
    fake._extract_cover_color = MagicMock()
    fake.setWindowTitle = MagicMock()
    fake._current_track_title = ""

    MainWindow._on_track_changed(
        fake,
        {
            "id": 1,
            "title": "Next Song",
            "artist": "Singer",
            "path": "/tmp/next.mp3",
        },
    )

    fake.setWindowTitle.assert_called_once_with("Next Song - Singer")


def test_now_playing_track_change_updates_window_title_even_if_state_not_playing():
    fake = SimpleNamespace()
    fake._playback = SimpleNamespace(state=PlaybackState.STOPPED)
    fake._progress_slider = SimpleNamespace(setValue=MagicMock())
    fake._current_time = SimpleNamespace(setText=MagicMock())
    fake._total_time = SimpleNamespace(setText=MagicMock())
    fake._track_title = SimpleNamespace(setText=MagicMock())
    fake._track_artist = SimpleNamespace(setText=MagicMock())
    fake._track_album = SimpleNamespace(setText=MagicMock())
    fake._lyrics_widget = SimpleNamespace(set_lyrics=MagicMock())
    fake._set_default_cover = MagicMock()
    fake._load_cover_async = MagicMock()
    fake._load_lyrics_async = MagicMock()
    fake._update_favorite_state = MagicMock()
    fake.setWindowTitle = MagicMock()
    fake._current_track_title = ""
    fake._current_cover_path = ""

    NowPlayingWindow._on_track_changed(
        fake,
        {
            "title": "Another Song",
            "artist": "Another Artist",
            "album": "Album",
        },
    )

    fake.setWindowTitle.assert_called_once_with("Another Song - Another Artist")


def test_mini_player_track_change_updates_window_title_even_if_state_not_playing():
    fake = SimpleNamespace()
    fake._playback = None
    fake._player = SimpleNamespace(engine=SimpleNamespace(state=PlaybackState.STOPPED))
    fake._title_label = SimpleNamespace(setText=MagicMock())
    fake._artist_label = SimpleNamespace(setText=MagicMock())
    fake._album_label = SimpleNamespace(setText=MagicMock())
    fake._set_elided_text = MagicMock()
    fake._load_cover_async = MagicMock()
    fake._load_lyrics_async = MagicMock()
    fake.setWindowTitle = MagicMock()
    fake._current_track_title = ""

    MiniPlayer._on_track_changed(
        fake,
        {
            "title": "Mini Song",
            "artist": "Mini Artist",
            "album": "Mini Album",
        },
    )

    fake.setWindowTitle.assert_called_once_with("Mini Song - Mini Artist")


def test_normalize_restore_position_resets_when_near_track_end():
    # 120s track, saved at 119.5s should reset to 0 to avoid instant auto-next
    assert MainWindow._normalize_restore_position(119500, 120.0) == 0


def test_normalize_restore_position_keeps_regular_middle_position():
    # 120s track, saved at 40s should be preserved
    assert MainWindow._normalize_restore_position(40000, 120.0) == 40000

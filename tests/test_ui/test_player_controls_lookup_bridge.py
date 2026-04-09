"""Tests for PlayerControls lookup APIs without direct db access."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from ui.widgets.player_controls import PlayerControls


class _DummyLabel:
    def __init__(self):
        self.text = None

    def setText(self, text):
        self.text = text


class _DummyArtistWidget:
    def __init__(self):
        self.artists = None

    def set_artists(self, artists):
        self.artists = artists


def _make_controls(player):
    controls = PlayerControls.__new__(PlayerControls)
    controls._player = player
    controls._title_label = _DummyLabel()
    controls._artist_widget = _DummyArtistWidget()
    controls._cover_load_version = 0
    controls._load_cover_art_async = Mock()
    controls._cover_label = SimpleNamespace(clear=Mock())
    controls._current_cover_path = "/covers/current.jpg"
    return controls


def test_on_metadata_updated_uses_player_lookup_method_without_db():
    track = SimpleNamespace(
        id=7,
        path="/music/song.mp3",
        title="Song",
        artist="Artist",
        album="Album",
        duration=180.0,
        cover_path="/covers/song.jpg",
    )
    player = SimpleNamespace(
        engine=SimpleNamespace(current_track={"id": None, "path": "/music/song.mp3"}),
        get_track_by_path=Mock(return_value=track),
    )
    controls = _make_controls(player)

    with patch("ui.widgets.player_controls.QTimer.singleShot", side_effect=lambda _delay, callback: callback()):
        controls._on_metadata_updated(7)

    player.get_track_by_path.assert_called_once_with("/music/song.mp3")
    assert controls._title_label.text == "Song"
    assert controls._artist_widget.artists == "Artist"
    controls._load_cover_art_async.assert_called_once()


def test_on_cover_updated_uses_player_get_track_without_db():
    track = SimpleNamespace(
        id=9,
        path="/music/song.mp3",
        title="Song",
        artist="Artist",
        album="Album",
        duration=180.0,
        cover_path="/covers/song.jpg",
    )
    player = SimpleNamespace(
        engine=SimpleNamespace(current_track={"id": 9, "path": "/music/song.mp3"}),
        get_track=Mock(return_value=track),
    )
    controls = _make_controls(player)

    with patch("ui.widgets.player_controls.QTimer.singleShot", side_effect=lambda _delay, callback: callback()):
        controls._on_cover_updated(9, is_cloud=False)

    player.get_track.assert_called_once_with(9)
    controls._load_cover_art_async.assert_called_once()


def test_on_cover_updated_uses_player_cloud_lookup_without_db():
    track = SimpleNamespace(
        id=11,
        path="online://qqmusic/track/abc",
        title="Song",
        artist="Artist",
        album="Album",
        duration=200.0,
        cover_path="/covers/cloud.jpg",
    )
    player = SimpleNamespace(
        engine=SimpleNamespace(current_track={"cloud_file_id": "abc", "title": "Old"}),
        get_track_by_cloud_file_id=Mock(return_value=track),
    )
    controls = _make_controls(player)

    with patch("ui.widgets.player_controls.QTimer.singleShot", side_effect=lambda _delay, callback: callback()):
        controls._on_cover_updated("abc", is_cloud=True)

    player.get_track_by_cloud_file_id.assert_called_once_with("abc")
    controls._load_cover_art_async.assert_called_once()

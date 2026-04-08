from plugins.builtin.qqmusic.lib.search_normalizers import (
    normalize_album_item,
    normalize_artist_item,
    normalize_detail_song,
    normalize_playlist_item,
    normalize_song_item,
    normalize_top_list_track,
)


def test_normalize_song_item_supports_remote_api_shape():
    song = {
        "mid": "song-1",
        "name": "Song 1",
        "singer": [{"name": "Singer 1"}],
        "album": {"name": "Album 1", "mid": "album-1"},
        "interval": 180,
    }

    assert normalize_song_item(song) == {
        "mid": "song-1",
        "name": "Song 1",
        "title": "Song 1",
        "artist": "Singer 1",
        "singer": "Singer 1",
        "album": "Album 1",
        "album_mid": "album-1",
        "duration": 180,
    }


def test_normalize_detail_song_supports_service_shape():
    song = {
        "mid": "song-1",
        "title": "Song 1",
        "singer": [{"name": "Singer 1"}],
        "album": {"name": "Album 1", "mid": "album-1"},
        "interval": 180,
    }

    assert normalize_detail_song(song) == {
        "mid": "song-1",
        "title": "Song 1",
        "artist": "Singer 1",
        "album": "Album 1",
        "album_mid": "album-1",
        "duration": 180,
    }


def test_normalize_top_list_track_supports_dict_and_object_shapes():
    class _Track:
        mid = "song-2"
        title = "Song 2"
        singer_name = "Singer 2"
        album_name = "Album 2"
        duration = 200

        class album:
            mid = "album-2"

    assert normalize_top_list_track(
        {
            "mid": "song-1",
            "title": "Song 1",
            "artist": [{"name": "Singer 1"}],
            "album": {"name": "Album 1", "mid": "album-1"},
            "interval": 180,
        }
    )["artist"] == "Singer 1"
    assert normalize_top_list_track(_Track())["album_mid"] == "album-2"


def test_normalize_artist_album_and_playlist_items():
    artist = normalize_artist_item({"singerMID": "artist-1", "singerName": "Singer 1", "songNum": 8})
    album = normalize_album_item({"albummid": "album-1", "name": "Album 1", "singer": "Singer 1"})
    playlist = normalize_playlist_item({"dissid": 3, "dissname": "List 1", "nickname": "User 1"})

    assert artist["mid"] == "artist-1"
    assert album["mid"] == "album-1"
    assert playlist["id"] == "3"

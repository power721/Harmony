"""OnlineMusicAdapter normalization behavior tests."""

from services.online.adapter import OnlineMusicAdapter


def test_parse_ygking_song_info_list_parses_singers():
    items = [
        {
            "mid": "song-1",
            "title": "Song 1",
            "singer": [{"mid": "s1", "name": "Singer 1"}],
            "album": {"mid": "a1", "name": "Album 1"},
            "interval": 180,
        }
    ]

    tracks = OnlineMusicAdapter._parse_ygking_song_info_list(items)

    assert len(tracks) == 1
    assert tracks[0].singer[0].name == "Singer 1"
    assert tracks[0].album.name == "Album 1"


def test_parse_ygking_album_detail_parses_song_list():
    data = {
        "code": 0,
        "data": {
            "basicInfo": {"albumMid": "alb-1", "albumName": "Album 1"},
            "singer": {"singerList": [{"mid": "s1", "name": "Singer 1"}]},
            "songs": [{"mid": "song-1", "name": "Song 1", "singer": [], "album": {}}],
        },
    }

    parsed = OnlineMusicAdapter.parse_ygking_album_detail(data)

    assert parsed is not None
    assert parsed["mid"] == "alb-1"
    assert len(parsed["songs"]) == 1
    assert parsed["songs"][0]["mid"] == "song-1"


def test_parse_ygking_playlist_detail_parses_songlist():
    data = {
        "code": 0,
        "data": {
            "dirinfo": {"id": "pl-1", "title": "Playlist 1"},
            "songlist": [{"mid": "song-1", "name": "Song 1", "singer": [], "album": {}}],
        },
    }

    parsed = OnlineMusicAdapter.parse_ygking_playlist_detail(data)

    assert parsed is not None
    assert parsed["id"] == "pl-1"
    assert len(parsed["songs"]) == 1
    assert parsed["songs"][0]["mid"] == "song-1"

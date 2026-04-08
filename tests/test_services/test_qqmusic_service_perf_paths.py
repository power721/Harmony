"""QQMusicService behavior tests for list/dict iteration paths."""

from types import SimpleNamespace

from plugins.builtin.qqmusic.lib.qqmusic_service import QQMusicService


def test_get_playback_url_info_uses_first_non_empty_url():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_song_url=lambda *_args, **_kwargs: {
            "urls": {"a": "", "b": "https://music.example/b.flac"},
            "quality": "flac",
            "file_type": {"s": "F000", "e": ".flac"},
            "extension": ".flac",
        }
    )

    info = service.get_playback_url_info("song-mid")

    assert info is not None
    assert info["url"] == "https://music.example/b.flac"
    assert info["quality"] == "flac"


def test_get_singer_info_builds_singer_list_data():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_singer=lambda _mid: {
            "singer_list": [
                {
                    "basic_info": {"name": "Singer 1", "singer_mid": "s1", "album_total": 1},
                    "ex_info": {"desc": "desc"},
                    "pic": {},
                }
            ]
        },
        get_singer_songs=lambda *_args, **_kwargs: {
            "totalNum": 1,
            "songList": [
                {
                    "songInfo": {
                        "mid": "song-1",
                        "name": "Song 1",
                        "singer": [{"mid": "s1", "name": "Singer 1"}],
                        "album": {"mid": "a1", "name": "Album 1"},
                        "interval": 180,
                    }
                }
            ],
        },
    )

    data = service.get_singer_info("s1", page=1, page_size=20)

    assert data is not None
    assert data["songs"][0]["singer"][0]["name"] == "Singer 1"


def test_get_top_lists_flattens_groups():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_top_lists=lambda: {
            "group": [
                {"toplist": [{"topId": 1, "title": "Top 1", "type": 0}]},
                {"toplist": [{"topId": 2, "title": "Top 2", "type": 1}]},
            ]
        }
    )

    top_lists = service.get_top_lists()

    assert top_lists == [
        {"id": 1, "title": "Top 1", "type": 0},
        {"id": 2, "title": "Top 2", "type": 1},
    ]


def test_get_singer_albums_builds_cover_url_from_shared_helper():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_album_list=lambda *_args, **_kwargs: {
            "albumList": [
                {
                    "albumMid": "album-1",
                    "albumName": "Album 1",
                    "singerName": "Singer 1",
                    "totalNum": 10,
                    "publishDate": "2024-01-01",
                }
            ],
            "total": 1,
        }
    )

    result = service.get_singer_albums("singer-1")

    assert result["albums"][0]["cover_url"] == (
        "https://y.gtimg.cn/music/photo_new/T002R300x300M000album-1.jpg"
    )


def test_get_top_list_songs_uses_shared_top_list_normalizer():
    service = QQMusicService()
    service.client = SimpleNamespace(
        get_top_list_detail=lambda *_args, **_kwargs: {
            "songInfoList": [
                {
                    "mid": "song-1",
                    "title": "Song 1",
                    "artist": [{"name": "Singer 1"}],
                    "album": {"name": "Album 1", "mid": "album-1"},
                    "interval": 180,
                }
            ]
        },
        query_songs_by_ids=lambda _ids: [],
    )

    songs = service.get_top_list_songs(1)

    assert songs == [
        {
            "mid": "song-1",
            "title": "Song 1",
            "artist": "Singer 1",
            "album": "Album 1",
            "album_mid": "album-1",
            "duration": 180,
        }
    ]

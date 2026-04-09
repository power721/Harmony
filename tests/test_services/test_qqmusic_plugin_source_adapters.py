from types import SimpleNamespace

from plugins.builtin.qqmusic.lib.api import QQMusicPluginAPI
from plugins.builtin.qqmusic.lib.artist_cover_source import QQMusicArtistCoverPluginSource
from plugins.builtin.qqmusic.lib.cover_source import QQMusicCoverPluginSource
from plugins.builtin.qqmusic.lib.lyrics_source import QQMusicLyricsPluginSource
from plugins.builtin.qqmusic.lib.provider import QQMusicOnlineProvider


def test_qqmusic_api_search_artist_uses_singer_search(monkeypatch):
    captured = {}

    def fake_search(self, keyword, search_type="song", limit=20, page=1):
        captured.update(
            keyword=keyword,
            search_type=search_type,
            limit=limit,
            page=page,
        )
        return {"artists": [{"mid": "artist-1", "name": "Singer 1"}]}

    monkeypatch.setattr(QQMusicPluginAPI, "search", fake_search)

    api = QQMusicPluginAPI(SimpleNamespace())

    assert api.search_artist("Singer 1", limit=5) == [{"mid": "artist-1", "name": "Singer 1"}]
    assert captured == {
        "keyword": "Singer 1",
        "search_type": "singer",
        "limit": 5,
        "page": 1,
    }


def test_qqmusic_api_get_artist_detail_returns_detail_view_shape(monkeypatch):
    responses = {
        "https://music.har01d.cn/api/singer": {
            "code": 0,
            "data": {
                "singer_list": [
                    {
                        "basic_info": {
                            "singer_mid": "artist-1",
                            "name": "Singer 1",
                        },
                        "ex_info": {"desc": "Artist desc"},
                    }
                ]
            },
        }
    }

    def fake_get(url, params=None, timeout=0):
        del params, timeout
        return SimpleNamespace(json=lambda: responses[url])

    context = SimpleNamespace(http=SimpleNamespace(get=fake_get))
    api = QQMusicPluginAPI(context)
    monkeypatch.setattr(
        api,
        "search",
        lambda keyword, search_type="song", limit=20, page=1: {
            "tracks": [{"mid": "song-1", "title": "Song 1"}],
        },
    )

    detail = api.get_artist_detail("artist-1")

    assert detail == {
        "mid": "artist-1",
        "name": "Singer 1",
        "desc": "Artist desc",
        "avatar": "https://y.gtimg.cn/music/photo_new/T001R300x300M000artist-1.jpg",
        "album_count": 0,
        "songs": [{"mid": "song-1", "title": "Song 1"}],
    }


def test_qqmusic_api_get_album_detail_falls_back_to_song_search_when_songlist_missing():
    album_response = {
        "code": 0,
        "data": {
            "basicInfo": {
                "albumMid": "album-1",
                "albumName": "Album 1",
                "publishDate": "2024-01-01",
                "desc": "Album desc",
            },
            "singer": {
                "singerList": [
                    {"mid": "artist-1", "name": "Singer 1"},
                ]
            },
            "company": {"name": "Company 1"},
        },
    }
    search_response = {
        "code": 0,
        "data": {
            "list": [
                {
                    "mid": "song-1",
                    "name": "Song 1",
                    "singer": [{"name": "Singer 1"}],
                    "album": {"name": "Album 1", "mid": "album-1"},
                    "interval": 180,
                },
                {
                    "mid": "song-2",
                    "name": "Other Song",
                    "singer": [{"name": "Singer 1"}],
                    "album": {"name": "Other Album", "mid": "album-2"},
                    "interval": 200,
                },
            ],
            "total": 2,
        },
    }

    def fake_get(url, params=None, timeout=0):
        del timeout
        if url.endswith("/album"):
            assert params == {"mid": "album-1"}
            return SimpleNamespace(json=lambda: album_response)
        if url.endswith("/search"):
            assert params == {"keyword": "Singer 1 Album 1", "type": "song", "num": 50, "page": 1}
            return SimpleNamespace(json=lambda: search_response)
        raise AssertionError(f"unexpected url: {url}")

    context = SimpleNamespace(http=SimpleNamespace(get=fake_get))
    api = QQMusicPluginAPI(context)

    detail = api.get_album_detail("album-1")

    assert detail == {
        "mid": "album-1",
        "name": "Album 1",
        "singer": "Singer 1",
        "singer_mid": "artist-1",
        "cover_url": "https://y.gtimg.cn/music/photo_new/T002R500x500M000album-1.jpg",
        "publish_date": "2024-01-01",
        "description": "Album desc",
        "company": "Company 1",
        "songs": [
            {
                "mid": "song-1",
                "name": "Song 1",
                "title": "Song 1",
                "artist": "Singer 1",
                "singer": "Singer 1",
                "album": "Album 1",
                "album_mid": "album-1",
                "duration": 180,
            }
        ],
        "total": 1,
    }


def test_qqmusic_api_get_playlist_detail_returns_cover_and_creator():
    playlist_response = {
        "code": 0,
        "data": {
            "dirinfo": {
                "id": 9,
                "title": "Playlist 1",
                "picurl": "https://example.com/playlist.jpg",
                "desc": "Playlist desc",
                "creator": {"nick": "User 1"},
            },
            "songlist": [
                {
                    "mid": "song-1",
                    "name": "Song 1",
                    "singer": [{"name": "Singer 1"}],
                    "album": {"name": "Album 1", "mid": "album-1"},
                    "interval": 180,
                }
            ],
            "total_song_num": 1,
        },
    }

    def fake_get(url, params=None, timeout=0):
        del params, timeout
        return SimpleNamespace(json=lambda: playlist_response)

    context = SimpleNamespace(http=SimpleNamespace(get=fake_get))
    api = QQMusicPluginAPI(context)

    detail = api.get_playlist_detail("9")

    assert detail == {
        "id": "9",
        "name": "Playlist 1",
        "creator": "User 1",
        "cover": "https://example.com/playlist.jpg",
        "description": "Playlist desc",
        "songs": [
            {
                "mid": "song-1",
                "name": "Song 1",
                "title": "Song 1",
                "artist": "Singer 1",
                "singer": "Singer 1",
                "album": "Album 1",
                "album_mid": "album-1",
                "duration": 180,
            }
        ],
        "total": 1,
    }


def test_qqmusic_lyrics_source_search_reads_tracks_payload(monkeypatch):
    captured = {}

    def fake_search(self, keyword, search_type="song", page=1, page_size=30):
        captured.update(
            keyword=keyword,
            search_type=search_type,
            page=page,
            page_size=page_size,
        )
        return {
            "tracks": [
                {
                    "mid": "song-1",
                    "title": "Song 1",
                    "artist": "Singer 1",
                    "album": "Album 1",
                    "album_mid": "album-1",
                    "duration": 180,
                }
            ]
        }

    monkeypatch.setattr(QQMusicOnlineProvider, "search", fake_search)
    source = QQMusicLyricsPluginSource(SimpleNamespace())

    results = source.search("Song 1", "Singer 1", limit=7)

    assert captured == {
        "keyword": "Song 1 Singer 1",
        "search_type": "song",
        "page": 1,
        "page_size": 7,
    }
    assert len(results) == 1
    assert results[0].song_id == "song-1"
    assert results[0].title == "Song 1"
    assert results[0].artist == "Singer 1"
    assert results[0].album == "Album 1"
    assert results[0].duration == 180
    assert results[0].cover_url is None


def test_qqmusic_lyrics_source_search_does_not_request_cover_data(monkeypatch):
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "search",
        lambda *_args, **_kwargs: {
            "tracks": [
                {
                    "mid": "song-1",
                    "title": "Song 1",
                    "artist": "Singer 1",
                    "album": "Album 1",
                    "album_mid": "album-1",
                    "duration": 180,
                }
            ]
        },
    )

    def fail_get_cover_url(*_args, **_kwargs):
        raise AssertionError("provider.get_cover_url should not be called for lyrics search")

    monkeypatch.setattr(QQMusicOnlineProvider, "get_cover_url", fail_get_cover_url)

    source = QQMusicLyricsPluginSource(SimpleNamespace())

    results = source.search("Song 1", "Singer 1")

    assert results[0].cover_url is None


def test_qqmusic_cover_source_search_reads_tracks_payload(monkeypatch):
    def fake_search(self, keyword, search_type="song", page=1, page_size=30):
        assert keyword == "Singer 1 Song 1"
        assert search_type == "song"
        assert page == 1
        assert page_size == 5
        return {
            "tracks": [
                {
                    "mid": "song-1",
                    "title": "Song 1",
                    "artist": "Singer 1",
                    "album": "Album 1",
                    "album_mid": "album-1",
                    "duration": 180,
                }
            ]
        }

    monkeypatch.setattr(QQMusicOnlineProvider, "search", fake_search)

    source = QQMusicCoverPluginSource(SimpleNamespace())

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].item_id == "song-1"
    assert results[0].title == "Song 1"
    assert results[0].artist == "Singer 1"
    assert results[0].album == "Album 1"
    assert results[0].duration == 180
    assert results[0].extra_id == "album-1"


def test_qqmusic_lyrics_source_get_lyrics_uses_provider(monkeypatch):
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "get_lyrics",
        lambda self, song_mid: f"lyrics:{song_mid}",
    )

    source = QQMusicLyricsPluginSource(SimpleNamespace())

    assert source.get_lyrics_by_song_id("song-1") == "lyrics:song-1"


def test_qqmusic_cover_source_get_cover_url_uses_provider(monkeypatch):
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "get_cover_url",
        lambda self, mid=None, album_mid=None, size=500: f"cover:{album_mid or mid}:{size}",
    )

    source = QQMusicCoverPluginSource(SimpleNamespace())

    assert source.get_cover_url(mid="song-1", album_mid="album-1", size=700) == "cover:album-1:700"


def test_qqmusic_artist_cover_source_search_reads_normalized_artist_payload(monkeypatch):
    monkeypatch.setattr(
        QQMusicPluginAPI,
        "search_artist",
        lambda self, artist_name, limit=10: [
            {
                "mid": "artist-1",
                "name": "Singer 1",
                "avatar_url": "https://y.gtimg.cn/music/photo_new/T001R150x150M000artist1.jpg",
                "album_count": 12,
            }
        ],
    )

    source = QQMusicArtistCoverPluginSource(SimpleNamespace())

    results = source.search("Singer 1", limit=5)

    assert len(results) == 1
    assert results[0].artist_id == "artist-1"
    assert results[0].name == "Singer 1"
    assert results[0].album_count == 12
    assert results[0].cover_url == "https://y.gtimg.cn/music/photo_new/T001R500x500M000artist1.jpg"


def test_qqmusic_api_search_extracts_total_from_payload():
    response = SimpleNamespace(
        json=lambda: {
            "code": 0,
            "data": {
                "totalnum": 321,
                "list": [
                    {
                        "mid": "song-1",
                        "name": "Song 1",
                        "singer": [{"name": "Singer 1"}],
                        "album": {"name": "Album 1", "mid": "album-1"},
                        "interval": 180,
                    }
                ],
            },
        }
    )
    context = SimpleNamespace(
        http=SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )
    api = QQMusicPluginAPI(context)

    result = api.search("Song 1", search_type="song", limit=10, page=1)

    assert result["total"] == 321
    assert len(result["tracks"]) == 1


def test_qqmusic_api_init_updates_class_remote_base_url_from_settings():
    original_base_url = QQMusicPluginAPI.REMOTE_BASE_URL

    try:
        context = SimpleNamespace(
            settings=SimpleNamespace(
                get=lambda key, default=None: {
                    "remote_api_url": "https://mirror.example.com/custom-api/",
                }.get(key, default)
            ),
            http=SimpleNamespace(get=lambda *_args, **_kwargs: None),
        )

        QQMusicPluginAPI(context)

        assert QQMusicPluginAPI.REMOTE_BASE_URL == "https://mirror.example.com/custom-api/api"
    finally:
        QQMusicPluginAPI.REMOTE_BASE_URL = original_base_url

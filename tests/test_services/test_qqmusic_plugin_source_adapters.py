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
    monkeypatch.setattr(
        QQMusicOnlineProvider,
        "get_cover_url",
        lambda *_args, **_kwargs: "cover-1",
    )

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
    assert results[0].cover_url == "cover-1"


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

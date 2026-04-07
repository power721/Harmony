"""OnlineMusicAdapter normalization behavior tests."""

from services.online.adapter import ApiSource, OnlineMusicAdapter
from domain.online_music import SearchType


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


def test_normalize_qqmusic_singer_search_reads_item_singer_body_key():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "item_singer": [
                {"singerMID": "artist-1", "singerName": "Singer 1", "songNum": 12, "albumNum": 3}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.SINGER,
        keyword="Singer",
        page=1,
        page_size=30,
    )

    assert result.total == 1
    assert len(result.artists) == 1
    assert result.artists[0].mid == "artist-1"


def test_normalize_qqmusic_singer_search_accepts_legacy_singer_body_key():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "singer": [
                {"singerMID": "artist-legacy", "singerName": "Legacy Singer", "songNum": 6, "albumNum": 1}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.SINGER,
        keyword="Singer",
        page=1,
        page_size=30,
    )

    assert len(result.artists) == 1
    assert result.artists[0].mid == "artist-legacy"


def test_normalize_qqmusic_singer_search_accepts_mid_name_fields():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "item_singer": [
                {"mid": "artist-2", "name": "Singer 2", "song_count": 8, "album_count": 2}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.SINGER,
        keyword="Singer",
        page=1,
        page_size=30,
    )

    assert len(result.artists) == 1
    assert result.artists[0].mid == "artist-2"
    assert result.artists[0].name == "Singer 2"


def test_normalize_qqmusic_singer_search_builds_avatar_and_counts_from_fallback_fields():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "item_singer": [
                {"mid": "artist-3", "name": "Singer 3", "songnum": 18, "albumnum": 4, "FanNum": 12345}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.SINGER,
        keyword="Singer",
        page=1,
        page_size=30,
    )

    assert len(result.artists) == 1
    assert result.artists[0].avatar_url.endswith("T001R300x300M000artist-3.jpg")
    assert result.artists[0].song_count == 18
    assert result.artists[0].album_count == 4
    assert result.artists[0].fan_count == 12345


def test_normalize_qqmusic_playlist_search_accepts_legacy_songlist_body_key():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "songlist": [
                {"dissid": "playlist-legacy", "dissname": "Legacy Playlist", "songnum": 9, "listennum": 123}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.PLAYLIST,
        keyword="Playlist",
        page=1,
        page_size=30,
    )

    assert len(result.playlists) == 1
    assert result.playlists[0].id == "playlist-legacy"


def test_normalize_qqmusic_album_search_reads_item_album_body_key():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "item_album": [
                {"albummid": "album-1", "name": "Album 1", "singer": "Singer 1", "song_count": 8}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.ALBUM,
        keyword="Album",
        page=1,
        page_size=30,
    )

    assert result.total == 1
    assert len(result.albums) == 1
    assert result.albums[0].mid == "album-1"


def test_normalize_qqmusic_playlist_search_reads_item_songlist_body_key():
    raw_data = {
        "meta": {"sum": 1},
        "body": {
            "item_songlist": [
                {"dissid": "playlist-1", "dissname": "Playlist 1", "song_count": 16, "play_count": 200}
            ]
        },
    }

    result = OnlineMusicAdapter.normalize_search_result(
        ApiSource.QQMUSIC,
        raw_data,
        SearchType.PLAYLIST,
        keyword="Playlist",
        page=1,
        page_size=30,
    )

    assert result.total == 1
    assert len(result.playlists) == 1
    assert result.playlists[0].id == "playlist-1"

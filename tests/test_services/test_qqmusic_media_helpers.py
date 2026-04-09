from plugins.builtin.qqmusic.lib.media_helpers import (
    build_album_cover_url,
    build_artist_cover_url,
    extract_album_mid,
    pick_lyric_text,
)


def test_build_album_cover_url_returns_expected_url():
    assert build_album_cover_url("album-1", 500) == (
        "https://y.gtimg.cn/music/photo_new/T002R500x500M000album-1.jpg"
    )


def test_build_artist_cover_url_returns_expected_url():
    assert build_artist_cover_url("artist-1", 300) == (
        "https://y.gtimg.cn/music/photo_new/T001R300x300M000artist-1.jpg"
    )


def test_extract_album_mid_supports_track_info_album():
    payload = {"track_info": {"album": {"mid": "album-from-track"}}}

    assert extract_album_mid(payload) == "album-from-track"


def test_extract_album_mid_supports_flat_album_mid_keys():
    payload = {"data": {"albumMid": "album-from-data"}}

    assert extract_album_mid(payload) == "album-from-data"


def test_pick_lyric_text_prefers_qrc_then_plain_lyric():
    assert pick_lyric_text({"qrc": "[0,100]qrc", "lyric": "[00:00.00]plain"}) == "[0,100]qrc"
    assert pick_lyric_text({"qrc": "", "lyric": "[00:00.00]plain"}) == "[00:00.00]plain"
    assert pick_lyric_text({"qrc": None, "lyric": None}) is None

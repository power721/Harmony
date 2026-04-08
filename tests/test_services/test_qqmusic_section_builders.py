from plugins.builtin.qqmusic.lib.section_builders import build_section, pick_section_cover


def test_pick_section_cover_prefers_track_album_mid():
    items = [{"Track": {"album": {"mid": "album-1"}}}]

    assert pick_section_cover(items) == (
        "https://y.gtimg.cn/music/photo_new/T002R300x300M000album-1.jpg"
    )


def test_pick_section_cover_reads_nested_playlist_cover_url():
    items = [
        {
            "Playlist": {
                "basic": {
                    "cover_url": "https://cover.example/playlist.jpg",
                }
            }
        }
    ]

    assert pick_section_cover(items) == "https://cover.example/playlist.jpg"


def test_pick_section_cover_falls_back_to_cover_url():
    items = [{"cover_url": "https://cover.example/1.jpg"}]

    assert pick_section_cover(items) == "https://cover.example/1.jpg"


def test_build_section_adds_count_only_when_requested():
    recommendation = build_section(
        card_id="guess",
        title="猜你喜欢",
        entry_type="songs",
        items=[{"cover_url": "https://cover.example/1.jpg"}],
    )
    favorites = build_section(
        card_id="fav_songs",
        title="我喜欢的歌曲",
        entry_type="songs",
        items=[{"cover_url": "https://cover.example/1.jpg"}],
        include_count=True,
    )

    assert recommendation["subtitle"] == "1 项"
    assert "count" not in recommendation
    assert favorites["count"] == 1

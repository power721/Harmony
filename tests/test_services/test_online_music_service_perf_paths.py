"""OnlineMusicService parsing behavior tests for list construction paths."""

from types import SimpleNamespace

from services.online.online_music_service import OnlineMusicService


def test_get_top_lists_ygking_flattens_group_toplists():
    service = OnlineMusicService()

    response = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {
            "code": 0,
            "data": {
                "group": [
                    {"toplist": [{"topId": 1, "title": "Top 1"}]},
                    {"toplist": [{"topId": 2, "title": "Top 2"}]},
                ]
            },
        },
    )
    service._http_client = SimpleNamespace(get=lambda *_args, **_kwargs: response)

    top_lists = service._get_top_lists_ygking()

    assert top_lists == [{"id": 1, "title": "Top 1"}, {"id": 2, "title": "Top 2"}]


def test_get_artist_albums_ygking_filters_by_singer():
    matching = SimpleNamespace(
        mid="a1",
        name="Album 1",
        singer_mid="s1",
        singer_name="Singer 1",
        cover_url="cover-1",
        song_count=10,
        publish_date="2024-01-01",
    )
    non_matching = SimpleNamespace(
        mid="a2",
        name="Album 2",
        singer_mid="other",
        singer_name="Other",
        cover_url="cover-2",
        song_count=8,
        publish_date="2023-01-01",
    )
    fake_service = SimpleNamespace(
        _get_artist_detail_ygking=lambda _mid: {"name": "Singer 1"},
        _search_ygking=lambda *_args, **_kwargs: SimpleNamespace(albums=[matching, non_matching], total=2),
    )

    result = OnlineMusicService._get_artist_albums_ygking(fake_service, "s1", number=20, begin=0)

    assert result["total"] == 2
    assert len(result["albums"]) == 1
    assert result["albums"][0]["mid"] == "a1"

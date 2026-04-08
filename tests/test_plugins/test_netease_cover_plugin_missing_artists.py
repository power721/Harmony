from types import SimpleNamespace

from plugins.builtin.netease_cover.lib.cover_source import NetEaseCoverPluginSource


def test_netease_cover_search_handles_empty_artists_list():
    responses = [
        SimpleNamespace(status_code=200, json=lambda: {"code": 200, "result": {"albums": []}}),
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": 200,
                "result": {
                    "songs": [
                        {
                            "id": 2,
                            "name": "Song 1",
                            "artists": [],
                            "duration": 180000,
                            "album": {
                                "name": "Album 1",
                                "picUrl": "https://example.com/song.jpg",
                            },
                        }
                    ]
                },
            },
        ),
    ]
    source = NetEaseCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: responses.pop(0))
    )

    results = source.search("Song 1", "Singer 1", "Album 1")

    assert len(results) == 1
    assert results[0].item_id == "2"
    assert results[0].artist == ""

from types import SimpleNamespace

from plugins.builtin.netease_lyrics.lib.lyrics_source import NetEaseLyricsPluginSource


def test_netease_lyrics_search_handles_missing_id_and_empty_artists():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "songs": [
                    {
                        "name": "Song 1",
                        "artists": [],
                        "album": {"name": "Album 1"},
                    }
                ]
            },
        },
    )
    source = NetEaseLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].id == ""
    assert results[0].artist == ""

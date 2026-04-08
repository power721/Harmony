from types import SimpleNamespace

from plugins.builtin.kugou.lib.lyrics_source import KugouLyricsPluginSource


def test_kugou_search_handles_candidates_without_id():
    fake_response = SimpleNamespace(
        json=lambda: {
            "candidates": [
                {
                    "name": "Song 1",
                    "singer": "Singer 1",
                    "accesskey": "k1",
                }
            ]
        }
    )
    source = KugouLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: fake_response)
    )

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].song_id == ""
    assert results[0].title == "Song 1"

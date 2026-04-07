from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.kugou.lib.lyrics_source import KugouLyricsPluginSource
from plugins.builtin.kugou.plugin_main import KugouLyricsPlugin


def test_kugou_plugin_registers_lyrics_source():
    context = Mock()
    plugin = KugouLyricsPlugin()

    plugin.register(context)

    context.services.register_lyrics_source.assert_called_once()
    registered = context.services.register_lyrics_source.call_args.args[0]
    assert isinstance(registered, KugouLyricsPluginSource)


def test_kugou_plugin_source_search_builds_results():
    fake_response = SimpleNamespace(
        json=lambda: {
            "candidates": [
                {
                    "id": 1,
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
    assert results[0].song_id == "1"
    assert results[0].title == "Song 1"
    assert results[0].artist == "Singer 1"
    assert results[0].source == "kugou"
    assert results[0].accesskey == "k1"

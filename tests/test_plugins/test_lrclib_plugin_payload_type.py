from types import SimpleNamespace

from plugins.builtin.lrclib.lib.lrclib_source import LRCLIBPluginSource


def test_lrclib_search_ignores_non_list_payload():
    response = SimpleNamespace(status_code=200, json=lambda: {"id": 1})
    source = LRCLIBPluginSource(SimpleNamespace(get=lambda *_args, **_kwargs: response))

    assert source.search("Song 1", "Singer 1") == []

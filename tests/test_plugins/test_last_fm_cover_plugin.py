from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.last_fm_cover.lib.cover_source import LastFmCoverPluginSource
from plugins.builtin.last_fm_cover.plugin_main import LastFmCoverPlugin


def test_last_fm_plugin_registers_cover_source():
    context = Mock()
    plugin = LastFmCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
    registered_cover = context.services.register_cover_source.call_args.args[0]
    assert isinstance(registered_cover, LastFmCoverPluginSource)


def test_last_fm_plugin_source_uses_default_api_key_when_env_missing(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=0):
        captured["url"] = url
        captured["params"] = params
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "album": {
                    "name": "Album 1",
                    "artist": "Singer 1",
                    "image": [
                        {"#text": ""},
                        {"#text": "https://example.com/cover-large.jpg"},
                    ],
                }
            },
        )

    monkeypatch.delenv("LASTFM_API_KEY", raising=False)
    source = LastFmCoverPluginSource(SimpleNamespace(get=fake_get))

    results = source.search("Song 1", "Singer 1", "Album 1")

    assert captured["url"] == "http://ws.audioscrobbler.com/2.0/"
    assert captured["params"]["api_key"] == "9b0cdcf446cc96dea3e747787ad23575"
    assert len(results) == 1
    assert results[0].title == "Album 1"
    assert results[0].artist == "Singer 1"
    assert results[0].album == "Album 1"
    assert results[0].source == "lastfm"
    assert results[0].cover_url == "https://example.com/cover-large.jpg"


def test_last_fm_plugin_source_uses_default_api_key_when_env_is_placeholder(monkeypatch):
    captured = {}

    def fake_get(url, params=None, timeout=0):
        captured["params"] = params
        return SimpleNamespace(status_code=200, json=lambda: {"album": {"image": []}})

    monkeypatch.setenv("LASTFM_API_KEY", "YOUR_LASTFM_API_KEY")
    source = LastFmCoverPluginSource(SimpleNamespace(get=fake_get))

    source.search("Song 1", "Singer 1", "Album 1")

    assert captured["params"]["api_key"] == "9b0cdcf446cc96dea3e747787ad23575"

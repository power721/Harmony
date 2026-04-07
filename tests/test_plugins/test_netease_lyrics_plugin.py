from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.netease_shared.common import (
    build_netease_image_url,
    netease_headers,
)
from plugins.builtin.netease_lyrics.lib.lyrics_source import NetEaseLyricsPluginSource
from plugins.builtin.netease_lyrics.plugin_main import NetEaseLyricsPlugin


def test_netease_shared_helpers_normalize_headers_and_image_urls():
    headers = netease_headers()

    assert headers["Referer"] == "https://music.163.com/"
    assert "Mozilla/5.0" in headers["User-Agent"]
    assert build_netease_image_url("https://example.com/cover.jpg", "500y500") == (
        "https://example.com/cover.jpg?param=500y500"
    )
    assert build_netease_image_url("https://example.com/cover.jpg?foo=1", "500y500") == (
        "https://example.com/cover.jpg?foo=1"
    )


def test_netease_lyrics_plugin_registers_lyrics_source():
    context = Mock()
    plugin = NetEaseLyricsPlugin()

    plugin.register(context)

    context.services.register_lyrics_source.assert_called_once()
    registered = context.services.register_lyrics_source.call_args.args[0]
    assert isinstance(registered, NetEaseLyricsPluginSource)


def test_netease_lyrics_plugin_source_search_maps_results():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "songs": [
                    {
                        "id": 1,
                        "name": "Song 1",
                        "artists": [{"name": "Singer 1"}],
                        "album": {
                            "name": "Album 1",
                            "picUrl": "https://example.com/cover.jpg",
                        },
                        "duration": 225000,
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
    assert results[0].song_id == "1"
    assert results[0].title == "Song 1"
    assert results[0].artist == "Singer 1"
    assert results[0].album == "Album 1"
    assert results[0].duration == 225.0
    assert results[0].source == "netease"
    assert results[0].cover_url == "https://example.com/cover.jpg"
    assert results[0].supports_yrc is True


def test_netease_lyrics_plugin_source_prefers_yrc_then_falls_back_to_lrc():
    responses = [
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": 200,
                "yrc": {},
                "lrc": {"lyric": "[00:01.00]line"},
            },
        )
    ]
    source = NetEaseLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: responses.pop(0))
    )

    lyrics = source.get_lyrics(SimpleNamespace(song_id="1"))

    assert lyrics == "[00:01.00]line"


def test_netease_lyrics_plugin_source_uses_lrc_fallback_request_when_first_call_has_no_lyrics():
    responses = [
        SimpleNamespace(status_code=200, json=lambda: {"code": 200, "yrc": {}, "lrc": {}}),
        SimpleNamespace(
            status_code=200,
            json=lambda: {"code": 200, "lrc": {"lyric": "[00:02.00]fallback"}},
        ),
    ]
    source = NetEaseLyricsPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: responses.pop(0))
    )

    lyrics = source.get_lyrics(SimpleNamespace(song_id="1"))

    assert lyrics == "[00:02.00]fallback"

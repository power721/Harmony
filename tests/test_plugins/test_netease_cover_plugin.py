from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.netease_cover.lib.artist_cover_source import (
    NetEaseArtistCoverPluginSource,
)
from plugins.builtin.netease_cover.lib.cover_source import NetEaseCoverPluginSource
from plugins.builtin.netease_cover.plugin_main import NetEaseCoverPlugin


def test_netease_cover_plugin_registers_cover_and_artist_sources():
    context = Mock()
    plugin = NetEaseCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1
    assert isinstance(
        context.services.register_cover_source.call_args.args[0],
        NetEaseCoverPluginSource,
    )
    assert isinstance(
        context.services.register_artist_cover_source.call_args.args[0],
        NetEaseArtistCoverPluginSource,
    )


def test_netease_cover_source_search_maps_album_and_song_results():
    responses = [
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": 200,
                "result": {
                    "albums": [
                        {
                            "id": 1,
                            "name": "Album 1",
                            "artist": {"name": "Singer 1"},
                            "picUrl": "https://example.com/album.jpg",
                        }
                    ]
                },
            },
        ),
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "code": 200,
                "result": {
                    "songs": [
                        {
                            "id": 2,
                            "name": "Song 1",
                            "artists": [{"name": "Singer 1"}],
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

    assert len(results) == 2
    assert results[0].item_id == "1"
    assert results[0].album == "Album 1"
    assert results[0].source == "netease"
    assert results[0].cover_url == "https://example.com/album.jpg?param=500y500"
    assert results[1].item_id == "2"
    assert results[1].duration == 180.0


def test_netease_cover_source_returns_empty_list_on_request_error():
    source = NetEaseCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")))
    )

    assert source.search("Song 1", "Singer 1", "Album 1") == []


def test_netease_artist_cover_source_search_maps_results():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "artists": [
                    {
                        "id": 1,
                        "name": "Singer 1",
                        "albumSize": 8,
                        "picUrl": "https://example.com/artist.jpg",
                    }
                ]
            },
        },
    )
    source = NetEaseArtistCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Singer 1", limit=5)

    assert len(results) == 1
    assert results[0].artist_id == "1"
    assert results[0].name == "Singer 1"
    assert results[0].album_count == 8
    assert results[0].source == "netease"
    assert results[0].cover_url == "https://example.com/artist.jpg?param=512y512"


def test_netease_artist_cover_source_uses_img1v1_url_when_pic_url_missing():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "code": 200,
            "result": {
                "artists": [
                    {
                        "id": 1,
                        "name": "Singer 1",
                        "albumSize": 8,
                        "img1v1Url": "https://example.com/artist-alt.jpg",
                    }
                ]
            },
        },
    )
    source = NetEaseArtistCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Singer 1", limit=5)

    assert results[0].cover_url == "https://example.com/artist-alt.jpg?param=512y512"

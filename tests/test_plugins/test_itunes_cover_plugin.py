from types import SimpleNamespace
from unittest.mock import Mock

from plugins.builtin.itunes_cover.lib.artist_cover_source import (
    ITunesArtistCoverPluginSource,
)
from plugins.builtin.itunes_cover.lib.cover_source import ITunesCoverPluginSource
from plugins.builtin.itunes_cover.plugin_main import ITunesCoverPlugin


def test_itunes_plugin_registers_cover_and_artist_sources():
    context = Mock()
    plugin = ITunesCoverPlugin()

    plugin.register(context)

    assert context.services.register_cover_source.call_count == 1
    assert context.services.register_artist_cover_source.call_count == 1

    registered_cover = context.services.register_cover_source.call_args.args[0]
    registered_artist_cover = (
        context.services.register_artist_cover_source.call_args.args[0]
    )

    assert isinstance(registered_cover, ITunesCoverPluginSource)
    assert isinstance(registered_artist_cover, ITunesArtistCoverPluginSource)


def test_itunes_cover_source_search_maps_album_results():
    responses = [
        SimpleNamespace(
            status_code=200,
            json=lambda: {
                "results": [
                    {
                        "collectionId": 1,
                        "collectionName": "Album 1",
                        "artistName": "Singer 1",
                        "artworkUrl100": "https://example.com/100x100bb.jpg",
                    }
                ]
            },
        ),
        SimpleNamespace(status_code=200, json=lambda: {"results": []}),
    ]
    http = SimpleNamespace(
        get=lambda *_args, **_kwargs: responses.pop(0),
    )
    source = ITunesCoverPluginSource(http)

    results = source.search("Song 1", "Singer 1", "Album 1")

    assert len(results) == 1
    assert results[0].item_id == "1"
    assert results[0].title == "Album 1"
    assert results[0].artist == "Singer 1"
    assert results[0].album == "Album 1"
    assert results[0].source == "itunes"
    assert results[0].cover_url == "https://example.com/600x600bb.jpg"


def test_itunes_artist_cover_source_deduplicates_artists():
    response = SimpleNamespace(
        status_code=200,
        json=lambda: {
            "results": [
                {
                    "artistId": 1,
                    "artistName": "Singer 1",
                    "artworkUrl100": "https://example.com/100x100bb.jpg",
                },
                {
                    "artistId": 2,
                    "artistName": "singer 1",
                    "artworkUrl100": "https://example.com/100x100cc.jpg",
                },
            ]
        },
    )
    source = ITunesArtistCoverPluginSource(
        SimpleNamespace(get=lambda *_args, **_kwargs: response)
    )

    results = source.search("Singer 1", limit=5)

    assert len(results) == 1
    assert results[0].artist_id == "1"
    assert results[0].name == "Singer 1"
    assert results[0].source == "itunes"
    assert results[0].cover_url == "https://example.com/600x600bb.jpg"

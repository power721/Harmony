"""CoverService behavior tests for transformed list construction paths."""

from types import SimpleNamespace

import services.metadata.cover_service as cover_service_module
from harmony_plugin_api.cover import PluginCoverResult
from harmony_plugin_api.cover import PluginArtistCoverResult
from services.metadata.cover_service import CoverService
from services.sources.base import CoverSearchResult


def test_fetch_online_cover_uses_best_match_and_cache(monkeypatch):
    source = SimpleNamespace(
        name="FakeCoverSource",
        search=lambda *_args, **_kwargs: [
            CoverSearchResult(
                id="song-1",
                title="Song 1",
                artist="Singer 1",
                album="Album 1",
                source="fake",
                cover_url="https://example.com/cover.jpg",
            )
        ],
        is_available=lambda: True,
    )
    service = CoverService(
        http_client=SimpleNamespace(get_content=lambda *_args, **_kwargs: b"img"),
        sources=[source],
    )
    monkeypatch.setattr(
        cover_service_module.MatchScorer,
        "find_best_match",
        staticmethod(lambda *_args, **_kwargs: (SimpleNamespace(
            title="Song 1",
            artist="Singer 1",
            source="fake",
            cover_url="https://example.com/cover.jpg",
        ), 80.0)),
    )
    monkeypatch.setattr(service, "_save_cover_to_cache", lambda *_args, **_kwargs: "/tmp/cover.jpg")

    cover_path = service._fetch_online_cover("Song 1", "Singer 1", "Album 1", "cache-key")

    assert cover_path == "/tmp/cover.jpg"


def test_fetch_online_cover_supports_plugin_cover_result_shape(monkeypatch):
    source = SimpleNamespace(
        name="QQMusic",
        search=lambda *_args, **_kwargs: [
            PluginCoverResult(
                item_id="song-1",
                title="Song 1",
                artist="Singer 1",
                album="Album 1",
                source="qqmusic",
                cover_url="https://example.com/cover.jpg",
                extra_id="album-1",
            )
        ],
        is_available=lambda: True,
    )
    service = CoverService(
        http_client=SimpleNamespace(get_content=lambda *_args, **_kwargs: b"img"),
        sources=[source],
    )
    monkeypatch.setattr(
        cover_service_module.MatchScorer,
        "find_best_match",
        staticmethod(
            lambda *_args, **_kwargs: (
                SimpleNamespace(
                    title="Song 1",
                    artist="Singer 1",
                    source="qqmusic",
                    cover_url="https://example.com/cover.jpg",
                ),
                80.0,
            )
        ),
    )
    monkeypatch.setattr(service, "_save_cover_to_cache", lambda *_args, **_kwargs: "/tmp/cover.jpg")

    cover_path = service._fetch_online_cover("Song 1", "Singer 1", "Album 1", "cache-key")

    assert cover_path == "/tmp/cover.jpg"


def test_fetch_online_cover_returns_none_when_no_sources(monkeypatch):
    service = CoverService(http_client=SimpleNamespace())
    monkeypatch.setattr(service, "_get_sources", lambda: [])

    cover_path = service._fetch_online_cover("Song 1", "Singer 1", "Album 1", "cache-key")

    assert cover_path is None


def test_search_covers_converts_and_scores_results(monkeypatch):
    source = SimpleNamespace(
        name="FakeCoverSource",
        search=lambda *_args, **_kwargs: [
            CoverSearchResult(
                id="song-1",
                title="Song 1",
                artist="Singer 1",
                album="Album 1",
                source="fake",
                cover_url="https://example.com/cover.jpg",
            )
        ],
        is_available=lambda: True,
    )
    service = CoverService(http_client=SimpleNamespace())
    monkeypatch.setattr(service, "_get_sources", lambda: [source])
    monkeypatch.setattr(
        cover_service_module.MatchScorer,
        "calculate_score",
        staticmethod(lambda *_args, **_kwargs: 88.0),
    )

    results = service.search_covers("Song 1", "Singer 1", "Album 1")

    assert len(results) == 1
    assert results[0]["id"] == "song-1"
    assert results[0]["score"] == 88.0


def test_search_covers_supports_plugin_cover_result_shape(monkeypatch):
    source = SimpleNamespace(
        name="QQMusic",
        search=lambda *_args, **_kwargs: [
            PluginCoverResult(
                item_id="song-1",
                title="Song 1",
                artist="Singer 1",
                album="Album 1",
                source="qqmusic",
                cover_url="https://example.com/cover.jpg",
                extra_id="album-1",
            )
        ],
        is_available=lambda: True,
    )
    service = CoverService(http_client=SimpleNamespace())
    monkeypatch.setattr(service, "_get_sources", lambda: [source])
    monkeypatch.setattr(
        cover_service_module.MatchScorer,
        "calculate_score",
        staticmethod(lambda *_args, **_kwargs: 88.0),
    )

    results = service.search_covers("Song 1", "Singer 1", "Album 1")

    assert len(results) == 1
    assert results[0]["id"] == "song-1"
    assert results[0]["album_mid"] == "album-1"
    assert results[0]["score"] == 88.0


def test_search_covers_returns_empty_list_when_no_sources(monkeypatch):
    service = CoverService(http_client=SimpleNamespace())
    monkeypatch.setattr(service, "_get_sources", lambda: [])

    results = service.search_covers("Song 1", "Singer 1", "Album 1")

    assert results == []


def test_search_artist_covers_supports_plugin_artist_result_shape(monkeypatch):
    source = SimpleNamespace(
        name="QQMusic",
        search=lambda *_args, **_kwargs: [
            PluginArtistCoverResult(
                artist_id="artist-1",
                name="Singer 1",
                source="qqmusic",
                cover_url=None,
                album_count=12,
            )
        ],
    )
    service = CoverService(http_client=SimpleNamespace())
    monkeypatch.setattr(service, "_get_artist_sources", lambda: [source])

    results = service.search_artist_covers("Singer 1", limit=5)

    assert len(results) == 1
    assert results[0]["id"] == "artist-1"
    assert results[0]["singer_mid"] == "artist-1"
    assert results[0]["album_count"] == 12


def test_search_artist_covers_returns_empty_list_when_no_sources(monkeypatch):
    service = CoverService(http_client=SimpleNamespace())
    monkeypatch.setattr(service, "_get_artist_sources", lambda: [])

    results = service.search_artist_covers("Singer 1", limit=5)

    assert results == []

"""CoverService behavior tests for transformed list construction paths."""

from types import SimpleNamespace

import services.metadata.cover_service as cover_service_module
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
    service = CoverService(http_client=SimpleNamespace(), sources=[source])
    monkeypatch.setattr(
        cover_service_module.MatchScorer,
        "calculate_score",
        staticmethod(lambda *_args, **_kwargs: 88.0),
    )

    results = service.search_covers("Song 1", "Singer 1", "Album 1")

    assert len(results) == 1
    assert results[0]["id"] == "song-1"
    assert results[0]["score"] == 88.0

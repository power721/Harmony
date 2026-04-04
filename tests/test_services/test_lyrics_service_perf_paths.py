"""LyricsService behavior tests for transformed list construction paths."""

from types import SimpleNamespace

from services.lyrics.lyrics_service import LyricsService
from services.sources.base import LyricsSearchResult


def test_search_songs_builds_compatibility_dicts(monkeypatch):
    fake_source = SimpleNamespace(
        name="FakeSource",
        search=lambda *_args, **_kwargs: [
            LyricsSearchResult(
                id="song-1",
                title="Song 1",
                artist="Singer 1",
                album="Album 1",
                duration=180,
                source="fake",
                cover_url="cover-1",
                lyrics=None,
                accesskey=None,
                supports_yrc=False,
            )
        ],
    )
    monkeypatch.setattr(LyricsService, "_get_sources", classmethod(lambda cls: [fake_source]))

    results = LyricsService.search_songs("Song 1", "Singer 1", limit=5)

    assert len(results) == 1
    assert results[0]["id"] == "song-1"
    assert results[0]["source"] == "fake"


def test_get_online_lyrics_uses_best_match_and_download(monkeypatch):
    fake_source = SimpleNamespace(
        name="FakeSource",
        search=lambda *_args, **_kwargs: [
            LyricsSearchResult(
                id="song-1",
                title="Song 1",
                artist="Singer 1",
                album="Album 1",
                duration=180,
                source="qqmusic",
                cover_url="cover-1",
            )
        ],
    )
    monkeypatch.setattr(LyricsService, "_get_sources", classmethod(lambda cls: [fake_source]))
    monkeypatch.setattr(
        "services.lyrics.lyrics_service.MatchScorer.find_best_match",
        lambda *_args, **_kwargs: (SimpleNamespace(id="song-1", source="qqmusic", title="Song 1", artist="Singer 1"), 90.0),
    )
    monkeypatch.setattr(
        LyricsService,
        "download_lyrics_by_id",
        classmethod(lambda cls, song_id, source, accesskey=None: f"{source}:{song_id}"),
    )

    lyrics = LyricsService._get_online_lyrics("Song 1", "Singer 1")

    assert lyrics == "qqmusic:song-1"

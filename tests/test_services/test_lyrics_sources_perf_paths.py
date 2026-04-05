"""Lyrics source behavior tests for transformed list construction paths."""

from types import SimpleNamespace

from plugins.builtin.qqmusic.lib.lyrics_source import QQMusicLyricsPluginSource
from services.sources.lyrics_sources import KugouLyricsSource


def test_qqmusic_lyrics_source_search_builds_results(monkeypatch):
    monkeypatch.setattr(
        "services.lyrics.qqmusic_lyrics.search_from_qqmusic",
        lambda *_args, **_kwargs: [
            {
                "id": "song-1",
                "title": "Song 1",
                "artist": "Singer 1",
                "album": "Album 1",
                "duration": 180,
                "cover_url": "cover-1",
            }
        ],
    )
    source = QQMusicLyricsPluginSource(SimpleNamespace())

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].song_id == "song-1"
    assert results[0].title == "Song 1"


def test_kugou_lyrics_source_search_builds_results():
    fake_response = SimpleNamespace(
        json=lambda: {"candidates": [{"id": 1, "name": "Song 1", "singer": "Singer 1", "accesskey": "k1"}]}
    )
    source = KugouLyricsSource(SimpleNamespace(get=lambda *_args, **_kwargs: fake_response))

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].id == "1"
    assert results[0].accesskey == "k1"

"""Lyrics source behavior tests for transformed list construction paths."""

from types import SimpleNamespace

from plugins.builtin.qqmusic.lib.api import QQMusicPluginAPI
from plugins.builtin.qqmusic.lib.lyrics_source import QQMusicLyricsPluginSource


def test_qqmusic_lyrics_source_search_builds_results(monkeypatch):
    monkeypatch.setattr(
        QQMusicPluginAPI,
        "search",
        lambda *_args, **_kwargs: [
            {
                "mid": "song-1",
                "title": "Song 1",
                "singer": "Singer 1",
                "album": "Album 1",
                "interval": 180,
                "album_mid": "album-1",
            }
        ],
    )
    monkeypatch.setattr(
        QQMusicPluginAPI,
        "get_cover_url",
        lambda *_args, **_kwargs: "cover-1",
    )
    source = QQMusicLyricsPluginSource(SimpleNamespace())

    results = source.search("Song 1", "Singer 1")

    assert len(results) == 1
    assert results[0].song_id == "song-1"
    assert results[0].title == "Song 1"

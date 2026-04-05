"""LyricsLoader regression tests."""

from __future__ import annotations

from services.lyrics.lyrics_loader import LyricsLoader
from services.lyrics import lyrics_loader as lyrics_loader_module


def test_lyrics_loader_skips_result_emit_when_loader_becomes_invalid(monkeypatch):
    """Loader should not emit results after the QObject becomes invalid."""
    monkeypatch.setattr(
        lyrics_loader_module.LyricsService,
        "get_lyrics",
        staticmethod(lambda *_args, **_kwargs: "lyrics"),
    )

    validity = iter([True, False])
    monkeypatch.setattr(lyrics_loader_module, "isValid", lambda _obj: next(validity), raising=False)

    loader = LyricsLoader("/tmp/test.mp3", "Song", "Artist")
    started = []
    results = []
    loader.loading_started.connect(lambda: started.append(True))
    loader.lyrics_ready.connect(results.append)

    loader.run()

    assert started == [True]
    assert results == []

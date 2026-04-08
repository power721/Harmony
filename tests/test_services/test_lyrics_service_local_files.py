"""Tests for local lyrics file loading paths."""

from pathlib import Path

from services.lyrics.lyrics_service import LyricsService


def test_get_local_lyrics_reads_non_utf8_file_once(tmp_path, monkeypatch):
    lyrics_path = tmp_path / "song.qrc"
    lyrics_path.write_text("[00:00.00]hello", encoding="utf-16")

    open_calls = []
    real_open = open

    def tracking_open(file, mode="r", *args, **kwargs):
        if Path(file) == lyrics_path:
            open_calls.append((str(file), mode, kwargs.get("encoding")))
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr("builtins.open", tracking_open)

    result = LyricsService._get_local_lyrics(str(tmp_path / "song.mp3"))

    assert result == "[00:00.00]hello"
    assert len(open_calls) == 1

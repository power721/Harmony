from types import SimpleNamespace

from harmony_plugin_api.lyrics import PluginLyricsResult
from services.lyrics.lyrics_service import LyricsService


def test_lyrics_service_merges_plugin_sources(monkeypatch):
    fake_plugin_source = SimpleNamespace(
        display_name="LRCLIB",
        search=lambda *_args, **_kwargs: [
            PluginLyricsResult(
                id="song-1",
                title="Song 1",
                artist="Singer 1",
                source="lrclib",
                lyrics="[00:01.00]line",
            )
        ],
        get_lyrics=lambda result: result.lyrics,
    )
    fake_manager = SimpleNamespace(
        registry=SimpleNamespace(lyrics_sources=lambda: [fake_plugin_source])
    )

    monkeypatch.setattr(
        LyricsService,
        "_get_builtin_sources",
        classmethod(lambda cls: []),
    )
    monkeypatch.setattr(
        "app.bootstrap.Bootstrap.instance",
        lambda: SimpleNamespace(plugin_manager=fake_manager),
    )

    results = LyricsService.search_songs("Song 1", "Singer 1")

    assert any(item["source"] == "lrclib" for item in results)


def test_builtin_lyrics_sources_exclude_plugin_owned_sources():
    sources = LyricsService._get_builtin_sources()
    names = {source.name for source in sources}

    assert "LRCLIB" not in names
    assert "QQMusic" not in names
    assert "Kugou" not in names
    assert "NetEase" not in names
    assert names == set()

from types import SimpleNamespace

from system.plugins.qqmusic_lyrics_helpers import download_qqmusic_lyrics


def test_download_qqmusic_lyrics_uses_registered_plugin_source(monkeypatch):
    source = SimpleNamespace(
        source="qqmusic",
        get_lyrics_by_song_id=lambda song_id: f"lyrics:{song_id}",
    )
    fake_manager = SimpleNamespace(
        registry=SimpleNamespace(lyrics_sources=lambda: [source])
    )
    monkeypatch.setattr(
        "app.bootstrap.Bootstrap.instance",
        lambda: SimpleNamespace(plugin_manager=fake_manager),
    )

    assert download_qqmusic_lyrics("mid123") == "lyrics:mid123"

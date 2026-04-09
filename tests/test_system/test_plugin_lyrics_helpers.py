from types import SimpleNamespace

from system.plugins.online_lyrics_helpers import download_online_lyrics


def test_download_online_lyrics_uses_registered_plugin_source(monkeypatch):
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

    assert download_online_lyrics("mid123", provider_id="qqmusic") == "lyrics:mid123"

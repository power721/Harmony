from types import SimpleNamespace

from system.plugins.qqmusic_cover_helpers import (
    get_qqmusic_artist_cover_url,
    get_qqmusic_cover_url,
)


def test_get_qqmusic_cover_url_uses_registered_plugin_source(monkeypatch):
    source = SimpleNamespace(
        source="qqmusic",
        get_cover_url=lambda **kwargs: f"cover:{kwargs.get('album_mid') or kwargs.get('mid')}",
    )
    fake_manager = SimpleNamespace(
        registry=SimpleNamespace(cover_sources=lambda: [source])
    )
    monkeypatch.setattr(
        "app.bootstrap.Bootstrap.instance",
        lambda: SimpleNamespace(plugin_manager=fake_manager),
    )

    assert get_qqmusic_cover_url(album_mid="album123", size=500) == "cover:album123"


def test_get_qqmusic_artist_cover_url_uses_registered_plugin_source(monkeypatch):
    source = SimpleNamespace(
        source="qqmusic",
        get_artist_cover_url=lambda singer_mid, size=500: f"artist:{singer_mid}:{size}",
    )
    fake_manager = SimpleNamespace(
        registry=SimpleNamespace(artist_cover_sources=lambda: [source])
    )
    monkeypatch.setattr(
        "app.bootstrap.Bootstrap.instance",
        lambda: SimpleNamespace(plugin_manager=fake_manager),
    )

    assert get_qqmusic_artist_cover_url("singer123", size=500) == "artist:singer123:500"

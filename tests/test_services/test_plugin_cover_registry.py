from types import SimpleNamespace

from services.metadata.cover_service import CoverService


def test_cover_service_merges_plugin_cover_sources(monkeypatch):
    fake_cover = SimpleNamespace(source_id="qqmusic-cover")
    fake_artist_cover = SimpleNamespace(source_id="qqmusic-artist-cover")
    fake_registry = SimpleNamespace(
        cover_sources=lambda: [fake_cover],
        artist_cover_sources=lambda: [fake_artist_cover],
    )
    fake_manager = SimpleNamespace(registry=fake_registry)

    monkeypatch.setattr(
        "app.bootstrap.Bootstrap.instance",
        lambda: SimpleNamespace(plugin_manager=fake_manager),
    )
    monkeypatch.setattr(
        CoverService,
        "_get_builtin_sources",
        lambda self: [],
    )
    monkeypatch.setattr(
        CoverService,
        "_get_builtin_artist_sources",
        lambda self: [],
    )

    service = CoverService(http_client=SimpleNamespace(), sources=None)

    assert service._get_sources() == [fake_cover]
    assert service._get_artist_sources() == [fake_artist_cover]

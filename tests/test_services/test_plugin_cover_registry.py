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


def test_builtin_cover_sources_exclude_plugin_owned_sources():
    service = CoverService(http_client=SimpleNamespace(), sources=None)

    names = {source.name for source in service._get_builtin_sources()}
    artist_names = {source.name for source in service._get_builtin_artist_sources()}

    assert "NetEase" not in names
    assert "NetEase" not in artist_names
    assert "QQMusic" not in names
    assert "QQMusic" not in artist_names
    assert "iTunes" not in names
    assert "iTunes" not in artist_names
    assert "Last.fm" not in names

from types import SimpleNamespace
from unittest.mock import MagicMock

from services.download.online_download_gateway import OnlineDownloadGateway


def _build_gateway(tmp_path, provider=None, event_bus=None):
    manager = SimpleNamespace(
        registry=SimpleNamespace(
            online_providers=lambda: [provider] if provider is not None else []
        )
    )
    return OnlineDownloadGateway(
        config_manager=SimpleNamespace(
            get_online_music_download_dir=lambda: str(tmp_path)
        ),
        plugin_manager=manager,
        event_bus=event_bus,
    )


def test_get_cached_path_uses_quality_extension_mapping(tmp_path):
    gateway = _build_gateway(tmp_path)

    assert gateway.get_cached_path("song", "ogg_320") == str(tmp_path / "song.ogg")
    assert gateway.get_cached_path("song", "aac_192") == str(tmp_path / "song.m4a")
    assert gateway.get_cached_path("song", "flac") == str(tmp_path / "song.flac")


def test_get_provider_matches_provider_id(tmp_path):
    qq_provider = MagicMock(provider_id="qqmusic")
    netease_provider = MagicMock(provider_id="netease")
    manager = SimpleNamespace(
        registry=SimpleNamespace(
            online_providers=lambda: [qq_provider, netease_provider]
        )
    )
    gateway = OnlineDownloadGateway(
        config_manager=SimpleNamespace(
            get_online_music_download_dir=lambda: str(tmp_path)
        ),
        plugin_manager=manager,
    )

    assert gateway._get_provider("netease") is netease_provider
    assert gateway._get_provider("missing") is None


def test_get_provider_treats_legacy_online_placeholder_as_unspecified_when_single_provider(tmp_path):
    provider = MagicMock(provider_id="qqmusic")
    gateway = _build_gateway(tmp_path, provider=provider)

    assert gateway._get_provider("online") is provider


def test_get_download_qualities_is_provider_aware(tmp_path):
    provider = MagicMock()
    provider.provider_id = "qqmusic"
    provider.get_download_qualities.return_value = [
        {"value": "flac", "label": "FLAC"},
        "320",
    ]
    gateway = _build_gateway(tmp_path, provider=provider)

    qualities = gateway.get_download_qualities("song", provider_id="qqmusic")

    assert qualities == [
        {"value": "flac", "label": "FLAC"},
        {"value": "320", "label": "320"},
    ]
    provider.get_download_qualities.assert_called_once_with("song")


def test_get_cached_path_prefers_existing_downloaded_file(tmp_path):
    existing_path = tmp_path / "song.ogg"
    existing_path.write_bytes(b"data")
    gateway = _build_gateway(tmp_path)

    assert gateway.is_cached("song", "flac") is True
    assert gateway.get_cached_path("song", "flac") == str(existing_path)


def test_get_cached_path_is_namespaced_by_provider(tmp_path):
    gateway = _build_gateway(tmp_path)

    assert gateway.get_cached_path("song", "flac", provider_id="qqmusic") == str(
        tmp_path / "qqmusic" / "song.flac"
    )


def test_download_delegates_to_provider_and_emits_completed(tmp_path):
    event_bus = MagicMock()
    provider = MagicMock()
    provider.provider_id = "qqmusic"
    local_path = str(tmp_path / "song.ogg")
    provider.download_track.return_value = {
        "local_path": local_path,
        "quality": "ogg_320",
    }
    gateway = _build_gateway(tmp_path, provider=provider, event_bus=event_bus)

    actual_path = gateway.download("song", provider_id="qqmusic", quality="flac")

    assert actual_path == local_path
    provider.download_track.assert_called_once_with(
        track_id="song",
        quality="flac",
        target_dir=str(tmp_path / "qqmusic"),
        progress_callback=None,
        force=False,
    )
    event_bus.download_completed.emit.assert_called_once_with(
        "song", local_path
    )


def test_download_records_actual_quality_for_ui_status(tmp_path):
    provider = MagicMock()
    provider.provider_id = "qqmusic"
    provider.download_track.return_value = {
        "local_path": str(tmp_path / "song.ogg"),
        "quality": "ogg_320",
    }
    gateway = _build_gateway(tmp_path, provider=provider)

    gateway.download("song", provider_id="qqmusic", quality="flac")

    assert gateway.pop_last_download_quality("song") == "ogg_320"
    assert gateway.pop_last_download_quality("song") is None


def test_force_download_prefers_provider_redownload_api(tmp_path):
    provider = MagicMock()
    provider.provider_id = "qqmusic"
    provider.redownload_track.return_value = {
        "local_path": str(tmp_path / "qqmusic" / "song.flac"),
        "quality": "flac",
    }
    gateway = _build_gateway(tmp_path, provider=provider)

    local_path = gateway.download("song", provider_id="qqmusic", quality="flac", force=True)

    assert local_path == str(tmp_path / "qqmusic" / "song.flac")
    provider.redownload_track.assert_called_once_with(
        track_id="song",
        quality="flac",
        target_dir=str(tmp_path / "qqmusic"),
        progress_callback=None,
    )
    provider.download_track.assert_not_called()


def test_delete_cached_file_removes_provider_namespaced_cache(tmp_path):
    gateway = _build_gateway(tmp_path)
    provider_file = tmp_path / "qqmusic" / "song.flac"
    provider_file.parent.mkdir()
    provider_file.write_bytes(b"data")

    deleted = gateway.delete_cached_file("song")

    assert deleted is True
    assert provider_file.exists() is False

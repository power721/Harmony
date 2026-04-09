from types import SimpleNamespace

from plugins.builtin.qqmusic.lib.plugin_online_download_service import PluginOnlineDownloadService


def _make_service(tmp_path):
    context = SimpleNamespace(http=SimpleNamespace(stream=None))
    return PluginOnlineDownloadService(
        context=context,
        config_manager=None,
        credential_provider=None,
        online_music_service=None,
        download_dir=str(tmp_path),
    )


def test_is_cached_accepts_provider_id(tmp_path):
    service = _make_service(tmp_path)

    assert service.is_cached("song-mid", provider_id="qqmusic") is False


def test_get_cached_path_accepts_provider_id(tmp_path):
    service = _make_service(tmp_path)

    path = service.get_cached_path("song-mid", provider_id="qqmusic")

    assert path.endswith("song-mid.mp3")

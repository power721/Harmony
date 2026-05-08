from unittest.mock import MagicMock

from plugins.builtin.qqmusic.lib.plugin_online_music_service import PluginOnlineMusicService
from plugins.builtin.qqmusic.lib.qqmusic_client import QQMusicClient
from plugins.builtin.qqmusic.lib.qqmusic_service import QQMusicService


def test_get_song_fav_status_uses_song_mid_payload():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        return {"000XOvoA0RVaYt": True}

    client._make_request = fake_make_request

    result = client.get_song_fav_status(["000XOvoA0RVaYt"])

    assert result == {"000XOvoA0RVaYt": True}
    assert captured == {
        "module": "music.musicasset.SongFavRead",
        "method": "IsSongFanByMid",
        "params": {"v_songMid": ["000XOvoA0RVaYt"]},
        "retry": False,
        "use_sign": False,
    }


def test_get_song_fav_status_returns_false_map_for_code_1000():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        assert module == "music.musicasset.SongFavRead"
        assert method == "IsSongFanByMid"
        assert params == {"v_songMid": ["000XOvoA0RVaYt", "001a1b2c3d4e5f"]}
        return {"__qqmusic_code__": 1000}

    client._make_request = fake_make_request

    result = client.get_song_fav_status(["000XOvoA0RVaYt", "001a1b2c3d4e5f"])

    assert result == {
        "000XOvoA0RVaYt": False,
        "001a1b2c3d4e5f": False,
    }


def test_get_song_fav_status_extracts_m_fan_from_nested_response():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        assert module == "music.musicasset.SongFavRead"
        assert method == "IsSongFanByMid"
        return {
            "m_fan": {
                "000XOvoA0RVaYt": True,
                "001a1b2c3d4e5f": False,
            },
            "source": 0,
        }

    client._make_request = fake_make_request

    result = client.get_song_fav_status(["000XOvoA0RVaYt", "001a1b2c3d4e5f"])

    assert result == {
        "000XOvoA0RVaYt": True,
        "001a1b2c3d4e5f": False,
    }


def test_fav_playlist_uses_tid_payload_for_remote_write():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        return {"ok": True}

    client._make_request = fake_make_request

    result = client.fav_playlist("12345")

    assert result == {"ok": True}
    assert captured == {
        "module": "music.musicasset.PlaylistFavWrite",
        "method": "FavPlaylist",
        "params": {"uin": "1", "v_tid": [12345], "opertype": 1},
        "retry": False,
        "use_sign": False,
    }


def test_unfav_playlist_uses_tid_payload_for_remote_write():
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        return {"ok": True}

    client._make_request = fake_make_request

    result = client.unfav_playlist("12345")

    assert result == {"ok": True}
    assert captured == {
        "module": "music.musicasset.PlaylistFavWrite",
        "method": "FavPlaylist",
        "params": {"uin": "1", "v_tid": [12345], "opertype": 2},
        "retry": False,
        "use_sign": False,
    }


def test_qqmusic_service_get_song_fav_status_filters_empty_mids():
    service = QQMusicService({"musicid": "1", "musickey": "secret"})
    service.client.get_song_fav_status = lambda mids: {mid: mid == "fav-mid" for mid in mids}

    result = service.get_song_fav_status(["fav-mid", "", "fav-mid", "plain-mid"])

    assert result == {
        "fav-mid": True,
        "plain-mid": False,
    }


def test_plugin_online_music_service_returns_remote_favorite_mid_set():
    provider = type(
        "ProviderStub",
        (),
        {"get_song_fav_status": lambda self, mids: {"fav-mid": True, "plain-mid": False}},
    )()
    service = PluginOnlineMusicService(context=MagicMock(), credential_provider=provider)

    result = service.get_song_favorite_mids(["fav-mid", "plain-mid"])

    assert result == {"fav-mid"}

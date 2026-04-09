from plugins.builtin.qqmusic.lib.qqmusic_client import QQMusicClient


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

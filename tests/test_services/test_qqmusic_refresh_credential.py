from plugins.builtin.qqmusic.lib.qqmusic_client import QQMusicClient


def test_refresh_credential_uses_reference_login_payload_and_merges_response(monkeypatch):
    client = QQMusicClient(
        {
            "musicid": "123",
            "musickey": "old-key",
            "login_type": 2,
            "openid": "openid-old",
            "access_token": "access-old",
            "unionid": "union-old",
            "refresh_key": "refresh-key-old",
            "refresh_token": "refresh-token-old",
        }
    )
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        return {
            "musickey": "new-key",
            "musicid": 456,
            "refresh_key": "refresh-key-new",
            "refresh_token": "refresh-token-new",
            "openid": "openid-new",
            "access_token": "access-new",
            "unionid": "union-new",
            "keyExpiresIn": 7200,
        }

    monkeypatch.setattr(client, "_make_request", fake_make_request)

    before = 1000
    monkeypatch.setattr("plugins.builtin.qqmusic.lib.qqmusic_client.time.time", lambda: before)

    refreshed = client.refresh_credential()

    assert captured == {
        "module": "music.login.LoginServer",
        "method": "Login",
        "params": {
            "openid": "openid-old",
            "access_token": "access-old",
            "unionid": "union-old",
            "refresh_key": "refresh-key-old",
            "refresh_token": "refresh-token-old",
            "musickey": "old-key",
            "musicid": 123,
            "loginMode": 2,
        },
        "retry": False,
        "use_sign": False,
    }
    assert refreshed["musickey"] == "new-key"
    assert refreshed["musicid"] == 456
    assert refreshed["refresh_key"] == "refresh-key-new"
    assert refreshed["refresh_token"] == "refresh-token-new"
    assert refreshed["openid"] == "openid-new"
    assert refreshed["access_token"] == "access-new"
    assert refreshed["unionid"] == "union-new"
    assert refreshed["musickey_createtime"] == before
    assert refreshed["key_expires_in"] == 7200

from plugins.builtin.qqmusic.lib.qqmusic_client import QQMusicClient


def test_send_phone_auth_code_uses_reference_payload():
    client = QQMusicClient()
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False, comm=None, platform=None):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        captured["comm"] = comm
        captured["platform"] = platform
        return {"code": 0}

    client._make_request = fake_make_request

    result = client.send_phone_auth_code("13000000000")

    assert result == {"code": 0}
    assert captured == {
        "module": "music.login.LoginServer",
        "method": "SendPhoneAuthCode",
        "params": {
            "tmeAppid": "qqmusic",
            "phoneNo": "13000000000",
            "areaCode": "86",
        },
        "retry": False,
        "use_sign": False,
        "comm": {"tmeLoginMethod": 3},
        "platform": "android",
    }


def test_phone_authorize_uses_reference_payload():
    client = QQMusicClient()
    captured = {}

    def fake_make_request(module, method, params, _retry=False, use_sign=False, comm=None, platform=None):
        captured["module"] = module
        captured["method"] = method
        captured["params"] = params
        captured["retry"] = _retry
        captured["use_sign"] = use_sign
        captured["comm"] = comm
        captured["platform"] = platform
        return {
            "musicid": 123,
            "musickey": "secret",
            "refresh_key": "refresh-key",
            "refresh_token": "refresh-token",
            "loginType": 0,
            "encryptUin": "enc-uin",
        }

    client._make_request = fake_make_request

    result = client.phone_authorize("13000000000", "123456")

    assert captured == {
        "module": "music.login.LoginServer",
        "method": "Login",
        "params": {
            "code": "123456",
            "phoneNo": "13000000000",
            "areaCode": "86",
            "loginMode": 1,
        },
        "retry": False,
        "use_sign": False,
        "comm": {"tmeLoginMethod": 3, "tmeLoginType": 0},
        "platform": "android",
    }
    assert result["musicid"] == "123"
    assert result["musickey"] == "secret"
    assert result["login_type"] == 0
    assert result["encrypt_uin"] == "enc-uin"

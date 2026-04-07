from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.legacy.client import QQMusicClient


def test_verify_login_accepts_hostname_when_profile_request_succeeds(monkeypatch):
    client = QQMusicClient({"musicid": "1", "musickey": "secret"})
    monkeypatch.setattr(
        client,
        "_make_request",
        Mock(return_value={"code": 0, "data": {"hostname": "Tester"}}),
    )
    monkeypatch.setattr(client, "_verify_login_fallback", Mock())

    result = client.verify_login()

    assert result["valid"] is True
    assert result["nick"] == "Tester"

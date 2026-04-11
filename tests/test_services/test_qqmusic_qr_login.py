from unittest.mock import Mock

from plugins.builtin.qqmusic.lib.qr_login import Credential, QQMusicQRLogin


class _Response:
    def __init__(self, *, cookies=None, headers=None, history=None):
        self.cookies = cookies or {}
        self.headers = headers or {}
        self.history = history or []


def test_authorize_qq_qr_forwards_check_sig_cookies_to_oauth_request():
    session = Mock()
    session.headers = {}
    session.mount = Mock()
    session.cookies = {}

    check_sig_response = _Response(
        cookies={"p_skey": "p-skey", "ptcz": "ptcz-token"},
    )
    authorize_response = _Response(
        headers={"Location": "https://y.qq.com/portal/wx_redirect.html?code=auth-code&state=state"},
    )
    session.get.return_value = check_sig_response
    session.post.return_value = authorize_response

    client = QQMusicQRLogin(http_client=session)
    client._qq_connect_login = Mock(return_value=Credential(musicid=1, musickey="secret"))

    credential = client._authorize_qq_qr("12345", "sigx-value")

    assert credential.musicid == 1
    session.post.assert_called_once()
    assert session.post.call_args.kwargs["cookies"] == {
        "p_skey": "p-skey",
        "ptcz": "ptcz-token",
    }
    client._qq_connect_login.assert_called_once_with("auth-code")

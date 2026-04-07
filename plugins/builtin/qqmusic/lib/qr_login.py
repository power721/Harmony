from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter


def create_qq_session(pool_size: int = 20, pool_block: bool = True) -> requests.Session:
    session = requests.Session()
    adapter = HTTPAdapter(
        pool_connections=pool_size,
        pool_maxsize=pool_size,
        pool_block=pool_block,
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def hash33(s: str, h: int = 0) -> int:
    for c in s:
        h = (h << 5) + h + ord(c)
    return 2147483647 & h


class QRLoginType(Enum):
    QQ = "qq"
    WX = "wx"


class QRCodeLoginEvents(Enum):
    DONE = (0, 405)
    SCAN = (66, 408)
    CONF = (67, 404)
    TIMEOUT = (65, None)
    REFUSE = (68, 403)
    OTHER = (None, None)

    @classmethod
    def get_by_value(cls, value: int):
        for member in cls:
            if value in member.value:
                return member
        return cls.OTHER


@dataclass
class QR:
    data: bytes
    qr_type: QRLoginType
    identifier: str


@dataclass
class Credential:
    openid: str = ""
    refresh_token: str = ""
    access_token: str = ""
    expired_at: int = 0
    musicid: int = 0
    musickey: str = ""
    unionid: str = ""
    str_musicid: str = ""
    refresh_key: str = ""
    encrypt_uin: str = ""
    login_type: int = 0
    extra_fields: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.login_type:
            self.login_type = 1 if self.musickey.startswith("W_X") else 2

    def as_dict(self) -> Dict[str, Any]:
        return {
            "openid": self.openid,
            "refresh_token": self.refresh_token,
            "access_token": self.access_token,
            "expired_at": self.expired_at,
            "musicid": str(self.musicid),
            "musickey": self.musickey,
            "unionid": self.unionid,
            "str_musicid": self.str_musicid,
            "refresh_key": self.refresh_key,
            "encrypt_uin": self.encrypt_uin,
            "login_type": self.login_type,
            "loginType": self.login_type,
            "encryptUin": self.encrypt_uin,
            **self.extra_fields,
        }

    @classmethod
    def from_cookies_dict(cls, cookies: Dict[str, Any]) -> "Credential":
        _musicid = int(cookies.pop("musicid", 0) or 0)
        return cls(
            openid=cookies.pop("openid", ""),
            refresh_token=cookies.pop("refresh_token", ""),
            access_token=cookies.pop("access_token", ""),
            expired_at=cookies.pop("expired_at", 0),
            musicid=_musicid,
            musickey=cookies.pop("musickey", ""),
            unionid=cookies.pop("unionid", ""),
            str_musicid=cookies.pop("str_musicid", str(_musicid)),
            refresh_key=cookies.pop("refresh_key", ""),
            encrypt_uin=cookies.pop("encryptUin", ""),
            login_type=cookies.pop("loginType", 0),
            extra_fields=cookies,
        )


class QQMusicQRLogin:
    QQ_QR_URL = "https://ssl.ptlogin2.qq.com/ptqrshow"
    QQ_CHECK_URL = "https://ssl.ptlogin2.qq.com/ptqrlogin"
    QQ_AUTHORIZE_URL = "https://ssl.ptlogin2.graph.qq.com/check_sig"
    QQ_OAUTH_URL = "https://graph.qq.com/oauth2.0/authorize"
    WX_QR_URL = "https://open.weixin.qq.com/connect/qrconnect"
    WX_CHECK_URL = "https://lp.open.weixin.qq.com/connect/l/qrconnect"
    WX_QR_IMAGE_URL = "https://open.weixin.qq.com/connect/qrcode/{uuid}"
    MUSIC_API_URL = "https://u.y.qq.com/cgi-bin/musicu.fcg"

    def __init__(self):
        self._session = create_qq_session()
        self._session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0.0.0 Safari/537.36"
                ),
                "Referer": "https://y.qq.com/",
            }
        )

    def get_qrcode(self, login_type: QRLoginType = QRLoginType.QQ) -> Optional[QR]:
        if login_type == QRLoginType.WX:
            return self._get_wx_qr()
        return self._get_qq_qr()

    def _get_qq_qr(self) -> Optional[QR]:
        try:
            response = self._session.get(
                self.QQ_QR_URL,
                params={
                    "appid": "716027609",
                    "e": "2",
                    "l": "M",
                    "s": "3",
                    "d": "72",
                    "v": "4",
                    "t": str(random.random()),
                    "daid": "383",
                    "pt_3rd_aid": "100497308",
                },
                headers={"Referer": "https://xui.ptlogin2.qq.com/"},
                timeout=10,
            )
            qrsig = response.cookies.get("qrsig")
            if not qrsig:
                return None
            return QR(response.content, QRLoginType.QQ, qrsig)
        except Exception:
            return None

    def _get_wx_qr(self) -> Optional[QR]:
        try:
            response = self._session.get(
                self.WX_QR_URL,
                params={
                    "appid": "wx48db31d50e334801",
                    "redirect_uri": "https://y.qq.com/portal/wx_redirect.html?login_type=2&surl=https://y.qq.com/",
                    "response_type": "code",
                    "scope": "snsapi_login",
                    "state": "STATE",
                    "href": "https://y.qq.com/mediastyle/music_v17/src/css/popup_wechat.css#wechat_redirect",
                },
                timeout=10,
            )
            match = re.findall(r"uuid=(.+?)\"", response.text)
            if not match:
                return None
            uuid = match[0]
            qr_response = self._session.get(
                self.WX_QR_IMAGE_URL.format(uuid=uuid),
                headers={"Referer": "https://open.weixin.qq.com/connect/qrconnect"},
                timeout=10,
            )
            return QR(qr_response.content, QRLoginType.WX, uuid)
        except Exception:
            return None

    def check_qrcode(self, qrcode: QR) -> tuple[QRCodeLoginEvents, Optional[Credential]]:
        if qrcode.qr_type == QRLoginType.WX:
            return self._check_wx_qr(qrcode)
        return self._check_qq_qr(qrcode)

    def _check_qq_qr(self, qrcode: QR) -> tuple[QRCodeLoginEvents, Optional[Credential]]:
        qrsig = qrcode.identifier
        try:
            response = self._session.get(
                self.QQ_CHECK_URL,
                params={
                    "u1": "https://graph.qq.com/oauth2.0/login_jump",
                    "ptqrtoken": hash33(qrsig),
                    "ptredirect": "0",
                    "h": "1",
                    "t": "1",
                    "g": "1",
                    "from_ui": "1",
                    "ptlang": "2052",
                    "action": f"0-0-{time.time() * 1000}",
                    "js_ver": "20102616",
                    "js_type": "1",
                    "pt_uistyle": "40",
                    "aid": "716027609",
                    "daid": "383",
                    "pt_3rd_aid": "100497308",
                    "has_onekey": "1",
                },
                headers={
                    "Referer": "https://xui.ptlogin2.qq.com/",
                    "Cookie": f"qrsig={qrsig}",
                },
                timeout=10,
            )
        except requests.RequestException:
            return QRCodeLoginEvents.SCAN, None

        match = re.search(r"ptuiCB\((.*?)\)", response.text)
        if not match:
            return QRCodeLoginEvents.OTHER, None

        data = [p.strip("'") for p in match.group(1).split(",")]
        if not data:
            return QRCodeLoginEvents.OTHER, None
        code_str = data[0]
        if not code_str.isdigit():
            return QRCodeLoginEvents.OTHER, None
        event = QRCodeLoginEvents.get_by_value(int(code_str))
        if event == QRCodeLoginEvents.DONE:
            try:
                sigx = re.findall(r"&ptsigx=(.+?)&s_url", data[2])[0]
                uin = re.findall(r"&uin=(.+?)&service", data[2])[0]
                credential = self._authorize_qq_qr(uin, sigx)
                return event, credential
            except Exception:
                return QRCodeLoginEvents.OTHER, None
        return event, None

    def _check_wx_qr(self, qrcode: QR) -> tuple[QRCodeLoginEvents, Optional[Credential]]:
        uuid = qrcode.identifier
        try:
            response = self._session.get(
                self.WX_CHECK_URL,
                params={"uuid": uuid, "_": str(int(time.time()) * 1000)},
                headers={"Referer": "https://open.weixin.qq.com/"},
                timeout=10,
            )
        except requests.Timeout:
            return QRCodeLoginEvents.SCAN, None
        except requests.RequestException:
            return QRCodeLoginEvents.SCAN, None

        match = re.search(r"window\.wx_errcode=(\d+);window\.wx_code='([^']*)'", response.text)
        if not match:
            return QRCodeLoginEvents.OTHER, None
        wx_errcode = match.group(1)
        if not wx_errcode.isdigit():
            return QRCodeLoginEvents.OTHER, None
        event = QRCodeLoginEvents.get_by_value(int(wx_errcode))
        if event == QRCodeLoginEvents.DONE:
            wx_code = match.group(2)
            if not wx_code:
                return QRCodeLoginEvents.OTHER, None
            try:
                credential = self._authorize_wx_qr(wx_code)
                return event, credential
            except Exception:
                return QRCodeLoginEvents.OTHER, None
        return event, None

    def _authorize_qq_qr(self, uin: str, sigx: str) -> Credential:
        response = self._session.get(
            self.QQ_AUTHORIZE_URL,
            params={
                "uin": uin,
                "pttype": "1",
                "service": "ptqrlogin",
                "nodirect": "0",
                "ptsigx": sigx,
                "s_url": "https://graph.qq.com/oauth2.0/login_jump",
                "ptlang": "2052",
                "ptredirect": "100",
                "aid": "716027609",
                "daid": "383",
                "j_later": "0",
                "low_login_hour": "0",
                "regmaster": "0",
                "pt_login_type": "3",
                "pt_aid": "0",
                "pt_aaid": "16",
                "pt_light": "0",
                "pt_3rd_aid": "100497308",
            },
            headers={"Referer": "https://xui.ptlogin2.qq.com/"},
            allow_redirects=True,
            timeout=10,
        )
        p_skey = self._session.cookies.get("p_skey") or response.cookies.get("p_skey")
        if not p_skey and hasattr(response, "history"):
            for hist_response in response.history:
                if "p_skey" in hist_response.cookies:
                    p_skey = hist_response.cookies.get("p_skey")
                    break
                set_cookie = hist_response.headers.get("Set-Cookie", "")
                if "p_skey=" in set_cookie:
                    match = re.search(r"p_skey=([^;]+)", set_cookie)
                    if match:
                        p_skey = match.group(1)
                        break
        if not p_skey:
            raise ValueError("Failed to get p_skey")
        response = self._session.post(
            self.QQ_OAUTH_URL,
            data={
                "response_type": "code",
                "client_id": "100497308",
                "redirect_uri": "https://y.qq.com/portal/wx_redirect.html?login_type=1&surl=https://y.qq.com/",
                "scope": "get_user_info,get_app_friends",
                "state": "state",
                "switch": "",
                "from_ptlogin": "1",
                "src": "1",
                "update_auth": "1",
                "openapi": "1010_1030",
                "g_tk": hash33(p_skey, 5381),
                "auth_time": str(int(time.time()) * 1000),
                "ui": str(random.randint(100000, 999999)),
            },
            allow_redirects=False,
            timeout=10,
        )
        location = response.headers.get("Location", "")
        try:
            code = re.findall(r"(?<=code=)(.+?)(?=&)", location)[0]
        except IndexError as exc:
            raise ValueError("Failed to get code from OAuth redirect") from exc
        return self._qq_connect_login(code)

    def _qq_connect_login(self, code: str) -> Credential:
        request_data = {
            "comm": {
                "ct": "11",
                "cv": "13020508",
                "v": "13020508",
                "tmeAppID": "qqmusic",
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "uid": "3931641530",
                "tmeLoginType": "2",
            },
            "QQConnectLogin.LoginServer.QQLogin": {
                "module": "QQConnectLogin.LoginServer",
                "method": "QQLogin",
                "param": {"code": code},
            },
        }
        response = self._session.post(self.MUSIC_API_URL, json=request_data, timeout=30)
        response.raise_for_status()
        data = response.json()
        result = data.get("QQConnectLogin.LoginServer.QQLogin", {})
        if result.get("code") != 0:
            raise ValueError(f"QQ Login failed with code: {result.get('code')}")
        return Credential.from_cookies_dict(result.get("data", {}))

    def _authorize_wx_qr(self, code: str) -> Credential:
        request_data = {
            "comm": {
                "ct": "11",
                "cv": "13020508",
                "v": "13020508",
                "tmeAppID": "qqmusic",
                "format": "json",
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "uid": "3931641530",
                "tmeLoginType": "1",
            },
            "music.login.LoginServer.Login": {
                "module": "music.login.LoginServer",
                "method": "Login",
                "param": {
                    "code": code,
                    "strAppid": "wx48db31d50e334801",
                },
            },
        }
        response = self._session.post(self.MUSIC_API_URL, json=request_data, timeout=30)
        response.raise_for_status()
        data = response.json()
        result = data.get("music.login.LoginServer.Login", {})
        if result.get("code") != 0:
            raise ValueError(f"WeChat Login failed with code: {result.get('code')}")
        return Credential.from_cookies_dict(result.get("data", {}))

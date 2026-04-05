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

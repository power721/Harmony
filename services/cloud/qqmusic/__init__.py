"""
QQ Music service for searching and downloading music.
"""

from .qqmusic_service import QQMusicService
from .client import QQMusicClient
from .qr_login import (
    QQMusicQRLogin,
    QRLoginType,
    QRCodeLoginEvents,
    Credential,
    QR
)

__all__ = [
    'QQMusicService',
    'QQMusicClient',
    'QQMusicQRLogin',
    'QRLoginType',
    'QRCodeLoginEvents',
    'Credential',
    'QR'
]

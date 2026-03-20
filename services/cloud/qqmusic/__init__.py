"""
QQ Music service for searching and downloading music.
"""

from .qqmusic_service import QQMusicService
from .client import QQMusicClient
from .qr_login import QQMusicQRLogin, QRLoginType, QRLoginStatus

__all__ = [
    'QQMusicService',
    'QQMusicClient',
    'QQMusicQRLogin',
    'QRLoginType',
    'QRLoginStatus'
]

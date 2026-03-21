"""
Online music services.
"""

from .adapter import OnlineMusicAdapter
from .online_music_service import OnlineMusicService
from .download_service import OnlineDownloadService

__all__ = ['OnlineMusicAdapter', 'OnlineMusicService', 'OnlineDownloadService']

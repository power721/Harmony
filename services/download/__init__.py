"""
Download services module.

Provides unified download management for different sources:
- Online music (plugin providers)
- Cloud storage (Quark, Baidu, etc.)
"""

from .download_manager import DownloadManager
from .cache_cleaner_service import CacheCleanerService
from .online_download_gateway import OnlineDownloadGateway

__all__ = ['DownloadManager', 'CacheCleanerService', 'OnlineDownloadGateway']

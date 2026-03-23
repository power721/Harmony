"""
Download services module.

Provides unified download management for different sources:
- Online music (QQ Music, etc.)
- Cloud storage (Quark, Baidu, etc.)
"""

from .download_manager import DownloadManager

__all__ = ['DownloadManager']

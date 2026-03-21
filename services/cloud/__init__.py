"""
Cloud service module.
"""

from .download_service import CloudDownloadService
from .quark_service import QuarkDriveService
from .baidu_service import BaiduDriveService

__all__ = ['QuarkDriveService', 'BaiduDriveService', 'CloudDownloadService']

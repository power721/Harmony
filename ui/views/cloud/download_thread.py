"""
Cloud file download thread for background downloading.
"""

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QThread, Signal

from domain.cloud import CloudFile
from services.cloud.baidu_service import BaiduDriveService
from services.cloud.quark_service import QuarkDriveService
from utils.helpers import sanitize_filename

if TYPE_CHECKING:
    from system.config import ConfigManager

logger = logging.getLogger(__name__)


class CloudFileDownloadThread(QThread):
    """Thread for downloading cloud files.

    Handles:
    - Checking for existing files at database path
    - Checking for cached files in download directory
    - Downloading from cloud with size verification
    - Token updates for cloud providers
    """

    finished = Signal(str)  # Emits local file path
    token_updated = Signal(str)  # Emits updated access token
    file_exists = Signal(str)  # Emits local file path when file already exists

    def __init__(
            self,
            access_token: str,
            file: CloudFile,
            file_index: int = 0,
            audio_files: list = None,
            config_manager: "ConfigManager" = None,
            parent=None,
            db_local_path: str = None,
            provider: str = "quark",
    ):
        """Initialize download thread.

        Args:
            access_token: Cloud provider access token
            file: CloudFile to download
            file_index: Index in audio files list
            audio_files: List of audio files for playlist
            config_manager: Configuration manager for download directory
            parent: Parent QObject
            db_local_path: Known local path from database
            provider: Cloud provider ("quark" or "baidu")
        """
        super().__init__(parent)
        self._access_token = access_token
        self._file = file
        self._file_index = file_index
        self._audio_files = audio_files or []
        self._config_manager = config_manager
        self._db_local_path = db_local_path
        self._provider = provider

    def run(self):
        """Download file in background thread."""
        start_time = time.time()

        # First check if file exists at database path (may have been moved by file organization)
        if self._db_local_path:
            db_path = Path(self._db_local_path)
            if db_path.exists():
                file_size = db_path.stat().st_size
                expected_size = self._file.size if self._file.size else 0

                if expected_size > 0:
                    size_diff = abs(file_size - expected_size)
                    tolerance = expected_size * 0.01

                    if size_diff <= tolerance:
                        self.file_exists.emit(str(db_path))
                        return
                else:
                    self.file_exists.emit(str(db_path))
                    return

        # Get download directory from config
        if self._config_manager:
            download_dir = self._config_manager.get_cloud_download_dir()
        else:
            download_dir = "data/cloud_downloads"

        # Create download directory if it doesn't exist
        download_path = Path(download_dir)
        # Convert to absolute path
        if not download_path.is_absolute():
            download_path = Path.cwd() / download_path
        download_path.mkdir(parents=True, exist_ok=True)

        # Use original filename
        safe_filename = sanitize_filename(self._file.name)
        local_file_path = download_path / safe_filename

        # Check if file already exists and has correct size
        if local_file_path.exists():
            file_size = local_file_path.stat().st_size
            expected_size = self._file.size if self._file.size else 0

            # If we have expected size, verify it matches
            if expected_size > 0:
                # Allow 1% tolerance for file size differences (metadata, etc.)
                size_diff = abs(file_size - expected_size)
                tolerance = expected_size * 0.01  # 1% tolerance

                if size_diff <= tolerance:
                    # File size matches, use existing file
                    self.file_exists.emit(str(local_file_path))
                    return
                else:
                    # File size mismatch, need to re-download
                    logger.debug(f"[CloudFileDownloadThread] File size mismatch, re-downloading")
            else:
                # No size info available, use existing file
                self.file_exists.emit(str(local_file_path))
                return

        # Get download URL - select service based on provider
        service = BaiduDriveService if self._provider == "baidu" else QuarkDriveService
        # For Baidu, pass file path (metadata) for mediainfo API
        if self._provider == "baidu":
            result = service.get_download_url(
                self._access_token, self._file.file_id, self._file.metadata
            )
        else:
            result = service.get_download_url(
                self._access_token, self._file.file_id
            )

        # Handle tuple return value
        if isinstance(result, tuple):
            url, updated_token = result
        else:
            url, updated_token = result, None

        # Emit token update signal if changed
        if updated_token:
            self.token_updated.emit(updated_token)

        if url:
            # If file exists and size mismatch, delete it first
            if local_file_path.exists():
                expected_size = self._file.size if self._file.size else 0
                if expected_size > 0:
                    actual_size = local_file_path.stat().st_size
                    size_diff = abs(actual_size - expected_size)
                    tolerance = expected_size * 0.01

                    if size_diff > tolerance:
                        local_file_path.unlink()

            # Download to persistent location
            download_start = time.time()
            service = BaiduDriveService if self._provider == "baidu" else QuarkDriveService
            success = service.download_file(
                url, str(local_file_path), self._access_token
            )

            if success:
                # Verify downloaded file size
                if local_file_path.exists():
                    downloaded_size = local_file_path.stat().st_size
                    expected_size = self._file.size if self._file.size else 0

                    if expected_size > 0:
                        size_diff = abs(downloaded_size - expected_size)
                        tolerance = expected_size * 0.01  # 1% tolerance

                        if size_diff <= tolerance:
                            self.finished.emit(str(local_file_path))
                            return
                        else:
                            # Delete incomplete file
                            local_file_path.unlink()
                            logger.error(
                                f"[CloudFileDownloadThread] Download size mismatch, "
                                f"expected {expected_size}, got {downloaded_size}"
                            )
                            self.finished.emit("")
                    else:
                        # No size info, assume download was successful
                        self.finished.emit(str(local_file_path))
                        return
                else:
                    logger.error("[CloudFileDownloadThread] File does not exist after download")
                    self.finished.emit("")
            else:
                logger.error("[CloudFileDownloadThread] Download failed")
                self.finished.emit("")
        else:
            logger.error(f"[CloudFileDownloadThread] Failed to get download URL")
            self.finished.emit("")

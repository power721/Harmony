"""
Cloud download service for managing cloud file downloads.

This service provides a unified interface for downloading files from cloud storage,
with support for caching, progress tracking, and download cancellation.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QThread

if TYPE_CHECKING:
    from domain.cloud import CloudFile, CloudAccount

# Configure logging
logger = logging.getLogger(__name__)


class CloudDownloadWorker(QThread):
    """Worker thread for downloading a single cloud file."""

    download_progress = Signal(str, int, int)  # file_id, current_bytes, total_bytes
    download_completed = Signal(str, str)  # file_id, local_path
    download_error = Signal(str, str)  # file_id, error_message

    def __init__(
        self,
        cloud_file: "CloudFile",
        account: "CloudAccount",
        download_dir: str,
        parent=None
    ):
        super().__init__(parent)
        self._cloud_file = cloud_file
        self._account = account
        self._download_dir = download_dir
        self._cancelled = False

    def cancel(self):
        """Cancel the download."""
        self._cancelled = True

    def run(self):
        """Download the file."""
        import time
        from services.cloud.quark_service import QuarkDriveService
        from utils.helpers import sanitize_filename

        start_time = time.time()
        file_id = self._cloud_file.file_id

        try:
            # Create download directory
            download_path = Path(self._download_dir)
            if not download_path.is_absolute():
                download_path = Path.cwd() / download_path
            download_path.mkdir(parents=True, exist_ok=True)

            # Determine local file path
            safe_filename = sanitize_filename(self._cloud_file.name)
            local_path = download_path / safe_filename

            # Check if file already exists
            if local_path.exists() and self._cloud_file.size:
                actual_size = local_path.stat().st_size
                size_diff = abs(actual_size - self._cloud_file.size)
                tolerance = self._cloud_file.size * 0.01

                if size_diff <= tolerance:
                    self.download_completed.emit(file_id, str(local_path))
                    return

            # Get download URL
            result = QuarkDriveService.get_download_url(
                self._account.access_token, file_id
            )

            if isinstance(result, tuple):
                url, updated_token = result
            else:
                url, updated_token = result, None

            if not url:
                self.download_error.emit(file_id, "Failed to get download URL")
                return

            if self._cancelled:
                return

            # Download the file
            success = self._download_file(url, str(local_path))

            if self._cancelled:
                # Clean up partial download
                if local_path.exists():
                    local_path.unlink()
                return

            if success:
                elapsed = time.time() - start_time
                self.download_completed.emit(file_id, str(local_path))
            else:
                self.download_error.emit(file_id, "Download failed")

        except Exception as e:
            logger.error(f"[CloudDownloadWorker] Error: {e}", exc_info=True)
            self.download_error.emit(file_id, str(e))

    def _download_file(self, url: str, dest_path: str) -> bool:
        """Download file from URL to destination."""
        import requests

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://pan.quark.cn/",
                "Cookie": self._account.access_token
            }

            response = requests.get(url, headers=headers, timeout=60, stream=True)

            if response.status_code != 200:
                logger.error(f"[CloudDownloadWorker] HTTP {response.status_code}")
                return False

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self._cancelled:
                        return False

                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

                        # Emit progress periodically
                        if total_size > 0 and downloaded % (1024 * 1024) == 0:
                            self.download_progress.emit(
                                self._cloud_file.file_id,
                                downloaded,
                                total_size
                            )

            return True

        except Exception as e:
            logger.error(f"[CloudDownloadWorker] Download error: {e}")
            return False


class CloudDownloadService(QObject):
    """
    Centralized service for managing cloud file downloads.

    This is a singleton service that provides:
    - Unified download management
    - File caching with size verification
    - Progress tracking
    - Download cancellation
    - Token update handling

    Signals:
        download_started: Emitted when a download starts (file_id)
        download_progress: Emitted during download (file_id, current, total)
        download_completed: Emitted when download finishes (file_id, local_path)
        download_error: Emitted when download fails (file_id, error)
        token_updated: Emitted when access token is updated (new_token)
    """

    download_started = Signal(str)  # file_id
    download_progress = Signal(str, int, int)  # file_id, current, total
    download_completed = Signal(str, str)  # file_id, local_path
    download_error = Signal(str, str)  # file_id, error
    token_updated = Signal(str)  # new_token

    _instance = None

    @classmethod
    def instance(cls) -> "CloudDownloadService":
        """Get the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        """Initialize the download service."""
        super().__init__(parent)
        self._active_downloads: Dict[str, CloudDownloadWorker] = {}
        self._cached_paths: Dict[str, str] = {}  # file_id -> local_path
        self._download_dir = "data/cloud_downloads"

    def set_download_dir(self, directory: str):
        """Set the download directory."""
        self._download_dir = directory

    def download_file(
        self,
        cloud_file: "CloudFile",
        account: "CloudAccount",
        priority: bool = False
    ) -> bool:
        """
        Start downloading a cloud file.

        Args:
            cloud_file: CloudFile to download
            account: CloudAccount for authentication
            priority: If True, cancel any existing download for this file

        Returns:
            True if download started, False if already downloading
        """
        file_id = cloud_file.file_id

        # Check if already downloading
        if file_id in self._active_downloads:
            if priority:
                self.cancel_download(file_id)
            else:
                return False

        # Check cache
        cached_path = self.get_cached_path(file_id, cloud_file, account)
        if cached_path:
            self._cached_paths[file_id] = cached_path
            self.download_completed.emit(file_id, cached_path)
            return True

        # Start download
        worker = CloudDownloadWorker(
            cloud_file, account, self._download_dir, self
        )

        # Connect signals
        worker.download_progress.connect(
            lambda fid, cur, tot: self.download_progress.emit(fid, cur, tot)
        )
        worker.download_completed.connect(self._on_download_completed)
        worker.download_error.connect(self._on_download_error)

        self._active_downloads[file_id] = worker
        self.download_started.emit(file_id)
        worker.start()

        return True

    def cancel_download(self, file_id: str) -> bool:
        """
        Cancel an active download.

        Args:
            file_id: File ID to cancel

        Returns:
            True if download was cancelled
        """
        if file_id in self._active_downloads:
            worker = self._active_downloads[file_id]
            worker.cancel()
            worker.wait(1000)  # Wait up to 1 second
            del self._active_downloads[file_id]
            return True
        return False

    def get_cached_path(
        self,
        file_id: str,
        cloud_file: Optional["CloudFile"] = None,
        account: Optional["CloudAccount"] = None
    ) -> Optional[str]:
        """
        Check if a file is already downloaded and cached.

        Args:
            file_id: Cloud file ID
            cloud_file: Optional CloudFile for size verification
            account: Optional CloudAccount for token updates

        Returns:
            Local path if cached, None otherwise
        """
        # Check memory cache first
        if file_id in self._cached_paths:
            path = Path(self._cached_paths[file_id])
            if path.exists():
                return str(path)

        # Check file system
        from utils.helpers import sanitize_filename

        download_path = Path(self._download_dir)
        if not download_path.is_absolute():
            download_path = Path.cwd() / download_path

        if cloud_file:
            safe_filename = sanitize_filename(cloud_file.name)
            local_path = download_path / safe_filename

            if local_path.exists():
                # Verify size if available
                if cloud_file.size:
                    actual_size = local_path.stat().st_size
                    size_diff = abs(actual_size - cloud_file.size)
                    tolerance = cloud_file.size * 0.01

                    if size_diff > tolerance:
                        return None

                self._cached_paths[file_id] = str(local_path)
                return str(local_path)

        return None

    def is_downloading(self, file_id: str) -> bool:
        """Check if a file is currently being downloaded."""
        return file_id in self._active_downloads

    def get_download_progress(self, file_id: str) -> tuple:
        """
        Get download progress for a file.

        Returns:
            Tuple of (current_bytes, total_bytes) or (0, 0) if not downloading
        """
        if file_id in self._active_downloads:
            worker = self._active_downloads[file_id]
            # This is approximate since we don't track exact progress
            return (0, 0)
        return (0, 0)

    def _on_download_completed(self, file_id: str, local_path: str):
        """Handle download completion."""
        if file_id in self._active_downloads:
            del self._active_downloads[file_id]

        self._cached_paths[file_id] = local_path
        self.download_completed.emit(file_id, local_path)

    def _on_download_error(self, file_id: str, error: str):
        """Handle download error."""
        if file_id in self._active_downloads:
            del self._active_downloads[file_id]

        self.download_error.emit(file_id, error)

    def clear_cache(self):
        """Clear the memory cache (does not delete files)."""
        self._cached_paths.clear()

    def cleanup(self):
        """Cancel all active downloads and cleanup."""
        for file_id in list(self._active_downloads.keys()):
            self.cancel_download(file_id)

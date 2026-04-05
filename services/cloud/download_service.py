"""
Cloud download service for managing cloud file downloads.

This service provides a unified interface for downloading files from cloud storage,
with support for caching, progress tracking, and download cancellation.
"""

import atexit
import logging
import threading
from pathlib import Path
from typing import Optional, Dict, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, QThread
from shiboken6 import isValid
from services.cloud.cache_paths import build_cloud_cache_path

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
        from services.cloud.quark_service import QuarkDriveService
        from services.cloud.baidu_service import BaiduDriveService

        file_id = self._cloud_file.file_id

        try:
            # Create download directory
            download_path = Path(self._download_dir)
            if not download_path.is_absolute():
                download_path = Path.cwd() / download_path
            download_path.mkdir(parents=True, exist_ok=True)

            # Determine local file path
            local_path = build_cloud_cache_path(download_path, self._cloud_file)

            # Check if file already exists
            if local_path.exists() and self._cloud_file.size:
                actual_size = local_path.stat().st_size
                size_diff = abs(actual_size - self._cloud_file.size)
                tolerance = self._cloud_file.size * 0.01

                if size_diff <= tolerance:
                    self.download_completed.emit(file_id, str(local_path))
                    return

            # Select service based on provider
            service = BaiduDriveService if self._account.provider == "baidu" else QuarkDriveService

            # Get download URL (pass file path for Baidu)
            if self._account.provider == "baidu":
                result = service.get_download_url(
                    self._account.access_token, file_id, self._cloud_file.metadata
                )
            else:
                result = service.get_download_url(
                    self._account.access_token, file_id
                )

            if isinstance(result, tuple):
                url, _ = result
            else:
                url = result

            if not url:
                self.download_error.emit(file_id, "Failed to get download URL")
                return

            if self._cancelled:
                return

            # Download the file with correct headers for provider
            success = self._download_file(url, str(local_path), service)

            if self._cancelled:
                # Clean up partial download
                if local_path.exists():
                    local_path.unlink()
                return

            if success:
                self.download_completed.emit(file_id, str(local_path))
            else:
                self.download_error.emit(file_id, "Download failed")

        except Exception as e:
            logger.error(f"[CloudDownloadWorker] Error: {e}", exc_info=True)
            self.download_error.emit(file_id, str(e))

    def _download_file(self, url: str, dest_path: str, service) -> bool:
        """Download file from URL to destination."""
        from infrastructure.network import HttpClient

        try:
            # Use service's download_file method if available
            if hasattr(service, 'download_file'):
                return service.download_file(url, dest_path, self._account.access_token)

            # Fallback: build headers based on provider
            if self._account.provider == "baidu":
                headers = {
                    "User-Agent": "netdisk",
                    "Referer": "https://pan.baidu.com/",
                }
            else:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": "https://pan.quark.cn/",
                    "Cookie": self._account.access_token
                }

            with HttpClient.shared().stream("GET", url, headers=headers, timeout=60) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_emitted_mb = 0  # Track last emitted MB threshold

                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._cancelled:
                            f.close()
                            if Path(dest_path).exists():
                                Path(dest_path).unlink()
                            return False

                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)

                            # Emit progress every 1MB threshold crossed
                            if total_size > 0:
                                current_mb = downloaded // (1024 * 1024)
                                if current_mb > last_emitted_mb:
                                    last_emitted_mb = current_mb
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
        self._downloads_lock = threading.Lock()
        self._cached_paths: Dict[str, str] = {}  # file_id -> local_path
        self._download_dir = "data/cloud_downloads"
        atexit.register(self.cleanup)

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
        worker_to_cancel = None

        # Check if already downloading and handle cancellation atomically
        with self._downloads_lock:
            if file_id in self._active_downloads:
                if priority:
                    # Get worker to cancel outside lock
                    worker_to_cancel = self._active_downloads[file_id]
                    del self._active_downloads[file_id]
                else:
                    return False

        # Cancel the worker outside the lock to avoid blocking
        if worker_to_cancel:
            worker_to_cancel.cancel()
            worker_to_cancel.wait(1000)  # Wait up to 1 second

        # Check cache
        cached_path = self.get_cached_path(file_id, cloud_file, account)
        if cached_path:
            self._cached_paths[file_id] = cached_path
            self.download_completed.emit(file_id, cached_path)
            return True

        # Check if already downloading and start worker atomically
        with self._downloads_lock:
            if file_id in self._active_downloads:
                return False  # Already downloading

            # Create worker inside lock to prevent race
            worker = CloudDownloadWorker(
                cloud_file, account, self._download_dir, self
            )

            # Connect signals
            worker.download_progress.connect(
                lambda fid, cur, tot: self.download_progress.emit(fid, cur, tot)
            )
            worker.download_completed.connect(self._on_download_completed)
            worker.download_error.connect(self._on_download_error)

            # Clean up worker ONLY after thread has fully stopped
            def on_thread_finished():
                with self._downloads_lock:
                    if file_id in self._active_downloads:
                        del self._active_downloads[file_id]

            worker.finished.connect(on_thread_finished)

            self._active_downloads[file_id] = worker
            worker.start()

        self.download_started.emit(file_id)

        return True

    def cancel_download(self, file_id: str) -> bool:
        """
        Cancel an active download.

        Args:
            file_id: File ID to cancel

        Returns:
            True if download was cancelled
        """
        with self._downloads_lock:
            if file_id in self._active_downloads:
                worker = self._active_downloads[file_id]
                del self._active_downloads[file_id]
            else:
                worker = None

        if worker:
            self._stop_worker(worker, file_id)
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

        download_path = Path(self._download_dir)
        if not download_path.is_absolute():
            download_path = Path.cwd() / download_path

        if cloud_file:
            local_path = build_cloud_cache_path(download_path, cloud_file)

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
        with self._downloads_lock:
            return file_id in self._active_downloads

    def get_download_progress(self, file_id: str) -> tuple:
        """
        Get download progress for a file.

        Returns:
            Tuple of (current_bytes, total_bytes) or (0, 0) if not downloading
        """
        with self._downloads_lock:
            if file_id in self._active_downloads:
                # This is approximate since we don't track exact progress
                return (0, 0)
        return (0, 0)

    def _on_download_completed(self, file_id: str, local_path: str):
        """Handle download completion."""
        # Don't remove from _active_downloads here - it will be removed in finished callback
        self._cached_paths[file_id] = local_path
        self.download_completed.emit(file_id, local_path)

    def _on_download_error(self, file_id: str, error: str):
        """Handle download error."""
        # Don't remove from _active_downloads here - it will be removed in finished callback
        self.download_error.emit(file_id, error)

    def clear_cache(self):
        """Clear the memory cache (does not delete files)."""
        self._cached_paths.clear()

    def cleanup(self):
        """Cancel all active downloads and cleanup."""
        with self._downloads_lock:
            file_ids = list(self._active_downloads.keys())
        for file_id in file_ids:
            self.cancel_download(file_id)

    def _stop_worker(self, worker: CloudDownloadWorker, file_id: str = ""):
        """Stop a worker thread using cooperative cancellation only."""
        try:
            worker.cancel()
        except Exception:
            logger.debug("[CloudDownloadService] Worker cancel raised during cleanup: %s", file_id, exc_info=True)

        if not isValid(worker) or not worker.isRunning():
            return

        worker.requestInterruption()
        worker.quit()
        if worker.wait(1000):
            return

        logger.warning("[CloudDownloadService] Worker did not stop in time: %s", file_id)

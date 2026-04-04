"""
Download manager - Unified interface for downloading tracks from different sources.

This module provides a unified abstraction for downloading tracks from:
- Online music services (QQ Music, etc.)
- Cloud storage (Quark, Baidu, etc.)
- Local sources (no-op)
"""
import logging
from typing import TYPE_CHECKING, Optional, Dict, Callable
from PySide6.QtCore import QThread, Signal, QObject
from shiboken6 import isValid

from domain.track import TrackSource

if TYPE_CHECKING:
    from domain.playlist_item import PlaylistItem
    from system.config import ConfigManager
    from infrastructure.database import DatabaseManager

logger = logging.getLogger(__name__)


class DownloadManager(QObject):
    """
    Unified download manager for all track sources.

    Routes download requests to appropriate service based on source type.
    All downloads run in background threads to avoid blocking the UI.
    """

    _instance = None

    # Signals
    download_started = Signal(str)  # song_mid or file_id
    download_completed = Signal(str, str)  # (song_mid/file_id, local_path)
    download_failed = Signal(str)  # song_mid or file_id

    @classmethod
    def instance(cls) -> "DownloadManager":
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self, parent=None):
        """
        Initialize download manager.

        Args:
            parent: Optional parent QObject
        """
        super().__init__(parent)  # 必须调用父类__init__以支持Signal/Slot
        self._config = None
        self._db = None
        self._playback_service = None
        self._download_workers: Dict[str, QThread] = {}  # Track active downloads
        logger.debug("[DownloadManager] Initialized")

    def set_dependencies(self, config: Optional["ConfigManager"] = None,
                        db_manager: Optional["DatabaseManager"] = None,
                        playback_service = None,
                        cloud_repo = None):
        """
        Set dependencies for download services.

        Args:
            config: ConfigManager instance
            db_manager: DatabaseManager instance
            playback_service: PlaybackService instance (for callbacks)
            cloud_repo: Cloud repository
        """
        self._config = config
        self._db = db_manager
        self._playback_service = playback_service
        self._cloud_repo = cloud_repo
        logger.debug("[DownloadManager] Dependencies set")

    def download_track(self, item: "PlaylistItem") -> bool:
        """
        Download a track based on its source type.

        This is the unified entry point for all downloads.
        Routes to appropriate service:
        - QQ -> OnlineDownloadService (QQ Music)
        - QUARK/BAIDU -> CloudDownloadService (cloud storage)
        - LOCAL -> No-op (already available)

        All downloads run in background threads.

        Args:
            item: PlaylistItem to download

        Returns:
            True if download was initiated successfully
        """
        logger.info(f"[DownloadManager] Download request: source={item.source}, "
                   f"cloud_file_id={item.cloud_file_id}, title={item.title}")

        # Route based on source type
        if item.source == TrackSource.LOCAL:
            logger.warning("[DownloadManager] Local track doesn't need download")
            return False

        elif item.source == TrackSource.QQ:
            return self._download_online_track(item)

        elif item.source in (TrackSource.QUARK, TrackSource.BAIDU):
            return self._download_cloud_track(item)

        else:
            logger.error(f"[DownloadManager] Unknown source type: {item.source}")
            return False

    def _download_online_track(self, item: "PlaylistItem") -> bool:
        """
        Download track from online music service (QQ Music, etc.).

        Download runs in a background thread to avoid blocking.

        Args:
            item: PlaylistItem with ONLINE source type

        Returns:
            True if download was initiated
        """
        from services.online import OnlineDownloadService
        from app.bootstrap import Bootstrap

        song_mid = item.cloud_file_id
        if not song_mid:
            logger.error("[DownloadManager] ONLINE track missing cloud_file_id")
            return False

        # Check if already downloading
        if song_mid in self._download_workers:
            worker = self._download_workers[song_mid]
            if worker and isValid(worker) and worker.isRunning():
                logger.info(f"[DownloadManager] Already downloading: {song_mid}")
                return True
            else:
                # Clean up finished worker - safe to delete since it's not running
                del self._download_workers[song_mid]
                worker.deleteLater()

        # Get download service
        bootstrap = Bootstrap.instance()
        service = bootstrap.online_download_service
        if not service:
            logger.error("[DownloadManager] Online download service not available")
            return False

        logger.info(f"[DownloadManager] Starting online download: {song_mid}")

        # Create download worker
        worker = self._OnlineDownloadWorker(service, song_mid, item.title, item)

        # Clean up worker ONLY after thread has fully stopped
        def on_thread_finished():
            if song_mid in self._download_workers:
                worker_obj = self._download_workers.pop(song_mid)
                worker_obj.deleteLater()

        worker.download_finished.connect(self._on_online_download_finished)
        worker.finished.connect(on_thread_finished)

        # Start download
        self._download_workers[song_mid] = worker
        worker.start()

        return True

    def redownload_online_track(self, song_mid: str, title: str,
                                quality: str = None, force: bool = True) -> bool:
        """
        Re-download an online track with specified quality.

        Similar to _download_online_track but allows explicit quality and force parameters.

        Args:
            song_mid: Song MID
            title: Track title
            quality: Audio quality (master/flac/320/128), None uses config default
            force: If True, skip cache check and re-download

        Returns:
            True if download was initiated
        """
        from services.online import OnlineDownloadService
        from app.bootstrap import Bootstrap

        if not song_mid:
            logger.error("[DownloadManager] redownload_online_track: missing song_mid")
            return False

        # Check if already downloading
        if song_mid in self._download_workers:
            worker = self._download_workers[song_mid]
            if worker and isValid(worker) and worker.isRunning():
                logger.info(f"[DownloadManager] Already downloading: {song_mid}")
                return True
            else:
                del self._download_workers[song_mid]
                worker.deleteLater()

        # Get download service
        bootstrap = Bootstrap.instance()
        service = bootstrap.online_download_service
        if not service:
            logger.error("[DownloadManager] Online download service not available")
            return False

        logger.info(f"[DownloadManager] Re-downloading online track: {song_mid}, quality={quality}")

        # Create a minimal PlaylistItem for the worker
        from domain.playlist_item import PlaylistItem
        from domain.track import TrackSource
        item = PlaylistItem(
            cloud_file_id=song_mid,
            title=title,
            source=TrackSource.QQ,
        )

        worker = self._OnlineDownloadWorker(service, song_mid, title, item,
                                             quality=quality, force=force)

        def on_thread_finished():
            if song_mid in self._download_workers:
                worker_obj = self._download_workers.pop(song_mid)
                worker_obj.deleteLater()

        worker.download_finished.connect(self._on_online_download_finished)
        worker.finished.connect(on_thread_finished)

        self._download_workers[song_mid] = worker
        worker.start()

        return True

    def _download_cloud_track(self, item: "PlaylistItem") -> bool:
        """
        Download track from cloud storage (Quark, Baidu, etc.).

        Args:
            item: PlaylistItem with cloud storage source type

        Returns:
            True if download was initiated
        """
        from services.cloud.download_service import CloudDownloadService
        from domain.cloud import CloudFile

        if not self._db:
            logger.error("[DownloadManager] Database manager not available")
            return False

        # Find cloud file
        cloud_file = self._cloud_repo.get_file_by_file_id(item.cloud_file_id)
        if not cloud_file:
            logger.error(f"[DownloadManager] CloudFile not found: {item.cloud_file_id}")
            return False

        # Get cloud account
        cloud_account = None
        if item.cloud_account_id:
            cloud_account = self._cloud_repo.get_account_by_id(item.cloud_account_id)
        if not cloud_account:
            logger.error("[DownloadManager] No cloud account for download")
            return False

        # Get download service
        service = CloudDownloadService.instance()
        service.set_download_dir(
            self._config.get_cloud_download_dir() if self._config else "data/cloud_downloads"
        )

        # CloudDownloadService handles its own async downloading
        # Just trigger the download
        logger.info(f"[DownloadManager] Starting cloud download: {cloud_file.file_id}")
        service.download_file(cloud_file, cloud_account)
        return True

    def _on_online_download_finished(self, song_mid: str, local_path: str):
        """
        Handle online download completion.

        Args:
            song_mid: Song MID
            local_path: Local path of downloaded file (empty if failed)
        """
        # Don't delete worker here - it will be deleted in on_thread_finished callback
        # Just disconnect the signal
        if song_mid in self._download_workers:
            worker = self._download_workers[song_mid]
            worker.download_finished.disconnect(self._on_online_download_finished)

        if not local_path:
            logger.error(f"[DownloadManager] Online download failed: {song_mid}")
            self.download_failed.emit(song_mid)
            return

        logger.info(f"[DownloadManager] Online download complete: {song_mid} -> {local_path}")
        self.download_completed.emit(song_mid, local_path)

        # Notify playback service
        if self._playback_service:
            self._playback_service.on_online_track_downloaded(song_mid, local_path)

    class _OnlineDownloadWorker(QThread):
        """Background worker for online music download."""
        download_finished = Signal(str, str)  # (song_mid, local_path)

        def __init__(self, service, song_mid: str, title: str, item: "PlaylistItem",
                     quality: str = None, force: bool = False):
            super().__init__()
            self._service = service
            self._song_mid = song_mid
            self._title = title
            self._item = item
            self._quality = quality
            self._force = force

        def run(self):
            """Execute download in background thread."""
            logger.info(f"[DownloadManager] Worker downloading: {self._song_mid}")
            path = self._service.download(
                self._song_mid, self._title,
                quality=self._quality, force=self._force
            )
            # Always emit, even if path is None (failed)
            self.download_finished.emit(self._song_mid, path or "")

    def cleanup(self):
        """Cancel all active downloads and cleanup workers."""
        logger.info("[DownloadManager] Cleaning up download workers")
        for song_mid, worker in list(self._download_workers.items()):
            self._stop_worker(worker, song_mid, wait_ms=1000)
        self._download_workers.clear()

    def _stop_worker(self, worker: Optional[QThread], worker_id: str, wait_ms: int = 1000):
        """Stop a download worker cooperatively."""
        if not (worker and isValid(worker) and worker.isRunning()):
            return

        worker.requestInterruption()
        worker.quit()
        if not worker.wait(wait_ms):
            logger.warning(
                f"[DownloadManager] Worker did not stop in time via cooperative shutdown: {worker_id}"
            )

"""
Cache cleaner service for online music downloads.
Provides automatic and manual cleanup of cached music files.
"""

import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from system.config import ConfigManager
    from system.event_bus import EventBus
    from services.online.download_service import OnlineDownloadService
    from services.playback.queue_service import QueueService

logger = logging.getLogger(__name__)


class CacheCleanerService(QObject):
    """
    Service for managing online music cache cleanup.

    Supports multiple cleanup strategies:
    - Time-based: Clean files older than N days
    - Size-based: Clean oldest files when cache exceeds X MB
    - Count-based: Clean oldest files when cache exceeds N files
    - Manual: Only clean on explicit request
    - Disabled: No automatic cleanup
    """

    def __init__(
        self,
        config_manager: "ConfigManager",
        download_service: "OnlineDownloadService",
        event_bus: "EventBus",
        queue_service: Optional["QueueService"] = None
    ):
        """
        Initialize cache cleaner service.

        Args:
            config_manager: ConfigManager instance
            download_service: OnlineDownloadService instance
            event_bus: EventBus instance
            queue_service: QueueService instance (optional, for queue protection)
        """
        super().__init__()
        self._config = config_manager
        self._download_service = download_service
        self._event_bus = event_bus
        self._queue_service = queue_service

        # Timer for periodic cleanup checks
        self._timer: Optional[QTimer] = None

    def start(self):
        """Start automatic cleanup scheduler."""
        if self._timer is not None:
            logger.warning("Cache cleaner already started")
            return

        # Create timer
        self._timer = QTimer()
        self._timer.timeout.connect(self._on_timer)

        # Check if cleanup is needed on startup
        if self._config.get_cache_cleanup_auto_enabled():
            if self.should_cleanup():
                logger.info("Running cache cleanup on startup")
                self.cleanup()

            # Start periodic timer
            interval_hours = self._config.get_cache_cleanup_interval_hours()
            interval_ms = interval_hours * 3600 * 1000
            self._timer.start(interval_ms)
            logger.info(f"Cache cleaner started with {interval_hours}h interval")
        else:
            logger.info("Auto cache cleanup is disabled")

    def stop(self):
        """Stop automatic cleanup scheduler."""
        if self._timer is not None:
            self._timer.stop()
            self._timer.deleteLater()
            self._timer = None
            logger.info("Cache cleaner stopped")

    def cleanup(self, strategy: Optional[str] = None) -> Dict:
        """
        Execute cleanup based on configured or specified strategy.

        Args:
            strategy: Override strategy ("time", "size", "count", or None for config)

        Returns:
            dict with keys: files_deleted, space_freed, errors
        """
        # Determine strategy
        if strategy is None:
            strategy = self._config.get_cache_cleanup_strategy()

        if strategy == "disabled":
            logger.info("Cache cleanup is disabled")
            return {"files_deleted": 0, "space_freed": 0, "errors": []}

        if strategy == "manual":
            logger.info("Manual strategy - use explicit cleanup")
            return {"files_deleted": 0, "space_freed": 0, "errors": []}

        # Emit started event
        self._event_bus.cache_cleanup_started.emit()
        logger.info(f"Starting cache cleanup with strategy: {strategy}")

        try:
            # Get cache directory
            cache_dir = Path(self._download_service._download_dir)
            if not cache_dir.exists():
                logger.warning(f"Cache directory does not exist: {cache_dir}")
                return {"files_deleted": 0, "space_freed": 0, "errors": []}

            # Get protected song mids from queue
            protected_mids = self._get_protected_song_mids()

            # Execute strategy-specific cleanup
            if strategy == "time":
                deleted_files = self._cleanup_by_time(cache_dir, protected_mids)
            elif strategy == "size":
                deleted_files = self._cleanup_by_size(cache_dir, protected_mids)
            elif strategy == "count":
                deleted_files = self._cleanup_by_count(cache_dir, protected_mids)
            else:
                logger.error(f"Unknown cleanup strategy: {strategy}")
                self._event_bus.cache_cleanup_error.emit(f"Unknown strategy: {strategy}")
                return {"files_deleted": 0, "space_freed": 0, "errors": [f"Unknown strategy: {strategy}"]}

            # Calculate stats
            files_deleted = len(deleted_files)
            space_freed = sum(self._get_file_size(f) for f in deleted_files)

            # Update last run timestamp
            self._config.set_cache_cleanup_last_run(int(time.time()))

            # Emit completed event
            result = {
                "files_deleted": files_deleted,
                "space_freed": space_freed,
                "errors": []
            }
            self._event_bus.cache_cleanup_completed.emit(result)

            logger.info(f"Cache cleanup completed: {files_deleted} files, {space_freed} bytes freed")
            return result

        except Exception as e:
            logger.error(f"Cache cleanup error: {e}")
            self._event_bus.cache_cleanup_error.emit(str(e))
            return {"files_deleted": 0, "space_freed": 0, "errors": [str(e)]}

    def get_cache_info(self) -> Dict:
        """
        Get current cache statistics.

        Returns:
            dict with: file_count, total_size, oldest_file, newest_file
        """
        cache_dir = Path(self._download_service._download_dir)
        if not cache_dir.exists():
            return {
                "file_count": 0,
                "total_size": 0,
                "oldest_file": None,
                "newest_file": None
            }

        audio_files = self._get_audio_files(cache_dir)

        if not audio_files:
            return {
                "file_count": 0,
                "total_size": 0,
                "oldest_file": None,
                "newest_file": None
            }

        # Cache stat results once per file
        file_stats = [(f, f.stat()) for f in audio_files]
        file_stats.sort(key=lambda x: x[1].st_mtime)

        total_size = sum(s.st_size for _, s in file_stats)

        return {
            "file_count": len(file_stats),
            "total_size": total_size,
            "oldest_file": str(file_stats[0][0]),
            "oldest_time": file_stats[0][1].st_mtime,
            "newest_file": str(file_stats[-1][0]),
            "newest_time": file_stats[-1][1].st_mtime
        }

    def should_cleanup(self) -> bool:
        """
        Check if cleanup is needed based on current strategy.

        Returns:
            True if cleanup should run
        """
        strategy = self._config.get_cache_cleanup_strategy()

        if strategy in ("manual", "disabled"):
            return False

        # Check if enough time has passed since last run
        last_run = self._config.get_cache_cleanup_last_run()
        if last_run is None:
            return True  # Never run before

        interval_hours = self._config.get_cache_cleanup_interval_hours()
        interval_seconds = interval_hours * 3600
        return (time.time() - last_run) >= interval_seconds

    def _on_timer(self):
        """Handle timer timeout."""
        if self.should_cleanup():
            logger.info("Timer triggered cache cleanup")
            self.cleanup()

    def _get_protected_song_mids(self) -> Set[str]:
        """
        Get song mids that should be protected from deletion.

        Returns:
            Set of song mids currently in the playback queue
        """
        protected = set()

        if self._queue_service is None:
            return protected

        try:
            # Get current queue
            queue = self._queue_service.get_queue()

            # Extract song mids from online tracks
            for item in queue:
                # Check if this is an online track (has song_mid)
                if hasattr(item, 'song_mid') and item.song_mid:
                    protected.add(item.song_mid)

            logger.debug(f"Protected {len(protected)} songs in queue")
            return protected

        except Exception as e:
            logger.warning(f"Failed to get protected songs from queue: {e}")
            return protected

    def _cleanup_by_time(self, cache_dir: Path, protected_mids: Set[str]) -> List[str]:
        """
        Remove cache files older than N days.

        Args:
            cache_dir: Cache directory path
            protected_mids: Set of song mids to protect

        Returns:
            List of deleted file paths
        """
        days = self._config.get_cache_cleanup_time_days()
        cutoff_time = time.time() - (days * 86400)

        deleted_files = []

        # Find old audio files
        for audio_file in self._get_audio_files(cache_dir):
            # Skip protected files
            song_mid = audio_file.stem
            if song_mid in protected_mids:
                continue

            # Check file age
            if audio_file.stat().st_mtime < cutoff_time:
                # Delete both audio and lyrics
                deleted_files.extend(self._delete_song_files(cache_dir, song_mid))

        return deleted_files

    def _cleanup_by_size(self, cache_dir: Path, protected_mids: Set[str]) -> List[str]:
        """
        Remove oldest files until cache size is below threshold.

        Args:
            cache_dir: Cache directory path
            protected_mids: Set of song mids to protect

        Returns:
            List of deleted file paths
        """
        max_size_mb = self._config.get_cache_cleanup_size_mb()
        max_size_bytes = max_size_mb * 1024 * 1024

        # Get current cache size
        current_size = 0
        audio_files = []

        for audio_file in self._get_audio_files(cache_dir):
            song_mid = audio_file.stem
            if song_mid in protected_mids:
                continue

            stat = audio_file.stat()
            current_size += stat.st_size
            audio_files.append((audio_file, stat.st_mtime, stat.st_size, song_mid))

        # Check if cleanup is needed
        if current_size <= max_size_bytes:
            logger.info(f"Cache size {current_size} bytes below threshold {max_size_bytes} bytes")
            return []

        # Sort by modification time (oldest first)
        audio_files.sort(key=lambda x: x[1])

        # Delete oldest files until size is below threshold
        deleted_files = []
        for audio_file, mtime, file_size, song_mid in audio_files:
            if current_size <= max_size_bytes:
                break

            deleted = self._delete_song_files(cache_dir, song_mid)
            if deleted:
                deleted_files.extend(deleted)
                current_size -= file_size

        return deleted_files

    def _cleanup_by_count(self, cache_dir: Path, protected_mids: Set[str]) -> List[str]:
        """
        Remove oldest files until cache file count is below threshold.

        Args:
            cache_dir: Cache directory path
            protected_mids: Set of song mids to protect

        Returns:
            List of deleted file paths
        """
        max_count = self._config.get_cache_cleanup_count()

        # Get all audio files (excluding protected)
        audio_files = []
        for audio_file in self._get_audio_files(cache_dir):
            song_mid = audio_file.stem
            if song_mid in protected_mids:
                continue

            stat = audio_file.stat()
            audio_files.append((audio_file, stat.st_mtime, song_mid))

        # Check if cleanup is needed
        current_count = len(audio_files)
        if current_count <= max_count:
            logger.info(f"Cache count {current_count} below threshold {max_count}")
            return []

        # Sort by modification time (oldest first)
        audio_files.sort(key=lambda x: x[1])

        # Delete oldest files until count is below threshold
        deleted_files = []
        files_to_delete = current_count - max_count

        for audio_file, mtime, song_mid in audio_files[:files_to_delete]:
            deleted = self._delete_song_files(cache_dir, song_mid)
            if deleted:
                deleted_files.extend(deleted)

        return deleted_files

    def _delete_song_files(self, cache_dir: Path, song_mid: str) -> List[str]:
        """
        Delete all files associated with a song (audio and lyrics).

        Args:
            cache_dir: Cache directory path
            song_mid: Song MID

        Returns:
            List of deleted file paths
        """
        deleted_files = []

        # Try to delete audio file across all supported cache extensions
        for ext in self._get_audio_extensions():
            audio_file = cache_dir / f"{song_mid}{ext}"
            if audio_file.exists():
                try:
                    audio_file.unlink()
                    deleted_files.append(str(audio_file))
                    logger.debug(f"Deleted: {audio_file}")
                except Exception as e:
                    logger.warning(f"Failed to delete {audio_file}: {e}")

        # Delete lyrics file
        lyrics_file = cache_dir / f"{song_mid}.qrc"
        if lyrics_file.exists():
            try:
                lyrics_file.unlink()
                deleted_files.append(str(lyrics_file))
                logger.debug(f"Deleted: {lyrics_file}")
            except Exception as e:
                logger.warning(f"Failed to delete {lyrics_file}: {e}")

        return deleted_files

    def _get_audio_extensions(self) -> tuple[str, ...]:
        """Return the cache audio extensions supported by the download service."""
        extensions = getattr(self._download_service, "_CACHE_EXTENSIONS", None)
        if isinstance(extensions, (list, tuple)) and extensions:
            return tuple(extensions)
        return (".mp3", ".flac")

    def _get_audio_files(self, cache_dir: Path) -> List[Path]:
        """Collect cached audio files for all supported extensions."""
        audio_files = []
        for ext in self._get_audio_extensions():
            audio_files.extend(cache_dir.glob(f"*{ext}"))
        return audio_files

    @staticmethod
    def _get_file_size(file_path: str) -> int:
        """Get file size in bytes."""
        try:
            return os.path.getsize(file_path)
        except Exception:
            return 0

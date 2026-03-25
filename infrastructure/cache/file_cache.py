"""
File cache for downloaded cloud files.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

MAX_CACHE_SIZE_MB = 500  # Maximum cache size in megabytes


class FileCache:
    """Manages cached files for cloud playback with LRU eviction."""

    def __init__(self, cache_dir: str = None, max_size_mb: int = MAX_CACHE_SIZE_MB):
        """
        Initialize file cache.

        Args:
            cache_dir: Directory for cached files
            max_size_mb: Maximum cache size in megabytes
        """
        self.cache_dir = Path(cache_dir) if cache_dir else Path.home() / ".harmony" / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def get_path(self, file_id: str) -> Optional[str]:
        """
        Get cached file path if exists.

        Args:
            file_id: Cloud file ID

        Returns:
            Local path if cached, None otherwise
        """
        cache_key = self._get_cache_key(file_id)
        for ext in ['.mp3', '.flac', '.m4a', '.ogg', '.wav']:
            cached_path = self.cache_dir / f"{cache_key}{ext}"
            if cached_path.exists():
                return str(cached_path)
        return None

    def save(self, file_id: str, source_path: str) -> str:
        """
        Save a file to cache.

        Args:
            file_id: Cloud file ID
            source_path: Source file path

        Returns:
            Cached file path
        """
        cache_key = self._get_cache_key(file_id)
        ext = Path(source_path).suffix or '.mp3'
        dest_path = self.cache_dir / f"{cache_key}{ext}"

        # Copy file to cache
        import shutil
        shutil.copy2(source_path, dest_path)

        # Enforce size limit after adding new file
        self._enforce_size_limit()

        return str(dest_path)

    def exists(self, file_id: str) -> bool:
        """
        Check if file is cached.

        Args:
            file_id: Cloud file ID

        Returns:
            True if cached
        """
        return self.get_path(file_id) is not None

    def clear(self):
        """Clear all cached files."""
        try:
            if not self.cache_dir.exists():
                return
            # Convert to list first to avoid issues with concurrent modification
            for file in list(self.cache_dir.iterdir()):
                if file.is_file():
                    try:
                        file.unlink()
                    except FileNotFoundError:
                        pass  # File was deleted by another process
        except Exception as e:
            logger.warning(f"Error clearing cache: {e}")

    def _get_cache_key(self, file_id: str) -> str:
        """Generate cache key from file ID."""
        return hashlib.md5(file_id.encode()).hexdigest()

    def _enforce_size_limit(self):
        """Enforce cache size limit by removing oldest files (LRU)."""
        try:
            if not self.cache_dir.exists():
                return

            # Get all files with their sizes and modification times
            files = []
            total_size = 0
            for f in self.cache_dir.iterdir():
                if f.is_file():
                    stat = f.stat()
                    files.append((f, stat.st_size, stat.st_mtime))
                    total_size += stat.st_size

            # If under limit, no action needed
            if total_size <= self.max_size_bytes:
                return

            # Sort by modification time (oldest first)
            files.sort(key=lambda x: x[2])

            # Remove oldest files until under 80% of limit
            target_size = int(self.max_size_bytes * 0.8)
            for f, size, _ in files:
                if total_size <= target_size:
                    break
                try:
                    f.unlink()
                    total_size -= size
                    logger.debug(f"Removed cached file: {f.name}")
                except OSError as e:
                    logger.warning(f"Failed to remove cached file {f}: {e}")

        except Exception as e:
            logger.warning(f"Error enforcing cache size limit: {e}")

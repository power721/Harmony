"""
Image cache for online music images (covers, avatars, etc.).
Provides disk-based caching with automatic cleanup.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Optional

from utils.helpers import get_cache_dir

logger = logging.getLogger(__name__)


class ImageCache:
    """Manages cached images for online music views."""

    CACHE_DIR = get_cache_dir('online_images')

    # Supported image extensions
    EXTENSIONS = {b'\xff\xd8\xff': '.jpg', b'\x89PNG': '.png', b'GIF8': '.gif'}

    @classmethod
    def get(cls, url: str) -> Optional[bytes]:
        """
        Get cached image data if exists.

        Args:
            url: Image URL

        Returns:
            Image data if cached, None otherwise
        """
        cache_path = cls._get_cache_path(url)
        if cache_path:
            try:
                return cache_path.read_bytes()
            except FileNotFoundError:
                return None
        return None

    @classmethod
    def set(cls, url: str, data: bytes) -> Optional[str]:
        """
        Save image data to cache.

        Args:
            url: Image URL
            data: Image binary data

        Returns:
            Cache file path if saved, None on error
        """
        try:
            cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

            cache_key = cls._get_cache_key(url)
            ext = cls._detect_extension(data)
            cache_path = cls.CACHE_DIR / f"{cache_key}{ext}"

            cache_path.write_bytes(data)
            return str(cache_path)

        except Exception as e:
            logger.warning(f"Failed to cache image: {e}")
            return None

    @classmethod
    def exists(cls, url: str) -> bool:
        """Check if URL is cached."""
        cache_path = cls._get_cache_path(url)
        return cache_path is not None and cache_path.exists()

    @classmethod
    def cleanup(cls, days: int = 7) -> int:
        """
        Clean up cached files older than specified days.

        Args:
            days: Delete files older than this many days

        Returns:
            Number of deleted files
        """
        if not cls.CACHE_DIR.exists():
            return 0

        cutoff = time.time() - days * 86400
        deleted = 0

        for f in cls.CACHE_DIR.iterdir():
            try:
                if f.is_file() and f.stat().st_mtime < cutoff:
                    f.unlink()
                    deleted += 1
                    logger.debug(f"Deleted old cache: {f}")
            except FileNotFoundError:
                # File was deleted by another process - ignore
                pass
            except OSError as e:
                logger.debug(f"Could not delete cache file {f}: {e}")

        if deleted > 0:
            logger.info(f"Cleaned up {deleted} cached images older than {days} days")

        return deleted

    @classmethod
    def _get_cache_key(cls, url: str) -> str:
        """Generate cache key from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    @classmethod
    def _get_cache_path(cls, url: str) -> Optional[Path]:
        """Get cache file path for URL."""
        cache_key = cls._get_cache_key(url)
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            path = cls.CACHE_DIR / f"{cache_key}{ext}"
            if path.exists():
                return path
        return None

    @classmethod
    def _detect_extension(cls, data: bytes) -> str:
        """Detect image format from magic bytes."""
        for magic, ext in cls.EXTENSIONS.items():
            if data.startswith(magic):
                return ext
        return '.jpg'  # Default to jpg

"""In-memory pixmap cache wrapping QPixmapCache for cover art."""
import hashlib
import logging

from PySide6.QtGui import QPixmap, QPixmapCache

logger = logging.getLogger(__name__)


class CoverPixmapCache:
    """Wraps QPixmapCache with cover-specific key generation."""

    _initialized = False

    @classmethod
    def initialize(cls):
        """Set cache limit (128MB)."""
        if not cls._initialized:
            QPixmapCache.setCacheLimit(131072)  # 128MB in KB
            cls._initialized = True

    @classmethod
    def make_key(cls, artist: str, album: str) -> str:
        """Generate cache key from artist + album."""
        raw = f"{artist}:{album}".lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def make_key_from_path(cls, path: str) -> str:
        """Generate cache key from file path."""
        return hashlib.md5(path.encode()).hexdigest()

    @classmethod
    def get(cls, key: str):
        """Get cached pixmap. Returns QPixmap or None."""
        pixmap = QPixmap()
        if QPixmapCache.find(key, pixmap):
            return pixmap if not pixmap.isNull() else None
        return None

    @classmethod
    def set(cls, key: str, pixmap: QPixmap) -> bool:
        """Store pixmap in cache. Returns True on success."""
        if pixmap is None or pixmap.isNull():
            return False
        return QPixmapCache.insert(key, pixmap)

"""
Extract dominant color from images for dynamic theming.

Uses pixel sampling with frequency-based color clustering.
Runs in background threads to avoid blocking the UI.
"""
import logging
from pathlib import Path
from typing import Optional, Callable

from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


def extract_dominant_color(image: QImage) -> Optional[QColor]:
    """Extract the dominant color from a QImage.

    Samples pixels across the image, quantizes them into buckets,
    and returns the most frequent color bucket's average.

    Args:
        image: QImage to analyze

    Returns:
        Dominant QColor, or None if image is null
    """
    if image.isNull():
        return None

    # Convert to Format_RGB32 for consistent pixel access
    converted = image.convertToFormat(QImage.Format_RGB32)
    width = converted.width()
    height = converted.height()

    if width == 0 or height == 0:
        return None

    # Sample pixels (every Nth pixel to keep it fast)
    step = max(1, min(width, height) // 20)
    buckets: dict[tuple[int, int, int], list[int]] = {}

    for y in range(0, height, step):
        for x in range(0, width, step):
            pixel = converted.pixel(x, y)
            r = (pixel >> 16) & 0xFF
            g = (pixel >> 8) & 0xFF
            b = pixel & 0xFF

            # Quantize to reduce color space (divide by 32, round)
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            if key not in buckets:
                buckets[key] = [0, 0, 0, 0]
            buckets[key][0] += r
            buckets[key][1] += g
            buckets[key][2] += b
            buckets[key][3] += 1

    if not buckets:
        return None

    # Find the most frequent bucket
    best_key = max(buckets, key=lambda k: buckets[k][3])
    count = buckets[best_key][3]
    avg_r = buckets[best_key][0] // count
    avg_g = buckets[best_key][1] // count
    avg_b = buckets[best_key][2] // count

    return QColor(avg_r, avg_g, avg_b)


def extract_from_file(path: str) -> Optional[QColor]:
    """Extract dominant color from an image file.

    Args:
        path: File path to the image

    Returns:
        Dominant QColor, or None on failure
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.debug(f"[ColorExtractor] File not found: {path}")
        return None

    image = QImage(str(file_path))
    if image.isNull():
        logger.debug(f"[ColorExtractor] Failed to load image: {path}")
        return None

    return extract_dominant_color(image)


class ColorWorker(QRunnable):
    """Runnable that extracts color from an image file and emits via signal.

    Designed to run in QThreadPool via QThreadPool.globalInstance().start(worker).
    Auto-deletes when finished (default QRunnable behavior).
    """

    def __init__(self, image_path: str, result_signal: Signal):
        super().__init__()
        self.image_path = image_path
        self.result_signal = result_signal
        self.setAutoDelete(True)

    def run(self):
        """Extract color and emit result."""
        try:
            color = extract_from_file(self.image_path)
            self.result_signal.emit(color)
        except Exception as e:
            logger.error(f"[ColorExtractor] Error extracting color: {e}")
            self.result_signal.emit(None)


class CoverFetchWorker(QRunnable):
    """Runnable that fetches cover art and extracts color.

    Combines cover fetching and color extraction in a single background task.
    This prevents UI thread blocking when fetching online covers.
    """

    def __init__(self, cover_fetcher: Callable, title: str, artist: str,
                 path: str, album: str, skip_online: bool, result_signal: Signal,
                 fallback_fetcher: Callable = None):
        super().__init__()
        self.cover_fetcher = cover_fetcher
        self.title = title
        self.artist = artist
        self.path = path
        self.album = album
        self.skip_online = skip_online
        self.result_signal = result_signal
        self.fallback_fetcher = fallback_fetcher
        self.setAutoDelete(True)

    def run(self):
        """Fetch cover, extract color, and emit result."""
        try:
            # Fetch cover (may download from online sources)
            cover_path = self.cover_fetcher(
                self.path, self.title, self.artist,
                self.album, self.skip_online
            )

            # Try fallback if main fetcher didn't find cover
            if not cover_path and self.fallback_fetcher and self.album and self.artist:
                cover_path = self.fallback_fetcher(self.album, self.artist)

            if cover_path:
                # Extract color from the cover
                color = extract_from_file(cover_path)
                self.result_signal.emit(color)
            else:
                self.result_signal.emit(None)
        except Exception as e:
            logger.error(f"[CoverFetchWorker] Error fetching cover or extracting color: {e}")
            self.result_signal.emit(None)


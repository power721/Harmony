"""Tests for ColorExtractor."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QObject, Signal

from services.metadata.color_extractor import (
    extract_dominant_color,
    extract_from_file,
    ColorWorker,
)


def test_extract_dominant_color_red_image():
    """Should extract dominant red from a solid red image."""
    # Create a 10x10 solid red QImage
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(QColor(255, 0, 0))

    result = extract_dominant_color(img)
    assert result == QColor(255, 0, 0)


def test_extract_dominant_color_dark_image():
    """Should handle dark images gracefully."""
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(QColor(18, 18, 18))

    result = extract_dominant_color(img)
    assert result is not None


def test_extract_dominant_color_null_image():
    """Should return None for null QImage."""
    img = QImage()

    result = extract_dominant_color(img)
    assert result is None


def test_extract_from_file_nonexistent():
    """Should return None for nonexistent file."""
    result = extract_from_file("/nonexistent/path/image.jpg")
    assert result is None


def test_color_worker_emits_result():
    """ColorWorker should emit color_extracted signal when done."""
    # Create a temp image using QImage (no Pillow dependency)
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(QColor(255, 0, 0))

    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        tmp_path = f.name

    class Receiver(QObject):
        color_received = Signal(object)

    receiver = Receiver()
    received = []
    receiver.color_received.connect(lambda c: received.append(c))

    worker = ColorWorker(tmp_path, receiver.color_received)
    worker.run()

    assert len(received) == 1
    assert received[0] is not None
    assert isinstance(received[0], QColor)

    Path(tmp_path).unlink(missing_ok=True)

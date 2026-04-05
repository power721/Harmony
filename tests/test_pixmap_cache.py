"""Tests for CoverPixmapCache."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from infrastructure.cache.pixmap_cache import CoverPixmapCache


def test_cache_key_generation():
    """Cache key should be deterministic."""
    k1 = CoverPixmapCache.make_key("The Beatles", "Abbey Road")
    k2 = CoverPixmapCache.make_key("The Beatles", "Abbey Road")
    k3 = CoverPixmapCache.make_key("Other", "Album")
    assert isinstance(k1, str)
    assert len(k1) == 32  # MD5 hex
    assert k1 == k2
    assert k1 != k3


def test_cache_key_from_path():
    """Cache key from file path."""
    k1 = CoverPixmapCache.make_key_from_path("/music/cover.jpg")
    k2 = CoverPixmapCache.make_key_from_path("/music/cover.jpg")
    assert k1 == k2
    assert isinstance(k1, str)


def test_get_cache_miss():
    """get returns None on cache miss."""
    with patch('infrastructure.cache.pixmap_cache.QPixmapCache.setCacheLimit'):
        CoverPixmapCache.initialize()

    with patch('infrastructure.cache.pixmap_cache.QPixmap'):
        with patch('PySide6.QtGui.QPixmapCache.find', return_value=False):
            result = CoverPixmapCache.get("test_key")
            assert result is None


def test_get_cache_hit():
    """get returns pixmap on cache hit."""
    with patch('infrastructure.cache.pixmap_cache.QPixmapCache.setCacheLimit'):
        CoverPixmapCache.initialize()

    qpixmap_mock = MagicMock()
    qpixmap_mock.isNull.return_value = False

    with patch('infrastructure.cache.pixmap_cache.QPixmap', return_value=qpixmap_mock):
        with patch('PySide6.QtGui.QPixmapCache.find', return_value=True):
            result = CoverPixmapCache.get("test_key")
            assert result is qpixmap_mock


def test_set_rejects_null():
    """set returns False for null pixmap."""
    null_pixmap = MagicMock()
    null_pixmap.isNull.return_value = True
    assert CoverPixmapCache.set("key", null_pixmap) is False


def test_set_returns_insert_result():
    """set delegates to QPixmapCache.insert."""
    valid_pixmap = MagicMock()
    valid_pixmap.isNull.return_value = False

    with patch('infrastructure.cache.pixmap_cache.QPixmapCache.insert', return_value=True):
        assert CoverPixmapCache.set("key", valid_pixmap) is True

    with patch('infrastructure.cache.pixmap_cache.QPixmapCache.insert', return_value=False):
        assert CoverPixmapCache.set("key", valid_pixmap) is False


def test_cache_key_from_none_path():
    """Cache key from None path should not crash (bug fix for cloud tracks)."""
    # This was causing AttributeError: 'NoneType' object has no attribute 'encode'
    k1 = CoverPixmapCache.make_key_from_path(None)
    k2 = CoverPixmapCache.make_key_from_path("")
    assert isinstance(k1, str)
    assert len(k1) == 32  # MD5 hex
    # Both None and empty string should produce the same key
    assert k1 == k2

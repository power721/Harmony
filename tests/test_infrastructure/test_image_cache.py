"""
Tests for ImageCache.
"""

import os
import tempfile
import time
from pathlib import Path


from infrastructure.cache.image_cache import ImageCache


class TestImageCache:
    """Tests for ImageCache class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Use a temporary directory for tests
        self.temp_dir = tempfile.mkdtemp()
        self.original_cache_dir = ImageCache.CACHE_DIR
        self.original_max_cache_size = getattr(ImageCache, "MAX_CACHE_SIZE", None)
        ImageCache.CACHE_DIR = Path(self.temp_dir)

    def teardown_method(self):
        """Clean up test fixtures."""
        ImageCache.CACHE_DIR = self.original_cache_dir
        if self.original_max_cache_size is not None:
            ImageCache.MAX_CACHE_SIZE = self.original_max_cache_size
        # Clean up temp directory
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_get_cache_key(self):
        """Test cache key generation."""
        key1 = ImageCache._get_cache_key("https://example.com/image.jpg")
        key2 = ImageCache._get_cache_key("https://example.com/image.jpg")
        key3 = ImageCache._get_cache_key("https://example.com/other.jpg")

        assert key1 == key2
        assert key1 != key3
        assert len(key1) == 32  # MD5 hex digest length

    def test_detect_extension_jpg(self):
        """Test JPG detection."""
        jpg_data = b'\xff\xd8\xff' + b'data'
        assert ImageCache._detect_extension(jpg_data) == '.jpg'

    def test_detect_extension_png(self):
        """Test PNG detection."""
        png_data = b'\x89PNG' + b'data'
        assert ImageCache._detect_extension(png_data) == '.png'

    def test_detect_extension_gif(self):
        """Test GIF detection."""
        gif_data = b'GIF8' + b'data'
        assert ImageCache._detect_extension(gif_data) == '.gif'

    def test_detect_extension_unknown(self):
        """Test unknown format defaults to jpg."""
        unknown_data = b'unknown'
        assert ImageCache._detect_extension(unknown_data) == '.jpg'

    def test_set_and_get(self):
        """Test saving and retrieving cached image."""
        url = "https://example.com/test.jpg"
        data = b'\xff\xd8\xff' + b'test image data'

        # Cache should be empty
        assert ImageCache.get(url) is None

        # Save to cache
        ImageCache.set(url, data)

        # Retrieve from cache
        cached = ImageCache.get(url)
        assert cached == data

    def test_exists(self):
        """Test exists check."""
        url = "https://example.com/exists.jpg"
        data = b'\xff\xd8\xff' + b'data'

        assert not ImageCache.exists(url)

        ImageCache.set(url, data)
        assert ImageCache.exists(url)

    def test_cleanup_old_files(self):
        """Test cleanup of old files."""
        # Create a file
        url = "https://example.com/old.jpg"
        data = b'\xff\xd8\xff' + b'data'
        ImageCache.set(url, data)

        cached_path = ImageCache._get_cache_path(url)
        assert cached_path is not None

        # Set mtime to 8 days ago
        old_time = time.time() - 8 * 86400
        os.utime(cached_path, (old_time, old_time))

        # Cleanup files older than 7 days
        deleted = ImageCache.cleanup(days=7)
        assert deleted == 1
        assert not ImageCache.exists(url)

    def test_cleanup_keeps_recent_files(self):
        """Test that recent files are not cleaned up."""
        url = "https://example.com/recent.jpg"
        data = b'\xff\xd8\xff' + b'data'
        ImageCache.set(url, data)

        # Cleanup should not delete recent files
        deleted = ImageCache.cleanup(days=7)
        assert deleted == 0
        assert ImageCache.exists(url)

    def test_cleanup_empty_dir(self):
        """Test cleanup on empty directory."""
        deleted = ImageCache.cleanup(days=7)
        assert deleted == 0

    def test_set_writes_via_temp_file_then_replaces(self, monkeypatch):
        """Test cache writes use a temp file before atomically replacing the target."""
        url = "https://example.com/atomic.jpg"
        data = b'\xff\xd8\xff' + b'data'
        cache_key = ImageCache._get_cache_key(url)

        writes = []
        replaces = []
        real_write_bytes = Path.write_bytes
        real_replace = Path.replace

        def tracking_write_bytes(path_obj, payload):
            writes.append(path_obj.name)
            return real_write_bytes(path_obj, payload)

        def tracking_replace(path_obj, target):
            replaces.append((path_obj.name, target.name))
            return real_replace(path_obj, target)

        monkeypatch.setattr(Path, "write_bytes", tracking_write_bytes)
        monkeypatch.setattr(Path, "replace", tracking_replace)

        ImageCache.set(url, data)

        assert writes == [f"{cache_key}.jpg.tmp"]
        assert replaces == [(f"{cache_key}.jpg.tmp", f"{cache_key}.jpg")]

    def test_set_enforces_cache_size_limit(self):
        """Test cache eviction removes the oldest files when size exceeds the limit."""
        old_url = "https://example.com/old.jpg"
        new_url = "https://example.com/new.jpg"
        data = b'\xff\xd8\xff' + b'12345678'

        ImageCache.MAX_CACHE_SIZE = len(data)

        ImageCache.set(old_url, data)
        time.sleep(0.01)
        ImageCache.set(new_url, data)

        assert not ImageCache.exists(old_url)
        assert ImageCache.exists(new_url)

"""
Tests for FileCache infrastructure component.
"""

import pytest
from pathlib import Path
from infrastructure.cache.file_cache import FileCache


class TestFileCache:
    """Test FileCache class."""

    def test_initialization_default_dir(self, temp_dir):
        """Test cache initialization with custom directory."""
        cache = FileCache(cache_dir=str(temp_dir))
        assert cache.cache_dir == temp_dir
        assert temp_dir.exists()

    def test_get_cache_key(self):
        """Test cache key generation."""
        cache = FileCache()
        key1 = cache._get_cache_key("file_id_123")
        key2 = cache._get_cache_key("file_id_123")
        key3 = cache._get_cache_key("file_id_456")

        # Same file ID should produce same key
        assert key1 == key2
        # Different file IDs should produce different keys
        assert key1 != key3
        # Keys should be MD5 hashes (32 hex characters)
        assert len(key1) == 32

    def test_cache_not_exists(self, temp_dir):
        """Test checking if non-existent file is cached."""
        cache = FileCache(cache_dir=str(temp_dir))
        assert not cache.exists("non_existent_file")

    def test_save_and_get_path(self, temp_dir, sample_track_data):
        """Test saving and retrieving cached file."""
        cache = FileCache(cache_dir=str(temp_dir))

        # Create a test source file
        source_file = temp_dir / "source.mp3"
        source_file.write_text("test audio data")

        # Save to cache
        file_id = "test_file_123"
        cached_path = cache.save(file_id, str(source_file))

        assert Path(cached_path).exists()
        assert cached_path.startswith(str(temp_dir))

        # Retrieve path
        retrieved_path = cache.get_path(file_id)
        assert retrieved_path == cached_path

    def test_exists_after_save(self, temp_dir):
        """Test exists returns True after saving."""
        cache = FileCache(cache_dir=str(temp_dir))

        source_file = temp_dir / "source.mp3"
        source_file.write_text("test data")

        file_id = "test_file"
        cache.save(file_id, str(source_file))

        assert cache.exists(file_id)

    def test_clear_cache(self, temp_dir):
        """Test clearing all cached files."""
        cache = FileCache(cache_dir=str(temp_dir))

        # Create and save multiple files
        for i in range(3):
            source_file = temp_dir / f"source{i}.mp3"
            source_file.write_text(f"data{i}")
            cache.save(f"file_id_{i}", str(source_file))

        # Clear cache
        cache.clear()

        # Check all files are gone
        assert not cache.exists("file_id_0")
        assert not cache.exists("file_id_1")
        assert not cache.exists("file_id_2")

    def test_get_path_multiple_extensions(self, temp_dir):
        """Test get_path checks multiple audio extensions."""
        cache = FileCache(cache_dir=str(temp_dir))

        source_file = temp_dir / "source.flac"
        source_file.write_text("flac data")

        file_id = "test_flac"
        cache.save(file_id, str(source_file))

        # Should find the file with .flac extension
        retrieved_path = cache.get_path(file_id)
        assert retrieved_path is not None
        assert retrieved_path.endswith(".flac")

    def test_save_preserves_extension(self, temp_dir):
        """Test that save preserves original file extension."""
        cache = FileCache(cache_dir=str(temp_dir))

        extensions = [".mp3", ".flac", ".m4a", ".ogg", ".wav"]

        for ext in extensions:
            source_file = temp_dir / f"source{ext}"
            source_file.write_text(f"data{ext}")

            cached_path = cache.save(f"file_{ext}", str(source_file))
            assert cached_path.endswith(ext)

    def test_save_with_no_extension_defaults_to_mp3(self, temp_dir):
        """Test that files without extension default to .mp3."""
        cache = FileCache(cache_dir=str(temp_dir))

        source_file = temp_dir / "source_no_ext"
        source_file.write_text("data")

        cached_path = cache.save("file_no_ext", str(source_file))
        assert cached_path.endswith(".mp3")

    def test_get_path_returns_none_if_not_cached(self, temp_dir):
        """Test get_path returns None for non-existent cache."""
        cache = FileCache(cache_dir=str(temp_dir))
        assert cache.get_path("non_existent") is None

import time

from infrastructure.cache.image_cache import ImageCache


class _FakeStat:
    def __init__(self, mtime: float):
        self.st_mtime = mtime


class _FakeCacheDir:
    def __init__(self):
        self.entries = {}

    def exists(self):
        return True

    def iterdir(self):
        return iter(self.entries.values())


class _FakeFile:
    def __init__(self, name: str, cache_dir: _FakeCacheDir, mtime: float):
        self.name = name
        self._cache_dir = cache_dir
        self._mtime = mtime

    def is_file(self):
        return True

    def stat(self):
        return _FakeStat(self._mtime)

    def unlink(self):
        self._cache_dir.entries.pop(self.name, None)

    def __str__(self):
        return self.name


def test_cleanup_uses_snapshot_when_deleting_old_files():
    cache_dir = _FakeCacheDir()
    old_time = time.time() - 9 * 86400
    cache_dir.entries = {
        "a": _FakeFile("a", cache_dir, old_time),
        "b": _FakeFile("b", cache_dir, old_time),
    }

    original_dir = ImageCache.CACHE_DIR
    ImageCache.CACHE_DIR = cache_dir
    try:
        deleted = ImageCache.cleanup(days=7)
    finally:
        ImageCache.CACHE_DIR = original_dir

    assert deleted == 2
    assert cache_dir.entries == {}

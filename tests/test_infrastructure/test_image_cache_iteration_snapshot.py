import time
import builtins

from infrastructure.cache.image_cache import ImageCache


class _FakeStat:
    def __init__(self, mtime: float, size: int = 1):
        self.st_mtime = mtime
        self.st_size = size


class _FakeCacheDir:
    def __init__(self):
        self.entries = {}

    def exists(self):
        return True

    def iterdir(self):
        return iter(self.entries.values())


class _FakeFile:
    def __init__(self, name: str, cache_dir: _FakeCacheDir, mtime: float, size: int = 1):
        self.name = name
        self._cache_dir = cache_dir
        self._mtime = mtime
        self._size = size

    def is_file(self):
        return True

    def stat(self):
        return _FakeStat(self._mtime, self._size)

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


def test_enforce_cache_limit_uses_snapshot_when_evicting():
    cache_dir = _FakeCacheDir()
    old_time = time.time() - 9 * 86400
    recent_time = time.time()
    cache_dir.entries = {
        "a": _FakeFile("a", cache_dir, old_time, size=8),
        "b": _FakeFile("b", cache_dir, recent_time, size=8),
    }

    original_dir = ImageCache.CACHE_DIR
    original_limit = getattr(ImageCache, "MAX_CACHE_SIZE", None)
    ImageCache.CACHE_DIR = cache_dir
    ImageCache.MAX_CACHE_SIZE = 8
    try:
        deleted = ImageCache._enforce_cache_limit()
    finally:
        ImageCache.CACHE_DIR = original_dir
        if original_limit is not None:
            ImageCache.MAX_CACHE_SIZE = original_limit

    assert deleted == 1
    assert list(cache_dir.entries) == ["b"]


def test_enforce_cache_limit_skips_sort_when_under_budget(monkeypatch):
    cache_dir = _FakeCacheDir()
    now = time.time()
    cache_dir.entries = {
        "a": _FakeFile("a", cache_dir, now, size=2),
        "b": _FakeFile("b", cache_dir, now, size=2),
    }

    original_dir = ImageCache.CACHE_DIR
    original_limit = getattr(ImageCache, "MAX_CACHE_SIZE", None)
    ImageCache.CACHE_DIR = cache_dir
    ImageCache.MAX_CACHE_SIZE = 10
    try:
        monkeypatch.setattr(
            builtins,
            "sorted",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("sorted should not be called")),
        )
        deleted = ImageCache._enforce_cache_limit()
    finally:
        ImageCache.CACHE_DIR = original_dir
        if original_limit is not None:
            ImageCache.MAX_CACHE_SIZE = original_limit

    assert deleted == 0
    assert list(cache_dir.entries) == ["a", "b"]

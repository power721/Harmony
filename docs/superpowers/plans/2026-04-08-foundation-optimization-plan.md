# Foundation Optimizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the still-valid low-risk foundation optimizations from `docs/optimization_report.md`, excluding `plugins/builtin/qqmusic`, with one optimization per commit.

**Architecture:** The work stays within existing boundaries: domain model micro-optimizations, repository query consolidation, service file-loading improvements, and infrastructure hardening for queueing, HTTP, and caching. Each task preserves current behavior unless the optimization itself requires a narrow, explicitly tested behavior change, and each task is validated with the smallest relevant pytest target before commit.

**Tech Stack:** Python 3.13, PySide6 application code, SQLite repositories, `requests`, pytest via `uv`

---

### Task 1: Cache Domain IDs

**Files:**
- Modify: `domain/album.py`
- Modify: `domain/artist.py`
- Modify: `domain/genre.py`
- Modify: `tests/test_domain/test_album.py`
- Modify: `tests/test_domain/test_artist.py`
- Modify: `tests/test_domain/test_genre_id.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_id_property_is_stable_across_accesses(self):
    album = Album(name="Album", artist="Artist")
    first = album.id
    second = album.id
    assert first == second == "artist:album"


def test_named_genre_id_is_stable_across_accesses():
    genre = Genre(name="Rock")
    first = genre.id
    second = genre.id
    assert first == second == "rock"


def test_empty_genres_keep_per_instance_ids():
    first = Genre(name="")
    second = Genre(name="")
    assert first.id == first.id
    assert second.id == second.id
    assert first.id != second.id
```

- [ ] **Step 2: Run tests to verify the new assertions are covered**

Run: `uv run pytest tests/test_domain/test_album.py tests/test_domain/test_artist.py tests/test_domain/test_genre_id.py -v`
Expected: PASS after adding the assertions, but still validating the current behavior before refactor.

- [ ] **Step 3: Implement cached ID computation**

```python
from functools import cached_property


@cached_property
def id(self) -> str:
    return f"{self.artist}:{self.name}".lower()
```

```python
@cached_property
def id(self) -> str:
    return self.name.lower() if self.name else "unknown"
```

```python
@property
def id(self) -> str:
    if self.name:
        return self._named_id
    return self._anonymous_id


@cached_property
def _named_id(self) -> str:
    return self.name.lower()


@cached_property
def _anonymous_id(self) -> str:
    return f"unknown:{id(self)}"
```

- [ ] **Step 4: Run tests to verify behavior is unchanged**

Run: `uv run pytest tests/test_domain/test_album.py tests/test_domain/test_artist.py tests/test_domain/test_genre_id.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add domain/album.py domain/artist.py domain/genre.py tests/test_domain/test_album.py tests/test_domain/test_artist.py tests/test_domain/test_genre_id.py
git commit -m "缓存聚合实体ID"
```

### Task 2: Optimize Album Repository Single-Record Lookup

**Files:**
- Modify: `repositories/album_repository.py`
- Modify: `tests/test_repositories/test_album_repository.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_by_name_uses_track_cover_from_single_grouped_query(self, album_repo, temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO tracks (path, title, artist, album, duration, cover_path) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("/music/a.mp3", "A", "Artist A", "Album 1", 180.0, None),
            ("/music/b.mp3", "B", "Artist A", "Album 1", 200.0, "/covers/album1.jpg"),
        ],
    )
    conn.commit()
    conn.close()

    album = album_repo.get_by_name("Album 1", artist="Artist A")

    assert album is not None
    assert album.cover_path == "/covers/album1.jpg"
    assert album.song_count == 2
```

- [ ] **Step 2: Run the focused repository test**

Run: `uv run pytest tests/test_repositories/test_album_repository.py -v`
Expected: PASS before refactor, establishing the result contract.

- [ ] **Step 3: Replace the two-query fallback with a single aggregate query**

```python
cursor.execute(
    """
    SELECT
        album AS name,
        artist,
        COUNT(*) AS song_count,
        SUM(duration) AS total_duration,
        MAX(CASE WHEN cover_path IS NOT NULL AND cover_path != '' THEN cover_path END) AS cover_path
    FROM tracks
    WHERE album = ? AND artist = ?
    GROUP BY album, artist
    """,
    (album_name, artist),
)
```

- [ ] **Step 4: Re-run repository tests**

Run: `uv run pytest tests/test_repositories/test_album_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/album_repository.py tests/test_repositories/test_album_repository.py
git commit -m "优化专辑查询封面聚合"
```

### Task 3: Optimize Artist Repository Single-Record Lookup

**Files:**
- Modify: `repositories/artist_repository.py`
- Modify: `tests/test_repositories/test_artist_repository.py`

- [ ] **Step 1: Write the failing test**

```python
def test_get_by_name_uses_grouped_cover_lookup(self, artist_repo, temp_db):
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO tracks (path, title, artist, album, duration, cover_path) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("/music/a.mp3", "A", "Artist A", "Album 1", 180.0, None),
            ("/music/b.mp3", "B", "Artist A", "Album 2", 200.0, "/covers/artist-a.jpg"),
        ],
    )
    conn.commit()
    conn.close()

    artist = artist_repo.get_by_name("Artist A")

    assert artist is not None
    assert artist.cover_path == "/covers/artist-a.jpg"
    assert artist.song_count == 2
    assert artist.album_count == 2
```

- [ ] **Step 2: Run the focused repository test**

Run: `uv run pytest tests/test_repositories/test_artist_repository.py -v`
Expected: PASS before refactor, documenting the current contract.

- [ ] **Step 3: Replace the fallback pair of queries with one aggregate**

```python
cursor.execute(
    """
    SELECT
        artist AS name,
        COUNT(*) AS song_count,
        COUNT(DISTINCT album) AS album_count,
        MAX(CASE WHEN cover_path IS NOT NULL AND cover_path != '' THEN cover_path END) AS cover_path
    FROM tracks
    WHERE artist = ?
    GROUP BY artist
    """,
    (artist_name,),
)
```

- [ ] **Step 4: Re-run repository tests**

Run: `uv run pytest tests/test_repositories/test_artist_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/artist_repository.py tests/test_repositories/test_artist_repository.py
git commit -m "优化歌手查询封面聚合"
```

### Task 4: Remove Random Genre Cover Selection

**Files:**
- Modify: `repositories/genre_repository.py`
- Modify: `tests/test_repositories/test_genre_repository.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_get_all_uses_first_available_track_cover_without_random_order():
    genres = repo.get_all(use_cache=True)
    assert genres[0].cover_path == "/covers/rock1.jpg"


def test_refresh_uses_non_empty_cover_without_random_order():
    repo.refresh()
    refreshed = repo.get_by_name("Rock")
    assert refreshed.cover_path == "/covers/rock1.jpg"
```

- [ ] **Step 2: Run the focused repository test**

Run: `uv run pytest tests/test_repositories/test_genre_repository.py -v`
Expected: FAIL once the assertions are tightened to deterministic first-match behavior.

- [ ] **Step 3: Update subqueries to drop `ORDER BY RANDOM()` and keep non-empty-cover filtering**

```sql
SELECT t.cover_path
FROM tracks t
WHERE t.genre = g.name
  AND t.cover_path IS NOT NULL
  AND t.cover_path != ''
LIMIT 1
```

- [ ] **Step 4: Re-run repository tests**

Run: `uv run pytest tests/test_repositories/test_genre_repository.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add repositories/genre_repository.py tests/test_repositories/test_genre_repository.py
git commit -m "移除流派随机封面查询"
```

### Task 5: Optimize Local Lyrics Loading

**Files:**
- Modify: `services/lyrics/lyrics_service.py`
- Create: `tests/test_services/test_lyrics_service_local_files.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_get_local_lyrics_prefers_utf8_without_trying_other_encodings(tmp_path, monkeypatch):
    lyrics_path = tmp_path / "song.lrc"
    lyrics_path.write_text("[00:00.00]hello", encoding="utf-8")

    opened_encodings = []
    real_open = open

    def tracking_open(path, mode="r", encoding=None, *args, **kwargs):
        opened_encodings.append(encoding)
        return real_open(path, mode, encoding=encoding, *args, **kwargs)

    monkeypatch.setattr("builtins.open", tracking_open)

    result = LyricsService._get_local_lyrics(str(tmp_path / "song.mp3"))

    assert result == "[00:00.00]hello"
    assert opened_encodings == ["utf-8"]
```

```python
def test_get_local_lyrics_detects_non_utf8_file_once(tmp_path):
    lyrics_path = tmp_path / "song.qrc"
    lyrics_path.write_bytes("[00:00.00]\xc4\xe3\xba\xc3".encode("latin1"))

    result = LyricsService._get_local_lyrics(str(tmp_path / "song.mp3"))

    assert "你好" in result
```

- [ ] **Step 2: Run the focused service test**

Run: `uv run pytest tests/test_services/test_lyrics_service_local_files.py -v`
Expected: FAIL because the optimized open-count and encoding-detection behavior is not implemented yet.

- [ ] **Step 3: Implement UTF-8-first loading with one binary read and charset detection fallback**

```python
from charset_normalizer import from_bytes


raw = lyrics_path.read_bytes()
try:
    return raw.decode("utf-8")
except UnicodeDecodeError:
    match = from_bytes(raw).best()
    if match is not None:
        return str(match)
```

- [ ] **Step 4: Re-run the focused service test**

Run: `uv run pytest tests/test_services/test_lyrics_service_local_files.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/lyrics/lyrics_service.py tests/test_services/test_lyrics_service_local_files.py
git commit -m "优化本地歌词读取路径"
```

### Task 6: Bound DBWriteWorker Queue Growth

**Files:**
- Modify: `infrastructure/database/db_write_worker.py`
- Modify: `tests/test_infrastructure/test_db_write_worker.py`

- [ ] **Step 1: Write the failing test**

```python
def test_submit_async_uses_bounded_queue(tmp_path):
    worker = DBWriteWorker(str(tmp_path / "bounded.db"))
    try:
        assert worker._queue.maxsize == 1000
    finally:
        worker.stop()
```

- [ ] **Step 2: Run the focused infrastructure test**

Run: `uv run pytest tests/test_infrastructure/test_db_write_worker.py -v`
Expected: FAIL because the queue is currently unbounded.

- [ ] **Step 3: Add a bounded queue constant and use it during initialization**

```python
class DBWriteWorker:
    MAX_QUEUE_SIZE = 1000

    def __init__(self, db_path: str):
        self._queue: queue.Queue = queue.Queue(maxsize=self.MAX_QUEUE_SIZE)
```

- [ ] **Step 4: Re-run infrastructure tests**

Run: `uv run pytest tests/test_infrastructure/test_db_write_worker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/database/db_write_worker.py tests/test_infrastructure/test_db_write_worker.py
git commit -m "限制数据库写队列大小"
```

### Task 7: Add HTTP Retry Behavior

**Files:**
- Modify: `infrastructure/network/http_client.py`
- Modify: `tests/test_infrastructure/test_http_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_initialization_mounts_adapter_with_retries(self):
    client = HttpClient()
    adapter = client._session.get_adapter("https://example.com")
    retries = adapter.max_retries
    assert retries.total == 3
    assert retries.backoff_factor == 1
    assert 429 in retries.status_forcelist
```

- [ ] **Step 2: Run the focused HTTP client test**

Run: `uv run pytest tests/test_infrastructure/test_http_client.py -v`
Expected: FAIL because the adapter currently has no retry strategy.

- [ ] **Step 3: Configure a reusable retry strategy on the mounted adapter**

```python
from urllib3.util.retry import Retry

retry_strategy = Retry(
    total=3,
    read=3,
    connect=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"]),
)
adapter = HTTPAdapter(
    pool_connections=pool_connections,
    pool_maxsize=pool_maxsize,
    pool_block=pool_block,
    max_retries=retry_strategy,
)
```

- [ ] **Step 4: Re-run HTTP client tests**

Run: `uv run pytest tests/test_infrastructure/test_http_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/network/http_client.py tests/test_infrastructure/test_http_client.py
git commit -m "为HTTP客户端增加重试"
```

### Task 8: Throttle Download Progress Callbacks

**Files:**
- Modify: `infrastructure/network/http_client.py`
- Modify: `tests/test_infrastructure/test_http_client.py`

- [ ] **Step 1: Write the failing test**

```python
@patch("infrastructure.network.http_client.time.monotonic")
def test_download_throttles_progress_callback(self, mock_monotonic, mock_session_class, tmp_path):
    mock_monotonic.side_effect = [0.0, 0.01, 0.02, 0.20, 0.21]
    progress_calls = []

    def on_progress(current, total):
        progress_calls.append((current, total))

    ...
    assert progress_calls == [(5, 20), (15, 20), (20, 20)]
```

- [ ] **Step 2: Run the focused HTTP client test**

Run: `uv run pytest tests/test_infrastructure/test_http_client.py -v`
Expected: FAIL because callbacks are currently emitted for every chunk.

- [ ] **Step 3: Add monotonic-time throttling while preserving the final progress event**

```python
import time

last_progress_at = float("-inf")
progress_interval = 0.1

if progress_callback:
    now = time.monotonic()
    if downloaded == total_size or total_size == 0 or now - last_progress_at >= progress_interval:
        progress_callback(downloaded, total_size)
        last_progress_at = now
```

- [ ] **Step 4: Re-run HTTP client tests**

Run: `uv run pytest tests/test_infrastructure/test_http_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/network/http_client.py tests/test_infrastructure/test_http_client.py
git commit -m "节流下载进度回调"
```

### Task 9: Make ImageCache Writes Atomic

**Files:**
- Modify: `infrastructure/cache/image_cache.py`
- Modify: `tests/test_infrastructure/test_image_cache.py`

- [ ] **Step 1: Write the failing test**

```python
def test_set_writes_via_temp_file_and_replaces_atomically(self, monkeypatch):
    url = "https://example.com/test.jpg"
    data = b"\xff\xd8\xffdata"
    replaced = {}

    real_write_bytes = Path.write_bytes
    real_replace = Path.replace

    def tracking_write_bytes(path_obj, payload):
        replaced["tmp_name"] = path_obj.name
        return real_write_bytes(path_obj, payload)

    def tracking_replace(src, dst):
        replaced["final_name"] = dst.name
        return real_replace(src, dst)

    monkeypatch.setattr(Path, "write_bytes", tracking_write_bytes)
    monkeypatch.setattr(Path, "replace", tracking_replace)

    ImageCache.set(url, data)

    assert replaced["tmp_name"].endswith(".tmp")
    assert replaced["final_name"].endswith(".jpg")
```

- [ ] **Step 2: Run the focused image cache test**

Run: `uv run pytest tests/test_infrastructure/test_image_cache.py -v`
Expected: FAIL because writes currently go straight to the final cache file.

- [ ] **Step 3: Implement temp-file write and atomic replace**

```python
cache_path = cls.CACHE_DIR / f"{cache_key}{ext}"
temp_path = cache_path.with_suffix(f"{cache_path.suffix}.tmp")
temp_path.write_bytes(data)
temp_path.replace(cache_path)
```

- [ ] **Step 4: Re-run image cache tests**

Run: `uv run pytest tests/test_infrastructure/test_image_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/cache/image_cache.py tests/test_infrastructure/test_image_cache.py
git commit -m "改进图片缓存原子写入"
```

### Task 10: Add ImageCache Size Limiting

**Files:**
- Modify: `infrastructure/cache/image_cache.py`
- Modify: `tests/test_infrastructure/test_image_cache.py`
- Modify: `tests/test_infrastructure/test_image_cache_iteration_snapshot.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_set_enforces_cache_size_limit(self):
    ImageCache.MAX_CACHE_SIZE = 10
    ImageCache.set("https://example.com/old.jpg", b"\xff\xd8\xff123456")
    time.sleep(0.01)
    ImageCache.set("https://example.com/new.jpg", b"\xff\xd8\xffabcdef")
    assert ImageCache.exists("https://example.com/new.jpg")
    assert not ImageCache.exists("https://example.com/old.jpg")
```

```python
def test_enforce_cache_limit_uses_snapshot_when_evicting(monkeypatch):
    deleted = ImageCache._enforce_cache_limit()
    assert deleted >= 0
```

- [ ] **Step 2: Run the focused image cache tests**

Run: `uv run pytest tests/test_infrastructure/test_image_cache.py tests/test_infrastructure/test_image_cache_iteration_snapshot.py -v`
Expected: FAIL because no size limit or eviction helper exists.

- [ ] **Step 3: Add configurable size limiting and oldest-first eviction**

```python
class ImageCache:
    MAX_CACHE_SIZE = 500 * 1024 * 1024

    @classmethod
    def _enforce_cache_limit(cls) -> int:
        entries = [
            (path, path.stat().st_mtime, path.stat().st_size)
            for path in list(cls.CACHE_DIR.iterdir())
            if path.is_file()
        ]
        total_size = sum(size for _, _, size in entries)
        for path, _, size in sorted(entries, key=lambda item: item[1]):
            if total_size <= cls.MAX_CACHE_SIZE:
                break
            path.unlink()
            total_size -= size
```

- [ ] **Step 4: Re-run image cache tests**

Run: `uv run pytest tests/test_infrastructure/test_image_cache.py tests/test_infrastructure/test_image_cache_iteration_snapshot.py -v`
Expected: PASS

- [ ] **Step 5: Run the full touched-foundation regression pass**

Run: `uv run pytest tests/test_domain/test_album.py tests/test_domain/test_artist.py tests/test_domain/test_genre_id.py tests/test_repositories/test_album_repository.py tests/test_repositories/test_artist_repository.py tests/test_repositories/test_genre_repository.py tests/test_services/test_lyrics_service_local_files.py tests/test_infrastructure/test_db_write_worker.py tests/test_infrastructure/test_http_client.py tests/test_infrastructure/test_image_cache.py tests/test_infrastructure/test_image_cache_iteration_snapshot.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add infrastructure/cache/image_cache.py tests/test_infrastructure/test_image_cache.py tests/test_infrastructure/test_image_cache_iteration_snapshot.py
git commit -m "限制图片缓存容量"
```

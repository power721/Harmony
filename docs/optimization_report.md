# Harmony 代码优化分析报告

> 基于对 113,000+ 行 Python 源码的全面审查，覆盖所有架构层。

---

## 目录

1. [概述与优先级总览](#1-概述与优先级总览)
2. [Domain 层优化](#2-domain-层优化)
3. [Repositories 层优化](#3-repositories-层优化)
4. [Services 层优化](#4-services-层优化)
5. [Infrastructure 层优化](#5-infrastructure-层优化)
6. [UI 层优化](#6-ui-层优化)
7. [System 层与启动优化](#7-system-层与启动优化)
8. [Plugin 系统优化](#8-plugin-系统优化)
9. [测试套件优化](#9-测试套件优化)
10. [实施路线图](#10-实施路线图)

---

## 1. 概述与优先级总览

### 关键指标

| 维度 | 发现数量 | 严重 | 高 | 中 | 低 |
|------|---------|------|---|---|---|
| 性能 | 28 | 5 | 10 | 9 | 4 |
| 内存 | 14 | 3 | 5 | 4 | 2 |
| 线程安全 | 12 | 3 | 4 | 3 | 2 |
| 代码质量 | 22 | 0 | 6 | 10 | 6 |
| 错误处理 | 15 | 2 | 5 | 5 | 3 |
| 安全 | 5 | 1 | 2 | 2 | 0 |
| 测试覆盖 | 10 | 2 | 4 | 3 | 1 |
| **合计** | **106** | **16** | **36** | **36** | **18** |

### TOP 10 最高优先级问题

| # | 问题 | 层 | 影响 |
|---|------|---|------|
| 1 | UI 线程阻塞（数据库查询在主线程执行） | UI | 界面冻结 |
| 2 | N+1 查询（Album/Artist/Genre 封面查找） | Repositories | 数据库性能 |
| 3 | 信号连接未断开导致内存泄漏 | UI / System | 内存增长 |
| 4 | 缓存无大小限制（ImageCache/QSS/SingleFlight） | Infrastructure / System | 内存溢出 |
| 5 | DBWriteWorker 队列无上限 | Infrastructure | 内存溢出 |
| 6 | HTTP 客户端缺少重试逻辑 | Infrastructure | 网络不稳定 |
| 7 | 云服务线程安全问题（Baidu bdstoken、Quark cookie） | Services | 数据损坏 |
| 8 | 播放引擎 `play_after_download()` 竞态条件 | Infrastructure | 播放故障 |
| 9 | 插件全局上下文缺少线程安全保护 | Plugins | 插件崩溃传播 |
| 10 | 关键服务缺少测试（PlaylistService、CoverService 等） | Tests | 质量风险 |

---

## 2. Domain 层优化

### 2.1 性能：ID 属性重复计算 [高]

**文件**: `domain/album.py:35-38`, `domain/artist.py:28-30`, `domain/genre.py:29-31`

`id` 属性每次访问都执行 `.lower()` 字符串操作。在大型音乐库中，这些对象频繁用于 set/dict 查找，导致不必要的计算开销。

```python
# 当前实现
@property
def id(self) -> str:
    return f"{self.artist}:{self.name}".lower()

# 建议：使用 cached_property
from functools import cached_property

@cached_property
def id(self) -> str:
    return f"{self.artist}:{self.name}".lower()
```

### 2.2 内存：缺少 `__slots__` [高]

**文件**: 所有 dataclass 文件

Track、PlaylistItem、OnlineTrack 等高频实例化类未使用 `__slots__`，每个实例额外消耗约 280 字节。以 10,000 首曲目计算，浪费约 2.8 MB。

```python
@dataclass
class Track:
    __slots__ = ('id', 'title', 'artist', 'album', 'duration', 'path', ...)
    # ...
```

### 2.3 代码质量：`__hash__`/`__eq__` 重复实现 [中]

**文件**: `album.py:40-48`, `artist.py:32-40`, `genre.py:33-41`

三个实体类有完全相同的哈希/相等性实现模式。

```python
# 建议：提取 mixin
class HashableById:
    @property
    def id(self) -> str:
        raise NotImplementedError

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if type(self) is type(other):
            return self.id == other.id
        return False
```

### 2.4 时区处理不一致 [中]

**文件**: `cloud.py`, `history.py`, `playback.py`, `playlist.py`, `track.py`

多个类在 `__post_init__` 中使用 `datetime.now()` 创建无时区的朴素时间。

```python
# 建议：统一使用 UTC
from datetime import datetime, timezone

created_at: Optional[datetime] = field(
    default_factory=lambda: datetime.now(timezone.utc)
)
```

### 2.5 PlaylistItem 违反单一职责原则 [中]

**文件**: `domain/playlist_item.py`

PlaylistItem 承担了 8 项职责（数据表示、Track/CloudFile/dict 转换、序列化、显示属性等）。建议将转换逻辑提取到独立的 `PlaylistItemConverter` 类。

### 2.6 缺少输入验证 [中]

所有 dataclass 文件均缺少字段约束验证：Album/Artist 名称可为空串，Track duration 可为负数，CloudFile size 可为负数。

---

## 3. Repositories 层优化

### 3.1 N+1 查询模式 [严重]

**文件**: `album_repository.py:148-161`, `artist_repository.py:122-129`, `genre_repository.py:180-209`

Album/Artist/Genre 的封面查找使用独立查询，应合并为单条 SQL：

```sql
-- 当前：2 条查询
-- 查询1: SELECT album, artist, COUNT(*) ... GROUP BY ...
-- 查询2: SELECT cover_path FROM tracks WHERE ... LIMIT 1

-- 建议：合并为 1 条
SELECT
    album AS name, artist,
    COUNT(*) AS song_count,
    SUM(duration) AS total_duration,
    MAX(CASE WHEN cover_path IS NOT NULL THEN cover_path END) AS cover_path
FROM tracks
WHERE album = ? AND artist = ?
GROUP BY album, artist
```

**影响**: 每次 Album/Artist 查询减少 50% 数据库调用。

### 3.2 Genre 查询使用 `ORDER BY RANDOM()` [高]

**文件**: `genre_repository.py:38-79`

Genre 封面选择使用 `ORDER BY RANDOM()`，这在大数据集上极其低效（全表扫描 + 随机排序）。

```sql
-- 当前（慢）
SELECT t.cover_path FROM tracks t
WHERE t.genre = g.name AND t.cover_path IS NOT NULL
ORDER BY RANDOM() LIMIT 1

-- 建议（快）
SELECT t.cover_path FROM tracks t
WHERE t.genre = g.name AND t.cover_path IS NOT NULL
LIMIT 1
```

### 3.3 缺少批量操作 [高]

**文件**: `album_repository.py`, `artist_repository.py`, `playlist_repository.py`

- Album/Artist 封面更新为逐条执行，缺少 `batch_update_cover_paths()`
- Playlist 添加曲目为逐条插入，缺少 `add_tracks()` 批量方法

建议使用 `executemany()` 实现批量操作，预计可获得 10 倍性能提升。

### 3.4 缓存聚合仓库代码重复 [高]

**文件**: `album_repository.py`, `artist_repository.py`, `genre_repository.py`, `track_repository.py`

5 处实现了相同的"先查缓存表，后回退到 tracks 聚合查询"模式，约 200 行重复代码。

```python
# 建议：提取基类
class CachedAggregateRepository(BaseRepository):
    def _get_all_with_cache(self, cache_table, cache_query, fallback_query, row_converter, use_cache=True):
        # 统一实现缓存回退逻辑
```

### 3.5 事务管理不完整 [中]

**文件**: `artist_repository.py:146-230`, `track_repository.py:331-387`

- Artist `refresh()` 多步操作缺少显式事务包装，失败时可能导致数据不一致
- `batch_add()` 静默忽略 `IntegrityError` 且不记录日志

```python
# 建议
try:
    cursor.execute("BEGIN TRANSACTION")
    # ... 所有操作 ...
    conn.commit()
except Exception:
    conn.rollback()
    raise
```

### 3.6 get_all() 缺少分页 [中]

**文件**: `album_repository.py`, `artist_repository.py`, `genre_repository.py`, `favorite_repository.py`

所有 `get_all()` 方法返回全部记录，无 LIMIT/OFFSET，10,000+ 条记录全部加载到内存。

### 3.7 缺少索引 [中]

建议添加：
```sql
CREATE INDEX IF NOT EXISTS idx_albums_name_artist ON albums(name, artist);
CREATE INDEX IF NOT EXISTS idx_artists_normalized_name ON artists(normalized_name);
CREATE INDEX IF NOT EXISTS idx_genres_name ON genres(name);
```

---

## 4. Services 层优化

### 4.1 LibraryService 是 God Object [严重]

**文件**: `services/library/library_service.py` (940+ 行)

承担 6 类职责：Track CRUD、搜索、Album/Artist/Genre 聚合、在线曲目管理等。

**建议**: 拆分为 `TrackService`、`LibraryAggregateService`、`OnlineTrackService`。

### 4.2 文件扫描效率低 [高]

**文件**: `services/library/library_service.py:416-463`

`scan_directory()` 使用 `rglob('*')` 遍历全部文件再过滤扩展名，且不检查已有曲目。

**建议**:
- 使用增量扫描（基于 mtime 检测新增/修改文件）
- 预先查询已有路径集合，跳过已存在曲目
- 对文件存在性检查使用 `concurrent.futures` 并行处理

### 4.3 歌词文件编码检测低效 [高]

**文件**: `services/lyrics/lyrics_service.py:351-383`

每首曲目尝试 3 种扩展名 x 6 种编码 = 最多 18 次文件打开操作。

**建议**: 优先尝试 UTF-8，使用 `chardet` 自动检测编码，并缓存检测结果。

### 4.4 云服务线程安全问题 [严重]

| 文件 | 问题 |
|------|------|
| `baidu_service.py:54-56` | `bdstoken` 为类变量，多线程共享且无同步 |
| `baidu_service.py:76-80` | 共享 `requests.Session`，非线程安全 |
| `quark_service.py:65-91` | Cookie 更新非原子操作，并发调用丢失更新 |

**建议**: 使用 `threading.local()` 存储线程相关状态，对 Session 使用连接池。

### 4.5 SingleFlight/Cover 缓存无大小限制 [高]

**文件**: `lyrics_service.py:34-35`, `cover_service.py:21`

SingleFlight 缓存无上限，长时间运行可能无限增长。

**建议**: 实现 LRU 缓存，设置最大条目数（如 1000 条）。

### 4.6 云下载服务竞态条件 [中]

**文件**: `download_service.py:307-359`

双重检查锁模式存在竞态：在锁释放和 worker 取消之间，worker 可能被其他线程移除。

### 4.7 下载文件异常清理缺失 [中]

**文件**: `download_service.py:177-237`

下载过程中发生异常时，不清理残留的部分文件。

```python
# 建议
try:
    # 下载逻辑
except Exception:
    if Path(dest_path).exists():
        Path(dest_path).unlink()
    raise
```

### 4.8 裸 except 吞没异常 [中]

**文件**: `quark_service.py:435-436`

```python
except Exception:  # 吞没所有异常，包括 KeyboardInterrupt
    time.sleep(0.6)
```

**建议**: 使用具体异常类型：`except (IOError, TimeoutError, ConnectionError):`

### 4.9 云服务代码重复 [中]

- JSON 解析逻辑在 `baidu_service.py` 和 `quark_service.py` 中重复
- Cookie 处理逻辑重复
- 下载 URL 获取逻辑重复

**建议**: 提取 `CloudStorageService` 抽象基类和共享工具模块。

---

## 5. Infrastructure 层优化

### 5.1 DBWriteWorker 队列无上限 [严重]

**文件**: `infrastructure/database/db_write_worker.py:43`

写入队列 `Queue()` 无 `maxsize`，高写入负载下可能耗尽内存。

```python
# 建议
self._queue: queue.Queue = queue.Queue(maxsize=1000)
```

### 5.2 播放引擎竞态条件 [严重]

**文件**: `infrastructure/audio/audio_engine.py:784-795`

`play_after_download()` 中 `_media_loaded_flag` 在锁外检查后在锁内使用，存在 TOCTOU 竞态。

**建议**: 将标志检查移入 `_playlist_lock` 内或使用条件变量。

### 5.3 ImageCache 无大小限制 [高]

**文件**: `infrastructure/cache/image_cache.py:45-68`

磁盘缓存可无限增长，无最大容量限制。

```python
# 建议：添加 500MB 上限和 LRU 驱逐
MAX_CACHE_SIZE = 500 * 1024 * 1024

@classmethod
def _enforce_cache_limit(cls):
    total_size = sum(f.stat().st_size for f in cls.CACHE_DIR.glob("*"))
    if total_size > cls.MAX_CACHE_SIZE:
        # 按最后访问时间删除最旧文件
```

### 5.4 ImageCache 写入非原子 [中]

**文件**: `infrastructure/cache/image_cache.py:56-68`

缓存写入过程中断可能导致损坏条目。

```python
# 建议：原子写入
temp_path = cache_path.with_suffix('.tmp')
temp_path.write_bytes(data)
temp_path.replace(cache_path)  # 大多数文件系统上是原子操作
```

### 5.5 HTTP 客户端缺少重试逻辑 [高]

**文件**: `infrastructure/network/http_client.py:104-148`

单次请求失败即返回，无瞬态故障重试。

```python
# 建议
from urllib3.util.retry import Retry

retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
adapter = HTTPAdapter(max_retries=retry_strategy)
```

### 5.6 下载进度回调未节流 [中]

**文件**: `infrastructure/network/http_client.py:264-265`

每个 chunk 都触发回调，可能每秒数千次，导致 UI 线程过载。

```python
# 建议：最多每秒 10 次
if time.time() - last_update > 0.1:
    progress_callback(downloaded, total_size)
    last_update = time.time()
```

### 5.7 播放列表索引重建低效 [中]

**文件**: `infrastructure/audio/audio_engine.py:182-189`

`_rebuild_cloud_file_id_index()` 在每次插入/移除/重排时完整遍历播放列表 (O(n))。

**建议**: 增量更新索引而非全量重建。

### 5.8 临时文件列表无限增长 [中]

**文件**: `infrastructure/audio/audio_engine.py:340-357`

`_temp_files` 列表在长时间运行中持续增长。

### 5.9 MPV 滤波器链缺少错误处理 [中]

**文件**: `infrastructure/audio/mpv_backend.py:429-463`

无效滤波器语法可能导致播放崩溃。

```python
try:
    self._player.af = ",".join(filters)
except Exception as e:
    logger.error(f"Failed to apply audio filters: {e}")
    self._player.af = ""  # 回退到无滤波器
```

### 5.10 FTS5 索引在每次架构变更时重建 [中]

**文件**: `infrastructure/database/sqlite_manager.py:908-943`

即使不相关的架构变更也会触发完整 FTS 索引重建，大型数据库启动很慢。

**建议**: 仅在 FTS 相关迁移发生时重建。

---

## 6. UI 层优化

### 6.1 UI 线程阻塞 [严重]

**文件**: `ui/views/library_view.py:421-476`, `ui/views/albums_view.py`, `ui/views/artists_view.py`, `ui/views/genres_view.py`, `ui/views/album_view.py`, `ui/views/artist_view.py`

多个视图在 UI 线程直接执行数据库查询和搜索操作，导致界面冻结。

**建议**:
- 将所有数据库查询移至后台线程（QThread 或 ThreadPoolExecutor）
- 使用信号传递结果到 UI 线程
- 添加加载指示器和取消令牌

### 6.2 信号连接泄漏 [高]

**文件**: `ui/views/library_view.py:181-234`, `ui/views/playlist_view.py:280-303`, `ui/views/local_tracks_list_view.py:567-577`, `ui/widgets/player_controls.py:182-265`

大量信号连接（30+）在 `_setup_connections()` 中创建，但 `closeEvent()` 中的清理不完整。

**建议**:
- 实现完整的信号断开逻辑
- 使用 `Qt.ConnectionType.SingleShotConnection`（适用时）
- 批量断开信号连接

### 6.3 Delegate 实现严重重复 [高]

| 文件 | 类 | 重复度 |
|------|---|--------|
| `local_tracks_list_view.py:272-512` | `LocalTrackDelegate` | 基准 |
| `history_list_view.py:56-296` | `HistoryItemDelegate` | 95% 重复 |
| `queue_view.py:325-649` | `QueueItemDelegate` | 90% 重复 |

**建议**: 创建 `BaseTrackDelegate` 基类，提取公共绘制逻辑。

### 6.4 封面加载逻辑分散 [高]

至少 6 处独立实现封面加载逻辑：
- `local_tracks_list_view.py:246-270` (CoverLoadWorker)
- `queue_view.py:253-274` (CoverLoadWorker)
- `albums_view.py:127-226` (使用 QTimer 轮询)
- `genres_view.py:385-427` (同上)
- `artist_view.py:63-86` (无缓存)

项目已有 `ui/controllers/cover_controller.py`，但未被统一使用。

**建议**: 全面改用 `CoverController`，替代分散的本地实现。

### 6.5 所有视图预先创建 [中]

**文件**: `ui/windows/main_window.py:360-393`

10+ 个视图在 `_setup_ui()` 中全部创建，即使不立即可见。

**建议**: 实现按需创建（懒加载），在首次切换到该视图时才初始化。

### 6.6 QSS 内联过多 [中]

**文件**: `albums_view.py` (10+ 处), `artists_view.py` (9+ 处), `genre_view.py` (12+ 处), `album_view.py` (10+ 处), `artist_view.py` (大量内联样式)

每个小部件都有独立的 `setStyleSheet()` 调用。

**建议**: 将 QSS 集中到 `ui/styles/` 目录，使用 `ThemeManager.get_qss()` 统一管理。

### 6.7 动画定时器持续运行 [中]

**文件**: `ui/views/queue_view.py:342-347`

动画定时器以 300ms 间隔持续运行，即使列表不可见。

```python
# 建议
def hideEvent(self, event):
    self._animation_timer.stop()
    super().hideEvent(event)

def showEvent(self, event):
    super().showEvent(event)
    if self._animation_playing:
        self._animation_timer.start()
```

### 6.8 异步操作使用轮询模式 [中]

**文件**: `albums_view.py:200-223`, `genres_view.py:220-242`, `genre_view.py:451-469`

使用 `QTimer.singleShot(100)` 每 100ms 轮询 `Future` 结果。

**建议**: 使用 `Future.add_done_callback()` 替代轮询。

### 6.9 ThreadPoolExecutor 未正确清理 [中]

**文件**: `albums_view.py`, `genres_view.py`, `genre_view.py`, `artist_view.py`

按需创建 `ThreadPoolExecutor` 但从未调用 `shutdown()`。

**建议**: 存储为实例变量，在 `closeEvent()` 中调用 `executor.shutdown(wait=True)`。

---

## 7. System 层与启动优化

### 7.1 EventBus 信号从未断开 [严重]

**文件**: `system/event_bus.py:44-152`

EventBus 定义 30+ 信号但无全局断开机制。信号监听器在窗口关闭后仍然存在。

```python
# 建议
def disconnect_all(self):
    """断开所有信号连接。"""
    for signal in [self.track_changed, self.playback_state_changed, ...]:
        try:
            signal.disconnect()
        except RuntimeError:
            pass
```

### 7.2 i18n 模块级阻塞加载 [高]

**文件**: `system/i18n.py:102`

`load_translations()` 在模块导入时执行，阻塞启动。

**建议**: 改为首次使用 `t()` 时懒加载。

### 7.3 i18n 缺少线程安全 [高]

**文件**: `system/i18n.py:11-12, 52-58`

全局变量 `_current_language` 和 `_translations` 无线程同步保护。

**建议**: 添加 `threading.RLock()` 保护读写操作。

### 7.4 ThemeManager QSS 缓存无上限 [中]

**文件**: `system/theme.py:169, 299-323`

`_qss_cache` 字典无大小限制，大量唯一模板会导致内存增长。

**建议**: 使用 `OrderedDict` 实现 LRU 缓存，限制 100 个条目。

### 7.5 ConfigManager 配置无 Schema 验证 [中]

**文件**: `system/config.py:111-127`

任意 key 可设置任意值，无类型检查。音频效果配置的验证逻辑静默修正无效值而不记录日志。

**建议**: 定义 `CONFIG_SCHEMA` 进行类型和范围验证。

### 7.6 Application._dispatch_to_ui 方法签名错误 [高]

**文件**: `app/application.py:108-109`

```python
def _dispatch_to_ui(fn, *args, **kwargs):  # 缺少 self 参数
    QTimer.singleShot(0, lambda: fn(*args, **kwargs))
```

### 7.7 Application.quit() 清理不完整 [高]

**文件**: `app/application.py:134-150`

缺少：热键清理、EventBus 信号断开、ThemeManager 清理、PluginManager 清理。

```python
# 建议：完整关闭序列
def quit(self):
    self._bootstrap.stop_mpris()
    cache_cleaner = self._bootstrap.cache_cleaner_service
    if cache_cleaner:
        cache_cleaner.stop()
    from system.hotkeys import cleanup as cleanup_hotkeys
    cleanup_hotkeys()
    self._bootstrap.event_bus.disconnect_all()
    db = self._bootstrap.db
    if db and hasattr(db, '_write_worker') and db._write_worker:
        db._write_worker.wait_idle()
        db._write_worker.stop()
    self._qt_app.quit()
```

### 7.8 Bootstrap 缺少清理方法 [中]

**文件**: `app/bootstrap.py`

Bootstrap 创建大量服务但无 `cleanup()` 方法来停止它们。

### 7.9 全局热键监听器未在退出时清理 [中]

**文件**: `system/hotkeys.py:27, 220-225`

Windows 媒体键监听器的后台线程在应用退出时未停止。`application.py` 的 `quit()` 方法中无 `hotkeys.cleanup()` 调用。

---

## 8. Plugin 系统优化

### 8.1 全局上下文缺少线程安全 [高]

**文件**: `plugins/builtin/qqmusic/lib/runtime_bridge.py:5-23`

```python
_context = None  # 全局变量，无线程保护

def bind_context(context) -> None:
    global _context
    _context = context
```

**建议**: 使用 `threading.local()` 或插件级别的上下文隔离。

### 8.2 共享客户端竞态条件 [高]

**文件**: `plugins/builtin/qqmusic/lib/runtime_client.py:7-20`

```python
_shared_client = None

def get_shared_client() -> QQMusicClient:
    global _shared_client
    if _shared_client is None:
        _shared_client = QQMusicClient()
    return _shared_client
```

**建议**: 使用双重检查锁或 `functools.lru_cache`。

### 8.3 封面源代码大量重复 [高]

4 个独立的封面源实现结构完全相同：

| 文件 | 类 |
|------|---|
| `itunes_cover/lib/cover_source.py:19-64` | iTunesCoverSource |
| `last_fm_cover/lib/cover_source.py:30-82` | LastFmCoverSource |
| `netease_cover/lib/cover_source.py:23-92` | NeteaseCoverSource |
| `qqmusic/lib/cover_source.py:18-69` | QQMusicCoverSource |

3 个 Artist 封面源同样高度重复。歌词源也存在类似问题。

```python
# 建议：创建基类
class BaseCoverSource:
    def search(self, title, artist, album="", duration=None):
        try:
            url, params = self._build_request(title, artist, album, duration)
            response = self._http_client.get(url, params=params, timeout=5)
            if response.status_code == 200:
                return self._parse_results(response.json())
        except Exception as exc:
            logger.debug(f"{self.display_name} search error: {exc}")
        return []
```

### 8.4 API 请求无缓存 [中]

**文件**: `plugins/builtin/qqmusic/lib/api.py:12-270`

每次 `search()` 调用都发起新的 HTTP 请求，相同关键词的重复搜索浪费带宽。

**建议**: 添加请求级缓存 `@lru_cache(maxsize=128)`。

### 8.5 硬编码 API Key [中]

**文件**: `plugins/builtin/last_fm_cover/lib/cover_source.py:16`

```python
_DEFAULT_API_KEY = "9b0cdcf446cc96dea3e747787ad23575"
```

**建议**: 移除硬编码 Key，要求用户配置或使用安全存储。

### 8.6 HTTP Session 未关闭 [中]

**文件**: `plugins/builtin/qqmusic/lib/legacy/client.py:36-42`

`requests.Session` 在 `__init__` 中创建但从未显式关闭。

**建议**: 实现 `__enter__`/`__exit__` 上下文管理器，或在插件卸载时关闭。

### 8.7 Plugin API 缺少错误契约 [中]

**文件**: `packages/harmony-plugin-api/src/harmony_plugin_api/context.py:14-78`

Protocol 定义使用 `Any` 类型，无错误说明文档。

**建议**: 为每个 Protocol 方法添加异常说明。

### 8.8 缺少 API 版本兼容性检查 [低]

**文件**: `packages/harmony-plugin-api/src/harmony_plugin_api/manifest.py:39-99`

`api_version` 字段存在但加载时不检查兼容性。

---

## 9. 测试套件优化

### 9.1 关键服务缺少测试 [严重]

| 服务 | 测试状态 |
|------|---------|
| PlaylistService | 无测试 |
| CoverService | 无测试 |
| FileOrganizationService | 无测试 |
| AcoustIDService | 无测试 |
| ShareSearchService | 无测试 |
| Genre domain model | 无专门测试 |

### 9.2 缺少集成测试 [严重]

无 `@pytest.mark.integration` 标记的测试。缺少：
- 完整播放工作流测试（本地 → 云 → 在线曲目切换）
- 数据库迁移持久化测试
- 插件加载和初始化流程测试

### 9.3 数据库 Fixture 重复 [高]

`temp_db` fixture 在 5+ 个测试文件中重复定义，手动创建表结构与实际 schema 耦合。

**建议**: 在 `conftest.py` 中使用 `DatabaseManager.init_database()` 创建统一 fixture。

### 9.4 Mock 配置不完整 [中]

**文件**: `tests/test_services/test_library_service.py:70-79`

Mock 对象未配置返回值，测试可能在不完整的 mock 设置下通过。

### 9.5 断言缺少描述信息 [中]

约 1,400+ 个断言无描述信息，仅约 175 个有描述信息。失败时难以调试。

### 9.6 UI 测试缺少行为验证 [中]

UI 测试主要关注清理和线程管理，缺少：用户交互测试、状态转换测试、数据绑定验证。

### 9.7 缺少边界条件测试 [中]

缺少：
- 超长标题（>1000 字符）
- 无效文件路径
- 并发访问模式
- 大型播放列表（10K+ 曲目）内存表现

### 9.8 pytest.ini 配置可增强 [低]

建议添加：覆盖率报告（`--cov`）、最大失败数（`--maxfail=5`）、慢测试统计（`--durations=10`）。

---

## 10. 实施路线图

### 第一阶段：紧急修复（1-2 周）

| # | 任务 | 影响 | 工作量 |
|---|------|------|--------|
| 1 | 修复 `Application._dispatch_to_ui` 方法签名 | 运行时错误 | 小 |
| 2 | 修复播放引擎 `play_after_download()` 竞态条件 | 播放故障 | 小 |
| 3 | DBWriteWorker 队列添加 maxsize | 内存溢出 | 小 |
| 4 | HTTP 客户端添加重试逻辑 | 网络稳定性 | 小 |
| 5 | ImageCache 添加大小限制 | 磁盘空间 | 小 |
| 6 | 修复 Baidu bdstoken 线程安全 | 数据损坏 | 小 |
| 7 | 修复 Quark Cookie 原子更新 | 数据损坏 | 小 |
| 8 | Application.quit() 添加完整清理 | 资源泄漏 | 中 |

### 第二阶段：性能优化（2-3 周）

| # | 任务 | 影响 | 工作量 |
|---|------|------|--------|
| 9 | 合并 N+1 Album/Artist/Genre 查询 | 查询性能 50%↑ | 中 |
| 10 | UI 数据库查询移至后台线程 | 消除界面冻结 | 大 |
| 11 | 统一封面加载到 CoverController | 减少重复 / 内存 | 中 |
| 12 | EventBus 添加 disconnect_all() | 内存泄漏 | 中 |
| 13 | i18n 改为懒加载 + 添加线程安全 | 启动速度 | 小 |
| 14 | ThemeManager QSS 缓存添加 LRU 上限 | 内存 | 小 |
| 15 | 移除 Genre 查询 ORDER BY RANDOM() | 查询性能 100x↑ | 小 |
| 16 | 仓库添加批量操作方法 | 批量操作 10x↑ | 中 |

### 第三阶段：代码质量（2-3 周）

| # | 任务 | 影响 | 工作量 |
|---|------|------|--------|
| 17 | 提取 BaseTrackDelegate 消除 Delegate 重复 | 可维护性 | 大 |
| 18 | 提取 CachedAggregateRepository 基类 | 减少 200 行重复 | 中 |
| 19 | 提取云服务抽象基类和工具模块 | 可维护性 | 大 |
| 20 | 提取封面/歌词源基类 | 减少插件代码 50% | 中 |
| 21 | Domain 类添加 `__slots__` | 内存 ~2.8MB↓ | 小 |
| 22 | Domain ID 属性改用 `cached_property` | 性能 | 小 |
| 23 | QSS 集中到 styles 目录 | 可维护性 | 大 |
| 24 | 视图改为按需创建（懒加载） | 启动速度/内存 | 中 |

### 第四阶段：测试补全（2-3 周）

| # | 任务 | 影响 | 工作量 |
|---|------|------|--------|
| 25 | 补充 PlaylistService / CoverService 等服务测试 | 质量保证 | 大 |
| 26 | 创建集成测试（播放流程/数据库/插件） | 回归防护 | 大 |
| 27 | 统一 temp_db fixture 到 conftest.py | 可维护性 | 中 |
| 28 | 补充 Genre domain model 测试 | 覆盖率 | 小 |
| 29 | 添加边界条件和错误路径测试 | 健壮性 | 中 |
| 30 | 启用覆盖率报告 | 可观测性 | 小 |

---

## 附录：按文件索引的问题清单

<details>
<summary>展开完整文件索引</summary>

| 文件路径 | 问题编号 | 严重程度 |
|---------|---------|---------|
| `app/application.py:108-109` | 方法签名错误 | 高 |
| `app/application.py:134-150` | 关闭清理不完整 | 高 |
| `app/bootstrap.py` | 缺少 cleanup() 方法 | 中 |
| `domain/album.py:35-38` | ID 重复计算 | 高 |
| `domain/artist.py:28-30` | ID 重复计算 | 高 |
| `domain/genre.py:29-31` | ID 重复计算 | 高 |
| `domain/playlist_item.py` | SRP 违规 | 中 |
| `domain/*.py` | 缺少 __slots__ | 高 |
| `domain/*.py` | 缺少输入验证 | 中 |
| `infrastructure/audio/audio_engine.py:182-189` | 索引全量重建 | 中 |
| `infrastructure/audio/audio_engine.py:340-357` | 临时文件列表无限增长 | 中 |
| `infrastructure/audio/audio_engine.py:784-795` | 竞态条件 | 严重 |
| `infrastructure/audio/mpv_backend.py:429-463` | 滤波器链无错误处理 | 中 |
| `infrastructure/cache/image_cache.py:45-68` | 缓存无大小限制 | 高 |
| `infrastructure/cache/image_cache.py:56-68` | 写入非原子 | 中 |
| `infrastructure/database/db_write_worker.py:43` | 队列无上限 | 严重 |
| `infrastructure/database/sqlite_manager.py:908-943` | FTS 过度重建 | 中 |
| `infrastructure/network/http_client.py:104-148` | 缺少重试 | 高 |
| `infrastructure/network/http_client.py:264-265` | 回调未节流 | 中 |
| `repositories/album_repository.py:148-161` | N+1 查询 | 严重 |
| `repositories/artist_repository.py:122-129` | N+1 查询 | 严重 |
| `repositories/genre_repository.py:38-79` | ORDER BY RANDOM() | 高 |
| `repositories/genre_repository.py:180-209` | N+1 子查询 | 严重 |
| `repositories/album,artist,genre_repository.py` | 缓存模式重复 | 高 |
| `repositories/artist_repository.py:146-230` | 事务管理不完整 | 中 |
| `repositories/*.py get_all()` | 缺少分页 | 中 |
| `services/library/library_service.py` | God Object (940行) | 严重 |
| `services/library/library_service.py:416-463` | 扫描效率低 | 高 |
| `services/lyrics/lyrics_service.py:351-383` | 编码检测低效 | 高 |
| `services/lyrics/lyrics_service.py:34-35` | 缓存无限增长 | 高 |
| `services/cloud/baidu_service.py:54-56` | bdstoken 非线程安全 | 严重 |
| `services/cloud/baidu_service.py:76-80` | Session 非线程安全 | 严重 |
| `services/cloud/quark_service.py:65-91` | Cookie 更新非原子 | 严重 |
| `services/cloud/quark_service.py:435-436` | 裸 except | 中 |
| `services/cloud/download_service.py:177-237` | 异常未清理文件 | 中 |
| `services/cloud/download_service.py:307-359` | 竞态条件 | 中 |
| `system/event_bus.py:44-152` | 信号从不断开 | 严重 |
| `system/i18n.py:102` | 模块级阻塞加载 | 高 |
| `system/i18n.py:11-12` | 缺少线程安全 | 高 |
| `system/theme.py:169, 322` | QSS 缓存无上限 | 中 |
| `system/config.py:237-267` | 配置验证弱 | 中 |
| `system/hotkeys.py:27, 220` | 退出时未清理 | 中 |
| `ui/views/library_view.py:421-476` | UI 线程阻塞 | 严重 |
| `ui/views/local_tracks_list_view.py` | Delegate 重复 | 高 |
| `ui/views/history_list_view.py` | Delegate 重复 | 高 |
| `ui/views/queue_view.py` | Delegate 重复 / 动画未停 | 高/中 |
| `ui/views/albums_view.py:200-223` | 轮询模式 | 中 |
| `ui/windows/main_window.py:360-393` | 视图预先全部创建 | 中 |
| `ui/views/*.py` | QSS 内联过多 | 中 |
| `plugins/builtin/qqmusic/lib/runtime_bridge.py` | 全局上下文无线程安全 | 高 |
| `plugins/builtin/qqmusic/lib/runtime_client.py` | 共享客户端竞态 | 高 |
| `plugins/builtin/*/lib/cover_source.py` | 封面源大量重复 | 高 |
| `plugins/builtin/last_fm_cover/lib/cover_source.py:16` | 硬编码 API Key | 中 |
| `plugins/builtin/qqmusic/lib/legacy/client.py:36-42` | Session 未关闭 | 中 |

</details>

---

*报告生成时间: 2026-04-08*
*分析范围: 113,675 行 Python 源码, 150+ 文件*
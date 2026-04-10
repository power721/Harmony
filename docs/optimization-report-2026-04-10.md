# Harmony 全面代码优化分析报告

> 日期：2026-04-10
> 范围：全部 Python 源代码（domain / repositories / infrastructure / services / system / ui / app / utils）

---

## 目录

1. [严重问题 (CRITICAL)](#1-严重问题-critical)
2. [线程安全问题](#2-线程安全问题)
3. [性能优化](#3-性能优化)
4. [资源管理与内存泄漏](#4-资源管理与内存泄漏)
5. [错误处理](#5-错误处理)
6. [代码质量与重复代码](#6-代码质量与重复代码)
7. [数据库优化](#7-数据库优化)
8. [UI 响应性与渲染优化](#8-ui-响应性与渲染优化)
9. [设计与架构改进](#9-设计与架构改进)
10. [输入验证与边界检查](#10-输入验证与边界检查)
11. [优先级执行路线图](#11-优先级执行路线图)

---

## 1. 严重问题 (CRITICAL)

### 1.1 N+1 查询 — `track_repository.py`

**文件:** `repositories/track_repository.py`（行 579-603）

`_row_to_track()` 在行转换期间执行 UPDATE 查询。当调用 `get_all()`、`search()` 或 `get_by_ids()` 时，每条需要 provider_id 推断的曲目都会触发一次额外的 UPDATE。1000 条曲目 = 1000+ 条额外查询。

```python
# 问题代码
if online_provider_id != (row["online_provider_id"] ...):
    conn = self._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tracks SET source = ?, online_provider_id = ? WHERE id = ?",
        (TrackSource.ONLINE.value, online_provider_id, row["id"]),
    )
    conn.commit()
```

**建议:** 将此逻辑移到单独的批量更新方法中，在加载所有曲目后调用一次，使用单条 UPDATE 语句配合 CASE 逻辑。

---

### 1.2 AudioEngine 播放列表锁外访问 item

**文件:** `infrastructure/audio/audio_engine.py`（行 664-668 等多处）

在释放 `_playlist_lock` 后使用 `item` 变量。释放锁和使用之间，播放列表可能被另一个线程修改。

```python
# 不安全：item 在锁外访问
if current_source != local_path:
    if not self._load_track_if_match(current_index, item, require_current=True):
        return
```

**建议:** 在锁内捕获所有需要的值，或在锁外重新获取锁进行访问。

---

### 1.3 临时文件清理上限过高

**文件:** `infrastructure/audio/audio_engine.py`（行 331-366）

临时文件列表无限增长，仅在 >100 时才裁剪到 50。期间可能消耗大量磁盘空间，且应用退出时如果 <100 则不清理。

**建议:** 降低阈值（如 50/30），并确保应用退出时始终清理。

---

### 1.4 DBWriteWorker 队列溢出未处理

**文件:** `infrastructure/database/db_write_worker.py`（行 45, 192）

队列设了 `maxsize` 但 `put()` 会无限期阻塞，可能导致死锁。

```python
self._queue.put((func, args, kwargs, future))  # 队列满时阻塞
```

**建议:** 使用 `put(timeout=5.0)` 并在 `queue.Full` 时设置 Future 异常。

---

### 1.5 Genre ID 非确定性回退

**文件:** `domain/genre.py`（行 34）

```python
return f"unknown:{id(self)}"  # 使用对象内存地址
```

两个未命名 Genre 实例会有不同的 ID，破坏 set 去重和等值检查。

**建议:** 使用确定性回退如 `"unknown"` 或要求 name 非空。

---

## 2. 线程安全问题

### 2.1 BaiduService 全局速率限制状态

**文件:** `services/cloud/baidu_service.py`（行 21-33）

模块级 `_last_request_time` 在所有线程间共享，`time.sleep()` 阻塞调用线程。

**建议:** 移到实例变量，实现每账户速率限制。

### 2.2 单例模式缺少线程安全

**文件:**
- `services/cloud/download_service.py`（行 265-272）
- `services/download/download_manager.py`（行 33-45）
- `services/lyrics/lyrics_service.py`（行 35-46）

```python
if cls._instance is None:   # TOCTOU 竞态
    cls._instance = cls()
```

**建议:** 使用 `threading.Lock()` 保护的双重检查锁定。

### 2.3 ConfigManager 缓存锁竞争

**文件:** `system/config.py`（行 107-126）

仓库调用在持有锁时执行，如果仓库慢则阻塞其他线程。

**建议:** 在仓库访问期间释放锁，重新获取时做双重检查。

### 2.4 ThemeManager WeakSet 无同步

**文件:** `system/theme.py`（行 169, 273-281）

`_widgets` WeakSet 在 `_apply_and_broadcast()` 中修改，无同步机制。

**建议:** 添加 `_widgets_lock` 保护。

### 2.5 PluginManager `_loaded_plugins` 无同步

**文件:** `system/plugins/manager.py`（行 41-103）

多线程场景下 `_loaded_plugins` 的访问无锁保护。

**建议:** 添加 `threading.Lock()`。

### 2.6 AudioEngine 云文件 ID 索引更新非原子

**文件:** `infrastructure/audio/audio_engine.py`（行 401-406）

如果在播放列表修改和索引更新之间发生异常，索引会不一致。

**建议:** 包装在 try-except 中，失败时从头重建索引。

### 2.7 MpvBackend `_media_ready` 标志无同步

**文件:** `infrastructure/audio/mpv_backend.py`（行 150-195）

`_media_ready` 在无锁的情况下被检查和设置。

**建议:** 添加 `_media_ready_lock`。

### 2.8 EventBus 信号线程安全

**文件:** `system/event_bus.py`（行 21-203）

Qt 信号不是天然线程安全的，多线程同时发射可能出问题。

**建议:** 添加线程安全的信号发射包装器，使用 `QMetaObject.invokeMethod` + `QueuedConnection`。

### 2.9 PluginStateStore 文件写入竞态

**文件:** `system/plugins/state_store.py`（行 24-30）

`os.replace()` 在 Windows 上文件被锁定时可能失败。

**建议:** 添加错误处理和重试逻辑。

---

## 3. 性能优化

### 3.1 缓存表存在性检查重复执行

**文件:** `repositories/album_repository.py`、`artist_repository.py`、`genre_repository.py`（行 34-37）

每个方法调用时都用单独的查询检查缓存表是否存在。

**建议:** 在内存中缓存表存在性检查结果（实例变量），或在初始化时检查一次。

### 3.2 Genre 封面查询使用相关子查询

**文件:** `repositories/genre_repository.py`（行 38-120）

100 个流派就运行 100+ 个子查询。

**建议:** 使用 JOIN 配合窗口函数替代相关子查询。

### 3.3 Artist 刷新加载曲目两次

**文件:** `repositories/artist_repository.py`（行 138-222）

`refresh()` 方法做了两次全表扫描。

**建议:** 合并为单条查询。

### 3.4 AudioEngine 线性查找代替 O(1) 字典查找

**文件:** `infrastructure/audio/audio_engine.py`（行 525-527）

`update_playlist_item` 做 O(n) 全扫描，但 `_cloud_file_id_to_index` 字典可 O(1) 查找。

**建议:** 优先使用字典查找。

### 3.5 SQLite 索引重复创建

**文件:** `infrastructure/database/sqlite_manager.py`（行 290-358, 696-715）

索引在 `_init_database()` 和 `_run_migrations()` 中各创建一次。

**建议:** 合并到一处。

### 3.6 ImageCache 限制执行效率低

**文件:** `infrastructure/cache/image_cache.py`（行 115-145）

即使缓存远低于限制，也遍历所有文件并排序。

**建议:** 先快速计算总大小，低于限制直接返回，仅在需要删除时才排序。

### 3.7 不必要的播放列表拷贝

**文件:** `infrastructure/audio/audio_engine.py`（行 204, 210）

`playlist` 和 `playlist_items` 属性被频繁调用，每次创建完整拷贝。

**建议:** 返回 tuple 替代 list 拷贝以保证不可变性。

### 3.8 `find_lyric_line()` 使用线性搜索

**文件:** `utils/helpers.py`（行 82-100）

对大歌词文件（1000+ 行）是 O(n) 而非 O(log n)。

**建议:** 使用 `bisect` 模块做二分查找。

### 3.9 MatchScorer 顺序正则替换

**文件:** `utils/match_scorer.py`（行 375-402）

每次字符串规范化时迭代 18 个模式。

**建议:** 合并模式为单个正则（alternation）。

### 3.10 MPRIS 属性每次访问都重算

**文件:** `system/mpris.py`（行 158-175）

`player_properties()` 频繁调用但每次重算所有属性。

**建议:** 缓存属性，设置失效机制。

### 3.11 ConfigManager `get_audio_effects()` 每次调用都做归一化

**文件:** `system/config.py`（行 237-258）

**建议:** 缓存归一化结果或在写入时验证。

### 3.12 MpvBackend 滤波链不必要重建

**文件:** `infrastructure/audio/mpv_backend.py`（行 451-485）

每次重建滤波链，即使没有变化。设置 `self._player.af` 会导致音频处理重启，产生可听到的故障。

**建议:** 仅在实际改变时才更新。

### 3.13 Dedup 模块 20+ 预编译正则

**文件:** `utils/dedup.py`（行 24-90）

模块加载时创建 20+ 个编译正则对象，许多是同一概念的变体。

**建议:** 合并相关模式或使用模式工厂。

### 3.14 PluginRegistry 低效过滤

**文件:** `system/plugins/registry.py`（行 40-59）

`unregister_plugin()` 多次遍历所有列表，每次创建新列表。

**建议:** 用就地过滤 `lst[:] = [...]`。

---

## 4. 资源管理与内存泄漏

### 4.1 HttpClient 下载失败时文件清理不完整

**文件:** `infrastructure/network/http_client.py`（行 265-322）

如果 `open()` 成功但 `iter_content()` 失败，文件可能保持打开且部分写入。

**建议:** 使用临时文件下载，成功后再原子移动到最终位置。

### 4.2 SQLite 连接池未清理

**文件:** `infrastructure/database/sqlite_manager.py`（行 33-56）

线程本地连接存储但从未显式关闭。线程退出时连接可能泄漏。

**建议:** 实现完整的 `close()` 方法，关闭所有连接并清理字典。

### 4.3 MpvBackend 观察回调未清理

**文件:** `infrastructure/audio/mpv_backend.py`（行 128, 252-272）

`cleanup()` 中 `unobserve` 失败时回调仍然注册。

**建议:** 增加日志并确保播放器停止和资源释放。

### 4.4 UI 信号连接从未断开

**文件（多处）:**
- `ui/windows/mini_player.py`（行 307-328）— 13 个信号连接
- `ui/windows/now_playing_window.py`（行 334-351）— 8 个信号连接
- `ui/views/albums_view.py`、`artists_view.py`、`library_view.py`
- `ui/dialogs/lyrics_download_dialog.py`（行 233-238）

**建议:** 在所有窗口/对话框的 `closeEvent()` 中断开信号连接。

### 4.5 GlobalHotkeys 快捷方式未清理

**文件:** `system/hotkeys.py`（行 61-69）

QShortcut 对象存储但从未显式删除。

**建议:** 添加 `cleanup()` 方法调用 `deleteLater()` 并清空列表。

### 4.6 MPRIS EventBus 连接从未断开

**文件:** `system/mpris.py`（行 517-522）

5 个事件总线连接在 MPRISController 销毁时从未断开。

**建议:** 添加清理方法。

### 4.7 PluginLoader 模块未清理

**文件:** `system/plugins/loader.py`（行 62-69）

模块添加到 `sys.modules` 但卸载时从未移除。

**建议:** 卸载时调用 `_purge_package_modules()`。

### 4.8 Theme QSS 缓存无上限

**文件:** `system/theme.py`（行 170, 335）

`_qss_cache` 字典无限增长。

**建议:** 使用 LRU 缓存（如 `functools.lru_cache(maxsize=128)`）。

### 4.9 ThreadPoolExecutor 生命周期问题

**文件:**
- `ui/views/albums_view.py`（行 195-196）
- `ui/widgets/album_card.py`（行 236-262）
- `ui/views/artists_view.py`

Executor 创建但 `shutdown(wait=False)` 不等待完成，或从未 shutdown。

**建议:** 使用共享模块级线程池或确保 `shutdown(wait=True)`。

### 4.10 Bootstrap 关闭不完整

**文件:** `app/bootstrap.py`（行 497-513）

`shutdown_database()` 只处理写入 worker，不刷新仓库的待写入操作。

**建议:** 在关闭数据库前显式刷新所有仓库。

---

## 5. 错误处理

### 5.1 异常被静默吞没（多处）

| 文件 | 行 | 问题 |
|------|------|------|
| `repositories/base_repository.py` | 33-38 | WAL 模式设置失败静默忽略 |
| `services/playback/queue_service.py` | 99-102 | PlayMode 恢复失败 `pass` |
| `services/playback/playback_service.py` | 1752-1754 | `except Exception` 无日志 |
| `services/cloud/baidu_service.py` | 232-236 | 账户信息获取失败 `pass` |
| `system/plugins/manager.py` | 81-103 | 插件注销错误静默捕获 |
| `system/plugins/host_services.py` | 25-29 | JSON 解析静默失败 |
| `infrastructure/audio/audio_engine.py` | 130-136 | 清理异常只记录不上报 |
| `infrastructure/database/sqlite_manager.py` | 914-932 | FTS 索引损坏静默处理 |

**建议:** 所有 `except Exception: pass` 至少添加 `logger.warning()` 或 `logger.debug()`。

### 5.2 事务缺少 Rollback

**文件（多处）:**
- `repositories/album_repository.py` — `refresh()`、`refresh_album()`
- `repositories/artist_repository.py` — `refresh()`、`refresh_artist()`
- `repositories/genre_repository.py` — `refresh()`、`refresh_genre()`
- `repositories/history_repository.py` — `add()`
- `repositories/playlist_repository.py` — `add_track()`

**建议:** 在所有事务方法中添加 try-except-rollback。

### 5.3 Application.run() 缺少异常保护

**文件:** `app/application.py`（行 108-129）

缓存清理、MPRIS 启动没有 try-except。

**建议:** 包装在 try-except 中，记录错误但不崩溃。

### 5.4 HttpClient 错误上下文不足

**文件:** `infrastructure/network/http_client.py`（行 244-246）

通用错误日志不区分网络错误、超时和 HTTP 错误。

**建议:** 区分 `requests.Timeout`、`ConnectionError`、`HTTPError`。

### 5.5 MPRIS UI 分发无错误处理

**文件:** `system/mpris.py`（行 187-191）

**建议:** 添加 try-except。

### 5.6 ScanWorker 元数据提取无错误处理

**文件:** `ui/windows/components/scan_dialog.py`（行 279-320）

`MetadataService.extract_metadata()` 失败时无保护。

**建议:** 添加 try-except 和失败计数。

---

## 6. 代码质量与重复代码

### 6.1 `_normalize_online_provider_id()` 在三个文件中重复

**文件:**
- `repositories/queue_repository.py`（行 23-28）
- `repositories/track_repository.py`（行 34-38）
- `repositories/favorite_repository.py`（行 23-28）

**建议:** 移到共享工具模块 `utils/normalization.py`。

### 6.2 CloudRepository 7 个类似的 UPDATE 查询

**文件:** `repositories/cloud_repository.py`（行 207-281）

`update_account_playing_state()` 有 7 个不同的 UPDATE 分支。

**建议:** 构建动态查询：

```python
def update_account_playing_state(self, account_id: int, **kwargs) -> bool:
    updates = []
    params = []
    for key, col in [('playing_fid', 'last_playing_fid'), ...]:
        if key in kwargs:
            updates.append(f"{col} = ?")
            params.append(kwargs[key])
    updates.append("updated_at = CURRENT_TIMESTAMP")
    params.append(account_id)
    cursor.execute(f"UPDATE cloud_accounts SET {', '.join(updates)} WHERE id = ?", params)
```

### 6.3 拖拽移动代码在 20+ 个对话框中重复

**文件:** 所有无框对话框（`add_to_playlist_dialog.py`、`base_rename_dialog.py`、`message_dialog.py` 等）

**建议:** 创建可复用的 `DraggableDialogMixin`。

### 6.4 封面加载逻辑在三处重复

**文件:**
- `ui/windows/mini_player.py`（行 552-602）
- `ui/windows/now_playing_window.py`（行 410-451）
- `ui/widgets/album_card.py`（行 168-217）

**建议:** 创建可复用的 `CoverLoader` 类。

### 6.5 悬停效果代码重复

**文件:**
- `ui/widgets/album_card.py`（行 285-295）
- `ui/widgets/artist_card.py`（行 245-255）

**建议:** 创建 `HoverEffectMixin`。

### 6.6 冗余的 `sanitize_filename` 包装器

**文件:** `utils/helpers.py`（行 103-115）

包装器每次调用触发模块导入，重复了 `file_helpers.py` 中的函数。

**建议:** 移除包装器，直接从 `file_helpers` 导入。

### 6.7 冗余导入

| 文件 | 行 | 问题 |
|------|------|------|
| `infrastructure/audio/audio_engine.py` | 333, 356 | `import os` 在函数内重复 |
| `system/config.py` | 858 | `import json` 在函数内重复 |
| `utils/lrc_parser.py` | 74-75 | `import re, html` 在函数内 |

### 6.8 未使用的代码

| 文件 | 行 | 问题 |
|------|------|------|
| `utils/file_helpers.py` | 14 | `INVALID_CHARS` 常量定义但未使用 |
| `system/hotkeys.py` | 195, 213 | `player` 参数未使用（已 `del player`） |
| `utils/dedup.py` | 416 | `groups` 变量仅用于 `len()` |

### 6.9 魔法数字

**文件:** `system/config.py`（行 239-249）

`10`（EQ 频段数）出现多次。

**建议:** 定义常量 `EQ_BANDS_COUNT = 10`。

---

## 7. 数据库优化

### 7.1 缺少索引

以下频繁过滤的列缺少索引：

```sql
CREATE INDEX IF NOT EXISTS idx_tracks_path ON tracks(path);
CREATE INDEX IF NOT EXISTS idx_tracks_cloud_file_id ON tracks(cloud_file_id);
CREATE INDEX IF NOT EXISTS idx_tracks_source ON tracks(source);
CREATE INDEX IF NOT EXISTS idx_cloud_files_account_id ON cloud_files(account_id);
CREATE INDEX IF NOT EXISTS idx_cloud_files_parent_id ON cloud_files(account_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_play_history_track_id ON play_history(track_id);
CREATE INDEX IF NOT EXISTS idx_favorites_track_id ON favorites(track_id);
CREATE INDEX IF NOT EXISTS idx_favorites_cloud_file_id ON favorites(cloud_file_id);
CREATE INDEX IF NOT EXISTS idx_cloud_accounts_is_active ON cloud_accounts(is_active);
```

### 7.2 缺少缓存表唯一约束

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_albums_unique ON albums(name, artist);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artists_unique ON artists(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_genres_unique ON genres(name);
```

### 7.3 缺少批量操作方法

**文件:** 多个仓库

以下仓库缺少批量更新方法：
- `album_repository.py` — 批量更新封面路径
- `artist_repository.py` — 批量更新封面路径
- `genre_repository.py` — 批量更新封面路径
- `favorite_repository.py` — 批量添加/移除收藏

### 7.4 WAL 模式未验证

**文件:** `infrastructure/database/sqlite_manager.py`（行 45-46）

设置了 WAL 模式但未验证是否生效。

**建议:** 执行 `PRAGMA journal_mode` 验证。

### 7.5 Genre 刷新使用 DELETE+INSERT 而非 UPSERT

**文件:** `repositories/genre_repository.py`（行 285-336）

**建议:** 使用 `INSERT OR REPLACE`。

### 7.6 FTS 查询可强化 Unicode 安全

**文件:** `infrastructure/database/sqlite_manager.py`（行 86-95）

**建议:** 在构建 FTS 查询前做 Unicode 规范化（`unicodedata.normalize('NFKD', query)`），移除控制字符，限制词项长度。

---

## 8. UI 响应性与渲染优化

### 8.1 `resizeEvent` 中昂贵的 `setMask()` 调用

**文件:** 所有无框对话框（`base_rename_dialog.py` 行 312-317 等）

`QPainterPath → QRegion → setMask()` 在每次 resize 时执行。

**建议:** 使用 `QTimer` 防抖：

```python
def resizeEvent(self, event):
    if not hasattr(self, '_resize_timer'):
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_mask)
    self._resize_timer.start(100)
    super().resizeEvent(event)
```

### 8.2 编辑对话框中 mutagen 阻塞主线程

**文件:** `ui/dialogs/edit_media_info_dialog.py`（行 302-334）

`mutagen.File()` 每个文件可能耗时 100ms+。

**建议:** 移到后台线程。

### 8.3 样式表每次主题刷新时重编译

**文件:** 多个对话框和视图

`findChildren()` + 循环 `setStyleSheet()` 效率低。

**建议:** 缓存子控件引用，避免 `findChildren()`；缓存样式字符串。

### 8.4 Equalizer 主题刷新遍历所有子控件

**文件:** `ui/widgets/equalizer_widget.py`（行 467-488）

**建议:** 在 `_setup_ui()` 中存储控件引用，直接访问。

### 8.5 Pixmap 双重缩放

**文件:** `ui/widgets/artist_card.py`（行 189-213）

Pixmap 先缩放，再在 `_make_circular()` 中再次缩放。

**建议:** 只缩放一次。

### 8.6 默认封面每次创建新 Pixmap

**文件:** `ui/views/album_view.py`（行 500-520）

**建议:** 使用类级别缓存，相同主题参数复用。

### 8.7 主题刷新期间初始化

**文件:** `ui/windows/main_window.py`（行 449-450）

初始化时调用 `refresh_theme()` 可能触发多次样式表更新。

**建议:** 使用 `QTimer.singleShot(0, self.refresh_theme)` 延迟到控件树构建完成后。

### 8.8 icon 缓存 key 使用字符串拼接

**文件:** `ui/icons.py`（行 152-155）

```python
cache_key = f"{icon_name}_{color}_{size}"
```

**建议:** 使用 tuple key `(icon_name, color, size)` 更高效。

---

## 9. 设计与架构改进

### 9.1 Domain 模型缺少 `__slots__`

**文件:** 所有 dataclass 文件

每个实例使用比必要更多的内存。

**建议:** 为所有 dataclass 添加 `__slots__`（或使用 Python 3.10+ 的 `@dataclass(slots=True)`）。

### 9.2 Domain 模型 ID 属性实现不一致

**文件:** `album.py`、`artist.py`、`genre.py`

- `Album.id` — `@cached_property`
- `Artist.id` — `@cached_property`
- `Genre.id` — `@property` + 条件逻辑 + `_named_id` cached_property

**建议:** 统一使用 `@cached_property` 和一致的回退行为。

### 9.3 `SearchType` 应为 Enum

**文件:** `domain/online_music.py`（行 131-137）

```python
class SearchType:
    SONG = "song"
    SINGER = "singer"
    ...
```

**建议:** 转换为 `Enum` 类，与 `PlayMode`、`PlaybackState` 一致。

### 9.4 `PlaylistItem` 可变但提供不可变模式方法

**文件:** `domain/playlist_item.py`

`with_metadata()` 暗示不可变性，但类是可变的。

**建议:** 使用 `@dataclass(frozen=True)` 或移除不可变模式。

### 9.5 服务间紧耦合

**文件:** `services/ai/acoustid_service.py`（行 288-298）

直接在方法内导入 MetadataService。

**建议:** 通过依赖注入接受 `metadata_service` 参数。

### 9.6 ThemeManager QSS 缓存使用不稳定 hash

**文件:** `system/theme.py`（行 301-336）

`hash(template)` 可能碰撞，跨运行不稳定。

**建议:** 使用 `hashlib.sha256(template.encode()).hexdigest()`。

### 9.7 ConfigManager 缓存无 TTL/失效

**文件:** `system/config.py`（行 107-178）

缓存永不失效，可能提供过时数据。

**建议:** 添加 TTL 或显式失效机制。

### 9.8 缺少配置值范围验证

**文件:** `system/config.py`

- `set_volume()` 不验证 0-100 范围
- `set_audio_effects()` 不验证效果值范围

**建议:** 添加 `max(0, min(100, int(volume)))` 类型的钳制。

---

## 10. 输入验证与边界检查

### 10.1 Repository 方法缺少输入验证

| 文件 | 方法 | 问题 |
|------|------|------|
| `album_repository.py` | `get_by_name()` | 不验证 `album_name` 非空 |
| `artist_repository.py` | `get_by_name()` | 不验证 `artist_name` 非空 |
| `genre_repository.py` | `get_by_name()` | 不验证 `name` 非空 |
| `track_repository.py` | `search()` | 不验证 `query` 非空 |

### 10.2 Domain 工厂方法缺少验证

**文件:** `domain/playlist_item.py`

- `from_track()` 不验证 `track` 非 None
- `from_cloud_file()` 不验证输入
- `from_dict()` 不验证必需键
- 行 177, 185: `int()` / `float()` 转换无 try-except

### 10.3 文件路径操作缺少验证

**文件:** `utils/file_helpers.py`（行 39-81）

`calculate_target_path()` 不验证 `target_dir` 存在或可写。

### 10.4 服务层输入验证

**文件:**
- `services/cloud/cache_paths.py`（行 11-19）— 不验证 `download_dir` 和 `cloud_file`
- `services/library/file_organization_service.py`（行 77-80）— 不检查写权限
- `services/playback/queue_service.py`（行 86-92）— 空列表时索引 0 仍无效

### 10.5 时区硬编码

**文件:** `utils/helpers.py`（行 226-237）

`format_relative_time()` 硬编码北京时区（+8 小时）。

**建议:** 使用系统时区。

### 10.6 i18n 缺少语言验证日志

**文件:** `system/i18n.py`（行 55-62）

无效语言静默回退到 "en"。

**建议:** 记录日志。

---

## 11. 优先级执行路线图

### Phase 1 — 立即修复（CRITICAL）

| # | 问题 | 影响 |
|---|------|------|
| 1 | 移除 `_row_to_track()` 中的 UPDATE（§1.1） | 消除 N+1 查询 |
| 2 | 修复 AudioEngine 锁外 item 访问（§1.2） | 防止数据损坏/崩溃 |
| 3 | 添加缺失的数据库索引（§7.1） | 查询性能大幅提升 |
| 4 | DBWriteWorker 队列溢出处理（§1.4） | 防止死锁 |
| 5 | 修复 Genre ID 非确定性回退（§1.5） | 修复逻辑错误 |

### Phase 2 — 高优先级

| # | 问题 | 影响 |
|---|------|------|
| 6 | 单例模式添加线程安全（§2.2） | 防止竞态条件 |
| 7 | 所有仓库事务添加 rollback（§5.2） | 数据一致性 |
| 8 | 优化缓存表存在性检查（§3.1） | 减少冗余查询 |
| 9 | MpvBackend `_media_ready` 加锁（§2.7） | 修复播放竞态 |
| 10 | 静默异常改为日志记录（§5.1） | 可调试性 |

### Phase 3 — 中优先级

| # | 问题 | 影响 |
|---|------|------|
| 11 | UI 信号连接清理（§4.4） | 防止内存泄漏 |
| 12 | 重复代码提取公共组件（§6.1-6.5） | 可维护性 |
| 13 | 添加批量操作方法（§7.3） | 性能提升 |
| 14 | `resizeEvent` 防抖（§8.1） | UI 流畅性 |
| 15 | 输入验证（§10.1-10.4） | 健壮性 |

### Phase 4 — 低优先级

| # | 问题 | 影响 |
|---|------|------|
| 16 | Domain 模型添加 `__slots__`（§9.1） | 内存优化 |
| 17 | 清理冗余导入/未使用代码（§6.7-6.8） | 代码整洁 |
| 18 | Pixmap 缓存与优化（§8.5-8.6） | 渲染性能 |
| 19 | ConfigManager 缓存 TTL（§9.7） | 数据新鲜度 |
| 20 | 歌词二分查找替代线性搜索（§3.8） | 性能微优化 |

---

## 统计摘要

| 类别 | 数量 | 严重 | 高 | 中 | 低 |
|------|------|------|------|------|------|
| 线程安全 | 9 | 1 | 3 | 5 | 0 |
| 性能优化 | 14 | 1 | 2 | 8 | 3 |
| 资源/内存泄漏 | 10 | 1 | 2 | 6 | 1 |
| 错误处理 | 6 | 0 | 1 | 4 | 1 |
| 代码质量/重复 | 9 | 0 | 0 | 4 | 5 |
| 数据库 | 6 | 1 | 1 | 3 | 1 |
| UI 响应性 | 8 | 0 | 1 | 5 | 2 |
| 设计/架构 | 8 | 1 | 0 | 5 | 2 |
| 输入验证 | 6 | 0 | 0 | 4 | 2 |
| **合计** | **76** | **5** | **10** | **44** | **17** |
# Harmony 音乐播放器 — 10 万首歌曲可扩展性分析

**日期：** 2026-04-02
**范围：** 数据库层、服务层、UI 渲染层、启动流程全链路分析
**结论：** 当前架构无法支撑 10 万首歌曲，需针对性优化实现细节

---

## 一、总体结论

当前实现针对 **1,000~5,000 首**歌曲优化，在 10 万首规模下会出现严重性能问题。架构设计（分层、依赖注入、EventBus）本身是合理的，但数据访问层和 UI 渲染层缺少大数据量下的关键优化（分页、索引、虚拟滚动、批量操作）。**需要改的是实现细节而非架构本身。**

---

## 二、量化影响预估

| 指标 | 当前 (5K 歌曲) | 10 万首歌曲 | 问题程度 |
|------|---------------|------------|---------|
| 启动时间 | 2~5 秒 | **15~30 秒** | 严重 |
| 首次扫描入库 | 几分钟 | **4+ 小时** | 致命 |
| 点击"播放全部" | <1 秒 | **5+ 分钟** | 致命 |
| 内存占用 | 50~100 MB | **500 MB~1.5 GB** | 严重 |
| 搜索响应 | <100 ms | **500 ms~1 秒** | 中等 |
| 随机播放切歌 | <10 ms | **65 ms** | 可接受 |

---

## 三、5 个致命瓶颈详解

### 3.1 Library View 使用 QTableWidget — 直接卡死 UI

**文件：** `ui/views/library_view.py`（第 351~973 行）

**问题：** 使用 `QTableWidget` 渲染曲目列表，每个单元格都创建一个 QWidget 对象。

**10 万首歌的影响：**
- 10 万首歌 × 7 列 = **70 万个 widget 对象**
- 内存消耗：~**1.2 GB**（仅 table items）
- UI 冻结 **5~10 秒**（创建 + 填充循环）
- `setRowCount(len(tracks))` + 循环 `setItem()` 为 O(n) 阻塞操作

**对比：** 项目中 `local_tracks_list_view.py` 已使用 QListView + QAbstractListModel + Delegate 模式（虚拟滚动，只渲染可见行），但主 Library 视图没有跟进。

**代码示例：**
```python
# library_view.py 第 891~970 行 — 逐行创建 widget
self._tracks_table.setRowCount(len(tracks))
for row, track in enumerate(tracks):
    self._tracks_table.setItem(row, 0, QTableWidgetItem(track.title))
    self._tracks_table.setItem(row, 1, QTableWidgetItem(track.artist))
    # ... 7 列，每列一个 QTableWidgetItem
    if row % 50 == 0:
        QApplication.processEvents()  # 每 50 行让 UI 喘口气
```

---

### 3.2 Path.exists() 逐文件检查 — 播放操作耗时数分钟

**文件：**
- `services/playback/playback_service.py`（第 334~360, 450~460 行）
- `services/playback/queue_service.py`（第 130, 188 行）
- `infrastructure/audio/audio_engine.py`（第 528, 575, 709, 761 行）

**问题：** 播放时对每首歌调用 `Path(t.path).exists()`，这是一次磁盘 I/O 系统调用（~1-5ms/次）。

**10 万首歌的影响：**
```
100,000 首 × 3ms/次 = 300,000 ms = 5 分钟
```

每次点击"播放全部"、恢复队列、加载播放列表都会触发。

**代码示例：**
```python
# playback_service.py 第 450~460 行
for t in tracks:
    is_online = not t.path or t.source == TrackSource.QQ
    if is_online or Path(t.path).exists():  # 每首歌一次磁盘 I/O
        item = PlaylistItem.from_track(t)
        items.append(item)
```

---

### 3.3 get_all_tracks(limit=0) 加载全部数据到内存

**文件：**
- `repositories/track_repository.py`（第 79~88 行）
- `services/library/library_service.py`（第 125~127 行）

**问题：** `get_all()` 在 `limit=0` 时执行无分页的 `SELECT * FROM tracks`，一次性将全部数据加载为 Python 对象。

**10 万首歌的影响：**
```
100,000 Track 对象 × ~500 字节/个 = 50 MB/次调用
```

在 `play_local_library()`、UI Library 视图加载等多处被调用，且每次都是全量加载。

**代码示例：**
```python
# track_repository.py 第 79~88 行
def get_all(self, limit: int = 0, offset: int = 0) -> List[Track]:
    if limit > 0:
        cursor.execute("SELECT * FROM tracks ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset))
    else:
        cursor.execute("SELECT * FROM tracks ORDER BY id DESC")  # 无 LIMIT！
    rows = cursor.fetchall()
    return [self._row_to_track(row) for row in rows]  # 全部转换为 Python 对象
```

---

### 3.4 关联子查询导致 O(n²) 复杂度

**文件：**
- `repositories/track_repository.py`（第 406~408 行）
- `repositories/album_repository.py`（第 199~202 行）
- `repositories/artist_repository.py`（第 59~61 行）
- `repositories/genre_repository.py`（第 184~186 行）

**问题：** 四个 Repository 的聚合查询都使用相关子查询获取封面路径，每个分组结果触发一次子查询扫描 tracks 表。

**10 万首歌的影响：**
```
5,000 个艺术家 × 子查询扫描 ~20 行 = 100,000 次行扫描（+ 初始 GROUP BY 扫描）
预计耗时：2~5 秒/次（对比 <100ms 使用 MAX 聚合）
```

**代码示例：**
```sql
-- 当前写法（O(n²)）
SELECT t.artist as name, COUNT(*) as song_count,
    (SELECT cover_path FROM tracks t2
     WHERE t2.artist = t.artist AND t2.cover_path IS NOT NULL
     LIMIT 1) as cover_path        -- 每组触发一次子查询
FROM tracks t
WHERE t.artist IS NOT NULL AND t.artist != ''
GROUP BY t.artist

-- 修复写法（O(n)）
SELECT t.artist as name, COUNT(*) as song_count,
    MAX(CASE WHEN t.cover_path IS NOT NULL THEN t.cover_path END) as cover_path
FROM tracks t
WHERE t.artist IS NOT NULL AND t.artist != ''
GROUP BY t.artist
```

---

### 3.5 顺序扫描入库 — 无并行化、无批量插入

**文件：** `services/library/library_service.py`（第 378~414 行）

**问题：** `scan_directory()` 逐文件串行提取元数据（mutagen I/O ~150ms/文件）+ 逐条 INSERT 数据库。

**10 万首歌的影响：**
```
100,000 × 150ms = 15,000,000 ms ≈ 4.2 小时
```

**代码示例：**
```python
# library_service.py 第 378~414 行
def scan_directory(self, directory: str, recursive: bool = True) -> int:
    for file_path in files:
        track = self._create_track_from_file(str(file_path))  # 串行元数据提取
        if track:
            track_id = self._track_repo.add(track)             # 串行数据库插入
            if track_id:
                added_count += 1
```

---

## 四、其他重要瓶颈

| # | 问题 | 位置 | 复杂度 | 10 万首时的影响 |
|---|------|------|--------|---------------|
| 1 | 缺少 `tracks.genre` 索引 | `sqlite_manager.py` | O(n) 全表扫描 | 每次流派查询 ~500ms |
| 2 | 艺术家刷新 3 次全表查询 | `artist_repository.py` 第 148~237 行 | 3 × O(n) | ~1.5~2 秒/次刷新 |
| 3 | FTS5 索引仅在 schema 变更时重建 | `sqlite_manager.py` 第 844~887 行 | O(n) | 搜索退化到 LIKE 全表扫描 ~500ms |
| 4 | 播放列表 cloud_file_id 索引每次全量重建 | `audio_engine.py` 第 80~87 行 | O(n) × 5 次/操作 | ~75ms 额外开销/操作 |
| 5 | 随机播放：全量拷贝 + shuffle + 线性搜索 | `audio_engine.py` 第 839~862 行 | O(n log n) | ~65ms + 60MB 内存 |
| 6 | 所有 11 个 View 启动时立即创建 | `main_window.py` 第 353~412 行 | — | 多消耗 500ms~1s + 20~30MB |
| 7 | 队列恢复使用逐条元数据填充 | `queue_service.py` 第 102~153 行 | O(n) × 3 查询/条 | 10 万队列 = 30 万次查询 |
| 8 | 缺少 PRAGMA 优化 | `sqlite_manager.py` 第 37~46 行 | — | 写入性能低 15~25% |
| 9 | 无队列大小限制 | `queue_view.py` | — | 内存无限增长 |
| 10 | 搜索过滤为 Python 端线性扫描 | `library_view.py` 第 979~984 行 | O(n)/每次按键 | 每次按键扫描 10 万条 |

---

## 五、内存占用拆解（10 万首歌曲）

| 组件 | 预估大小 | 说明 |
|------|---------|------|
| Library View QTableWidget | ~1,200 MB | 70 万个 QTableWidgetItem |
| Track 对象（全量加载） | ~50 MB | 100K × 500 字节 |
| PlaylistItem 对象 | ~30 MB | 100K × 300 字节 |
| 播放列表副本（shuffle 模式） | ~60 MB | 原始 + 随机各一份 |
| 图片缓存（封面） | ~128 MB | QPixmapCache 上限 |
| SQLite 页缓存 | ~10 MB | 默认配置 |
| **合计** | **~1.5 GB** | 对比当前 5K 歌曲 ~80 MB |

---

## 六、启动流程耗时拆解（10 万首歌曲）

```
Bootstrap 初始化                          ~1 秒
├─ SQLite 连接 + PRAGMA 设置
├─ 迁移检查 + FTS5 验证/重建              ~1~2 秒（schema 变更时）
│
LibraryService.init_albums_artists()      ~5~10 秒
├─ album_repo.refresh()                   ~2~3 秒（关联子查询）
├─ artist_repo.refresh()                  ~3~5 秒（3 次全表扫描）
│
MainWindow 创建                           ~2~3 秒
├─ 11 个 View 全部立即初始化
├─ Library View 加载全部歌曲              ~5~10 秒（QTableWidget 填充）
│
总计                                      ~15~30 秒
```

---

## 七、最小改动清单（支撑 10 万首）

按优先级排序，前 5 项完成后即可基本可用：

### 第一优先级 — 致命问题修复

| # | 改动 | 预计耗时 | 效果 |
|---|------|---------|------|
| 1 | **替换 Library View 的 QTableWidget** 为 QListView + Model + Delegate（参考 `local_tracks_list_view.py`） | 4~6 小时 | 内存 1.2GB → 250MB，加载从卡死变流畅 |
| 2 | **预建 Path 存在性缓存**，用 set 查找替代逐文件 stat | 1~2 小时 | "播放全部"从 5 分钟 → <20 秒 |
| 3 | **替换关联子查询**为 `MAX(CASE WHEN ... THEN ... END)` | 2~3 小时 | 刷新从 2~5 秒 → <200ms |
| 4 | **get_all_tracks 加默认分页** + UI 懒加载 | 3~4 小时 | 单次调用内存 50MB → 5MB |
| 5 | **添加缺失索引**（`tracks.genre`、`genres.name` 等） | 30 分钟 | 流派查询提速 10~50 倍 |

### 第二优先级 — 重要优化

| # | 改动 | 预计耗时 | 效果 |
|---|------|---------|------|
| 6 | 并行化元数据提取（ThreadPoolExecutor × 4）+ 批量 INSERT | 4~6 小时 | 扫描入库从 4 小时 → 30~60 分钟 |
| 7 | View 懒加载（仅在首次切换到该视图时创建） | 3~4 小时 | 启动时间减少 500ms~1s |
| 8 | 增量更新 cloud_file_id 索引（替代全量重建） | 1~2 小时 | 播放列表操作减少 70% 开销 |
| 9 | 添加 PRAGMA 优化（`synchronous=NORMAL`、`cache_size=10000`） | 15 分钟 | 写入性能提升 15~25% |
| 10 | 确保队列恢复始终使用批量元数据填充 | 1~2 小时 | 队列恢复从 30 万次查询 → 3 次 |

### 第三优先级 — 锦上添花

| # | 改动 | 预计耗时 | 效果 |
|---|------|---------|------|
| 11 | 合并艺术家刷新的 3 次全表查询为 1 次 | 1~2 小时 | 刷新时间减半 |
| 12 | FTS5 索引增量维护（触发器 + 每次启动验证） | 1~2 小时 | 搜索始终走 FTS5，<10ms |
| 13 | 搜索过滤改为数据库端执行 | 2~3 小时 | 每次按键从 O(n) → O(log n) |
| 14 | 随机播放优化（用 Fisher-Yates 原地 shuffle，索引增量更新） | 1~2 小时 | shuffle 内存减半，速度提升 4~6 倍 |
| 15 | 添加队列大小上限（如 50,000） | 30 分钟 | 防止内存无限增长 |

**总工期估算：3~5 天**

---

## 八、修复后预期效果

| 指标 | 修复前 (10 万首) | 修复后 (10 万首) | 提升倍数 |
|------|-----------------|-----------------|---------|
| 启动时间 | 15~30 秒 | **3~5 秒** | 3~6× |
| 播放全部 | 5+ 分钟 | **10~20 秒** | 15~30× |
| 内存占用 | 500 MB~1.5 GB | **80~150 MB** | 5~10× |
| 搜索响应 | 500 ms~1 秒 | **<50 ms** | 10~20× |
| 扫描入库 | 4+ 小时 | **30~60 分钟** | 4~8× |
| 刷新专辑/艺术家 | 2~5 秒 | **<200 ms** | 10~25× |

---

## 九、总结

**架构层面：** 分层设计、依赖注入、EventBus 解耦等架构决策是正确的，不需要重构。

**实现层面：** 5 个核心问题阻碍了大规模扩展：
1. UI 渲染未使用虚拟滚动（QTableWidget vs QListView+Delegate）
2. 数据加载无分页（全量 SELECT + 全量内存）
3. SQL 查询有 O(n²) 关联子查询 + 缺失索引
4. 播放链路逐文件磁盘 I/O（Path.exists）
5. 入库流程串行且无批量操作

这些都是**实现细节层面的优化**，不涉及架构变更，预计 3~5 天可完成核心修复
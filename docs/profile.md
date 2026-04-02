# Harmony 运行性能分析指南

**日期**: 2026-03-31  
**适用版本**: Harmony 1.0  
**技术栈**: Python 3.11+ / PySide6 / SQLite  

---

## 一、分析工具总览

| 工具 | 类型 | 侵入性 | 适用场景 | 安装方式 |
|------|------|--------|----------|----------|
| **py-spy** | 采样式 Profiler | 零侵入 | 整体热点定位、火焰图 | `pip install py-spy` |
| **cProfile** | 确定性 Profiler | 低（命令行参数） | 函数调用次数与耗时统计 | Python 内置 |
| **snakeviz** | cProfile 可视化 | 无 | 可视化 cProfile 结果 | `pip install snakeviz` |
| **memray** | 内存分析器 | 低 | 内存泄漏、内存热点 | `pip install memray` |
| **tracemalloc** | 内存追踪 | 低（代码插桩） | 精确内存分配追踪 | Python 内置 |
| **importtime** | 导入时间分析 | 零侵入 | 启动阶段慢导入定位 | Python 内置（`-X importtime`） |
| **time.perf_counter** | 手动打桩 | 中（需改代码） | 精确测量特定代码段耗时 | Python 内置 |
| **QElapsedTimer** | Qt 计时器 | 中（需改代码） | UI 操作耗时测量 | PySide6 内置 |

---

## 二、推荐分析流程

```
步骤 1: 启动时间分析 (importtime)
    ↓
步骤 2: 整体热点定位 (py-spy 火焰图)
    ↓
步骤 3: 启动各阶段耗时 (手动打桩)
    ↓
步骤 4: 数据库查询分析 (SQLite trace)
    ↓
步骤 5: 内存分析 (memray)
    ↓
步骤 6: 特定功能深入分析 (cProfile + snakeviz)
```

---

## 三、具体操作方法

### 3.1 cProfile — 函数级性能分析

最基础的分析方式，直接命令行运行，无需改代码。

#### 基本用法

```bash
# 全量 profiling，输出到文件
uv run python -m cProfile -o profile.prof main.py

# 查看结果（按累计时间排序，显示前 50 项）
uv run python -c "
import pstats
p = pstats.Stats('profile.prof')
p.sort_stats('cumulative')
p.print_stats(50)
"

# 按调用次数排序
uv run python -c "
import pstats
p = pstats.Stats('profile.prof')
p.sort_stats('calls')
p.print_stats(50)
"

# 只看特定模块
uv run python -c "
import pstats
p = pstats.Stats('profile.prof')
p.sort_stats('cumulative')
p.print_stats('services/')
"
```

#### snakeviz 可视化

```bash
# 安装并启动可视化（会打开浏览器）
uv run --with snakeviz snakeviz profile.prof
```

snakeviz 提供交互式的 sunburst 图和 icicle 图，可以直观看到哪些函数消耗了最多时间。

#### 局限性

- 对 Qt 事件循环内的性能热点捕获不够精细
- 适合分析启动阶段和非 UI 逻辑
- 确定性 profiling 会使程序变慢 2-5 倍

---

### 3.2 py-spy — 采样式 Profiler（推荐）

零侵入的采样式分析器，特别适合 GUI 应用，几乎不影响运行性能。

#### 安装

```bash
pip install py-spy
```

#### 实时 top 视图

类似 `htop`，实时查看最耗 CPU 的函数：

```bash
# 启动新进程并分析
sudo py-spy top -- uv run python main.py

# 附加到已运行的进程
sudo py-spy top --pid <PID>
```

#### 生成火焰图

```bash
# 启动新进程，录制并生成 SVG 火焰图
sudo py-spy record -o flamegraph.svg -- uv run python main.py

# 附加到已运行进程，录制 60 秒
sudo py-spy record -o flamegraph.svg --pid <PID> --duration 60

# 生成 speedscope 格式（可在 https://www.speedscope.app/ 打开）
sudo py-spy record -o profile.speedscope.json --format speedscope -- uv run python main.py
```

#### 火焰图解读

- **横轴宽度**: 函数在采样中出现的比例（越宽 = 越耗时）
- **纵轴**: 调用栈深度（底部是入口，顶部是叶子函数）
- **颜色**: 无特殊含义，仅用于区分不同函数
- **关注点**: 顶部的宽色块 = 性能瓶颈

#### 优势

- 几乎不影响应用性能（采样开销 < 1%）
- 能看到 C 扩展（Qt、SQLite）的调用栈
- 火焰图直观定位热点
- 支持附加到已运行进程

---

### 3.3 启动时间分析

Harmony 启动涉及大量模块导入和数据库初始化，可以专门分析。

#### Python 导入时间分析

```bash
# 输出每个模块的导入时间
uv run python -X importtime main.py 2> import_time.log

# 按耗时排序查看最慢的导入
sort -t'|' -k2 -rn import_time.log | head -30
```

输出格式示例：
```
import time: self [us] | cumulative | imported package
import time:       234 |        234 | json
import time:     15432 |      18765 | PySide6.QtWidgets
```

- `self`: 模块自身的导入时间（微秒）
- `cumulative`: 包含子依赖的累计时间

#### 手动打桩测量启动阶段

在 `main.py` 的 `main()` 函数中临时添加计时代码：

```python
import time

def main():
    t_start = time.perf_counter()

    # ... Qt 初始化 ...
    qt_app = QApplication(sys.argv)
    t_qt = time.perf_counter()

    # ... 字体加载 ...
    FontLoader.instance().load_fonts()
    t_font = time.perf_counter()

    # ... 依赖注入 ...
    app = Application.create(qt_app)
    t_bootstrap = time.perf_counter()

    # ... 主窗口初始化 ...
    window = MainWindow()
    t_window = time.perf_counter()

    # ... 显示 ...
    window.show()
    t_show = time.perf_counter()

    print(f"=== 启动时间分析 ===")
    print(f"QApplication 初始化: {t_qt - t_start:.3f}s")
    print(f"字体加载:            {t_font - t_qt:.3f}s")
    print(f"Bootstrap (DI):      {t_bootstrap - t_font:.3f}s")
    print(f"MainWindow 初始化:   {t_window - t_bootstrap:.3f}s")
    print(f"窗口显示:            {t_show - t_window:.3f}s")
    print(f"总启动时间:          {t_show - t_start:.3f}s")

    sys.exit(app.run())
```

---

### 3.4 特定模块的精细分析

对已知的性能敏感区域，使用装饰器做定点 profiling。

#### 性能分析装饰器

创建临时工具文件（分析完成后删除）：

```python
# utils/profiling.py
import time
import functools
import logging

logger = logging.getLogger(__name__)

def profile_method(threshold_ms: float = 100):
    """
    装饰器：记录方法执行时间。

    Args:
        threshold_ms: 只记录超过此阈值（毫秒）的调用
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms > threshold_ms:
                logger.warning(
                    f"SLOW: {func.__qualname__} took {elapsed_ms:.1f}ms"
                )
            return result
        return wrapper
    return decorator


def profile_block(name: str):
    """
    上下文管理器：测量代码块执行时间。

    用法:
        with profile_block("数据库查询"):
            results = db.get_all_tracks()
    """
    class _Timer:
        def __enter__(self):
            self.start = time.perf_counter()
            return self

        def __exit__(self, *args):
            elapsed_ms = (time.perf_counter() - self.start) * 1000
            logger.info(f"[PROFILE] {name}: {elapsed_ms:.1f}ms")

    return _Timer()
```

#### 使用示例

```python
from utils.profiling import profile_method, profile_block

class LibraryService:
    @profile_method(threshold_ms=200)
    def scan_directory(self, directory, recursive=True):
        # ... 原有逻辑 ...
        pass

    def rebuild_albums_artists(self):
        with profile_block("重建专辑索引"):
            # ... 专辑重建 ...
            pass
        with profile_block("重建艺术家索引"):
            # ... 艺术家重建 ...
            pass
```

#### 重点关注模块

| 模块 | 文件 | 行数 | 关注原因 |
|------|------|------|----------|
| 数据库管理 | `infrastructure/database/sqlite_manager.py` | 3,551 | 最大文件，所有 SQL 查询 |
| 音乐库扫描 | `services/library/library_service.py` | — | 目录扫描、批量添加 |
| 元数据解析 | `services/metadata/metadata_service.py` | — | mutagen 文件解析 |
| 封面服务 | `services/metadata/cover_service.py` | — | 封面下载和缓存 |
| 播放服务 | `services/playback/playback_service.py` | 1,782 | 播放切换、队列操作 |
| 主窗口 | `ui/windows/main_window.py` | 1,828 | 初始化耗时 |

---

### 3.5 数据库性能分析

SQLite 查询是桌面应用中常见的性能瓶颈。

#### 启用查询日志

在 `sqlite_manager.py` 中临时添加：

```python
def _get_connection(self):
    if not hasattr(self.local, "conn"):
        self.local.conn = sqlite3.connect(self.db_path, ...)
        # 临时：记录所有 SQL 查询及其耗时
        self.local.conn.set_trace_callback(
            lambda sql: logging.debug(f"SQL: {sql}")
        )
    return self.local.conn
```

#### 带耗时的查询日志

```python
import time

class SQLProfiler:
    """SQLite 查询性能分析器"""

    def __init__(self, threshold_ms: float = 50):
        self.threshold_ms = threshold_ms
        self.queries = []  # (sql, duration_ms)

    def trace(self, sql: str):
        """作为 set_trace_callback 的回调"""
        self._current_sql = sql
        self._start = time.perf_counter()

    def profile(self, sql: str, rows: int):
        """
        启用方式: conn.set_trace_callback(profiler.trace)
        注意: set_trace_callback 不直接支持耗时，
        需要搭配 execute 包装使用。
        """
        pass

    def report(self):
        """输出慢查询报告"""
        slow = [(sql, ms) for sql, ms in self.queries if ms > self.threshold_ms]
        slow.sort(key=lambda x: -x[1])
        for sql, ms in slow[:20]:
            print(f"  {ms:.1f}ms | {sql[:120]}")
```

#### 分析查询计划

```bash
uv run python -c "
import sqlite3

conn = sqlite3.connect('Harmony.db')

# 检查索引
print('=== 表索引 ===')
for row in conn.execute(\"SELECT name FROM sqlite_master WHERE type='index'\").fetchall():
    print(f'  {row[0]}')

# 分析常见查询
queries = [
    'SELECT * FROM tracks WHERE title LIKE \"%test%\"',
    'SELECT * FROM tracks WHERE artist = \"Unknown\"',
    'SELECT DISTINCT album FROM tracks',
]

print()
print('=== 查询计划 ===')
for q in queries:
    print(f'Query: {q}')
    plan = conn.execute(f'EXPLAIN QUERY PLAN {q}').fetchall()
    for row in plan:
        print(f'  {row}')
    print()
"
```

#### 数据库统计信息

```bash
uv run python -c "
import sqlite3, os

db_path = 'Harmony.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    print(f'数据库大小: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB')

    tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()
    for (table,) in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM [{table}]').fetchone()[0]
        print(f'  {table}: {count} 行')
"
```

---

### 3.6 Qt/UI 性能分析

PySide6 特有的分析方法。

#### Qt 调试日志

```bash
# 启用事件循环计时器调试
QT_LOGGING_RULES="qt.core.timer.debug=true" uv run python main.py

# 启用 widget 重绘日志
QT_LOGGING_RULES="qt.widgets.painting=true" uv run python main.py

# 启用全部 Qt 调试日志（输出量大）
QT_LOGGING_RULES="*.debug=true" uv run python main.py 2>&1 | head -500
```

#### QElapsedTimer 测量 UI 操作

```python
from PySide6.QtCore import QElapsedTimer

class LibraryView:
    def _populate_tracks_table(self, tracks):
        timer = QElapsedTimer()
        timer.start()

        # ... 填充表格逻辑 ...

        elapsed = timer.elapsed()  # 毫秒
        if elapsed > 200:
            logger.warning(f"_populate_tracks_table: {elapsed}ms for {len(tracks)} tracks")
```

#### 检测 UI 卡顿

在主事件循环中检测长时间阻塞：

```python
from PySide6.QtCore import QTimer, QElapsedTimer

class UIFreezeDetector:
    """检测 UI 线程卡顿（超过阈值的事件循环阻塞）"""

    def __init__(self, threshold_ms: int = 200):
        self.threshold_ms = threshold_ms
        self._timer = QTimer()
        self._timer.timeout.connect(self._check)
        self._timer.start(100)  # 每 100ms 检查一次
        self._elapsed = QElapsedTimer()
        self._elapsed.start()

    def _check(self):
        elapsed = self._elapsed.elapsed()
        if elapsed > self.threshold_ms:
            logger.warning(f"UI freeze detected: {elapsed}ms since last check")
        self._elapsed.restart()
```

在 `main.py` 中临时启用：

```python
# 开发调试时启用
freeze_detector = UIFreezeDetector(threshold_ms=200)
```

---

### 3.7 内存分析

#### memray（推荐）

```bash
# 录制内存使用
uv run --with memray memray run main.py

# 生成火焰图
uv run --with memray memray flamegraph memray-*.bin -o memory_flamegraph.html

# 生成表格报告
uv run --with memray memray table memray-*.bin

# 生成统计摘要
uv run --with memray memray stats memray-*.bin

# 检测内存泄漏（只显示未释放的分配）
uv run --with memray memray flamegraph --leaks memray-*.bin -o leaks.html
```

#### tracemalloc（内置，无需安装）

在 `main.py` 顶部临时添加：

```python
import tracemalloc
tracemalloc.start(25)  # 保存 25 帧调用栈

# 在需要检查的时刻（如运行 30 秒后）获取快照
import signal

def dump_memory_stats(signum, frame):
    """按 Ctrl+C 时输出内存统计"""
    snapshot = tracemalloc.take_snapshot()
    print("\n=== 内存使用 Top 20 (按行号) ===")
    for stat in snapshot.statistics('lineno')[:20]:
        print(stat)

    print("\n=== 内存使用 Top 20 (按文件) ===")
    for stat in snapshot.statistics('filename')[:20]:
        print(stat)

signal.signal(signal.SIGUSR1, dump_memory_stats)
print(f"发送 SIGUSR1 查看内存: kill -USR1 {os.getpid()}")
```

#### 对比两个时间点的内存增长

```python
import tracemalloc

tracemalloc.start()

# 时间点 1：启动后
snapshot1 = tracemalloc.take_snapshot()

# ... 执行一些操作（如扫描音乐库）...

# 时间点 2：操作后
snapshot2 = tracemalloc.take_snapshot()

# 查看内存增长
print("=== 内存增长 Top 20 ===")
for stat in snapshot2.compare_to(snapshot1, 'lineno')[:20]:
    print(stat)
```

---

## 四、Harmony 项目特定关注点

基于代码库分析，以下区域最可能存在性能问题：

### 4.1 数据库层

| 关注点 | 文件 | 说明 |
|--------|------|------|
| `sqlite_manager.py` 巨型类 | `infrastructure/database/sqlite_manager.py` (3,551 行) | 所有 SQL 集中于此，查询可能缺少索引优化 |
| FTS5 搜索性能 | 同上 | 全文搜索在大音乐库时的性能 |
| 播放队列持久化 | `services/playback/playback_service.py` | 频繁的队列保存/恢复操作 |

### 4.2 UI 层

| 关注点 | 文件 | 说明 |
|--------|------|------|
| 大列表渲染 | `ui/views/library_view.py` (2,128 行) | 上千首歌曲的表格渲染 |
| 封面加载 | `ui/workers/batch_cover_worker.py` | 批量封面下载和显示 |
| 歌词滚动 | `ui/widgets/lyrics_widget.py` | 60 FPS 刷新率（`timer.start(16)`） |
| 在线视图 | `ui/views/online_music_view.py` (3,213 行) | 网络请求 + 动态 UI 加载 |

### 4.3 服务层

| 关注点 | 文件 | 说明 |
|--------|------|------|
| 音乐库扫描 | `services/library/library_service.py` | 大量文件的元数据解析 |
| 封面获取 | `services/metadata/cover_service.py` | 多数据源查找 + 网络请求 |
| 云文件下载 | `services/cloud/download_service.py` | 下载进度和并发管理 |

---

## 五、性能分析结果保存

建议将分析结果保存到 `docs/profiling/` 目录：

```bash
mkdir -p docs/profiling

# 保存火焰图
sudo py-spy record -o docs/profiling/flamegraph_$(date +%Y%m%d).svg -- uv run python main.py

# 保存 cProfile 结果
uv run python -m cProfile -o docs/profiling/profile_$(date +%Y%m%d).prof main.py

# 保存导入时间
uv run python -X importtime main.py 2> docs/profiling/import_time_$(date +%Y%m%d).log

# 保存内存报告
uv run --with memray memray run -o docs/profiling/memory_$(date +%Y%m%d).bin main.py
```

---

## 六、注意事项

1. **所有临时代码分析完后务必删除**，不要提交到版本库
2. **py-spy 需要 root 权限**（Linux 上需要 `sudo` 或修改 `ptrace_scope`）
3. **cProfile 会使程序变慢 2-5 倍**，不代表真实性能
4. **采样式分析器 (py-spy) 的结果是统计近似值**，不是精确计数
5. **GUI 应用的性能瓶颈通常在 UI 线程**，关注事件循环阻塞
6. **数据库分析需要真实数据**，空库测试结果没有参考意义
7. **内存分析建议运行较长时间**（5-10 分钟），以捕获泄漏
# Harmony 全面代码审查 Bug 报告

**日期**: 2026-04-02
**范围**: 全项目代码审查（domain / infrastructure / repositories / services / system / app / ui）
**方法**: 逐层阅读全部 Python 源文件，关键 Bug 已通过二次源码验证确认

---

## 目录

- [一、严重 Bug（CRITICAL）](#一严重-bugcritical)
- [二、高优先级 Bug（HIGH）](#二高优先级-bughigh)
- [三、中优先级 Bug（MEDIUM）](#三中优先级-bugmedium)
- [四、低优先级 Bug / 代码质量问题（LOW）](#四低优先级-bug--代码质量问题low)
- [五、测试问题](#五测试问题)
- [六、统计总览](#六统计总览)

---

## 一、严重 Bug（CRITICAL）

### C-01 | eval() 执行不可信数据 — 安全漏洞

- **文件**: `ui/views/queue_view.py` ~行 197
- **代码**:
  ```python
  source_rows = eval(data.data("application/x-queueitem").data().decode())
  ```
- **问题**: 使用 `eval()` 解析拖放 MIME 数据，可执行任意 Python 代码。
- **修复**: 改用 `ast.literal_eval()` 或 `json.loads()`。

---

### C-02 | DBWriteWorker._get_connection() 竞态条件

- **文件**: `infrastructure/database/db_write_worker.py` ~行 64-76
- **代码**:
  ```python
  def _get_connection(self) -> sqlite3.Connection:
      if self._conn is None:          # 无锁保护
          self._conn = sqlite3.connect(...)
      return self._conn
  ```
- **问题**: 多线程同时调用时可能创建多个数据库连接，违反单连接保证。
- **修复**: 加入双重检查锁（double-check locking），使用 `self._start_lock`。

---

### C-03 | SqliteManager 直接访问 _write_worker._conn

- **文件**: `infrastructure/database/sqlite_manager.py` 行 1552, 1583, 1677, 1720, 1761, 1781, 1804
- **代码**:
  ```python
  conn=self._write_worker._conn  # 多处
  ```
- **问题**: 绕过 `_get_connection()` 的初始化逻辑，当连接尚未创建时访问 `None`，引发 `AttributeError`。
- **修复**: 统一改为 `conn=self._write_worker._get_connection()`。

---

### C-04 | CloudDownloadService 下载竞态条件

- **文件**: `services/cloud/download_service.py` ~行 280-300
- **问题**: 在释放锁之后、双重检查之前的窗口期，另一线程可能启动重复下载。缓存检查在锁外执行，`download_started.emit()` 也在锁外，可能导致状态不一致。
- **修复**: 将缓存检查和 worker 创建都放入锁内，或使用更精细的同步机制。

---

## 二、高优先级 Bug（HIGH）

### H-01 | SleepTimerService 信号重复连接

- **文件**: `services/playback/sleep_timer_service.py` ~行 87
- **代码**:
  ```python
  self._event_bus.track_finished.connect(self._on_track_finished)
  ```
- **问题**: 每次 `start()` 在 track 模式下都会连接信号。若 `_is_active` 为 `False` 时重复调用 `start()`，信号处理器会累积，导致一首歌结束时触发多次回调。
- **修复**: 连接前先断开，或增加已连接状态标记。

---

### H-02 | LibraryService 立即刷新未停止防抖定时器

- **文件**: `services/library/library_service.py` ~行 152-162
- **代码**:
  ```python
  def refresh_albums_artists(self, immediate=False):
      if immediate:
          self._do_refresh()      # 未调用 self._refresh_timer.stop()
      else:
          self._refresh_albums_artist_async()
  ```
- **问题**: `immediate=True` 时未取消待执行的防抖定时器，导致刷新执行两次。
- **修复**: 在 `self._do_refresh()` 前加 `self._refresh_timer.stop()`。

---

### H-03 | EventBus 单例竞态条件

- **文件**: `system/event_bus.py` ~行 154-158
- **代码**:
  ```python
  @classmethod
  def instance(cls) -> "EventBus":
      if cls._instance is None:      # 无锁
          cls._instance = cls()
      return cls._instance
  ```
- **问题**: 多线程并发调用可能创建多个 EventBus 实例，导致信号分散在不同实例中，组件间通信失败。
- **修复**: 加入 `threading.Lock()` 保护。
- **同类问题**: `Application`(app/application.py)、`Bootstrap`(app/bootstrap.py)、`ThemeManager`(system/theme.py) 的单例模式存在相同问题。

---

### H-04 | ConfigManager 缓存非线程安全

- **文件**: `system/config.py` ~行 97-116
- **问题**: `_cache` 字典无锁保护。`get()` 的 check-then-act 模式在并发访问时可能读到不一致状态。
- **修复**: 加入 `threading.RLock()` 保护所有缓存读写操作。

---

### H-05 | Windows 媒体键监听器未保存引用

- **文件**: `system/hotkeys.py` ~行 266-268
- **代码**:
  ```python
  listener = keyboard.Listener(on_press=on_press)
  listener.start()
  # listener 为局部变量，函数返回后被 GC 回收
  ```
- **问题**: 监听器对象是局部变量，函数返回后被垃圾回收，媒体键功能实际不生效。应用退出时也无法正常停止线程。
- **修复**: 保存到模块级变量，并在退出时调用 `cleanup()`。

---

### H-06 | QQMusicClient 音质降级 ValueError

- **文件**: `services/cloud/qqmusic/client.py` ~行 405-408
- **代码**:
  ```python
  if quality not in APIConfig.QUALITY_FALLBACK:
      quality = APIConfig.QUALITY_FALLBACK[0]
  for q in APIConfig.QUALITY_FALLBACK:
      if APIConfig.QUALITY_FALLBACK.index(q) < APIConfig.QUALITY_FALLBACK.index(quality):
          continue
  ```
- **问题**: 当 `quality` 被重新赋值后，`index(quality)` 在每次循环迭代中被重复调用（性能低），且如果列表发生变动可能抛出 `ValueError`。
- **修复**: 预先存储 `start_idx = APIConfig.QUALITY_FALLBACK.index(quality)`，用索引比较。

---

### H-07 | QQMusicQRLogin 列表越界访问

- **文件**: `services/cloud/qqmusic/qr_login.py` ~行 311-318
- **代码**:
  ```python
  data = [p.strip("'") for p in match.group(1).split(",")]
  code_str = data[0]                         # 无越界检查
  ...
  sigx = re.findall(r"...", data[2])[0]      # data[2] 无越界检查
  ```
- **问题**: 如果响应格式异常导致 `data` 元素不足，将抛出 `IndexError`。虽然 line 322 捕获了 `IndexError`，但 `data[0]`（line 312）在 try 块外。
- **修复**: 在访问前检查 `len(data)`。

---

### H-08 | UI 线程外更新 — online_grid_view

- **文件**: `ui/views/online_grid_view.py` ~行 197-220
- **问题**: 使用 `ThreadPoolExecutor` 下载封面后，通过 `QTimer.singleShot` 回调更新 UI。`QTimer` 应在 UI 线程创建才安全。
- **修复**: 使用 `QThread` 替代 `ThreadPoolExecutor`，或确保 `QMetaObject.invokeMethod()` 在主线程执行。

---

### H-09 | CoverController 从工作线程发射信号

- **文件**: `ui/controllers/cover_controller.py` ~行 59
- **问题**: `search_completed` 信号从线程池的工作线程中发射，Qt 信号应从创建 QObject 的线程发射。
- **修复**: 使用 `Qt.QueuedConnection` 确保信号安全传递。

---

### H-10 | LyricsDownloadDialog 使用危险的 thread.terminate()

- **文件**: `ui/dialogs/lyrics_download_dialog.py` ~行 471
- **代码**:
  ```python
  if self._search_thread.isRunning():
      self._search_thread.terminate()   # 危险！
  ```
- **问题**: `terminate()` 强制终止线程，不执行清理，可能导致锁未释放、资源泄漏、数据损坏。
- **修复**: 移除 `terminate()`，改为更长的等待时间，并确保线程中的任务能响应取消标志。

---

### H-11 | QQMusicQRLoginDialog 重启登录时线程未等待

- **文件**: `ui/dialogs/qqmusic_qr_login_dialog.py` ~行 369-382
- **问题**: `_restart_login()` 调用 `old_thread.stop()` 后不等待线程完成，旧线程可能仍在运行并发射信号。
- **修复**: 加入 `old_thread.wait(2000)` 等待旧线程结束。

---

## 三、中优先级 Bug（MEDIUM）

### M-01 | album_repository 不可达的重复代码

- **文件**: `repositories/album_repository.py` ~行 210-214
- **代码**:
  ```python
  conn.commit()
  return True

  conn.commit()    # 不可达
  return True      # 不可达
  ```
- **问题**: `_do_add_track_to_playlist` 中存在重复的 `conn.commit()` + `return True`，第二对永远不会执行。
- **修复**: 删除重复代码。

---

### M-02 | cloud_repository.hard_delete_account 缺少事务回滚

- **文件**: `repositories/cloud_repository.py` ~行 280-289
- **问题**: 删除两张表的数据时无事务保护。若第一个 DELETE 成功、第二个失败，数据处于不一致状态。
- **修复**: 加入 `try/except` 和 `conn.rollback()`。

---

### M-03 | playlist_repository.add_track 缺少显式返回

- **文件**: `repositories/playlist_repository.py` ~行 90-117
- **问题**: 重试循环耗尽后没有显式 `return False`，函数隐式返回 `None`，调用方期望 `bool`。
- **修复**: 在循环后加 `return False`。

---

### M-04 | http_client content-length 解析可能失败

- **文件**: `infrastructure/network/http_client.py` ~行 111
- **代码**:
  ```python
  total_size = int(response.headers.get('content-length', 0))
  ```
- **问题**: 若 HTTP 头返回非数字字符串，`int()` 抛出 `ValueError`。
- **修复**: 用 `try/except (ValueError, TypeError)` 包裹。

---

### M-05 | image_cache TOCTOU 竞态

- **文件**: `infrastructure/cache/image_cache.py` ~行 37-39, 93-96
- **问题**: `get()` 先检查 `cache_path.exists()` 再 `read_bytes()`，`cleanup()` 先检查 `stat()` 再 `unlink()`。文件可能在检查和操作之间被删除。
- **修复**: 在 `get()` 中直接尝试 `read_bytes()` 并捕获 `FileNotFoundError`。

---

### M-06 | MPRIS 信号重复连接

- **文件**: `system/mpris.py` ~行 525-530
- **问题**: `start()` 被多次调用时信号会重复连接，导致处理器被调用多次。
- **修复**: 在 `start()` 开头检查 `if self._service is not None: return`。

---

### M-07 | MPRIS stop() 吞掉所有异常

- **文件**: `system/mpris.py` ~行 544-552
- **问题**: `except Exception: pass` 静默吞掉所有异常，调试困难。
- **修复**: 至少 `logger.warning()` 记录异常。

---

### M-08 | config.py base64 解码使用宽泛异常

- **文件**: `system/config.py` ~行 342, 366
- **代码**:
  ```python
  except Exception:
      return None
  ```
- **问题**: `except Exception` 过于宽泛，可能掩盖非预期异常。
- **修复**: 改为 `except (ValueError, binascii.Error)`。

---

### M-09 | OrganizeFilesDialog 线程无父对象

- **文件**: `ui/dialogs/organize_files_dialog.py` ~行 377-385
- **问题**: `OrganizeFilesThread` 创建时未设置 parent。对话框关闭时线程可能向已销毁的对象发射信号导致崩溃。
- **修复**: 加 `self.organize_thread.setParent(self)`。

---

### M-10 | ThreadPoolExecutor 泄漏 — albums_view / album_card

- **文件**: `ui/views/albums_view.py` ~行 177-220, `ui/widgets/album_card.py` ~行 234-252
- **问题**: `ThreadPoolExecutor` 创建后未存储为实例变量，控件销毁前无法取消；`executor.shutdown(wait=False)` 不保证线程清理。
- **修复**: 将 executor 存为实例变量，在 `closeEvent` 中 `shutdown()`。

---

### M-11 | local_tracks_list_view 类级信号连接泄漏

- **文件**: `ui/views/local_tracks_list_view.py` ~行 201-205
- **问题**: `_cover_loaded_signal` 是类级信号，每个 delegate 实例在 `__init__` 中连接，多个实例会导致信号处理器累积。
- **修复**: 使用实例级信号，或在销毁时断开连接。

---

### M-12 | cloud_drive_view EventBus 信号未断开

- **文件**: `ui/views/cloud/cloud_drive_view.py` ~行 401-407
- **问题**: `_setup_event_bus()` 中连接了多个信号，但视图销毁时从未断开，导致内存泄漏和潜在崩溃。
- **修复**: 在析构函数或 `closeEvent` 中断开所有 EventBus 连接。

---

### M-13 | queue_view 拖拽排序索引调整错误

- **文件**: `ui/views/queue_view.py` ~行 139-150
- **问题**: `remove_tracks()` 中删除多行时，对 `_selection` 集合的索引调整在每次迭代中都重新计算，但处理非连续行时可能产生错误偏移。
- **修复**: 确保 rows 按倒序处理（已有 `sorted(rows, reverse=True)`），验证 selection 调整逻辑。

---

### M-14 | SettingsDialog 验证线程无 parent

- **文件**: `ui/dialogs/settings_dialog.py` ~行 26-45
- **问题**: `VerifyLoginThread` 无 parent，对话框关闭时不会自动清理。
- **修复**: 创建时传入 `parent=self`。

---

### M-15 | MiniPlayer 封面加载线程未管理

- **文件**: `ui/windows/mini_player.py` ~行 508-552
- **问题**: 封面加载线程创建后未存储，无法在窗口关闭时取消。
- **修复**: 存储线程引用，在关闭时取消。

---

### M-16 | PlayerControls 信号连接无清理

- **文件**: `ui/widgets/player_controls.py` ~行 483-522
- **问题**: `_setup_connections()` 连接大量信号（包括 lambda），但无对应断开逻辑。控件销毁重建时信号处理器泄漏。
- **修复**: 在 `closeEvent` 中断开所有信号。

---

### M-17 | online_detail_view 封面加载线程竞态

- **文件**: `ui/views/online_detail_view.py` ~行 102-127
- **问题**: `AlbumCoverLoader` 线程完成时发射信号，但目标控件可能已被销毁。
- **修复**: 使用弱引用或在发射前检查目标有效性。

---

### M-18 | recommend_card CoverLoader 清理不完整

- **文件**: `ui/widgets/recommend_card.py` ~行 61-64
- **问题**: `CoverLoader.__del__` 中 `wait(100)` 超时太短，线程可能仍在运行。未调用 `requestInterruption()`。
- **修复**: 先 `requestInterruption()`，再 `wait(500)`，最后 `terminate()` 作为兜底。

---

### M-19 | MessageDialog._result 可能未初始化

- **文件**: `ui/dialogs/message_dialog.py` ~行 228-231
- **问题**: `exec()` 异常中断时 `_result` 可能未赋值。
- **修复**: 在 `__init__` 中初始化 `self._result = StandardButton.Cancel`。

---

## 四、低优先级 Bug / 代码质量问题（LOW）

### L-01 | domain/playlist_item.py 未使用的 logging 导入

- **文件**: `domain/playlist_item.py` 行 5, 12
- **问题**: 导入了 `logging` 并创建 `logger`，但整个文件未使用。违反 domain 层纯净性原则。
- **修复**: 删除 `import logging` 和 `logger = ...`。

---

### L-02 | db_write_worker 静默吞掉连接关闭异常

- **文件**: `infrastructure/database/db_write_worker.py` ~行 118-119
- **代码**:
  ```python
  except Exception:
      pass
  ```
- **修复**: 改为 `logger.warning()`。

---

### L-03 | CoverPixmapCache.initialize() 非线程安全

- **文件**: `infrastructure/cache/pixmap_cache.py` ~行 15-20
- **问题**: `_initialized` 标志的检查与设置非原子操作。
- **修复**: 加入 `threading.Lock()`。

---

### L-04 | font_loader 加载字体无异常处理

- **文件**: `infrastructure/fonts/font_loader.py` ~行 50-62
- **问题**: `QFontDatabase.addApplicationFont()` 可能因字体文件损坏而异常，但无 try-except。
- **修复**: 包裹 try-except 并记录日志。

---

### L-05 | base_repository 线程本地连接未关闭

- **文件**: `repositories/base_repository.py` ~行 26-35
- **问题**: 回退创建的 thread-local 连接在线程销毁时不会被显式关闭。
- **修复**: 增加 `close()` 方法。

---

### L-06 | track_repository.sync_track_artists 异常无日志

- **文件**: `repositories/track_repository.py` ~行 809-810
- **代码**:
  ```python
  except Exception:
      return False
  ```
- **修复**: 加 `logger.error()`。

---

### L-07 | ThemeManager._apply_and_broadcast 吞掉控件刷新异常

- **文件**: `system/theme.py` ~行 269-270
- **问题**: 控件 `refresh_theme()` 异常被静默记录为 warning，可能掩盖 UI bug。
- **修复**: 改为 `logger.error(..., exc_info=True)`。

---

### L-08 | Application 单例模式不一致

- **文件**: `app/application.py` ~行 29-49
- **问题**: `__init__` 直接设置 `_instance`，`create()` 也设置。直接调用构造函数可绕过单例保护。
- **修复**: 仅在 `create()` 中设置 `_instance`。

---

## 五、测试问题

### T-01 | 测试集因 QApplication 崩溃

- **文件**: `tests/test_queue_delegate.py` 行 12, `tests/test_queue_selection_fix.py` 行 9
- **问题**: 模块级别创建 `QApplication.instance() or QApplication(sys.argv)` 导致多个测试文件冲突，pytest 收集阶段 `Fatal Python error: Aborted`。
- **修复**: 使用 `pytest-qt` 的 `qtbot` fixture 管理 QApplication 生命周期，避免模块级创建。

---

### T-02 | 服务层测试因缺少 libpulse.so 报错

- **文件**: `tests/test_services/`, `tests/test_infrastructure/`
- **问题**: 导入链 `services → infrastructure → audio_engine → PySide6.QtMultimedia` 触发 `ImportError: libpulse.so.0 not found`。7 个测试模块无法收集。
- **修复**: 使用条件导入或 mock，使不依赖音频引擎的测试可在无 PulseAudio 环境中运行。

---

## 六、统计总览

| 严重级别 | 数量 | 类型分布 |
|---------|------|---------|
| CRITICAL | 4 | 安全漏洞 ×1, 竞态条件 ×2, 空指针 ×1 |
| HIGH | 11 | 竞态条件 ×3, 线程安全 ×3, 信号泄漏 ×2, 资源泄漏 ×1, 逻辑错误 ×2 |
| MEDIUM | 19 | 线程管理 ×7, 资源泄漏 ×4, 逻辑错误 ×3, 异常处理 ×3, 事务安全 ×1, 代码重复 ×1 |
| LOW | 8 | 代码质量 ×5, 异常处理 ×3 |
| TEST | 2 | 测试环境问题 |
| **总计** | **44** | |

### 按模块分布

| 模块 | CRITICAL | HIGH | MEDIUM | LOW |
|------|----------|------|--------|-----|
| infrastructure/ | 2 | 0 | 2 | 3 |
| repositories/ | 0 | 0 | 3 | 2 |
| services/ | 1 | 4 | 0 | 0 |
| system/ | 0 | 3 | 3 | 1 |
| app/ | 0 | 0 | 0 | 1 |
| ui/ | 1 | 4 | 11 | 1 |
| domain/ | 0 | 0 | 0 | 1 |

### 优先修复建议

1. **立即修复**: C-01 (eval 安全漏洞), C-02/C-03 (数据库连接竞态)
2. **本迭代修复**: 所有 HIGH 级别 Bug
3. **下一迭代**: MEDIUM 级别 Bug
4. **持续改进**: LOW 级别代码质量问题
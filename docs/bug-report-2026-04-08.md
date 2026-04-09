# Harmony 代码审查 Bug 报告

**日期:** 2026-04-08  
**分支:** feature/plugin-system  
**审查范围:** 全代码库（domain / repositories / services / infrastructure / ui / system / plugins）

---

## 概览

| 严重程度 | 数量 |
|---------|------|
| Critical | 2 |
| High | 13 |
| Medium | 15 |
| Low | 2 |
| **合计** | **32** |

---

## Critical（致命）

### BUG-01: `Application._dispatch_to_ui` 缺少 `self` 参数

**文件:** `app/application.py`  
**行号:** 108  
**影响:** 应用启动时 MPRIS 初始化将直接崩溃

**问题代码:**
```python
def _dispatch_to_ui(fn, *args, **kwargs):
    QTimer.singleShot(0, lambda: fn(*args, **kwargs))
```

`_dispatch_to_ui` 是实例方法，但缺少 `self` 参数。当被 `self._dispatch_to_ui(...)` 调用时，`fn` 会绑定为 `self`，导致 `TypeError`。

**修复建议:**
```python
def _dispatch_to_ui(self, fn, *args, **kwargs):
    QTimer.singleShot(0, lambda: fn(*args, **kwargs))
```

---

### BUG-02: `SingleFlight.do()` 存在竞态条件

**文件:** `services/_singleflight.py`  
**行号:** 36-53  
**影响:** 跟随者线程可能读到错误结果或永久阻塞

**问题代码:**
```python
# Leader 完成后:
finally:
    with self._lock:
        self._calls.pop(key, None)   # 1) 先从字典移除
    state.event.set()                 # 2) 再设置事件
```

在步骤 1 和步骤 2 之间，新线程可能对同一 key 创建新的 `_CallState`，成为新的 leader。原 follower 被唤醒后可能读到错误 state 的数据。

**修复建议:**
```python
finally:
    state.event.set()                 # 先设置事件
    with self._lock:
        self._calls.pop(key, None)    # 再从字典移除
```

---

## High（高危）

### BUG-03: AudioEngine `play()` 竞态条件 — 锁外使用索引

**文件:** `infrastructure/audio/audio_engine.py`  
**行号:** 616-657  
**影响:** 播放错误曲目或 IndexError 崩溃

**问题代码:**
```python
with self._playlist_lock:
    current_index = self._current_index
    local_path = item.local_path
    # 锁释放

# 此处 playlist 可能已被其他线程修改
current_source = self._backend.get_source_path()
if current_source != local_path:
    self._load_track(current_index)  # current_index 可能已失效
```

`current_index` 和 `local_path` 在锁内获取，但在锁外使用。期间 playlist 可能被 `remove_track()` 等方法修改。

**修复建议:** 在锁外使用前重新验证索引有效性，或将 `_load_track` 逻辑移入锁内。

---

### BUG-04: AudioEngine `play_next()` 同样的竞态条件

**文件:** `infrastructure/audio/audio_engine.py`  
**行号:** 799-845  
**影响:** 同 BUG-03

`item` 和 `current_index` 在锁内捕获，但在锁外用于 `_load_track()` 和信号发射。

---

### BUG-05: AudioEngine `play_after_download()` 长操作持锁 + 竞态条件

**文件:** `infrastructure/audio/audio_engine.py`  
**行号:** 740-797  
**影响:** 锁内调用 `MetadataService.extract_metadata()` 阻塞其他线程；`item_copy` 锁外使用可能过期

**问题代码:**
```python
with self._playlist_lock:
    if item.needs_metadata and local_path:
        metadata = MetadataService.extract_metadata(local_path)  # 长操作持锁
    item_copy = item

if is_current:
    self.current_track_changed.emit(item_copy.to_dict())  # 锁外使用
```

**修复建议:** 将元数据提取移到锁外执行；在锁内深拷贝 item 数据。

---

### BUG-06: 睡眠定时器淡出逻辑 — 音量为 0 时失效

**文件:** `services/playback/sleep_timer_service.py`  
**行号:** 179  
**影响:** 当原始音量为 0 时，淡出逻辑被跳过，定时器行为异常

**问题代码:**
```python
if self._original_volume:  # 当 _original_volume == 0 时为 False
    step_size = max(1, self._original_volume // 20)
    new_volume = max(0, current - step_size)
    self._playback_service.set_volume(new_volume)
```

**修复建议:**
```python
if self._original_volume is not None:
```

---

### BUG-07: MetadataService `path` 变量可能未定义

**文件:** `services/metadata/metadata_service.py`  
**行号:** 78-91  
**影响:** 当 `Path(file_path)` 构造失败时，后续 `path.stem` 引用触发 `NameError`

**问题代码:**
```python
try:
    path = Path(file_path)  # 在 try 内定义
    # ...
except Exception as e:
    logger.error(...)

if not metadata["title"]:
    metadata["title"] = path.stem  # 若异常发生在 path 赋值前，此处崩溃
```

**修复建议:** 将 `path = Path(file_path)` 移到 `try` 块之前。

---

### BUG-08: SecretStore `decrypt()` 缺少异常处理

**文件:** `infrastructure/security/secret_store.py`  
**行号:** 52-66  
**影响:** 当加密数据损坏时，base64 解码或 AES 验证失败导致应用崩溃

**问题代码:**
```python
payload = base64.urlsafe_b64decode(...)
cipher = AES.new(self._get_or_create_key(), AES.MODE_GCM, nonce=nonce)
plaintext = cipher.decrypt_and_verify(ciphertext, tag)  # 可抛出 ValueError
```

**修复建议:** 用 `try-except` 包裹，捕获 `ValueError`/`IndexError`/`UnicodeDecodeError`，失败时返回空字符串并记录日志。

---

### BUG-09: `ThemeManager.instance()` 在插件 SDK 中未传 config

**文件:** `system/plugins/plugin_sdk_ui.py`  
**行号:** 8, 13, 18, 23, 28  
**影响:** 如果 ThemeManager 尚未初始化，调用将抛出 `ValueError: ConfigManager required for first initialization`

**问题代码:**
```python
class PluginThemeBridgeImpl:
    def register_widget(self, widget) -> None:
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(widget)  # 未传 config
```

**修复建议:** 在 Bootstrap 中确保 ThemeManager 在插件加载前完成初始化；或在调用处添加 `try-except`。

---

### BUG-10: `PluginStateStore` 无线程同步

**文件:** `system/plugins/state_store.py`  
**行号:** 13-45  
**影响:** 多线程并发读写 JSON 状态文件导致数据丢失或损坏

**问题代码:**
```python
def set_enabled(self, plugin_id, enabled, source, version, load_error=None):
    payload = self._read()       # 线程 A 读取
    payload[plugin_id] = {...}
    self._write(payload)         # 线程 B 可能在读写之间写入
```

**修复建议:** 添加 `threading.Lock` 保护 `_read()` + `_write()` 操作。

---

### BUG-11: 文件整理服务 — 回滚失败时静默吞异常

**文件:** `services/library/file_organization_service.py`  
**行号:** 165-175  
**影响:** 数据库更新失败后文件回滚也失败时，用户无法得知文件已处于不一致状态

**问题代码:**
```python
if not self._track_repo.update(track):
    try:
        shutil.move(str(final_audio_path), str(old_audio_path))
        for old_path, new_path in moved_lyrics:
            shutil.move(str(new_path), str(old_path))
    except Exception:
        pass  # 静默吞掉回滚异常
```

**修复建议:** 记录回滚失败日志，并在错误信息中注明"文件回滚失败"。

---

### BUG-12: `CloudRepository.hard_delete_account()` rowcount 判断错误

**文件:** `repositories/cloud_repository.py`  
**行号:** 301-314  
**影响:** 删除关联文件成功但账户本身不存在时，返回 False 但文件已被删除

**问题代码:**
```python
cursor.execute("DELETE FROM cloud_files WHERE account_id = ?", (account_id,))
cursor.execute("DELETE FROM cloud_accounts WHERE id = ?", (account_id,))
conn.commit()
return cursor.rowcount > 0  # 仅检查最后一条 DELETE 的 rowcount
```

**修复建议:** 分别保存两个 DELETE 的 `rowcount`，返回值基于 `cloud_accounts` 的删除结果。

---

### BUG-13: Kugou 歌词插件 — 直接字典访问无保护

**文件:** `plugins/builtin/kugou/lib/lyrics_source.py`  
**行号:** 32  
**影响:** API 响应缺少 `id` 字段时抛出 `KeyError` 崩溃

**问题代码:**
```python
song_id=str(item["id"]),  # 无 .get() 保护
```

**修复建议:** 改为 `str(item.get("id", ""))`，并用 `try-except` 包裹整个 `search()` 方法。

---

### BUG-14: NetEase 歌词插件 — `song["id"]` 直接访问 + artists 列表越界

**文件:** `plugins/builtin/netease_lyrics/lib/lyrics_source.py`  
**行号:** 48, 50  
**影响:** API 响应异常时 `KeyError` 或 `IndexError` 崩溃

**问题代码:**
```python
song_id=str(song["id"]),  # KeyError 风险
artist=song["artists"][0]["name"] if song.get("artists") else "",  # 空列表时 IndexError
```

**修复建议:**
```python
song_id=str(song.get("id", "")),
artist=(song["artists"][0].get("name", "")
        if song.get("artists") and len(song["artists"]) > 0
        else ""),
```

---

### BUG-15: NetEase 封面插件 — 同样的 artists 列表越界问题

**文件:** `plugins/builtin/netease_cover/lib/cover_source.py`  
**行号:** 81  
**影响:** 同 BUG-14

---

## Medium（中等）

### BUG-16: Qt Backend — QMediaPlayer/QAudioOutput 无 parent 导致内存泄漏

**文件:** `infrastructure/audio/qt_backend.py`  
**行号:** 20-21  
**影响:** Qt 对象不会随 backend 销毁自动回收

**修复建议:** 构造时传入 `self` 作为 parent：
```python
self._player = QMediaPlayer(self)
self._audio_output = QAudioOutput(self)
```

---

### BUG-17: ImageCache `cleanup()` 迭代器失效风险

**文件:** `infrastructure/cache/image_cache.py`  
**行号:** 77-108  
**影响:** 并发修改目录时可能抛出 `RuntimeError`

**修复建议:** 先 `list(cls.CACHE_DIR.iterdir())` 创建快照再遍历。

---

### BUG-18: HttpClient 共享实例从不清理

**文件:** `infrastructure/network/http_client.py`  
**行号:** 73-102  
**影响:** 连接池泄漏，应用退出时未关闭 HTTP 会话

**修复建议:** 注册 `atexit` 回调清理 `_shared_clients`。

---

### BUG-19: SqliteManager 线程本地连接未自动关闭

**文件:** `infrastructure/database/sqlite_manager.py`  
**行号:** 42-56  
**影响:** 未调用 `close()` 的线程退出后数据库连接泄漏，可能造成数据库锁

---

### BUG-20: MPRIS 事件处理器竞态条件

**文件:** `system/mpris.py`  
**行号:** 456-481  
**影响:** `self.service` 在信号处理线程和 GLib 主循环线程间无同步，可能空指针解引用

**问题代码:**
```python
def on_track_changed(self, *args):
    if self.service:  # 竞态：stop() 可能同时将 service 置 None
        self.service.emit_player_properties(...)

def stop(self):
    self.service = None  # 可能在信号处理期间执行
```

**修复建议:** 添加 `threading.Lock` 保护 `self.service` 的访问。

---

### BUG-21: i18n 模块全局状态无线程同步

**文件:** `system/i18n.py`  
**行号:** 11-12, 54-58  
**影响:** 并发调用 `set_language()` 和 `t()` 时竞态条件

**修复建议:** 添加 `threading.Lock` 保护 `_current_language` 和 `_translations`。

---

### BUG-22: Hotkeys `cleanup()` 未被调用

**文件:** `system/hotkeys.py`  
**行号:** 220-225  
**影响:** Windows 媒体键监听器线程在应用退出后继续运行

**修复建议:** 在 `Application.quit()` 中显式调用 `hotkeys.cleanup()`。

---

### BUG-23: `ConfigManager._get_secret()` 未检查 `_secret_store` 为 None

**文件:** `system/config.py`  
**行号:** 141-143  
**影响:** 若 `SecretStore.default()` 失败，后续 decrypt 调用触发 `AttributeError`

**修复建议:**
```python
def _get_secret(self, key, default=""):
    if self._secret_store is None:
        return self.get(key, default)
    return self._secret_store.decrypt(self.get(key, default))
```

---

### BUG-24: `Genre.id` 空名称返回空字符串

**文件:** `domain/genre.py`  
**行号:** 31  
**影响:** 多个空名称 Genre 具有相同 ID，破坏 hash/equality 语义

**问题代码:**
```python
@property
def id(self) -> str:
    return self.name.lower()  # name="" 时返回 ""
```

---

### BUG-25: `PlaylistItem.from_dict()` 缺少类型转换

**文件:** `domain/playlist_item.py`  
**行号:** 171-185  
**影响:** 从 JSON 反序列化时，`track_id`（应为 `int`）和 `duration`（应为 `float`）可能保持字符串类型，导致下游类型错误

**修复建议:**
```python
track_id=int(data["id"]) if data.get("id") is not None else None,
duration=float(data.get("duration", 0.0)),
```

---

### BUG-26: LRCLIB 插件 — `response.json()` 返回值类型未校验

**文件:** `plugins/builtin/lrclib/lib/lrclib_source.py`  
**行号:** 30-41  
**影响:** 若 API 返回 dict 而非 list，`payload[:limit]` 将抛出 `TypeError`

**修复建议:** 添加 `isinstance(payload, list)` 检查。

---

### BUG-27: QQMusic 客户端 — socket 未在 finally 中关闭

**文件:** `plugins/builtin/qqmusic/lib/client.py`  
**行号:** 32-38  
**影响:** 若 `sock.close()` 之前发生异常，socket 泄漏

**问题代码:**
```python
try:
    sock = socket.create_connection(("u.y.qq.com", 443), timeout=0.5)
    sock.close()
    self._legacy_network_reachable = True
except OSError:
    self._legacy_network_reachable = False
```

**修复建议:** 使用 `try...finally` 或 `with` 上下文管理器。

---

### BUG-28: NowPlayingWindow 对话框内存泄漏

**文件:** `ui/windows/now_playing_window.py`  
**行号:** 621-686  
**影响:** `_show_playlist_dialog()` 创建 QDialog 但 `exec()` 后未调用 `deleteLater()`

**修复建议:** `dialog.exec()` 后添加 `dialog.deleteLater()`。

---

### BUG-29: MiniPlayer 使用 daemon 线程加载封面

**文件:** `ui/windows/mini_player.py`  
**行号:** 553-611  
**影响:** daemon 线程在应用退出时被强制终止，可能导致资源未释放

**修复建议:** 改用 QThread 并管理生命周期。

---

### BUG-30: `PlaylistRepository.delete()` — rowcount 仅反映最后一条 DELETE

**文件:** `repositories/playlist_repository.py`  
**行号:** 79-88  
**影响:** 类似 BUG-12，先删除 playlist_items 再删除 playlists，rowcount 仅反映 playlists 表。逻辑上正确（playlist 不存在确实应返回 False），但缺少事务保护——若第二条 DELETE 失败，playlist_items 已被删除。

**修复建议:** 添加 `try-except` + `conn.rollback()`。

---

## Low（低危）

### BUG-31: `exec_()` 已弃用

**文件:** `ui/windows/components/lyrics_panel.py`  
**行号:** 139  
**影响:** PySide6 中 `exec_()` 已弃用，应使用 `exec()`

---

### BUG-32: `Bootstrap.instance()` 在循环内重复调用

**文件:** `ui/windows/components/online_music_handler.py`  
**行号:** 213-229, 269-285, 323-339  
**影响:** 性能浪费，每次循环迭代都进行 singleton 查找

**修复建议:** 将 `Bootstrap.instance()` 提取到循环外。

---

## 按模块分类汇总

| 模块 | Critical | High | Medium | Low |
|------|----------|------|--------|-----|
| app/ | 1 | 0 | 0 | 0 |
| domain/ | 0 | 0 | 2 | 0 |
| repositories/ | 0 | 1 | 1 | 0 |
| services/ | 1 | 2 | 0 | 0 |
| infrastructure/ | 0 | 4 | 4 | 0 |
| system/ | 0 | 2 | 4 | 0 |
| ui/ | 0 | 0 | 2 | 2 |
| plugins/ | 0 | 4 | 2 | 0 |
| **合计** | **2** | **13** | **15** | **2** |

---

## 建议修复优先级

1. **立即修复:** BUG-01（应用无法正常启动 MPRIS）、BUG-02（SingleFlight 死锁/错误结果）
2. **高优先级:** BUG-03 ~ BUG-05（AudioEngine 竞态）、BUG-06 ~ BUG-08（服务层逻辑错误）、BUG-13 ~ BUG-15（插件崩溃）
3. **常规修复:** 所有 Medium 级别 Bug
4. **可选优化:** Low 级别 Bug
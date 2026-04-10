# Optimization Report Wave C Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the system-layer report items covering service concurrency, configuration, themes, plugins, event delivery, MPRIS integration, logging, and application safety.

**Architecture:** This wave centers on synchronization and lifecycle fixes inside `system/` and service singletons. Caching and lock changes remain internal to managers and helpers so higher layers keep the same public APIs while gaining stronger behavior guarantees.

**Tech Stack:** Python 3.11+, PySide6, SQLite-backed settings, pytest, uv, git

---

## File Map

- Modify: `services/cloud/baidu_service.py`
- Modify: `services/cloud/download_service.py`
- Modify: `services/download/download_manager.py`
- Modify: `services/lyrics/lyrics_service.py`
- Modify: `system/config.py`
- Modify: `system/theme.py`
- Modify: `system/event_bus.py`
- Modify: `system/hotkeys.py`
- Modify: `system/mpris.py`
- Modify: `system/i18n.py`
- Modify: `system/plugins/manager.py`
- Modify: `system/plugins/state_store.py`
- Modify: `system/plugins/registry.py`
- Modify: `system/plugins/loader.py`
- Modify: `system/plugins/host_services.py`
- Modify: `app/application.py`
- Test: `tests/test_system/test_event_bus.py`
- Test: `tests/test_system/test_hotkeys.py`
- Test: `tests/test_system/test_mpris.py`
- Test: `tests/test_system/test_plugin_manager.py`
- Test: `tests/test_system/test_plugin_registry.py`
- Test: `tests/test_system/test_plugin_state_store_locking.py`
- Test: `tests/test_system/test_theme.py`
- Test: `tests/test_system/test_config_security.py`
- Test: `tests/test_system/test_i18n_locking.py`
- Test: `tests/test_services/test_download_manager_cleanup.py`
- Test: `tests/test_services/test_lyrics_service_perf_paths.py`

### Task 1: Service Rate Limiting And Singleton Synchronization

**Files:**
- Modify: `services/cloud/baidu_service.py`
- Modify: `services/cloud/download_service.py`
- Modify: `services/download/download_manager.py`
- Modify: `services/lyrics/lyrics_service.py`
- Test: `tests/test_services/test_download_manager_cleanup.py`
- Test: `tests/test_services/test_lyrics_service_perf_paths.py`

- [ ] **Step 1: Add coverage for report items 2.1 and 2.2**

```python
def test_baidu_service_rate_limit_is_instance_scoped(...): ...
def test_singleton_get_instance_is_lock_protected(...): ...
```

- [ ] **Step 2: Run the focused service tests**

Run:
- `uv run pytest tests/test_services/test_download_manager_cleanup.py -v`
- `uv run pytest tests/test_services/test_lyrics_service_perf_paths.py -v`

Expected: FAIL where singleton initialization or shared limiter state is unsafe.

- [ ] **Step 3: Implement the service synchronization changes**

```python
self._last_request_time = 0.0
self._rate_limit_lock = threading.Lock()

if cls._instance is None:
    with cls._instance_lock:
        if cls._instance is None:
            cls._instance = cls()
```

- [ ] **Step 4: Re-run the focused service tests**

Run:
- `uv run pytest tests/test_services/test_download_manager_cleanup.py -v`
- `uv run pytest tests/test_services/test_lyrics_service_perf_paths.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add services/cloud/baidu_service.py
git commit -m "优化 2.1 百度服务限流状态"

git add services/cloud/download_service.py services/download/download_manager.py services/lyrics/lyrics_service.py tests/test_services/test_download_manager_cleanup.py tests/test_services/test_lyrics_service_perf_paths.py
git commit -m "优化 2.2 单例线程安全"
```

### Task 2: Config Manager Locking, Caching, And Validation

**Files:**
- Modify: `system/config.py`
- Test: `tests/test_system/test_config_security.py`

- [ ] **Step 1: Add coverage for report items 2.3, 3.11, 6.9, 9.7, and 9.8**

```python
def test_config_cache_load_releases_lock_before_repository_access(...): ...
def test_get_audio_effects_reuses_normalized_cache(...): ...
def test_eq_band_count_constant_is_shared(...): ...
def test_volume_and_effect_values_are_clamped(...): ...
```

- [ ] **Step 2: Run the focused config tests**

Run: `uv run pytest tests/test_system/test_config_security.py -v`
Expected: FAIL where caching, invalidation, or clamping behavior is missing.

- [ ] **Step 3: Implement the config changes**

```python
EQ_BANDS_COUNT = 10

if cached is not None and not self._cache_expired(key):
    return cached

volume = max(0, min(100, int(volume)))
```

- [ ] **Step 4: Re-run the focused config tests**

Run: `uv run pytest tests/test_system/test_config_security.py -v`
Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add system/config.py tests/test_system/test_config_security.py
git commit -m "优化 2.3 配置缓存锁竞争"

git add system/config.py tests/test_system/test_config_security.py
git commit -m "优化 3.11 音效配置归一化缓存"

git add system/config.py tests/test_system/test_config_security.py
git commit -m "优化 6.9 EQ频段常量"

git add system/config.py tests/test_system/test_config_security.py
git commit -m "优化 9.7 配置缓存失效"

git add system/config.py tests/test_system/test_config_security.py
git commit -m "优化 9.8 配置范围校验"
```

### Task 3: Theme Manager Locking And Cache Stability

**Files:**
- Modify: `system/theme.py`
- Test: `tests/test_system/test_theme.py`

- [ ] **Step 1: Add coverage for report items 2.4, 4.8, and 9.6**

```python
def test_widget_registration_is_lock_protected(...): ...
def test_qss_cache_has_bounded_size(...): ...
def test_template_cache_key_uses_stable_digest(...): ...
```

- [ ] **Step 2: Run the theme tests**

Run: `uv run pytest tests/test_system/test_theme.py -v`
Expected: FAIL where lock-free mutation or unbounded cache behavior remains.

- [ ] **Step 3: Implement the theme changes**

```python
self._widgets_lock = threading.Lock()
@lru_cache(maxsize=128)
def _compile_qss(...): ...
digest = hashlib.sha256(template.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Re-run the theme tests**

Run: `uv run pytest tests/test_system/test_theme.py -v`
Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add system/theme.py tests/test_system/test_theme.py
git commit -m "优化 2.4 主题组件集合并发"

git add system/theme.py tests/test_system/test_theme.py
git commit -m "优化 4.8 主题QSS缓存上限"

git add system/theme.py tests/test_system/test_theme.py
git commit -m "优化 9.6 主题缓存稳定哈希"
```

### Task 4: Plugin Manager, Registry, Loader, And State Store Hardening

**Files:**
- Modify: `system/plugins/manager.py`
- Modify: `system/plugins/state_store.py`
- Modify: `system/plugins/registry.py`
- Modify: `system/plugins/loader.py`
- Modify: `system/plugins/host_services.py`
- Test: `tests/test_system/test_plugin_manager.py`
- Test: `tests/test_system/test_plugin_registry.py`
- Test: `tests/test_system/test_plugin_state_store_locking.py`

- [ ] **Step 1: Add coverage for report items 2.5, 2.9, 3.14, 4.7, and part of 5.1**

```python
def test_loaded_plugins_access_uses_lock(...): ...
def test_state_store_retries_atomic_replace(...): ...
def test_unregister_plugin_filters_lists_in_place(...): ...
def test_loader_purges_package_modules_on_unload(...): ...
def test_host_services_logs_json_parse_failure(...): ...
```

- [ ] **Step 2: Run the plugin tests**

Run:
- `uv run pytest tests/test_system/test_plugin_manager.py -v`
- `uv run pytest tests/test_system/test_plugin_registry.py -v`
- `uv run pytest tests/test_system/test_plugin_state_store_locking.py -v`

Expected: FAIL where lock, retry, purge, or logging behavior is absent.

- [ ] **Step 3: Implement the plugin changes**

```python
with self._loaded_plugins_lock:
    ...

for attempt in range(3):
    try:
        os.replace(tmp_path, target_path)
        break
    except OSError:
        time.sleep(0.1)

lst[:] = [entry for entry in lst if entry is not plugin_id]
```

- [ ] **Step 4: Re-run the plugin tests**

Run:
- `uv run pytest tests/test_system/test_plugin_manager.py -v`
- `uv run pytest tests/test_system/test_plugin_registry.py -v`
- `uv run pytest tests/test_system/test_plugin_state_store_locking.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add system/plugins/manager.py tests/test_system/test_plugin_manager.py
git commit -m "优化 2.5 插件加载集合并发"

git add system/plugins/state_store.py tests/test_system/test_plugin_state_store_locking.py
git commit -m "优化 2.9 插件状态存储写入竞态"

git add system/plugins/registry.py tests/test_system/test_plugin_registry.py
git commit -m "优化 3.14 插件注册表过滤"

git add system/plugins/loader.py tests/test_system/test_plugin_manager.py
git commit -m "优化 4.7 插件模块清理"

git add system/plugins/host_services.py
git commit -m "优化 5.1 静默异常日志"
```

### Task 5: Event Bus, MPRIS, Hotkeys, And Application Safety

**Files:**
- Modify: `system/event_bus.py`
- Modify: `system/mpris.py`
- Modify: `system/hotkeys.py`
- Modify: `app/application.py`
- Test: `tests/test_system/test_event_bus.py`
- Test: `tests/test_system/test_mpris.py`
- Test: `tests/test_system/test_hotkeys.py`

- [ ] **Step 1: Add coverage for report items 2.8, 3.10, 4.5, 4.6, 5.3, and 5.5**

```python
def test_event_bus_emits_via_thread_safe_queued_dispatch(...): ...
def test_player_properties_cache_invalidates_on_state_change(...): ...
def test_hotkeys_cleanup_deletes_shortcuts(...): ...
def test_mpris_disconnects_event_bus_on_cleanup(...): ...
def test_application_run_logs_startup_failures_without_crashing(...): ...
def test_mpris_ui_dispatch_handles_callback_errors(...): ...
```

- [ ] **Step 2: Run the focused system tests**

Run:
- `uv run pytest tests/test_system/test_event_bus.py -v`
- `uv run pytest tests/test_system/test_mpris.py -v`
- `uv run pytest tests/test_system/test_hotkeys.py -v`

Expected: FAIL where thread-safe dispatch or cleanup semantics are missing.

- [ ] **Step 3: Implement the system changes**

```python
QMetaObject.invokeMethod(self, "_emit_on_main_thread", Qt.QueuedConnection, ...)

if self._player_properties_cache is None:
    self._player_properties_cache = build_properties()

def cleanup(self):
    for shortcut in self._shortcuts:
        shortcut.deleteLater()
    self._shortcuts.clear()
```

- [ ] **Step 4: Re-run the focused system tests**

Run:
- `uv run pytest tests/test_system/test_event_bus.py -v`
- `uv run pytest tests/test_system/test_mpris.py -v`
- `uv run pytest tests/test_system/test_hotkeys.py -v`

Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add system/event_bus.py tests/test_system/test_event_bus.py
git commit -m "优化 2.8 事件总线线程安全"

git add system/mpris.py tests/test_system/test_mpris.py
git commit -m "优化 3.10 MPRIS属性缓存"

git add system/hotkeys.py tests/test_system/test_hotkeys.py
git commit -m "优化 4.5 全局快捷键清理"

git add system/mpris.py tests/test_system/test_mpris.py
git commit -m "优化 4.6 MPRIS事件连接清理"

git add app/application.py
git commit -m "优化 5.3 应用启动异常保护"

git add system/mpris.py tests/test_system/test_mpris.py
git commit -m "优化 5.5 MPRIS界面分发保护"
```

### Task 6: Logging And Language Fallback Visibility

**Files:**
- Modify: `services/cloud/baidu_service.py`
- Modify: `system/plugins/manager.py`
- Modify: `system/i18n.py`
- Test: `tests/test_system/test_i18n_locking.py`

- [ ] **Step 1: Add focused coverage for the remaining report items 5.1 and 10.6**

```python
def test_invalid_language_fallback_logs_warning(...): ...
def test_plugin_unload_errors_are_logged(...): ...
```

- [ ] **Step 2: Run the focused tests**

Run: `uv run pytest tests/test_system/test_i18n_locking.py -v`
Expected: FAIL before invalid-language logging exists.

- [ ] **Step 3: Implement the logging changes**

```python
except Exception:
    logger.warning("Failed to restore language %s; falling back to en", language, exc_info=True)
```

- [ ] **Step 4: Re-run the focused tests**

Run: `uv run pytest tests/test_system/test_i18n_locking.py -v`
Expected: PASS

- [ ] **Step 5: Commit each report item separately**

```bash
git add services/cloud/baidu_service.py system/plugins/manager.py system/plugins/host_services.py
git commit -m "优化 5.1 静默异常日志"

git add system/i18n.py tests/test_system/test_i18n_locking.py
git commit -m "优化 10.6 语言回退日志"
```

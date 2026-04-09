# QQMusic Externalization Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining host-side QQMusic-specific online code so QQ Music can ship and run only as an external plugin.

**Architecture:** The host keeps only generic plugin runtime, registry, settings, media, and UI bridge capabilities. All QQ Music-specific UI, runtime helpers, and online behavior move behind the plugin package, and the host must still boot and function when `plugins/builtin/qqmusic` is absent. External plugin precedence must be explicit so an installed external `qqmusic` package can replace any bundled copy during transition.

**Tech Stack:** Python 3.11+, PySide6, pytest, Harmony plugin runtime, `harmony-plugin-api`

---

## File Map

**Remove or stop referencing**
- `system/plugins/qqmusic_runtime_helpers.py` — legacy host helper that imports QQMusic plugin internals directly
- `ui/views/legacy_online_music_view.py` — QQMusic compatibility shim
- `ui/views/online_detail_view.py` — QQMusic compatibility shim
- `ui/views/online_grid_view.py` — QQMusic compatibility shim
- `ui/views/online_tracks_list_view.py` — QQMusic compatibility shim

**Modify**
- `system/plugins/manager.py` — resolve duplicate plugin ids and define external-vs-builtin precedence
- `system/plugins/installer.py` — strengthen plugin import audit to reject dynamic host bridge imports
- `system/plugins/loader.py` — align runtime import guard with the stricter audit boundary if needed
- `ui/widgets/context_menus.py` — remove direct dependency on `plugins.builtin.qqmusic`
- `ui/dialogs/plugin_management_tab.py` — surface install safety warning and, if in scope, uninstall entry points for external plugins only
- `README.md` — replace built-in QQ settings assumptions with plugin-based installation and usage

**Test**
- `tests/test_app/test_qqmusic_host_cleanup.py`
- `tests/test_system/test_plugin_import_guard.py`
- `tests/test_system/test_plugin_manager.py`
- `tests/test_system/test_plugin_packaging.py`
- `tests/test_ui/test_plugin_settings_tab.py`

### Task 1: Tighten The Plugin Boundary

**Files:**
- Modify: `system/plugins/installer.py`
- Modify: `system/plugins/loader.py`
- Test: `tests/test_system/test_plugin_import_guard.py`

- [ ] **Step 1: Add failing tests for dynamic host bridge imports**

Add a test plugin fixture that uses:

```python
import importlib

class BadRuntimePlugin:
    plugin_id = "bad-runtime"

    def register(self, context):
        importlib.import_module("system.plugins.plugin_sdk_runtime")

    def unregister(self, context):
        return None
```

and assert install-time audit or runtime load rejects it. Add a second assertion covering the real QQ plugin source so the test fails until `plugins/builtin/qqmusic/lib/runtime_bridge.py` stops importing `system.plugins.*`.

- [ ] **Step 2: Run the focused guard tests**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py -v`

Expected: FAIL on the new dynamic-import test and/or the QQ plugin boundary assertion.

- [ ] **Step 3: Harden import auditing**

Extend `audit_plugin_imports()` in `system/plugins/installer.py` to reject dynamic imports targeting forbidden roots such as:

```python
importlib.import_module("system.plugins.plugin_sdk_runtime")
__import__("ui.dialogs.message_dialog")
```

The simplest acceptable approach is AST checks for string literal arguments on `importlib.import_module(...)` and `__import__(...)`.

- [ ] **Step 4: Align runtime loading if audit and loader differ**

If needed, extend `PluginLoader._guard_imports()` so plugin code cannot reach `system`, `ui`, `services`, or similar forbidden roots through absolute imports even when they are executed indirectly during plugin module import.

- [ ] **Step 5: Re-run guard tests**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add system/plugins/installer.py system/plugins/loader.py tests/test_system/test_plugin_import_guard.py
git commit -m "收紧插件宿主导入边界"
```

### Task 2: Move QQ Plugin Off Host Bridge Internals

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/runtime_bridge.py`
- Modify: `plugins/builtin/qqmusic/lib/provider.py`
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `plugins/builtin/qqmusic/lib/dialog_title_bar.py`
- Test: `tests/test_plugins/test_qqmusic_plugin.py`
- Test: `tests/test_system/test_plugin_import_guard.py`

- [ ] **Step 1: Write failing tests for SDK-only access**

Add assertions that QQ plugin runtime and UI code obtain host services from `context.ui`, `context.services`, `context.http`, `context.events`, and plugin-local helpers only. The tests should fail if `runtime_bridge.py` still references `system.plugins.plugin_sdk_runtime` or `system.plugins.plugin_sdk_ui`.

- [ ] **Step 2: Run QQ plugin boundary tests**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py tests/test_system/test_plugin_import_guard.py -v`

Expected: FAIL until the runtime bridge no longer imports host internals by module path.

- [ ] **Step 3: Replace the dynamic bridge**

Refactor `plugins/builtin/qqmusic/lib/runtime_bridge.py` so it is a thin wrapper over plugin context objects instead of `importlib.import_module("system.plugins...")`. The plugin should use the typed bridges already exposed through `PluginContext` where possible, and any missing host capability should be added to `harmony_plugin_api.context` plus `system/plugins/host_services.py` rather than imported from `system.plugins.*` inside the plugin.

- [ ] **Step 4: Update call sites**

Adjust provider, login dialog, settings tab, title bar, and any other plugin UI modules to pass explicit `context` or bridge objects down to the places that currently depend on the implicit runtime bridge.

- [ ] **Step 5: Re-run QQ plugin tests**

Run: `uv run pytest tests/test_plugins/test_qqmusic_plugin.py tests/test_system/test_plugin_import_guard.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add plugins/builtin/qqmusic/lib/runtime_bridge.py plugins/builtin/qqmusic/lib/provider.py plugins/builtin/qqmusic/lib/settings_tab.py plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/lib/dialog_title_bar.py tests/test_plugins/test_qqmusic_plugin.py tests/test_system/test_plugin_import_guard.py
git commit -m "改造QQ插件宿主桥接方式"
```

### Task 3: Remove Host-Side QQ Compatibility Shims

**Files:**
- Delete: `system/plugins/qqmusic_runtime_helpers.py`
- Delete: `ui/views/legacy_online_music_view.py`
- Delete: `ui/views/online_detail_view.py`
- Delete: `ui/views/online_grid_view.py`
- Delete: `ui/views/online_tracks_list_view.py`
- Modify: `ui/widgets/context_menus.py`
- Test: `tests/test_app/test_qqmusic_host_cleanup.py`

- [ ] **Step 1: Update the cleanup tests to require full removal**

Replace assertions that currently expect compatibility shims to exist with assertions that:

```python
assert not Path("ui/views/legacy_online_music_view.py").exists()
assert not Path("ui/views/online_detail_view.py").exists()
assert not Path("ui/views/online_grid_view.py").exists()
assert not Path("ui/views/online_tracks_list_view.py").exists()
assert not Path("system/plugins/qqmusic_runtime_helpers.py").exists()
```

Also add assertions that `ui/widgets/context_menus.py` no longer imports `plugins.builtin.qqmusic`.

- [ ] **Step 2: Run cleanup tests**

Run: `uv run pytest tests/test_app/test_qqmusic_host_cleanup.py -v`

Expected: FAIL because the files and imports still exist.

- [ ] **Step 3: Remove the host imports**

Delete the shim/helper files and refactor `ui/widgets/context_menus.py` to provide only host-owned local playlist/library menus. Any QQ-specific online context menu must be instantiated inside the plugin page instead of being imported from host code.

- [ ] **Step 4: Re-run cleanup tests**

Run: `uv run pytest tests/test_app/test_qqmusic_host_cleanup.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/widgets/context_menus.py tests/test_app/test_qqmusic_host_cleanup.py
git commit -m "移除宿主QQ兼容遗留代码"
```

### Task 4: Make External QQ Plugin Override Bundled Copies

**Files:**
- Modify: `system/plugins/manager.py`
- Test: `tests/test_system/test_plugin_manager.py`

- [ ] **Step 1: Add a failing duplicate-id precedence test**

Create a test with both:

```text
builtin/qqmusic/plugin.json version 1.0.0
external/qqmusic/plugin.json version 1.1.0
```

and assert the manager loads exactly one `qqmusic` plugin and that the loaded source is `external`.

- [ ] **Step 2: Run plugin manager tests**

Run: `uv run pytest tests/test_system/test_plugin_manager.py -v`

Expected: FAIL because builtin roots are currently loaded first and duplicate ids are skipped as already loaded.

- [ ] **Step 3: Implement precedence**

Change discovery or load planning so duplicate plugin ids are collapsed before loading, with `external` overriding `builtin`. `list_plugins()` should also avoid showing two rows for the same plugin id in that case.

- [ ] **Step 4: Re-run plugin manager tests**

Run: `uv run pytest tests/test_system/test_plugin_manager.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add system/plugins/manager.py tests/test_system/test_plugin_manager.py
git commit -m "支持外部插件覆盖内置插件"
```

### Task 5: Verify External-Only QQ Plugin Boot

**Files:**
- Modify: `tests/test_system/test_plugin_packaging.py`
- Modify: `tests/test_system/test_plugin_manager.py`

- [ ] **Step 1: Add a failing end-to-end external-only test**

Write a test that:

1. builds `plugins/builtin/qqmusic` into a zip
2. installs it into a temp external plugin root
3. does not provide any builtin `qqmusic` root
4. loads plugins through `PluginManager`
5. asserts the external plugin registers expected capabilities

This test should fail if the plugin still depends on removed built-in-only files or host-side QQ shims.

- [ ] **Step 2: Run the packaging and manager tests**

Run: `uv run pytest tests/test_system/test_plugin_packaging.py tests/test_system/test_plugin_manager.py -v`

Expected: FAIL until external-only boot works.

- [ ] **Step 3: Fix whatever still assumes builtin placement**

Keep the fix scope narrow. Only touch host/plugin code that still assumes the QQ plugin lives under `plugins/builtin/qqmusic`.

- [ ] **Step 4: Re-run the external-only tests**

Run: `uv run pytest tests/test_system/test_plugin_packaging.py tests/test_system/test_plugin_manager.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_system/test_plugin_packaging.py tests/test_system/test_plugin_manager.py
git commit -m "验证QQ外部插件独立加载"
```

### Task 6: Finish The Distribution Surface

**Files:**
- Modify: `ui/dialogs/plugin_management_tab.py`
- Modify: `README.md`
- Test: `tests/test_ui/test_plugin_settings_tab.py`

- [ ] **Step 1: Add failing UI/doc expectations**

Add focused tests for plugin install UX where appropriate, including a warning that external plugins execute trusted Python code. Update README expectations away from `Settings -> QQ Music Configuration` as a host-owned built-in feature.

- [ ] **Step 2: Run focused UI tests**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py -v`

Expected: FAIL if the new warning or labels are not implemented yet.

- [ ] **Step 3: Implement the final UX/documentation cleanup**

Update the plugin management tab to show the install safety warning and, if desired in this scope, add uninstall support for external plugins only. Update README to describe plugin installation, enabling, and QQ Music login through the plugin-provided settings tab.

- [ ] **Step 4: Re-run UI/doc tests**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ui/dialogs/plugin_management_tab.py README.md tests/test_ui/test_plugin_settings_tab.py
git commit -m "完善插件发布入口与文档"
```

## Acceptance Checklist

- [ ] No host file under `app/`, `services/`, `system/`, `ui/`, `repositories/`, `domain/`, `infrastructure/`, or `utils/` imports `plugins.builtin.qqmusic`.
- [ ] `plugins/builtin/qqmusic` can be zipped, installed externally, and loaded without relying on any host-side QQ compatibility shim.
- [ ] Deleting the builtin QQ plugin from the repository does not break host startup.
- [ ] An external `qqmusic` plugin overrides any bundled plugin with the same id.
- [ ] Plugin audit rejects both static and simple dynamic imports of forbidden host modules.
- [ ] README and settings UI describe QQ Music as a plugin, not a baked-in host feature.

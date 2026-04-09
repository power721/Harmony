# Harmony Plugin API Packaging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `harmony_plugin_api` as a standalone pip package `harmony-plugin-api` while keeping all Harmony host runtime implementations inside the main app.

**Architecture:** Create a repo-local distributable package under `packages/harmony-plugin-api/` and move only the pure SDK modules there. Replace the current `harmony_plugin_api.ui` and `harmony_plugin_api.runtime` host-coupled modules with host-side bridge modules under `system/plugins/`, then update host wiring and the QQ plugin to use `PluginContext` or host bridge imports instead of SDK runtime imports.

**Tech Stack:** Python 3.11, uv, pytest, build backend via `pyproject.toml`

---

## File Map

- Create: `packages/harmony-plugin-api/pyproject.toml` — standalone package metadata and build config for `harmony-plugin-api`
- Create: `packages/harmony-plugin-api/README.md` — package-facing README with installation and scope notes
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/__init__.py` — public SDK exports
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/context.py` — pure bridge protocols only
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/plugin.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/manifest.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/media.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/lyrics.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/cover.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/online.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/registry_types.py`
- Create: `system/plugins/plugin_sdk_ui.py` — host-side theme/dialog/icon bridge implementation
- Create: `system/plugins/plugin_sdk_runtime.py` — host-side runtime helpers used by legacy QQ bridge code
- Modify: `system/plugins/host_services.py` — swap imports from SDK runtime modules to host bridge modules while preserving `PluginContext`
- Modify: `plugins/builtin/qqmusic/lib/dialog_title_bar.py` — stop importing `harmony_plugin_api.ui`
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py` — stop importing `harmony_plugin_api.ui`
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py` — stop importing `harmony_plugin_api.ui`
- Modify: `plugins/builtin/qqmusic/lib/runtime_bridge.py` — stop importing `harmony_plugin_api.ui` / `runtime`
- Delete: `harmony_plugin_api/ui.py` — not part of publishable SDK
- Delete: `harmony_plugin_api/runtime.py` — not part of publishable SDK
- Modify: `harmony_plugin_api/__init__.py` — leave as local compatibility shim or re-export from installed package path only if still needed during migration
- Modify: `harmony_plugin_api/context.py` — keep in sync with packaged SDK or reduce to thin compatibility wrapper
- Modify: `tests/test_system/test_plugin_ui_bridge.py` — assert host bridge is provided via context, not via SDK runtime imports
- Modify: `tests/test_system/test_plugin_import_guard.py` — verify packaged SDK modules are allowed and host modules are forbidden
- Add: `tests/test_system/test_harmony_plugin_api_package.py` — package structure/build/import assertions

### Task 1: Scaffold the Standalone Package and Lock the SDK Boundary

**Files:**
- Create: `packages/harmony-plugin-api/pyproject.toml`
- Create: `packages/harmony-plugin-api/README.md`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/__init__.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/context.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/plugin.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/manifest.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/media.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/lyrics.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/cover.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/online.py`
- Create: `packages/harmony-plugin-api/src/harmony_plugin_api/registry_types.py`
- Add: `tests/test_system/test_harmony_plugin_api_package.py`

- [ ] **Step 1: Write the failing package structure tests**

```python
from pathlib import Path


def test_harmony_plugin_api_package_has_standalone_pyproject():
    pyproject = Path("packages/harmony-plugin-api/pyproject.toml")
    assert pyproject.exists()
    content = pyproject.read_text(encoding="utf-8")
    assert 'name = "harmony-plugin-api"' in content
    assert 'version = "0.1.0"' in content


def test_harmony_plugin_api_package_excludes_host_runtime_modules():
    package_root = Path("packages/harmony-plugin-api/src/harmony_plugin_api")
    assert (package_root / "context.py").exists()
    assert not (package_root / "ui.py").exists()
    assert not (package_root / "runtime.py").exists()
```

- [ ] **Step 2: Run the package structure tests to verify they fail**

Run: `uv run pytest tests/test_system/test_harmony_plugin_api_package.py -v`
Expected: FAIL because `packages/harmony-plugin-api/` does not exist yet

- [ ] **Step 3: Create the standalone package skeleton and copy only pure SDK modules**

```toml
[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "harmony-plugin-api"
version = "0.1.0"
description = "Pure plugin SDK for Harmony plugins"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

```python
# packages/harmony-plugin-api/src/harmony_plugin_api/__init__.py
from .context import (
    PluginContext,
    PluginDialogBridge,
    PluginMediaBridge,
    PluginServiceBridge,
    PluginSettingsBridge,
    PluginStorageBridge,
    PluginThemeBridge,
    PluginUiBridge,
)
from .cover import (
    PluginArtistCoverResult,
    PluginArtistCoverSource,
    PluginCoverResult,
    PluginCoverSource,
)
from .lyrics import PluginLyricsResult, PluginLyricsSource
from .manifest import Capability, PluginManifest, PluginManifestError
from .media import PluginPlaybackRequest, PluginTrack
from .online import PluginOnlineProvider
from .plugin import HarmonyPlugin
from .registry_types import SettingsTabSpec, SidebarEntrySpec
```

- [ ] **Step 4: Run the package structure tests again**

Run: `uv run pytest tests/test_system/test_harmony_plugin_api_package.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add packages/harmony-plugin-api tests/test_system/test_harmony_plugin_api_package.py
git commit -m "新增可发布的插件SDK包"
```

### Task 2: Move Host Runtime Helpers out of the SDK

**Files:**
- Create: `system/plugins/plugin_sdk_ui.py`
- Create: `system/plugins/plugin_sdk_runtime.py`
- Modify: `system/plugins/host_services.py`
- Delete: `harmony_plugin_api/ui.py`
- Delete: `harmony_plugin_api/runtime.py`
- Modify: `tests/test_system/test_plugin_ui_bridge.py`

- [ ] **Step 1: Write the failing host bridge tests**

```python
def test_plugin_context_ui_bridge_uses_host_bridge_modules(tmp_path: Path):
    config = Mock()
    config.get.return_value = "dark"
    config.get_language.return_value = "zh"
    ThemeManager._instance = None
    ThemeManager.instance(config)

    bootstrap = SimpleNamespace(
        _plugin_manager=SimpleNamespace(registry=Mock()),
        online_download_service=Mock(),
        playback_service=Mock(),
        library_service=Mock(),
        http_client=Mock(),
        event_bus=Mock(),
        config=config,
    )
    manifest = PluginManifest.from_dict({...})

    context = BootstrapPluginContextFactory(bootstrap, tmp_path).build(manifest)

    assert context.ui.theme.__class__.__module__ == "system.plugins.plugin_sdk_ui"
    assert context.ui.dialogs.__class__.__module__ == "system.plugins.plugin_sdk_ui"
```

- [ ] **Step 2: Run the host bridge test to verify it fails**

Run: `uv run pytest tests/test_system/test_plugin_ui_bridge.py::test_plugin_context_ui_bridge_uses_host_bridge_modules -v`
Expected: FAIL because `system.plugins.plugin_sdk_ui` does not exist yet

- [ ] **Step 3: Implement host-side SDK runtime modules and switch host wiring**

```python
# system/plugins/plugin_sdk_ui.py
class PluginThemeBridgeImpl:
    def register_widget(self, widget) -> None:
        ThemeManager.instance().register_widget(widget)

    def get_qss(self, template: str) -> str:
        return ThemeManager.instance().get_qss(template)

    def current_theme(self):
        return ThemeManager.instance().current_theme
```

```python
# system/plugins/plugin_sdk_ui.py
class PluginDialogBridgeImpl:
    def information(self, parent, title: str, message: str):
        return MessageDialog.information(parent, title, message)

    def setup_title_bar(self, dialog, container_layout, title: str, **kwargs):
        return setup_equalizer_title_layout(dialog, container_layout, title, **kwargs)
```

```python
# system/plugins/host_services.py
from .plugin_sdk_ui import PluginDialogBridgeImpl, PluginThemeBridgeImpl
```

- [ ] **Step 4: Run the host bridge tests**

Run: `uv run pytest tests/test_system/test_plugin_ui_bridge.py tests/test_system/test_plugin_online_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add system/plugins/plugin_sdk_ui.py system/plugins/plugin_sdk_runtime.py system/plugins/host_services.py tests/test_system/test_plugin_ui_bridge.py
git commit -m "移出SDK宿主运行时实现"
```

### Task 3: Retarget QQ Plugin Imports Away from SDK Runtime Modules

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/dialog_title_bar.py`
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Modify: `plugins/builtin/qqmusic/lib/runtime_bridge.py`
- Modify: `tests/test_system/test_plugin_import_guard.py`

- [ ] **Step 1: Write the failing import boundary test**

```python
def test_qqmusic_plugin_no_longer_imports_sdk_runtime_modules():
    plugin_root = Path("plugins/builtin/qqmusic")
    for py_file in plugin_root.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        assert "harmony_plugin_api.ui" not in source
        assert "harmony_plugin_api.runtime" not in source
```

- [ ] **Step 2: Run the import boundary test to verify it fails**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py -k "sdk_runtime_modules" -v`
Expected: FAIL because QQ plugin still imports `harmony_plugin_api.ui` / `runtime`

- [ ] **Step 3: Retarget QQ plugin code to host bridge modules or injected context**

```python
# plugins/builtin/qqmusic/lib/dialog_title_bar.py
from system.plugins.plugin_sdk_ui import get_host_icon, get_host_qss
```

```python
# plugins/builtin/qqmusic/lib/runtime_bridge.py
from system.plugins.plugin_sdk_runtime import (
    IconName,
    add_requests_to_favorites,
    add_requests_to_playlist,
    add_track_ids_to_playlist,
    bootstrap,
    ...
)
from system.plugins.plugin_sdk_ui import (
    current_theme,
    get_qss,
    information,
    register_themed_widget,
    warning,
)
```

- [ ] **Step 4: Run the QQ plugin import boundary tests**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py tests/test_ui/test_plugin_settings_tab.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add plugins/builtin/qqmusic/lib/dialog_title_bar.py plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/lib/settings_tab.py plugins/builtin/qqmusic/lib/runtime_bridge.py tests/test_system/test_plugin_import_guard.py
git commit -m "清理插件对SDK运行时模块的依赖"
```

### Task 4: Build and Install the Standalone SDK Package

**Files:**
- Modify: `tests/test_system/test_harmony_plugin_api_package.py`
- Create: `packages/harmony-plugin-api/dist/` (build artifact, not committed)

- [ ] **Step 1: Write the failing build/import smoke test**

```python
def test_harmony_plugin_api_package_can_be_built():
    dist_dir = Path("packages/harmony-plugin-api/dist")
    assert any(path.suffix == ".whl" for path in dist_dir.glob("*.whl"))
```

- [ ] **Step 2: Run the smoke test to verify it fails before building**

Run: `uv run pytest tests/test_system/test_harmony_plugin_api_package.py::test_harmony_plugin_api_package_can_be_built -v`
Expected: FAIL because no wheel has been built yet

- [ ] **Step 3: Build the package and install it into a temporary target**

```bash
cd packages/harmony-plugin-api
uv build
python -m pip install --target /tmp/harmony-plugin-api-test dist/harmony_plugin_api-0.1.0-py3-none-any.whl
python -c "import sys; sys.path.insert(0, '/tmp/harmony-plugin-api-test'); import harmony_plugin_api; print(harmony_plugin_api.__all__)"
```

- [ ] **Step 4: Run the build/import smoke test and focused integration tests**

Run: `uv run pytest tests/test_system/test_harmony_plugin_api_package.py tests/test_system/test_plugin_import_guard.py tests/test_system/test_plugin_ui_bridge.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 4**

```bash
git add tests/test_system/test_harmony_plugin_api_package.py packages/harmony-plugin-api/pyproject.toml packages/harmony-plugin-api/README.md
git commit -m "验证插件SDK包可构建"
```

## Self-Review

- Spec coverage: the plan covers package layout, pure SDK boundary, host runtime extraction, plugin import retargeting, and build/install verification.
- Placeholder scan: every task lists exact files, test targets, implementation seams, and verification commands.
- Type consistency: the plan keeps `PluginContext` as the sole stable plugin entry and treats theme/dialog bridges as protocols in the SDK with host implementations in `system/plugins/`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-harmony-plugin-api-packaging.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

# Plugin Restart Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let unsafe plugins opt into restart-only enable and disable behavior.

**Architecture:** Extend the manifest with a restart-required flag, thread that metadata through the plugin manager list output, and make `set_plugin_enabled()` skip hot load and unload for flagged plugins. Update the plugin management tab to show a restart prompt after those toggles.

**Tech Stack:** Python, PySide6, pytest

---

### Task 1: Manifest Contract

**Files:**
- Modify: `packages/harmony-plugin-api/src/harmony_plugin_api/manifest.py`
- Test: `tests/test_system/test_plugin_manifest.py`

- [ ] **Step 1: Write the failing test**

```python
def test_manifest_accepts_requires_restart_on_toggle():
    manifest = PluginManifest.from_dict(
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "api_version": "1",
            "entrypoint": "plugin_main.py",
            "entry_class": "QQMusicPlugin",
            "capabilities": ["sidebar"],
            "min_app_version": "0.1.0",
            "requires_restart_on_toggle": True,
        }
    )

    assert manifest.requires_restart_on_toggle is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system/test_plugin_manifest.py::test_manifest_accepts_requires_restart_on_toggle -v`
Expected: FAIL because `PluginManifest` has no `requires_restart_on_toggle` attribute.

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True)
class PluginManifest:
    ...
    requires_restart_on_toggle: bool = False

@classmethod
def from_dict(cls, data: dict[str, Any]) -> "PluginManifest":
    requires_restart_on_toggle = data.get("requires_restart_on_toggle", False)
    if not isinstance(requires_restart_on_toggle, bool):
        raise PluginManifestError(
            "Manifest field 'requires_restart_on_toggle' must be a bool if provided"
        )
    ...
    return cls(..., requires_restart_on_toggle=requires_restart_on_toggle)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system/test_plugin_manifest.py::test_manifest_accepts_requires_restart_on_toggle -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_system/test_plugin_manifest.py packages/harmony-plugin-api/src/harmony_plugin_api/manifest.py
git commit -m "支持插件切换需重启声明"
```

### Task 2: Manager Toggle Semantics

**Files:**
- Modify: `system/plugins/manager.py`
- Modify: `plugins/builtin/qqmusic/plugin.json`
- Test: `tests/test_system/test_plugin_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_manager_toggle_for_restart_required_plugin_only_updates_state(tmp_path: Path):
    ...
    manager._load_plugin_root = Mock()
    manager._unload_plugin = Mock()

    manager.set_plugin_enabled("qqmusic", False)

    assert store.get("qqmusic")["enabled"] is False
    manager._load_plugin_root.assert_not_called()
    manager._unload_plugin.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_system/test_plugin_manager.py::test_manager_toggle_for_restart_required_plugin_only_updates_state -v`
Expected: FAIL because the current manager immediately unloads the plugin.

- [ ] **Step 3: Write minimal implementation**

```python
plugins.append(
    {
        ...,
        "requires_restart_on_toggle": manifest.requires_restart_on_toggle,
    }
)

if manifest.requires_restart_on_toggle:
    return

if enabled:
    self._load_plugin_root(source, plugin_root)
else:
    self._unload_plugin(plugin_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_system/test_plugin_manager.py::test_manager_toggle_for_restart_required_plugin_only_updates_state -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_system/test_plugin_manager.py system/plugins/manager.py plugins/builtin/qqmusic/plugin.json
git commit -m "限制需重启插件热切换"
```

### Task 3: Plugin Management Prompt

**Files:**
- Modify: `ui/dialogs/plugin_management_tab.py`
- Modify: `translations/en.json`
- Modify: `translations/zh.json`
- Test: `tests/test_ui/test_plugin_settings_tab.py`

- [ ] **Step 1: Write the failing test**

```python
def test_plugin_management_tab_shows_restart_prompt_for_restart_required_plugin(...):
    ...
    manager.set_plugin_enabled.return_value = {"requires_restart": True}
    information = Mock()
    monkeypatch.setattr("ui.dialogs.plugin_management_tab.MessageDialog.information", information)
    ...
    information.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_shows_restart_prompt_for_restart_required_plugin -v`
Expected: FAIL because no dialog is shown today.

- [ ] **Step 3: Write minimal implementation**

```python
result = self._plugin_manager.set_plugin_enabled(plugin_id, enabled)
if isinstance(result, dict) and result.get("requires_restart"):
    MessageDialog.information(
        self,
        t("info"),
        t("plugins_restart_required_after_toggle"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_shows_restart_prompt_for_restart_required_plugin -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_plugin_settings_tab.py ui/dialogs/plugin_management_tab.py translations/en.json translations/zh.json
git commit -m "提示需重启插件切换生效"
```

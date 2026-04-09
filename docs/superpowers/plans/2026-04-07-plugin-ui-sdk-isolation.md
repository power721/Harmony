# Plugin UI SDK Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the QQ Music settings tab to legacy parity while moving plugin theme/dialog access behind `harmony_plugin_api` and enforcing that plugins only import the SDK and their own files.

**Architecture:** Keep plugin settings tabs mounted by the host settings dialog, but rebuild `plugins/builtin/qqmusic/lib/settings_tab.py` to mirror the legacy QQ settings composition and behaviors using plugin-scoped settings. Add a stable UI bridge to `harmony_plugin_api` that is implemented by the host and consumed by plugins, then enforce the boundary with both install-time audit and runtime import guarding.

**Tech Stack:** Python 3.11, PySide6, pytest, pytest-qt, `uv`

---

## File Map

- Modify: `harmony_plugin_api/context.py` — add typed UI bridge protocols for theme, message dialogs, and dialog title bar helpers
- Modify: `system/plugins/host_services.py` — implement the new host-backed SDK UI bridge and expose it from `PluginContext`
- Modify: `system/plugins/installer.py` — tighten static import audit to reject host modules while allowing SDK, plugin-relative imports, standard library, and Qt imports
- Modify: `system/plugins/loader.py` — add runtime import guarding during plugin module execution
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py` — rebuild the plugin settings tab to match the legacy QQ settings structure and behavior
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py` — swap private bridge helpers for SDK UI/theme access
- Modify: `plugins/builtin/qqmusic/plugin_main.py` — stop relying on private runtime bridge assumptions if needed by the settings tab/widget factories
- Remove or stop using: `plugins/builtin/qqmusic/lib/runtime_bridge.py`, `plugins/builtin/qqmusic/lib/dialog_title_bar.py`
- Modify: `tests/test_ui/test_plugin_settings_tab.py` — add regression tests for QQ settings parity and host-mounted plugin tab behavior
- Modify: `tests/test_system/test_plugin_import_guard.py` — add install-time and runtime isolation tests
- Add: `tests/test_system/test_plugin_ui_bridge.py` — verify the new SDK UI bridge uses host theme/dialog implementations

### Task 1: Add Failing Tests for SDK UI Bridge and Plugin Isolation

**Files:**
- Modify: `tests/test_system/test_plugin_import_guard.py`
- Add: `tests/test_system/test_plugin_ui_bridge.py`
- Modify: `harmony_plugin_api/context.py`
- Modify: `system/plugins/host_services.py`
- Modify: `system/plugins/installer.py`
- Modify: `system/plugins/loader.py`

- [ ] **Step 1: Write the failing UI bridge and runtime isolation tests**

```python
def test_plugin_context_ui_bridge_exposes_theme_dialog_and_title_bar(tmp_path):
    config = Mock()
    ThemeManager._instance = None
    ThemeManager.instance(config)
    registry = Mock()
    bootstrap = Mock(
        http_client=Mock(),
        event_bus=Mock(),
        config=config,
        online_download_service=Mock(),
        playback_service=Mock(),
        library_service=Mock(),
    )
    bootstrap.plugin_manager = Mock(registry=registry)

    factory = BootstrapPluginContextFactory(bootstrap, tmp_path)
    manifest = PluginManifest.from_dict(
        {"id": "qqmusic", "name": "QQ Music", "version": "1.0.0", "entrypoint": "plugin_main.py", "entry_class": "QQMusicPlugin"}
    )

    context = factory.build(manifest)

    assert hasattr(context.ui, "theme")
    assert hasattr(context.ui, "dialogs")
    assert callable(context.ui.theme.get_qss)
    assert callable(context.ui.dialogs.information)
    assert callable(context.ui.dialogs.setup_title_bar)
```

```python
def test_runtime_import_guard_rejects_host_module_import(tmp_path: Path):
    plugin_root = tmp_path / "bad_plugin"
    plugin_root.mkdir()
    (plugin_root / "plugin.json").write_text(json.dumps({
        "id": "bad-plugin",
        "name": "Bad Plugin",
        "version": "1.0.0",
        "entrypoint": "plugin_main.py",
        "entry_class": "BadPlugin",
    }), encoding="utf-8")
    (plugin_root / "plugin_main.py").write_text(
        "from ui.dialogs.message_dialog import MessageDialog\n"
        "class BadPlugin:\n"
        "    pass\n",
        encoding="utf-8",
    )

    with pytest.raises(PluginLoadError):
        PluginLoader().load_plugin(plugin_root)
```

- [ ] **Step 2: Run the focused system tests to verify they fail**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py tests/test_system/test_plugin_ui_bridge.py -v`
Expected: FAIL with missing `context.ui.theme` / `context.ui.dialogs` attributes and missing runtime import guard behavior

- [ ] **Step 3: Implement the SDK UI bridge and runtime import guard**

```python
class PluginThemeBridge(Protocol):
    def register_widget(self, widget) -> None: ...
    def get_qss(self, template: str) -> str: ...
    def current_theme(self): ...
```

```python
class PluginDialogBridge(Protocol):
    def information(self, parent, title: str, message: str): ...
    def warning(self, parent, title: str, message: str): ...
    def question(self, parent, title: str, message: str, buttons, default_button): ...
    def critical(self, parent, title: str, message: str): ...
    def setup_title_bar(self, dialog, container_layout, title: str, **kwargs): ...
```

```python
class _PluginImportGuard:
    _FORBIDDEN_ROOTS = {"app", "domain", "services", "repositories", "infrastructure", "system", "ui"}
    _ALLOWED_ROOTS = {"harmony_plugin_api", "PySide6", "shiboken6"}
```

- [ ] **Step 4: Re-run the focused system tests and the existing plugin bootstrap tests**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py tests/test_system/test_plugin_ui_bridge.py tests/test_app/test_plugin_bootstrap.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/test_system/test_plugin_import_guard.py tests/test_system/test_plugin_ui_bridge.py harmony_plugin_api/context.py system/plugins/host_services.py system/plugins/installer.py system/plugins/loader.py
git commit -m "增加插件UI桥和导入隔离"
```

### Task 2: Rebuild the QQ Music Plugin Settings Tab to Match Legacy Layout and Behavior

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/settings_tab.py`
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `tests/test_ui/test_plugin_settings_tab.py`

- [ ] **Step 1: Write the failing parity tests for the QQ settings tab**

```python
def test_qqmusic_settings_tab_matches_legacy_sections(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: {
        "quality": "320",
        "download_dir": "data/online_cache",
        "credential": {"musicid": "12345", "loginType": 2},
        "nick": "Tester",
    }.get(key, default)
    settings.set = Mock()
    context = Mock(settings=settings, events=Mock(), language="zh", ui=Mock())
    context.ui.theme.get_qss.side_effect = lambda template: template
    context.ui.theme.current_theme.return_value = type("Theme", (), {"text_secondary": "#999999"})()
    context.ui.theme.register_widget = Mock()

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)

    assert widget._quality_combo.count() >= 3
    assert widget._download_dir_input.text() == "data/online_cache"
    assert widget._qqmusic_logout_btn.isVisible()
    assert widget._status_label.text()
```

```python
def test_qqmusic_settings_tab_save_writes_plugin_scoped_settings(qtbot):
    settings = Mock()
    settings.get.side_effect = lambda key, default=None: default
    context = Mock(settings=settings, events=Mock(), language="zh", ui=Mock())
    context.ui.theme.get_qss.side_effect = lambda template: template
    context.ui.theme.current_theme.return_value = type("Theme", (), {"text_secondary": "#999999"})()
    context.ui.theme.register_widget = Mock()

    widget = QQMusicSettingsTab(context)
    qtbot.addWidget(widget)
    widget._download_dir_input.setText("/tmp/music")
    widget._quality_combo.setCurrentIndex(1)
    widget._save_settings()

    settings.set.assert_any_call("download_dir", "/tmp/music")
    settings.set.assert_any_call("quality", widget._quality_combo.currentData())
```

- [ ] **Step 2: Run the focused UI tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py -k "qqmusic_settings_tab" -v`
Expected: FAIL with missing legacy widgets such as `_download_dir_input`, `_qqmusic_logout_btn`, or `_save_settings`

- [ ] **Step 3: Implement the legacy-style plugin settings tab and move it to SDK UI access**

```python
class QQMusicSettingsTab(QWidget):
    def __init__(self, context, parent=None):
        self._context = context
        self._verify_thread: Optional[VerifyLoginThread] = None
        self._theme = context.ui.theme
```

```python
layout.addWidget(_build_quality_group())
layout.addWidget(_build_download_dir_group())
layout.addWidget(_build_login_group())
self._save_btn.clicked.connect(self._save_settings)
self._qqmusic_qr_btn.clicked.connect(self._open_login_dialog)
self._qqmusic_logout_btn.clicked.connect(self._clear_credentials)
```

- [ ] **Step 4: Re-run the focused QQ settings UI tests and the settings dialog plugin-tab tests**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py tests/test_ui/test_settings_dialog.py -k "plugin or qqmusic_settings_tab" -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/test_ui/test_plugin_settings_tab.py plugins/builtin/qqmusic/lib/settings_tab.py plugins/builtin/qqmusic/lib/login_dialog.py
git commit -m "恢复QQ插件设置页布局"
```

### Task 3: Remove Private QQ Runtime UI Bridges and Finish the Boundary

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/login_dialog.py`
- Modify: `plugins/builtin/qqmusic/plugin_main.py`
- Remove or stop using: `plugins/builtin/qqmusic/lib/runtime_bridge.py`
- Remove or stop using: `plugins/builtin/qqmusic/lib/dialog_title_bar.py`
- Modify: `tests/test_plugins/test_qqmusic_plugin.py`

- [ ] **Step 1: Write the failing test that QQ plugin imports only SDK and plugin-local modules**

```python
def test_builtin_qqmusic_plugin_passes_import_audit():
    audit_plugin_imports(Path("plugins/builtin/qqmusic"))
```

- [ ] **Step 2: Run the audit test to verify it fails while the private bridges still import host modules**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py::test_builtin_qqmusic_plugin_passes_import_audit -v`
Expected: FAIL because QQ plugin files still import host `system` / `ui` modules directly

- [ ] **Step 3: Replace private bridge usage with SDK-backed context UI access**

```python
def _apply_theme(self):
    self.setStyleSheet(self._context.ui.theme.get_qss(self._STYLE_TEMPLATE))
    self._title_bar_controller.refresh_theme()
```

```python
self._title_bar_controller = self._context.ui.dialogs.setup_title_bar(
    self,
    container_layout,
    t("qqmusic_login_title"),
    content_spacing=2,
)[1]
```

- [ ] **Step 4: Re-run the plugin import audit and focused QQ plugin tests**

Run: `uv run pytest tests/test_system/test_plugin_import_guard.py tests/test_plugins/test_qqmusic_plugin.py -k "qqmusic or import" -v`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add tests/test_system/test_plugin_import_guard.py tests/test_plugins/test_qqmusic_plugin.py plugins/builtin/qqmusic/lib/login_dialog.py plugins/builtin/qqmusic/plugin_main.py
git commit -m "收紧插件边界"
```

## Self-Review

- Spec coverage: the plan covers legacy QQ settings parity, SDK-based theme/dialog exposure, and both install-time + runtime plugin isolation.
- Placeholder scan: each task identifies exact files, focused tests, implementation seams, and verification commands.
- Type consistency: the plan uses `context.ui.theme` and `context.ui.dialogs` as the stable SDK boundary everywhere, so plugins do not need host imports.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-07-plugin-ui-sdk-isolation.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?

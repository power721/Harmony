# Plugin Management Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the settings plugin management tab so each plugin row owns its own enable or disable toggle and built-in or external source labels are localized.

**Architecture:** Keep `QListWidget` as the container, replace plain text entries with a compact row widget that renders plugin metadata and a row-level `QCheckBox`, and route toggle callbacks back through `PluginManagementTab.refresh()`. Localize source ids in the tab with dedicated host translation keys so the change stays confined to the existing settings UI and translation JSON files.

**Tech Stack:** Python 3.11, PySide6, pytest, pytest-qt, host JSON translations

---

## File Map

- Modify: `ui/dialogs/plugin_management_tab.py` — replace plain text rows and shared buttons with row widgets and per-plugin toggle wiring
- Modify: `tests/test_ui/test_plugin_settings_tab.py` — cover localized source labels, row-level toggles, and load error rendering
- Modify: `translations/zh.json` — add localized source labels for `builtin` and `external`
- Modify: `translations/en.json` — add English source labels for `builtin` and `external`

### Task 1: Localize Plugin Source Labels in Row Widgets

**Files:**
- Modify: `tests/test_ui/test_plugin_settings_tab.py`
- Modify: `ui/dialogs/plugin_management_tab.py`
- Modify: `translations/zh.json`
- Modify: `translations/en.json`

- [ ] **Step 1: Write the failing source label test**

```python
from PySide6.QtWidgets import QLabel, QTabWidget, QWidget


def _plugin_row_text(widget: PluginManagementTab, index: int) -> str:
    item = widget._list.item(index)
    row_widget = widget._list.itemWidget(item)
    assert row_widget is not None
    labels = row_widget.findChildren(QLabel)
    return " ".join(label.text() for label in labels)


def test_plugin_management_tab_localizes_plugin_sources(qtbot):
    manager = Mock()
    manager.list_plugins.return_value = [
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "source": "builtin",
            "enabled": True,
            "load_error": None,
        },
        {
            "id": "lrclib",
            "name": "LRCLIB",
            "version": "1.0.0",
            "source": "external",
            "enabled": False,
            "load_error": None,
        },
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    first_row = _plugin_row_text(widget, 0)
    second_row = _plugin_row_text(widget, 1)

    assert "内置" in first_row
    assert "builtin" not in first_row.lower()
    assert "外部" in second_row
    assert "external" not in second_row.lower()
```

- [ ] **Step 2: Run the source label test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_localizes_plugin_sources -v`
Expected: FAIL because `PluginManagementTab` still renders plain text `QListWidgetItem` rows, so `itemWidget()` returns `None`

- [ ] **Step 3: Implement row widgets and localized source mapping**

```python
# ui/dialogs/plugin_management_tab.py
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class _PluginListRow(QWidget):
    def __init__(self, row: dict, source_label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        name_label = QLabel(row["name"], self)
        meta_label = QLabel(f'{row["version"]} · {source_label}', self)

        info_layout.addWidget(name_label)
        info_layout.addWidget(meta_label)
        layout.addLayout(info_layout, 1)


class PluginManagementTab(QWidget):
    def _source_label(self, source: str) -> str:
        key = {
            "builtin": "plugins_source_builtin",
            "external": "plugins_source_external",
        }.get(source)
        return t(key) if key else source

    def refresh(self) -> None:
        rows = self._plugin_manager.list_plugins()
        self._list.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setData(0x0100, row)
            row_widget = _PluginListRow(
                row,
                self._source_label(row.get("source", "")),
                self,
            )
            item.setSizeHint(row_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)
```

```json
// translations/zh.json
"plugins_source_builtin": "内置",
"plugins_source_external": "外部",
```

```json
// translations/en.json
"plugins_source_builtin": "Built-in",
"plugins_source_external": "External",
```

- [ ] **Step 4: Run the source label test again**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_localizes_plugin_sources -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add tests/test_ui/test_plugin_settings_tab.py ui/dialogs/plugin_management_tab.py translations/zh.json translations/en.json
git commit -m "翻译插件来源文案"
```

### Task 2: Replace Shared Buttons with Per-Row Toggle Controls

**Files:**
- Modify: `tests/test_ui/test_plugin_settings_tab.py`
- Modify: `ui/dialogs/plugin_management_tab.py`

- [ ] **Step 1: Write the failing row toggle test**

```python
from PySide6.QtWidgets import QCheckBox, QLabel, QTabWidget, QWidget


def _plugin_toggle(widget: PluginManagementTab, plugin_id: str) -> QCheckBox:
    toggle = widget.findChild(QCheckBox, f"pluginToggle:{plugin_id}")
    assert toggle is not None
    return toggle


def test_plugin_management_tab_uses_row_level_toggles(qtbot):
    manager = Mock()
    manager.list_plugins.side_effect = [
        [
            {
                "id": "qqmusic",
                "name": "QQ Music",
                "version": "1.0.0",
                "source": "builtin",
                "enabled": True,
                "load_error": None,
            },
            {
                "id": "lrclib",
                "name": "LRCLIB",
                "version": "1.0.0",
                "source": "external",
                "enabled": False,
                "load_error": None,
            },
        ],
        [
            {
                "id": "qqmusic",
                "name": "QQ Music",
                "version": "1.0.0",
                "source": "builtin",
                "enabled": False,
                "load_error": None,
            },
            {
                "id": "lrclib",
                "name": "LRCLIB",
                "version": "1.0.0",
                "source": "external",
                "enabled": False,
                "load_error": None,
            },
        ],
        [
            {
                "id": "qqmusic",
                "name": "QQ Music",
                "version": "1.0.0",
                "source": "builtin",
                "enabled": False,
                "load_error": None,
            },
            {
                "id": "lrclib",
                "name": "LRCLIB",
                "version": "1.0.0",
                "source": "external",
                "enabled": True,
                "load_error": None,
            },
        ],
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    _plugin_toggle(widget, "qqmusic").click()
    _plugin_toggle(widget, "lrclib").click()

    manager.set_plugin_enabled.assert_any_call("qqmusic", False)
    manager.set_plugin_enabled.assert_any_call("lrclib", True)
    assert manager.list_plugins.call_count == 3
```

- [ ] **Step 2: Run the row toggle test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_uses_row_level_toggles -v`
Expected: FAIL because the tab still has shared action buttons and no row-level `QCheckBox` named `pluginToggle:<plugin_id>`

- [ ] **Step 3: Implement row-level toggles and remove shared enable or disable buttons**

```python
# ui/dialogs/plugin_management_tab.py
from PySide6.QtCore import Signal


class _PluginListRow(QWidget):
    toggled = Signal(str, bool)

    def __init__(self, row: dict, source_label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        name_label = QLabel(row["name"], self)
        status = t("plugins_enabled") if row.get("enabled", True) else t("plugins_disabled")
        meta_label = QLabel(f'{row["version"]} · {source_label} · {status}', self)
        info_layout.addWidget(name_label)
        info_layout.addWidget(meta_label)
        layout.addLayout(info_layout, 1)

        plugin_id = row.get("id", "")
        toggle = QCheckBox(t("plugins_enabled"), self)
        toggle.setObjectName(f"pluginToggle:{plugin_id}")
        toggle.setChecked(bool(row.get("enabled", True)))
        toggle.toggled.connect(lambda enabled: self.toggled.emit(plugin_id, enabled))
        layout.addWidget(toggle)


class PluginManagementTab(QWidget):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self._plugin_manager = plugin_manager
        self._list = QListWidget(self)
        self._url_input = QLineEdit(self)
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(self._list)

        controls = QHBoxLayout()
        self._url_input.setPlaceholderText("https://example.com/plugin.zip")
        install_zip_btn = QPushButton(t("plugins_install_zip"), self)
        install_zip_btn.clicked.connect(self._install_zip)
        install_url_btn = QPushButton(t("plugins_install_url"), self)
        install_url_btn.clicked.connect(self._install_url)
        controls.addWidget(self._url_input)
        controls.addWidget(install_zip_btn)
        controls.addWidget(install_url_btn)
        layout.addLayout(controls)

    def _set_plugin_enabled(self, plugin_id: str, enabled: bool) -> None:
        if not plugin_id:
            return
        self._plugin_manager.set_plugin_enabled(plugin_id, enabled)
        self.refresh()

    def refresh(self) -> None:
        rows = self._plugin_manager.list_plugins()
        self._list.clear()
        for row in rows:
            item = QListWidgetItem()
            item.setData(0x0100, row)
            row_widget = _PluginListRow(
                row,
                self._source_label(row.get("source", "")),
                self,
            )
            row_widget.toggled.connect(self._set_plugin_enabled)
            item.setSizeHint(row_widget.sizeHint())
            self._list.addItem(item)
            self._list.setItemWidget(item, row_widget)
```

- [ ] **Step 4: Run the row toggle test again**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_uses_row_level_toggles -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add tests/test_ui/test_plugin_settings_tab.py ui/dialogs/plugin_management_tab.py
git commit -m "改为插件行内启用开关"
```

### Task 3: Preserve Load Error Rendering in the New Row Layout

**Files:**
- Modify: `tests/test_ui/test_plugin_settings_tab.py`
- Modify: `ui/dialogs/plugin_management_tab.py`

- [ ] **Step 1: Write the failing load error regression test**

```python
def test_plugin_management_tab_shows_load_errors_in_custom_rows(qtbot):
    manager = Mock()
    manager.list_plugins.return_value = [
        {
            "id": "qqmusic",
            "name": "QQ Music",
            "version": "1.0.0",
            "source": "builtin",
            "enabled": False,
            "load_error": "load failed",
        }
    ]

    widget = PluginManagementTab(manager)
    qtbot.addWidget(widget)

    row_text = _plugin_row_text(widget, 0)
    assert "load failed" in row_text
```

- [ ] **Step 2: Run the load error regression test to verify it fails**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_shows_load_errors_in_custom_rows -v`
Expected: FAIL because the first row-widget implementation only renders plugin name and metadata, not `load_error`

- [ ] **Step 3: Add an optional error label to the row widget**

```python
# ui/dialogs/plugin_management_tab.py
class _PluginListRow(QWidget):
    def __init__(self, row: dict, source_label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        info_layout = QVBoxLayout()
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(4)

        name_label = QLabel(row["name"], self)
        status = t("plugins_enabled") if row.get("enabled", True) else t("plugins_disabled")
        meta_label = QLabel(f'{row["version"]} · {source_label} · {status}', self)
        info_layout.addWidget(name_label)
        info_layout.addWidget(meta_label)

        plugin_id = row.get("id", "")
        toggle = QCheckBox(t("plugins_enabled"), self)
        toggle.setObjectName(f"pluginToggle:{plugin_id}")
        toggle.setChecked(bool(row.get("enabled", True)))
        toggle.toggled.connect(lambda enabled: self.toggled.emit(plugin_id, enabled))

        load_error = row.get("load_error")
        if load_error:
            error_label = QLabel(load_error, self)
            error_label.setWordWrap(True)
            info_layout.addWidget(error_label)

        layout.addLayout(info_layout, 1)
        layout.addWidget(toggle)
```

- [ ] **Step 4: Run the focused plugin management tests**

Run: `uv run pytest tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_localizes_plugin_sources tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_uses_row_level_toggles tests/test_ui/test_plugin_settings_tab.py::test_plugin_management_tab_shows_load_errors_in_custom_rows -v`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add tests/test_ui/test_plugin_settings_tab.py ui/dialogs/plugin_management_tab.py
git commit -m "补齐插件管理页错误展示"
```

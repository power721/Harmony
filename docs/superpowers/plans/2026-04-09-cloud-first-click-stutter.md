# Cloud First-Click Stutter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the first-click cloud page stutter by moving the initial remote cloud load off the immediate UI-thread navigation path.

**Architecture:** `CloudDriveView` keeps its existing rendering and selection logic, but the first page load is deferred and resolved asynchronously. The implementation adds a small worker/coordinator layer rather than changing playback, download, or cache semantics.

**Tech Stack:** Python, PySide6, pytest, unittest.mock

---

### Task 1: Lock In The Regression With Tests

**Files:**
- Modify: `tests/test_ui/test_cloud_views.py`
- Test: `tests/test_ui/test_cloud_views.py`

- [ ] **Step 1: Write the failing test**

```python
def test_show_event_defers_initial_account_load(...):
    view = CloudDriveView(...)
    view._data_loaded = False

    with patch.object(view, "_load_accounts") as mock_load_accounts:
        view.showEvent(QShowEvent())

    mock_load_accounts.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_cloud_views.py -k "show_event_defers_initial_account_load" -v`
Expected: FAIL because `showEvent()` currently calls `_load_accounts()` inline.

- [ ] **Step 3: Write minimal implementation**

```python
def showEvent(self, event):
    super().showEvent(event)
    if not self._data_loaded:
        self._schedule_initial_load()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_cloud_views.py -k "show_event_defers_initial_account_load" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_cloud_views.py ui/views/cloud/cloud_drive_view.py
git commit -m "修复网盘首次点击卡顿"
```

### Task 2: Implement Async Initial Cloud Load

**Files:**
- Modify: `ui/views/cloud/cloud_drive_view.py`
- Test: `tests/test_ui/test_cloud_views.py`

- [ ] **Step 1: Write the failing test**

```python
def test_show_event_schedules_initial_load_once(...):
    view = CloudDriveView(...)
    view._data_loaded = False

    with patch("ui.views.cloud.cloud_drive_view.QTimer.singleShot") as mock_single_shot:
        view.showEvent(QShowEvent())
        view.showEvent(QShowEvent())

    assert mock_single_shot.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_cloud_views.py -k "show_event_schedules_initial_load_once" -v`
Expected: FAIL because no scheduling guard exists yet.

- [ ] **Step 3: Write minimal implementation**

```python
self._initial_load_scheduled = False

def _schedule_initial_load(self):
    if self._initial_load_scheduled or self._data_loaded:
        return
    self._initial_load_scheduled = True
    QTimer.singleShot(0, self._load_accounts_async)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_cloud_views.py -k "show_event_schedules_initial_load_once" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_cloud_views.py ui/views/cloud/cloud_drive_view.py
git commit -m "异步化网盘初始加载"
```

### Task 3: Verify No Regression In Existing Cloud View Behavior

**Files:**
- Test: `tests/test_ui/test_cloud_views.py`

- [ ] **Step 1: Run focused cloud view tests**

```bash
uv run pytest tests/test_ui/test_cloud_views.py tests/test_ui/test_cloud_drive_view_thread_cleanup.py -v
```

- [ ] **Step 2: Run main-window integration coverage for sidebar/page switching**

```bash
uv run pytest tests/test_ui/test_main_window_components.py tests/test_ui/test_plugin_sidebar_integration.py -k "show_event or cloud" -v
```

- [ ] **Step 3: Review failures and apply minimal fixes only if needed**

```python
# No planned code here; only respond to verified regressions from the commands above.
```

- [ ] **Step 4: Re-run the same commands to verify green**

```bash
uv run pytest tests/test_ui/test_cloud_views.py tests/test_ui/test_cloud_drive_view_thread_cleanup.py -v
uv run pytest tests/test_ui/test_main_window_components.py tests/test_ui/test_plugin_sidebar_integration.py -k "show_event or cloud" -v
```

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_cloud_views.py ui/views/cloud/cloud_drive_view.py
git commit -m "补充网盘首屏加载回归测试"
```

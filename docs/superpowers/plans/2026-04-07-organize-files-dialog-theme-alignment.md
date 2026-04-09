# OrganizeFilesDialog Theme Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align `OrganizeFilesDialog` with the unified dialog theme pattern used by `EditMediaInfoDialog`.

**Architecture:** Keep the dialog's frameless shell and container-level stylesheet, but remove local button/progress/table color rules that duplicate global theme behavior. Drive action buttons through shared `role` properties so the foundation theme stylesheet owns their appearance.

**Tech Stack:** Python, PySide6, pytest-qt, Harmony theme system (`ThemeManager`, `ui/styles.qss`)

---

### Task 1: Lock the desired dialog theme behavior with a regression test

**Files:**
- Modify: `tests/test_ui/test_dialog_action_buttons.py`
- Test: `tests/test_ui/test_dialog_action_buttons.py`

- [ ] **Step 1: Write the failing test**

```python
def test_organize_files_dialog_uses_foundation_action_button_roles(qtbot):
    dialog = OrganizeFilesDialog(
        tracks=[Track(id=1, path="/tmp/song.mp3", title="Song", artist="Artist")],
        file_org_service=Mock(),
        config_manager=Mock(),
    )
    qtbot.addWidget(dialog)

    roles = _buttons_by_role(dialog)

    assert "QPushButton {" not in OrganizeFilesDialog._STYLE_TEMPLATE
    assert "QProgressBar {" not in OrganizeFilesDialog._STYLE_TEMPLATE
    assert len(roles["primary"]) == 1
    assert len(roles["cancel"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ui/test_dialog_action_buttons.py::test_organize_files_dialog_uses_foundation_action_button_roles -v`
Expected: FAIL because `OrganizeFilesDialog` still includes local button/progress styling and its buttons do not yet declare shared `role` properties.

- [ ] **Step 3: Write minimal implementation**

```python
class OrganizeFilesDialog(QDialog):
    _STYLE_TEMPLATE = """
        QWidget#dialogContainer {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QLabel#dialogTitle {
            color: %text%;
            font-size: 15px;
            font-weight: bold;
        }
        QLabel {
            color: %text%;
            font-size: 13px;
        }
    """

    def __init__(...):
        ...
        self.setProperty("shell", True)

    def _setup_ui(self):
        ...
        self.organize_btn.setProperty("role", "primary")
        close_btn.setProperty("role", "cancel")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ui/test_dialog_action_buttons.py::test_organize_files_dialog_uses_foundation_action_button_roles -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_ui/test_dialog_action_buttons.py ui/dialogs/organize_files_dialog.py docs/superpowers/plans/2026-04-07-organize-files-dialog-theme-alignment.md
git commit -m "统一整理文件对话框主题样式"
```

### Task 2: Verify no regression in focused dialog theme coverage

**Files:**
- Test: `tests/test_ui/test_dialog_action_buttons.py`

- [ ] **Step 1: Run focused dialog theme tests**

Run: `uv run pytest tests/test_ui/test_dialog_action_buttons.py -v`
Expected: PASS

- [ ] **Step 2: Commit if verification remains green**

```bash
git add tests/test_ui/test_dialog_action_buttons.py ui/dialogs/organize_files_dialog.py docs/superpowers/plans/2026-04-07-organize-files-dialog-theme-alignment.md
git commit -m "补充整理文件对话框主题回归测试"
```

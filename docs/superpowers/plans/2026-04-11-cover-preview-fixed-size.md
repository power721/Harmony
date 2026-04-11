# Cover Preview Fixed Size Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the shared cover preview dialog always render as a fixed `800x800` window while keeping all current title-bar and closing behavior unchanged.

**Architecture:** Keep the change localized to the shared preview dialog and its test file. Replace content-driven dialog resizing with a fixed shell size, then scale and center the pixmap inside the existing content area so all callers, including QQ plugin views, automatically inherit the new behavior.

**Tech Stack:** Python, PySide6, pytest, shared dialog title-bar helper

---

### Task 1: Lock fixed-size behavior with failing tests

**Files:**
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Replace the size-cap assertion with a fixed-size assertion**

```python
def test_cover_preview_window_is_fixed_at_800_pixels(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)

    pixmap = QPixmap(1600, 1200)
    pixmap.fill(Qt.GlobalColor.blue)
    image_path = tmp_path / "large-cover.png"
    pixmap.save(str(image_path), "PNG")

    dialog = CoverPreviewDialog(str(image_path), title="Large Cover")
    dialog.show()
    qapp.processEvents()

    assert dialog.width() == 800
    assert dialog.height() == 800
```

- [ ] **Step 2: Add a small-image regression test so the dialog still stays fixed**

```python
def test_cover_preview_small_image_still_uses_fixed_800_window(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)

    image_path = tmp_path / "small-cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Small Cover")
    dialog.show()
    qapp.processEvents()

    assert dialog.width() == 800
    assert dialog.height() == 800
```

- [ ] **Step 3: Run the focused test file to verify RED**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: FAIL because `_set_pixmap()` still calls `adjustSize()` and then shrinks the dialog to the content size.

- [ ] **Step 4: Commit the failing-test checkpoint**

```bash
git add tests/test_ui/test_cover_preview_dialog.py
git commit -m "调整封面预览固定尺寸测试"
```

### Task 2: Make the shared preview shell permanently fixed at 800x800

**Files:**
- Modify: `ui/dialogs/cover_preview_dialog.py`
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Keep the dialog shell fixed during initialization**

```python
class CoverPreviewDialog(QDialog):
    MAX_WINDOW_WIDTH = 800
    MAX_WINDOW_HEIGHT = 800

    def __init__(...):
        ...
        self.setMaximumSize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
        self.setMinimumSize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
        self.setFixedSize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
```

- [ ] **Step 2: Remove content-driven resizing from `_set_pixmap()`**

```python
    def _set_pixmap(self, pixmap: QPixmap):
        horizontal_padding = self.CONTENT_MARGINS[0] + self.CONTENT_MARGINS[2]
        max_content_width = self.MAX_WINDOW_WIDTH - horizontal_padding
        max_content_height = self.MAX_WINDOW_HEIGHT - self.MAX_CONTENT_HEIGHT_PADDING
        scaled = pixmap.scaled(
            max(1, max_content_width),
            max(1, max_content_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setText("")
        self._image_label.setPixmap(scaled)
        self._content_frame.setFixedSize(scaled.size())
```

Delete these lines entirely from `_set_pixmap()`:

```python
        self.adjustSize()
        self.setFixedSize(
            min(self.width(), self.MAX_WINDOW_WIDTH),
            min(self.height(), self.MAX_WINDOW_HEIGHT),
        )
```

- [ ] **Step 3: Run the focused preview tests and verify GREEN**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: PASS

- [ ] **Step 4: Commit the implementation**

```bash
git add ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "固定封面预览窗口尺寸"
```

### Task 3: Run regression checks on merged behavior

**Files:**
- Test: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_detail_cover_preview_integration.py`
- Test: `tests/test_ui/test_online_detail_view_actions.py`

- [ ] **Step 1: Run preview and integration regressions**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_online_detail_view_actions.py -v`

Expected: PASS

- [ ] **Step 2: Run lint for the touched files**

Run: `uv run --extra dev ruff check ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py`

Expected: `All checks passed!`

- [ ] **Step 3: Commit if any verification-only adjustments were needed**

```bash
git add ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "整理封面预览固定尺寸验证"
```

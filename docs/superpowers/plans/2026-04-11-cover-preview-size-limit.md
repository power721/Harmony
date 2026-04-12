# Cover Preview Size Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Limit the shared cover preview window to at most `500x500` while preserving outside-click close, `Esc` close, and drag behavior.

**Architecture:** Keep all changes inside `ui/dialogs/cover_preview_dialog.py` and its existing test file. Add a failing test for the size cap first, then update the dialog sizing logic so the dialog itself never exceeds `500x500` and the image still scales within the available content area.

**Tech Stack:** Python, PySide6, pytest, Qt test helpers

---

### Task 1: Lock the preview size limit with a failing test

**Files:**
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Add a failing size-limit test**

```python
def test_cover_preview_window_does_not_exceed_500_pixels(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)

    pixmap = QPixmap(1200, 900)
    pixmap.fill(Qt.GlobalColor.blue)
    image_path = tmp_path / "large-cover.png"
    pixmap.save(str(image_path), "PNG")

    dialog = CoverPreviewDialog(str(image_path), title="Large Cover")
    dialog.show()
    qapp.processEvents()

    assert dialog.width() <= 500
    assert dialog.height() <= 500
```

- [ ] **Step 2: Run the focused dialog tests to verify the new test fails**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: FAIL because the dialog currently starts at `900x700` and the window itself can exceed `500x500`.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_ui/test_cover_preview_dialog.py
git commit -m "添加封面预览尺寸限制测试"
```

### Task 2: Implement the `500x500` window cap in the shared preview dialog

**Files:**
- Modify: `ui/dialogs/cover_preview_dialog.py`
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Replace the large default window size with a hard max size**

```python
class CoverPreviewDialog(QDialog):
    MAX_WINDOW_WIDTH = 500
    MAX_WINDOW_HEIGHT = 500
    OUTER_MARGIN = 24
    CONTENT_PADDING = 0

    def __init__(...):
        ...
        self.setMaximumSize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
        self.resize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
```

- [ ] **Step 2: Scale the image against the window cap and keep the dialog itself within bounds**

```python
    def _set_pixmap(self, pixmap: QPixmap):
        max_content_width = self.MAX_WINDOW_WIDTH - (self.OUTER_MARGIN * 2)
        max_content_height = self.MAX_WINDOW_HEIGHT - (self.OUTER_MARGIN * 2)
        scaled = pixmap.scaled(
            max(1, max_content_width),
            max(1, max_content_height),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setText("")
        self._image_label.setPixmap(scaled)
        self._content_frame.setFixedSize(scaled.size())
        self.adjustSize()
        self.setFixedSize(
            min(self.width(), self.MAX_WINDOW_WIDTH),
            min(self.height(), self.MAX_WINDOW_HEIGHT),
        )
```

- [ ] **Step 3: Keep outside-click close behavior explicit in the tests**

```python
def test_cover_preview_closes_when_clicking_overlay(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Album")
    dialog.show()
    qapp.processEvents()

    assert dialog.isVisible()
    assert dialog._content_frame.geometry().contains(dialog.rect().center()) is False

    QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    qapp.processEvents()

    assert not dialog.isVisible()
```

- [ ] **Step 4: Run the focused dialog tests and verify they pass**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit the implementation**

```bash
git add ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "限制封面预览窗口尺寸"
```

### Task 3: Verify the shared preview behavior on the affected UI paths

**Files:**
- Test: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_detail_cover_preview_integration.py`
- Test: `tests/test_ui/test_online_detail_view_actions.py`

- [ ] **Step 1: Run the affected preview-related tests**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_online_detail_view_actions.py -v`

Expected: PASS

- [ ] **Step 2: Run lint on the touched files**

Run: `uv run ruff check ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py`

Expected: PASS

- [ ] **Step 3: Commit any verification-only cleanup if needed**

```bash
git add ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "修复封面预览尺寸收尾问题"
```

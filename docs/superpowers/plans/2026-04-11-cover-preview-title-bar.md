# Cover Preview Title Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the shared cover preview into an `800x800` themed dialog with a title bar and close button, and remove outside-click close behavior.

**Architecture:** Keep all changes inside `ui/dialogs/cover_preview_dialog.py` and `tests/test_ui/test_cover_preview_dialog.py`. Replace the frameless overlay interaction with the project’s shared title-bar pattern from `ui/dialogs/dialog_title_bar.py`, move drag behavior to the title bar, and update the tests to assert the new chrome and closing rules.

**Tech Stack:** Python, PySide6, pytest, Qt test helpers, existing dialog title bar helper

---

### Task 1: Lock the new title-bar behavior with failing tests

**Files:**
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Replace the outside-click-close expectation with the new behavior tests**

```python
def test_cover_preview_clicking_outside_content_does_not_close(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Album")
    dialog.show()
    qapp.processEvents()

    assert dialog.isVisible()

    QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    qapp.processEvents()

    assert dialog.isVisible()


def test_cover_preview_window_does_not_exceed_800_pixels(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)

    pixmap = QPixmap(1600, 1200)
    pixmap.fill(Qt.GlobalColor.blue)
    image_path = tmp_path / "large-cover.png"
    pixmap.save(str(image_path), "PNG")

    dialog = CoverPreviewDialog(str(image_path), title="Large Cover")
    dialog.show()
    qapp.processEvents()

    assert dialog.width() <= 800
    assert dialog.height() <= 800
```

```python
def test_cover_preview_shows_title_bar_and_close_button(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Album")
    dialog.show()
    qapp.processEvents()

    assert dialog.findChild(QWidget, "dialogTitleBar") is not None
    assert dialog.findChild(QPushButton, "dialogCloseBtn") is not None
```

- [ ] **Step 2: Move the drag test from content dragging to title-bar dragging**

```python
def test_cover_preview_drags_from_title_bar(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Genre")
    dialog.show()
    qapp.processEvents()
    dialog.move(100, 120)
    qapp.processEvents()

    title_bar = dialog.findChild(QWidget, "dialogTitleBar")
    start = title_bar.rect().center()

    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(start),
        QPointF(title_bar.mapToGlobal(start)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(start + QPoint(40, 35)),
        QPointF(title_bar.mapToGlobal(start + QPoint(40, 35))),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(start + QPoint(40, 35)),
        QPointF(title_bar.mapToGlobal(start + QPoint(40, 35))),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    QApplication.sendEvent(title_bar, press)
    QApplication.sendEvent(title_bar, move)
    QApplication.sendEvent(title_bar, release)
    qapp.processEvents()

    assert dialog.pos() != QPoint(100, 120)
```

- [ ] **Step 3: Run the focused dialog tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: FAIL because the dialog still closes on outside click, still caps at `500x500`, and does not yet expose the shared title bar widgets.

- [ ] **Step 4: Commit the failing-test checkpoint**

```bash
git add tests/test_ui/test_cover_preview_dialog.py
git commit -m "调整封面预览标题栏测试"
```

### Task 2: Rebuild the shared preview dialog around the project title bar

**Files:**
- Modify: `ui/dialogs/cover_preview_dialog.py`
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Swap the frameless overlay shell for the shared title-bar layout**

```python
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout


class CoverPreviewDialog(QDialog):
    MAX_WINDOW_WIDTH = 800
    MAX_WINDOW_HEIGHT = 800

    def __init__(...):
        ...
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMaximumSize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
        self.resize(self.MAX_WINDOW_WIDTH, self.MAX_WINDOW_HEIGHT)
```

```python
    def _build_ui(self):
        theme = ThemeManager.instance().current_theme
        self.setStyleSheet(
            f"QDialog {{ background-color: {theme.background}; }}"
            f"QFrame#coverPreviewContent {{ background-color: {theme.background_alt}; border-radius: 12px; }}"
            f"QLabel {{ color: {theme.text_secondary}; background-color: transparent; }}"
        )

        outer = QVBoxLayout(self)
        self._content_layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            outer,
            self.windowTitle(),
            content_margins=(24, 20, 24, 24),
            content_spacing=12,
        )

        self._content_frame = QFrame(self)
        self._content_frame.setObjectName("coverPreviewContent")
        self._content_layout.addWidget(self._content_frame, 1)
```

- [ ] **Step 2: Remove outside-click-close and content dragging**

```python
    def mousePressEvent(self, event):
        super().mousePressEvent(event)
```

Delete `_on_content_press()`, `_on_content_move()`, `_on_content_release()`, and the `_content_frame.mousePressEvent = ...` wiring entirely, because dragging is now provided by the shared title bar helper.

- [ ] **Step 3: Update image sizing for the `800x800` window cap**

```python
    def _set_pixmap(self, pixmap: QPixmap):
        max_content_width = self.MAX_WINDOW_WIDTH - 48
        max_content_height = self.MAX_WINDOW_HEIGHT - 120
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

- [ ] **Step 4: Run the focused dialog tests and verify they pass**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit the implementation**

```bash
git add ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "为封面预览添加标题栏"
```

### Task 3: Verify the shared preview still works on the connected UI paths

**Files:**
- Test: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_detail_cover_preview_integration.py`
- Test: `tests/test_ui/test_online_detail_view_actions.py`

- [ ] **Step 1: Run the affected preview-related regression tests**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_online_detail_view_actions.py -v`

Expected: PASS

- [ ] **Step 2: Run lint on the touched files**

Run: `uv run ruff check ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py`

Expected: PASS

- [ ] **Step 3: Commit any verification-only cleanup if needed**

```bash
git add ui/dialogs/cover_preview_dialog.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "修复封面预览标题栏收尾问题"
```

# Unified Cover Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the split cover-preview implementations with one shared frameless preview dialog, then wire all detail pages to use it.

**Architecture:** Add a single `CoverPreviewDialog` under `ui/dialogs/` that owns local/remote image loading, outside-click close, `Esc` close, and drag-to-move behavior. `AlbumView`, `ArtistView`, `GenreView`, and `OnlineDetailView` should only prepare the source image/title and call the shared preview entrypoint; duplicate preview classes and view-local full-cover loader logic should be removed.

**Tech Stack:** Python, PySide6, pytest, unittest.mock, infrastructure image cache, shared HTTP client

---

### Task 1: Lock the shared preview dialog behavior with failing tests

**Files:**
- Create: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Write the failing dialog behavior tests**

```python
"""Tests for the shared cover preview dialog."""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent, QPixmap
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from system.theme import ThemeManager
from ui.dialogs.cover_preview_dialog import CoverPreviewDialog

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def theme_config():
    class _Config:
        def get(self, *_args, **_kwargs):
            return "dark"

    return _Config()


def _make_png_bytes() -> bytes:
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.blue)
    ba = QByteArray()
    buffer = QBuffer(ba)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(ba)


def test_cover_preview_closes_when_clicking_overlay(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Album")
    dialog.show()
    qapp.processEvents()

    assert dialog.isVisible()

    QTest.mouseClick(dialog, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(5, 5))
    qapp.processEvents()

    assert not dialog.isVisible()


def test_cover_preview_closes_on_escape(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Artist")
    dialog.show()
    qapp.processEvents()

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    qapp.processEvents()

    assert not dialog.isVisible()


def test_cover_preview_drags_from_content(qapp, theme_config, tmp_path):
    ThemeManager.instance(theme_config)
    image_path = tmp_path / "cover.png"
    image_path.write_bytes(_make_png_bytes())

    dialog = CoverPreviewDialog(str(image_path), title="Genre")
    dialog.show()
    qapp.processEvents()
    dialog.move(100, 120)
    qapp.processEvents()

    content = dialog._content_frame
    start = content.rect().center()

    press = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(start),
        QPointF(content.mapToGlobal(start)),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    move = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(start + QPoint(40, 35)),
        QPointF(content.mapToGlobal(start + QPoint(40, 35))),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    release = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(start + QPoint(40, 35)),
        QPointF(content.mapToGlobal(start + QPoint(40, 35))),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )

    QApplication.sendEvent(content, press)
    QApplication.sendEvent(content, move)
    QApplication.sendEvent(content, release)
    qapp.processEvents()

    assert dialog.pos() != QPoint(100, 120)


def test_cover_preview_stops_loader_on_close(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)

    class _FakeLoader:
        def __init__(self):
            self.called = []

        def isRunning(self):
            return True

        def requestInterruption(self):
            self.called.append("requestInterruption")

        def quit(self):
            self.called.append("quit")

        def wait(self, timeout):
            self.called.append(("wait", timeout))
            return True

    monkeypatch.setattr(CoverPreviewDialog, "_is_url", lambda self: True)
    monkeypatch.setattr(CoverPreviewDialog, "_start_remote_load", lambda self: None)

    dialog = CoverPreviewDialog("https://example.com/cover.png", title="Online")
    dialog._loader = _FakeLoader()

    dialog.close()
    qapp.processEvents()

    assert dialog._loader.called == ["requestInterruption", "quit", ("wait", 1000)]
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: FAIL with `ModuleNotFoundError` for `ui.dialogs.cover_preview_dialog` or missing `CoverPreviewDialog`.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_ui/test_cover_preview_dialog.py
git commit -m "添加封面预览对话框测试"
```

### Task 2: Implement the shared frameless cover preview dialog

**Files:**
- Create: `ui/dialogs/cover_preview_dialog.py`
- Modify: `ui/dialogs/__init__.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Write the minimal shared dialog implementation**

```python
"""Shared frameless cover preview dialog."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QVBoxLayout

from infrastructure.cache.image_cache import ImageCache
from infrastructure.network.http_client import HttpClient
from system.i18n import t
from system.theme import ThemeManager

logger = logging.getLogger(__name__)


class CoverPreviewLoader(QThread):
    loaded = Signal(bytes)
    failed = Signal()

    def __init__(self, url: str, headers: dict | None = None):
        super().__init__()
        self._url = url
        self._headers = headers

    def run(self):
        cached = ImageCache.get(self._url)
        if cached:
            self.loaded.emit(cached)
            return

        data = HttpClient().get_content(self._url, headers=self._headers, timeout=10)
        if not data:
            self.failed.emit()
            return

        ImageCache.set(self._url, data)
        self.loaded.emit(data)


class CoverPreviewDialog(QDialog):
    def __init__(self, image_source: str, title: str = "", request_headers: dict | None = None, parent=None):
        super().__init__(parent)
        self._image_source = image_source
        self._request_headers = request_headers
        self._loader = None
        self._drag_pos = None
        self._pixmap = None

        self.setWindowTitle(title or t("cover"))
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setObjectName("coverPreviewDialog")

        self._build_ui()
        self._load_image()

    def _build_ui(self):
        theme = ThemeManager.instance().current_theme
        self.resize(900, 700)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)

        self._content_frame = QFrame(self)
        self._content_frame.setObjectName("coverPreviewContent")
        self._content_frame.setStyleSheet(
            f"QFrame#coverPreviewContent {{ background: {theme.background_alt}; border-radius: 12px; }}"
        )

        content_layout = QVBoxLayout(self._content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._image_label = QLabel(t("loading"))
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self._image_label)

        layout.addWidget(self._content_frame, 1)

    def _is_url(self) -> bool:
        return self._image_source.startswith(("http://", "https://"))

    def _load_image(self):
        if self._is_url():
            self._start_remote_load()
            return

        pixmap = QPixmap(str(Path(self._image_source)))
        if pixmap.isNull():
            self._image_label.setText(t("cover_load_failed"))
            return
        self._set_pixmap(pixmap)

    def _start_remote_load(self):
        self._loader = CoverPreviewLoader(self._image_source, headers=self._request_headers)
        self._loader.loaded.connect(self._on_remote_loaded)
        self._loader.failed.connect(lambda: self._image_label.setText(t("cover_load_failed")))
        self._loader.start()

    def _on_remote_loaded(self, data: bytes):
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self._image_label.setText(t("cover_load_failed"))
            return
        self._set_pixmap(pixmap)

    def _set_pixmap(self, pixmap: QPixmap):
        screen = self.screen()
        available = screen.availableGeometry().size() if screen else self.size()
        scaled = pixmap.scaled(
            max(200, available.width() - 160),
            max(200, available.height() - 160),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmap = scaled
        self._image_label.setPixmap(scaled)
        self._image_label.setText("")
        self._content_frame.setFixedSize(scaled.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self._content_frame.geometry().contains(event.position().toPoint()):
            self.close()
            return
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        if self._loader and self._loader.isRunning():
            self._loader.requestInterruption()
            self._loader.quit()
            self._loader.wait(1000)
        super().closeEvent(event)


def show_cover_preview(parent, image_source: str, title: str = "", request_headers: dict | None = None):
    dialog = CoverPreviewDialog(image_source, title=title, request_headers=request_headers, parent=parent)
    dialog.show()
    return dialog
```

- [ ] **Step 2: Add drag behavior on the content frame and export the helper**

```python
    def _build_ui(self):
        ...
        self._content_frame.mousePressEvent = self._on_content_press
        self._content_frame.mouseMoveEvent = self._on_content_move
        self._content_frame.mouseReleaseEvent = self._on_content_release

    def _on_content_press(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def _on_content_move(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def _on_content_release(self, event):
        self._drag_pos = None
        event.accept()
```

```python
from .cover_preview_dialog import CoverPreviewDialog, show_cover_preview
```

- [ ] **Step 3: Run the shared-dialog tests and make sure they pass**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py -v`

Expected: PASS

- [ ] **Step 4: Commit the shared dialog**

```bash
git add ui/dialogs/cover_preview_dialog.py ui/dialogs/__init__.py tests/test_ui/test_cover_preview_dialog.py
git commit -m "实现统一封面预览对话框"
```

### Task 3: Switch album, artist, and genre detail views to the shared preview

**Files:**
- Modify: `ui/views/album_view.py`
- Modify: `ui/views/artist_view.py`
- Modify: `ui/views/genre_view.py`
- Create: `tests/test_ui/test_detail_cover_preview_integration.py`
- Modify: `tests/test_ui/test_genre_view.py`
- Test: `tests/test_ui/test_detail_cover_preview_integration.py`
- Test: `tests/test_ui/test_genre_view.py`

- [ ] **Step 1: Write failing integration tests for the three local detail views**

```python
"""Integration tests for local detail views using the shared cover preview."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

import ui.views.album_view as album_module
import ui.views.artist_view as artist_module
import ui.views.genre_view as genre_module
from system.theme import ThemeManager
from ui.views.album_view import AlbumView
from ui.views.artist_view import ArtistView
from ui.views.genre_view import GenreView

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def reset_theme_singleton():
    ThemeManager._instance = None
    yield
    ThemeManager._instance = None


@pytest.fixture
def theme_config():
    config = Mock()
    config.get.return_value = "dark"
    return config


def test_album_view_cover_click_uses_shared_preview(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)
    calls = []
    monkeypatch.setattr(
        album_module,
        "show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = AlbumView(library_service=Mock())
    view._album = SimpleNamespace(display_name="Album A")
    view._current_cover_path = "/tmp/album-cover.png"

    view._on_cover_clicked()

    assert calls == [(view, "/tmp/album-cover.png", "Album A", None)]


def test_artist_view_cover_click_uses_shared_preview(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)
    calls = []
    monkeypatch.setattr(
        artist_module,
        "show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = ArtistView(library_service=Mock())
    view._artist = SimpleNamespace(display_name="Artist A")
    view._current_cover_path = "/tmp/artist-cover.png"

    view._on_cover_clicked()

    assert calls == [(view, "/tmp/artist-cover.png", "Artist A", None)]


def test_genre_view_cover_click_uses_shared_preview(qapp, theme_config, monkeypatch):
    ThemeManager.instance(theme_config)
    calls = []
    monkeypatch.setattr(
        genre_module,
        "show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = GenreView(library_service=Mock())
    view._genre = SimpleNamespace(display_name="Genre A")
    view._current_cover_path = "/tmp/genre-cover.png"

    view._on_cover_clicked()

    assert calls == [(view, "/tmp/genre-cover.png", "Genre A", None)]
```

```python
def test_genre_view_cover_is_clickable(qapp, mock_theme_config):
    ThemeManager.instance(mock_theme_config)

    view = GenreView(library_service=Mock())

    assert view._cover_label.cursor().shape() == Qt.CursorShape.PointingHandCursor
```

- [ ] **Step 2: Run the local-view preview tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_genre_view.py -v`

Expected: FAIL because `GenreView` has no `_on_cover_clicked()`, and `AlbumView` / `ArtistView` still instantiate dedicated dialog classes.

- [ ] **Step 3: Replace the local dialog classes with the shared preview helper**

```python
from ui.dialogs.cover_preview_dialog import show_cover_preview


def _on_cover_clicked(self):
    """Handle cover art click with the shared frameless preview."""
    if not self._current_cover_path:
        return

    title = self._album.display_name if self._album else ""
    self._cover_preview_dialog = show_cover_preview(
        self,
        self._current_cover_path,
        title=title,
    )
```

```python
from ui.dialogs.cover_preview_dialog import show_cover_preview


def _on_cover_clicked(self):
    """Handle artist cover click with the shared frameless preview."""
    if not self._current_cover_path:
        return

    title = self._artist.display_name if self._artist else ""
    self._cover_preview_dialog = show_cover_preview(
        self,
        self._current_cover_path,
        title=title,
    )
```

```python
from PySide6.QtGui import QCursor, QMouseEvent
from ui.dialogs.cover_preview_dialog import show_cover_preview


class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


def _create_header(self) -> QWidget:
    ...
    self._cover_label = ClickableLabel()
    self._cover_label.clicked.connect(self._on_cover_clicked)
    ...


def _on_cover_clicked(self):
    """Handle genre cover click with the shared frameless preview."""
    if not self._current_cover_path:
        return

    title = self._genre.display_name if self._genre else ""
    self._cover_preview_dialog = show_cover_preview(
        self,
        self._current_cover_path,
        title=title,
    )
```

Delete the trailing `AlbumCoverDialog` class from `ui/views/album_view.py` and the trailing `ArtistCoverDialog` class from `ui/views/artist_view.py` entirely after switching the click handlers.

- [ ] **Step 4: Run the local-view test set and make sure it passes**

Run: `uv run pytest tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_genre_view.py -v`

Expected: PASS

- [ ] **Step 5: Commit the local-view migration**

```bash
git add ui/views/album_view.py ui/views/artist_view.py ui/views/genre_view.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_genre_view.py
git commit -m "统一本地详情页封面预览"
```

### Task 4: Switch OnlineDetailView to the shared preview and remove duplicate loader logic

**Files:**
- Modify: `plugins/builtin/qqmusic/lib/online_detail_view.py`
- Modify: `tests/test_ui/test_online_detail_view_actions.py`
- Delete: `tests/test_ui/test_online_detail_view_thread_cleanup.py`
- Modify: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_online_detail_view_actions.py`
- Test: `tests/test_ui/test_cover_preview_dialog.py`

- [ ] **Step 1: Write failing tests for the shared-preview integration in OnlineDetailView**

```python
def test_online_detail_view_cover_click_uses_shared_preview(monkeypatch):
    calls = []

    monkeypatch.setattr(
        "plugins.builtin.qqmusic.lib.online_detail_view.show_cover_preview",
        lambda parent, image_source, title="", request_headers=None: calls.append(
            (parent, image_source, title, request_headers)
        ),
    )

    view = OnlineDetailView.__new__(OnlineDetailView)
    view._cover_url = "https://y.gtimg.cn/music/photo_new/T002R300x300M000albummid.jpg"
    view._name_label = SimpleNamespace(text=lambda: "Album Name")

    OnlineDetailView._on_cover_clicked(view, None)

    assert calls == [
        (
            view,
            "https://y.gtimg.cn/music/photo_new/T002R800x800M000albummid.jpg",
            "Album Name",
            None,
        )
    ]
```

```python
def test_cover_preview_close_event_ignores_missing_loader(qapp, theme_config):
    ThemeManager.instance(theme_config)

    dialog = CoverPreviewDialog("/tmp/missing-cover.png", title="Any")
    dialog._loader = None
    dialog.close()
    qapp.processEvents()

    assert not dialog.isVisible()
```

- [ ] **Step 2: Run the online-detail preview tests to verify they fail**

Run: `uv run pytest tests/test_ui/test_online_detail_view_actions.py tests/test_ui/test_cover_preview_dialog.py -v`

Expected: FAIL because `OnlineDetailView` still calls `_show_cover_dialog_async()` and the old thread-cleanup test still assumes `_stop_full_cover_loader()` exists.

- [ ] **Step 3: Replace the dedicated full-cover dialog path with the shared helper**

```python
from ui.dialogs.cover_preview_dialog import show_cover_preview


def _on_cover_clicked(self, event):
    """Handle cover click with the shared frameless preview."""
    if not self._cover_url:
        return

    cover_url = self._cover_url
    if "y.gtimg.cn" in cover_url and "R300x300" in cover_url:
        cover_url = cover_url.replace("R300x300", "R800x800")

    self._cover_preview_dialog = show_cover_preview(
        self,
        cover_url,
        title=self._name_label.text() or t("cover"),
    )
```

Delete `_show_cover_dialog_async()` and `_stop_full_cover_loader()` from `plugins/builtin/qqmusic/lib/online_detail_view.py` once `_on_cover_clicked()` is using the shared helper.

Remove `tests/test_ui/test_online_detail_view_thread_cleanup.py` entirely, because loader cleanup now belongs to the shared dialog test file.

- [ ] **Step 4: Run the focused online-detail and dialog tests**

Run: `uv run pytest tests/test_ui/test_online_detail_view_actions.py tests/test_ui/test_cover_preview_dialog.py -v`

Expected: PASS

- [ ] **Step 5: Commit the online-detail migration**

```bash
git add plugins/builtin/qqmusic/lib/online_detail_view.py tests/test_ui/test_online_detail_view_actions.py tests/test_ui/test_cover_preview_dialog.py
git rm tests/test_ui/test_online_detail_view_thread_cleanup.py
git commit -m "统一在线详情页封面预览"
```

### Task 5: Run the verification sweep for all affected preview paths

**Files:**
- Test: `tests/test_ui/test_cover_preview_dialog.py`
- Test: `tests/test_ui/test_detail_cover_preview_integration.py`
- Test: `tests/test_ui/test_genre_view.py`
- Test: `tests/test_ui/test_online_detail_view_actions.py`

- [ ] **Step 1: Run the full affected UI test set**

Run: `uv run pytest tests/test_ui/test_cover_preview_dialog.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_genre_view.py tests/test_ui/test_online_detail_view_actions.py -v`

Expected: PASS

- [ ] **Step 2: Run lint on the touched files**

Run: `uv run ruff check ui/dialogs/cover_preview_dialog.py ui/views/album_view.py ui/views/artist_view.py ui/views/genre_view.py plugins/builtin/qqmusic/lib/online_detail_view.py tests/test_ui/test_cover_preview_dialog.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_genre_view.py tests/test_ui/test_online_detail_view_actions.py`

Expected: PASS

- [ ] **Step 3: Commit any verification-only fixes if needed**

```bash
git add ui/dialogs/cover_preview_dialog.py ui/views/album_view.py ui/views/artist_view.py ui/views/genre_view.py plugins/builtin/qqmusic/lib/online_detail_view.py tests/test_ui/test_cover_preview_dialog.py tests/test_ui/test_detail_cover_preview_integration.py tests/test_ui/test_genre_view.py tests/test_ui/test_online_detail_view_actions.py
git commit -m "修复封面预览收尾问题"
```

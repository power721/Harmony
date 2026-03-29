# Spotify-style Title Bar with Dynamic Cover Color — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace native OS title bar with a custom Spotify-style frameless title bar that adapts to themes and dynamically tints from album cover colors.

**Architecture:** New `TitleBar` widget in `ui/widgets/`, new `ColorExtractor` in `services/metadata/`. MainWindow gets `FramelessWindowHint` and the title bar is inserted into its layout. Cover color flows: track_changed → cover path → ColorExtractor (QThread) → TitleBar gradient.

**Tech Stack:** PySide6, QImage pixel sampling, QPropertyAnimation for smooth color transitions

---

### Task 1: ColorExtractor Service

**Files:**
- Create: `services/metadata/color_extractor.py`
- Modify: `services/metadata/__init__.py`
- Test: `tests/test_color_extractor.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_color_extractor.py
"""Tests for ColorExtractor."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QObject, Signal


def test_extract_dominant_color_red_image():
    """Should extract dominant red from a solid red image."""
    # Create a 10x10 solid red QImage
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(QColor(255, 0, 0))

    from services.metadata.color_extractor import extract_dominant_color
    result = extract_dominant_color(img)
    assert result is not None
    assert result.red() == 255
    assert result.green() < 100
    assert result.blue() < 100


def test_extract_dominant_color_dark_image():
    """Should handle dark images gracefully."""
    img = QImage(10, 10, QImage.Format_RGB32)
    img.fill(QColor(18, 18, 18))

    from services.metadata.color_extractor import extract_dominant_color
    result = extract_dominant_color(img)
    assert result is not None


def test_extract_dominant_color_null_image():
    """Should return None for null QImage."""
    img = QImage()

    from services.metadata.color_extractor import extract_dominant_color
    result = extract_dominant_color(img)
    assert result is None


def test_extract_from_file_nonexistent():
    """Should return None for nonexistent file."""
    from services.metadata.color_extractor import extract_from_file
    result = extract_from_file("/nonexistent/path/image.jpg")
    assert result is None


def test_color_worker_emits_result():
    """ColorWorker should emit color_extracted signal when done."""
    from services.metadata.color_extractor import ColorWorker
    import tempfile
    from PIL import Image as PILImage

    # Create a temp image
    img = PILImage.new('RGB', (10, 10), (255, 0, 0))
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
        img.save(f.name)
        tmp_path = f.name

    receiver = QObject()
    received = []
    receiver.color_received = Signal(object)
    receiver.color_received.connect(lambda c: received.append(c))

    worker = ColorWorker(tmp_path, receiver.color_received)
    worker.run()

    assert len(received) == 1
    assert received[0] is not None
    assert isinstance(received[0], QColor)

    Path(tmp_path).unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_color_extractor.py -v`
Expected: FAIL (import errors)

- [ ] **Step 3: Write the ColorExtractor implementation**

```python
# services/metadata/color_extractor.py
"""
Extract dominant color from images for dynamic theming.

Uses pixel sampling with frequency-based color clustering.
Runs in background threads to avoid blocking the UI.
"""
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtGui import QImage, QColor
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


def extract_dominant_color(image: QImage) -> Optional[QColor]:
    """Extract the dominant color from a QImage.

    Samples pixels across the image, quantizes them into buckets,
    and returns the most frequent color bucket's average.

    Args:
        image: QImage to analyze

    Returns:
        Dominant QColor, or None if image is null
    """
    if image.isNull():
        return None

    # Convert to Format_RGB32 for consistent pixel access
    converted = image.convertToFormat(QImage.Format_RGB32)
    width = converted.width()
    height = converted.height()

    if width == 0 or height == 0:
        return None

    # Sample pixels (every Nth pixel to keep it fast)
    step = max(1, min(width, height) // 20)
    buckets: dict[tuple[int, int, int], list[int]] = {}

    for y in range(0, height, step):
        for x in range(0, width, step):
            pixel = converted.pixel(x, y)
            r = (pixel >> 16) & 0xFF
            g = (pixel >> 8) & 0xFF
            b = pixel & 0xFF

            # Quantize to reduce color space (divide by 32, round)
            key = (r // 32 * 32, g // 32 * 32, b // 32 * 32)
            if key not in buckets:
                buckets[key] = [0, 0, 0, 0]
            buckets[key][0] += r
            buckets[key][1] += g
            buckets[key][2] += b
            buckets[key][3] += 1

    if not buckets:
        return None

    # Find the most frequent bucket
    best_key = max(buckets, key=lambda k: buckets[k][3])
    count = buckets[best_key][3]
    avg_r = buckets[best_key][0] // count
    avg_g = buckets[best_key][1] // count
    avg_b = buckets[best_key][2] // count

    return QColor(avg_r, avg_g, avg_b)


def extract_from_file(path: str) -> Optional[QColor]:
    """Extract dominant color from an image file.

    Args:
        path: File path to the image

    Returns:
        Dominant QColor, or None on failure
    """
    file_path = Path(path)
    if not file_path.exists():
        logger.debug(f"[ColorExtractor] File not found: {path}")
        return None

    image = QImage(str(file_path))
    if image.isNull():
        logger.debug(f"[ColorExtractor] Failed to load image: {path}")
        return None

    return extract_dominant_color(image)


class ColorWorker:
    """Runnable that extracts color from an image file and emits via signal.

    Designed to run in QThreadPool.
    """

    def __init__(self, image_path: str, result_signal: Signal):
        self.image_path = image_path
        self.result_signal = result_signal

    def run(self):
        """Extract color and emit result."""
        try:
            color = extract_from_file(self.image_path)
            self.result_signal.emit(color)
        except Exception as e:
            logger.error(f"[ColorExtractor] Error extracting color: {e}")
            self.result_signal.emit(None)
```

- [ ] **Step 4: Update `services/metadata/__init__.py`**

Add at the end of `services/metadata/__init__.py`:

```python
from .color_extractor import extract_dominant_color, extract_from_file, ColorWorker
```

And add `'extract_dominant_color', 'extract_from_file', 'ColorWorker'` to `__all__`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_color_extractor.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add services/metadata/color_extractor.py services/metadata/__init__.py tests/test_color_extractor.py
git commit -m "feat: add ColorExtractor service for dominant color extraction"
```

---

### Task 2: TitleBar Widget (Static — Theme-aware, No Dynamic Color Yet)

**Files:**
- Create: `ui/widgets/title_bar.py`
- Test: `tests/test_title_bar.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_title_bar.py
"""Tests for TitleBar widget."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock, PropertyMock


def test_title_bar_creation(qtbot):
    """TitleBar should create with all child widgets."""
    from PySide6.QtWidgets import QMainWindow
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    assert bar.height() == 44
    # Verify child widgets exist
    assert bar._title_label is not None
    assert bar._btn_min is not None
    assert bar._btn_max is not None
    assert bar._btn_close is not None
    assert bar._btn_close.objectName() == "closeBtn"


def test_toggle_maximize(qtbot):
    """Double-clicking should toggle maximize."""
    from PySide6.QtWidgets import QMainWindow
    from PySide6.QtCore import Qt
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    window.resize(400, 300)
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    # Not maximized initially
    assert not window.isMaximized()

    # Simulate double-click
    bar.mouseDoubleClickEvent(
        MagicMock(button=Qt.LeftButton)
    )
    assert window.isMaximized()

    # Double-click again to restore
    bar.mouseDoubleClickEvent(
        MagicMock(button=Qt.LeftButton)
    )
    assert not window.isMaximized()


def test_close_button(qtbot):
    """Close button should trigger window.close()."""
    from PySide6.QtWidgets import QMainWindow
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    with patch.object(window, 'close') as mock_close:
        bar._btn_close.click()
        mock_close.assert_called_once()


def test_minimize_button(qtbot):
    """Minimize button should trigger showMinimized."""
    from PySide6.QtWidgets import QMainWindow
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    with patch.object(window, 'showMinimized') as mock_min:
        bar._btn_min.click()
        mock_min.assert_called_once()


def test_set_track_title(qtbot):
    """set_track_title should update the title label."""
    from PySide6.QtWidgets import QMainWindow
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    bar.set_track_title("Bohemian Rhapsody", "Queen")
    assert "Bohemian Rhapsody" in bar._title_label.text()
    assert "Queen" in bar._title_label.text()


def test_clear_track_title(qtbot):
    """clear_track_title should restore default title."""
    from PySide6.QtWidgets import QMainWindow
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    bar.set_track_title("Song", "Artist")
    bar.clear_track_title()
    assert bar._title_label.text() == "Harmony"


def test_set_accent_color(qtbot):
    """set_accent_color should update the background."""
    from PySide6.QtWidgets import QMainWindow
    from PySide6.QtGui import QColor
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    bar.set_accent_color(QColor(100, 200, 50))
    assert bar._accent_color is not None
    assert bar._accent_color.red() == 100


def test_clear_accent_color(qtbot):
    """clear_accent_color should reset to theme bg."""
    from PySide6.QtWidgets import QMainWindow
    from PySide6.QtGui import QColor
    from ui.widgets.title_bar import TitleBar

    window = QMainWindow()
    bar = TitleBar(window)
    qtbot.addWidget(bar)

    bar.set_accent_color(QColor(100, 200, 50))
    bar.clear_accent_color()
    assert bar._accent_color is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_title_bar.py -v`
Expected: FAIL (import errors)

- [ ] **Step 3: Write the TitleBar implementation**

```python
# ui/widgets/title_bar.py
"""
Spotify-style custom title bar for Harmony.

Features:
- Mac-style decorative traffic lights
- Windows-style window controls (minimize, maximize, close)
- Drag-to-move
- Double-click to toggle maximize
- Theme-aware via ThemeManager token system
- Dynamic accent color from album cover (gradient blend)
"""
import logging

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPalette, QPainter, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QApplication,
    QSizeGrip,
)
from PySide6.QtGui import QPainterPath

from system.theme import ThemeManager

logger = logging.getLogger(__name__)


class TitleBar(QWidget):
    """Custom Spotify-style title bar widget."""

    # Signal emitted when accent color should be extracted (track changed)
    cover_color_requested = Signal(str)  # cover_path

    _STYLE_TEMPLATE = """
        QWidget#titleBar {
            background-color: %background%;
        }
        QPushButton#winBtn {
            border: none;
            color: %text%;
            background: transparent;
            width: 36px;
            height: 28px;
            border-radius: 6px;
            font-size: 14px;
        }
        QPushButton#winBtn:hover {
            background-color: %background_hover%;
        }
        QPushButton#closeBtn:hover {
            background-color: #e81123;
            color: white;
        }
        QLabel#titleLabel {
            color: %text%;
            font-size: 14px;
            font-weight: bold;
        }
        QLabel#trackLabel {
            color: %text_secondary%;
            font-size: 13px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("titleBar")
        self.setFixedHeight(44)

        self._accent_color: QColor | None = None
        self._default_title = "Harmony"
        self._drag_pos = None

        self._setup_ui()
        self._apply_style()

        # Register for theme changes
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Create child widgets and layout."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 6, 0)
        layout.setSpacing(0)

        # === Mac-style decorative traffic lights ===
        mac_container = QWidget()
        mac_container.setFixedWidth(60)
        mac_layout = QHBoxLayout(mac_container)
        mac_layout.setContentsMargins(0, 0, 0, 0)
        mac_layout.setSpacing(8)
        mac_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        for color in ["#ff5f57", "#febc2e", "#28c840"]:
            dot = QLabel()
            dot.setFixedSize(12, 12)
            dot.setStyleSheet(f"""
                QLabel {{
                    background-color: {color};
                    border-radius: 6px;
                }}
            """)
            mac_layout.addWidget(dot)

        layout.addWidget(mac_container)

        # === Title (center) ===
        self._title_label = QLabel(self._default_title)
        self._title_label.setObjectName("titleLabel")
        layout.addWidget(self._title_label)

        layout.addStretch()

        # === Windows-style controls (right) ===
        self._btn_min = QPushButton("—")
        self._btn_min.setObjectName("winBtn")
        self._btn_min.clicked.connect(lambda: self.window().showMinimized() if self.window() else None)

        self._btn_max = QPushButton("□")
        self._btn_max.setObjectName("winBtn")
        self._btn_max.clicked.connect(self._toggle_maximize)

        self._btn_close = QPushButton("✕")
        self._btn_close.setObjectName("closeBtn")
        self._btn_close.clicked.connect(lambda: self.window().close() if self.window() else None)

        for btn in (self._btn_min, self._btn_max, self._btn_close):
            btn.setFixedSize(36, 28)
            layout.addWidget(btn)

    def _toggle_maximize(self):
        """Toggle maximize/restore."""
        win = self.window()
        if win:
            if win.isMaximized():
                win.showNormal()
            else:
                win.showMaximized()

    def _apply_style(self):
        """Apply themed stylesheet."""
        theme = ThemeManager.instance()
        style = theme.get_qss(self._STYLE_TEMPLATE)
        self.setStyleSheet(style)

    def refresh_theme(self):
        """Called by ThemeManager on theme change."""
        self._apply_style()
        self.update()

    # === Track title display ===

    def set_track_title(self, title: str, artist: str):
        """Display track info in the title bar."""
        text = f"{title} — {artist}" if artist else title
        self._title_label.setText(text)
        self._title_label.setObjectName("trackLabel")
        # Re-apply to pick up trackLabel style
        style = self._title_label.style()
        if style:
            style.unpolish(self._title_label)
            style.polish(self._title_label)

    def clear_track_title(self):
        """Restore default 'Harmony' title."""
        self._title_label.setText(self._default_title)
        self._title_label.setObjectName("titleLabel")
        style = self._title_label.style()
        if style:
            style.unpolish(self._title_label)
            style.polish(self._title_label)

    # === Dynamic accent color ===

    def set_accent_color(self, color: QColor):
        """Set accent color from album cover. Triggers animated gradient update."""
        self._accent_color = color
        self.update()

    def clear_accent_color(self):
        """Clear accent color, revert to theme background."""
        self._accent_color = None
        self.update()

    def paintEvent(self, event):
        """Paint gradient background when accent color is active."""
        if self._accent_color is None:
            # Use default themed background
            return super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Get theme background
        theme = ThemeManager.instance()
        bg_color = QColor(theme.current_theme.background)

        # Blend: 40% accent + 60% theme background
        blended = QColor(
            int(self._accent_color.red() * 0.4 + bg_color.red() * 0.6),
            int(self._accent_color.green() * 0.4 + bg_color.green() * 0.6),
            int(self._accent_color.blue() * 0.4 + bg_color.blue() * 0.6),
        )

        # Gradient: blended at top → theme bg at bottom
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, blended)
        gradient.setColorAt(1.0, bg_color)

        painter.fillRect(self.rect(), gradient)
        painter.end()

    # === Drag to move ===

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            win = self.window()
            if win:
                delta = event.globalPosition().toPoint() - self._drag_pos
                win.move(win.pos() + delta)
                self._drag_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._toggle_maximize()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_title_bar.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add ui/widgets/title_bar.py tests/test_title_bar.py
git commit -m "feat: add Spotify-style TitleBar widget with theme support"
```

---

### Task 3: Integrate TitleBar into MainWindow

**Files:**
- Modify: `ui/windows/main_window.py`

- [ ] **Step 1: Add imports at top of `main_window.py`**

After the existing imports (around line 63), add:

```python
from ui.widgets.title_bar import TitleBar
```

- [ ] **Step 2: Set frameless window flag in `__init__`**

In `MainWindow.__init__`, after `self._setup_ui()` call (line 301), add frameless flag. Actually, it must be set before `_setup_ui()` since layout depends on it. Insert **before** `self._setup_ui()` (around line 300):

```python
# Frameless window with custom title bar
self.setWindowFlags(Qt.FramelessWindowHint)
```

- [ ] **Step 3: Insert TitleBar into layout in `_setup_ui`**

In `_setup_ui()`, right after creating the `main_layout` (after line 325 `main_layout.setSpacing(0)`), add:

```python
        # Custom title bar
        self._title_bar = TitleBar(self)
        main_layout.addWidget(self._title_bar)
```

- [ ] **Step 4: Update `_on_track_changed` to use title bar**

In `_on_track_changed` (around line 1101-1102), after setting `self._current_track_title`, add title bar update and cover color extraction:

Replace the lines:
```python
        # Save current track title for window title update
        self._current_track_title = f"{title} - {artist}" if artist else title
```

With:
```python
        # Update title bar with track info
        if title:
            self._title_bar.set_track_title(title, artist)
            self._extract_cover_color(title, artist, path, track_dict)
        else:
            self._title_bar.clear_track_title()
            self._title_bar.clear_accent_color()

        # Save current track title for backward compat
        self._current_track_title = f"{title} - {artist}" if artist else title
```

- [ ] **Step 5: Add `_extract_cover_color` method**

Add this method to MainWindow (after `_on_playback_state_changed`, around line 1122):

```python
    def _extract_cover_color(self, title: str, artist: str, path: str, track_dict: dict):
        """Extract dominant color from album cover and apply to title bar."""
        from services.metadata.color_extractor import extract_from_file

        # Get cover path
        cover_path = None
        try:
            cover_path = self._player.get_track_cover(
                path, title, artist,
                track_dict.get("album", ""),
                skip_online=track_dict.get("needs_download", False) or (track_dict.get("is_cloud", False) and not path)
            )
            # Fallback: try album cover
            if not cover_path:
                album = track_dict.get("album", "")
                if album and artist:
                    cover_path = self._get_album_cover(album, artist)
        except Exception as e:
            logger.debug(f"[MainWindow] Error getting cover for color extraction: {e}")

        if cover_path:
            from PySide6.QtCore import QThreadPool
            from services.metadata.color_extractor import ColorWorker
            worker = ColorWorker(cover_path, self._title_bar.set_accent_color)
            QThreadPool.globalInstance().start(worker)
        else:
            self._title_bar.clear_accent_color()
```

- [ ] **Step 6: Add `_get_album_cover` helper (same pattern as PlayerControls)**

Add near the `_extract_cover_color` method:

```python
    def _get_album_cover(self, album: str, artist: str) -> str | None:
        """Get cover from albums table via LibraryService."""
        from pathlib import Path
        try:
            album_obj = self._library_service.get_album_by_name(album, artist)
            if album_obj and album_obj.cover_path:
                if Path(album_obj.cover_path).exists():
                    return album_obj.cover_path
        except Exception as e:
            logger.debug(f"[MainWindow] Error getting album cover: {e}")
        return None
```

- [ ] **Step 7: Update `_on_playback_state_changed` to update title bar**

In `_on_playback_state_changed`, add title bar clear on pause/stop. Replace:

```python
        elif state == "paused":
            # Paused - restore original title
            if self._original_title:
                self.setWindowTitle(self._original_title)
```

With:

```python
        elif state in ("paused", "stopped"):
            # Paused/stopped - restore original title
            self._title_bar.clear_track_title()
            self._title_bar.clear_accent_color()
            if self._original_title:
                self.setWindowTitle(self._original_title)
```

- [ ] **Step 8: Update `_refresh_ui_texts` to include title bar**

In `_refresh_ui_texts` (around line 849), add after the setWindowTitle line:

```python
        self._title_bar.clear_track_title()
```

- [ ] **Step 9: Run the app to verify visually**

Run: `uv run python main.py`
Expected: Window opens with custom title bar, traffic lights on left, controls on right, draggable, double-click maximizes

- [ ] **Step 10: Commit**

```bash
git add ui/windows/main_window.py
git commit -m "feat: integrate TitleBar into MainWindow with frameless window"
```

---

### Task 4: Add Window Resize Grip

**Files:**
- Modify: `ui/windows/main_window.py`

- [ ] **Step 1: Add resize grip to MainWindow**

In `_setup_ui()`, after adding the title bar and before creating the content_widget, add a resize grip:

Actually, the resize grip needs to be on the central widget or as a child of the main window. The simplest approach for frameless windows is to handle `resizeEvent` with edge detection. But a simpler Qt-native approach is to add a `QSizeGrip`.

In `_setup_ui()`, after `main_layout.addWidget(self._player_controls)` (around line 419), add:

```python
        # Resize grip for frameless window
        self._resize_grip = QSizeGrip(self)
        self._resize_grip.setFixedSize(16, 16)
        self._resize_grip.setStyleSheet("background: transparent;")
```

- [ ] **Step 2: Override `resizeEvent` to position the grip**

Add to MainWindow:

```python
    def resizeEvent(self, event):
        """Position resize grip at bottom-right corner."""
        super().resizeEvent(event)
        if hasattr(self, '_resize_grip') and self._resize_grip:
            self._resize_grip.move(self.width() - 16, self.height() - 16)
```

- [ ] **Step 3: Run the app and verify resize works**

Run: `uv run python main.py`
Expected: Can resize window by dragging bottom-right corner

- [ ] **Step 4: Commit**

```bash
git add ui/windows/main_window.py
git commit -m "feat: add resize grip for frameless window"
```

---

### Task 5: Run All Tests and Final Verification

- [ ] **Step 1: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Manual smoke test**

Run: `uv run python main.py`

Verify:
- [ ] Custom title bar visible with "Harmony" text
- [ ] Mac-style traffic lights on left (red/yellow/green dots)
- [ ] Windows-style buttons on right (—, □, ✕)
- [ ] Close button has red hover
- [ ] Drag title bar to move window
- [ ] Double-click title bar to maximize/restore
- [ ] Minimize button works
- [ ] Close button works
- [ ] Resize via bottom-right grip works
- [ ] Theme switching updates title bar colors
- [ ] Playing a track shows track title and tints background
- [ ] Pausing restores "Harmony" default

- [ ] **Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: title bar integration fixes"
```

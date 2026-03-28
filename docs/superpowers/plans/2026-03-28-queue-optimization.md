# Queue Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite queue_view.py to use QListView + QAbstractListModel + QStyledItemDelegate with QThreadPool cover loading and QPixmapCache, eliminating per-item setStyleSheet and threading overhead.

**Architecture:** Replace QListWidget+QWidget items with QListView+Model+Delegate. Add CoverPixmapCache (wraps QPixmapCache). Cover decode runs in QThreadPool workers, QPixmap conversion on UI thread. Theme styling via QProperty selectors in global QSS.

**Tech Stack:** PySide6 (QAbstractListModel, QStyledItemDelegate, QListView, QRunnable, QThreadPool, QPixmapCache), Python hashlib

---

### Task 1: CoverPixmapCache

**Files:**
- Create: `infrastructure/cache/pixmap_cache.py`
- Test: `tests/test_pixmap_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pixmap_cache.py
"""Tests for CoverPixmapCache."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from infrastructure.cache.pixmap_cache import CoverPixmapCache


def test_cache_key_generation():
    """Cache key should be deterministic."""
    k1 = CoverPixmapCache.make_key("The Beatles", "Abbey Road")
    k2 = CoverPixmapCache.make_key("The Beatles", "Abbey Road")
    k3 = CoverPixmapCache.make_key("Other", "Album")
    assert isinstance(k1, str)
    assert len(k1) == 32  # MD5 hex
    assert k1 == k2
    assert k1 != k3


def test_cache_key_from_path():
    """Cache key from file path."""
    k1 = CoverPixmapCache.make_key_from_path("/music/cover.jpg")
    k2 = CoverPixmapCache.make_key_from_path("/music/cover.jpg")
    assert k1 == k2
    assert isinstance(k1, str)


def test_get_set_roundtrip():
    """Put and get a pixmap."""
    app_mock = MagicMock()
    with patch('infrastructure.cache.pixmap_cache.QApplication', return_value=app_mock):
        with patch('PySide6.QtGui.QPixmapCache.setCacheLimit'):
            CoverPixmapCache.initialize()

            pixmap_mock = MagicMock()
            pixmap_mock.isNull.return_value = False

            with patch('PySide6.QtGui.QPixmapCache.insert', return_value=True) as mock_insert:
                with patch('PySide6.QtGui.QPixmapCache.find', return_value=None):
                    # Cache miss
                    assert CoverPixmapCache.get("test_key") is None

                with patch('PySide6.QtGui.QPixmapCache.find', return_value=pixmap_mock):
                    # Cache hit
                    result = CoverPixmapCache.get("test_key")
                    assert result is pixmap_mock
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pixmap_cache.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Write minimal implementation**

```python
# infrastructure/cache/pixmap_cache.py
"""In-memory pixmap cache wrapping QPixmapCache for cover art."""
import hashlib
import logging

from PySide6.QtGui import QPixmap, QPixmapCache
from PySide6.QtWidgets import QApplication

logger = logging.getLogger(__name__)


class CoverPixmapCache:
    """Wraps QPixmapCache with cover-specific key generation."""

    _initialized = False

    @classmethod
    def initialize(cls):
        """Set cache limit (128MB)."""
        if not cls._initialized:
            QPixmapCache.setCacheLimit(131072)  # 128MB in KB
            cls._initialized = True

    @classmethod
    def make_key(cls, artist: str, album: str) -> str:
        """Generate cache key from artist + album."""
        raw = f"{artist}:{album}".lower().strip()
        return hashlib.md5(raw.encode()).hexdigest()

    @classmethod
    def make_key_from_path(cls, path: str) -> str:
        """Generate cache key from file path."""
        return hashlib.md5(path.encode()).hexdigest()

    @classmethod
    def get(cls, key: str):
        """Get cached pixmap. Returns QPixmap or None."""
        pixmap = QPixmap()
        if QPixmapCache.find(key, pixmap):
            return pixmap if not pixmap.isNull() else None
        return None

    @classmethod
    def set(cls, key: str, pixmap: QPixmap) -> bool:
        """Store pixmap in cache. Returns True on success."""
        if pixmap is None or pixmap.isNull():
            return False
        return QPixmapCache.insert(key, pixmap)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_pixmap_cache.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add infrastructure/cache/pixmap_cache.py tests/test_pixmap_cache.py
git commit -m "feat: add CoverPixmapCache wrapping QPixmapCache"
```

---

### Task 2: QueueTrackModel (QAbstractListModel)

**Files:**
- Modify: `ui/views/queue_view.py` (add QueueTrackModel class at top, before QueueView)
- Test: `tests/test_queue_track_model.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_queue_track_model.py
"""Tests for QueueTrackModel."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock
from PySide6.QtCore import Qt

# Must create app before importing model
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)


class MockTheme:
    name = "dark"
    background = "#121212"
    background_alt = "#282828"
    background_hover = "#2a2a2a"
    text = "#ffffff"
    text_secondary = "#b3b3b3"
    highlight = "#1db954"
    highlight_hover = "#1ed760"
    selection = "rgba(40,40,40,0.8)"
    border = "#3a3a3a"


class MockThemeManager:
    _instance = None
    current_theme = MockTheme()

    @classmethod
    def instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_widget(self, w):
        pass


TRACKS = [
    {"id": 1, "title": "Song A", "artist": "Artist", "album": "Album", "duration": 180, "path": "/a.mp3"},
    {"id": 2, "title": "Song B", "artist": "Artist", "album": "Album", "duration": 200, "path": "/b.mp3"},
    {"id": 3, "title": "Song C", "artist": "Other", "album": "Other", "duration": 160, "path": "/c.mp3"},
]


def test_model_row_count():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        assert m.rowCount() == 3


def test_model_data_title():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        idx = m.index(0)
        assert m.data(idx, QueueTrackModel.TitleRole) == "Song A"


def test_model_data_selected():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        idx = m.index(1)
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is False
        m.set_selection({1})
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is True


def test_model_current_index():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        assert m.current_index == -1
        m.set_current(2)
        assert m.current_index == 2
        idx = m.index(2)
        assert m.data(idx, QueueTrackModel.IsCurrentRole) is True
        idx0 = m.index(0)
        assert m.data(idx0, QueueTrackModel.IsCurrentRole) is False


def test_model_is_playing():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        m.set_current(0)
        m.set_playing(True)
        assert m.data(m.index(0), QueueTrackModel.IsPlayingRole) is True
        m.set_playing(False)
        assert m.data(m.index(0), QueueTrackModel.IsPlayingRole) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_queue_track_model.py -v`
Expected: FAIL (import error)

- [ ] **Step 3: Write QueueTrackModel**

Add this class at the top of `ui/views/queue_view.py` (after imports, before the old `QueueItemWidget` class):

```python
from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, QRunnable, QThreadPool
```

```python
class QueueTrackModel(QAbstractListModel):
    """QAbstractListModel for queue track data."""

    # Custom roles
    TrackRole = Qt.UserRole + 1
    CoverRole = Qt.UserRole + 2
    IsSelectedRole = Qt.UserRole + 3
    IsCurrentRole = Qt.UserRole + 4
    IsPlayingRole = Qt.UserRole + 5
    IndexRole = Qt.UserRole + 6

    # Signal emitted when cover is loaded asynchronously
    cover_loaded = Signal(int)  # row index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list = []
        self._selection: set = set()
        self._current_index: int = -1
        self._is_playing: bool = False

    def rowCount(self, parent=QModelIndex()):
        return len(self._tracks)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._tracks):
            return None
        row = index.row()
        track = self._tracks[row]
        if role == self.TrackRole:
            return track
        elif role == self.CoverRole:
            return None  # loaded asynchronously
        elif role == self.IsSelectedRole:
            return row in self._selection
        elif role == self.IsCurrentRole:
            return row == self._current_index
        elif role == self.IsPlayingRole:
            return row == self._current_index and self._is_playing
        elif role == self.IndexRole:
            return row
        return None

    def roleNames(self):
        return {
            Qt.DisplayRole: b"display",
            self.TrackRole: b"track",
            self.CoverRole: b"cover",
            self.IsSelectedRole: b"selected",
            self.IsCurrentRole: b"current",
            self.IsPlayingRole: b"playing",
            self.IndexRole: b"index",
        }

    def reset_tracks(self, tracks: list, selected_rows: set = None):
        """Full reset of track list."""
        self.beginResetModel()
        self._tracks = list(tracks)
        self._selection = set(selected_rows) if selected_rows else set()
        self.endResetModel()

    def set_selection(self, rows: set):
        """Update selection set."""
        old = self._selection.copy()
        self._selection = set(rows)
        # Emit dataChanged for rows that changed
        changed = old.symmetric_difference(self._selection)
        for row in changed:
            idx = self.index(row)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [self.IsSelectedRole])

    def set_current(self, index: int):
        """Set current playing track index."""
        old = self._current_index
        self._current_index = index
        if old >= 0 and old < len(self._tracks):
            idx = self.index(old)
            self.dataChanged.emit(idx, idx, [self.IsCurrentRole, self.IsPlayingRole])
        if index >= 0 and index < len(self._tracks):
            idx = self.index(index)
            self.dataChanged.emit(idx, idx, [self.IsCurrentRole, self.IsPlayingRole])

    def set_playing(self, playing: bool):
        """Set playing state."""
        self._is_playing = playing
        if 0 <= self._current_index < len(self._tracks):
            idx = self.index(self._current_index)
            self.dataChanged.emit(idx, idx, [self.IsPlayingRole])

    def insert_tracks(self, position: int, tracks: list):
        """Insert tracks at position."""
        self.beginInsertRows(QModelIndex(), position, position + len(tracks) - 1)
        for i, t in enumerate(tracks):
            self._tracks.insert(position + i, t)
        self.endInsertRows()

    def remove_tracks(self, rows: list):
        """Remove tracks by row indices (must be sorted descending)."""
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self._tracks):
                self.beginRemoveRows(QModelIndex(), row, row)
                self._tracks.pop(row)
                self.endRemoveRows()
                # Adjust selection
                self._selection.discard(row)
                self._selection = {r - 1 if r > row else r for r in self._selection}
                # Adjust current index
                if self._current_index == row:
                    self._current_index = -1
                elif self._current_index > row:
                    self._current_index -= 1

    def get_selected_rows(self) -> list:
        """Return sorted list of selected row indices."""
        return sorted(self._selection)

    def get_track_at(self, row: int):
        """Get track dict at row."""
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_queue_track_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/views/queue_view.py tests/test_queue_track_model.py
git commit -m "feat: add QueueTrackModel (QAbstractListModel)"
```

---

### Task 3: QueueItemDelegate (QStyledItemDelegate)

**Files:**
- Modify: `ui/views/queue_view.py` (add QueueItemDelegate class)
- Test: `tests/test_queue_delegate.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_queue_delegate.py
"""Tests for QueueItemDelegate."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)


class MockTheme:
    name = "dark"
    background = "#121212"
    background_alt = "#282828"
    background_hover = "#2a2a2a"
    text = "#ffffff"
    text_secondary = "#b3b3b3"
    highlight = "#1db954"
    highlight_hover = "#1ed760"
    selection = "rgba(40,40,40,0.8)"
    border = "#3a3a3a"


class MockThemeManager:
    _instance = None
    current_theme = MockTheme()

    @classmethod
    def instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


def test_size_hint():
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueItemDelegate
        from PySide6.QtWidgets import QStyleOptionViewItem
        d = QueueItemDelegate()
        option = QStyleOptionViewItem()
        assert d.sizeHint(option, None) == QSize(0, 72)


def test_paint_does_not_crash():
    """Paint should not crash with various track states."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueItemDelegate, QueueTrackModel
        from PySide6.QtCore import QModelIndex
        from PySide6.QtGui import QPainter, QPixmap, QColor

        model = QueueTrackModel()
        model.reset_tracks([
            {"id": 1, "title": "Test Song", "artist": "Artist", "album": "Album", "duration": 180, "path": "/a.mp3"},
        ])

        # Create offscreen pixmap for painting
        pixmap = QPixmap(400, 72)
        pixmap.fill(QColor("#121212"))
        painter = QPainter(pixmap)

        delegate = QueueItemDelegate()

        # Paint normal item
        idx = model.index(0)
        option = delegate._make_style_option(idx)
        delegate.paint(painter, option, idx)
        painter.end()

        # Paint current item
        model.set_current(0)
        model.set_playing(True)
        pixmap2 = QPixmap(400, 72)
        pixmap2.fill(QColor("#121212"))
        painter2 = QPainter(pixmap2)
        idx = model.index(0)
        option2 = delegate._make_style_option(idx)
        delegate.paint(painter2, option2, idx)
        painter2.end()

        # Paint selected item
        model.reset_tracks([{"id": 1, "title": "Sel", "artist": "A", "album": "B", "duration": 180, "path": "/a.mp3"}])
        model.set_selection({0})
        pixmap3 = QPixmap(400, 72)
        pixmap3.fill(QColor("#121212"))
        painter3 = QPainter(pixmap3)
        idx = model.index(0)
        option3 = delegate._make_style_option(idx)
        delegate.paint(painter3, option3, idx)
        painter3.end()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_queue_delegate.py -v`
Expected: FAIL

- [ ] **Step 3: Write QueueItemDelegate**

Add to `ui/views/queue_view.py`:

```python
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QListView

import hashlib
from infrastructure.cache.pixmap_cache import CoverPixmapCache
```

```python
class CoverLoadWorker(QRunnable):
    """Worker to load cover in background and emit result via signal."""

    def __init__(self, row: int, load_func, callback_signal):
        super().__init__()
        self.row = row
        self.load_func = load_func
        self.callback_signal = callback_signal

    def run(self):
        try:
            cover_path = self.load_func()
            # Decode QImage in worker thread
            from PySide6.QtGui import QImage
            qimage = None
            if cover_path:
                qimage = QImage(cover_path)
            self.callback_signal.emit(self.row, cover_path, qimage)
        except Exception:
            self.callback_signal.emit(self.row, None, None)


class QueueItemDelegate(QStyledItemDelegate):
    """Delegate for painting queue items without per-item QWidget overhead."""

    # Signal for cover loaded (row, cover_path, qimage)
    _cover_loaded_signal = Signal(int, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_loaded_signal.connect(self._on_cover_loaded)
        self._pending_covers: dict = {}  # row -> version counter
        self._cover_versions: dict = {}  # row -> int

        # Initialize cache
        CoverPixmapCache.initialize()

        # Cover dimensions
        self._cover_size = 64
        self._index_width = 30
        self._padding = 10

    def sizeHint(self, option, index):
        return QSize(0, 72)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        track = index.data(QueueTrackModel.TrackRole)
        is_selected = index.data(QueueTrackModel.IsSelectedRole)
        is_current = index.data(QueueTrackModel.IsCurrentRole)
        is_playing = index.data(QueueTrackModel.IsPlayingRole)
        row = index.data(QueueTrackModel.IndexRole)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect

        # Background
        if is_selected:
            painter.fillRect(rect, QColor(theme.highlight))
        else:
            painter.fillRect(rect, QColor(theme.background))

        # Separator line
        if not is_selected:
            painter.setPen(QColor(theme.background_hover))
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Determine text color
        if is_selected:
            text_color = QColor(theme.background)
            secondary_color = QColor(theme.background)
        elif is_current:
            text_color = QColor(theme.highlight)
            secondary_color = QColor(theme.highlight)
        else:
            text_color = QColor(theme.text)
            secondary_color = QColor(theme.text_secondary)

        x = rect.left() + self._padding

        # Index
        painter.setPen(secondary_color)
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)
        index_text = f"{row + 1}"
        painter.drawText(x, rect.top(), self._index_width, rect.height(),
                         Qt.AlignVCenter | Qt.AlignHCenter, index_text)
        x += self._index_width

        # Cover
        cover_rect = QRect(x + 2, rect.top() + 4, self._cover_size, self._cover_size)
        self._paint_cover(painter, cover_rect, track, row, theme)
        x += self._cover_size + 8

        # Title
        title = track.get("title", "Unknown") if isinstance(track, dict) else "Unknown"
        if is_current:
            icon = "\u25B6 " if is_playing else "\u23F8 "
            title = f"{icon}{title}"

        painter.setPen(text_color)
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)
        title_rect = QRect(x, rect.top() + 14, rect.right() - x - 60, 22)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, title, title_rect.width()))

        # Artist + Album
        artist = track.get("artist", "Unknown") if isinstance(track, dict) else "Unknown"
        album = track.get("album", "") if isinstance(track, dict) else ""
        artist_album = artist + (f" \u2022 {album}" if album else "")

        painter.setPen(secondary_color)
        font.setPixelSize(11)
        font.setBold(False)
        painter.setFont(font)
        info_rect = QRect(x, rect.top() + 38, rect.right() - x - 60, 22)
        painter.drawText(info_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, artist_album, info_rect.width()))

        # Duration
        duration = track.get("duration", 0) if isinstance(track, dict) else 0
        from utils.helpers import format_duration
        duration_text = format_duration(duration)
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(rect.right() - self._padding - 50, rect.top(), 50, rect.height(),
                         Qt.AlignVCenter | Qt.AlignRight, duration_text)

        painter.restore()

    def _paint_cover(self, painter: QPainter, rect: QRect, track, row: int, theme):
        """Paint cover art, with caching and async loading."""
        from PySide6.QtGui import QPixmap

        cache_key = self._get_cover_cache_key(track)

        # Try cache first
        cached = CoverPixmapCache.get(cache_key)
        if cached and not cached.isNull():
            painter.drawPixmap(rect, cached)
            return

        # Draw placeholder
        placeholder = QPixmap(self._cover_size, self._cover_size)
        placeholder.fill(QColor(theme.background_alt))
        p = QPainter(placeholder)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QColor(theme.border))
        font = p.font()
        font.setPixelSize(28)
        p.setFont(font)
        p.drawText(0, 0, self._cover_size, self._cover_size, Qt.AlignCenter, "\u266B")
        p.end()
        painter.drawPixmap(rect, placeholder)

        # Request async load (debounce by tracking pending)
        version = self._cover_versions.get(row, 0) + 1
        self._cover_versions[row] = version
        self._pending_covers[row] = version

        def load_func():
            return self._resolve_cover_path(track)

        worker = CoverLoadWorker(row, load_func, self._cover_loaded_signal)
        QThreadPool.globalInstance().start(worker)

    def _on_cover_loaded(self, row: int, cover_path: str, qimage):
        """Handle cover loaded in worker thread — runs on UI thread."""
        # Check if this result is still valid
        current_version = self._cover_versions.get(row, 0)
        if self._pending_covers.get(row) != current_version:
            return

        from PySide6.QtGui import QPixmap
        if qimage and not qimage.isNull():
            pixmap = QPixmap.fromImage(qimage).scaled(
                self._cover_size, self._cover_size,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation,
            )
            cache_key = None
            # Find the track for cache key (need model reference)
            if hasattr(self, 'parent') and self.parent():
                model = self.parent().model()
                if model and 0 <= row < model.rowCount():
                    track = model.data(model.index(row), QueueTrackModel.TrackRole)
                    cache_key = self._get_cover_cache_key(track)
            if cache_key:
                CoverPixmapCache.set(cache_key, pixmap)

            # Trigger repaint for this row
            if hasattr(self, 'parent') and self.parent():
                view = self.parent()
                view.update(view.indexAt(QPoint(0, 0)))  # Will be refined below

    def _get_cover_cache_key(self, track) -> str:
        """Generate cache key for a track."""
        if not isinstance(track, dict):
            return CoverPixmapCache.make_key_from_path("")
        artist = track.get("artist", "")
        album = track.get("album", "")
        if artist and album:
            return CoverPixmapCache.make_key(artist, album)
        path = track.get("path", "") or track.get("cover_path", "")
        return CoverPixmapCache.make_key_from_path(path)

    def _resolve_cover_path(self, track) -> str:
        """Resolve cover path for a track (runs in worker thread)."""
        from pathlib import Path

        if not isinstance(track, dict):
            return None

        source = track.get("source", "") or track.get("source_type", "")
        cloud_file_id = track.get("cloud_file_id", "")
        is_online = source == "QQ" or source == "online"

        if is_online and cloud_file_id:
            try:
                from app.bootstrap import Bootstrap
                bootstrap = Bootstrap.instance()
                if bootstrap and hasattr(bootstrap, 'cover_service'):
                    cover_path = bootstrap.cover_service.get_online_cover(
                        song_mid=cloud_file_id,
                        album_mid=None,
                        artist=track.get("artist", ""),
                        title=track.get("title", ""),
                    )
                    if cover_path:
                        return cover_path
            except Exception:
                pass

        cover_path = track.get("cover_path")
        if cover_path and Path(cover_path).exists():
            return cover_path

        path = track.get("path", "")
        if path and Path(path).exists():
            try:
                from app.bootstrap import Bootstrap
                bootstrap = Bootstrap.instance()
                if bootstrap and hasattr(bootstrap, 'cover_service'):
                    cover_path = bootstrap.cover_service.get_cover(
                        path, track.get("title", ""), track.get("artist", ""),
                        track.get("album", ""), skip_online=True,
                    )
                    if cover_path:
                        return cover_path
            except Exception:
                pass

        return None

    @staticmethod
    def _elided_text(painter, text: str, max_width: int) -> str:
        """Return elided text if too wide."""
        fm = painter.fontMetrics()
        if fm.horizontalAdvance(text) <= max_width:
            return text
        return fm.elidedText(text, Qt.ElideRight, max_width)

    def _make_style_option(self, index: QModelIndex) -> QStyleOptionViewItem:
        """Create a QStyleOptionViewItem for testing paint."""
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 400, 72)
        option.state = QStyleOptionViewItem.State_Enabled
        return option
```

**Important:** Add to imports at top of file:
```python
from PySide6.QtCore import QRect, QPoint
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_queue_delegate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui/views/queue_view.py tests/test_queue_delegate.py
git commit -m "feat: add QueueItemDelegate with async cover loading"
```

---

### Task 4: Rewrite QueueView to use QListView + Model + Delegate

**Files:**
- Modify: `ui/views/queue_view.py` (rewrite QueueView class)
- Modify: `ui/styles.qss` (add QListView rules for queue)

- [ ] **Step 1: Rewrite QueueView.__init__ and _setup_ui**

Replace `QueueView._setup_ui()` to use QListView instead of QListWidget:

In `_setup_ui`, replace:
```python
self._queue_list = QListWidget()
```
with:
```python
from PySide6.QtWidgets import QListView
self._list_view = QListView()
self._model = QueueTrackModel(self)
self._delegate = QueueItemDelegate(self._list_view)
self._list_view.setModel(self._model)
self._list_view.setItemDelegate(self._delegate)
self._list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
self._list_view.setDragDropMode(QAbstractItemView.InternalMove)
self._list_view.setContextMenuPolicy(Qt.CustomContextMenu)
self._list_view.customContextMenuRequested.connect(self._show_context_menu)
self._list_view.setSpacing(0)
self._list_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
self._list_view.setFocusPolicy(Qt.NoFocus)
```

Replace `self._queue_list` references throughout with `self._list_view` and use model operations instead of QListWidget operations. See Step 3 for the full list.

- [ ] **Step 2: Add QListView styles to styles.qss**

Append to `ui/styles.qss`:

```css
/* Queue QListView */
QListView#queueList {
    background-color: %background%;
    border: none;
    outline: none;
    border-radius: 8px;
}
QListView#queueList::item {
    border: none;
    margin: 0px;
    background-color: transparent;
}
```

- [ ] **Step 3: Rewrite QueueView signal handlers and methods**

Replace all `self._queue_list` references with `self._list_view` equivalents:

- `_setup_connections()`: Connect to `self._list_view.selectionModel().selectionChanged`, `self._list_view.doubleClicked`
- `_on_selection_changed(selection, deselected)`: Use `self._model.set_selection(rows)`
- `_initialize_view()`: Use `self._model.reset_tracks(playlist)`
- `_refresh_queue()`: Use `self._model.reset_tracks(playlist)` + restore selection via model
- `_update_current_track_indicator()`: Use `self._model.set_current(idx)` + `self._model.set_playing(is_playing)`
- `_scroll_to_current_track()`: Use `self._list_view.scrollTo(model_index, ...)` where `model_index = self._model.index(current_index)`
- `_on_rows_moved()`: No longer needed — drag-drop handled by model. Remove or stub.
- `_remove_selected()`: Get selected rows from model, call `self._model.remove_tracks(rows)` then remove from engine
- `_play_selected()`: Get first selected row from model, call `self._player.engine.play_at(row)`
- `_show_context_menu(pos)`: Map position, get index via `self._list_view.indexAt(pos)`
- `_select_track_by_id(track_id)`: Iterate model tracks, find by id
- `add_tracks(track_ids)`: After adding to engine, call `self._refresh_queue()` (engine emits playlist_changed)
- `insert_tracks_after_current(track_ids)`: Same as above
- `_on_item_double_clicked(index)`: Get track from model, emit `play_track`
- `closeEvent`, `showEvent`: Keep but use model

Keep all dialog methods unchanged (`_edit_media_info`, `_create_playlist_from_queue`, etc.) but replace `self._queue_list.selectedItems()` with `self._model.get_selected_rows()` and get tracks via `self._model.get_track_at(row)`.

Replace the `refresh_theme()` method to only update the QListView QSS, no per-item iteration:

```python
def refresh_theme(self):
    from system.theme import ThemeManager
    theme_manager = ThemeManager.instance()
    theme = theme_manager.current_theme
    self.setStyleSheet(theme_manager.get_qss(self._STYLE_TEMPLATE))
    self._highlight_color = theme.highlight
    # No per-item refresh needed — delegate reads theme on paint
```

- [ ] **Step 4: Run existing tests**

Run: `uv run pytest tests/test_queue_selection_fix.py -v`

**Note:** This test references `QueueItemWidget` which no longer exists. The test needs to be **updated** to test the new model/delegate instead:

Update `tests/test_queue_selection_fix.py` to test model selection state:

```python
"""Test for queue selection state synchronization with new model."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)


class MockTheme:
    name = "dark"
    background = "#121212"
    background_alt = "#282828"
    background_hover = "#2a2a2a"
    text = "#ffffff"
    text_secondary = "#b3b3b3"
    highlight = "#1db954"
    highlight_hover = "#1ed760"
    selection = "rgba(40,40,40,0.8)"
    border = "#3a3a3a"


class MockThemeManager:
    _instance = None
    current_theme = MockTheme()

    @classmethod
    def instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_widget(self, w):
        pass


TRACKS = [
    {"id": 1, "title": "Test", "artist": "A", "album": "B", "duration": 180, "path": "/t.mp3"},
]


def test_selection_state_sync():
    """Model selection state updates correctly."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        idx = m.index(0)
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is False
        m.set_selection({0})
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is True


def test_current_and_selected_state():
    """Current track can be selected simultaneously."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueTrackModel
        m = QueueTrackModel()
        m.reset_tracks(TRACKS)
        m.set_current(0)
        m.set_playing(True)
        idx = m.index(0)
        assert m.data(idx, QueueTrackModel.IsCurrentRole) is True
        assert m.data(idx, QueueTrackModel.IsPlayingRole) is True
        m.set_selection({0})
        assert m.data(idx, QueueTrackModel.IsSelectedRole) is True
```

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add ui/views/queue_view.py ui/styles.qss tests/test_queue_selection_fix.py
git commit -m "refactor: rewrite QueueView with QListView + Model + Delegate"
```

---

### Task 5: Clean up old code and remove QueueItemWidget

**Files:**
- Modify: `ui/views/queue_view.py` (remove QueueItemWidget class entirely)

- [ ] **Step 1: Remove QueueItemWidget class**

Delete the entire `class QueueItemWidget(QWidget)` block (lines 44-396 of original). This includes:
- All `_STYLE_SELECTED`, `_STYLE_CURRENT`, `_STYLE_NORMAL` constants
- `__init__`, `set_selected`, `refresh_theme`, `_update_style`, `_setup_ui`
- `_load_cover_async`, `_on_cover_loaded`, `_set_default_cover`, `update_play_state`

Remove the `threading` import if no longer used.

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add ui/views/queue_view.py
git commit -m "refactor: remove QueueItemWidget, fully migrated to delegate"
```

---

### Task 6: Fix _on_cover_loaded to properly trigger repaint

**Files:**
- Modify: `ui/views/queue_view.py` (QueueItemDelegate._on_cover_loaded)

- [ ] **Step 1: Fix delegate repaint signal**

The `_on_cover_loaded` method needs to trigger a repaint of the specific row. Replace the placeholder update logic with proper model notification:

In `QueueItemDelegate`, the signal connects to the model. Add a method to QueueTrackModel:

```python
class QueueTrackModel(QAbstractListModel):
    # Add to existing class
    cover_ready = Signal(int)  # row

    def notify_cover_loaded(self, row: int):
        """Notify view that cover for a row has been loaded."""
        if 0 <= row < len(self._tracks):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [self.CoverRole])
```

Then in QueueView.__init__ or _setup_ui, connect:
```python
self._delegate._cover_loaded_signal.connect(self._on_cover_ready)
```

And add to QueueView:
```python
def _on_cover_ready(self, row: int, cover_path: str, qimage):
    """Handle cover loaded — update cache and trigger repaint."""
    from PySide6.QtGui import QPixmap
    if qimage and not qimage.isNull():
        pixmap = QPixmap.fromImage(qimage).scaled(
            64, 64, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
        )
        track = self._model.get_track_at(row)
        if track:
            cache_key = self._delegate._get_cover_cache_key(track)
            CoverPixmapCache.set(cache_key, pixmap)
        self._model.notify_cover_loaded(row)
```

Remove the `_on_cover_loaded` method from QueueItemDelegate — move responsibility to QueueView.

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add ui/views/queue_view.py
git commit -m "fix: proper cover repaint via model dataChanged signal"
```

---

### Task 7: Final integration test and cleanup

**Files:**
- Test: `tests/test_queue_view.py` (integration test)
- Verify: `ui/views/queue_view.py` final state

- [ ] **Step 1: Write integration test for QueueView**

```python
# tests/test_queue_view.py
"""Integration tests for refactored QueueView."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from unittest.mock import patch, MagicMock, PropertyMock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

app = QApplication.instance() or QApplication(sys.argv)


class MockTheme:
    name = "dark"
    background = "#121212"
    background_alt = "#282828"
    background_hover = "#2a2a2a"
    text = "#ffffff"
    text_secondary = "#b3b3b3"
    highlight = "#1db954"
    highlight_hover = "#1ed760"
    selection = "rgba(40,40,40,0.8)"
    border = "#3a3a3a"


class MockThemeManager:
    _instance = None
    current_theme = MockTheme()

    @classmethod
    def instance(cls, config=None):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_widget(self, w):
        pass

    def get_qss(self, template):
        return template


def test_queue_view_creates():
    """QueueView can be instantiated with mock services."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView

        mock_player = MagicMock()
        mock_player.engine = MagicMock()
        mock_player.engine.playlist = []
        mock_player.engine.current_index = -1
        mock_player.engine.state = MagicMock()
        mock_player.engine.state.value = "stopped"
        mock_player.engine.current_track_changed = MagicMock()
        mock_player.engine.state_changed = MagicMock()
        mock_player.engine.playlist_changed = MagicMock()

        mock_lib = MagicMock()
        mock_fav = MagicMock()
        mock_pl = MagicMock()

        view = QueueView(mock_player, mock_lib, mock_fav, mock_pl)
        assert view is not None


def test_queue_view_refresh():
    """refresh_queue updates model without crash."""
    with patch('system.theme.ThemeManager', MockThemeManager):
        from ui.views.queue_view import QueueView

        mock_player = MagicMock()
        mock_engine = MagicMock()
        mock_engine.playlist = [
            {"id": 1, "title": "A", "artist": "B", "album": "C", "duration": 180, "path": "/a.mp3"},
        ]
        mock_engine.current_index = 0
        mock_engine.state = MagicMock()
        mock_engine.state.value = "playing"
        mock_engine.current_track_changed = MagicMock()
        mock_engine.state_changed = MagicMock()
        mock_engine.playlist_changed = MagicMock()
        mock_player.engine = mock_engine

        view = QueueView(mock_player, MagicMock(), MagicMock(), MagicMock())
        view._refresh_queue()
        assert view._model.rowCount() == 1
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Manual smoke test**

Run: `uv run python main.py`

Verify:
- Queue view displays tracks
- Cover art loads for tracks
- Selection highlighting works (click tracks)
- Current track indicator shows (play a track)
- Drag-drop reorder works
- Right-click context menu works
- Theme switching updates queue styling
- Scrolling with 100+ tracks is smooth

- [ ] **Step 4: Final commit**

```bash
git add tests/test_queue_view.py
git commit -m "test: add QueueView integration tests"
```

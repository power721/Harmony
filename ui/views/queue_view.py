"""
Queue view for managing the current playback queue.
"""

import logging
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QAbstractListModel, QModelIndex, QRunnable, QThreadPool, QRect, \
    QItemSelectionModel, QPoint
from PySide6.QtGui import QColor, QPixmap, QPainter, QImage, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QMenu,
    QAbstractItemView,
    QDialog,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QListView,
    QFrame,
    QStyle,
    QApplication,
)

from domain.playback import PlaybackState
from domain.playlist import Playlist
from infrastructure.cache.pixmap_cache import CoverPixmapCache
from services.library import LibraryService
from services.library.favorites_service import FavoritesService
from services.library.playlist_service import PlaylistService
from services.playback import PlaybackService
from system.event_bus import EventBus
from system.i18n import t
from ui.dialogs import EditMediaInfoDialog
from ui.dialogs.add_to_playlist_dialog import AddToPlaylistDialog
from ui.dialogs.message_dialog import MessageDialog, Yes, No
from utils.dedup import deduplicate_playlist_items

logger = logging.getLogger(__name__)


class QueueTrackModel(QAbstractListModel):
    """QAbstractListModel for queue track data."""

    TrackRole = Qt.UserRole + 1
    CoverRole = Qt.UserRole + 2
    IsSelectedRole = Qt.UserRole + 3
    IsCurrentRole = Qt.UserRole + 4
    IsPlayingRole = Qt.UserRole + 5
    IndexRole = Qt.UserRole + 6

    cover_ready = Signal(int)
    rows_moved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: list = []
        self._selection: set = set()
        self._current_index: int = -1
        self._is_playing: bool = False

    @property
    def current_index(self) -> int:
        return self._current_index

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
            return None
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
        self.beginResetModel()
        self._tracks = list(tracks)
        self._selection = set(selected_rows) if selected_rows else set()
        self.endResetModel()

    def set_selection(self, rows: set):
        old = self._selection.copy()
        self._selection = set(rows)
        changed = old.symmetric_difference(self._selection)
        for row in changed:
            idx = self.index(row)
            if idx.isValid():
                self.dataChanged.emit(idx, idx, [self.IsSelectedRole])

    def set_current(self, index: int):
        old = self._current_index
        self._current_index = index
        if old >= 0 and old < len(self._tracks):
            idx = self.index(old)
            self.dataChanged.emit(idx, idx, [self.IsCurrentRole, self.IsPlayingRole])
        if index >= 0 and index < len(self._tracks):
            idx = self.index(index)
            self.dataChanged.emit(idx, idx, [self.IsCurrentRole, self.IsPlayingRole])

    def set_playing(self, playing: bool):
        self._is_playing = playing
        if 0 <= self._current_index < len(self._tracks):
            idx = self.index(self._current_index)
            self.dataChanged.emit(idx, idx, [self.IsPlayingRole])

    def insert_tracks(self, position: int, tracks: list):
        self.beginInsertRows(QModelIndex(), position, position + len(tracks) - 1)
        for i, t in enumerate(tracks):
            self._tracks.insert(position + i, t)
        self.endInsertRows()

    def remove_tracks(self, rows: list):
        for row in sorted(rows, reverse=True):
            if 0 <= row < len(self._tracks):
                self.beginRemoveRows(QModelIndex(), row, row)
                self._tracks.pop(row)
                self.endRemoveRows()
                self._selection.discard(row)
                self._selection = {r - 1 if r > row else r for r in self._selection}
                if self._current_index == row:
                    self._current_index = -1
                elif self._current_index > row:
                    self._current_index -= 1

    def get_selected_rows(self) -> list:
        return sorted(self._selection)

    def get_track_at(self, row: int):
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def notify_cover_loaded(self, row: int):
        if 0 <= row < len(self._tracks):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [self.CoverRole])

    def flags(self, index):
        """Enable item dragging."""
        default_flags = super().flags(index)
        if index.isValid():
            return default_flags | Qt.ItemIsDragEnabled
        return default_flags | Qt.ItemIsDropEnabled

    def supportedDropActions(self):
        return Qt.MoveAction

    def supportedDragActions(self):
        return Qt.MoveAction

    def mimeTypes(self):
        return ["application/x-queueitem"]

    def mimeData(self, indexes):
        """Encode dragged row indices."""
        from PySide6.QtCore import QMimeData
        mime = QMimeData()
        rows = [idx.row() for idx in indexes if idx.isValid()]
        mime.setData("application/x-queueitem", str(rows).encode())
        return mime

    def dropMimeData(self, data, action, row, column, parent):
        """Handle drop to reorder items."""
        if action == Qt.IgnoreAction:
            return True
        if not data.hasFormat("application/x-queueitem"):
            return False

        try:
            source_rows = eval(data.data("application/x-queueitem").data().decode())
        except Exception:
            return False

        if not source_rows:
            return False

        # Determine target row
        if parent.isValid():
            target_row = parent.row()
        elif row >= 0:
            target_row = row
        else:
            target_row = self.rowCount()

        # Calculate adjusted target (account for source removal)
        sorted_sources = sorted(source_rows)
        adjusted_target = target_row
        for src in sorted_sources:
            if src < adjusted_target:
                adjusted_target -= 1

        if adjusted_target < 0:
            adjusted_target = 0

        # Move items
        items = [self._tracks[r] for r in sorted_sources if 0 <= r < len(self._tracks)]
        if not items:
            return False

        # Remove from old positions
        for r in sorted(sorted_sources, reverse=True):
            if 0 <= r < len(self._tracks):
                self._tracks.pop(r)

        if adjusted_target > len(self._tracks):
            adjusted_target = len(self._tracks)

        for i, item in enumerate(items):
            self._tracks.insert(adjusted_target + i, item)

        # Update current index
        for src in sorted_sources:
            if self._current_index == src:
                self._current_index = adjusted_target
                break

        self.layoutChanged.emit()
        self.rows_moved.emit()
        return True


class CoverLoadWorker(QRunnable):
    """Worker to load cover in background thread."""

    def __init__(self, track_id: str, track: dict, callback_signal):
        super().__init__()
        self.track_id = track_id
        self.track = track  # shallow copy made by caller
        self.callback_signal = callback_signal
        self.version = 0
        self.setAutoDelete(True)

    def run(self):
        try:
            cover_path = _resolve_cover_path(self.track)
            qimage = None
            if cover_path:
                qimage = QImage(cover_path)
            try:
                self.callback_signal.emit(self.track_id, cover_path, qimage)
            except RuntimeError:
                pass  # signal source deleted (e.g., delegate GC'd during test)
        except Exception:
            pass


def _resolve_cover_path(track: dict) -> str | None:
    """Resolve cover path for a track dict (runs in worker thread)."""
    if not isinstance(track, dict):
        return None

    from pathlib import Path

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


class QueueItemDelegate(QStyledItemDelegate):
    """Delegate for painting queue items without per-item QWidget overhead."""

    _cover_loaded_signal = Signal(str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_loaded_signal.connect(self._on_cover_loaded)
        self._cover_versions: dict[str, int] = {}
        self._requested_covers: set[str] = set()  # track IDs with pending cover requests
        self._failed_covers: set[str] = set()  # track IDs where cover loading returned nothing
        CoverPixmapCache.initialize()
        self._cover_size = 64
        self._index_width = 40
        self._padding = 10

        # Animation state
        self._animation_frame = 0
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._advance_animation)
        self._animation_timer.setInterval(300)
        self._animation_playing = False
        self._current_anim_row = -1

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

        # Check for download failure
        is_download_failed = False
        if isinstance(track, dict):
            is_download_failed = track.get("download_failed", False)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect

        # Background (semi-transparent to show blur through)
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver
        if is_selected:
            painter.fillRect(rect, QColor(theme.highlight))
        elif is_hovered:
            hover_bg = QColor(theme.background_hover)
            hover_bg.setAlpha(220)
            painter.fillRect(rect, hover_bg)
        else:
            bg = QColor(theme.background)
            bg.setAlpha(220)
            painter.fillRect(rect, bg)

        # Hand cursor on hover
        if is_hovered and not is_selected:
            self.parent().setCursor(Qt.CursorShape.PointingHandCursor) if self.parent() else None

        # Separator line
        if not is_selected:
            painter.setPen(QColor(theme.background_hover))
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Text colors
        if is_download_failed:
            text_color = QColor(128, 128, 128)
            secondary_color = QColor(160, 160, 160)
        elif is_selected:
            text_color = QColor(theme.background)
            secondary_color = QColor(theme.background)
        elif is_current:
            text_color = QColor(theme.highlight)
            secondary_color = QColor(theme.highlight)
        else:
            text_color = QColor(theme.text)
            secondary_color = QColor(theme.text_secondary)

        x = rect.left() + self._padding

        # Index number (or playing animation bars for current track)
        font = painter.font()
        if is_current and is_playing and row == self._current_anim_row:
            self._paint_playing_bars(painter, x, rect, theme.background if is_selected else theme.highlight)
        else:
            painter.setPen(secondary_color)
            font.setPixelSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(x, rect.top(), self._index_width, rect.height(),
                             Qt.AlignVCenter | Qt.AlignHCenter, f"{row + 1}")
        x += self._index_width

        # Cover art
        cover_rect = QRect(x + 2, rect.top() + 4, self._cover_size, self._cover_size)
        self._paint_cover(painter, cover_rect, track, row, theme)
        x += self._cover_size + 8

        # Title
        title = track.get("title", "Unknown") if isinstance(track, dict) else "Unknown"

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

        # Duration / status label
        from system.i18n import t as i18n_t
        if is_download_failed:
            duration_text = i18n_t("download_failed")
            font.setPixelSize(10)
        else:
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
        """Paint cover art with caching and async loading."""
        from PySide6.QtGui import QPixmap as Pm

        cache_key = self._get_cover_cache_key(track)

        # Try cache
        cached = CoverPixmapCache.get(cache_key)
        if cached and not cached.isNull():
            painter.drawPixmap(rect, cached)
        else:
            # Draw placeholder (music note icon)
            placeholder = Pm(self._cover_size, self._cover_size)
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

            # Request async load (debounced by version tracking)
            if cache_key not in self._requested_covers and cache_key not in self._failed_covers:
                self._requested_covers.add(cache_key)
                version = self._cover_versions.get(cache_key, 0) + 1
                self._cover_versions[cache_key] = version
                worker = CoverLoadWorker(cache_key, dict(track), self._cover_loaded_signal)
                worker.version = version
                QThreadPool.globalInstance().start(worker)

        # Preload nearby covers (±3 rows)
        parent_view = self.parent()
        if parent_view and hasattr(parent_view, '_model'):
            model = parent_view._model
            for offset in [-3, -2, -1, 1, 2, 3]:
                nearby_row = row + offset
                if 0 <= nearby_row < model.rowCount():
                    nearby_track = model.get_track_at(nearby_row)
                    if nearby_track:
                        nearby_key = self._get_cover_cache_key(nearby_track)
                        if nearby_key not in self._requested_covers and nearby_key not in self._failed_covers and not CoverPixmapCache.get(
                                nearby_key):
                            self._requested_covers.add(nearby_key)
                            worker = CoverLoadWorker(
                                nearby_key,
                                dict(nearby_track),
                                self._cover_loaded_signal
                            )
                            QThreadPool.globalInstance().start(worker)

    def _on_cover_loaded(self, track_id: str, cover_path: str, qimage):
        """Handle cover loaded from background — runs on UI thread."""
        # Reject stale results (version mismatch)
        current_version = self._cover_versions.get(track_id, 0)
        # Walk the thread pool to check worker version — simplified: just clear pending
        self._requested_covers.discard(track_id)

        parent_view = self.parent()
        if parent_view and hasattr(parent_view, '_on_cover_ready'):
            parent_view._on_cover_ready(track_id, cover_path, qimage)

    def _advance_animation(self):
        """Advance animation frame and repaint current row's index area only."""
        self._animation_frame = (self._animation_frame + 1) % 4
        parent = self.parent()
        if parent and hasattr(parent, '_model'):
            model = parent._model
            if 0 <= model.current_index < model.rowCount():
                idx = model.index(model.current_index)
                view = parent._list_view if hasattr(parent, '_list_view') else None
                if view and idx.isValid():
                    rect = view.visualRect(idx)
                    rect.setWidth(self._index_width)
                    view.viewport().update(rect)

    def _start_animation(self, row: int):
        """Start playing animation for a row."""
        if not self._animation_playing:
            self._animation_playing = True
            self._animation_frame = 0
            self._animation_timer.start()
        self._current_anim_row = row

    def _stop_animation(self):
        """Stop playing animation."""
        self._animation_timer.stop()
        self._animation_playing = False
        self._current_anim_row = -1
        self._animation_frame = 0

    def _paint_playing_bars(self, painter, x, rect, color):
        """Draw animated equalizer bars."""
        painter.setPen(Qt.NoPen)
        bar_color = QColor(color)
        bar_color.setAlpha(200)
        painter.setBrush(bar_color)

        bar_width = 3
        bar_gap = 2
        num_bars = 3
        total_width = num_bars * bar_width + (num_bars - 1) * bar_gap
        start_x = x + (self._index_width - total_width) // 2
        center_y = rect.top() + rect.height() // 2

        # Different heights per frame
        patterns = [
            [0.4, 0.8, 0.6],  # frame 0
            [0.6, 0.4, 0.8],  # frame 1
            [0.8, 0.6, 0.4],  # frame 2
            [0.5, 0.9, 0.5],  # frame 3
        ]
        heights = patterns[self._animation_frame % len(patterns)]

        max_height = 20
        for i, h_factor in enumerate(heights):
            bar_height = int(max_height * h_factor)
            bar_x = start_x + i * (bar_width + bar_gap)
            bar_y = center_y - bar_height // 2
            painter.drawRoundedRect(int(bar_x), int(bar_y), bar_width, bar_height, 1, 1)

    def _get_cover_cache_key(self, track) -> str:
        """Generate cache key for a track."""
        if not isinstance(track, dict):
            return CoverPixmapCache.make_key_from_path("")
        artist = track.get("artist", "")
        album = track.get("album", "")
        if artist and album:
            return CoverPixmapCache.make_key(artist, album)
        path = track.get("path") or track.get("cover_path") or ""
        return CoverPixmapCache.make_key_from_path(path)

    @staticmethod
    def _elided_text(painter, text: str, max_width: int) -> str:
        """Return elided text if too wide."""
        fm = painter.fontMetrics()
        if fm.horizontalAdvance(text) <= max_width:
            return text
        return fm.elidedText(text, Qt.ElideRight, max_width)

    def _make_style_option(self, index: QModelIndex) -> QStyleOptionViewItem:
        """Create a QStyleOptionViewItem for testing paint."""
        from PySide6.QtWidgets import QStyle
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 400, 72)
        option.state = QStyle.StateFlag.State_Enabled
        return option


class CoverHoverPopup(QWidget):
    """Popup widget to display large cover art on hover."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # Size for the popup
        self._size = 300

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Cover label
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(self._size, self._size)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setStyleSheet("border-radius: 8px;")
        layout.addWidget(self._cover_label)

        self._current_track_id = None
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_cover(self, cover_path: str, track_id: str, pos: QPoint):
        """Show cover at specified position.

        Args:
            cover_path: Path to the cover image
            track_id: Track identifier to prevent flickering
            pos: Global position to show popup near
        """
        # Skip if already showing this track
        if self._current_track_id == track_id and self.isVisible():
            return

        self._current_track_id = track_id

        # Load cover
        if cover_path:
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self._size, self._size,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
                self._cover_label.setPixmap(scaled)
            else:
                self._show_placeholder()
        else:
            self._show_placeholder()

        # Position popup near cursor but not covering it
        screen = QApplication.screenAt(pos)
        if not screen:
            screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()

        # Calculate position (offset from cursor - move further right)
        offset = 250
        x = pos.x() + offset
        y = pos.y() - self._size // 2

        # Keep within screen bounds
        if x + self._size > screen_rect.right():
            x = pos.x() - self._size - offset
        if y < screen_rect.top():
            y = screen_rect.top()
        if y + self._size > screen_rect.bottom():
            y = screen_rect.bottom() - self._size

        self.move(x, y)
        self.show()
        self._hide_timer.stop()  # Cancel any pending hide

    def _show_placeholder(self):
        """Show placeholder when no cover available."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        pixmap = QPixmap(self._size, self._size)
        pixmap.fill(QColor(theme.background_alt))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.border))
        font = painter.font()
        font.setPixelSize(120)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self._size, self._size),
            Qt.AlignCenter, "\u266B"
        )
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def schedule_hide(self, delay_ms: int = 100):
        """Schedule hide after delay."""
        self._hide_timer.start(delay_ms)

    def cancel_hide(self):
        """Cancel scheduled hide."""
        self._hide_timer.stop()


class QueueView(QWidget):
    """View for managing the current playback queue."""

    # QSS template with theme tokens
    _STYLE_TEMPLATE = """
        QLabel#queueTitle {
            color: %highlight%;
            font-size: 28px;
            font-weight: bold;
            padding: 10px;
        }
        QWidget#queueHeader {
            background-color: %background%;
        }
        QPushButton#queueActionBtn {
            background: transparent;
            border: 2px solid %border%;
            color: %text_secondary%;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
        }
        QPushButton#queueActionBtn:hover {
            border-color: %highlight%;
            color: %highlight%;
            background-color: %selection%;
        }
        QListView#queueList {
            background-color: transparent;
            border: none;
            outline: none;
            border-radius: 8px;
        }
        QFrame#queueListContainer {
            background-color: %background%;
            border: none;
            border-radius: 8px;
        }
        QListView#queueList::item {
            border: none;
            margin: 0px;
            background-color: transparent;
        }
        QListView QScrollBar:vertical {
            background-color: %background%;
            width: 12px;
            border-radius: 6px;
        }
        QListView QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 40px;
        }
        QListView QScrollBar::handle:vertical:hover {
            background-color: %background_hover%;
        }
    """
    _CONTEXT_MENU_STYLE = """
        QMenu {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
        }
        QMenu::item {
            padding: 8px 20px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """
    _EDIT_DIALOG_STYLE = """
        QDialog { background-color: %background_alt%; color: %text%; }
        QLabel { color: %text%; font-size: 13px; }
        QLineEdit {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px;
            font-size: 13px;
        }
        QLineEdit:focus { border: 1px solid %highlight%; }
        QPushButton {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: %highlight_hover%; }
        QPushButton[role="cancel"] { background-color: %border%; color: %text%; }
        QPushButton[role="cancel"]:hover { background-color: %background_hover%; }
    """

    play_track = Signal(int)
    queue_reordered = Signal()  # Emitted when queue order changes via drag-drop

    def __init__(
            self,
            player: PlaybackService,
            library_service: LibraryService,
            favorite_service: FavoritesService,
            playlist_service: PlaylistService,
            parent=None
    ):
        """
        Initialize queue view.

        Args:
            player: Playback service
            library_service: Library service for track operations
            favorite_service: Favorites service for favorite operations
            playlist_service: Playlist service for creating playlists
            parent: Parent widget
        """
        super().__init__(parent)
        self._player = player
        self._library_service = library_service
        self._favorite_service = favorite_service
        self._playlist_service = playlist_service

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)
        self._highlight_color = ThemeManager.instance().current_theme.highlight

        # Cover hover popup
        self._cover_popup = CoverHoverPopup()
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_cover_popup)
        self._hovered_row = -1
        self._last_cover_pos = QPoint()

        self._setup_ui()
        self._setup_connections()

        # Load initial queue content and update indicators
        QTimer.singleShot(0, self._initialize_view)

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)

        # Header
        header = QWidget()
        header.setObjectName("queueHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 10, 0, 10)
        header_layout.setSpacing(10)

        self._title_label = QLabel(t("play_queue"))
        self._title_label.setObjectName("queueTitle")
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Create playlist button
        self._create_playlist_btn = QPushButton(t("create_playlist"))
        self._create_playlist_btn.setObjectName("queueActionBtn")
        self._create_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._create_playlist_btn.clicked.connect(self._create_playlist_from_queue)
        header_layout.addWidget(self._create_playlist_btn)

        # Smart deduplicate button
        self._dedup_btn = QPushButton(t("smart_deduplicate"))
        self._dedup_btn.setObjectName("queueActionBtn")
        self._dedup_btn.setCursor(Qt.PointingHandCursor)
        self._dedup_btn.clicked.connect(self._deduplicate_queue)
        header_layout.addWidget(self._dedup_btn)

        # Clear button
        self._clear_btn = QPushButton(t("clear_queue"))
        self._clear_btn.setObjectName("queueActionBtn")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_queue)
        header_layout.addWidget(self._clear_btn)

        layout.addWidget(header)

        # Queue list container (blur background + list stacked)
        list_container = QFrame()
        list_container.setObjectName("queueListContainer")
        list_container_layout = QVBoxLayout(list_container)
        list_container_layout.setContentsMargins(0, 0, 0, 0)
        list_container_layout.setSpacing(0)

        # Blur background label
        self._bg_label = QLabel(list_container)
        self._bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bg_label.lower()

        self._list_view = QListView(list_container)
        self._list_view.setObjectName("queueList")
        self._list_view.setMouseTracking(True)
        self._list_view.viewport().installEventFilter(self)
        self._model = QueueTrackModel(self)
        self._delegate = QueueItemDelegate(self)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list_view.setDragDropMode(QAbstractItemView.InternalMove)
        self._model.rows_moved.connect(self._on_rows_moved)
        self._list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.doubleClicked.connect(self._on_item_double_clicked)
        self._list_view.setSpacing(0)
        self._list_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list_view.setFocusPolicy(Qt.NoFocus)
        list_container_layout.addWidget(self._list_view)

        layout.addWidget(list_container)

        # Status bar
        self._status_label = QLabel(f"0 {t('tracks_in_queue')}")
        layout.addWidget(self._status_label)

        # Add track hint
        self._hint_label = QLabel(t("tip_right_click"))
        layout.addWidget(self._hint_label)

        # Apply themed styles
        self.refresh_theme()

    def refresh_theme(self):
        """Apply themed styles from ThemeManager."""
        from system.theme import ThemeManager
        theme_manager = ThemeManager.instance()
        theme = theme_manager.current_theme

        self.setStyleSheet(theme_manager.get_qss(self._STYLE_TEMPLATE))
        self._highlight_color = theme.highlight

        # Update status label
        self._status_label.setStyleSheet(
            f"color: {theme.text_secondary}; font-size: 13px;"
        )
        # Update hint label
        self._hint_label.setStyleSheet(
            f"color: {theme.text_secondary}; font-size: 11px;"
        )

        # No per-item refresh needed — delegate reads theme on paint
        # Trigger full viewport repaint
        if hasattr(self, '_list_view'):
            self._list_view.viewport().update()

    def _setup_connections(self):
        """Setup signal connections."""
        # Connect to engine signals to update current track indicator
        self._player.engine.current_track_changed.connect(
            self._on_current_track_changed
        )
        self._player.engine.state_changed.connect(self._on_player_state_changed)
        self._player.engine.playlist_changed.connect(self._refresh_queue)

        # Connect to selection changes to update model
        self._list_view.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Track playlist size to detect playlist changes
        self._last_playlist_size = 0

    def eventFilter(self, obj, event):
        """Filter events for the list view viewport to handle cover hover."""
        if obj == self._list_view.viewport():
            if event.type() == event.Type.MouseMove:
                self._handle_mouse_move(event)
            elif event.type() == event.Type.Leave:
                self._handle_mouse_leave()
        return super().eventFilter(obj, event)

    def _handle_mouse_move(self, event):
        """Handle mouse move to detect cover hover."""
        pos = event.pos()
        index = self._list_view.indexAt(pos)

        if not index.isValid():
            self._handle_mouse_leave()
            return

        row = index.row()
        rect = self._list_view.visualRect(index)

        # Calculate cover rect (matches delegate logic)
        padding = 10
        index_width = 40
        x = rect.left() + padding + index_width + 2
        cover_rect = QRect(x, rect.top() + 4, 64, 64)

        # Check if mouse is over cover area
        if cover_rect.contains(pos):
            if self._hovered_row != row:
                # New row - start timer
                self._hovered_row = row
                self._last_cover_pos = QCursor.pos()
                self._hover_timer.start(500)  # 500ms delay like tooltip
            else:
                # Same row - cancel hide if showing
                self._cover_popup.cancel_hide()
        else:
            # Not over cover - hide popup
            self._handle_mouse_leave()

    def _handle_mouse_leave(self):
        """Handle mouse leaving cover area."""
        self._hover_timer.stop()
        self._hovered_row = -1
        self._cover_popup.schedule_hide()

    def _show_cover_popup(self):
        """Show cover popup for the currently hovered row."""
        if self._hovered_row < 0 or self._hovered_row >= self._model.rowCount():
            return

        track = self._model.get_track_at(self._hovered_row)
        if not track:
            return

        # Get cover path using the same logic as delegate
        track_dict = dict(track) if isinstance(track, dict) else {}
        cover_path = _resolve_cover_path(track_dict)

        # Get track ID for deduplication
        track_id = self._delegate._get_cover_cache_key(track)

        # Show popup
        self._cover_popup.show_cover(cover_path, track_id, self._last_cover_pos)

    def _on_selection_changed(self, selected, deselected):
        """Handle selection changes to update model."""
        rows = set()
        for index in self._list_view.selectionModel().selectedIndexes():
            rows.add(index.row())
        self._model.set_selection(rows)

    def _initialize_view(self):
        """Initialize the queue view with current content and indicators."""
        # Get current playlist from engine
        playlist = self._player.engine.playlist
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlaybackState.PLAYING

        # Update last known playlist size
        self._last_playlist_size = len(playlist)

        # Save current selection
        selected_rows = self._model.get_selected_rows() if hasattr(self, '_model') else set()

        # Reset model (blocks signals internally)
        self._delegate._failed_covers.clear()
        self._list_view.blockSignals(True)
        self._model.reset_tracks(list(playlist), selected_rows=set(selected_rows))
        self._model.set_current(current_index)
        self._model.set_playing(is_playing)
        self._list_view.blockSignals(False)

        # Restore visual selection
        sm = self._list_view.selectionModel()
        sm.blockSignals(True)
        sm.clearSelection()
        for row in selected_rows:
            if row < self._model.rowCount():
                sm.select(self._model.index(row), QItemSelectionModel.Select)
        sm.blockSignals(False)

        # Update status
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

        # Scroll to current track after a delay
        QTimer.singleShot(100, self._scroll_to_current_track)

    def _on_cover_ready(self, track_id: str, cover_path: str, qimage):
        """Handle cover loaded — cache it and trigger repaint."""
        # Find the row for this track_id
        track_row = self._find_row_by_cover_key(track_id)

        if qimage and not qimage.isNull():
            pixmap = QPixmap.fromImage(qimage).scaled(
                64, 64,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            CoverPixmapCache.set(track_id, pixmap)
            if track_row is not None:
                # Update blur background if this is the current track
                if track_row == self._model.current_index:
                    full_pixmap = QPixmap.fromImage(qimage)
                    QTimer.singleShot(0, lambda pm=full_pixmap: self._update_bg_blur(pm))
                self._model.notify_cover_loaded(track_row)
        elif track_row is not None:
            # No cover found — mark as failed to prevent infinite re-requests
            self._delegate._failed_covers.add(track_id)
            # Don't call notify_cover_loaded; it would trigger repaint → new worker → loop

    def _find_row_by_cover_key(self, track_id: str):
        """Find row index for a cover cache key."""
        for row in range(self._model.rowCount()):
            track = self._model.get_track_at(row)
            if track and self._delegate._get_cover_cache_key(track) == track_id:
                return row
        return None

    def refresh_queue(self):
        """Refresh the queue display (can be called externally)."""
        self._refresh_queue()

    def _refresh_queue(self):
        """Refresh the queue display."""
        # Update UI texts
        self._update_ui_texts()

        # Get current playlist from engine
        playlist = self._player.engine.playlist
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlaybackState.PLAYING

        # Save current selection
        selected_rows = self._model.get_selected_rows()

        # Reset model (blocks signals internally)
        self._delegate._failed_covers.clear()
        self._list_view.blockSignals(True)
        self._model.reset_tracks(list(playlist), selected_rows=set(selected_rows))
        self._model.set_current(current_index)
        self._model.set_playing(is_playing)
        self._list_view.blockSignals(False)

        # Restore visual selection
        sm = self._list_view.selectionModel()
        sm.blockSignals(True)
        sm.clearSelection()
        for row in selected_rows:
            if row < self._model.rowCount():
                sm.select(self._model.index(row), QItemSelectionModel.Select)
        sm.blockSignals(False)

        # Update status
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

        # Scroll to current track after a short delay
        QTimer.singleShot(100, self._scroll_to_current_track)

    def _update_ui_texts(self):
        """Update UI texts after language change."""
        # Update title
        self._title_label.setText(t("play_queue"))

        # Update create playlist button
        self._create_playlist_btn.setText(t("create_playlist"))

        # Update deduplicate button
        self._dedup_btn.setText(t("smart_deduplicate"))

        # Update clear button
        self._clear_btn.setText(t("clear_queue"))

        # Update status
        playlist = self._player.engine.playlist
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

        # Update hint
        self._hint_label.setText(t("tip_right_click"))

    def _update_current_track_indicator(self):
        """Update the visual indicator for current track."""
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlaybackState.PLAYING
        self._model.set_current(current_index)
        self._model.set_playing(is_playing)

        # Control playing animation
        if is_playing and current_index >= 0:
            self._delegate._start_animation(current_index)
            # Try to set blur background from cached cover
            track = self._model.get_track_at(current_index)
            if track:
                cache_key = self._delegate._get_cover_cache_key(track)
                cached = CoverPixmapCache.get(cache_key)
                if cached:
                    QTimer.singleShot(0, lambda pm=cached: self._update_bg_blur(pm))
        else:
            self._delegate._stop_animation()

    def _update_bg_blur(self, cover_pixmap):
        """Set blurred cover as background via QLabel."""
        if not cover_pixmap or cover_pixmap.isNull():
            self._bg_label.clear()
            return

        # Cheap blur: downscale then upscale
        w = self._list_view.viewport().width()
        h = self._list_view.viewport().height()
        if w < 10 or h < 10:
            return

        small = cover_pixmap.scaled(w // 10, h // 10,
                                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                    Qt.TransformationMode.SmoothTransformation)
        blurred = small.scaled(w, h,
                               Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)

        # Darken for readability
        painter = QPainter(blurred)
        painter.fillRect(blurred.rect(), QColor(0, 0, 0, 180))
        painter.end()

        self._bg_label.setPixmap(blurred)
        self._bg_label.setGeometry(0, 0, w, h)
        self._bg_label.lower()

    def _on_current_track_changed(self, track_dict):
        """Handle current track change."""
        # Check if playlist size changed (indicates new playlist loaded)
        current_size = len(self._player.engine.playlist)
        if current_size != self._last_playlist_size:
            self._last_playlist_size = current_size
            self._refresh_queue()
        else:
            self._update_current_track_indicator()

        # Scroll to current track with delay to ensure UI is updated
        QTimer.singleShot(100, self._scroll_to_current_track)

    def _scroll_to_current_track(self):
        """Scroll to the current playing track."""
        current_index = self._model.current_index
        if 0 <= current_index < self._model.rowCount():
            model_index = self._model.index(current_index)
            self._list_view.scrollTo(model_index, QAbstractItemView.PositionAtCenter)

    def _select_track_by_id(self, track_id: int):
        """
        Select a track by its ID.

        Args:
            track_id: Track ID to select
        """
        for row in range(self._model.rowCount()):
            track = self._model.get_track_at(row)
            if track and isinstance(track, dict):
                if track.get("id") == track_id:
                    sm = self._list_view.selectionModel()
                    sm.clearSelection()
                    sm.select(self._model.index(row), QItemSelectionModel.Select)
                    break

    def _on_player_state_changed(self, state: PlaybackState):
        """Handle player state change (play/pause)."""
        # Update the play/pause icon
        self._update_current_track_indicator()

    def _on_rows_moved(self):
        """Handle row move (drag and drop reorder) - sync engine playlist."""
        # Reload engine playlist from model to keep in sync
        model_items = [self._model.get_track_at(i) for i in range(self._model.rowCount())]

        # Sync by reloading the engine playlist with the new order
        if model_items:
            from domain import PlaylistItem
            items = []
            for item in model_items:
                if isinstance(item, PlaylistItem):
                    items.append(item)
                elif isinstance(item, dict):
                    items.append(PlaylistItem.from_dict(item))
            if items:
                current_idx = self._model.current_index
                # Use reorder_playlist instead of load_playlist_items to preserve playback state
                self._player.engine.reorder_playlist(items, current_idx)
        self.queue_reordered.emit()

    def _on_item_double_clicked(self, index):
        """Handle item double click."""
        self._player.engine.play_at(index.row())

    def _clear_queue(self):
        """Clear the queue."""
        reply = MessageDialog.question(
            self,
            t("clear_queue"),
            t("clear_queue_confirm"),
            Yes | No,
        )

        if reply == Yes:
            self._player.engine.clear_playlist()

    def _remove_selected(self):
        """Remove selected tracks from queue."""
        selected_rows = self._model.get_selected_rows()
        if not selected_rows:
            return

        # Get indices in reverse order to remove from back to front
        rows_to_remove = sorted(selected_rows, reverse=True)

        # Block list widget signals during removal to prevent feedback
        self._list_view.blockSignals(True)

        # Remove from engine playlist
        for row in rows_to_remove:
            self._player.engine.remove_track(row)

        # Unblock signals
        self._list_view.blockSignals(False)

        # Refresh the queue display (will be called automatically by playlist_changed signal,
        # but we also call it here to ensure immediate update)
        self._refresh_queue()

    def _retry_download_selected(self):
        """Retry download for selected failed track."""
        index = self._list_view.currentIndex()
        if not index.isValid():
            return

        track = index.data(QueueTrackModel.TrackRole)
        if not isinstance(track, dict) or not track.get("download_failed", False):
            return

        from system.event_bus import EventBus
        bus = EventBus.instance()
        bus.track_needs_download.emit(track)

    def _play_selected(self):
        """Play the selected track."""
        selected_rows = self._model.get_selected_rows()
        if not selected_rows:
            return

        # Play the first selected track
        row = selected_rows[0]
        self._player.engine.play_at(row)

    def _toggle_favorite_selected(self):
        """Toggle favorite status for selected tracks."""
        selected_rows = self._model.get_selected_rows()
        if not selected_rows:
            return

        track_ids = []
        for row in selected_rows:
            track = self._model.get_track_at(row)
            if track and isinstance(track, dict):
                track_id = track.get("id")
                if track_id:
                    track_ids.append(track_id)

        if not track_ids:
            return

        added_count = 0
        removed_count = 0
        for track_id in track_ids:
            if self._favorite_service.is_favorite(track_id=track_id):
                self._favorite_service.remove_favorite(track_id=track_id)
                removed_count += 1
            else:
                self._favorite_service.add_favorite(track_id=track_id)
                added_count += 1

        if added_count > 0 and removed_count == 0:
            from utils import format_count_message
            message = format_count_message("added_x_tracks_to_favorites", added_count)
            MessageDialog.information(
                self,
                t("added_to_favorites"),
                message,
            )
        elif removed_count > 0 and added_count == 0:
            from utils import format_count_message
            message = format_count_message("removed_x_tracks_from_favorites", removed_count)
            MessageDialog.information(
                self,
                t("removed_from_favorites"),
                message,
            )
        else:
            message = t("added_x_removed_y").format(added=added_count, removed=removed_count)
            MessageDialog.information(
                self,
                t("updated_favorites"),
                message,
            )

    def _show_context_menu(self, pos):
        """Show context menu."""
        index = self._list_view.indexAt(pos)
        if not index.isValid():
            return

        track = index.data(QueueTrackModel.TrackRole)
        is_download_failed = isinstance(track, dict) and track.get("download_failed", False)

        menu = QMenu(self)
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._CONTEXT_MENU_STYLE))

        if is_download_failed:
            retry_action = menu.addAction(t("retry_download"))
            retry_action.triggered.connect(self._retry_download_selected)
            menu.addSeparator()

        # Play action (disabled for failed items)
        play_action = menu.addAction(t("play_now"))
        if is_download_failed:
            play_action.setEnabled(False)
        else:
            play_action.triggered.connect(self._play_selected)

        menu.addSeparator()

        edit_action = menu.addAction(t("edit_media_info"))
        edit_action.triggered.connect(lambda: self._edit_media_info())

        menu.addSeparator()

        # Add to playlist action
        add_to_playlist_action = menu.addAction(t("add_to_playlist"))
        add_to_playlist_action.triggered.connect(self._add_selected_to_playlist)

        menu.addSeparator()

        remove_action = menu.addAction(t("remove_from_queue"))
        remove_action.triggered.connect(self._remove_selected)

        menu.exec_(self._list_view.mapToGlobal(pos))

    def add_tracks(self, track_ids: List[int]):
        """
        Add tracks to the queue.

        Args:
            track_ids: List of track IDs to add
        """
        for track_id in track_ids:
            track = self._library_service.get_track(track_id)
            if track:
                from pathlib import Path
                from domain.track import TrackSource

                # Include online tracks (empty path) and existing local files
                is_online = not track.path or not track.path.strip() or track.source == TrackSource.QQ
                if is_online or Path(track.path).exists():
                    track_dict = {
                        "id": track.id,
                        "path": track.path,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album,
                        "duration": track.duration,
                    }
                    self._player.engine.add_track(track_dict)

    def insert_tracks_after_current(self, track_ids: List[int]):
        """
        Insert tracks after the current playing track.

        Args:
            track_ids: List of track IDs to insert
        """
        # Get current index
        current_index = self._player.engine.current_index

        # Insert position is after current track
        insert_index = current_index + 1 if current_index >= 0 else 0

        for track_id in track_ids:
            track = self._library_service.get_track(track_id)
            if track:
                from pathlib import Path
                from domain.track import TrackSource

                # Include online tracks (empty path) and existing local files
                is_online = not track.path or not track.path.strip() or track.source == TrackSource.QQ
                if is_online or Path(track.path).exists():
                    track_dict = {
                        "id": track.id,
                        "path": track.path,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album,
                        "duration": track.duration,
                    }
                    self._player.engine.insert_track(insert_index, track_dict)
                    insert_index += 1

    def closeEvent(self, event):
        """Handle close event."""
        self._cover_popup.hide()
        event.accept()

    def hideEvent(self, event):
        """Handle hide event."""
        super().hideEvent(event)
        self._cover_popup.hide()
        self._hover_timer.stop()

    def showEvent(self, event):
        """Handle show event - refresh queue when view becomes visible."""
        super().showEvent(event)
        # Refresh queue content and update indicators when the view becomes visible
        QTimer.singleShot(50, self._initialize_view)

    def _edit_media_info(self):
        """Edit media information for selected track."""
        selected_rows = self._model.get_selected_rows()
        if not selected_rows:
            return

        track_ids = []
        for row in selected_rows:
            track = self._model.get_track_at(row)
            if track:
                track_ids.append(track["id"])

        if not track_ids:
            return

        dialog = EditMediaInfoDialog(track_ids, self._library_service, self)
        dialog.tracks_updated.connect(self._on_tracks_updated)
        dialog.exec()

    def _on_tracks_updated(self, track_ids: List[int]):
        """Handle tracks updated event from EditMediaInfoDialog."""
        logger.info(f"Tracks updated {len(track_ids)} tracks")
        # TODO: refresh_tracks_in_table

    def refresh(self):
        """Refresh the queue display."""
        self._refresh_queue()

    def _deduplicate_queue(self):
        """Intelligently deduplicate the queue by removing version duplicates."""
        from domain.playlist_item import PlaylistItem

        # Get current playlist items
        current_playlist = self._player.engine.playlist_items
        if not current_playlist:
            return

        # Show confirmation dialog
        reply = MessageDialog.question(
            self,
            t("smart_deduplicate"),
            t("deduplicate_confirm"),
        )

        if reply != Yes:
            return

        # Perform deduplication
        original_count = len(current_playlist)
        deduplicated = deduplicate_playlist_items(current_playlist)
        new_count = len(deduplicated)

        if new_count == original_count:
            # No duplicates removed
            MessageDialog.information(self, t("info"), t("deduplicate_nothing"))
            return

        # Get currently playing track info before changing playlist
        current_index = self._player.engine.current_index
        current_track = None
        if 0 <= current_index < len(current_playlist):
            current_track = current_playlist[current_index]

        # Build new playlist
        new_playlist = []
        for item in deduplicated:
            if isinstance(item, PlaylistItem):
                new_playlist.append(item.to_dict())
            else:
                new_playlist.append(item)

        # Find new index of currently playing track
        new_current_index = -1
        if current_track:
            current_track_id = current_track.track_id if hasattr(current_track, 'track_id') else current_track.get("id")
            current_cloud_file_id = current_track.cloud_file_id if hasattr(current_track,
                                                                           'cloud_file_id') else current_track.get(
                "cloud_file_id")
            for i, item_dict in enumerate(new_playlist):
                # Match by track_id for local tracks or cloud_file_id for cloud tracks
                if current_track_id and item_dict.get("id") == current_track_id:
                    new_current_index = i
                    break
                elif current_cloud_file_id and item_dict.get("cloud_file_id") == current_cloud_file_id:
                    new_current_index = i
                    break

        # Replace engine playlist
        self._player.engine.load_playlist(new_playlist)

        # Update current index if we found the track
        if new_current_index >= 0:
            self._player.engine._current_index = new_current_index
            self._player.engine._load_track(new_current_index)

        # Show success message
        removed_count = original_count - new_count
        message = t("deduplicate_success").format(removed=removed_count, kept=new_count)
        MessageDialog.information(self, t("success"), message)

        # Notify that queue was reordered (for saving)
        self.queue_reordered.emit()

    def _create_playlist_from_queue(self):
        """Create a new playlist from the current queue."""
        from ui.dialogs.input_dialog import InputDialog

        # Get current playlist items
        playlist_items = self._player.engine.playlist_items
        if not playlist_items:
            MessageDialog.information(self, t("info"), t("queue_is_empty"))
            return

        # Collect track IDs (only local tracks with track_id)
        track_ids = []
        for item in playlist_items:
            # Get track_id from PlaylistItem or dict
            if hasattr(item, 'track_id'):
                track_id = item.track_id
            else:
                track_id = item.get("id") if isinstance(item, dict) else None

            if track_id:
                track_ids.append(track_id)

        if not track_ids:
            MessageDialog.information(self, t("info"), t("no_valid_tracks"))
            return

        # Use InputDialog for playlist name
        name, accepted = InputDialog.getText(
            self,
            t("create_playlist"),
            t("enter_playlist_name")
        )

        if not accepted or not name:
            return

        # Create playlist
        playlist = Playlist(name=name)
        playlist_id = self._playlist_service.create_playlist(playlist)

        # Add tracks to playlist
        added_count = 0
        for track_id in track_ids:
            if self._playlist_service.add_track_to_playlist(playlist_id, track_id):
                added_count += 1

        # Show success message
        message = t("playlist_created_with_tracks").format(
            name=name,
            count=added_count
        )
        MessageDialog.information(self, t("success"), message)

        # Emit event to notify playlist view to refresh
        EventBus.instance().playlist_created.emit(playlist_id)

    def _add_selected_to_playlist(self):
        """Add selected tracks to an existing playlist."""
        selected_rows = self._model.get_selected_rows()
        if not selected_rows:
            return

        # Collect track IDs from selected rows
        track_ids = []
        for row in selected_rows:
            track = self._model.get_track_at(row)
            if track:
                # Get track_id from dict or PlaylistItem
                if isinstance(track, dict):
                    track_id = track.get("id")
                elif hasattr(track, 'track_id'):
                    track_id = track.track_id
                else:
                    track_id = None

                if track_id:
                    track_ids.append(track_id)

        if not track_ids:
            MessageDialog.information(self, t("info"), t("no_valid_tracks"))
            return

        # Use AddToPlaylistDialog
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        dialog = AddToPlaylistDialog(bootstrap.library_service, self)

        # Check if there are playlists
        if not dialog.has_playlists():
            dialog.deleteLater()
            reply = MessageDialog.question(
                self,
                t("no_playlists"),
                t("no_playlists_message"),
                Yes | No,
            )
            if reply == Yes:
                self._create_playlist_from_queue_with_tracks(track_ids)
            return

        # Set track IDs
        dialog.set_track_ids(track_ids)

        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            playlist = dialog.get_selected_playlist()
            if playlist:
                # Add tracks to playlist
                added_count = 0
                duplicate_count = 0
                for track_id in track_ids:
                    if self._playlist_service.add_track_to_playlist(playlist.id, track_id):
                        added_count += 1
                    else:
                        duplicate_count += 1

                # Show result message
                if duplicate_count == 0:
                    message = t("added_tracks_to_playlist").format(
                        count=added_count,
                        name=playlist.name
                    )
                    MessageDialog.information(self, t("success"), message)
                elif added_count == 0:
                    message = t("all_tracks_duplicate").format(
                        count=duplicate_count,
                        name=playlist.name
                    )
                    MessageDialog.warning(self, t("duplicate"), message)
                else:
                    message = t("added_skipped_duplicates").format(
                        added=added_count,
                        duplicates=duplicate_count
                    )
                    MessageDialog.information(self, t("partially_added"), message)

                # Emit event to notify playlist modified
                EventBus.instance().playlist_modified.emit(playlist.id)

    def _create_playlist_from_queue_with_tracks(self, track_ids: list, parent_dialog=None):
        """Create a new playlist with specified track IDs."""
        from ui.dialogs.input_dialog import InputDialog

        # Use InputDialog for playlist name
        name, accepted = InputDialog.getText(
            self,
            t("create_playlist"),
            t("enter_playlist_name")
        )

        if not accepted or not name:
            return

        # Create playlist
        playlist = Playlist(name=name)
        playlist_id = self._playlist_service.create_playlist(playlist)

        # Add tracks to playlist
        added_count = 0
        for track_id in track_ids:
            if self._playlist_service.add_track_to_playlist(playlist_id, track_id):
                added_count += 1

        if parent_dialog:
            parent_dialog.accept()

        # Show success message
        message = t("playlist_created_with_tracks").format(
            name=name,
            count=added_count
        )
        MessageDialog.information(self, t("success"), message)

        # Emit event to notify playlist view to refresh
        EventBus.instance().playlist_created.emit(playlist_id)

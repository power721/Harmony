"""
Queue view for managing the current playback queue.
"""

from typing import List
from pathlib import Path
import logging

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QAbstractListModel, QModelIndex, QRunnable, QThreadPool, QRect, QPoint
from PySide6.QtGui import QColor, QBrush, QPixmap, QPainter, QFont, QImage
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMenu,
    QAbstractItemView,
    QMessageBox,
    QDialog,
    QLineEdit,
    QDialogButtonBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QListView,
)

import hashlib
from infrastructure.cache.pixmap_cache import CoverPixmapCache

from domain.playback import PlaybackState
from services.playback import PlaybackService
from services.library import LibraryService
from services.library.favorites_service import FavoritesService
from ui.dialogs.add_to_playlist_dialog import AddToPlaylistDialog
from services.library.playlist_service import PlaylistService
from domain.playlist import Playlist
from system.i18n import t
from system.event_bus import EventBus
from system.config import ConfigManager
from utils.helpers import format_duration
from utils.dedup import deduplicate_playlist_items, get_version_summary
from app.bootstrap import Bootstrap

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


class CoverLoadWorker(QRunnable):
    """Worker to load cover in background thread."""

    def __init__(self, row: int, load_func, callback_signal):
        super().__init__()
        self.row = row
        self.load_func = load_func
        self.callback_signal = callback_signal
        self.setAutoDelete(True)

    def run(self):
        try:
            cover_path = self.load_func()
            qimage = None
            if cover_path:
                qimage = QImage(cover_path)
            self.callback_signal.emit(self.row, cover_path, qimage)
        except Exception:
            self.callback_signal.emit(self.row, None, None)


class QueueItemDelegate(QStyledItemDelegate):
    """Delegate for painting queue items without per-item QWidget overhead."""

    _cover_loaded_signal = Signal(int, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_loaded_signal.connect(self._on_cover_loaded)
        self._cover_versions: dict = {}
        CoverPixmapCache.initialize()
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

        # Text colors
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

        # Index number
        painter.setPen(secondary_color)
        font = painter.font()
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
        """Paint cover art with caching and async loading."""
        from PySide6.QtGui import QPixmap as Pm

        cache_key = self._get_cover_cache_key(track)

        # Try cache
        cached = CoverPixmapCache.get(cache_key)
        if cached and not cached.isNull():
            painter.drawPixmap(rect, cached)
            return

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
        version = self._cover_versions.get(row, 0) + 1
        self._cover_versions[row] = version
        worker = CoverLoadWorker(row, self._resolve_cover_path, self._cover_loaded_signal)
        # Store version on worker for validation in callback
        worker._version = version
        QThreadPool.globalInstance().start(worker)

    def _on_cover_loaded(self, row: int, cover_path: str, qimage):
        """Handle cover loaded — will be wired up in Task 6."""
        # Stub: full implementation in Task 6
        pass

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
        from PySide6.QtWidgets import QStyle
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, 400, 72)
        option.state = QStyle.StateFlag.State_Enabled
        return option


class QueueItemWidget(QWidget):
    """Custom widget for queue items with cover art."""

    # Signal for cover loaded in background thread
    _cover_loaded = Signal(str, int)

    # Style templates for different states
    _STYLE_SELECTED = """
        QWidget {
            background-color: %highlight%;
        }
    """
    _STYLE_CURRENT = """
        QWidget {
            background-color: transparent;
        }
    """
    _STYLE_NORMAL = """
        QWidget {
            background-color: transparent;
        }
    """

    def __init__(self, track: dict, index: int, is_current: bool, is_playing: bool, highlight_color: str = "#FFD700", parent=None):
        super().__init__(parent)
        self._track = track
        self._index = index
        self._is_current = is_current
        self._is_playing = is_playing
        self._cover_load_version = 0
        self._current_cover_path = None
        self._is_selected = False
        self._highlight_color = highlight_color

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        self._setup_ui()

        # Connect cover loaded signal
        self._cover_loaded.connect(self._on_cover_loaded)

        # Load cover asynchronously
        QTimer.singleShot(50, self._load_cover_async)

    def set_selected(self, selected: bool):
        """Set selection state for the widget."""
        self._is_selected = selected
        self._update_style()

    def refresh_theme(self):
        """Refresh widget style when theme changes."""
        # Update highlight color from theme
        from system.theme import ThemeManager
        self._highlight_color = ThemeManager.instance().current_theme.highlight
        self._update_style()

    def _update_style(self):
        """Update widget style based on current/selected state."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        if self._is_selected:
            # Selected track - use highlight background
            self.setStyleSheet(f"""
                QWidget {{
                    background-color: {self._highlight_color};
                }}
            """)
            self._index_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.background};
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)
            self._title_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.background};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            self._artist_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.background};
                    font-size: 11px;
                }}
            """)
            self._duration_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.background};
                    font-size: 12px;
                }}
            """)
        elif self._is_current:
            # Current playing track - highlight text only
            self.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                }
            """)
            self._index_label.setStyleSheet(f"""
                QLabel {{
                    color: {self._highlight_color};
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)
            self._title_label.setStyleSheet(f"""
                QLabel {{
                    color: {self._highlight_color};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            self._artist_label.setStyleSheet(f"""
                QLabel {{
                    color: {self._highlight_color};
                    font-size: 11px;
                }}
            """)
            self._duration_label.setStyleSheet(f"""
                QLabel {{
                    color: {self._highlight_color};
                    font-size: 12px;
                }}
            """)
        else:
            # Normal state
            self.setStyleSheet("""
                QWidget {
                    background-color: transparent;
                }
            """)
            self._index_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 12px;
                }}
            """)
            self._title_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text};
                    font-size: 13px;
                    font-weight: bold;
                }}
            """)
            self._artist_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 11px;
                }}
            """)
            self._duration_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 12px;
                }}
            """)

    def _setup_ui(self):
        """Setup the item UI."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        # Index label
        self._index_label = QLabel(f"{self._index + 1}")
        self._index_label.setFixedWidth(30)
        layout.addWidget(self._index_label)

        # Cover art
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(64, 64)
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.background_alt};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self._cover_label)

        # Track info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Title
        title = self._track.get("title", t("unknown"))
        if self._is_current:
            icon = "▶ " if self._is_playing else "⏸ "
            title = f"{icon}{title}"

        self._title_label = QLabel(title)
        info_layout.addWidget(self._title_label)

        # Artist and album
        artist = self._track.get("artist", t("unknown"))
        album = self._track.get("album", "")
        artist_album = f"{artist}" + (f" • {album}" if album else "")

        self._artist_label = QLabel(artist_album)
        info_layout.addWidget(self._artist_label)

        layout.addWidget(info_widget, 1)

        # Duration
        duration = format_duration(self._track.get("duration", 0))
        self._duration_label = QLabel(duration)
        layout.addWidget(self._duration_label)

        # Apply initial style
        self._update_style()

    def _load_cover_async(self):
        """Load cover art asynchronously."""
        # Don't reload if already loaded
        if self._current_cover_path:
            return

        def load_cover():
            # Check if this is an online QQ Music track
            source = self._track.get("source", "") or self._track.get("source_type", "")
            cloud_file_id = self._track.get("cloud_file_id", "")
            is_online = source == "QQ" or source == "online"

            if is_online and cloud_file_id:
                # For online QQ Music tracks, get cover directly by song_mid
                try:
                    from app.bootstrap import Bootstrap
                    bootstrap = Bootstrap.instance()
                    if bootstrap and hasattr(bootstrap, 'cover_service'):
                        cover_service = bootstrap.cover_service
                        if cover_service:
                            cover_path = cover_service.get_online_cover(
                                song_mid=cloud_file_id,
                                album_mid=None,
                                artist=self._track.get("artist", ""),
                                title=self._track.get("title", "")
                            )
                            if cover_path:
                                return cover_path
                except Exception as e:
                    logger.debug(f"QueueItem: Error getting online cover: {e}")

            # Check if cover_path is already saved
            cover_path = self._track.get("cover_path")
            if cover_path and Path(cover_path).exists():
                return cover_path

            # Try to get cover from file path
            path = self._track.get("path", "")
            if path and Path(path).exists():
                # Try to get embedded or cached cover
                try:
                    from app.bootstrap import Bootstrap
                    bootstrap = Bootstrap.instance()
                    if bootstrap and hasattr(bootstrap, 'cover_service'):
                        cover_service = bootstrap.cover_service
                        if cover_service:
                            title = self._track.get("title", "")
                            artist = self._track.get("artist", "")
                            album = self._track.get("album", "")
                            cover_path = cover_service.get_cover(
                                path, title, artist, album, skip_online=True
                            )
                            if cover_path:
                                logger.debug(f"QueueItem: Loaded cover from service: {cover_path}")
                                return cover_path
                            else:
                                logger.debug(f"QueueItem: No cover found from service for {title}")
                except Exception as e:
                    logger.debug(f"QueueItem: Error loading cover: {e}")

            return None

        # Run in thread
        from threading import Thread
        self._cover_load_version += 1
        version = self._cover_load_version

        def worker():
            try:
                cover_path = load_cover()
                # Always emit, even if None
                self._cover_loaded.emit(cover_path, version)
            except Exception as e:
                logger.debug(f"QueueItem: Error in cover loading thread: {e}")

        Thread(target=worker, daemon=True).start()

    def _on_cover_loaded(self, cover_path: str, version: int):
        """Handle cover loaded from background thread."""
        if version != self._cover_load_version:
            logger.debug(f"QueueItem: Ignoring stale cover (version {version}, current {self._cover_load_version})")
            return

        if cover_path:
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        64, 64,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                    self._cover_label.setPixmap(scaled_pixmap)
                    self._current_cover_path = cover_path
                else:
                    logger.warning(f"QueueItem: Pixmap is null for {cover_path}")
                    self._set_default_cover()
            except Exception as e:
                logger.error(f"QueueItem: Error showing cover: {e}")
                self._set_default_cover()
        else:
            self._set_default_cover()

    def _set_default_cover(self):
        """Set default cover when no cover is available."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(theme.background_alt))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor(theme.border))

        font = QFont()
        font.setPixelSize(32)
        painter.setFont(font)
        painter.drawText(0, 0, 64, 64, Qt.AlignCenter, "\u266B")
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def update_play_state(self, is_playing: bool):
        """Update the playing state indicator."""
        self._is_playing = is_playing
        title = self._track.get("title", t("unknown"))
        if self._is_current:
            icon = "▶ " if self._is_playing else "⏸ "
            self._title_label.setText(f"{icon}{title}")
        else:
            # Remove icon for non-current tracks
            self._title_label.setText(title)


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
        QListWidget#queueList {
            background-color: %background%;
            border: none;
            outline: none;
            border-radius: 8px;
        }
        QListWidget#queueList::item {
            border-bottom: 1px solid %background_hover%;
            margin: 0px;
            background-color: %background%;
        }
        QListWidget#queueList::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
        QListWidget QScrollBar:vertical {
            background-color: %background%;
            width: 12px;
            border-radius: 6px;
        }
        QListWidget QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 40px;
        }
        QListWidget QScrollBar::handle:vertical:hover {
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

        self._setup_ui()
        self._setup_connections()

        # Load initial queue content and update indicators
        from PySide6.QtCore import QTimer

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

        # Queue list
        self._queue_list = QListWidget()
        self._queue_list.setObjectName("queueList")
        self._queue_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._queue_list.setAlternatingRowColors(False)  # Disable alternating colors since we handle it
        self._queue_list.setDragDropMode(QAbstractItemView.InternalMove)
        self._queue_list.model().rowsMoved.connect(self._on_rows_moved)
        self._queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._queue_list.customContextMenuRequested.connect(self._show_context_menu)
        self._queue_list.itemDoubleClicked.connect(self._play_selected)
        self._queue_list.setFocusPolicy(Qt.NoFocus)  # Remove focus frame
        layout.addWidget(self._queue_list)

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

        # Refresh all queue item widgets
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            widget = self._queue_list.itemWidget(item)
            if widget and hasattr(widget, 'refresh_theme'):
                widget.refresh_theme()

    def _setup_connections(self):
        """Setup signal connections."""
        # Connect to engine signals to update current track indicator
        self._player.engine.current_track_changed.connect(
            self._on_current_track_changed
        )
        self._player.engine.state_changed.connect(self._on_player_state_changed)
        self._player.engine.playlist_changed.connect(self._refresh_queue)

        # Connect to selection changes to update widget styles
        self._queue_list.itemSelectionChanged.connect(self._on_selection_changed)

        # Track playlist size to detect playlist changes
        self._last_playlist_size = 0

    def _on_selection_changed(self):
        """Handle selection changes to update widget styles."""
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            widget = self._queue_list.itemWidget(item)
            if widget and isinstance(widget, QueueItemWidget):
                widget.set_selected(item.isSelected())

    def _initialize_view(self):
        """Initialize the queue view with current content and indicators."""
        # Get current playlist from engine
        playlist = self._player.engine.playlist
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlaybackState.PLAYING

        # Update last known playlist size
        self._last_playlist_size = len(playlist)

        # Save current selection
        selected_items = self._queue_list.selectedItems()
        selected_indices = [self._queue_list.row(item) for item in selected_items]

        # Block signals to prevent feedback
        self._queue_list.blockSignals(True)

        # Clear and repopulate
        self._queue_list.clear()

        for i, track in enumerate(playlist):
            is_current = (i == current_index)

            # Create list item
            item = QListWidgetItem()
            item.setData(Qt.UserRole, track)
            item.setSizeHint(QSize(0, 84))  # Set item height (64px cover + padding)

            # Create custom widget
            widget = QueueItemWidget(track, i, is_current, is_playing, self._highlight_color)

            # Add item to list
            self._queue_list.addItem(item)
            self._queue_list.setItemWidget(item, widget)

            # Mark current track
            if is_current:
                item.setData(Qt.UserRole + 1, True)

        # Restore selection
        for row in selected_indices:
            if row < self._queue_list.count():
                item = self._queue_list.item(row)
                item.setSelected(True)
                # Manually update widget selection state since signals are blocked
                widget = self._queue_list.itemWidget(item)
                if widget and isinstance(widget, QueueItemWidget):
                    widget.set_selected(True)

        self._queue_list.blockSignals(False)

        # Update status
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

        # Scroll to current track after a delay
        QTimer.singleShot(100, self._scroll_to_current_track)

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
        selected_items = self._queue_list.selectedItems()
        selected_indices = [self._queue_list.row(item) for item in selected_items]

        # Block signals to prevent feedback
        self._queue_list.blockSignals(True)

        # Clear and repopulate
        self._queue_list.clear()

        for i, track in enumerate(playlist):
            is_current = (i == current_index)

            # Create list item
            item = QListWidgetItem()
            item.setData(Qt.UserRole, track)
            item.setSizeHint(QSize(0, 84))  # Set item height (64px cover + padding)

            # Create custom widget
            widget = QueueItemWidget(track, i, is_current, is_playing, self._highlight_color)

            # Add item to list
            self._queue_list.addItem(item)
            self._queue_list.setItemWidget(item, widget)

            # Mark current track
            if is_current:
                item.setData(Qt.UserRole + 1, True)

        # Restore selection
        for row in selected_indices:
            if row < self._queue_list.count():
                item = self._queue_list.item(row)
                item.setSelected(True)
                # Manually update widget selection state since signals are blocked
                widget = self._queue_list.itemWidget(item)
                if widget and isinstance(widget, QueueItemWidget):
                    widget.set_selected(True)

        self._queue_list.blockSignals(False)

        # Update current track styling
        self._update_current_track_indicator()

        # Scroll to current track after a short delay
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._scroll_to_current_track)

        # Update status
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

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

        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            widget = self._queue_list.itemWidget(item)

            if i == current_index:
                item.setData(Qt.UserRole + 1, True)
                # Set current property for QSS selector
                item.setData(Qt.UserRole + 2, "true")
                # Update widget to show current state
                if widget and isinstance(widget, QueueItemWidget):
                    widget._is_current = True
                    widget._is_playing = is_playing
                    widget.update_play_state(is_playing)
                    widget._update_style()
            else:
                item.setData(Qt.UserRole + 1, False)
                item.setData(Qt.UserRole + 2, "false")
                # Update widget to show non-current state
                if widget and isinstance(widget, QueueItemWidget):
                    widget._is_current = False
                    widget._is_playing = False
                    widget.update_play_state(False)
                    widget._update_style()

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
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._scroll_to_current_track)

    def _scroll_to_current_track(self):
        """Scroll to the current playing track."""
        current_index = self._player.engine.current_index
        if 0 <= current_index < self._queue_list.count():
            item = self._queue_list.item(current_index)
            if item:
                self._queue_list.scrollToItem(item, QListWidget.PositionAtCenter)

    def _select_track_by_id(self, track_id: int):
        """
        Select a track by its ID.

        Args:
            track_id: Track ID to select
        """
        # Find the item with the track
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item:
                track = item.data(Qt.UserRole)
                if track and isinstance(track, dict):
                    item_track_id = track.get("id")
                    if item_track_id == track_id:
                        # Clear previous selection
                        self._queue_list.clearSelection()
                        # Select the item
                        item.setSelected(True)
                        break

    def _on_player_state_changed(self, state: PlaybackState):
        """Handle player state change (play/pause)."""
        # Update the play/pause icon
        self._update_current_track_indicator()

    def _on_rows_moved(self):
        """Handle row move (drag and drop reorder)."""
        from domain.playlist_item import PlaylistItem

        # Get current track info before reordering
        current_index = self._player.engine.current_index
        current_track = None
        if 0 <= current_index < len(self._player.engine.playlist):
            current_track = self._player.engine.playlist[current_index]

        # Build new playlist from current list order
        new_playlist = []
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            track = item.data(Qt.UserRole)
            if track:
                new_playlist.append(track)

        # Find new index of currently playing track
        new_current_index = -1
        if current_track:
            current_track_id = current_track.get("id")
            current_cloud_file_id = current_track.get("cloud_file_id")
            for i, track in enumerate(new_playlist):
                # Match by track_id for local tracks or cloud_file_id for cloud tracks
                if current_track_id and track.get("id") == current_track_id:
                    new_current_index = i
                    break
                elif current_cloud_file_id and track.get("cloud_file_id") == current_cloud_file_id:
                    new_current_index = i
                    break

        # Convert to PlaylistItem list
        new_items = []
        for track in new_playlist:
            if isinstance(track, PlaylistItem):
                new_items.append(track)
            else:
                new_items.append(PlaylistItem.from_dict(track))

        # Update engine playlist directly without resetting state
        self._player.engine._playlist = new_items
        self._player.engine._original_playlist = new_items.copy()

        # Update current index if we found the track
        if new_current_index >= 0:
            self._player.engine._current_index = new_current_index

        # Emit signal to notify that queue was reordered (for saving)
        self.queue_reordered.emit()

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle item double click."""
        track = item.data(Qt.UserRole)
        if track:
            track_id = track.get("id")
            if track_id:
                self.play_track.emit(track_id)

    def _clear_queue(self):
        """Clear the queue."""
        reply = QMessageBox.question(
            self,
            t("clear_queue"),
            t("clear_queue_confirm"),
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._player.engine.clear_playlist()

    def _remove_selected(self):
        """Remove selected tracks from queue."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        # Get indices in reverse order to remove from back to front
        rows_to_remove = sorted(
            [self._queue_list.row(item) for item in selected_items], reverse=True
        )

        # Block list widget signals during removal to prevent feedback
        self._queue_list.blockSignals(True)

        # Remove from engine playlist
        for row in rows_to_remove:
            self._player.engine.remove_track(row)

        # Unblock signals
        self._queue_list.blockSignals(False)

        # Refresh the queue display (will be called automatically by playlist_changed signal,
        # but we also call it here to ensure immediate update)
        self._refresh_queue()

    def _play_selected(self):
        """Play the selected track."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        # Play the first selected track
        item = selected_items[0]
        track = item.data(Qt.UserRole)
        if track:
            row = self._queue_list.row(item)
            self._player.engine.play_at(row)

    def _toggle_favorite_selected(self):
        """Toggle favorite status for selected tracks."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            track = item.data(Qt.UserRole)
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
            QMessageBox.information(
                self,
                t("added_to_favorites"),
                message,
            )
        elif removed_count > 0 and added_count == 0:
            from utils import format_count_message
            message = format_count_message("removed_x_tracks_from_favorites", removed_count)
            QMessageBox.information(
                self,
                t("removed_from_favorites"),
                message,
            )
        else:
            message = t("added_x_removed_y").format(added=added_count, removed=removed_count)
            QMessageBox.information(
                self,
                t("updated_favorites"),
                message,
            )

    def _show_context_menu(self, pos):
        """Show context menu."""
        item = self._queue_list.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._CONTEXT_MENU_STYLE))

        # Play action
        play_action = menu.addAction(t("play_now"))
        play_action.triggered.connect(self._play_selected)

        menu.addSeparator()

        # Add to playlist action
        add_to_playlist_action = menu.addAction(t("add_to_playlist"))
        add_to_playlist_action.triggered.connect(self._add_selected_to_playlist)

        remove_action = menu.addAction(t("remove_from_queue"))
        remove_action.triggered.connect(self._remove_selected)

        menu.exec_(self._queue_list.mapToGlobal(pos))

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
        event.accept()

    def showEvent(self, event):
        """Handle show event - refresh queue when view becomes visible."""
        super().showEvent(event)
        # Refresh queue content and update indicators when the view becomes visible
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._initialize_view)

    def _edit_media_info(self):
        """Edit media information for selected track."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QFormLayout,
            QLabel,
            QLineEdit,
            QDialogButtonBox,
        )
        from services import MetadataService

        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        track = item.data(Qt.UserRole)

        if not track or not isinstance(track, dict):
            return

        track_id = track.get("id")
        if not track_id:
            return

        track = self._library_service.get_track(track_id)
        if not track:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(t("edit_media_info_title"))
        dialog.setMinimumWidth(450)
        from system.theme import ThemeManager
        dialog.setStyleSheet(ThemeManager.instance().get_qss(self._EDIT_DIALOG_STYLE))

        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        title_input = QLineEdit(track.title or "")
        title_input.setPlaceholderText(t("enter_title"))
        artist_input = QLineEdit(track.artist or "")
        artist_input.setPlaceholderText(t("enter_artist"))
        album_input = QLineEdit(track.album or "")
        album_input.setPlaceholderText(t("enter_album"))

        path_label = QLabel(track.path)
        theme = ThemeManager.instance().current_theme
        path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
        path_label.setWordWrap(True)

        form_layout.addRow(t("title") + ":", title_input)
        form_layout.addRow(t("artist") + ":", artist_input)
        form_layout.addRow(t("album") + ":", album_input)
        form_layout.addRow(t("file") + ":", path_label)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox()
        ok_button = QPushButton(t("save"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(buttons)

        def save_changes():
            new_title = title_input.text().strip() or track.title
            new_artist = artist_input.text().strip() or track.artist
            new_album = album_input.text().strip() or track.album

            success = MetadataService.save_metadata(
                track.path, title=new_title, artist=new_artist, album=new_album
            )

            if success:
                track.title = new_title
                track.artist = new_artist
                track.album = new_album
                self._library_service.update_track(track)
                # Emit metadata_updated signal to update play_queue
                EventBus.instance().metadata_updated.emit(track_id)
                QMessageBox.information(self, t("success"), t("media_saved"))
                self.refresh()
            else:
                QMessageBox.warning(self, "Error", t("media_save_failed"))

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

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
        reply = QMessageBox.question(
            self,
            t("smart_deduplicate"),
            t("deduplicate_confirm"),
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            return

        # Perform deduplication
        original_count = len(current_playlist)
        deduplicated = deduplicate_playlist_items(current_playlist)
        new_count = len(deduplicated)

        if new_count == original_count:
            # No duplicates removed
            QMessageBox.information(self, t("info"), t("deduplicate_nothing"))
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
            current_cloud_file_id = current_track.cloud_file_id if hasattr(current_track, 'cloud_file_id') else current_track.get("cloud_file_id")
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
        QMessageBox.information(self, t("success"), message)

        # Notify that queue was reordered (for saving)
        self.queue_reordered.emit()

    def _create_playlist_from_queue(self):
        """Create a new playlist from the current queue."""
        # Get current playlist items
        playlist_items = self._player.engine.playlist_items
        if not playlist_items:
            QMessageBox.information(self, t("info"), t("queue_is_empty"))
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
            QMessageBox.information(self, t("info"), t("no_valid_tracks"))
            return

        # Show input dialog for playlist name
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        dialog = QDialog(self)
        dialog.setWindowTitle(t("create_playlist"))
        dialog.setMinimumWidth(350)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.background_alt};
                color: {theme.text};
            }}
            QLabel {{
                color: {theme.text};
            }}
            QLineEdit {{
                background-color: {theme.background_hover};
                color: {theme.text};
                border: 1px solid {theme.border};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.highlight};
            }}
            QPushButton {{
                background-color: {theme.highlight};
                color: {theme.background};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {theme.highlight_hover};
            }}
            QPushButton[role="cancel"] {{
                background-color: {theme.border};
                color: {theme.text};
            }}
            QPushButton[role="cancel"]:hover {{
                background-color: {theme.background_hover};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        label = QLabel(t("enter_playlist_name"))
        layout.addWidget(label)

        input_field = QLineEdit()
        layout.addWidget(input_field)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton(t("ok"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)

        def on_accept():
            name = input_field.text().strip()
            if not name:
                QMessageBox.warning(dialog, t("warning"), t("enter_playlist_name"))
                return

            # Create playlist
            playlist = Playlist(name=name)
            playlist_id = self._playlist_service.create_playlist(playlist)

            # Add tracks to playlist
            added_count = 0
            for track_id in track_ids:
                if self._playlist_service.add_track_to_playlist(playlist_id, track_id):
                    added_count += 1

            dialog.accept()

            # Show success message
            message = t("playlist_created_with_tracks").format(
                name=name,
                count=added_count
            )
            QMessageBox.information(self, t("success"), message)

            # Emit event to notify playlist view to refresh
            EventBus.instance().playlist_created.emit(playlist_id)

        ok_button.clicked.connect(on_accept)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

    def _add_selected_to_playlist(self):
        """Add selected tracks to an existing playlist."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        # Collect track IDs from selected items
        track_ids = []
        for item in selected_items:
            track = item.data(Qt.UserRole)
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
            QMessageBox.information(self, t("info"), t("no_valid_tracks"))
            return

        # Use AddToPlaylistDialog
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        dialog = AddToPlaylistDialog(bootstrap.library_service, self)

        # Check if there are playlists
        if not dialog.has_playlists():
            dialog.deleteLater()
            reply = QMessageBox.question(
                self,
                t("no_playlists"),
                t("no_playlists_message"),
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
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
                    QMessageBox.information(self, t("success"), message)
                elif added_count == 0:
                    message = t("all_tracks_duplicate").format(
                        count=duplicate_count,
                        name=playlist.name
                    )
                    QMessageBox.warning(self, t("duplicate"), message)
                else:
                    message = t("added_skipped_duplicates").format(
                        added=added_count,
                        duplicates=duplicate_count
                    )
                    QMessageBox.information(self, t("partially_added"), message)

                # Emit event to notify playlist modified
                EventBus.instance().playlist_modified.emit(playlist.id)

    def _create_playlist_from_queue_with_tracks(self, track_ids: list, parent_dialog=None):
        """Create a new playlist with specified track IDs."""
        # Show input dialog for playlist name
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        dialog = QDialog(self)
        dialog.setWindowTitle(t("create_playlist"))
        dialog.setMinimumWidth(350)
        dialog.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.background_alt};
                color: {theme.text};
            }}
            QLabel {{
                color: {theme.text};
            }}
            QLineEdit {{
                background-color: {theme.background_hover};
                color: {theme.text};
                border: 1px solid {theme.border};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit:focus {{
                border: 1px solid {theme.highlight};
            }}
            QPushButton {{
                background-color: {theme.highlight};
                color: {theme.background};
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
                min-width: 80px;
            }}
            QPushButton:hover {{
                background-color: {theme.highlight_hover};
            }}
            QPushButton[role="cancel"] {{
                background-color: {theme.border};
                color: {theme.text};
            }}
            QPushButton[role="cancel"]:hover {{
                background-color: {theme.background_hover};
            }}
        """)

        layout = QVBoxLayout(dialog)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        label = QLabel(t("enter_playlist_name"))
        layout.addWidget(label)

        input_field = QLineEdit()
        layout.addWidget(input_field)

        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton(t("ok"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)

        def on_accept():
            name = input_field.text().strip()
            if not name:
                QMessageBox.warning(dialog, t("warning"), t("enter_playlist_name"))
                return

            # Create playlist
            playlist = Playlist(name=name)
            playlist_id = self._playlist_service.create_playlist(playlist)

            # Add tracks to playlist
            added_count = 0
            for track_id in track_ids:
                if self._playlist_service.add_track_to_playlist(playlist_id, track_id):
                    added_count += 1

            dialog.accept()
            if parent_dialog:
                parent_dialog.accept()

            # Show success message
            message = t("playlist_created_with_tracks").format(
                name=name,
                count=added_count
            )
            QMessageBox.information(self, t("success"), message)

            # Emit event to notify playlist view to refresh
            EventBus.instance().playlist_created.emit(playlist_id)

        ok_button.clicked.connect(on_accept)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()


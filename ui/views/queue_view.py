"""
Queue view for managing the current playback queue.
"""

from typing import List
from pathlib import Path
import logging

from PySide6.QtCore import Qt, Signal, QTimer, QSize, QAbstractListModel, QModelIndex, QRunnable, QThreadPool, QRect, QPoint, QItemSelectionModel
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
        self._list_view = QListView()
        self._list_view.setObjectName("queueList")
        self._model = QueueTrackModel(self)
        self._delegate = QueueItemDelegate(self._list_view)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._list_view.setDragDropMode(QAbstractItemView.InternalMove)
        self._list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.doubleClicked.connect(self._on_item_double_clicked)
        self._list_view.setSpacing(0)
        self._list_view.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list_view.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self._list_view)

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
        from PySide6.QtCore import QTimer

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
        """Handle row move (drag and drop reorder)."""
        # This won't be auto-triggered since we don't have QListWidget rowsMoved.
        # Drag-drop with QListView needs different handling.
        # For now, keep the method as a no-op stub.
        # Will be properly implemented if drag-drop is needed.
        pass

    def _on_item_double_clicked(self, index):
        """Handle item double click."""
        track = self._model.get_track_at(index.row())
        if track:
            track_id = track.get("id") if isinstance(track, dict) else None
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
        index = self._list_view.indexAt(pos)
        if not index.isValid():
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

        selected_rows = self._model.get_selected_rows()
        if not selected_rows:
            return

        track = self._model.get_track_at(selected_rows[0])

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


"""
Online tracks list view for displaying online music tracks.
"""

import logging
from typing import List

from PySide6.QtCore import Qt, Signal, QSize, QTimer, QPoint, QAbstractListModel, QModelIndex, QRunnable, QThreadPool, QRect
from PySide6.QtGui import QColor, QPainter, QImage, QCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListView, QStyledItemDelegate, QStyleOptionViewItem, QStyle

from domain import TrackSource
from domain.online_music import OnlineTrack
from infrastructure.cache.pixmap_cache import CoverPixmapCache
from system import t
from system.event_bus import EventBus
from ui.views.cover_hover_popup import CoverHoverPopup
from ui.widgets.context_menus import OnlineTrackContextMenu
from utils.helpers import format_duration

logger = logging.getLogger(__name__)


def _resolve_online_cover_path(track: OnlineTrack) -> str | None:
    """Resolve online cover for QQ music track."""
    if not track:
        return None

    try:
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        if bootstrap and hasattr(bootstrap, 'cover_service'):
            return bootstrap.cover_service.get_online_cover(
                song_mid=track.mid,
                album_mid=None,
                artist=track.singer_name,
                title=track.title,
            )
    except Exception:
        pass

    return None


class OnlineTracksModel(QAbstractListModel):
    """QAbstractListModel for online track data."""

    TrackRole = Qt.UserRole + 1
    CoverRole = Qt.UserRole + 2
    IsFavoriteRole = Qt.UserRole + 3
    RankRole = Qt.UserRole + 4
    IsVipRole = Qt.UserRole + 5
    IndexRole = Qt.UserRole + 6

    cover_ready = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: List[OnlineTrack] = []
        self._favorite_mids: set = set()  # QQ music song mids

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
        elif role == self.IsFavoriteRole:
            return track.mid in self._favorite_mids if track else False
        elif role == self.RankRole:
            return row + 1
        elif role == self.IsVipRole:
            return track.pay_play if track else False
        elif role == self.IndexRole:
            return row
        return None

    def roleNames(self):
        return {
            Qt.DisplayRole: b"display",
            self.TrackRole: b"track",
            self.CoverRole: b"cover",
            self.IsFavoriteRole: b"favorite",
            self.RankRole: b"rank",
            self.IsVipRole: b"vip",
            self.IndexRole: b"index",
        }

    def reset_tracks(self, tracks: List[OnlineTrack], favorite_mids: set):
        self.beginResetModel()
        self._tracks = list(tracks)
        self._favorite_mids = set(favorite_mids)
        self.endResetModel()

    def update_favorites(self, favorite_mids: set):
        """Update favorite MIDs and emit dataChanged for affected rows."""
        old_favs = self._favorite_mids
        self._favorite_mids = set(favorite_mids)

        # Find rows that changed
        for i, track in enumerate(self._tracks):
            if track and (track.mid in old_favs) != (track.mid in self._favorite_mids):
                idx = self.index(i)
                self.dataChanged.emit(idx, idx, [self.IsFavoriteRole])

    def get_track_at(self, row: int):
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def notify_cover_loaded(self, row: int):
        if 0 <= row < len(self._tracks):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [self.CoverRole])


class OnlineCoverLoadWorker(QRunnable):
    """Worker to load online cover in background thread."""

    def __init__(self, cache_key: str, track: OnlineTrack, callback_signal):
        super().__init__()
        self.cache_key = cache_key
        self.track = track
        self.callback_signal = callback_signal
        self.setAutoDelete(True)

    def run(self):
        try:
            cover_path = self._resolve_online_cover()
            qimage = None
            if cover_path:
                qimage = QImage(cover_path)
            try:
                self.callback_signal.emit(self.cache_key, cover_path, qimage)
            except RuntimeError:
                pass  # signal source deleted
        except Exception:
            pass

    def _resolve_online_cover(self) -> str | None:
        """Resolve online cover for QQ music track."""
        return _resolve_online_cover_path(self.track)


class OnlineTracksDelegate(QStyledItemDelegate):
    """Delegate for painting online track items without per-item QWidget overhead."""

    _cover_loaded_signal = Signal(str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_loaded_signal.connect(self._on_cover_loaded)
        self._requested_covers: set = set()
        self._failed_covers: set = set()
        CoverPixmapCache.initialize()
        self._cover_size = 64
        self._rank_width = 50
        self._padding = 10
        self._star_size = 20

    def sizeHint(self, option, index):
        return QSize(0, 82)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Skip off-screen items
        parent_view = self.parent()
        if parent_view and (option.rect.bottom() < 0 or option.rect.top() > parent_view.height()):
            return

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        track = index.data(OnlineTracksModel.TrackRole)
        is_favorite = index.data(OnlineTracksModel.IsFavoriteRole)
        rank = index.data(OnlineTracksModel.RankRole)
        is_vip = index.data(OnlineTracksModel.IsVipRole)
        row = index.data(OnlineTracksModel.IndexRole)

        if not track:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect

        # Background
        is_hovered = option.state & QStyle.StateFlag.State_MouseOver
        is_selected = option.state & QStyle.StateFlag.State_Selected

        if is_selected:
            painter.fillRect(rect, QColor(theme.highlight))
        elif is_hovered:
            hover_bg = QColor(theme.background_hover)
            hover_bg.setAlpha(220)
            painter.fillRect(rect, hover_bg)
            # Hand cursor on hover
            if self.parent():
                self.parent().setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            bg = QColor(theme.background)
            bg.setAlpha(220)
            painter.fillRect(rect, bg)

        # Separator line
        if not is_selected:
            painter.setPen(QColor(theme.background_hover))
            painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # Text colors
        if is_selected:
            text_color = QColor(theme.background)
            secondary_color = QColor(theme.background)
        elif is_vip:
            # VIP tracks: gold title
            text_color = QColor("#FFD700")
            secondary_color = QColor(theme.text_secondary)
        else:
            text_color = QColor(theme.text)
            secondary_color = QColor(theme.text_secondary)

        x = rect.left() + self._padding

        # Index number
        painter.setPen(secondary_color)
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(False)
        painter.setFont(font)

        painter.drawText(x, rect.top(), self._rank_width, rect.height(),
                         Qt.AlignVCenter | Qt.AlignHCenter, str(rank))
        x += self._rank_width

        # Cover art
        cover_rect = QRect(x + 2, rect.top() + 9, self._cover_size, self._cover_size)
        self._paint_cover(painter, cover_rect, track, row, theme)
        x += self._cover_size + 12

        # Title (with VIP indicator)
        title = track.title or "Unknown"
        if is_vip:
            title = f"VIP {title}"

        painter.setPen(text_color)
        font.setPixelSize(15)
        font.setBold(True)
        painter.setFont(font)
        title_rect = QRect(x, rect.top() + 10, rect.right() - x - 100, 22)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, title, title_rect.width()))

        # Artist + Album
        artist = track.singer_name or "Unknown"
        album = track.album_name or ""
        artist_album = artist + (f" • {album}" if album else "")

        painter.setPen(secondary_color)
        font.setPixelSize(13)
        font.setBold(False)
        painter.setFont(font)
        info_rect = QRect(x, rect.top() + 32, rect.right() - x - 100, 20)
        painter.drawText(info_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, artist_album, info_rect.width()))

        # Source indicator (QQ Music)
        source_text = t("source_qq")
        painter.setPen(secondary_color)
        font.setPixelSize(11)
        font.setBold(False)
        painter.setFont(font)
        source_rect = QRect(x, rect.top() + 52, rect.right() - x - 100, 16)
        painter.drawText(source_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, source_text, source_rect.width()))

        # Duration
        duration = track.duration or 0
        duration_text = format_duration(duration)
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(rect.right() - self._padding - 50 - self._star_size - 10, rect.top(), 50, rect.height(),
                         Qt.AlignVCenter | Qt.AlignRight, duration_text)

        painter.restore()

    def _paint_cover(self, painter: QPainter, rect: QRect, track: OnlineTrack, row: int, theme):
        """Paint cover art with caching and async loading."""
        from PySide6.QtGui import QPixmap as Pm

        cache_key = self._get_cover_cache_key(track)

        # Try cache
        cached = CoverPixmapCache.get(cache_key)
        if cached and not cached.isNull():
            painter.drawPixmap(rect, cached)
        else:
            # Draw placeholder
            placeholder = Pm(self._cover_size, self._cover_size)
            placeholder.fill(QColor(theme.background_alt))
            p = QPainter(placeholder)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(QColor(theme.border))
            font = p.font()
            font.setPixelSize(28)
            p.setFont(font)
            p.drawText(0, 0, self._cover_size, self._cover_size, Qt.AlignCenter, "♪")
            p.end()
            painter.drawPixmap(rect, placeholder)

            # Request async load
            if cache_key not in self._requested_covers and cache_key not in self._failed_covers:
                self._requested_covers.add(cache_key)
                worker = OnlineCoverLoadWorker(cache_key, track, self._cover_loaded_signal)
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
                            worker = OnlineCoverLoadWorker(nearby_key, nearby_track, self._cover_loaded_signal)
                            QThreadPool.globalInstance().start(worker)

    def _on_cover_loaded(self, cache_key: str, cover_path: str, qimage):
        """Handle cover loaded from background — runs on UI thread."""
        self._requested_covers.discard(cache_key)

        parent_view = self.parent()
        if parent_view and hasattr(parent_view, '_on_cover_ready'):
            parent_view._on_cover_ready(cache_key, cover_path, qimage)

    def _get_cover_cache_key(self, track: OnlineTrack) -> str:
        """Generate cache key for an online track."""
        return f"{TrackSource.QQ.name}:{track.mid}"

    def cover_rect_for_item(self, item_rect: QRect) -> QRect:
        """Return the clickable cover rectangle for an item."""
        x = item_rect.left() + self._padding + self._rank_width
        return QRect(x + 2, item_rect.top() + 9, self._cover_size, self._cover_size)

    @staticmethod
    def _elided_text(painter, text: str, max_width: int) -> str:
        """Return elided text if too wide."""
        fm = painter.fontMetrics()
        if fm.horizontalAdvance(text) <= max_width:
            return text
        return fm.elidedText(text, Qt.ElideRight, max_width)


class OnlineTracksListView(QWidget):
    """List view for online tracks with delegate-based rendering."""

    track_activated = Signal(object)  # OnlineTrack
    favorite_toggled = Signal(object, bool)  # OnlineTrack, is_favorite
    play_requested = Signal(list)
    insert_to_queue_requested = Signal(list)
    add_to_queue_requested = Signal(list)
    add_to_playlist_requested = Signal(list)
    favorites_toggle_requested = Signal(list, bool)  # (tracks, all_favorited)
    qq_fav_toggle_requested = Signal(list, bool)  # (tracks, all_favorited) - QQ Music remote
    download_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = OnlineTracksModel(self)
        self._delegate = OnlineTracksDelegate(self)
        self._cover_popup = CoverHoverPopup()
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_cover_popup)
        self._hovered_row = -1
        self._last_cover_pos = QPoint()
        self._setup_ui()
        self._setup_connections()
        self._context_menu = OnlineTrackContextMenu(self)
        self._connect_context_menu()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list_view = QListView()
        self._apply_viewport_bg()
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self._list_view.setSelectionBehavior(QListView.SelectionBehavior.SelectRows)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.setMouseTracking(True)
        self._list_view.viewport().installEventFilter(self)
        self._list_view.setUniformItemSizes(True)
        self._list_view.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)

        layout.addWidget(self._list_view)

    def _setup_connections(self):
        self._list_view.activated.connect(self._on_item_activated)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.clicked.connect(self._on_item_clicked)

        # Event bus
        bus = EventBus.instance()
        bus.favorite_changed.connect(self._on_favorite_changed)

    def closeEvent(self, event):
        """Clean up event bus connections before closing."""
        try:
            EventBus.instance().favorite_changed.disconnect(self._on_favorite_changed)
        except RuntimeError:
            pass
        self._hover_timer.stop()
        self._cover_popup.hide()
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        """Filter viewport events to drive cover hover popup."""
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
        item_rect = self._list_view.visualRect(index)
        cover_rect = self._delegate.cover_rect_for_item(item_rect)

        if cover_rect.contains(pos):
            if self._hovered_row != row:
                self._hovered_row = row
                self._last_cover_pos = QCursor.pos()
                self._hover_timer.start(500)
            else:
                self._cover_popup.cancel_hide()
        else:
            self._handle_mouse_leave()

    def _handle_mouse_leave(self):
        """Handle mouse leaving cover hover area."""
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

        cache_key = self._delegate._get_cover_cache_key(track)
        cover_path = _resolve_online_cover_path(track)
        self._cover_popup.show_cover(cover_path, cache_key, self._last_cover_pos)

    def _on_item_activated(self, index):
        track = index.data(OnlineTracksModel.TrackRole)
        if track:
            self.track_activated.emit(track)

    def _on_item_clicked(self, index):
        """Handle click events - check if star icon was clicked."""
        from PySide6.QtGui import QCursor

        # Get click position
        pos = self._list_view.mapFromGlobal(QCursor.pos())
        rect = self._list_view.visualRect(index)

        # Check if click is in star icon area
        star_size = 20
        padding = 10
        star_area = QRect(
            rect.right() - padding - star_size,
            rect.top(),
            star_size + padding,
            rect.height()
        )

        if star_area.contains(pos):
            # Toggle favorite
            track = index.data(OnlineTracksModel.TrackRole)
            if track:
                is_favorite = index.data(OnlineTracksModel.IsFavoriteRole)
                self._toggle_favorite(track, not is_favorite)

    def _toggle_favorite(self, track: OnlineTrack, new_state: bool):
        """Toggle favorite status for online track."""
        self.favorite_toggled.emit(track, new_state)

    def set_track_favorite(self, mid: str, is_favorite: bool):
        """Update favorite status for a specific track and refresh UI."""
        if is_favorite:
            self._model._favorite_mids.add(mid)
        else:
            self._model._favorite_mids.discard(mid)
        for i, track in enumerate(self._model._tracks):
            if track.mid == mid:
                idx = self._model.index(i)
                self._model.dataChanged.emit(idx, idx, [OnlineTracksModel.IsFavoriteRole])
                break

    def _connect_context_menu(self):
        self._context_menu.play.connect(self.play_requested)
        self._context_menu.insert_to_queue.connect(self.insert_to_queue_requested)
        self._context_menu.add_to_queue.connect(self.add_to_queue_requested)
        self._context_menu.add_to_playlist.connect(self.add_to_playlist_requested)
        self._context_menu.favorite_toggled.connect(self.favorites_toggle_requested)
        self._context_menu.qq_fav_toggled.connect(self.qq_fav_toggle_requested)
        self._context_menu.download.connect(self.download_requested)

    def _show_context_menu(self, pos):
        """Show context menu."""
        indexes = self._list_view.selectedIndexes()
        if not indexes:
            return

        rows = sorted(set(idx.row() for idx in indexes))
        tracks = [self._model.get_track_at(r) for r in rows]
        tracks = [t for t in tracks if t is not None]

        if not tracks:
            return

        self._context_menu.show_menu(tracks, favorite_mids=self._model._favorite_mids, parent_widget=self)

    def _on_favorite_changed(self, item_id, is_favorite: bool, is_cloud: bool):
        """Handle favorite changed event from EventBus."""
        if not is_cloud:
            return
        # item_id is cloud_file_id (mid) for cloud tracks
        self.set_track_favorite(str(item_id), is_favorite)

    def _on_cover_ready(self, cache_key: str, cover_path: str, qimage):
        """Handle cover loaded from background worker."""
        # Find the row for this cache_key
        track_row = self._find_row_by_cover_key(cache_key)

        if qimage and not qimage.isNull():
            # Cache the cover
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap.fromImage(qimage).scaled(
                self._delegate._cover_size,
                self._delegate._cover_size,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            CoverPixmapCache.set(cache_key, pixmap)

            if track_row is not None:
                self._model.notify_cover_loaded(track_row)
        elif track_row is not None:
            # No cover found — mark as failed
            self._delegate._failed_covers.add(cache_key)

    def _find_row_by_cover_key(self, cache_key: str):
        """Find row index for a cover cache key."""
        for row in range(self._model.rowCount()):
            track = self._model.get_track_at(row)
            if track and self._delegate._get_cover_cache_key(track) == cache_key:
                return row
        return None

    def _apply_viewport_bg(self):
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme
        self._list_view.setStyleSheet(
            f"QListView {{ background-color: {theme.background_alt}; border: none; outline: none; }}"
        )

    def load_tracks(self, tracks: List[OnlineTrack], favorite_mids: set = None):
        """Load tracks into the view."""
        self._model.reset_tracks(tracks, favorite_mids or set())
        self._apply_viewport_bg()

    def clear(self):
        """Clear all tracks."""
        self._model.reset_tracks([], set())

"""
Local tracks list view for displaying local music tracks.
Base class for track list views with configurable display options.
"""

import logging
from typing import List

from PySide6.QtCore import Qt, Signal, QSize, QAbstractListModel, QModelIndex, QRunnable, QThreadPool, QRect
from PySide6.QtGui import QColor, QPixmap, QPainter, QImage, QCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QListView, QStyledItemDelegate, QStyleOptionViewItem, QStyle

from domain.track import Track, TrackSource
from infrastructure.cache.pixmap_cache import CoverPixmapCache
from system import t
from system.event_bus import EventBus
from ui.icons import IconName, get_icon
from ui.widgets.context_menus import LocalTrackContextMenu
from utils.helpers import format_duration

logger = logging.getLogger(__name__)


class LocalTrackModel(QAbstractListModel):
    """QAbstractListModel for local track data."""

    TrackRole = Qt.UserRole + 1
    CoverRole = Qt.UserRole + 2
    IsFavoriteRole = Qt.UserRole + 3
    IndexRole = Qt.UserRole + 4
    IsCurrentRole = Qt.UserRole + 5
    IsPlayingRole = Qt.UserRole + 6

    cover_ready = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tracks: List[Track] = []
        self._favorite_ids: set = set()
        self._current_track_id = None
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
            return None
        elif role == self.IsFavoriteRole:
            return track.id in self._favorite_ids if track else False
        elif role == self.IndexRole:
            return row
        elif role == self.IsCurrentRole:
            return bool(self._current_track_id and track and track.id == self._current_track_id)
        elif role == self.IsPlayingRole:
            return (bool(self._current_track_id and track and track.id == self._current_track_id)
                    and self._is_playing)
        return None

    def roleNames(self):
        return {
            Qt.DisplayRole: b"display",
            self.TrackRole: b"track",
            self.CoverRole: b"cover",
            self.IsFavoriteRole: b"favorite",
            self.IndexRole: b"index",
            self.IsCurrentRole: b"current",
            self.IsPlayingRole: b"playing",
        }

    def reset_tracks(self, tracks: List[Track], favorite_ids: set):
        self.blockSignals(True)
        self.beginResetModel()
        self._tracks = list(tracks)
        self._favorite_ids = set(favorite_ids)
        self.endResetModel()
        self.blockSignals(False)

    def update_favorites(self, favorite_ids: set):
        """Update favorite IDs and emit dataChanged for affected rows."""
        old_favs = self._favorite_ids
        self._favorite_ids = set(favorite_ids)

        # Find rows that changed and batch emit
        changed_indices = []
        for i, track in enumerate(self._tracks):
            if track and (track.id in old_favs) != (track.id in self._favorite_ids):
                changed_indices.append(i)
        if changed_indices:
            first = self.index(min(changed_indices))
            last = self.index(max(changed_indices))
            self.dataChanged.emit(first, last, [self.IsFavoriteRole])

    def get_track_at(self, row: int):
        if 0 <= row < len(self._tracks):
            return self._tracks[row]
        return None

    def notify_cover_loaded(self, row: int):
        if 0 <= row < len(self._tracks):
            idx = self.index(row)
            self.dataChanged.emit(idx, idx, [self.CoverRole])

    def set_current_track(self, track_id):
        """Update the current track and emit dataChanged for affected rows."""
        old_track_id = self._current_track_id
        self._current_track_id = track_id
        changed_indices = []
        for i, track in enumerate(self._tracks):
            if track and (track.id == old_track_id or track.id == track_id):
                changed_indices.append(i)
        if changed_indices:
            first = self.index(min(changed_indices))
            last = self.index(max(changed_indices))
            self.dataChanged.emit(first, last, [self.IsCurrentRole, self.IsPlayingRole])

    def set_playing(self, playing: bool):
        """Update playing state and emit dataChanged for current track."""
        self._is_playing = playing
        if self._current_track_id:
            for i, track in enumerate(self._tracks):
                if track and track.id == self._current_track_id:
                    idx = self.index(i)
                    self.dataChanged.emit(idx, idx, [self.IsPlayingRole])
                    break


class CoverLoadWorker(QRunnable):
    """Worker to load cover in background thread."""

    def __init__(self, cache_key: str, track: Track, callback_signal):
        super().__init__()
        self.cache_key = cache_key
        self.track = track
        self.callback_signal = callback_signal
        self.setAutoDelete(True)

    def run(self):
        try:
            cover_path = self._resolve_cover_path()
            qimage = None
            if cover_path:
                qimage = QImage(cover_path)
            try:
                self.callback_signal.emit(self.cache_key, cover_path, qimage)
            except RuntimeError:
                pass  # signal source deleted
        except Exception:
            pass

    def _resolve_cover_path(self) -> str | None:
        """Resolve cover path for a track (runs in worker thread)."""
        if not self.track:
            return None

        from pathlib import Path

        source = self.track.source
        cloud_file_id = self.track.cloud_file_id
        is_online = source == TrackSource.QQ

        if is_online and cloud_file_id:
            try:
                from app.bootstrap import Bootstrap
                bootstrap = Bootstrap.instance()
                if bootstrap and hasattr(bootstrap, 'cover_service'):
                    cover_path = bootstrap.cover_service.get_online_cover(
                        song_mid=cloud_file_id,
                        album_mid=None,
                        artist=self.track.artist,
                        title=self.track.title,
                    )
                    if cover_path:
                        return cover_path
            except Exception:
                pass

        # Try cover_path first
        cover_path = self.track.cover_path
        if cover_path and Path(cover_path).exists():
            return cover_path

        # Try extracting from file
        path = self.track.path
        if path and Path(path).exists():
            try:
                from app.bootstrap import Bootstrap
                bootstrap = Bootstrap.instance()
                if bootstrap and hasattr(bootstrap, 'cover_service'):
                    cover_path = bootstrap.cover_service.get_cover(
                        path, self.track.title, self.track.artist,
                        self.track.album, skip_online=True,
                    )
                    if cover_path:
                        return cover_path
            except Exception:
                pass

        return None


class LocalTrackDelegate(QStyledItemDelegate):
    """Delegate for painting local track items without per-item QWidget overhead."""

    _cover_loaded_signal = Signal(str, object, object)

    def __init__(self, parent=None, show_index: bool = True, show_source: bool = True):
        super().__init__(parent)
        self._cover_loaded_signal.connect(self._on_cover_loaded)
        self._requested_covers: set = set()
        self._failed_covers: set = set()
        CoverPixmapCache.initialize()
        self._cover_size = 64
        self._index_width = 50
        self._padding = 10
        self._star_size = 20
        self._show_index = show_index
        self._show_source = show_source

    def sizeHint(self, option, index):
        return QSize(0, 82)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        # Skip off-screen items
        parent_view = self.parent()
        if parent_view and (option.rect.bottom() < 0 or option.rect.top() > parent_view.height()):
            return

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        track = index.data(LocalTrackModel.TrackRole)
        is_favorite = index.data(LocalTrackModel.IsFavoriteRole)
        row = index.data(LocalTrackModel.IndexRole)
        is_current = index.data(LocalTrackModel.IsCurrentRole)

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
        elif is_current:
            text_color = QColor(theme.highlight)
            secondary_color = QColor(theme.highlight)
        else:
            text_color = QColor(theme.text)
            secondary_color = QColor(theme.text_secondary)

        x = rect.left() + self._padding

        # Index number (if enabled)
        if self._show_index:
            painter.setPen(secondary_color)
            font = painter.font()
            font.setPixelSize(12)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(x, rect.top(), self._index_width, rect.height(),
                             Qt.AlignVCenter | Qt.AlignHCenter, str(row + 1))
            x += self._index_width

        # Cover art
        cover_rect = QRect(x + 2, rect.top() + 9, self._cover_size, self._cover_size)
        self._paint_cover(painter, cover_rect, track, row, theme)
        x += self._cover_size + 12

        # Title
        title = track.title or "Unknown"
        painter.setPen(text_color)
        font = painter.font()
        font.setPixelSize(15)
        font.setBold(True)
        painter.setFont(font)
        title_rect = QRect(x, rect.top() + 10, rect.right() - x - 100, 22)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, title, title_rect.width()))

        # Artist + Album
        artist = track.artist or "Unknown"
        album = track.album or ""
        artist_album = artist + (f" • {album}" if album else "")

        painter.setPen(secondary_color)
        font.setPixelSize(13)
        font.setBold(False)
        painter.setFont(font)
        info_rect = QRect(x, rect.top() + 32, rect.right() - x - 100, 20)
        painter.drawText(info_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, artist_album, info_rect.width()))

        # Source indicator (if enabled)
        if self._show_source:
            source_str = track.source.value if track.source else "Local"
            try:
                source = TrackSource(source_str) if source_str else TrackSource.LOCAL
            except ValueError:
                source = TrackSource.LOCAL

            source_text = ""
            if source == TrackSource.LOCAL:
                source_text = t("source_local")
            elif source == TrackSource.QQ:
                source_text = t("source_qq")
            elif source == TrackSource.QUARK:
                source_text = t("source_quark")
            elif source == TrackSource.BAIDU:
                source_text = t("source_baidu")

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

        # Favorite icon (star)
        star_x = rect.right() - self._padding - self._star_size
        star_y = rect.top() + (rect.height() - self._star_size) // 2

        star_color = "#ff4444" if is_favorite else theme.text_secondary
        star_icon = get_icon(IconName.STAR_FILLED if is_favorite else IconName.STAR_OUTLINE,
                            star_color)
        star_pixmap = star_icon.pixmap(self._star_size, self._star_size)
        painter.drawPixmap(star_x, star_y, star_pixmap)

        painter.restore()

    def _paint_cover(self, painter: QPainter, rect: QRect, track: Track, row: int, theme):
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
                worker = CoverLoadWorker(cache_key, track, self._cover_loaded_signal)
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
                        if nearby_key not in self._requested_covers and nearby_key not in self._failed_covers and not CoverPixmapCache.get(nearby_key):
                            self._requested_covers.add(nearby_key)
                            worker = CoverLoadWorker(nearby_key, nearby_track, self._cover_loaded_signal)
                            QThreadPool.globalInstance().start(worker)

    def _on_cover_loaded(self, cache_key: str, cover_path: str, qimage):
        """Handle cover loaded from background — runs on UI thread."""
        self._requested_covers.discard(cache_key)

        parent_view = self.parent()
        if parent_view and hasattr(parent_view, '_on_cover_ready'):
            parent_view._on_cover_ready(cache_key, cover_path, qimage)

    def _get_cover_cache_key(self, track: Track) -> str:
        """Generate cache key for a track."""
        if track.cloud_file_id:
            return f"{track.source.name}:{track.cloud_file_id}"
        if track.artist and track.title:
            return CoverPixmapCache.make_key(track.artist, track.title)
        path = track.path or track.cover_path or ""
        return CoverPixmapCache.make_key_from_path(path)

    @staticmethod
    def _elided_text(painter, text: str, max_width: int) -> str:
        """Return elided text if too wide."""
        fm = painter.fontMetrics()
        if fm.horizontalAdvance(text) <= max_width:
            return text
        return fm.elidedText(text, Qt.ElideRight, max_width)


class LocalTracksListView(QWidget):
    """List view for local tracks with delegate-based rendering."""

    track_activated = Signal(object)  # Track
    favorite_toggled = Signal(object, bool)  # Track, is_favorite
    play_requested = Signal(list)
    insert_to_queue_requested = Signal(list)
    add_to_queue_requested = Signal(list)
    add_to_playlist_requested = Signal(list)
    favorites_toggle_requested = Signal(list, bool)  # (tracks, all_favorited)
    edit_info_requested = Signal(object)
    download_cover_requested = Signal(object)
    open_file_location_requested = Signal(object)
    remove_from_library_requested = Signal(list)
    delete_file_requested = Signal(list)
    redownload_requested = Signal(object)  # Track

    def __init__(self, parent=None, show_index: bool = True, show_source: bool = True):
        super().__init__(parent)
        self._model = LocalTrackModel(self)
        self._delegate = LocalTrackDelegate(self, show_index=show_index, show_source=show_source)
        self._setup_ui()
        self._setup_connections()
        self._context_menu = LocalTrackContextMenu(self)
        self._connect_context_menu()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._list_view = QListView()
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)
        self._list_view.setSelectionMode(QListView.SelectionMode.ExtendedSelection)
        self._list_view.setSelectionBehavior(QListView.SelectionBehavior.SelectRows)
        self._list_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list_view.setMouseTracking(True)
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
        bus.track_changed.connect(self._on_track_changed)
        bus.playback_state_changed.connect(self._on_playback_state_changed)

    def closeEvent(self, event):
        """Clean up event bus connections before closing."""
        try:
            bus = EventBus.instance()
            bus.favorite_changed.disconnect(self._on_favorite_changed)
            bus.track_changed.disconnect(self._on_track_changed)
            bus.playback_state_changed.disconnect(self._on_playback_state_changed)
        except RuntimeError:
            pass
        # Disconnect delegate's class-level signal to prevent leaked connections
        try:
            self._delegate._cover_loaded_signal.disconnect(self._delegate._on_cover_loaded)
        except RuntimeError:
            pass
        super().closeEvent(event)

    def _on_item_activated(self, index):
        track = index.data(LocalTrackModel.TrackRole)
        if track:
            self.track_activated.emit(track)

    def _on_item_clicked(self, index):
        """Handle click events - check if star icon was clicked."""
        # Get click position
        pos = self._list_view.mapFromGlobal(QCursor.pos())
        rect = self._list_view.visualRect(index)

        # Check if click is in star icon area (right side)
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
            track = index.data(LocalTrackModel.TrackRole)
            if track:
                is_favorite = index.data(LocalTrackModel.IsFavoriteRole)
                self._toggle_favorite(track, not is_favorite)

    def _toggle_favorite(self, track: Track, new_state: bool):
        """Toggle favorite status."""
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        if bootstrap and hasattr(bootstrap, 'favorites_service'):
            service = bootstrap.favorites_service
            if new_state:
                service.add_favorite(track_id=track.id)
            else:
                service.remove_favorite(track_id=track.id)

    def _connect_context_menu(self):
        self._context_menu.play.connect(self.play_requested)
        self._context_menu.insert_to_queue.connect(self.insert_to_queue_requested)
        self._context_menu.add_to_queue.connect(self.add_to_queue_requested)
        self._context_menu.add_to_playlist.connect(self.add_to_playlist_requested)
        self._context_menu.favorite_toggled.connect(self.favorites_toggle_requested)
        self._context_menu.edit_info.connect(self.edit_info_requested)
        self._context_menu.download_cover.connect(self.download_cover_requested)
        self._context_menu.open_file_location.connect(self.open_file_location_requested)
        self._context_menu.remove_from_library.connect(self.remove_from_library_requested)
        self._context_menu.delete_file.connect(self.delete_file_requested)
        self._context_menu.redownload.connect(self.redownload_requested)

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

        self._context_menu.show_menu(
            tracks,
            favorite_ids=self._model._favorite_ids,
            parent_widget=self
        )

    def _on_favorite_changed(self, item_id, is_favorite: bool, is_cloud: bool):
        """Handle favorite changed event from EventBus."""
        if is_cloud:
            return  # Only shows local tracks

        # Refresh favorites from service
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        if bootstrap and hasattr(bootstrap, 'favorites_service'):
            favorite_ids = bootstrap.favorites_service.get_all_favorite_track_ids()
            self._model.update_favorites(favorite_ids)

    def _on_track_changed(self, track_item):
        """Handle current track change from EventBus."""
        track_id = None
        if track_item:
            if isinstance(track_item, dict):
                track_id = track_item.get("track_id") or track_item.get("id")
            else:
                track_id = getattr(track_item, 'track_id', None) or getattr(track_item, 'id', None)
        self._model.set_current_track(track_id)

    def _on_playback_state_changed(self, state):
        """Handle playback state change from EventBus."""
        self._model.set_playing(state == "playing")

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

    def load_tracks(self, tracks: List[Track], favorite_ids: set = None):
        """Load tracks into the view."""
        self._model.reset_tracks(tracks, favorite_ids or set())
        self._apply_viewport_bg()

    def clear(self):
        """Clear all tracks."""
        self._model.reset_tracks([], set())

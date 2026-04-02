"""
History list view for displaying play history.
Extends LocalTracksListView to add played time display.
"""

import logging
from datetime import datetime
from typing import List

from PySide6.QtCore import Qt, Signal, QSize, QModelIndex, QRect
from PySide6.QtGui import QColor, QPainter, QCursor
from PySide6.QtWidgets import QListView, QStyledItemDelegate, QStyleOptionViewItem, QStyle

from domain.track import Track
from infrastructure.cache.pixmap_cache import CoverPixmapCache
from system import t
from ui.views.local_tracks_list_view import (
    LocalTracksListView,
    LocalTrackModel,
    CoverLoadWorker,
)
from ui.widgets.context_menus import LocalTrackContextMenu
from utils.helpers import format_relative_time

logger = logging.getLogger(__name__)


class HistoryTrackModel(LocalTrackModel):
    """Extended model for history track data with played_at support."""

    PlayedAtRole = Qt.UserRole + 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._played_at_map: dict = {}  # track_id -> datetime

    def roleNames(self):
        names = super().roleNames()
        names[self.PlayedAtRole] = b"played_at"
        return names

    def data(self, index, role=Qt.DisplayRole):
        if role == self.PlayedAtRole:
            track = super().data(index, self.TrackRole)
            return self._played_at_map.get(track.id) if track else None
        return super().data(index, role)

    def reset_tracks(self, tracks: List[Track], played_at_map: dict, favorite_ids: set):
        """Reset tracks with played_at timestamps."""
        self.beginResetModel()
        self._tracks = list(tracks)
        self._played_at_map = dict(played_at_map)
        self._favorite_ids = set(favorite_ids)
        self.endResetModel()


class HistoryItemDelegate(QStyledItemDelegate):
    """Delegate for painting history items with played time."""

    _cover_loaded_signal = Signal(str, object, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_loaded_signal.connect(self._on_cover_loaded)
        self._requested_covers: set = set()
        self._failed_covers: set = set()
        CoverPixmapCache.initialize()
        self._cover_size = 64
        self._index_width = 50
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

        track = index.data(HistoryTrackModel.TrackRole)
        is_favorite = index.data(HistoryTrackModel.IsFavoriteRole)
        played_at = index.data(HistoryTrackModel.PlayedAtRole)
        row = index.data(HistoryTrackModel.IndexRole)
        is_current = index.data(HistoryTrackModel.IsCurrentRole)

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

        # Index number
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

        # Source indicator + Played time (relative)
        from domain.track import TrackSource
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

        played_time_text = ""
        if played_at:
            played_time_text = format_relative_time(played_at)

        # Combine source and played time
        source_time_text = f"{source_text} • {played_time_text}" if source_text and played_time_text else (source_text or played_time_text)

        painter.setPen(secondary_color)
        font.setPixelSize(11)
        font.setBold(False)
        painter.setFont(font)
        time_rect = QRect(x, rect.top() + 52, rect.right() - x - 100, 16)
        painter.drawText(time_rect, Qt.AlignLeft | Qt.AlignVCenter,
                         self._elided_text(painter, source_time_text, time_rect.width()))

        # Duration
        from utils.helpers import format_duration
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
        from ui.icons import IconName, get_icon
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
                from PySide6.QtCore import QThreadPool
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
                            from PySide6.QtCore import QThreadPool
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


class HistoryListView(LocalTracksListView):
    """List view for play history with played time display."""

    def __init__(self, parent=None):
        # Override parent init - we need custom model and delegate
        super().__init__(parent, show_index=True, show_source=False)

        # Replace with history-specific model and delegate
        self._model = HistoryTrackModel(self)
        self._delegate = HistoryItemDelegate(self)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)

        # Reconnect context menu (same as parent)
        self._context_menu = LocalTrackContextMenu(self)
        self._connect_context_menu()

    def load_tracks(self, tracks: List[Track], played_at_map: dict, favorite_ids: set):
        """Load tracks into the view with played_at timestamps."""
        self._model.reset_tracks(tracks, played_at_map, favorite_ids)
        self._apply_viewport_bg()

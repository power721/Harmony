"""
Online music grid view for displaying artists/albums/playlists in a grid layout.
Uses QListView + Model/Delegate for high-performance rendering with lazy loading.
"""

import logging
from collections import OrderedDict
from typing import List, Optional, Union

from PySide6.QtCore import (
    Qt, Signal,
    QAbstractListModel, QModelIndex, QSize, QRect
)
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QPen
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QListView,
    QProgressBar,
    QStyledItemDelegate,
    QStyle,
    QPushButton,
)

from domain.online_music import OnlineArtist, OnlineAlbum, OnlinePlaylist
from system.i18n import t

logger = logging.getLogger(__name__)

# Type alias for online items
OnlineItem = Union[OnlineArtist, OnlineAlbum, OnlinePlaylist]


class OnlineItemModel(QAbstractListModel):
    """Model for online item data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[OnlineItem] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._items)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._items):
            return None

        item = self._items[index.row()]

        if role == Qt.DisplayRole:
            if isinstance(item, OnlineArtist):
                return item.name
            elif isinstance(item, OnlineAlbum):
                return item.name
            elif isinstance(item, OnlinePlaylist):
                return item.title
        elif role == Qt.UserRole:
            return item

        return None

    def set_items(self, items: List[OnlineItem]):
        self.beginResetModel()
        self._items = items
        self.endResetModel()

    def get_item(self, row: int) -> Optional[OnlineItem]:
        if 0 <= row < len(self._items):
            return self._items[row]
        return None

    def clear(self):
        self.beginResetModel()
        self._items.clear()
        self.endResetModel()


class OnlineItemDelegate(QStyledItemDelegate):
    """Delegate for rendering online item cards."""

    # Card size constants
    COVER_SIZE = 180
    CARD_WIDTH = 180
    CARD_HEIGHT = 240
    SPACING = 20

    def __init__(self, data_type: str, parent=None):
        """
        Initialize delegate.

        Args:
            data_type: Type of data ('singer', 'album', or 'playlist')
            parent: Parent widget
        """
        super().__init__(parent)
        self._data_type = data_type

        # Set border radius based on data type
        if data_type == "singer":
            self._border_radius = 90  # Circular
        else:
            self._border_radius = 8  # Rounded rectangle

        self._cover_cache = OrderedDict()  # LRU cache for loaded covers
        self._cache_max_size = 500
        self._pending_downloads = set()  # Track URLs being downloaded

        self._default_cover = self._create_default_cover()

    def _create_default_cover(self) -> QPixmap:
        """Create default cover pixmap."""
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme

        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        if self._data_type == "singer":
            # Circular background for artists with theme color
            painter.setBrush(QColor(theme.text_secondary))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(0, 0, self.COVER_SIZE, self.COVER_SIZE)
            icon = "\u265A"  # Chess queen (person icon)
        else:
            # Rounded rectangle for albums/playlists with theme color
            painter.setBrush(QColor(theme.text_secondary))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(0, 0, self.COVER_SIZE, self.COVER_SIZE, 8, 8)
            icon = "\u266B"  # Music note

        # Draw icon with contrasting theme color
        painter.setPen(QColor(theme.text))
        font = QFont()
        font.setPixelSize(60 if self._data_type == "singer" else 80)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, icon
        )
        painter.end()
        return pixmap

    def _load_cover(self, item: OnlineItem) -> QPixmap:
        """Load cover from URL with caching."""
        cover_url = None

        if isinstance(item, OnlineArtist):
            cover_url = item.avatar_url
        elif isinstance(item, OnlineAlbum):
            cover_url = item.cover_url
        elif isinstance(item, OnlinePlaylist):
            cover_url = item.cover_url

        if not cover_url:
            return self._default_cover

        if cover_url in self._cover_cache:
            self._cover_cache.move_to_end(cover_url)
            return self._cover_cache[cover_url]

        # Start async download if not already pending
        if cover_url not in self._pending_downloads:
            self._pending_downloads.add(cover_url)
            self._download_cover_async(cover_url)

        return self._default_cover

    def _download_cover_async(self, url: str):
        """Download cover image asynchronously with disk caching."""
        from concurrent.futures import ThreadPoolExecutor
        from infrastructure.cache import ImageCache
        from infrastructure.network import HttpClient

        try:
            # Check disk cache first
            cached_data = ImageCache.get(url)
            if cached_data:
                self._load_cached_cover(url, cached_data)
                return

            http_client = HttpClient()

            def download():
                try:
                    return http_client.get_content(url, timeout=5, headers={
                        'Referer': 'https://y.qq.com/'
                    })
                except Exception as e:
                    logger.warning(f"Failed to download cover from {url}: {e}")
                    return None

            # Run in background thread
            executor = ThreadPoolExecutor(max_workers=1)
            future = executor.submit(download)

            # Check completion after a short delay
            from PySide6.QtCore import QTimer
            def check_download():
                if future.done():
                    image_data = future.result()
                    if image_data:
                        # Save to disk cache
                        ImageCache.set(url, image_data)
                        self._load_cached_cover(url, image_data)
                    self._pending_downloads.discard(url)
                    executor.shutdown(wait=False)
                else:
                    # Check again later
                    QTimer.singleShot(100, check_download)

            QTimer.singleShot(100, check_download)

        except Exception as e:
            logger.warning(f"Failed to start cover download: {e}")
            self._pending_downloads.discard(url)

    def _load_cached_cover(self, url: str, image_data: bytes):
        """Load cover from cached data."""
        pixmap = QPixmap()
        if pixmap.loadFromData(image_data):
            # Scale image
            scaled = pixmap.scaled(
                self.COVER_SIZE, self.COVER_SIZE,
                Qt.KeepAspectRatioByExpanding,
                Qt.SmoothTransformation
            )

            # Apply mask based on data type
            if self._data_type == "singer":
                # Create circular mask
                circular = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
                circular.fill(Qt.transparent)

                painter = QPainter(circular)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(Qt.white)
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(0, 0, self.COVER_SIZE, self.COVER_SIZE)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                painter.drawPixmap(0, 0, scaled)
                painter.end()

                final = circular
            else:
                # Use rounded rectangle mask
                masked = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
                masked.fill(Qt.transparent)

                painter = QPainter(masked)
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setBrush(Qt.white)
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(0, 0, self.COVER_SIZE, self.COVER_SIZE, 8, 8)
                painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
                painter.drawPixmap(0, 0, scaled)
                painter.end()

                final = masked

            self._cover_cache[url] = final
            if len(self._cover_cache) > self._cache_max_size:
                self._cover_cache.popitem(last=False)

            # Trigger repaint
            if self.parent():
                widget = self.parent()
                if hasattr(widget, 'viewport'):
                    widget.viewport().update()

    def sizeHint(self, option, index):
        return QSize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def paint(self, painter, option, index):
        item = index.data(Qt.UserRole)
        if not item:
            logger.warning(f"[OnlineItemDelegate] paint called but item is None, index={index.row()}")
            return

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        rect = option.rect
        is_hovered = option.state & QStyle.State_MouseOver

        # Debug log for first item
        # if index.row() == 0:
        #     if isinstance(item, OnlineArtist):
        #         logger.info(f"[OnlineItemDelegate] Painting artist: {item.name}, rect: {rect.x()}, {rect.y()}, {rect.width()}, {rect.height()}")
        #         logger.info(f"[OnlineItemDelegate] Name rect will be: x={rect.x() + 4}, y={rect.y() + self.COVER_SIZE + 8}, w={rect.width() - 8}, h=36")
        #     elif isinstance(item, OnlineAlbum):
        #         logger.info(f"[OnlineItemDelegate] Painting album: {item.name}")
        #     elif isinstance(item, OnlinePlaylist):
        #         logger.info(f"[OnlineItemDelegate] Painting playlist: {item.title}")

        # Draw cover
        cover = self._load_cover(item)
        cover_x = rect.x() + (rect.width() - self.COVER_SIZE) // 2
        cover_y = rect.y()

        # Draw highlight on hover
        if is_hovered:
            painter.setRenderHint(QPainter.Antialiasing)

            if self._data_type == "singer":
                # Circular border for artists
                painter.setPen(QPen(QColor(theme.highlight_hover), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(cover_x - 2, cover_y - 2, self.COVER_SIZE + 4, self.COVER_SIZE + 4)
            else:
                # Rounded background for albums/playlists
                bg_rect = QRect(
                    cover_x - 4,
                    cover_y - 4,
                    self.COVER_SIZE + 8,
                    self.CARD_HEIGHT - 40
                )
                painter.setPen(Qt.NoPen)
                # Use semi-transparent background_hover for hover background
                hover_bg = QColor(theme.background_hover)
                hover_bg.setAlpha(200)
                painter.setBrush(hover_bg)
                painter.drawRoundedRect(bg_rect, 12, 12)

                # Border
                painter.setPen(QPen(QColor(theme.highlight_hover), 2))
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(cover_x, cover_y, self.COVER_SIZE, self.COVER_SIZE, 4, 4)

        painter.drawPixmap(cover_x, cover_y, cover)

        # Draw text based on item type
        painter.setPen(QColor(theme.text))
        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)

        # Get name and alignment based on type
        if isinstance(item, OnlineArtist):
            name = item.name
            name_align = Qt.AlignHCenter | Qt.TextWordWrap
        elif isinstance(item, OnlineAlbum):
            name = item.name
            name_align = Qt.AlignLeft | Qt.TextWordWrap
        elif isinstance(item, OnlinePlaylist):
            name = item.title
            name_align = Qt.AlignLeft | Qt.TextWordWrap
        else:
            name = "Unknown"
            name_align = Qt.AlignLeft | Qt.TextWordWrap

        name_rect = QRect(
            rect.x() + 4,
            rect.y() + self.COVER_SIZE + 8,
            rect.width() - 8,
            36
        )
        painter.drawText(name_rect, name_align, name)

        # Draw subtitle
        painter.setPen(QColor(theme.text_secondary))
        font.setBold(False)
        font.setPixelSize(11)
        painter.setFont(font)

        if isinstance(item, OnlineArtist):
            from system.i18n import t
            if item.song_count or item.album_count:
                subtitle = f"{item.song_count} {t('tracks')} • {item.album_count} {t('albums')}"
            elif item.fan_count:
                if item.fan_count >= 10000:
                    subtitle = f"{item.fan_count / 10000:.1f}{t('ten_thousand')} {t('fans')}"
                else:
                    subtitle = f"{item.fan_count:,} {t('fans')}"
            else:
                subtitle = ""
            align = Qt.AlignHCenter
        elif isinstance(item, OnlineAlbum):
            subtitle = item.singer_name
            align = Qt.AlignLeft
        elif isinstance(item, OnlinePlaylist):
            from system.i18n import t
            play_str = self._format_play_count(item.play_count) if item.play_count else ""
            parts = []
            if item.song_count:
                parts.append(f"{item.song_count} {t('tracks')}")
            if play_str:
                parts.append(play_str)
            subtitle = " • ".join(parts) if parts else ""
            align = Qt.AlignLeft
        else:
            subtitle = ""
            align = Qt.AlignLeft

        if subtitle:
            subtitle_rect = QRect(
                rect.x() + 4,
                rect.y() + self.COVER_SIZE + 44,
                rect.width() - 8,
                20
            )
            painter.drawText(subtitle_rect, align, subtitle)

    def _format_play_count(self, count: int) -> str:
        """Format play count to human-readable string."""
        if count >= 100_000_000:
            return f"{count / 100_000_000:.1f}亿"
        elif count >= 10_000:
            return f"{count / 10_000:.1f}万"
        elif count > 0:
            return str(count)
        return ""

    def clear_cache(self):
        """Clear cover cache and pending downloads."""
        self._cover_cache.clear()
        self._pending_downloads.clear()

    def refresh_theme(self):
        """Refresh default cover when theme changes."""
        self._default_cover = self._create_default_cover()


class OnlineGridView(QWidget):
    """
    Grid view for online music items (artists/albums/playlists).
    Supports lazy loading and custom delegate rendering.
    """

    item_clicked = Signal(object)  # Emits OnlineItem object
    load_more_requested = Signal()  # Emitted when "load more" button is clicked

    _STYLE_MAIN = """
        background-color: %background%;
    """
    _STYLE_LIST_VIEW = """
        QListView {
            background-color: %background%;
            border: none;
        }
        QListView::item {
            background: transparent;
        }
        QScrollBar:vertical {
            background-color: %background%;
            width: 12px;
        }
        QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: %text_secondary%;
        }
    """
    _STYLE_LOAD_MORE_BTN = """
        QPushButton {
            background: %background_hover%;
            color: %highlight%;
            border: 1px solid %highlight%;
            border-radius: 20px;
            font-size: 14px;
            padding: 0 20px;
        }
        QPushButton:hover {
            background: %highlight%;
            color: %background%;
        }
    """
    _STYLE_PROGRESS_BAR = """
        QProgressBar {
            background-color: %background_hover%;
            border: none;
            border-radius: 2px;
        }
        QProgressBar::chunk {
            background-color: %highlight%;
            border-radius: 2px;
        }
    """

    def __init__(self, data_type: str, parent=None):
        """
        Initialize grid view.

        Args:
            data_type: Type of data ('singer', 'album', or 'playlist')
            parent: Parent widget
        """
        super().__init__(parent)
        self._data_type = data_type
        self._items: List[OnlineItem] = []
        self._data_loaded = False
        self._pending_data: Optional[List[OnlineItem]] = None

        self._setup_ui()
        self._connect_signals()

        # Register with theme system
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def showEvent(self, event):
        """Load data when view is first shown (lazy loading)."""
        super().showEvent(event)
        if not self._data_loaded and self._pending_data:
            self._do_load(self._pending_data)

    def _setup_ui(self):
        """Set up the grid view UI."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme
        self.setStyleSheet(f"background-color: {theme.background};")
        self.setMouseTracking(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # List view
        self._list_view = QListView()
        self._list_view.setViewMode(QListView.IconMode)
        self._list_view.setResizeMode(QListView.Adjust)
        self._list_view.setMovement(QListView.Static)
        self._list_view.setSelectionMode(QListView.SingleSelection)
        self._list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_view.setVerticalScrollMode(QListView.ScrollPerPixel)
        self._list_view.setMouseTracking(True)

        # Model and delegate
        self._model = OnlineItemModel(self)
        self._delegate = OnlineItemDelegate(self._data_type, self._list_view)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)

        # Set grid size
        self._list_view.setGridSize(QSize(
            OnlineItemDelegate.CARD_WIDTH + OnlineItemDelegate.SPACING,
            OnlineItemDelegate.CARD_HEIGHT + OnlineItemDelegate.SPACING
        ))

        layout.addWidget(self._list_view)
        self._list_view.hide()  # Hide until data is loaded

        # Load more button
        self._load_more_btn = QPushButton()
        self._load_more_btn.setText(t("load_more"))
        self._load_more_btn.setCursor(Qt.PointingHandCursor)
        self._load_more_btn.setFixedHeight(40)
        self._load_more_btn.clicked.connect(self._on_load_more_clicked)
        self._load_more_btn.hide()
        layout.addWidget(self._load_more_btn)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()  # Hide initially

    def _create_loading_indicator(self) -> QWidget:
        """Create loading indicator."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        progress.setFixedSize(200, 4)
        layout.addWidget(progress)

        self._loading_label = QLabel(t("loading"))
        layout.addWidget(self._loading_label)

        return widget

    def _connect_signals(self):
        """Connect signals."""
        self._list_view.clicked.connect(self._on_item_clicked)
        self._list_view.entered.connect(self._on_item_entered)

    def _on_item_entered(self, index):
        """Handle item entered for hover effect."""
        self._list_view.viewport().setCursor(Qt.PointingHandCursor)

    def _on_item_clicked(self, index: QModelIndex):
        """Handle item click."""
        item = index.data(Qt.UserRole)
        if item:
            self.item_clicked.emit(item)

    def _on_load_more_clicked(self):
        """Handle load more button click."""
        self.load_more_requested.emit()

    def load_data(self, items: List[OnlineItem]):
        """
        Load data into the view with lazy loading.

        Args:
            items: List of online items to display
        """
        self._pending_data = items

        if self.isVisible():
            # Show loading indicator
            self._loading.show()
            self._list_view.hide()
            # Use small delay to allow UI to update
            from PySide6.QtCore import QTimer
            QTimer.singleShot(50, lambda: self._do_load(items))

    def _do_load(self, items: List[OnlineItem]):
        """Actually load data into the view."""
        self._items = items
        self._data_loaded = True
        self._model.set_items(items)
        self._loading.hide()
        self._list_view.show()

    def append_data(self, items: List[OnlineItem]):
        """
        Append more items to existing data (for load more functionality).

        Args:
            items: Additional items to append
        """
        if not items:
            return

        self._items.extend(items)
        self._model.set_items(self._items)
        self._loading.hide()
        self._list_view.show()

    def set_has_more(self, has_more: bool):
        """
        Set whether there are more items to load.

        Args:
            has_more: True if more items can be loaded
        """
        if has_more:
            self._load_more_btn.show()
        else:
            self._load_more_btn.hide()

    def show_loading(self):
        """Show loading indicator."""
        self._loading.show()
        self._list_view.hide()
        self._load_more_btn.hide()

    def hide_loading(self):
        """Hide loading indicator."""
        self._loading.hide()

    def clear(self):
        """Clear all data from the view."""
        self._items.clear()
        self._data_loaded = False
        self._pending_data = None
        self._model.clear()
        self._delegate.clear_cache()
        self._load_more_btn.hide()

    def refresh_ui(self):
        """Refresh UI (for language changes)."""
        # Update load more button text
        if hasattr(self, '_load_more_btn'):
            self._load_more_btn.setText(t("load_more"))
        # Update loading label text
        if hasattr(self, '_loading_label'):
            self._loading_label.setText(t("loading"))

    def refresh_theme(self):
        """Refresh all styles using current theme tokens."""
        from system.theme import ThemeManager
        tm = ThemeManager.instance()

        # Main widget
        self.setStyleSheet(tm.get_qss(self._STYLE_MAIN))

        # List view
        self._list_view.setStyleSheet(tm.get_qss(self._STYLE_LIST_VIEW))

        # Load more button
        self._load_more_btn.setStyleSheet(tm.get_qss(self._STYLE_LOAD_MORE_BTN))

        # Progress bar
        if hasattr(self, '_loading'):
            progress = self._loading.findChild(QProgressBar)
            if progress:
                progress.setStyleSheet(tm.get_qss(self._STYLE_PROGRESS_BAR))

        # Loading label
        self._loading_label.setStyleSheet(
            f"color: {tm.current_theme.text_secondary}; font-size: 14px;"
        )

        # Refresh delegate's default cover
        self._delegate.refresh_theme()

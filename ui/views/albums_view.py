"""
Albums view widget for browsing albums in a grid layout.
Uses QListView + Model/Delegate for high-performance rendering.
"""

import logging
from pathlib import Path
from typing import List, Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListView,
    QFrame,
    QLineEdit,
    QProgressBar,
    QStyledItemDelegate,
    QStyle,
    QMenu,
    QApplication,
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QThread,
    QAbstractListModel, QModelIndex, QSize, QRect, QEvent
)
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QPen, QAction, QCursor

from domain.album import Album
from services.library import LibraryService
from services.metadata import CoverService
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class LoadAlbumsWorker(QThread):
    """Background worker to load albums."""
    finished = Signal(list)

    def __init__(self, library_service: LibraryService, parent=None):
        super().__init__(parent)
        self._library = library_service

    def run(self):
        albums = self._library.get_albums()
        self.finished.emit(albums)


class AlbumModel(QAbstractListModel):
    """Model for album data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._albums: List[Album] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._albums)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._albums):
            return None

        album = self._albums[index.row()]

        if role == Qt.DisplayRole:
            return album.name
        elif role == Qt.UserRole:
            return album

        return None

    def set_albums(self, albums: List[Album]):
        self.beginResetModel()
        self._albums = albums
        self.endResetModel()

    def get_album(self, row: int) -> Optional[Album]:
        if 0 <= row < len(self._albums):
            return self._albums[row]
        return None


class AlbumDelegate(QStyledItemDelegate):
    """Delegate for rendering album cards."""

    # Card size constants
    COVER_SIZE = 180
    CARD_WIDTH = 180
    CARD_HEIGHT = 240
    BORDER_RADIUS = 8
    SPACING = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_cache = {}  # Cache for loaded covers
        self._default_cover = self._create_default_cover()

    def _create_default_cover(self) -> QPixmap:
        """Create default cover pixmap."""
        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(QColor("#3d3d3d"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(60)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, "\u266B"
        )
        painter.end()
        return pixmap

    def _load_cover(self, cover_path: str) -> QPixmap:
        """Load cover from path with caching."""
        if not cover_path:
            return self._default_cover

        if cover_path in self._cover_cache:
            return self._cover_cache[cover_path]

        if Path(cover_path).exists():
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        self.COVER_SIZE, self.COVER_SIZE,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    self._cover_cache[cover_path] = scaled
                    return scaled
            except Exception:
                pass

        return self._default_cover

    def sizeHint(self, option, index):
        return QSize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def paint(self, painter, option, index):
        album = index.data(Qt.UserRole)
        if not album:
            return

        rect = option.rect
        is_hovered = option.state & QStyle.State_MouseOver

        # Draw cover
        cover = self._load_cover(album.cover_path)
        cover_rect = QRect(
            rect.x() + (rect.width() - self.COVER_SIZE) // 2,
            rect.y(),
            self.COVER_SIZE,
            self.COVER_SIZE
        )

        # Draw highlight background on hover
        if is_hovered:
            # Draw rounded rect background
            bg_rect = QRect(
                cover_rect.x() - 4,
                cover_rect.y() - 4,
                self.COVER_SIZE + 8,
                self.CARD_HEIGHT - 40
            )
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(30, 30, 30, 200))
            painter.drawRoundedRect(bg_rect, 12, 12)

            # Draw border
            painter.setPen(QPen(QColor("#1db954"), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(cover_rect, self.BORDER_RADIUS, self.BORDER_RADIUS)

        painter.drawPixmap(cover_rect, cover)

        # Draw album name
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setPixelSize(13)
        font.setBold(True)
        painter.setFont(font)

        name_rect = QRect(
            rect.x() + 4,
            rect.y() + self.COVER_SIZE + 8,
            rect.width() - 8,
            36
        )
        painter.drawText(name_rect, Qt.AlignLeft | Qt.TextWordWrap, album.display_name)

        # Draw artist name
        painter.setPen(QColor("#b3b3b3"))
        font.setBold(False)
        font.setPixelSize(12)
        painter.setFont(font)

        artist_rect = QRect(
            rect.x() + 4,
            rect.y() + self.COVER_SIZE + 44,
            rect.width() - 8,
            20
        )
        painter.drawText(artist_rect, Qt.AlignLeft, album.display_artist)

    def clear_cache(self):
        """Clear cover cache."""
        self._cover_cache.clear()


class AlbumsView(QWidget):
    """
    Albums page displaying a scrollable grid of album cards.
    Uses QListView with custom delegate for high performance.
    """

    album_clicked = Signal(object)  # Emits Album object
    play_album = Signal(list)  # Emits list of Track objects
    download_cover_requested = Signal(object)  # Emits Album object

    MARGIN = 20

    def __init__(
        self,
        library_service: LibraryService,
        cover_service: CoverService = None,
        parent=None
    ):
        super().__init__(parent)
        self._library = library_service
        self._cover_service = cover_service
        self._albums: List[Album] = []
        self._filtered_albums: List[Album] = []
        self._data_loaded = False
        self._load_worker = None
        self._hovered_index = -1

        self._setup_ui()
        self._connect_signals()

    def showEvent(self, event):
        """Load data when view is first shown."""
        super().showEvent(event)
        if not self._data_loaded:
            self._load_albums()

    def _setup_ui(self):
        """Set up the albums view UI."""
        self.setStyleSheet("background-color: #121212;")
        self.setMouseTracking(True)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # List view
        self._list_view = QListView()
        self._list_view.setViewMode(QListView.IconMode)
        self._list_view.setResizeMode(QListView.Adjust)
        self._list_view.setMovement(QListView.Static)
        self._list_view.setSelectionMode(QListView.SingleSelection)
        self._list_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list_view.setVerticalScrollMode(QListView.ScrollPerPixel)
        self._list_view.setMouseTracking(True)
        self._list_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_view.customContextMenuRequested.connect(self._show_context_menu)
        self._list_view.setStyleSheet("""
            QListView {
                background-color: #121212;
                border: none;
            }
            QListView::item {
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: #121212;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #4d4d4d;
            }
        """)

        # Model and delegate
        self._model = AlbumModel(self)
        self._delegate = AlbumDelegate(self)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)

        # Set grid size
        self._list_view.setGridSize(QSize(
            AlbumDelegate.CARD_WIDTH + AlbumDelegate.SPACING,
            AlbumDelegate.CARD_HEIGHT + AlbumDelegate.SPACING
        ))

        layout.addWidget(self._list_view)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()

    def _create_header(self) -> QWidget:
        """Create the header with title and search."""
        header = QFrame()
        header.setFixedHeight(80)
        header.setStyleSheet("""
            QFrame {
                background-color: #121212;
                border-bottom: 1px solid #282828;
            }
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 10, 20, 10)

        # Title
        title_label = QLabel(t("albums"))
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 28px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title_label)

        # Album count
        self._count_label = QLabel("")
        self._count_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 14px;
            }
        """)
        layout.addWidget(self._count_label)
        layout.addStretch()

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("search"))
        self._search_input.setFixedWidth(250)
        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                border: none;
                border-radius: 20px;
                padding: 8px 16px;
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit::placeholder {
                color: #7a7a7a;
            }
        """)
        layout.addWidget(self._search_input)

        return header

    def _create_loading_indicator(self) -> QWidget:
        """Create loading indicator."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        progress.setFixedSize(200, 4)
        progress.setStyleSheet("""
            QProgressBar {
                background-color: #2a2a2a;
                border: none;
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #1db954;
                border-radius: 2px;
            }
        """)
        layout.addWidget(progress)

        label = QLabel(t("loading"))
        label.setStyleSheet("color: #b3b3b3; font-size: 14px;")
        layout.addWidget(label)

        return widget

    def _connect_signals(self):
        """Connect signals."""
        self._search_input.textChanged.connect(self._on_search_changed)
        self._list_view.clicked.connect(self._on_album_clicked)
        self._list_view.entered.connect(self._on_item_entered)
        EventBus.instance().tracks_added.connect(self._on_tracks_added)
        EventBus.instance().cover_updated.connect(self._on_cover_updated)

    def _on_item_entered(self, index):
        """Handle item entered for hover effect."""
        self._hovered_index = index.row()
        self._list_view.viewport().setCursor(Qt.PointingHandCursor)

    def _show_context_menu(self, pos):
        """Show context menu for album."""
        index = self._list_view.indexAt(pos)
        if not index.isValid():
            return

        album = index.data(Qt.UserRole)
        if not album:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1db954;
                color: #000000;
            }
        """)

        # View details action
        view_action = QAction(t("view_details"), self)
        view_action.triggered.connect(lambda: self.album_clicked.emit(album))
        menu.addAction(view_action)

        # Download cover action
        download_action = QAction(t("download_cover_manual"), self)
        download_action.triggered.connect(lambda: self.download_cover_requested.emit(album))
        menu.addAction(download_action)

        menu.exec_(self._list_view.mapToGlobal(pos))

    def _load_albums(self, force: bool = False):
        """Load albums from library in background thread.

        Args:
            force: If True, reload even if data is already loaded
        """
        if self._data_loaded and not force:
            return

        if force:
            # Just reload data without showing loading indicator
            self._do_load_albums()
        else:
            self._loading.show()
            self._list_view.hide()
            self._do_load_albums()

    def _do_load_albums(self):
        """Actually load albums in background."""
        self._load_worker = LoadAlbumsWorker(self._library)
        self._load_worker.finished.connect(self._on_albums_loaded)
        self._load_worker.start()

    def _on_albums_loaded(self, albums: List[Album]):
        """Handle albums loaded from background thread."""
        self._albums = albums
        self._filtered_albums = albums.copy()
        self._data_loaded = True

        self._update_count_label()
        self._model.set_albums(self._filtered_albums)

        self._loading.hide()
        self._list_view.show()

        if self._load_worker:
            self._load_worker.deleteLater()
            self._load_worker = None

    def _update_count_label(self):
        """Update the album count label."""
        total = len(self._albums)
        if self._search_input.text():
            showing = len(self._filtered_albums)
            self._count_label.setText(f"{showing}/{total} {t('albums')}")
        else:
            self._count_label.setText(f"{total} {t('albums')}")

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        text = text.lower().strip()
        if text:
            self._filtered_albums = [
                a for a in self._albums
                if text in a.name.lower() or text in a.artist.lower()
            ]
        else:
            self._filtered_albums = self._albums.copy()

        self._update_count_label()
        self._model.set_albums(self._filtered_albums)

    def _on_album_clicked(self, index: QModelIndex):
        """Handle album click."""
        album = index.data(Qt.UserRole)
        if album:
            self.album_clicked.emit(album)

    def _on_tracks_added(self, count: int):
        """Handle tracks added to library."""
        self._data_loaded = False
        self._load_albums()

    def _on_cover_updated(self, item_id, is_cloud: bool = False):
        """Handle cover update from EventBus - update specific album cover."""
        # item_id format for album: "album_name:artist_name"
        if not isinstance(item_id, str) or ":" not in item_id:
            return

        album_name, artist_name = item_id.split(":", 1)

        # Find and update the matching album in the list
        for i, album in enumerate(self._filtered_albums):
            if album.name == album_name and album.artist == artist_name:
                # Reload this specific album from database
                updated_albums = self._library.get_albums()
                for updated_album in updated_albums:
                    if updated_album.name == album_name and updated_album.artist == artist_name:
                        self._filtered_albums[i] = updated_album
                        # Also update in the full list
                        for j, full_album in enumerate(self._albums):
                            if full_album.name == album_name and full_album.artist == artist_name:
                                self._albums[j] = updated_album
                                break
                        break
                # Clear delegate cache for this cover
                self._delegate.clear_cache()
                # Refresh the view
                self._model.set_albums(self._filtered_albums)
                break

    def refresh(self):
        """Refresh the albums view."""
        self._data_loaded = False
        self._load_albums()

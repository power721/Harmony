"""
Artists view widget for browsing artists in a grid layout.
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
)
from PySide6.QtCore import (
    Qt, Signal, QTimer, QThread,
    QAbstractListModel, QModelIndex, QSize, QRect
)
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QPen, QAction

from domain.artist import Artist
from services.library import LibraryService
from services.metadata import CoverService
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class LoadArtistsWorker(QThread):
    """Background worker to load artists."""
    finished = Signal(list)

    def __init__(self, library_service: LibraryService, parent=None):
        super().__init__(parent)
        self._library = library_service

    def run(self):
        artists = self._library.get_artists()
        self.finished.emit(artists)


class ArtistModel(QAbstractListModel):
    """Model for artist data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._artists: List[Artist] = []

    def rowCount(self, parent=QModelIndex()):
        return len(self._artists)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._artists):
            return None

        artist = self._artists[index.row()]

        if role == Qt.DisplayRole:
            return artist.name
        elif role == Qt.UserRole:
            return artist

        return None

    def set_artists(self, artists: List[Artist]):
        self.beginResetModel()
        self._artists = artists
        self.endResetModel()

    def get_artist(self, row: int) -> Optional[Artist]:
        if 0 <= row < len(self._artists):
            return self._artists[row]
        return None


class ArtistDelegate(QStyledItemDelegate):
    """Delegate for rendering artist cards."""

    # Card size constants
    COVER_SIZE = 180
    CARD_WIDTH = 180
    CARD_HEIGHT = 240
    BORDER_RADIUS = 90  # Circular
    SPACING = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cover_cache = {}
        self._default_cover = self._create_default_cover()

    def _create_default_cover(self) -> QPixmap:
        """Create default cover pixmap."""
        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circular background
        painter.setBrush(QColor("#3d3d3d"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, self.COVER_SIZE, self.COVER_SIZE)

        # Draw person icon
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(80)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, "\u265A"
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

                    self._cover_cache[cover_path] = circular
                    return circular
            except Exception:
                pass

        return self._default_cover

    def sizeHint(self, option, index):
        return QSize(self.CARD_WIDTH, self.CARD_HEIGHT)

    def paint(self, painter, option, index):
        artist = index.data(Qt.UserRole)
        if not artist:
            return

        rect = option.rect
        is_hovered = option.state & QStyle.State_MouseOver

        # Draw cover (circular)
        cover = self._load_cover(artist.cover_path)
        cover_x = rect.x() + (rect.width() - self.COVER_SIZE) // 2
        cover_y = rect.y()

        # Draw border on hover
        if is_hovered:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("#1db954"), 3))
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(cover_x - 2, cover_y - 2, self.COVER_SIZE + 4, self.COVER_SIZE + 4)

        painter.drawPixmap(cover_x, cover_y, cover)

        # Draw artist name
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
        painter.drawText(name_rect, Qt.AlignHCenter | Qt.TextWordWrap, artist.display_name)

        # Draw stats
        painter.setPen(QColor("#b3b3b3"))
        font.setBold(False)
        font.setPixelSize(11)
        painter.setFont(font)

        stats_text = f"{artist.song_count} {t('tracks')} • {artist.album_count} {t('albums')}"
        stats_rect = QRect(
            rect.x() + 4,
            rect.y() + self.COVER_SIZE + 44,
            rect.width() - 8,
            20
        )
        painter.drawText(stats_rect, Qt.AlignHCenter, stats_text)

    def clear_cache(self):
        """Clear cover cache."""
        self._cover_cache.clear()


class ArtistsView(QWidget):
    """
    Artists page displaying a scrollable grid of artist cards.
    Uses QListView with custom delegate for high performance.
    """

    artist_clicked = Signal(object)  # Emits Artist object
    download_cover_requested = Signal(object)  # Emits Artist object

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
        self._artists: List[Artist] = []
        self._filtered_artists: List[Artist] = []
        self._data_loaded = False
        self._load_worker = None

        self._setup_ui()
        self._connect_signals()

    def showEvent(self, event):
        """Load data when view is first shown."""
        super().showEvent(event)
        if not self._data_loaded:
            self._load_artists()

    def _setup_ui(self):
        """Set up the artists view UI."""
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
        self._model = ArtistModel(self)
        self._delegate = ArtistDelegate(self)
        self._list_view.setModel(self._model)
        self._list_view.setItemDelegate(self._delegate)

        # Set grid size
        self._list_view.setGridSize(QSize(
            ArtistDelegate.CARD_WIDTH + ArtistDelegate.SPACING,
            ArtistDelegate.CARD_HEIGHT + ArtistDelegate.SPACING
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
        title_label = QLabel(t("artists"))
        title_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 28px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title_label)

        # Artist count
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
        self._list_view.clicked.connect(self._on_artist_clicked)
        self._list_view.entered.connect(self._on_item_entered)
        EventBus.instance().tracks_added.connect(self._on_tracks_added)
        EventBus.instance().cover_updated.connect(self._on_cover_updated)

    def _on_item_entered(self, index):
        """Handle item entered for hover effect."""
        self._list_view.viewport().setCursor(Qt.PointingHandCursor)

    def _show_context_menu(self, pos):
        """Show context menu for artist."""
        index = self._list_view.indexAt(pos)
        if not index.isValid():
            return

        artist = index.data(Qt.UserRole)
        if not artist:
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
        view_action.triggered.connect(lambda: self.artist_clicked.emit(artist))
        menu.addAction(view_action)

        # Download cover action
        download_action = QAction(t("download_cover_manual"), self)
        download_action.triggered.connect(lambda: self.download_cover_requested.emit(artist))
        menu.addAction(download_action)

        menu.exec_(self._list_view.mapToGlobal(pos))

    def _load_artists(self, force: bool = False):
        """Load artists from library in background thread.

        Args:
            force: If True, reload even if data is already loaded
        """
        if self._data_loaded and not force:
            return

        if force:
            # Just reload data without showing loading indicator
            self._do_load_artists()
        else:
            self._loading.show()
            self._list_view.hide()
            self._do_load_artists()

    def _do_load_artists(self):
        """Actually load artists in background."""
        self._load_worker = LoadArtistsWorker(self._library)
        self._load_worker.finished.connect(self._on_artists_loaded)
        self._load_worker.start()

    def _on_artists_loaded(self, artists: List[Artist]):
        """Handle artists loaded from background thread."""
        self._artists = artists
        self._filtered_artists = artists.copy()
        self._data_loaded = True

        self._update_count_label()
        self._model.set_artists(self._filtered_artists)

        self._loading.hide()
        self._list_view.show()

        if self._load_worker:
            self._load_worker.deleteLater()
            self._load_worker = None

    def _update_count_label(self):
        """Update the artist count label."""
        total = len(self._artists)
        if self._search_input.text():
            showing = len(self._filtered_artists)
            self._count_label.setText(f"{showing}/{total} {t('artists')}")
        else:
            self._count_label.setText(f"{total} {t('artists')}")

    def _on_search_changed(self, text: str):
        """Handle search text change."""
        text = text.lower().strip()
        if text:
            self._filtered_artists = [
                a for a in self._artists
                if text in a.name.lower()
            ]
        else:
            self._filtered_artists = self._artists.copy()

        self._update_count_label()
        self._model.set_artists(self._filtered_artists)

    def _on_artist_clicked(self, index: QModelIndex):
        """Handle artist click."""
        artist = index.data(Qt.UserRole)
        if artist:
            self.artist_clicked.emit(artist)

    def _on_tracks_added(self, count: int):
        """Handle tracks added to library."""
        self._data_loaded = False
        self._load_artists()

    def _on_cover_updated(self, item_id, is_cloud: bool = False):
        """Handle cover update from EventBus - update specific artist cover."""
        # item_id for artist is the artist name
        if not isinstance(item_id, str):
            return

        artist_name = item_id

        # Find and update the matching artist in the list
        for i, artist in enumerate(self._filtered_artists):
            if artist.name == artist_name:
                # Reload this specific artist from database
                updated_artist = self._library.get_artist_by_name(artist_name)
                if updated_artist:
                    self._filtered_artists[i] = updated_artist
                    # Also update in the full list
                    for j, full_artist in enumerate(self._artists):
                        if full_artist.name == artist_name:
                            self._artists[j] = updated_artist
                            break
                # Clear delegate cache for this cover
                self._delegate.clear_cache()
                # Refresh the view
                self._model.set_artists(self._filtered_artists)
                break

    def refresh(self):
        """Refresh the artists view."""
        self._data_loaded = False
        self._load_artists()

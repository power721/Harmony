"""
Online music detail view.
Shows details for artist, album, or playlist.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QScrollArea,
    QFrame,
    QMenu,
    QMessageBox,
    QGridLayout,
    QGraphicsDropShadowEffect,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QThread, QSize, QRect, QPropertyAnimation, QEasingCurve, QTimer
from PySide6.QtGui import QCursor, QColor, QBrush, QPixmap, QPainter, QFont, QAction

from domain.online_music import OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist
from services.online import OnlineMusicService, OnlineDownloadService
from system.i18n import t
from system.event_bus import EventBus
from utils import format_duration

logger = logging.getLogger(__name__)


class DetailWorker(QThread):
    """Background worker for loading detail data."""

    detail_loaded = Signal(str, object)  # (type, data)

    def __init__(self, service: OnlineMusicService, detail_type: str, mid: str,
                 page: int = 1, page_size: int = 30):
        super().__init__()
        self._service = service
        self._detail_type = detail_type
        self._mid = mid
        self._page = page
        self._page_size = page_size

    def run(self):
        try:
            if self._detail_type == "artist":
                data = self._service.get_artist_detail(self._mid, page=self._page, page_size=self._page_size)
            elif self._detail_type == "album":
                data = self._service.get_album_detail(self._mid, page=self._page, page_size=self._page_size)
            elif self._detail_type == "playlist":
                data = self._service.get_playlist_detail(self._mid, page=self._page, page_size=self._page_size)
            else:
                data = None

            self.detail_loaded.emit(self._detail_type, data)
        except Exception as e:
            logger.error(f"Failed to load detail: {e}")


class AlbumListWorker(QThread):
    """Background worker for loading artist albums."""

    albums_loaded = Signal(list, int)  # (albums list, total count)

    def __init__(self, service: OnlineMusicService, singer_mid: str, number: int = 10, begin: int = 0):
        super().__init__()
        self._service = service
        self._singer_mid = singer_mid
        self._number = number
        self._begin = begin

    def run(self):
        try:
            result = self._service.get_artist_albums(self._singer_mid, number=self._number, begin=self._begin)
            albums = result.get('albums', [])
            total = result.get('total', 0)
            self.albums_loaded.emit(albums, total)
        except Exception as e:
            logger.error(f"Failed to load artist albums: {e}", exc_info=True)
            self.albums_loaded.emit([], 0)


class AlbumCoverLoader(QThread):
    """Background worker for loading album cover images with disk caching."""

    cover_loaded = Signal(QPixmap)

    def __init__(self, url: str, size: int):
        super().__init__()
        self._url = url
        self._size = size

    def run(self):
        try:
            from infrastructure.cache import ImageCache
            import requests

            # Check disk cache first
            image_data = ImageCache.get(self._url)
            if not image_data:
                # Download from network
                response = requests.get(self._url, timeout=10)
                response.raise_for_status()
                image_data = response.content
                # Save to cache
                ImageCache.set(self._url, image_data)

            pixmap = QPixmap()
            if pixmap.loadFromData(image_data):
                scaled = pixmap.scaled(
                    self._size, self._size,
                    Qt.KeepAspectRatioByExpanding,
                    Qt.SmoothTransformation
                )
                self.cover_loaded.emit(scaled)
        except Exception as e:
            logger.debug(f"Error loading album cover: {e}")


class OnlineAlbumCard(QWidget):
    """Card widget for displaying online album information."""

    clicked = Signal(object)  # Emits OnlineAlbum object

    COVER_SIZE = 150
    CARD_WIDTH = 150
    CARD_HEIGHT = 200
    BORDER_RADIUS = 8

    def __init__(self, album_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self._album_data = album_data
        self._album = OnlineAlbum(
            mid=album_data.get("mid", ""),
            name=album_data.get("name", ""),
            singer_mid=album_data.get("singer_mid", ""),
            singer_name=album_data.get("singer_name", ""),
            cover_url=album_data.get("cover_url", ""),
            song_count=album_data.get("song_count", 0),
            publish_date=album_data.get("publish_date", ""),
        )
        self._is_hovering = False
        self._cover_loaded = False

        self._setup_ui()
        self._set_default_cover()
        QTimer.singleShot(10, self._load_cover)

    def _setup_ui(self):
        """Set up the card UI."""
        self.setFixedSize(self.CARD_WIDTH, self.CARD_HEIGHT)
        self.setCursor(Qt.PointingHandCursor)

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Cover container
        self._cover_container = QFrame()
        self._cover_container.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
        self._cover_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)

        # Cover label
        self._cover_label = QLabel(self._cover_container)
        self._cover_label.setFixedSize(self.COVER_SIZE, self.COVER_SIZE)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)

        # Info container
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(4, 0, 4, 0)
        info_layout.setSpacing(2)

        # Album name
        self._name_label = QLabel(self._album.name or "Unknown")
        self._name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 12px;
                font-weight: bold;
                background: transparent;
            }
        """)
        self._name_label.setWordWrap(True)
        self._name_label.setMaximumHeight(32)

        info_layout.addWidget(self._name_label)
        info_layout.addStretch()

        layout.addWidget(self._cover_container, 0, Qt.AlignHCenter)
        layout.addWidget(info_widget)

    def _load_cover(self, force: bool = False):
        """Load album cover image asynchronously."""
        if self._cover_loaded and not force:
            return

        cover_url = self._album.cover_url
        if not cover_url:
            return

        # Create a worker thread for loading cover
        self._cover_loader = AlbumCoverLoader(cover_url, self.COVER_SIZE)
        self._cover_loader.cover_loaded.connect(self._on_cover_loaded)
        self._cover_loader.start()

    def _on_cover_loaded(self, pixmap: QPixmap):
        """Handle cover loaded."""
        if not pixmap.isNull():
            self._cover_label.setPixmap(pixmap)
            self._cover_loaded = True

    def _set_default_cover(self):
        """Set default cover when no cover is available."""
        pixmap = QPixmap(self.COVER_SIZE, self.COVER_SIZE)
        pixmap.fill(QColor("#3d3d3d"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(48)
        painter.setFont(font)
        painter.drawText(
            QRect(0, 0, self.COVER_SIZE, self.COVER_SIZE),
            Qt.AlignCenter, "\u266B"
        )
        painter.end()

        self._cover_label.setPixmap(pixmap)

    def enterEvent(self, event):
        """Handle mouse enter for hover effect."""
        self._is_hovering = True
        self._cover_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
                border: 2px solid #1db954;
            }}
        """)
        super().enterEvent(event)

    def leaveEvent(self, event):
        """Handle mouse leave for hover effect."""
        self._is_hovering = False
        self._cover_container.setStyleSheet(f"""
            QFrame {{
                background-color: #2a2a2a;
                border-radius: {self.BORDER_RADIUS}px;
            }}
        """)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        """Handle mouse click."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._album)
        super().mousePressEvent(event)

    def get_album(self) -> OnlineAlbum:
        """Get the album object."""
        return self._album


class OnlineDetailView(QWidget):
    """Detail view for artist, album, or playlist."""

    back_requested = Signal()
    play_all = Signal(list)  # List of OnlineTrack
    insert_all_to_queue = Signal(list)
    add_all_to_queue = Signal(list)
    album_clicked = Signal(object)  # OnlineAlbum

    def __init__(
        self,
        config_manager=None,
        db_manager=None,
        qqmusic_service=None,
        parent=None
    ):
        super().__init__(parent)

        self._config = config_manager
        self._db = db_manager
        self._service = OnlineMusicService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service
        )
        self._download_service = OnlineDownloadService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service,
            online_music_service=self._service
        )
        self._event_bus = EventBus.instance()

        self._detail_type = ""  # "artist", "album", "playlist"
        self._mid = ""
        self._cover_url = ""  # Store actual cover URL for full-size display
        self._tracks: List[OnlineTrack] = []
        self._detail_worker: Optional[DetailWorker] = None
        self._album_list_worker: Optional[AlbumListWorker] = None
        self._album_cards: List[OnlineAlbumCard] = []
        self._albums_loaded = 0  # Track how many albums have been loaded
        self._albums_total = 0  # Total album count from API
        self._albums_append = False  # Flag for append mode

        # Pagination state
        self._current_page = 1
        self._total_pages = 1
        self._total_songs = 0
        self._page_size = 30  # QQ Music API max per page

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(8)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Info section
        self._info_section = self._create_info_section()
        layout.addWidget(self._info_section)

        # Albums section (for artist detail)
        self._albums_section = self._create_albums_section()
        layout.addWidget(self._albums_section)

        # Songs section (title + table)
        self._songs_section = self._create_songs_section()
        layout.addWidget(self._songs_section, 1)  # Give stretch priority

    def _create_header(self) -> QWidget:
        """Create header with back button."""
        widget = QWidget()
        widget.setFixedHeight(28)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Back button
        self._back_btn = QPushButton("← " + t("back"))
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.clicked.connect(self.back_requested.emit)
        layout.addWidget(self._back_btn)

        layout.addStretch()

        return widget

    def _create_info_section(self) -> QWidget:
        """Create info section."""
        widget = QWidget()
        self._info_layout = QHBoxLayout(widget)
        self._info_layout.setContentsMargins(0, 0, 0, 0)
        self._info_layout.setSpacing(12)

        # Cover/Avatar placeholder - clickable
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(120, 120)
        self._cover_label.setStyleSheet("""
            background: #333;
            border-radius: 8px;
        """)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setCursor(Qt.PointingHandCursor)
        self._cover_label.mousePressEvent = self._on_cover_clicked
        self._info_layout.addWidget(self._cover_label)

        # Info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)

        # Type label
        self._type_label = QLabel()
        self._type_label.setStyleSheet("color: #808080; font-size: 11px;")
        info_layout.addWidget(self._type_label)

        # Name
        self._name_label = QLabel()
        self._name_label.setStyleSheet("color: white; font-size: 18px; font-weight: bold;")
        info_layout.addWidget(self._name_label)

        # Secondary info (artist/creator)
        self._secondary_label = QLabel()
        self._secondary_label.setStyleSheet("color: #808080; font-size: 12px;")
        info_layout.addWidget(self._secondary_label)

        # Extra info row (company, genre, language, etc.)
        self._extra_label = QLabel()
        self._extra_label.setStyleSheet("color: #666; font-size: 11px;")
        self._extra_label.setWordWrap(True)
        info_layout.addWidget(self._extra_label)

        # Stats
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #1db954; font-size: 12px;")
        info_layout.addWidget(self._stats_label)

        info_layout.addStretch()
        self._info_layout.addWidget(info_widget, 1)

        return widget

    def _create_actions(self) -> QWidget:
        """Create action buttons."""
        widget = QWidget()
        widget.setFixedHeight(32)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Play all
        self._play_all_btn = QPushButton(t("play_all"))
        self._play_all_btn.setObjectName("primaryBtn")
        self._play_all_btn.setCursor(Qt.PointingHandCursor)
        self._play_all_btn.setFixedHeight(28)
        self._play_all_btn.clicked.connect(self._on_play_all)
        layout.addWidget(self._play_all_btn)

        # Add to queue
        self._add_queue_btn = QPushButton(t("add_all_to_queue"))
        self._add_queue_btn.setCursor(Qt.PointingHandCursor)
        self._add_queue_btn.setFixedHeight(28)
        self._add_queue_btn.clicked.connect(self._on_add_all_to_queue)
        layout.addWidget(self._add_queue_btn)

        layout.addStretch()

        return widget

    def _create_pagination(self) -> QWidget:
        """Create pagination widget."""
        widget = QWidget()
        widget.setFixedHeight(32)
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Previous button
        self._prev_page_btn = QPushButton("← " + t("previous_page"))
        self._prev_page_btn.setFixedHeight(28)
        self._prev_page_btn.setCursor(Qt.PointingHandCursor)
        self._prev_page_btn.clicked.connect(self._on_prev_page)
        layout.addWidget(self._prev_page_btn)

        # Page label
        self._page_label = QLabel("1 / 1")
        self._page_label.setStyleSheet("color: #808080; padding: 0 10px;")
        layout.addWidget(self._page_label)

        # Next button
        self._next_page_btn = QPushButton(t("next_page") + " →")
        self._next_page_btn.setFixedHeight(28)
        self._next_page_btn.setCursor(Qt.PointingHandCursor)
        self._next_page_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_page_btn)

        layout.addStretch()

        # Initially hidden
        widget.hide()

        return widget

    def _create_albums_section(self) -> QWidget:
        """Create albums grid section for artist detail."""
        section = QWidget()
        section.setStyleSheet("background-color: #1a1a1a;")
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 8, 0, 8)
        section_layout.setSpacing(12)

        # Header with title and load more button
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Section title
        self._albums_title_label = QLabel(t("albums"))
        self._albums_title_label.setStyleSheet("""
            QLabel {
                color: #1db954;
                font-size: 18px;
                font-weight: bold;
                padding: 4px 0;
            }
        """)
        header_layout.addWidget(self._albums_title_label)

        header_layout.addStretch()

        # Load more button
        self._load_more_albums_btn = QPushButton(t("load_more"))
        self._load_more_albums_btn.setCursor(Qt.PointingHandCursor)
        self._load_more_albums_btn.setFixedHeight(28)
        self._load_more_albums_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #1db954;
                border: 1px solid #1db954;
                border-radius: 14px;
                padding: 4px 16px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #1db954;
                color: #000000;
            }
        """)
        self._load_more_albums_btn.clicked.connect(self._on_load_more_albums)
        header_layout.addWidget(self._load_more_albums_btn)

        section_layout.addWidget(header_widget)

        # Albums container with horizontal scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(False)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setFixedHeight(210)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background-color: #3d3d3d;
                border-radius: 4px;
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #4d4d4d;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                width: 0px;
            }
        """)

        # Albums container
        self._albums_container = QWidget()
        self._albums_container.setStyleSheet("background-color: transparent;")
        self._albums_container.setMinimumHeight(200)
        self._albums_layout = QHBoxLayout(self._albums_container)
        self._albums_layout.setContentsMargins(0, 0, 0, 0)
        self._albums_layout.setSpacing(16)
        self._albums_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        scroll_area.setWidget(self._albums_container)
        section_layout.addWidget(scroll_area)

        # Initially hidden
        section.hide()

        return section

    def _create_songs_section(self) -> QWidget:
        """Create songs section with title and table."""
        section = QWidget()
        section_layout = QVBoxLayout(section)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(8)

        # Section title
        self._songs_title_label = QLabel(t("songs"))
        self._songs_title_label.setStyleSheet("""
            QLabel {
                color: #1db954;
                font-size: 18px;
                font-weight: bold;
                padding: 4px 0;
            }
        """)
        section_layout.addWidget(self._songs_title_label)

        # Actions
        actions = self._create_actions()
        section_layout.addWidget(actions)

        # Pagination
        self._pagination_widget = self._create_pagination()
        section_layout.addWidget(self._pagination_widget)

        # Songs table
        self._songs_table = self._create_songs_table()
        section_layout.addWidget(self._songs_table, 1)

        return section

    def _create_songs_table(self) -> QTableWidget:
        """Create songs table."""
        table = QTableWidget()
        table.setObjectName("detailSongsTable")
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels([
            "#", t("title"), t("artist"), t("album"), t("duration")
        ])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        table.setColumnWidth(0, 50)
        table.setColumnWidth(4, 80)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.doubleClicked.connect(self._on_track_double_clicked)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_track_context_menu)

        # Same style as library view
        table.setStyleSheet("""
            QTableWidget#detailSongsTable {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget#detailSongsTable::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            QTableWidget#detailSongsTable::item:alternate {
                background-color: #252525;
            }
            QTableWidget#detailSongsTable::item:!alternate {
                background-color: #1e1e1e;
            }
            QTableWidget#detailSongsTable::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget#detailSongsTable::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget#detailSongsTable::item:selected:alternate {
                background-color: #1ed760;
            }
            QTableWidget#detailSongsTable::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget#detailSongsTable::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#detailSongsTable::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget#detailSongsTable:focus {
                outline: none;
                border: none;
            }
            QTableWidget#detailSongsTable QHeaderView::section {
                background-color: #2a2a2a;
                color: #1db954;
                padding: 14px 12px;
                border: none;
                border-bottom: 2px solid #1db954;
                font-weight: bold;
                text-transform: uppercase;
                font-size: 12px;
                letter-spacing: 0.5px;
            }
            QTableWidget#detailSongsTable QTableCornerButton::section {
                background-color: #2a2a2a;
                border: none;
                border-right: 1px solid #3a3a3a;
                border-bottom: 2px solid #1db954;
            }
            QTableWidget#detailSongsTable QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QTableWidget#detailSongsTable QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget#detailSongsTable QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QTableWidget#detailSongsTable QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border-radius: 6px;
            }
            QTableWidget#detailSongsTable QScrollBar::handle:horizontal {
                background-color: #404040;
                border-radius: 6px;
                min-width: 40px;
            }
            QTableWidget#detailSongsTable QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            QTableWidget#detailSongsTable QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
                width: 0px;
            }
        """)

        return table

    def _apply_styles(self):
        """Apply styles."""
        self.setStyleSheet("""
            QPushButton {
                background: #333;
                color: white;
                border: none;
                padding: 4px 16px;
                border-radius: 14px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #444;
            }
            QPushButton#primaryBtn {
                background: #1db954;
            }
            QPushButton#primaryBtn:hover {
                background: #1ed760;
            }
        """)

    def load_artist(self, mid: str, name: str = ""):
        """Load artist detail."""
        self._detail_type = "artist"
        self._mid = mid
        self._current_page = 1  # Reset to first page

        # Set placeholder info
        self._type_label.setText(t("artist"))
        self._name_label.setText(name)
        self._secondary_label.setText("")
        self._extra_label.setText("")
        self._stats_label.setText("")

        # Show albums section for artist
        self._albums_section.show()

        self._load_detail()

    def load_album(self, mid: str, name: str = "", singer_name: str = ""):
        """Load album detail."""
        self._detail_type = "album"
        self._mid = mid
        self._current_page = 1  # Reset to first page

        # Set placeholder info
        self._type_label.setText(t("album"))
        self._name_label.setText(name)
        self._secondary_label.setText(singer_name)
        self._extra_label.setText("")
        self._stats_label.setText("")

        # Hide albums section for album detail
        self._albums_section.hide()

        self._load_detail()

    def load_playlist(self, playlist_id: str, title: str = "", creator: str = ""):
        """Load playlist detail."""
        self._detail_type = "playlist"
        self._mid = playlist_id
        self._current_page = 1  # Reset to first page

        # Set placeholder info
        self._type_label.setText(t("playlist"))
        self._name_label.setText(title)
        self._secondary_label.setText(creator)
        self._extra_label.setText("")
        self._stats_label.setText("")

        # Hide albums section for playlist detail
        self._albums_section.hide()

        self._load_detail()

    def _load_detail(self):
        """Load detail data."""
        if self._detail_worker and self._detail_worker.isRunning():
            self._detail_worker.terminate()

        self._detail_worker = DetailWorker(
            self._service,
            self._detail_type,
            self._mid,
            self._current_page,
            self._page_size
        )
        self._detail_worker.detail_loaded.connect(self._on_detail_loaded)
        self._detail_worker.start()

    def _on_detail_loaded(self, detail_type: str, data: Optional[Dict]):
        """Handle detail loaded."""
        if not data:
            self._name_label.setText(t("detail_not_available"))
            self._secondary_label.setText(t("qqmusic_login_required"))
            return

        if detail_type == "artist":
            self._display_artist_detail(data)
        elif detail_type == "album":
            self._display_album_detail(data)
        elif detail_type == "playlist":
            self._display_playlist_detail(data)

    def _display_artist_detail(self, data: Dict):
        """Display artist detail."""
        self._name_label.setText(data.get("name", ""))
        self._secondary_label.setText(data.get("desc", "")[:100] + "..." if data.get("desc") else "")
        self._extra_label.setText("")

        # Load artist cover
        avatar_url = data.get("avatar", "")
        if avatar_url:
            self._cover_url = avatar_url
            self._load_cover(avatar_url)

        songs = data.get("songs", [])
        total = data.get("total", len(songs))
        page = data.get("page", 1)
        page_size = data.get("page_size", 50)

        # Update pagination state
        self._total_songs = total
        self._page_size = page_size  # Update page_size from response
        self._total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        self._tracks = self._parse_songs(songs)

        # Display stats showing loaded vs total songs and album count
        album_count = data.get("album_count", 0)
        stats_parts = []
        if total > len(self._tracks):
            stats_parts.append(f"{len(self._tracks)} / {total} {t('songs')}")
        else:
            stats_parts.append(f"{total} {t('songs')}")
        if album_count > 0:
            stats_parts.append(f"{album_count} {t('albums')}")
        self._stats_label.setText(" · ".join(stats_parts))

        # Update pagination controls
        self._update_pagination()
        self._display_songs(self._tracks)

        # Load artist albums
        self._load_artist_albums()

    def _update_pagination(self):
        """Update pagination controls visibility and state."""
        # Show pagination for any detail type with multiple pages
        if self._total_pages > 1:
            self._pagination_widget.show()
            self._page_label.setText(f"{self._current_page} / {self._total_pages}")
            self._prev_page_btn.setEnabled(self._current_page > 1)
            self._next_page_btn.setEnabled(self._current_page < self._total_pages)
        else:
            self._pagination_widget.hide()

    def _update_artist_stats(self):
        """Update artist stats label with song and album counts."""
        if self._detail_type != "artist":
            return

        stats_parts = []
        # Song count
        total = self._total_songs
        if total > len(self._tracks):
            stats_parts.append(f"{len(self._tracks)} / {total} {t('songs')}")
        else:
            stats_parts.append(f"{total} {t('songs')}")

        # Album count
        if self._albums_total > 0:
            stats_parts.append(f"{self._albums_total} {t('albums')}")

        self._stats_label.setText(" · ".join(stats_parts))

    def _on_prev_page(self):
        """Handle previous page button click."""
        if self._current_page > 1:
            self._current_page -= 1
            self._load_detail()

    def _on_next_page(self):
        """Handle next page button click."""
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_detail()

    def _load_cover(self, url: str):
        """Load cover image from URL."""
        from PySide6.QtGui import QPixmap
        from PySide6.QtCore import QThread, Signal
        from infrastructure.cache import ImageCache
        import requests

        class CoverLoader(QThread):
            loaded = Signal(QPixmap)

            def __init__(self, url):
                super().__init__()
                self.url = url

            def run(self):
                try:
                    # Check disk cache first
                    image_data = ImageCache.get(self.url)
                    if not image_data:
                        response = requests.get(self.url, timeout=10)
                        response.raise_for_status()
                        image_data = response.content
                        ImageCache.set(self.url, image_data)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(image_data):
                        self.loaded.emit(pixmap)
                except Exception as e:
                    logger.debug(f"Failed to load cover: {e}")

        if hasattr(self, '_cover_loader'):
            self._cover_loader.terminate()

        self._cover_loader = CoverLoader(url)
        self._cover_loader.loaded.connect(lambda pixmap: self._cover_label.setPixmap(
            pixmap.scaled(self._cover_label.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        ))
        self._cover_loader.start()

    def _on_cover_clicked(self, event):
        """Handle cover click to show full size image."""
        if not self._cover_url:
            return

        cover_url = self._cover_url

        # Try to get high-res version for y.gtimg.cn URLs
        if "y.gtimg.cn" in cover_url:
            if "R300x300" in cover_url:
                cover_url = cover_url.replace("R300x300", "R800x800")

        # For qpic.y.qq.com (playlist covers), use original URL as-is
        # The /600 suffix is already a reasonable size

        self._show_cover_dialog_async(cover_url)

    def _show_cover_dialog_async(self, url: str):
        """Show cover image in a dialog (async loading)."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel
        from PySide6.QtGui import QPixmap

        # Create dialog first
        dialog = QDialog(self)
        dialog.setWindowTitle(self._name_label.text() or t("cover"))
        dialog.setWindowFlags(dialog.windowFlags() | Qt.FramelessWindowHint)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)

        # Image label with loading state
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("background: #1a1a1a;")
        image_label.setText(t("loading"))
        image_label.setMinimumSize(200, 200)

        # Close on click
        dialog.mousePressEvent = lambda e: dialog.close()

        layout.addWidget(image_label)

        # Async load
        class FullCoverLoader(QThread):
            loaded = Signal(QPixmap)

            def __init__(self, url):
                super().__init__()
                self.url = url

            def run(self):
                try:
                    from infrastructure.cache import ImageCache
                    import requests
                    # Check disk cache first
                    image_data = ImageCache.get(self.url)
                    if not image_data:
                        response = requests.get(self.url, timeout=10)
                        response.raise_for_status()
                        image_data = response.content
                        ImageCache.set(self.url, image_data)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(image_data):
                        self.loaded.emit(pixmap)
                except Exception as e:
                    logger.debug(f"Failed to load cover for dialog: {e}")

        def on_cover_loaded(pixmap):
            if dialog.isVisible():
                # Scale to fit screen
                screen = self.screen() if self.screen() else None
                max_size = 600
                if screen:
                    max_size = min(screen.availableGeometry().width() - 100,
                                   screen.availableGeometry().height() - 100,
                                   600)

                if pixmap.width() > max_size or pixmap.height() > max_size:
                    pixmap = pixmap.scaled(max_size, max_size,
                                           Qt.KeepAspectRatio,
                                           Qt.SmoothTransformation)

                image_label.setPixmap(pixmap)
                image_label.setMinimumSize(pixmap.size())
                dialog.setFixedSize(pixmap.size())

        if hasattr(self, '_full_cover_loader') and self._full_cover_loader:
            self._full_cover_loader.terminate()

        self._full_cover_loader = FullCoverLoader(url)
        self._full_cover_loader.loaded.connect(on_cover_loaded)
        self._full_cover_loader.start()

        dialog.exec()

    def _display_album_detail(self, data: Dict):
        """Display album detail."""
        self._name_label.setText(data.get("name", ""))
        self._secondary_label.setText(data.get("singer", ""))

        # Extra info: company, genre, language, publish date
        extra_parts = []
        if data.get("publish_date"):
            extra_parts.append(data.get("publish_date", "")[:10])
        if data.get("company"):
            extra_parts.append(data.get("company", ""))
        if data.get("language"):
            extra_parts.append(data.get("language", ""))
        if data.get("album_type"):
            extra_parts.append(data.get("album_type", ""))
        self._extra_label.setText(" · ".join(extra_parts))

        # Load album cover
        cover_url = data.get("cover_url", "")
        if not cover_url:
            album_mid = data.get("mid", "")
            if album_mid:
                cover_url = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg"
        if cover_url:
            self._cover_url = cover_url
            self._load_cover(cover_url)

        songs = data.get("songs", [])
        total = data.get("total", len(songs))
        page = data.get("page", 1)
        page_size = data.get("page_size", 50)

        # Update pagination state
        self._total_songs = total
        self._page_size = page_size  # Update page_size from response
        self._total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        self._tracks = self._parse_songs(songs)

        # Display stats
        if total > len(self._tracks):
            self._stats_label.setText(f"{len(self._tracks)} / {total} {t('songs')}")
        else:
            self._stats_label.setText(f"{len(self._tracks)} {t('songs')}")

        # Update pagination controls
        self._update_pagination()
        self._display_songs(self._tracks)

    def _display_playlist_detail(self, data: Dict):
        """Display playlist detail."""
        self._name_label.setText(data.get("name", ""))
        self._secondary_label.setText(data.get("creator", ""))
        self._extra_label.setText("")

        # Load playlist cover
        cover_url = data.get("cover_url", "") or data.get("cover", "")
        if cover_url:
            self._cover_url = cover_url
            self._load_cover(cover_url)

        songs = data.get("songs", [])
        total = data.get("total", len(songs))
        page = data.get("page", 1)
        page_size = data.get("page_size", 50)

        # Update pagination state
        self._total_songs = total
        self._page_size = page_size  # Update page_size from response
        self._total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        self._tracks = self._parse_songs(songs)

        # Display stats
        if total > len(self._tracks):
            self._stats_label.setText(f"{len(self._tracks)} / {total} {t('songs')}")
        else:
            self._stats_label.setText(f"{len(self._tracks)} {t('songs')}")

        # Update pagination controls
        self._update_pagination()
        self._display_songs(self._tracks)

    def _parse_songs(self, songs: List[Dict]) -> List[OnlineTrack]:
        """Parse songs from API response."""
        from domain.online_music import OnlineSinger, AlbumInfo

        tracks = []
        for song in songs:
            # Parse singers - handle different formats
            singers = []
            singer_data = song.get("singer", [])
            if isinstance(singer_data, list):
                for s in singer_data:
                    if isinstance(s, dict):
                        singers.append(OnlineSinger(
                            mid=s.get("mid", ""),
                            name=s.get("name", "")
                        ))
                    elif isinstance(s, str):
                        singers.append(OnlineSinger(mid="", name=s))
            elif isinstance(singer_data, dict):
                singers.append(OnlineSinger(
                    mid=singer_data.get("mid", ""),
                    name=singer_data.get("name", "")
                ))
            elif isinstance(singer_data, str):
                singers.append(OnlineSinger(mid="", name=singer_data))

            # Parse album - handle different formats
            album_data = song.get("album")
            if isinstance(album_data, dict):
                album = AlbumInfo(
                    mid=album_data.get("mid", ""),
                    name=album_data.get("name", "")
                )
            elif isinstance(album_data, str):
                album = AlbumInfo(mid="", name=album_data)
            else:
                album = AlbumInfo(
                    mid=song.get("albummid", song.get("albumMid", "")),
                    name=song.get("albumname", song.get("albumName", ""))
                )

            track = OnlineTrack(
                mid=song.get("mid", song.get("songmid", song.get("songMid", ""))),
                id=song.get("id", song.get("songid", song.get("songId"))),
                title=song.get("name", song.get("songname", song.get("songName", song.get("title", "")))),
                singer=singers,
                album=album,
                duration=song.get("interval", song.get("duration", 0))
            )
            tracks.append(track)

        return tracks

    def _display_songs(self, songs: List[OnlineTrack]):
        """Display songs in table."""
        self._songs_table.setRowCount(len(songs))

        for i, song in enumerate(songs):
            # Index
            self._songs_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            # Title
            self._songs_table.setItem(i, 1, QTableWidgetItem(song.title))

            # Artist
            self._songs_table.setItem(i, 2, QTableWidgetItem(song.singer_name))

            # Album
            self._songs_table.setItem(i, 3, QTableWidgetItem(song.album_name))

            # Duration
            duration_str = format_duration(song.duration) if song.duration else ""
            self._songs_table.setItem(i, 4, QTableWidgetItem(duration_str))

    def _load_artist_albums(self, append: bool = False):
        """Load artist albums in background.

        Args:
            append: If True, append to existing albums; otherwise replace
        """
        if self._detail_type != "artist" or not self._mid:
            self._albums_section.hide()
            return

        if self._album_list_worker and self._album_list_worker.isRunning():
            self._album_list_worker.terminate()

        begin = self._albums_loaded if append else 0
        number = 10

        # Store append flag for callback
        self._albums_append = append

        self._album_list_worker = AlbumListWorker(self._service, self._mid, number=number, begin=begin)
        self._album_list_worker.albums_loaded.connect(self._on_albums_loaded, Qt.QueuedConnection)
        self._album_list_worker.start()

    def _on_albums_loaded(self, albums: List[Dict[str, Any]], total: int = 0):
        """Handle artist albums loaded.

        Args:
            albums: List of album data
            total: Total album count from API
        """
        append = getattr(self, '_albums_append', False)

        if not append:
            # Clear existing cards
            for card in self._album_cards:
                self._albums_layout.removeWidget(card)
                card.deleteLater()
            self._album_cards.clear()
            self._albums_loaded = 0
            # Store total count and update stats display
            self._albums_total = total
            self._update_artist_stats()

        if not albums:
            if not append:
                self._albums_section.hide()
            self._load_more_albums_btn.hide()
            return

        # Create album cards
        for album_data in albums:
            card = OnlineAlbumCard(album_data)
            card.clicked.connect(self._on_album_card_clicked)
            self._albums_layout.addWidget(card)
            self._album_cards.append(card)

        # Update loaded count - add to existing if appending
        self._albums_loaded += len(albums)

        # Update container width
        total_width = len(self._album_cards) * (OnlineAlbumCard.CARD_WIDTH + 16)
        self._albums_container.setFixedWidth(max(total_width, self.width()))
        self._albums_container.setMinimumHeight(200)

        # Force layout update
        self._albums_layout.update()
        self._albums_container.updateGeometry()

        # Show/hide load more button based on whether there are more albums
        if self._albums_loaded < self._albums_total:
            self._load_more_albums_btn.show()
        else:
            self._load_more_albums_btn.hide()

        self._albums_section.show()
        self._albums_section.raise_()  # Bring to front

    def _on_load_more_albums(self):
        """Handle load more albums button click."""
        self._load_artist_albums(append=True)

    def _on_album_card_clicked(self, album: OnlineAlbum):
        """Handle album card click."""
        self.album_clicked.emit(album)

    def _on_play_all(self):
        """Play all tracks."""
        if self._tracks:
            self.play_all.emit(self._tracks)

    def _on_add_all_to_queue(self):
        """Add all tracks to queue."""
        if self._tracks:
            self.add_all_to_queue.emit(self._tracks)

    def _on_track_double_clicked(self, index):
        """Handle track double click."""
        row = index.row()
        if 0 <= row < len(self._tracks):
            # TODO: Play single track
            pass

    def _show_track_context_menu(self, pos):
        """Show context menu for track."""
        selected_rows = self._songs_table.selectionModel().selectedRows()
        if not selected_rows:
            return

        # Get selected tracks
        selected_tracks = []
        for index in sorted(selected_rows, key=lambda x: x.row()):
            row = index.row()
            if 0 <= row < len(self._tracks):
                selected_tracks.append(self._tracks[row])

        if not selected_tracks:
            return

        is_single = len(selected_tracks) == 1
        track = selected_tracks[0] if is_single else None

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #2a2a2a;
                color: white;
                border: 1px solid #444;
            }
            QMenu::item:selected {
                background: #1db954;
            }
        """)

        play_action = menu.addAction(t("play"))

        insert_action = menu.addAction(t("insert_to_queue"))
        add_action = menu.addAction(t("add_to_queue"))

        menu.addSeparator()

        # Add to favorites action
        add_to_favorites_action = menu.addAction(t("add_to_favorites"))
        # Add to playlist action
        add_to_playlist_action = menu.addAction(t("add_to_playlist"))

        menu.addSeparator()

        download_action = menu.addAction(t("download"))

        # Connect actions
        if is_single:
            play_action.triggered.connect(lambda: self._play_track(track))
            insert_action.triggered.connect(lambda: self._insert_track_to_queue(track))
            add_action.triggered.connect(lambda: self._add_track_to_queue(track))
            add_to_favorites_action.triggered.connect(lambda: self._add_track_to_favorites(track))
            add_to_playlist_action.triggered.connect(lambda: self._add_track_to_playlist(track))
            download_action.triggered.connect(lambda: self._download_track(track))
        else:
            play_action.triggered.connect(lambda: self._play_tracks(selected_tracks))
            insert_action.triggered.connect(lambda: self._insert_tracks_to_queue(selected_tracks))
            add_action.triggered.connect(lambda: self._add_tracks_to_queue(selected_tracks))
            add_to_favorites_action.triggered.connect(lambda: self._add_tracks_to_favorites(selected_tracks))
            add_to_playlist_action.triggered.connect(lambda: self._add_tracks_to_playlist(selected_tracks))
            download_action.triggered.connect(lambda: self._download_tracks(selected_tracks))

        menu.exec(self._songs_table.viewport().mapToGlobal(pos))

    def _play_track(self, track: OnlineTrack):
        """Play a single track."""
        if self._tracks:
            # Find the track index and play all from that track
            try:
                index = self._tracks.index(track)
                tracks_to_play = self._tracks[index:]
                self.play_all.emit(tracks_to_play)
            except ValueError:
                logger.warning(f"Track not found in list: {track.title}")

    def _add_track_to_queue(self, track: OnlineTrack):
        """Add track to queue."""
        self.add_all_to_queue.emit([track])

    def _add_tracks_to_queue(self, tracks: list):
        """Add multiple tracks to queue."""
        self.add_all_to_queue.emit(tracks)

    def _insert_track_to_queue(self, track: OnlineTrack):
        """Insert track after current playing track."""
        self.insert_all_to_queue.emit([track])

    def _insert_tracks_to_queue(self, tracks: list):
        """Insert multiple tracks after current playing track."""
        self.insert_all_to_queue.emit(tracks)

    def _play_tracks(self, tracks: list):
        """Play multiple tracks."""
        if tracks:
            self.play_all.emit(tracks)

    def _download_track(self, track: OnlineTrack):
        """Download a track."""
        if self._download_service.is_cached(track.mid):
            logger.info(f"Track already cached: {track.title}")
            return

        # Start download
        worker = DownloadWorker(self._download_service, track.mid, track.title)
        worker.download_finished.connect(self._on_download_finished)
        worker.start()
        # Keep reference to prevent garbage collection
        if not hasattr(self, '_download_workers'):
            self._download_workers = []
        self._download_workers.append(worker)

    def _download_tracks(self, tracks: list):
        """Download multiple tracks."""
        for track in tracks:
            self._download_track(track)

    def _on_download_finished(self, song_mid: str, local_path: str):
        """Handle download finished."""
        if local_path:
            logger.info(f"Download completed: {song_mid} -> {local_path}")
        else:
            logger.warning(f"Download failed: {song_mid}")

    def _add_track_to_favorites(self, track: OnlineTrack):
        """Add track to favorites."""
        self._add_tracks_to_favorites([track])

    def _add_tracks_to_favorites(self, tracks: list):
        """Add multiple tracks to favorites."""
        from app.bootstrap import Bootstrap

        added_count = 0
        for track in tracks:
            track_id = self._add_online_track_to_library(track)
            if track_id and self._db:
                self._db.add_favorite(track_id=track_id)
                added_count += 1

        if added_count > 0:
            logger.info(f"[OnlineDetailView] Added {added_count} tracks to favorites")
            QMessageBox.information(
                self,
                t("success"),
                t("added_x_tracks_to_favorites").format(count=added_count)
            )

    def _add_track_to_playlist(self, track: OnlineTrack):
        """Add track to playlist."""
        self._add_tracks_to_playlist([track])

    def _add_tracks_to_playlist(self, tracks: list):
        """Add multiple tracks to playlist."""
        from app.bootstrap import Bootstrap
        from utils.playlist_utils import add_tracks_to_playlist

        bootstrap = Bootstrap.instance()

        # Add tracks to library first and collect track IDs
        track_ids = []
        for track in tracks:
            track_id = self._add_online_track_to_library(track)
            if track_id:
                track_ids.append(track_id)

        if not track_ids:
            return

        add_tracks_to_playlist(
            self,
            bootstrap.library_service,
            track_ids,
            "[OnlineDetailView]"
        )

    def _add_online_track_to_library(self, track: OnlineTrack):
        """Add online track to library, return track_id."""
        from app.bootstrap import Bootstrap
        from domain.track import TrackSource

        bootstrap = Bootstrap.instance()
        if not bootstrap.library_service:
            return None

        cover_url = self._get_cover_url(track)

        return bootstrap.library_service.add_online_track(
            song_mid=track.mid,
            title=track.title,
            artist=track.singer_name,
            album=track.album_name,
            duration=float(track.duration),
            cover_url=cover_url
        )

    def _get_cover_url(self, track: OnlineTrack) -> str:
        """Get cover URL for online track."""
        if track.album and track.album.mid:
            return f"https://y.qq.com/music/photo_new/T002R300x300M000{track.album.mid}.jpg"
        return ""

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update back button
        if hasattr(self, '_back_btn'):
            self._back_btn.setText("← " + t("back"))

        # Update action buttons
        if hasattr(self, '_play_all_btn'):
            self._play_all_btn.setText(t("play_all"))
        if hasattr(self, '_add_queue_btn'):
            self._add_queue_btn.setText(t("add_all_to_queue"))

        # Update pagination buttons
        if hasattr(self, '_prev_page_btn'):
            self._prev_page_btn.setText("← " + t("previous_page"))
        if hasattr(self, '_next_page_btn'):
            self._next_page_btn.setText(t("next_page") + " →")

        # Update albums section title
        if hasattr(self, '_albums_title_label'):
            self._albums_title_label.setText(t("albums"))

        # Update songs section title
        if hasattr(self, '_songs_title_label'):
            self._songs_title_label.setText(t("songs"))

        # Update table headers
        if hasattr(self, '_songs_table'):
            header = self._songs_table.horizontalHeader()
            if header.count() >= 5:
                header.model().setHeaderData(0, Qt.Horizontal, "#")
                header.model().setHeaderData(1, Qt.Horizontal, t("title"))
                header.model().setHeaderData(2, Qt.Horizontal, t("artist"))
                header.model().setHeaderData(3, Qt.Horizontal, t("album"))
                header.model().setHeaderData(4, Qt.Horizontal, t("duration"))


class DownloadWorker(QThread):
    """Background worker for downloading online music."""

    download_finished = Signal(str, str)  # (song_mid, local_path)

    def __init__(self, download_service: OnlineDownloadService, song_mid: str, song_title: str):
        super().__init__()
        self._download_service = download_service
        self._song_mid = song_mid
        self._song_title = song_title

    def run(self):
        """Run download."""
        try:
            result = self._download_service.download(self._song_mid, self._song_title)
            self.download_finished.emit(self._song_mid, result or "")
        except Exception as e:
            logger.error(f"Download worker error: {e}")
            self.download_finished.emit(self._song_mid, "")

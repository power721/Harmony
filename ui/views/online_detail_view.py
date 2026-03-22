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
)
from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QCursor, QColor, QBrush

from domain.online_music import OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist
from services.online import OnlineMusicService, OnlineDownloadService
from system.i18n import t
from system.event_bus import EventBus
from utils import format_duration

logger = logging.getLogger(__name__)


class DetailWorker(QThread):
    """Background worker for loading detail data."""

    detail_loaded = Signal(str, object)  # (type, data)

    def __init__(self, service: OnlineMusicService, detail_type: str, mid: str, page: int = 1):
        super().__init__()
        self._service = service
        self._detail_type = detail_type
        self._mid = mid
        self._page = page

    def run(self):
        try:
            if self._detail_type == "artist":
                data = self._service.get_artist_detail(self._mid, page=self._page)
            elif self._detail_type == "album":
                data = self._service.get_album_detail(self._mid)
            elif self._detail_type == "playlist":
                data = self._service.get_playlist_detail(self._mid)
            else:
                data = None

            self.detail_loaded.emit(self._detail_type, data)
        except Exception as e:
            logger.error(f"Failed to load detail: {e}")


class OnlineDetailView(QWidget):
    """Detail view for artist, album, or playlist."""

    back_requested = Signal()
    play_all = Signal(list)  # List of OnlineTrack
    add_all_to_queue = Signal(list)

    def __init__(
        self,
        config_manager=None,
        qqmusic_service=None,
        parent=None
    ):
        super().__init__(parent)

        self._config = config_manager
        self._service = OnlineMusicService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service
        )
        self._download_service = OnlineDownloadService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service
        )
        self._event_bus = EventBus.instance()

        self._detail_type = ""  # "artist", "album", "playlist"
        self._mid = ""
        self._cover_url = ""  # Store actual cover URL for full-size display
        self._tracks: List[OnlineTrack] = []
        self._detail_worker: Optional[DetailWorker] = None

        # Pagination state
        self._current_page = 1
        self._total_pages = 1
        self._total_songs = 0
        self._page_size = 50

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

        # Actions
        actions = self._create_actions()
        layout.addWidget(actions)

        # Pagination
        self._pagination_widget = self._create_pagination()
        layout.addWidget(self._pagination_widget)

        # Songs table
        self._songs_table = self._create_songs_table()
        layout.addWidget(self._songs_table, 1)  # Give table stretch priority

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
        table.setSelectionMode(QAbstractItemView.SingleSelection)
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

        self._load_detail()

    def _load_detail(self):
        """Load detail data."""
        if self._detail_worker and self._detail_worker.isRunning():
            self._detail_worker.terminate()

        self._detail_worker = DetailWorker(
            self._service,
            self._detail_type,
            self._mid,
            self._current_page
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
        self._total_pages = (total + page_size - 1) // page_size if total > 0 else 1

        self._tracks = self._parse_songs(songs)

        # Display stats showing loaded vs total
        if total > len(self._tracks):
            self._stats_label.setText(f"{len(self._tracks)} / {total} {t('songs')}")
        else:
            self._stats_label.setText(f"{len(self._tracks)} {t('songs')}")

        # Update pagination controls
        self._update_pagination()
        self._display_songs(self._tracks)

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
        import requests

        class CoverLoader(QThread):
            loaded = Signal(QPixmap)

            def __init__(self, url):
                super().__init__()
                self.url = url

            def run(self):
                try:
                    response = requests.get(self.url, timeout=10)
                    response.raise_for_status()
                    pixmap = QPixmap()
                    if pixmap.loadFromData(response.content):
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
        image_label.setText("...")
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
                    import requests
                    response = requests.get(self.url, timeout=10)
                    response.raise_for_status()
                    pixmap = QPixmap()
                    if pixmap.loadFromData(response.content):
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
        index = self._songs_table.indexAt(pos)
        row = index.row()
        if row < 0 or row >= len(self._tracks):
            return

        track = self._tracks[row]

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
        add_action = menu.addAction(t("add_to_queue"))

        # TODO: Connect actions

        menu.exec(self._songs_table.viewport().mapToGlobal(pos))

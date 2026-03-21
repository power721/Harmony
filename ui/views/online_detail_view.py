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

    def __init__(self, service: OnlineMusicService, detail_type: str, mid: str):
        super().__init__()
        self._service = service
        self._detail_type = detail_type
        self._mid = mid

    def run(self):
        try:
            if self._detail_type == "artist":
                data = self._service.get_artist_detail(self._mid)
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
        self._tracks: List[OnlineTrack] = []
        self._detail_worker: Optional[DetailWorker] = None

        self._setup_ui()
        self._apply_styles()

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(15)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Info section
        self._info_section = self._create_info_section()
        layout.addWidget(self._info_section)

        # Actions
        actions = self._create_actions()
        layout.addWidget(actions)

        # Songs table
        self._songs_table = self._create_songs_table()
        layout.addWidget(self._songs_table)

    def _create_header(self) -> QWidget:
        """Create header with back button."""
        widget = QWidget()
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
        self._info_layout.setSpacing(20)

        # Cover/Avatar placeholder
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(150, 150)
        self._cover_label.setStyleSheet("""
            background: #333;
            border-radius: 10px;
        """)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._info_layout.addWidget(self._cover_label)

        # Info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(10)

        # Type label
        self._type_label = QLabel()
        self._type_label.setStyleSheet("color: #808080; font-size: 12px;")
        info_layout.addWidget(self._type_label)

        # Name
        self._name_label = QLabel()
        self._name_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        info_layout.addWidget(self._name_label)

        # Secondary info
        self._secondary_label = QLabel()
        self._secondary_label.setStyleSheet("color: #808080; font-size: 14px;")
        info_layout.addWidget(self._secondary_label)

        # Stats
        self._stats_label = QLabel()
        self._stats_label.setStyleSheet("color: #1db954; font-size: 14px;")
        info_layout.addWidget(self._stats_label)

        info_layout.addStretch()
        self._info_layout.addWidget(info_widget, 1)

        return widget

    def _create_actions(self) -> QWidget:
        """Create action buttons."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Play all
        self._play_all_btn = QPushButton(t("play_all"))
        self._play_all_btn.setObjectName("primaryBtn")
        self._play_all_btn.setCursor(Qt.PointingHandCursor)
        self._play_all_btn.clicked.connect(self._on_play_all)
        layout.addWidget(self._play_all_btn)

        # Add to queue
        self._add_queue_btn = QPushButton(t("add_all_to_queue"))
        self._add_queue_btn.setCursor(Qt.PointingHandCursor)
        self._add_queue_btn.clicked.connect(self._on_add_all_to_queue)
        layout.addWidget(self._add_queue_btn)

        layout.addStretch()

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
                padding: 8px 20px;
                border-radius: 20px;
                font-size: 14px;
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

        # Set placeholder info
        self._type_label.setText(t("artist"))
        self._name_label.setText(name)
        self._secondary_label.setText("")
        self._stats_label.setText("")

        self._load_detail()

    def load_album(self, mid: str, name: str = "", singer_name: str = ""):
        """Load album detail."""
        self._detail_type = "album"
        self._mid = mid

        # Set placeholder info
        self._type_label.setText(t("album"))
        self._name_label.setText(name)
        self._secondary_label.setText(singer_name)
        self._stats_label.setText("")

        self._load_detail()

    def load_playlist(self, playlist_id: str, title: str = "", creator: str = ""):
        """Load playlist detail."""
        self._detail_type = "playlist"
        self._mid = playlist_id

        # Set placeholder info
        self._type_label.setText(t("playlist"))
        self._name_label.setText(title)
        self._secondary_label.setText(creator)
        self._stats_label.setText("")

        self._load_detail()

    def _load_detail(self):
        """Load detail data."""
        if self._detail_worker and self._detail_worker.isRunning():
            self._detail_worker.terminate()

        self._detail_worker = DetailWorker(
            self._service,
            self._detail_type,
            self._mid
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

        songs = data.get("songs", [])
        self._tracks = self._parse_songs(songs)
        self._stats_label.setText(f"{len(self._tracks)} {t('songs')}")
        self._display_songs(self._tracks)

    def _display_album_detail(self, data: Dict):
        """Display album detail."""
        self._name_label.setText(data.get("name", ""))
        self._secondary_label.setText(data.get("singer", ""))

        songs = data.get("songs", [])
        self._tracks = self._parse_songs(songs)
        self._stats_label.setText(f"{len(self._tracks)} {t('songs')}")
        self._display_songs(self._tracks)

    def _display_playlist_detail(self, data: Dict):
        """Display playlist detail."""
        self._name_label.setText(data.get("name", ""))
        self._secondary_label.setText(data.get("creator", ""))

        songs = data.get("songs", [])
        self._tracks = self._parse_songs(songs)
        self._stats_label.setText(f"{len(self._tracks)} {t('songs')}")
        self._display_songs(self._tracks)

    def _parse_songs(self, songs: List[Dict]) -> List[OnlineTrack]:
        """Parse songs from API response."""
        from domain.online_music import OnlineSinger, AlbumInfo

        tracks = []
        for song in songs:
            # Parse singers
            singers = []
            singer_data = song.get("singer", [])
            if isinstance(singer_data, list):
                for s in singer_data:
                    singers.append(OnlineSinger(
                        mid=s.get("mid", ""),
                        name=s.get("name", "")
                    ))

            # Parse album
            album = AlbumInfo(
                mid=song.get("albummid", ""),
                name=song.get("albumname", "")
            )

            track = OnlineTrack(
                mid=song.get("mid", song.get("songmid", "")),
                id=song.get("id", song.get("songid")),
                title=song.get("name", song.get("songname", "")),
                singer=singers,
                album=album,
                duration=song.get("interval", 0)
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

"""
Album detail view widget for showing album information and tracks.
"""

import logging
from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QProgressBar,
    QAbstractItemView,
    QMenu,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QAction, QCursor, QMouseEvent, QScreen

from domain.album import Album
from domain.track import Track
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService
from utils import format_duration
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class AlbumView(QWidget):
    """
    Album detail page showing album info and tracks.

    Features:
        - Album header with cover and info
        - Track list table
        - Play all / Shuffle buttons
    """

    back_clicked = Signal()
    play_tracks = Signal(list)  # Emits list of Track objects
    track_double_clicked = Signal(int)  # Emits track_id
    add_to_queue = Signal(list)  # Emits list of Track objects
    add_to_playlist = Signal(list)  # Emits list of Track objects

    def __init__(
        self,
        library_service: LibraryService,
        playback_service: PlaybackService = None,
        cover_service: CoverService = None,
        parent=None
    ):
        super().__init__(parent)
        self._library = library_service
        self._playback = playback_service
        self._cover_service = cover_service
        self._album: Album = None
        self._tracks: List[Track] = []
        self._current_cover_path: str = None  # Store current cover path

        self._setup_ui()

    def _setup_ui(self):
        """Set up the album view UI."""
        self.setStyleSheet("background-color: #121212;")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #121212;
                border: none;
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

        # Content container
        self._content = QWidget()
        self._content.setStyleSheet("background-color: #121212;")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 20)
        content_layout.setSpacing(0)

        # Album header
        self._header = self._create_header()
        content_layout.addWidget(self._header)

        # Tracks section
        self._tracks_section = self._create_tracks_section()
        content_layout.addWidget(self._tracks_section)

        scroll_area.setWidget(self._content)
        layout.addWidget(scroll_area)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()

    def _create_header(self) -> QWidget:
        """Create album header with cover and info."""
        header = QFrame()
        header.setMinimumHeight(280)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1e3a5f, stop:1 #121212
                );
            }
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(40, 40, 40, 20)
        layout.setSpacing(30)

        # Album cover (clickable to show large image)
        self._cover_label = ClickableLabel()
        self._cover_label.setFixedSize(200, 200)
        self._cover_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                border-radius: 8px;
            }
        """)
        self._cover_label.clicked.connect(self._on_cover_clicked)
        layout.addWidget(self._cover_label, 0, Qt.AlignVCenter)

        # Album info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)

        # Album type label
        self._type_label = QLabel(t("album_type"))
        self._type_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 12px;
                font-weight: bold;
            }
        """)
        info_layout.addWidget(self._type_label)

        # Album name
        self._name_label = QLabel("Album Name")
        self._name_label.setStyleSheet("""
            QLabel {
                color: #ffffff;
                font-size: 48px;
                font-weight: bold;
            }
        """)
        info_layout.addWidget(self._name_label)

        # Artist name
        self._artist_label = QLabel("Artist")
        self._artist_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 18px;
            }
        """)
        info_layout.addWidget(self._artist_label)

        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet("""
            QLabel {
                color: #b3b3b3;
                font-size: 14px;
            }
        """)
        info_layout.addWidget(self._stats_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._play_btn = QPushButton(t("play_all"))
        self._play_btn.setFixedSize(120, 36)
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setStyleSheet("""
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        self._play_btn.clicked.connect(self._on_play_all)
        btn_layout.addWidget(self._play_btn)

        self._shuffle_btn = QPushButton(t("shuffle"))
        self._shuffle_btn.setFixedSize(100, 36)
        self._shuffle_btn.setCursor(Qt.PointingHandCursor)
        self._shuffle_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #b3b3b3;
                border: 1px solid #535353;
                border-radius: 18px;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #ffffff;
                border-color: #ffffff;
            }
        """)
        self._shuffle_btn.clicked.connect(self._on_shuffle)
        btn_layout.addWidget(self._shuffle_btn)
        btn_layout.addStretch()

        info_layout.addLayout(btn_layout)
        info_layout.addStretch()

        layout.addWidget(info_widget, 1)

        return header

    def _create_tracks_section(self) -> QWidget:
        """Create tracks table section."""
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 0)
        layout.setSpacing(16)

        # Section title
        self._tracks_title_label = QLabel(t("all_tracks"))
        self._tracks_title_label.setStyleSheet("""
            QLabel {
                color: #1db954;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        layout.addWidget(self._tracks_title_label)

        # Tracks table
        self._tracks_table = QTableWidget()
        self._tracks_table.setObjectName("tracksTable")
        self._tracks_table.setColumnCount(3)
        self._tracks_table.setHorizontalHeaderLabels(
            ["#", t("title"), t("duration")]
        )

        # Configure table
        self._tracks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tracks_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tracks_table.setAlternatingRowColors(True)
        self._tracks_table.verticalHeader().setVisible(False)
        self._tracks_table.horizontalHeader().setStretchLastSection(False)
        self._tracks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tracks_table.setFocusPolicy(Qt.NoFocus)
        self._tracks_table.setShowGrid(False)

        # Set column widths
        header = self._tracks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(0, 50)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # Styling
        self._tracks_table.setStyleSheet("""
            QTableWidget#tracksTable {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget#tracksTable::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            QTableWidget#tracksTable::item:alternate {
                background-color: #252525;
            }
            QTableWidget#tracksTable::item:!alternate {
                background-color: #1e1e1e;
            }
            QTableWidget#tracksTable::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget#tracksTable::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget#tracksTable::item:selected:alternate {
                background-color: #1ed760;
            }
            QTableWidget#tracksTable::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget#tracksTable::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#tracksTable QHeaderView::section {
                background-color: #2a2a2a;
                color: #1db954;
                padding: 14px 12px;
                border: none;
                border-bottom: 2px solid #1db954;
                font-weight: bold;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QTableWidget#tracksTable QTableCornerButton::section {
                background-color: #2a2a2a;
                border: none;
                border-bottom: 2px solid #1db954;
            }
            QTableWidget#tracksTable QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
            }
            QTableWidget#tracksTable QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget#tracksTable QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
        """)

        self._tracks_table.doubleClicked.connect(self._on_track_double_clicked)
        self._tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tracks_table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self._tracks_table)

        return section

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

        self._loading_label = QLabel(t("loading_album"))
        self._loading_label.setStyleSheet("color: #b3b3b3; font-size: 14px;")
        layout.addWidget(self._loading_label)

        return widget

    def set_album(self, album: Album):
        """Set the album to display."""
        self._album = album
        self._loading.show()
        self._content.hide()

        QTimer.singleShot(10, lambda: self._do_load_album(album))

    def get_album(self) -> Album:
        """Get the currently displayed album."""
        return self._album

    def _do_load_album(self, album: Album):
        """Actually load album data."""
        try:
            # Load tracks
            self._tracks = self._library.get_album_tracks(album.name, album.artist)

            # Update header
            self._name_label.setText(album.display_name)
            self._artist_label.setText(album.display_artist)
            self._stats_label.setText(
                t("album_stats").format(
                    songs=album.song_count,
                    duration=format_duration(album.duration)
                )
            )
            self._load_cover(album)

            # Render tracks
            self._render_tracks()

        except Exception as e:
            logger.error(f"Error loading album: {e}")
        finally:
            self._loading.hide()
            self._content.show()

    def _load_cover(self, album: Album):
        """Load album cover."""
        cover_path = album.cover_path

        if cover_path and Path(cover_path).exists():
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(
                        200, 200,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    self._cover_label.setPixmap(scaled)
                    self._current_cover_path = cover_path  # Store cover path
                    return
            except Exception as e:
                logger.debug(f"Error loading cover: {e}")

        # Default cover
        self._set_default_cover()
        self._current_cover_path = None

    def _set_default_cover(self):
        """Set default cover."""
        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor("#3d3d3d"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw music note icon
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(60)
        painter.setFont(font)
        painter.drawText(0, 0, 200, 200, Qt.AlignCenter, "\u266B")
        painter.end()

        self._cover_label.setPixmap(pixmap)
        self._current_cover_path = None

    def _on_cover_clicked(self):
        """Handle cover art click - show large image dialog."""
        if self._current_cover_path:
            try:
                album_name = self._album.display_name if self._album else ""
                dialog = AlbumCoverDialog(self._current_cover_path, album_name, self)
                dialog.exec_()
            except Exception as e:
                logger.error(f"Error showing cover dialog: {e}")

    def _render_tracks(self):
        """Render tracks table."""
        self._tracks_table.setRowCount(len(self._tracks))

        for i, track in enumerate(self._tracks):
            # Number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            self._tracks_table.setItem(i, 0, num_item)

            # Title
            title_item = QTableWidgetItem(track.title or track.display_name)
            self._tracks_table.setItem(i, 1, title_item)

            # Duration
            duration_item = QTableWidgetItem(format_duration(track.duration))
            duration_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tracks_table.setItem(i, 2, duration_item)

            # Store track ID in item data
            title_item.setData(Qt.UserRole, track.id)

    def _on_play_all(self):
        """Handle play all button click."""
        if self._tracks:
            self.play_tracks.emit(self._tracks)

    def _on_shuffle(self):
        """Handle shuffle button click."""
        if self._tracks:
            import random
            shuffled = self._tracks.copy()
            random.shuffle(shuffled)
            self.play_tracks.emit(shuffled)

    def _on_track_double_clicked(self, index):
        """Handle track double click - play from this track."""
        item = self._tracks_table.item(index.row(), 1)
        if item and self._tracks:
            track_id = item.data(Qt.UserRole)
            # Find the index of the clicked track
            start_index = 0
            for i, track in enumerate(self._tracks):
                if track.id == track_id:
                    start_index = i
                    break
            # Play tracks starting from the clicked one
            tracks_to_play = self._tracks[start_index:]
            self.play_tracks.emit(tracks_to_play)

    def _show_context_menu(self, pos):
        """Show context menu for tracks."""
        item = self._tracks_table.itemAt(pos)
        if not item:
            return

        # Get selected track IDs
        selected_rows = set()
        for selected_item in self._tracks_table.selectedItems():
            selected_rows.add(selected_item.row())

        selected_tracks = []
        for row in selected_rows:
            title_item = self._tracks_table.item(row, 1)
            if title_item:
                track_id = title_item.data(Qt.UserRole)
                for track in self._tracks:
                    if track.id == track_id:
                        selected_tracks.append(track)
                        break

        if not selected_tracks:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #282828;
                color: #ffffff;
                border: 1px solid #404040;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #1db954;
            }
        """)

        # Play action
        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self.play_tracks.emit(selected_tracks))

        # Add to queue action
        add_queue_action = menu.addAction(t("add_to_queue"))
        add_queue_action.triggered.connect(lambda: self.add_to_queue.emit(selected_tracks))

        menu.addSeparator()

        # Add to playlist action
        add_playlist_action = menu.addAction(t("add_to_playlist"))
        add_playlist_action.triggered.connect(lambda: self.add_to_playlist.emit(selected_tracks))

        menu.exec_(self._tracks_table.mapToGlobal(pos))

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update header type label
        self._type_label.setText(t("album_type"))

        # Update buttons
        self._play_btn.setText(t("play_all"))
        self._shuffle_btn.setText(t("shuffle"))

        # Update tracks section title
        self._tracks_title_label.setText(t("all_tracks"))

        # Update table headers
        self._tracks_table.setHorizontalHeaderLabels(
            ["#", t("title"), t("duration")]
        )

        # Update loading indicator label
        self._loading_label.setText(t("loading_album"))

        # Reload album data to update stats text
        if self._album:
            self._stats_label.setText(
                t("album_stats").format(
                    songs=self._album.song_count,
                    duration=format_duration(self._album.duration)
                )
            )


class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press event."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AlbumCoverDialog(QDialog):
    """Dialog to display large album cover."""

    def __init__(self, cover_path: str, album_name: str = "", parent=None):
        """
        Initialize cover dialog.

        Args:
            cover_path: Path to the cover image
            album_name: Album name for window title
            parent: Parent widget
        """
        super().__init__(parent)
        self._cover_path = cover_path
        self._album_name = album_name
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(self._album_name or t("album_art"))
        self.setModal(True)

        # Get screen size
        screen = QScreen.availableGeometry(self.screen())
        screen_width = screen.width()
        screen_height = screen.height()

        # Set dialog size to 80% of screen, max 800x800
        dialog_width = min(int(screen_width * 0.8), 800)
        dialog_height = min(int(screen_height * 0.8), 800)
        self.setFixedSize(dialog_width, dialog_height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Image label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("background-color: #1e1e1e;")

        # Load and scale image to fit dialog
        pixmap = QPixmap(self._cover_path)
        if not pixmap.isNull():
            # Scale image to fit within dialog while maintaining aspect ratio
            scaled = pixmap.scaled(
                dialog_width - 20,
                dialog_height - 20,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            image_label.setPixmap(scaled)
        else:
            image_label.setText(t("cover_load_failed"))

        layout.addWidget(image_label)

        # Apply dialog style
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
        """)

    def keyPressEvent(self, event):
        """Handle key press - close on Escape."""
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

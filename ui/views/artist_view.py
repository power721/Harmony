"""
Artist detail view widget for showing artist information and tracks.
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
    QGridLayout,
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
from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QAction, QCursor, QMouseEvent, QScreen

from domain.artist import Artist
from domain.album import Album
from domain.track import Track
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService
from ui.widgets import AlbumCard
from utils import format_duration
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class ArtistView(QWidget):
    """
    Artist detail page showing artist info, albums, and tracks.

    Features:
        - Artist header with cover and info
        - Albums grid
        - Popular tracks list
        - Play all button
    """

    back_clicked = Signal()
    album_clicked = Signal(object)  # Emits Album object
    play_tracks = Signal(list)  # Emits list of Track objects
    track_double_clicked = Signal(int)  # Emits track_id
    insert_to_queue = Signal(list)  # Emits list of Track objects
    add_to_queue = Signal(list)  # Emits list of Track objects
    add_to_playlist = Signal(list)  # Emits list of Track objects
    download_cover_requested = Signal(object)  # Emits Album object

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
        self._artist: Artist = None
        self._albums: List[Album] = []
        self._tracks: List[Track] = []
        self._album_cards: List[AlbumCard] = []
        self._current_cover_path: str = None  # Store current cover path

        self._setup_ui()
        self._connect_signals()

        # Register with theme manager
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Set up the artist view UI."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        self.setStyleSheet(f"background-color: {theme.background};")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: {theme.background};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {theme.background};
                width: 12px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.background_alt};
                border-radius: 6px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.background_hover};
            }}
        """)

        # Content container
        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {theme.background};")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 20)
        content_layout.setSpacing(0)

        # Artist header
        self._header = self._create_header()
        content_layout.addWidget(self._header)

        # Albums section
        self._albums_section = self._create_albums_section()
        content_layout.addWidget(self._albums_section)

        # Tracks section
        self._tracks_section = self._create_tracks_section()
        content_layout.addWidget(self._tracks_section)

        scroll_area.setWidget(self._content)
        layout.addWidget(scroll_area)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()

    def _connect_signals(self):
        """Connect signals."""
        EventBus.instance().cover_updated.connect(self._on_cover_updated)

    def refresh_theme(self):
        """Refresh theme colors when theme changes."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        # Update main background
        self.setStyleSheet(f"background-color: {theme.background};")

        # Update scroll area
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            scroll_area.setStyleSheet(f"""
                QScrollArea {{
                    background-color: {theme.background};
                    border: none;
                }}
                QScrollBar:vertical {{
                    background-color: {theme.background};
                    width: 12px;
                }}
                QScrollBar::handle:vertical {{
                    background-color: {theme.background_alt};
                    border-radius: 6px;
                    min-height: 30px;
                }}
                QScrollBar::handle:vertical:hover {{
                    background-color: {theme.background_hover};
                }}
            """)

        # Update content widget
        if hasattr(self, '_content'):
            self._content.setStyleSheet(f"background-color: {theme.background};")

        # Update header gradient
        if hasattr(self, '_header'):
            self._header.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(
                        x1:0, y1:0, x2:0, y2:1,
                        stop:0 {theme.highlight}, stop:1 {theme.background}
                    );
                }}
            """)

        # Update cover label
        if hasattr(self, '_cover_label'):
            self._cover_label.setStyleSheet(f"""
                QLabel {{
                    background-color: {theme.background_hover};
                    border-radius: 100px;
                }}
            """)

        # Update type label
        if hasattr(self, '_type_label'):
            self._type_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 12px;
                    font-weight: bold;
                }}
            """)

        # Update name label
        if hasattr(self, '_name_label'):
            self._name_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text};
                    font-size: 48px;
                    font-weight: bold;
                }}
            """)

        # Update stats label
        if hasattr(self, '_stats_label'):
            self._stats_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 14px;
                }}
            """)

        # Update play button
        if hasattr(self, '_play_btn'):
            self._play_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {theme.highlight};
                    color: {theme.background};
                    border: none;
                    border-radius: 18px;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 10px 30px;
                }}
                QPushButton:hover {{
                    background-color: {theme.highlight_hover};
                }}
            """)

        # Update shuffle button
        if hasattr(self, '_shuffle_btn'):
            self._shuffle_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {theme.text_secondary};
                    border: 1px solid {theme.border};
                    border-radius: 18px;
                    font-size: 14px;
                    padding: 10px 20px;
                }}
                QPushButton:hover {{
                    color: {theme.text};
                    border-color: {theme.text};
                }}
            """)

        # Update back button
        if hasattr(self, '_back_btn'):
            self._back_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {theme.text_secondary};
                    border: 1px solid {theme.border};
                    border-radius: 18px;
                    font-size: 14px;
                    padding: 10px 20px;
                }}
                QPushButton:hover {{
                    color: {theme.text};
                    border-color: {theme.text};
                }}
            """)

        # Update albums title
        if hasattr(self, '_albums_title_label'):
            self._albums_title_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.highlight};
                    font-size: 24px;
                    font-weight: bold;
                    padding: 10px;
                }}
            """)

        # Update tracks title
        if hasattr(self, '_tracks_title_label'):
            self._tracks_title_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.highlight};
                    font-size: 24px;
                    font-weight: bold;
                    padding: 10px;
                }}
            """)

        # Update tracks table
        if hasattr(self, '_tracks_table'):
            self._tracks_table.setStyleSheet(f"""
                QTableWidget {{
                    background-color: {theme.background};
                    border: none;
                    border-radius: 8px;
                    gridline-color: {theme.background_hover};
                }}
                QTableWidget::item {{
                    padding: 12px 8px;
                    color: {theme.text};
                    border: none;
                    border-bottom: 1px solid {theme.background_hover};
                }}
                QTableWidget::item:alternate {{
                    background-color: {theme.background_alt};
                }}
                QTableWidget::item:!alternate {{
                    background-color: {theme.background};
                }}
                QTableWidget::item:selected {{
                    background-color: {theme.highlight};
                    color: {theme.background};
                    font-weight: 500;
                }}
                QTableWidget::item:selected:!alternate {{
                    background-color: {theme.highlight};
                }}
                QTableWidget::item:selected:alternate {{
                    background-color: {theme.highlight_hover};
                }}
                QTableWidget::item:hover {{
                    background-color: {theme.background_hover};
                }}
                QTableWidget::item:selected:hover {{
                    background-color: {theme.highlight_hover};
                }}
                QTableWidget QHeaderView::section {{
                    background-color: {theme.background_hover};
                    color: {theme.highlight};
                    padding: 14px 12px;
                    border: none;
                    border-bottom: 2px solid {theme.highlight};
                    font-weight: bold;
                    font-size: 13px;
                    letter-spacing: 0.5px;
                }}
                QTableWidget QTableCornerButton::section {{
                    background-color: {theme.background_hover};
                    border: none;
                    border-bottom: 2px solid {theme.highlight};
                }}
                QTableWidget QScrollBar:vertical {{
                    background-color: {theme.background};
                    width: 12px;
                    border-radius: 6px;
                }}
                QTableWidget QScrollBar::handle:vertical {{
                    background-color: {theme.border};
                    border-radius: 6px;
                    min-height: 40px;
                }}
                QTableWidget QScrollBar::handle:vertical:hover {{
                    background-color: {theme.background_hover};
                }}
            """)

        # Update loading label
        if hasattr(self, '_loading_label'):
            self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")

    def _create_header(self) -> QWidget:
        """Create artist header with cover and info."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        header = QFrame()
        header.setMinimumHeight(280)
        header.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(
                    x1:0, y1:0, x2:0, y2:1,
                    stop:0 {theme.highlight}, stop:1 {theme.background}
                );
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(40, 40, 40, 20)
        layout.setSpacing(30)

        # Artist cover (clickable to show large image)
        self._cover_label = ClickableLabel()
        self._cover_label.setFixedSize(200, 200)
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.background_hover};
                border-radius: 100px;
            }}
        """)
        self._cover_label.clicked.connect(self._on_cover_clicked)
        layout.addWidget(self._cover_label, 0, Qt.AlignVCenter)
        layout.addWidget(self._cover_label, 0, Qt.AlignVCenter)

        # Artist info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)

        # Artist type label
        self._type_label = QLabel(t("artist_type"))
        self._type_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_secondary};
                font-size: 12px;
                font-weight: bold;
            }}
        """)
        info_layout.addWidget(self._type_label)

        # Artist name
        self._name_label = QLabel("Artist Name")
        self._name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._name_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text};
                font-size: 48px;
                font-weight: bold;
            }}
        """)
        info_layout.addWidget(self._name_label)

        # Stats
        self._stats_label = QLabel("")
        self._stats_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_secondary};
                font-size: 14px;
            }}
        """)
        info_layout.addWidget(self._stats_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self._play_btn = QPushButton(t("play_all"))
        self._play_btn.setFixedSize(130, 36)
        self._play_btn.setCursor(Qt.PointingHandCursor)
        self._play_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {theme.highlight};
                color: {theme.background};
                border: none;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {theme.highlight_hover};
            }}
        """)
        self._play_btn.clicked.connect(self._on_play_all)
        btn_layout.addWidget(self._play_btn)

        self._shuffle_btn = QPushButton(t("shuffle"))
        self._shuffle_btn.setFixedSize(100, 36)
        self._shuffle_btn.setCursor(Qt.PointingHandCursor)
        self._shuffle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.text_secondary};
                border: 1px solid {theme.border};
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {theme.text};
                border-color: {theme.text};
            }}
        """)
        self._shuffle_btn.clicked.connect(self._on_shuffle)
        btn_layout.addWidget(self._shuffle_btn)

        self._back_btn = QPushButton(t("back"))
        self._back_btn.setFixedSize(80, 36)
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {theme.text_secondary};
                border: 1px solid {theme.border};
                border-radius: 18px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                color: {theme.text};
                border-color: {theme.text};
            }}
        """)
        self._back_btn.clicked.connect(self.back_clicked.emit)
        btn_layout.addWidget(self._back_btn)

        btn_layout.addStretch()

        info_layout.addLayout(btn_layout)

        layout.addWidget(info_widget, 1)

        return header

    def _create_albums_section(self) -> QWidget:
        """Create albums grid section."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        section = QWidget()
        section.setMinimumHeight(560)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 0)
        layout.setSpacing(16)

        # Section title - same style as library view
        self._albums_title_label = QLabel(t("albums"))
        self._albums_title_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.highlight};
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }}
        """)
        layout.addWidget(self._albums_title_label)

        # Scroll area for albums
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMaximumHeight(600)  # ~2 rows of album cards
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {theme.background};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {theme.background_alt};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {theme.background_hover};
            }}
        """)

        # Albums grid container
        self._albums_container = QWidget()
        self._albums_layout = QGridLayout(self._albums_container)
        self._albums_layout.setContentsMargins(0, 0, 0, 0)
        self._albums_layout.setSpacing(20)
        self._albums_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll_area.setWidget(self._albums_container)
        layout.addWidget(scroll_area)

        return section

    def _create_tracks_section(self) -> QWidget:
        """Create tracks table section with same style as library view."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 0)
        layout.setSpacing(16)

        # Section title
        self._tracks_title_label = QLabel(t("all_tracks"))
        self._tracks_title_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.highlight};
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }}
        """)
        layout.addWidget(self._tracks_title_label)

        # Tracks table - same style as LibraryView
        self._tracks_table = QTableWidget()
        self._tracks_table.setObjectName("tracksTable")
        self._tracks_table.setColumnCount(6)
        self._tracks_table.setHorizontalHeaderLabels(
            [t("source"), "#", t("title"), t("artist"), t("album"), t("duration")]
        )

        # Configure table - same as LibraryView
        self._tracks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tracks_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tracks_table.setAlternatingRowColors(True)
        self._tracks_table.verticalHeader().setVisible(False)
        self._tracks_table.horizontalHeader().setStretchLastSection(False)
        self._tracks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._tracks_table.setFocusPolicy(Qt.NoFocus)
        self._tracks_table.setShowGrid(False)

        # Set column widths - same as LibraryView
        header = self._tracks_table.horizontalHeader()
        # Source: fixed small width
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(0, 80)
        #: fixed small width
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(1, 50)
        # Title: stretch to fill all remaining space
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        # Artist: fixed width
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(3, 120)
        # Album: fixed width
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(4, 150)
        # Duration: fit content
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)

        # Styling - same as LibraryView
        self._tracks_table.setStyleSheet(f"""
            QTableWidget#tracksTable {{
                background-color: {theme.background};
                border: none;
                border-radius: 8px;
                gridline-color: {theme.background_hover};
            }}
            QTableWidget#tracksTable::item {{
                padding: 12px 8px;
                color: {theme.text};
                border: none;
                border-bottom: 1px solid {theme.background_hover};
            }}
            /* Alternating row colors for better readability */
            QTableWidget#tracksTable::item:alternate {{
                background-color: {theme.background_alt};
            }}
            QTableWidget#tracksTable::item:!alternate {{
                background-color: {theme.background};
            }}
            /* Selected state with vibrant accent */
            QTableWidget#tracksTable::item:selected {{
                background-color: {theme.highlight};
                color: {theme.background};
                font-weight: 500;
            }}
            QTableWidget#tracksTable::item:selected:!alternate {{
                background-color: {theme.highlight};
            }}
            QTableWidget#tracksTable::item:selected:alternate {{
                background-color: {theme.highlight_hover};
            }}
            /* Hover effect for interactivity */
            QTableWidget#tracksTable::item:hover {{
                background-color: {theme.background_hover};
            }}
            QTableWidget#tracksTable::item:selected:hover {{
                background-color: {theme.highlight_hover};
            }}
            /* Remove focus outline */
            QTableWidget#tracksTable::item:focus {{
                outline: none;
                border: none;
            }}
            QTableWidget#tracksTable:focus {{
                outline: none;
                border: none;
            }}
            /* Header styling */
            QTableWidget#tracksTable QHeaderView::section {{
                background-color: {theme.background_hover};
                color: {theme.highlight};
                padding: 14px 12px;
                border: none;
                border-bottom: 2px solid {theme.highlight};
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                letter-spacing: 0.5px;
            }}
            /* First header (top-left corner) */
            QTableWidget#tracksTable QTableCornerButton::section {{
                background-color: {theme.background_hover};
                border: none;
                border-right: 1px solid {theme.border};
                border-bottom: 2px solid {theme.highlight};
            }}
            /* Scrollbar styling */
            QTableWidget#tracksTable QScrollBar:vertical {{
                background-color: {theme.background};
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }}
            QTableWidget#tracksTable QScrollBar::handle:vertical {{
                background-color: {theme.border};
                border-radius: 6px;
                min-height: 40px;
            }}
            QTableWidget#tracksTable QScrollBar::handle:vertical:hover {{
                background-color: {theme.background_hover};
            }}
        """)

        self._tracks_table.doubleClicked.connect(self._on_track_double_clicked)
        self._tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tracks_table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self._tracks_table)

        return section

    def _create_loading_indicator(self) -> QWidget:
        """Create loading indicator."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)

        progress = QProgressBar()
        progress.setRange(0, 0)  # Indeterminate
        progress.setFixedSize(200, 4)
        progress.setStyleSheet(f"""
            QProgressBar {{
                background-color: {theme.background_hover};
                border: none;
                border-radius: 2px;
            }}
            QProgressBar::chunk {{
                background-color: {theme.highlight};
                border-radius: 2px;
            }}
        """)
        layout.addWidget(progress)

        self._loading_label = QLabel(t("loading_artist"))
        self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")
        layout.addWidget(self._loading_label)

        return widget

    def set_artist(self, artist: Artist):
        """Set the artist to display."""
        self._artist = artist
        self._loading.show()
        self._content.hide()

        QTimer.singleShot(10, lambda: self._do_load_artist(artist))

    def get_artist(self) -> Artist:
        """Get the currently displayed artist."""
        return self._artist

    def _do_load_artist(self, artist: Artist):
        """Actually load artist data."""
        try:
            # Load albums and tracks
            self._albums = self._library.get_artist_albums(artist.name)
            self._tracks = self._library.get_artist_tracks(artist.name)

            # Update header
            self._name_label.setText(artist.display_name)
            self._stats_label.setText(
                t("songs_albums").format(
                    songs=artist.song_count,
                    albums=artist.album_count
                )
            )
            self._load_cover(artist)

            # Render albums
            self._render_albums()

            # Render tracks
            self._render_tracks()

        except Exception as e:
            logger.error(f"Error loading artist: {e}")
        finally:
            self._loading.hide()
            self._content.show()

    def _load_cover(self, artist: Artist):
        """Load artist cover."""
        cover_path = artist.cover_path

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
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw circular background
        painter.setBrush(QColor("#3d3d3d"))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 200, 200)

        # Draw person icon
        painter.setPen(QColor("#666666"))
        font = QFont()
        font.setPixelSize(80)
        painter.setFont(font)
        painter.drawText(0, 0, 200, 200, Qt.AlignCenter, "\u265A")
        painter.end()

        self._cover_label.setPixmap(pixmap)
        self._current_cover_path = None

    def _on_cover_clicked(self):
        """Handle cover art click - show large image dialog."""
        if self._current_cover_path:
            try:
                artist_name = self._artist.display_name if self._artist else ""
                dialog = ArtistCoverDialog(self._current_cover_path, artist_name, self)
                dialog.exec_()
            except Exception as e:
                logger.error(f"Error showing cover dialog: {e}")

    def _render_albums(self):
        """Render album cards."""
        # Clear existing
        for card in self._album_cards:
            self._albums_layout.removeWidget(card)
            card.deleteLater()
        self._album_cards.clear()

        # Add album cards (show all albums)
        for i, album in enumerate(self._albums):
            card = AlbumCard(album)
            card.clicked.connect(self._on_album_clicked)
            card.download_cover_requested.connect(self._on_download_cover_requested)

            row = i // 5
            col = i % 5
            self._albums_layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)
            self._album_cards.append(card)

    def _render_tracks(self):
        """Render tracks table."""
        # Show all tracks (no limit)
        self._tracks_table.setRowCount(len(self._tracks))

        for i, track in enumerate(self._tracks):
            # Source
            from domain.track import TrackSource
            source_map = {
                TrackSource.LOCAL: t("source_local"),
                TrackSource.QUARK: t("source_quark"),
                TrackSource.BAIDU: t("source_baidu"),
                TrackSource.QQ: t("source_qq"),
            }
            source_text = source_map.get(track.source, t("source_local"))
            source_item = QTableWidgetItem(source_text)
            self._tracks_table.setItem(i, 0, source_item)

            # Number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            self._tracks_table.setItem(i, 1, num_item)

            # Title
            title_item = QTableWidgetItem(track.title or track.display_name)
            self._tracks_table.setItem(i, 2, title_item)

            # Artist
            artist_item = QTableWidgetItem(track.artist or "")
            self._tracks_table.setItem(i, 3, artist_item)

            # Album
            album_item = QTableWidgetItem(track.album or "")
            self._tracks_table.setItem(i, 4, album_item)

            # Duration
            duration_item = QTableWidgetItem(format_duration(track.duration))
            duration_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tracks_table.setItem(i, 5, duration_item)

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

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {theme.background_alt};
                color: {theme.text};
                border: 1px solid {theme.border};
            }}
            QMenu::item {{
                padding: 8px 20px;
            }}
            QMenu::item:selected {{
                background-color: {theme.highlight};
                color: {theme.background};
            }}
        """)

        # Play action
        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self.play_tracks.emit(selected_tracks))

        # Insert to queue action
        insert_queue_action = menu.addAction(t("insert_to_queue"))
        insert_queue_action.triggered.connect(lambda: self.insert_to_queue.emit(selected_tracks))

        # Add to queue action
        add_queue_action = menu.addAction(t("add_to_queue"))
        add_queue_action.triggered.connect(lambda: self.add_to_queue.emit(selected_tracks))

        menu.addSeparator()

        # Add to playlist action
        add_playlist_action = menu.addAction(t("add_to_playlist"))
        add_playlist_action.triggered.connect(lambda: self.add_to_playlist.emit(selected_tracks))

        menu.exec_(self._tracks_table.mapToGlobal(pos))

    def _on_album_clicked(self, album: Album):
        """Handle album card click - navigate to album detail."""
        self.album_clicked.emit(album)

    def _on_download_cover_requested(self, album: Album):
        """Handle download cover request from album card."""
        self.download_cover_requested.emit(album)

    def _on_cover_updated(self, item_id, is_cloud: bool = False):
        """Handle cover update from EventBus - reload artist cover if matching."""
        if not self._artist:
            return

        # None means batch update - refresh all
        if item_id is None:
            if self._artist:
                updated = self._library.get_artist_by_name(self._artist.name)
                if updated:
                    self._artist = updated
                    self._do_load_artist(updated)
            return

        # Check if this is an artist cover update
        if item_id == self._artist.name:
            # Reload artist from database to get updated cover_path
            try:
                updated_artist = self._library.get_artist_by_name(self._artist.name)
                if updated_artist:
                    self._artist = updated_artist
                    self._load_cover(updated_artist)
            except Exception as e:
                logger.error(f"Error reloading artist cover: {e}")

        # Check if this is an album cover update (item_id format: "album_name:artist_name")
        if isinstance(item_id, str) and ":" in item_id:
            album_name, artist_name = item_id.split(":", 1)
            if artist_name == self._artist.name:
                # Reload albums to get updated cover paths
                self._albums = self._library.get_artist_albums(self._artist.name)
                self._render_albums()

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update header type label
        self._type_label.setText(t("artist_type"))

        # Update buttons
        self._play_btn.setText(t("play_all"))
        self._shuffle_btn.setText(t("shuffle"))
        self._back_btn.setText(t("back"))

        # Update albums section title
        self._albums_title_label.setText(t("albums"))

        # Update tracks section title
        self._tracks_title_label.setText(t("all_tracks"))

        # Update table headers
        self._tracks_table.setHorizontalHeaderLabels(
            [t("source"), "#", t("title"), t("artist"), t("album"), t("duration")]
        )

        # Update loading indicator label
        self._loading_label.setText(t("loading_artist"))

        # Reload artist data to update stats text
        if self._artist:
            self._stats_label.setText(
                t("songs_albums").format(
                    songs=self._artist.song_count,
                    albums=self._artist.album_count
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


class ArtistCoverDialog(QDialog):
    """Dialog to display large artist cover."""

    def __init__(self, cover_path: str, artist_name: str = "", parent=None):
        """
        Initialize cover dialog.

        Args:
            cover_path: Path to the cover image
            artist_name: Artist name for window title
            parent: Parent widget
        """
        super().__init__(parent)
        self._cover_path = cover_path
        self._artist_name = artist_name
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(self._artist_name or t("artist_cover"))
        self.setModal(True)

        # Get screen size
        screen = QScreen.availableGeometry(self.screen())
        screen_width = screen.width()
        screen_height = screen.height()

        # Set dialog size to 80% of screen, max 800x800
        dialog_width = min(int(screen_width * 0.8), 800)
        dialog_height = min(int(screen_height * 0.8), 800)
        self.setFixedSize(dialog_width, dialog_height)

        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Image label
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet(f"background-color: {theme.background_alt};")

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
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {theme.background};
            }}
        """)

    def keyPressEvent(self, event):
        """Handle key press - close on Escape."""
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

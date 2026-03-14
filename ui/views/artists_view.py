"""
Artists view widget for browsing artists in a grid layout.
"""

import logging
from typing import List

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QGridLayout,
    QFrame,
    QLineEdit,
    QProgressBar,
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QColor

from domain.artist import Artist
from services.library import LibraryService
from services.metadata import CoverService
from ui.widgets import ArtistCard
from system.event_bus import EventBus

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


class ArtistsView(QWidget):
    """
    Artists page displaying a scrollable grid of artist cards.

    Features:
        - Responsive grid layout
        - Search/filter functionality
        - Click to view artist detail
        - Lazy loading for better performance
    """

    artist_clicked = Signal(object)  # Emits Artist object

    # Grid settings
    CARDS_PER_ROW = 5
    CARD_SPACING = 20
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
        self._cards: List[ArtistCard] = []
        self._data_loaded = False
        self._load_worker = None

        self._setup_ui()
        self._connect_signals()
        # Don't load data here - use lazy loading

    def showEvent(self, event):
        """Load data when view is first shown."""
        super().showEvent(event)
        if not self._data_loaded:
            self._load_artists()

    def _setup_ui(self):
        """Set up the artists view UI."""
        self.setStyleSheet("background-color: #121212;")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = self._create_header()
        layout.addWidget(header)

        # Scroll area for grid
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

        # Grid container
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background-color: #121212;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        self._grid_layout.setSpacing(self.CARD_SPACING)
        self._grid_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        scroll_area.setWidget(self._grid_container)
        layout.addWidget(scroll_area)

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
        title_label = QLabel("Artists")
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
        self._search_input.setPlaceholderText("Search artists...")
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

        label = QLabel("Loading artists...")
        label.setStyleSheet("color: #b3b3b3; font-size: 14px;")
        layout.addWidget(label)

        return widget

    def _connect_signals(self):
        """Connect signals."""
        self._search_input.textChanged.connect(self._on_search_changed)
        EventBus.instance().tracks_added.connect(self._on_tracks_added)

    def _load_artists(self):
        """Load artists from library in background thread."""
        if self._data_loaded:
            return

        self._loading.show()
        self._grid_container.hide()

        # Use background thread to load data
        self._load_worker = LoadArtistsWorker(self._library)
        self._load_worker.finished.connect(self._on_artists_loaded)
        self._load_worker.start()

    def _on_artists_loaded(self, artists: List[Artist]):
        """Handle artists loaded from background thread."""
        self._artists = artists
        self._filtered_artists = artists.copy()
        self._data_loaded = True

        self._update_count_label()
        self._render_grid()

        self._loading.hide()
        self._grid_container.show()

        # Clean up worker
        if self._load_worker:
            self._load_worker.deleteLater()
            self._load_worker = None

    def _update_count_label(self):
        """Update the artist count label."""
        total = len(self._artists)
        if self._search_input.text():
            showing = len(self._filtered_artists)
            self._count_label.setText(f"{showing} of {total} artists")
        else:
            self._count_label.setText(f"{total} artists")

    def _render_grid(self):
        """Render the artist cards in a grid."""
        # Clear existing cards
        self._clear_grid()

        # Calculate cards per row based on width
        available_width = self.width() - (2 * self.MARGIN)
        cards_per_row = max(1, available_width // (ArtistCard.CARD_WIDTH + self.CARD_SPACING))

        # Add cards to grid
        for i, artist in enumerate(self._filtered_artists):
            card = ArtistCard(artist)
            card.clicked.connect(self._on_artist_clicked)

            row = i // cards_per_row
            col = i % cards_per_row
            self._grid_layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)
            self._cards.append(card)

    def _clear_grid(self):
        """Clear all cards from the grid."""
        for card in self._cards:
            self._grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

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
        self._render_grid()

    def _on_artist_clicked(self, artist: Artist):
        """Handle artist card click."""
        self.artist_clicked.emit(artist)

    def _on_tracks_added(self, count: int):
        """Handle tracks added to library."""
        # Reload artists
        self._load_artists()

    def resizeEvent(self, event):
        """Handle resize to reflow grid."""
        super().resizeEvent(event)
        if self._filtered_artists:
            self._render_grid()

    def refresh(self):
        """Refresh the artists view."""
        self._load_artists()

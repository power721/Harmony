"""
Artist detail view widget for showing artist information and tracks.
"""

import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QCursor, QMouseEvent, QScreen
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QGridLayout,
    QFrame,
    QPushButton,
    QProgressBar,
    QDialog,
    QTabWidget,
)

from domain.album import Album
from domain.artist import Artist
from domain.track import Track
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService
from system.event_bus import EventBus
from system.i18n import t
from ui.views.local_tracks_list_view import LocalTracksListView
from ui.widgets import AlbumCard

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
    play_tracks = Signal(list, int)  # Emits (list of Track objects, start_index)
    track_double_clicked = Signal(int)  # Emits track_id
    insert_to_queue = Signal(list)  # Emits list of Track objects
    add_to_queue = Signal(list)  # Emits list of Track objects
    add_to_playlist = Signal(list)  # Emits list of Track objects
    remove_from_library_requested = Signal(list)  # Emits list of Track objects
    delete_file_requested = Signal(list)  # Emits list of Track objects
    download_cover_requested = Signal(object)  # Emits Album object
    ALBUMS_BATCH_SIZE = 30
    ALBUMS_LOAD_THRESHOLD_PX = 100

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
        self._albums_loaded_count = 0
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
        from ui.styles import get_scroll_area_style

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
        scroll_area.setStyleSheet(get_scroll_area_style(theme))

        # Content container
        self._content = QWidget()
        self._content.setStyleSheet(f"background-color: {theme.background};")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 20)
        content_layout.setSpacing(0)

        # Artist header
        self._header = self._create_header()
        content_layout.addWidget(self._header)

        # Detail tabs (albums / tracks)
        self._tab_widget = self._create_tab_widget()
        content_layout.addWidget(self._tab_widget)

        scroll_area.setWidget(self._content)
        layout.addWidget(scroll_area)

        # Loading indicator
        self._loading = self._create_loading_indicator()
        layout.addWidget(self._loading)
        self._loading.hide()

    def _connect_signals(self):
        """Connect signals."""
        EventBus.instance().cover_updated.connect(self._on_cover_updated)

    @staticmethod
    def _disconnect_signal(signal, slot):
        """Best-effort signal disconnection for shutdown cleanup."""
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass

    def closeEvent(self, event):
        """Release event bus subscriptions that outlive the view."""
        self._disconnect_signal(EventBus.instance().cover_updated, self._on_cover_updated)
        super().closeEvent(event)

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

        if hasattr(self, '_tracks_list'):
            self._tracks_list.refresh_theme()

        # Update loading label
        if hasattr(self, '_loading_label'):
            self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")

        # Update detail tabs
        if hasattr(self, '_tab_widget'):
            self._tab_widget.tabBar().setCursor(Qt.PointingHandCursor)
            self._tab_widget.setStyleSheet(f"""
                QTabWidget::pane {{
                    border: none;
                    background: transparent;
                }}
                QTabBar::tab {{
                    background: transparent;
                    color: {theme.text_secondary};
                    border: none;
                    border-bottom: 2px solid transparent;
                    padding: 8px 18px;
                }}
                QTabBar::tab:selected {{
                    color: {theme.highlight};
                    border-bottom: 2px solid {theme.highlight};
                }}
                QTabBar::tab:hover:!selected {{
                    color: {theme.highlight};
                }}
            """)

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

        # Scroll area for albums
        self._albums_scroll_area = QScrollArea()
        self._albums_scroll_area.setWidgetResizable(True)
        self._albums_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._albums_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._albums_scroll_area.setMinimumHeight(720)
        self._albums_scroll_area.setStyleSheet(f"""
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

        self._albums_scroll_area.setWidget(self._albums_container)
        self._albums_scroll_area.verticalScrollBar().valueChanged.connect(self._on_albums_scroll_changed)
        layout.addWidget(self._albums_scroll_area, 1)

        return section

    def _create_tab_widget(self) -> QTabWidget:
        """Create tab container for albums and tracks sections."""
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        tab_widget = QTabWidget()
        tab_widget.setDocumentMode(True)
        tab_widget.tabBar().setCursor(Qt.PointingHandCursor)
        tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: none;
                background: transparent;
            }}
            QTabBar::tab {{
                background: transparent;
                color: {theme.text_secondary};
                border: none;
                border-bottom: 2px solid transparent;
                padding: 8px 18px;
            }}
            QTabBar::tab:selected {{
                color: {theme.highlight};
                border-bottom: 2px solid {theme.highlight};
            }}
            QTabBar::tab:hover:!selected {{
                color: {theme.highlight};
            }}
        """)

        self._albums_section = self._create_albums_section()
        self._tracks_section = self._create_tracks_section()
        tab_widget.addTab(self._albums_section, t("albums"))
        tab_widget.addTab(self._tracks_section, t("track"))
        return tab_widget

    def _create_tracks_section(self) -> QWidget:
        """Create tracks list section."""

        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(20, 20, 20, 0)
        layout.setSpacing(16)

        self._tracks_list = LocalTracksListView(show_index=True, show_source=True)
        self._tracks_list.track_activated.connect(self._on_track_activated)
        self._tracks_list.play_requested.connect(self._on_play_requested)
        self._tracks_list.insert_to_queue_requested.connect(self.insert_to_queue.emit)
        self._tracks_list.add_to_queue_requested.connect(self.add_to_queue.emit)
        self._tracks_list.add_to_playlist_requested.connect(self.add_to_playlist.emit)
        self._tracks_list.remove_from_library_requested.connect(self.remove_from_library_requested.emit)
        self._tracks_list.delete_file_requested.connect(self.delete_file_requested.emit)

        layout.addWidget(self._tracks_list)

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
                dialog.exec()
            except Exception as e:
                logger.error(f"Error showing cover dialog: {e}")

    def _render_albums(self):
        """Render album cards with lazy loading."""
        self._clear_album_cards()
        self._albums_loaded_count = 0
        self._load_next_albums_batch()

    def _clear_album_cards(self):
        """Remove all rendered album cards."""
        for card in self._album_cards:
            self._albums_layout.removeWidget(card)
            card.deleteLater()
        self._album_cards.clear()

    def _load_next_albums_batch(self):
        """Append next batch of album cards."""
        if self._albums_loaded_count >= len(self._albums):
            return

        start = self._albums_loaded_count
        end = min(start + self.ALBUMS_BATCH_SIZE, len(self._albums))

        for i in range(start, end):
            album = self._albums[i]
            card = AlbumCard(album)
            card.clicked.connect(self._on_album_clicked)
            card.download_cover_requested.connect(self._on_download_cover_requested)

            row = i // 5
            col = i % 5
            self._albums_layout.addWidget(card, row, col, Qt.AlignTop | Qt.AlignLeft)
            self._album_cards.append(card)

        self._albums_loaded_count = end

    def _on_albums_scroll_changed(self, value: int):
        """Load more albums when user scrolls close to section bottom."""
        scrollbar = self._albums_scroll_area.verticalScrollBar()
        if value >= max(0, scrollbar.maximum() - self.ALBUMS_LOAD_THRESHOLD_PX):
            self._load_next_albums_batch()

    def _render_tracks(self):
        """Load tracks into the list view."""
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        favorite_ids = set()
        if bootstrap and hasattr(bootstrap, 'favorites_service'):
            favorite_ids = bootstrap.favorites_service.get_all_favorite_track_ids()
        self._tracks_list.load_tracks(self._tracks, favorite_ids)

    def _on_play_all(self):
        """Handle play all button click."""
        if self._tracks:
            self.play_tracks.emit(self._tracks, 0)

    def _on_shuffle(self):
        """Handle shuffle button click."""
        if self._tracks:
            import random
            shuffled = self._tracks.copy()
            random.shuffle(shuffled)
            self.play_tracks.emit(shuffled, 0)

    def _on_track_activated(self, track: Track):
        """Handle track activation - play entire artist list from this track."""
        if track and self._tracks:
            start_index = 0
            for i, t_track in enumerate(self._tracks):
                if t_track.id == track.id:
                    start_index = i
                    break
            self.play_tracks.emit(self._tracks, start_index)

    def _on_play_requested(self, selected_tracks: list):
        """Handle play from context menu - play full list from first selected track."""
        if not selected_tracks or not self._tracks:
            return
        first_track = selected_tracks[0]
        start_index = 0
        for i, t_track in enumerate(self._tracks):
            if t_track.id == first_track.id:
                start_index = i
                break
        self.play_tracks.emit(self._tracks, start_index)

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

        # Update tab labels
        self._tab_widget.setTabText(0, t("albums"))
        self._tab_widget.setTabText(1, t("track"))

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

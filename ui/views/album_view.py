"""
Album detail view widget for showing album information and tracks.
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
    QFrame,
    QPushButton,
    QProgressBar,
    QDialog,
)

from domain.album import Album
from domain.track import Track
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService
from system.i18n import t
from ui.views.local_tracks_list_view import LocalTracksListView
from utils import format_duration

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
    play_tracks = Signal(list, int)  # Emits (list of Track objects, start_index)
    track_double_clicked = Signal(int)  # Emits track_id
    insert_to_queue = Signal(list)  # Emits list of Track objects
    add_to_queue = Signal(list)  # Emits list of Track objects
    add_to_playlist = Signal(list)  # Emits list of Track objects
    favorites_toggle_requested = Signal(list, bool)  # (tracks, all_favorited)
    edit_info_requested = Signal(object)  # Track
    download_cover_requested = Signal(object)  # Track
    open_file_location_requested = Signal(object)  # Track
    remove_from_library_requested = Signal(list)  # list of Track
    delete_file_requested = Signal(list)  # list of Track

    _CONTEXT_MENU_TEMPLATE = """
        QMenu {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
        }
        QMenu::item {
            padding: 8px 20px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """

    def __init__(
            self,
            library_service: LibraryService,
            playback_service: PlaybackService = None,
            cover_service: CoverService = None,
            parent=None
    ):
        super().__init__(parent)
        self.setObjectName("albumView")
        self._library = library_service
        self._playback = playback_service
        self._cover_service = cover_service
        self._album: Album = None
        self._tracks: List[Track] = []
        self._current_cover_path: str = None  # Store current cover path

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the album view UI."""
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

        # Album cover (clickable to show large image)
        self._cover_label = ClickableLabel()
        self._cover_label.setFixedSize(200, 200)
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.background_hover};
                border-radius: 8px;
            }}
        """)
        self._cover_label.clicked.connect(self._on_cover_clicked)
        layout.addWidget(self._cover_label, 0, Qt.AlignVCenter)

        # Album info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)

        # Album type label
        self._type_label = QLabel(t("album_type"))
        self._type_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_secondary};
                font-size: 12px;
                font-weight: bold;
            }}
        """)
        info_layout.addWidget(self._type_label)

        # Album name
        self._name_label = QLabel("Album Name")
        self._name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._name_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text};
                font-size: 48px;
                font-weight: bold;
            }}
        """)
        info_layout.addWidget(self._name_label)

        # Artist name
        self._artist_label = QLabel("Artist")
        self._artist_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._artist_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_secondary};
                font-size: 14px;
            }}
        """)
        info_layout.addWidget(self._artist_label)

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

    def _create_tracks_section(self) -> QWidget:
        """Create tracks list section."""
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

        # Tracks list view
        self._tracks_list = LocalTracksListView(show_index=True, show_source=True)
        # Connect all signals
        self._tracks_list.track_activated.connect(self._on_track_activated)
        self._tracks_list.play_requested.connect(self._on_play_requested)
        self._tracks_list.insert_to_queue_requested.connect(self.insert_to_queue.emit)
        self._tracks_list.add_to_queue_requested.connect(self.add_to_queue.emit)
        self._tracks_list.add_to_playlist_requested.connect(self.add_to_playlist.emit)
        self._tracks_list.favorites_toggle_requested.connect(self.favorites_toggle_requested.emit)
        self._tracks_list.edit_info_requested.connect(self.edit_info_requested.emit)
        self._tracks_list.download_cover_requested.connect(self.download_cover_requested.emit)
        self._tracks_list.open_file_location_requested.connect(self.open_file_location_requested.emit)
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

        self._loading_label = QLabel(t("loading_album"))
        self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")
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
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        pixmap = QPixmap(200, 200)
        pixmap.fill(QColor(theme.background_hover))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw music note icon
        painter.setPen(QColor(theme.text_secondary))
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
                dialog.exec()
            except Exception as e:
                logger.error(f"Error showing cover dialog: {e}")

    def _render_tracks(self):
        """Load tracks into the list view."""
        # Get favorite IDs
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        favorite_ids = set()
        if bootstrap and hasattr(bootstrap, 'favorites_service'):
            favorite_ids = bootstrap.favorites_service.get_all_favorite_track_ids()

        self._tracks_list.load_tracks(self._tracks, favorite_ids)

    def _on_track_activated(self, track):
        """Handle track activation - play entire album from this track."""
        if track and self._tracks:
            # Find the index of the clicked track
            start_index = 0
            for i, t in enumerate(self._tracks):
                if t.id == track.id:
                    start_index = i
                    break
            # Play entire album starting from the clicked track
            self.play_tracks.emit(self._tracks, start_index)

    def _on_play_requested(self, selected_tracks: list):
        """Handle play requested from context menu - play full album from first selected track."""
        if not selected_tracks or not self._tracks:
            return
        # Find the index of the first selected track
        first_track = selected_tracks[0]
        start_index = 0
        for i, t in enumerate(self._tracks):
            if t.id == first_track.id:
                start_index = i
                break
        # Play entire album starting from the first selected track
        self.play_tracks.emit(self._tracks, start_index)

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
                    border-radius: 8px;
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

        # Update artist label
        if hasattr(self, '_artist_label'):
            self._artist_label.setStyleSheet(f"""
                QLabel {{
                    color: {theme.text_secondary};
                    font-size: 14px;
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
                }}
                QPushButton:hover {{
                    color: {theme.text};
                    border-color: {theme.text};
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

        # Update loading label
        if hasattr(self, '_loading_label'):
            self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update header type label
        self._type_label.setText(t("album_type"))

        # Update buttons
        self._play_btn.setText(t("play_all"))
        self._shuffle_btn.setText(t("shuffle"))
        self._back_btn.setText(t("back"))

        # Update tracks section title
        self._tracks_title_label.setText(t("all_tracks"))

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
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

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

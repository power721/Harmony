"""
Genre detail view widget for showing genre information and tracks.
"""

import logging
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont, QCursor, QMouseEvent
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QFrame,
    QPushButton,
    QProgressBar,
)

from domain.genre import Genre
from domain.track import Track
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService
from system.i18n import t
from ui.dialogs.cover_preview_dialog import show_cover_preview
from ui.views.local_tracks_list_view import LocalTracksListView

logger = logging.getLogger(__name__)


class GenreView(QWidget):
    """
    Genre detail page showing genre info and tracks.

    Features:
        - Genre header with cover and info
        - Track list view
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
    redownload_requested = Signal(object)  # Track

    def __init__(
            self,
            library_service: LibraryService,
            playback_service: PlaybackService = None,
            cover_service: CoverService = None,
            parent=None
    ):
        super().__init__(parent)
        self.setObjectName("genreView")
        self._library = library_service
        self._playback = playback_service
        self._cover_service = cover_service
        self._genre: Genre = None
        self._tracks: List[Track] = []
        self._current_cover_path: str = None
        self._cover_downloading = False
        self._cover_executor = None

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        self._setup_ui()

    def _setup_ui(self):
        """Set up the genre view UI."""
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

        # Genre header
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
        """Create genre header with cover and info."""
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

        # Genre cover
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

        # Genre info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setSpacing(8)

        # Genre type label
        self._type_label = QLabel(t("genre_type"))
        self._type_label.setStyleSheet(f"""
            QLabel {{
                color: {theme.text_secondary};
                font-size: 12px;
                font-weight: bold;
            }}
        """)
        info_layout.addWidget(self._type_label)

        # Genre name
        self._name_label = QLabel("Genre Name")
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

        self._tracks_list = LocalTracksListView(show_index=True, show_source=True)
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
        self._tracks_list.redownload_requested.connect(self.redownload_requested.emit)

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

        self._loading_label = QLabel(t("loading_genre"))
        self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")
        layout.addWidget(self._loading_label)

        return widget

    def set_genre(self, genre: Genre):
        """Set the genre to display."""
        self._genre = genre
        self._loading.show()
        self._content.hide()

        QTimer.singleShot(10, lambda: self._do_load_genre(genre))

    def get_genre(self) -> Genre:
        """Get the currently displayed genre."""
        return self._genre

    def _do_load_genre(self, genre: Genre):
        """Actually load genre data."""
        try:
            # Load tracks
            self._tracks = self._library.get_genre_tracks(genre.name)

            # Update header
            self._name_label.setText(genre.display_name)
            self._stats_label.setText(
                t("genre_stats").format(
                    songs=genre.song_count,
                    albums=genre.album_count
                )
            )
            self._load_cover(genre)

            # Render tracks
            self._render_tracks()

        except Exception as e:
            logger.error(f"Error loading genre: {e}")
        finally:
            self._loading.hide()
            self._content.show()

    def _load_cover(self, genre: Genre):
        """Load genre cover."""
        cover_path = genre.cover_path

        if cover_path and cover_path.startswith(("http://", "https://")):
            from infrastructure.cache import ImageCache
            cached_data = ImageCache.get(cover_path)
            if cached_data:
                pixmap = QPixmap()
                if pixmap.loadFromData(cached_data):
                    scaled = pixmap.scaled(
                        200, 200,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation
                    )
                    self._cover_label.setPixmap(scaled)
                    self._current_cover_path = cover_path
                    return

            if not self._cover_downloading:
                self._cover_downloading = True
                self._download_cover_async(cover_path)
            self._set_default_cover()
            return

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
                    self._current_cover_path = cover_path
                    return
            except Exception as e:
                logger.debug(f"Error loading cover: {e}")

        # Default cover
        self._set_default_cover()
        self._current_cover_path = None

    def _download_cover_async(self, url: str):
        """Download online cover asynchronously and update header when ready."""
        from concurrent.futures import ThreadPoolExecutor
        from infrastructure.cache import ImageCache
        from infrastructure.network import HttpClient

        try:
            http_client = HttpClient()
            request_url, request_headers = self._prepare_cover_request(url)

            def download():
                try:
                    return http_client.get_content(request_url, headers=request_headers, timeout=5)
                except Exception as e:
                    logger.warning(f"Failed to download genre cover: {e}")
                    return None

            if self._cover_executor is None:
                self._cover_executor = ThreadPoolExecutor(max_workers=1)

            future = self._cover_executor.submit(download)

            def check_download():
                if future.done():
                    image_data = future.result()
                    if image_data:
                        ImageCache.set(url, image_data)
                        pixmap = QPixmap()
                        if pixmap.loadFromData(image_data):
                            scaled = pixmap.scaled(
                                200, 200,
                                Qt.KeepAspectRatioByExpanding,
                                Qt.SmoothTransformation
                            )
                            self._cover_label.setPixmap(scaled)
                            self._current_cover_path = url
                    self._cover_downloading = False
                else:
                    QTimer.singleShot(100, check_download)

            QTimer.singleShot(100, check_download)
        except Exception as e:
            logger.warning(f"Failed to start genre cover download: {e}")
            self._cover_downloading = False

    def _prepare_cover_request(self, url: str) -> tuple[str, dict | None]:
        """Prepare URL/headers for cover hosts with special requirements."""
        request_url = url
        request_headers = None

        if url.startswith("https://y.qq.com/music/photo_new/"):
            request_url = url.replace("https://y.qq.com/music/photo_new/", "https://y.gtimg.cn/music/photo_new/", 1)
            request_headers = {"Referer": "https://y.qq.com/"}
        elif url.startswith("http://y.qq.com/music/photo_new/"):
            request_url = url.replace("http://y.qq.com/music/photo_new/", "https://y.gtimg.cn/music/photo_new/", 1)
            request_headers = {"Referer": "https://y.qq.com/"}
        elif "y.gtimg.cn" in url:
            request_headers = {"Referer": "https://y.qq.com/"}

        return request_url, request_headers

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

    def _render_tracks(self):
        """Load tracks into the list view."""
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        favorite_ids = set()
        if bootstrap and hasattr(bootstrap, "favorites_service"):
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
        """Handle track activation - play entire genre list from this track."""
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

    def _on_cover_clicked(self):
        """Handle genre cover click with the shared preview dialog."""
        if not self._current_cover_path:
            return

        genre_name = self._genre.display_name if self._genre else ""
        self._cover_preview_dialog = show_cover_preview(
            self,
            self._current_cover_path,
            title=genre_name,
        )

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

        if hasattr(self, "_tracks_list"):
            self._tracks_list.refresh_theme()

        # Update loading label
        if hasattr(self, '_loading_label'):
            self._loading_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 14px;")

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update header type label
        self._type_label.setText(t("genre_type"))

        # Update buttons
        self._play_btn.setText(t("play_all"))
        self._shuffle_btn.setText(t("shuffle"))
        self._back_btn.setText(t("back"))

        # Update tracks section title
        self._tracks_title_label.setText(t("all_tracks"))

        # Update loading indicator label
        self._loading_label.setText(t("loading_genre"))

        # Reload genre data to update stats text
        if self._genre:
            self._stats_label.setText(
                t("genre_stats").format(
                    songs=self._genre.song_count,
                    albums=self._genre.album_count
                )
            )


class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""

    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(QCursor(Qt.PointingHandCursor))

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press event."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

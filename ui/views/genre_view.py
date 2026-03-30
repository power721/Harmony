"""
Genre detail view widget for showing genre information and tracks.
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

from domain.genre import Genre
from domain.track import Track
from services.library import LibraryService
from services.metadata import CoverService
from services.playback import PlaybackService
from utils import format_duration
from system.event_bus import EventBus
from system.i18n import t

logger = logging.getLogger(__name__)


class GenreView(QWidget):
    """
    Genre detail page showing genre info and tracks.

    Features:
        - Genre header with cover and info
        - Track list table
        - Play all / Shuffle buttons
    """

    back_clicked = Signal()
    play_tracks = Signal(list)  # Emits list of Track objects
    track_double_clicked = Signal(int)  # Emits track_id
    insert_to_queue = Signal(list)  # Emits list of Track objects
    add_to_queue = Signal(list)  # Emits list of Track objects
    add_to_playlist = Signal(list)  # Emits list of Track objects

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
        self.setObjectName("genreView")
        self._library = library_service
        self._playback = playback_service
        self._cover_service = cover_service
        self._genre: Genre = None
        self._tracks: List[Track] = []
        self._current_cover_path: str = None

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
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(200, 200)
        self._cover_label.setStyleSheet(f"""
            QLabel {{
                background-color: {theme.background_hover};
                border-radius: 8px;
            }}
        """)
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
        """Create tracks table section."""
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

        # Tracks table
        self._tracks_table = QTableWidget()
        self._tracks_table.setObjectName("tracksTable")
        self._tracks_table.setColumnCount(5)
        self._tracks_table.setHorizontalHeaderLabels(
            ["#", t("source"), t("title"), t("artist"), t("duration")]
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
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(1, 80)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        # Styling
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
        """Render tracks table."""
        self._tracks_table.setRowCount(len(self._tracks))

        for i, track in enumerate(self._tracks):
            # Number
            num_item = QTableWidgetItem(str(i + 1))
            num_item.setTextAlignment(Qt.AlignCenter)
            self._tracks_table.setItem(i, 0, num_item)

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
            self._tracks_table.setItem(i, 1, source_item)

            # Title
            title_item = QTableWidgetItem(track.title or track.display_name)
            self._tracks_table.setItem(i, 2, title_item)

            # Artist
            artist_item = QTableWidgetItem(track.artist or "")
            self._tracks_table.setItem(i, 3, artist_item)

            # Duration
            duration_item = QTableWidgetItem(format_duration(track.duration))
            duration_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._tracks_table.setItem(i, 4, duration_item)

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
        item = self._tracks_table.item(index.row(), 2)
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
        from system.theme import ThemeManager

        item = self._tracks_table.itemAt(pos)
        if not item:
            return

        # Get selected track IDs
        selected_rows = set()
        for selected_item in self._tracks_table.selectedItems():
            selected_rows.add(selected_item.row())

        selected_tracks = []
        for row in selected_rows:
            title_item = self._tracks_table.item(row, 2)
            if title_item:
                track_id = title_item.data(Qt.UserRole)
                for track in self._tracks:
                    if track.id == track_id:
                        selected_tracks.append(track)
                        break

        if not selected_tracks:
            return

        menu = QMenu(self)
        menu.setStyleSheet(
            ThemeManager.instance().get_qss(self._CONTEXT_MENU_TEMPLATE)
        )

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

        # Update table headers
        self._tracks_table.setHorizontalHeaderLabels(
            ["#", t("source"), t("title"), t("artist"), t("duration")]
        )

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

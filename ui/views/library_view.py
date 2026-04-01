"""
Library view widget for browsing the music library.
"""
import logging
import shutil
from pathlib import Path

from system.theme import ThemeManager

# Configure logging
logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QAbstractItemView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QDialog,
    QStackedWidget,
    QPushButton,
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QColor, QBrush
from typing import List, Optional

from ui.dialogs.message_dialog import MessageDialog, Yes, No
from domain.track import Track
from services.playback import PlaybackService
from domain.playback import PlaybackState
from services.metadata import CoverService
from utils import format_duration, format_count_message
from system.i18n import t
from system.config import ConfigManager
from system.event_bus import EventBus
from ui.dialogs.edit_media_info_dialog import EditMediaInfoDialog
from ui.dialogs.progress_dialog import ProgressDialog
from ui.workers.ai_enhance_worker import AIEnhanceWorker
from ui.workers.acoustid_worker import AcoustIDWorker
from ui.views.history_list_view import HistoryListView
from ui.icons import IconName, get_icon


class LoadTracksWorker(QThread):
    """Background worker to load tracks from database."""

    finished = Signal(list)
    progress = Signal(list, int)  # (remaining_tracks, total_count)

    FIRST_BATCH = 50

    def __init__(self, library_service, search_text="", source_filter="all", parent=None):
        super().__init__(parent)
        self._library = library_service
        self._search_text = search_text
        self._source_filter = source_filter

    def run(self):
        if self._search_text:
            tracks = self._library.search_tracks(self._search_text)
            # Apply source filter
            if self._source_filter and self._source_filter != "all":
                from domain.track import TrackSource
                source_enum = TrackSource(self._source_filter)
                tracks = [t for t in tracks if t.source == source_enum]
            self.finished.emit(tracks)
        else:
            # First batch: load 50 tracks quickly
            first_batch = self._library.get_all_tracks(limit=self.FIRST_BATCH)
            # Apply source filter to first batch
            if self._source_filter and self._source_filter != "all":
                from domain.track import TrackSource
                source_enum = TrackSource(self._source_filter)
                first_batch = [t for t in first_batch if t.source == source_enum]

            total = self._library.get_track_count()
            if total <= self.FIRST_BATCH:
                self.finished.emit(first_batch)
                return

            # Emit first batch for immediate display
            self.finished.emit(first_batch)

            # Load remaining tracks
            remaining = self._library.get_all_tracks(limit=0, offset=self.FIRST_BATCH)
            if self._source_filter and self._source_filter != "all":
                remaining = [t for t in remaining if t.source == source_enum]
            self.progress.emit(remaining, total)


class LibraryView(QWidget):
    """Library view for browsing music."""

    # QSS template with theme tokens
    _STYLE_TEMPLATE = """
        QLabel#libraryTitle {
            color: %highlight%;
            font-size: 28px;
            font-weight: bold;
            padding: 10px;
        }
        """ + ThemeManager.get_combobox_style() + """
        QLineEdit {
            background-color: %background_hover%;
            color: %text%;
            border: 2px solid %border%;
            border-radius: 20px;
            padding: 10px 15px;
            font-size: 14px;
        }
        QLineEdit:focus {
            border: 2px solid %highlight%;
            background-color: %background_hover%;
        }
        QLineEdit::placeholder {
            color: %text_secondary%;
        }
        QLineEdit::clear-button {
            subcontrol-origin: padding;
            subcontrol-position: right;
            width: 18px;
            height: 18px;
            margin-right: 8px;
            border-radius: 9px;
            background-color: %border%;
        }
        QLineEdit::clear-button:hover {
            background-color: %background_hover%;
            border: 1px solid %border%;
        }
        QLineEdit::clear-button:pressed {
            background-color: %background_alt%;
        }
        QTableWidget#tracksTable {
            background-color: %background%;
            border: none;
            border-radius: 8px;
            gridline-color: %background_hover%;
        }
        QTableWidget#tracksTable::item {
            padding: 12px 8px;
            color: %text%;
            border: none;
            border-bottom: 1px solid %background_hover%;
        }
        QTableWidget#tracksTable::item:alternate {
            background-color: %background_alt%;
        }
        QTableWidget#tracksTable::item:!alternate {
            background-color: %background%;
        }
        QTableWidget#tracksTable::item:selected {
            background-color: %highlight%;
            color: %background%;
            font-weight: 500;
        }
        QTableWidget#tracksTable::item:selected:!alternate {
            background-color: %highlight%;
        }
        QTableWidget#tracksTable::item:selected:alternate {
            background-color: %highlight_hover%;
        }
        QTableWidget#tracksTable::item:hover {
            background-color: %background_hover%;
        }
        QTableWidget#tracksTable::item:selected:hover {
            background-color: %highlight_hover%;
        }
        QTableWidget#tracksTable::item:focus {
            outline: none;
            border: none;
        }
        QTableWidget#tracksTable:focus {
            outline: none;
            border: none;
        }
        QTableWidget#tracksTable QHeaderView::section {
            background-color: %background_hover%;
            color: %highlight%;
            padding: 14px 12px;
            border: none;
            border-bottom: 2px solid %highlight%;
            border-radius: 0px;
            font-weight: bold;
            font-size: 13px;
            letter-spacing: 0.5px;
        }
        QTableWidget#tracksTable QTableCornerButton::section {
            background-color: %background_hover%;
            border: none;
            border-right: 1px solid %border%;
            border-bottom: 2px solid %highlight%;
        }
        QTableWidget#tracksTable QScrollBar:vertical {
            background-color: %background%;
            width: 12px;
            border-radius: 6px;
            margin: 0px;
        }
        QTableWidget#tracksTable QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 40px;
        }
        QTableWidget#tracksTable QScrollBar::handle:vertical:hover {
            background-color: %border%;
        }
        QTableWidget#tracksTable QScrollBar:horizontal {
            background-color: %background%;
            height: 12px;
            border-radius: 6px;
        }
        QTableWidget#tracksTable QScrollBar::handle:horizontal {
            background-color: %border%;
            border-radius: 6px;
            min-width: 40px;
        }
        QTableWidget#tracksTable QScrollBar::handle:horizontal:hover {
            background-color: %border%;
        }
        QTableWidget#tracksTable QScrollBar::add-line, QScrollBar::sub-line {
            height: 0px;
            width: 0px;
        }
    """
    _CONTEXT_MENU_STYLE = """
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

    track_double_clicked = Signal(int)  # Signal when track is double-clicked
    cloud_file_double_clicked = Signal(str, int)  # Signal when cloud file is double-clicked (file_id, account_id)
    insert_to_queue = Signal(list)  # Signal when tracks should be inserted after current
    add_to_queue = Signal(list)  # Signal when tracks should be added to queue
    add_to_playlist_signal = Signal(
        list
    )  # Signal when tracks should be added to a playlist

    def __init__(
            self, library_service, favorites_service, play_history_service, player: PlaybackService,
            config_manager: ConfigManager = None,
            cover_service: CoverService = None, parent=None
    ):
        """
        Initialize library view.

        Args:
            library_service: Library service for track operations
            favorites_service: Favorites service for favorite operations
            play_history_service: Play history service for history operations
            player: Player controller
            config_manager: Configuration manager for AI settings
            cover_service: Cover service for downloading album art
            parent: Parent widget
        """
        super().__init__(parent)
        self._library_service = library_service
        self._favorites_service = favorites_service
        self._play_history_service = play_history_service
        self._player = player
        self._config = config_manager
        self._cover_service = cover_service
        self._current_view = "all"  # all, favorites, history
        self._current_playing_track_id = None  # Track currently playing
        self._current_playing_row = -1  # Row of currently playing track
        self._track_id_to_row = {}  # Dict for O(1) row lookup by track_id
        self._load_worker = None
        self._history_list_view = None  # History list view widget
        self._history_played_at_map = {}  # track_id -> played_at datetime
        self._view_search_texts = {
            "all": "",
            "favorites": "",
            "history": "",
        }  # 保存每个视图的搜索文本

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        self._setup_ui()
        self._setup_connections()
        self.refresh()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header with title and search
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(20, 10, 20, 10)

        self._title_label = QLabel(t("library"))
        self._title_label.setObjectName("libraryTitle")
        header_layout.addWidget(self._title_label)

        # View toggle button (for history view)
        self._view_toggle_btn = QPushButton()
        self._view_toggle_btn.setFixedSize(32, 32)
        self._view_toggle_btn.setToolTip(t("toggle_view"))
        self._view_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._view_toggle_btn.setVisible(False)  # Only visible in history view
        header_layout.addWidget(self._view_toggle_btn)

        header_layout.addStretch()

        # Source filter dropdown
        from PySide6.QtWidgets import QComboBox
        self._source_filter = QComboBox()
        self._source_filter.addItem(t("all_sources"), "all")
        self._source_filter.addItem(t("source_local"), "Local")
        self._source_filter.addItem(t("source_quark"), "QUARK")
        self._source_filter.addItem(t("source_baidu"), "BAIDU")
        self._source_filter.addItem(t("source_qq"), "QQ")
        self._source_filter.setFixedWidth(120)
        header_layout.addWidget(self._source_filter)

        # Add spacing between filter and search box
        header_layout.addSpacing(10)

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("search_tracks"))
        self._search_input.setFixedWidth(300)
        self._search_input.setClearButtonEnabled(True)  # 启用清除按钮
        header_layout.addWidget(self._search_input)

        layout.addLayout(header_layout)

        # Stacked widget for table and list views
        self._stacked_widget = QStackedWidget()
        layout.addWidget(self._stacked_widget)

        # Tracks table (page 0)
        self._tracks_table = QTableWidget()
        self._tracks_table.setObjectName("tracksTable")
        self._tracks_table.setColumnCount(7)
        self._tracks_table.setHorizontalHeaderLabels(
            [t("source"), t("title"), t("artist"), t("album"), t("genre"), t("duration"), ""]
        )

        # Configure table
        self._tracks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tracks_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tracks_table.setAlternatingRowColors(True)
        self._tracks_table.verticalHeader().setVisible(False)
        self._tracks_table.horizontalHeader().setStretchLastSection(False)
        self._tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tracks_table.customContextMenuRequested.connect(self._show_context_menu)
        # Disable editing
        self._tracks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Remove focus outline
        self._tracks_table.setFocusPolicy(Qt.NoFocus)

        # Set column widths
        header = self._tracks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        # Favorites: fixed small width
        header.setSectionResizeMode(6, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(6, 40)

        self._stacked_widget.addWidget(self._tracks_table)

        # History list view (page 1)
        self._history_list_view = HistoryListView()
        self._stacked_widget.addWidget(self._history_list_view)

        # Loading indicator
        self._loading_label = QLabel("⏳ " + t("loading"))
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setVisible(False)
        layout.addWidget(self._loading_label)

        # Status bar
        self._status_label = QLabel(t("no_tracks"))
        layout.addWidget(self._status_label)

        # Load view mode preference
        self._load_view_mode()

        # Apply themed styles
        self.refresh_theme()

    def _setup_connections(self):
        """Setup signal connections."""
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._on_search)
        self._source_filter.currentIndexChanged.connect(self._on_source_filter_changed)
        self._tracks_table.itemDoubleClicked.connect(self._on_item_double_clicked)

        # View toggle button
        self._view_toggle_btn.clicked.connect(self._toggle_history_view_mode)

        # History list view
        self._history_list_view.track_activated.connect(self._on_history_track_activated)
        self._history_list_view.play_requested.connect(self._on_history_play_requested)
        self._history_list_view.insert_to_queue_requested.connect(self._on_history_insert_to_queue)
        self._history_list_view.add_to_queue_requested.connect(self._on_history_add_to_queue)
        self._history_list_view.add_to_playlist_requested.connect(self._on_history_add_to_playlist)
        self._history_list_view.favorites_toggle_requested.connect(self._on_history_favorites_toggle)
        self._history_list_view.edit_info_requested.connect(self._on_history_edit_info)
        self._history_list_view.download_cover_requested.connect(self._on_history_download_cover)
        self._history_list_view.open_file_location_requested.connect(self._on_history_open_file_location)
        self._history_list_view.remove_from_library_requested.connect(self._on_history_remove_from_library)
        self._history_list_view.delete_file_requested.connect(self._on_history_delete_file)

        # Connect to player engine signals
        self._player.engine.current_track_changed.connect(
            self._on_current_track_changed
        )
        self._player.engine.state_changed.connect(self._on_player_state_changed)

        # Connect to file organization events
        event_bus = EventBus.instance()
        event_bus.tracks_organized.connect(self._on_tracks_organized)

    def refresh_theme(self):
        """Apply themed styles from ThemeManager."""
        from system.theme import ThemeManager
        theme_manager = ThemeManager.instance()

        self.setStyleSheet(theme_manager.get_qss(self._STYLE_TEMPLATE))

        # Update loading label with theme colors
        theme = theme_manager.current_theme
        self._loading_label.setStyleSheet(
            f"color: {theme.highlight}; font-size: 16px; padding: 40px; "
            f"background-color: {theme.background_alt}; border-radius: 8px;"
        )

        # Update status label with theme colors
        self._status_label.setStyleSheet(
            f"color: {theme.text_secondary}; font-size: 13px; padding: 8px 0px;"
        )

    def refresh(self):
        """Refresh the library view."""
        # Update UI texts
        self._search_input.setPlaceholderText(t("search_tracks"))

        # Update table headers
        self._tracks_table.setHorizontalHeaderLabels(
            [t("source"), t("title"), t("artist"), t("album"), t("genre"), t("duration"), ""]
        )

        # Update title based on current view
        if self._current_view == "all":
            self._title_label.setText(t("library"))
        elif self._current_view == "favorites":
            self._title_label.setText(t("favorites"))
        elif self._current_view == "history":
            self._title_label.setText(t("history"))

        # Reload data
        self._stacked_widget.setCurrentIndex(0)  # Show table view
        if self._current_view == "all":
            self._load_all_tracks()
        elif self._current_view == "favorites":
            self._load_favorites()
        elif self._current_view == "history":
            self._load_history()

    def get_current_view(self) -> str:
        """Get current view type.

        Returns:
            "all", "favorites", or "history"
        """
        return self._current_view

    def show_all(self):
        """Show all tracks."""
        # 保存当前视图的搜索文本
        self._view_search_texts[self._current_view] = self._search_input.text()

        self._current_view = "all"
        self._title_label.setText(t("library"))

        # Hide view toggle button for non-history views
        self._view_toggle_btn.setVisible(False)
        self._stacked_widget.setCurrentIndex(0)  # Show table view

        # Show source filter for library view
        self._source_filter.setVisible(True)

        # 恢复 Library 视图的搜索文本
        saved_text = self._view_search_texts.get("all", "")
        self._search_input.setText(saved_text)

        if saved_text:
            # 如果有保存的搜索文本，执行搜索
            self._on_search(saved_text)
        else:
            # 否则加载所有歌曲
            self._load_all_tracks()

        # Select and scroll to current playing track after UI updates
        from PySide6.QtCore import QTimer

        QTimer.singleShot(150, self._select_and_scroll_to_current)

    def show_favorites(self):
        """Show favorite tracks."""
        # 保存当前视图的搜索文本
        self._view_search_texts[self._current_view] = self._search_input.text()

        self._current_view = "favorites"
        self._title_label.setText(t("favorites"))

        # Hide view toggle button for non-history views
        self._view_toggle_btn.setVisible(False)
        self._stacked_widget.setCurrentIndex(0)  # Show table view

        # Hide source filter for favorites view
        self._source_filter.setVisible(False)

        # 恢复 Favorites 视图的搜索文本
        saved_text = self._view_search_texts.get("favorites", "")
        self._search_input.setText(saved_text)

        if saved_text:
            # 如果有保存的搜索文本，执行搜索
            self._on_search(saved_text)
        else:
            # 否则加载所有收藏
            self._load_favorites()

    def show_history(self):
        """Show play history."""
        # 保存当前视图的搜索文本
        self._view_search_texts[self._current_view] = self._search_input.text()

        self._current_view = "history"
        self._title_label.setText(t("history"))

        # Show view toggle button for history
        self._view_toggle_btn.setVisible(True)
        self._update_view_toggle_icon()

        # Hide source filter for history view
        self._source_filter.setVisible(False)

        # 恢复 History 视图的搜索文本
        saved_text = self._view_search_texts.get("history", "")
        self._search_input.setText(saved_text)

        if saved_text:
            # 如果有保存的搜索文本，执行搜索
            self._on_search(saved_text)
        else:
            # 否则加载历史记录
            self._load_history()

    def _load_all_tracks(self):
        """Load all tracks into the table (async via background thread)."""
        self._loading_label.setVisible(True)
        self._tracks_table.setVisible(False)

        # Clean up previous worker if still running
        if self._load_worker and self._load_worker.isRunning():
            self._load_worker.quit()
            if not self._load_worker.wait(1000):
                self._load_worker.terminate()
                self._load_worker.wait()

        search_text = self._search_input.text()
        source_filter = self._source_filter.currentData()
        self._load_worker = LoadTracksWorker(
            self._library_service, search_text=search_text, source_filter=source_filter, parent=self
        )
        self._load_worker.finished.connect(self._on_tracks_loaded)
        self._load_worker.progress.connect(self._on_tracks_remaining)
        self._load_worker.start()

    def _on_tracks_loaded(self, tracks):
        """Handle first batch of tracks loaded from background thread."""
        self._populate_table(tracks)
        self._status_label.setText(f"{len(tracks)} {t('tracks')}")

        self._loading_label.setVisible(False)
        self._tracks_table.setVisible(True)

    def _on_tracks_remaining(self, remaining_tracks, total_count):
        """Handle remaining tracks loaded after first batch."""
        if not remaining_tracks:
            return
        # Append remaining tracks to the table
        from PySide6.QtGui import QBrush, QColor
        from system.theme import ThemeManager

        theme = ThemeManager.instance().current_theme
        text_secondary_color = QColor(theme.text_secondary)
        text_color = QColor(theme.text)

        favorite_ids = self._favorites_service.get_all_favorite_track_ids()

        start_row = self._tracks_table.rowCount()
        self._tracks_table.setUpdatesEnabled(False)
        self._tracks_table.setRowCount(start_row + len(remaining_tracks))
        try:
            for i, track in enumerate(remaining_tracks):
                row = start_row + i
                self._track_id_to_row[track.id] = row

                # Source
                source_value = track.source.value if hasattr(track, 'source') and track.source else "Local"
                source_key_map = {"Local": "source_local", "QUARK": "source_quark", "BAIDU": "source_baidu",
                                  "QQ": "source_qq"}
                source_text = t(source_key_map.get(source_value, "source_local"))
                source_item = QTableWidgetItem(source_text)
                source_item.setForeground(QBrush(text_secondary_color))
                source_item.setData(Qt.UserRole, track.id)
                self._tracks_table.setItem(row, 0, source_item)

                # Title
                is_currently_playing = track.id == self._current_playing_track_id
                icon_prefix = ""
                if is_currently_playing:
                    if self._player.engine.state == PlaybackState.PLAYING:
                        icon_prefix = "▶️ "
                    else:
                        icon_prefix = "⏸️ "
                title_text = f"{icon_prefix}{track.title or track.path.split('/')[-1]}"
                title_item = QTableWidgetItem(title_text)
                title_item.setForeground(QBrush(text_color))
                if is_currently_playing:
                    from PySide6.QtGui import QFont
                    font = title_item.font()
                    font.setBold(True)
                    title_item.setFont(font)
                    title_item.setForeground(QBrush(QColor(theme.highlight)))
                self._tracks_table.setItem(row, 1, title_item)

                # Artist
                artist_item = QTableWidgetItem(track.artist or t("unknown"))
                artist_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 2, artist_item)

                # Album
                album_item = QTableWidgetItem(track.album or t("unknown"))
                album_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 3, album_item)

                # Genre
                genre_item = QTableWidgetItem(track.genre or t("unknown"))
                genre_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 4, genre_item)

                # Duration
                duration_item = QTableWidgetItem(format_duration(track.duration))
                duration_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 5, duration_item)

                # Favorite
                is_fav = track.id in favorite_ids
                fav_text = "★" if is_fav else ""
                fav_item = QTableWidgetItem(fav_text)
                fav_item.setForeground(
                    QBrush(QColor(theme.highlight if is_fav else theme.border))
                )
                self._tracks_table.setItem(row, 6, fav_item)
        finally:
            self._tracks_table.setUpdatesEnabled(True)

        # Update status with total count
        total_rows = self._tracks_table.rowCount()
        self._status_label.setText(f"{total_rows} {t('tracks')}")

    def _load_favorites(self):
        """Load favorite tracks and cloud files."""
        self._loading_label.setVisible(True)
        self._tracks_table.setVisible(False)

        favorites = self._favorites_service.get_favorites_with_cloud()
        self._populate_favorites_table(favorites)
        self._status_label.setText(f"{len(favorites)} {t('favorites_word')}")

        self._loading_label.setVisible(False)
        self._tracks_table.setVisible(True)

    def _populate_favorites_table(self, favorites: list):
        """Populate table with favorites (mix of local and cloud)."""
        from PySide6.QtGui import QBrush, QColor
        from system.theme import ThemeManager

        # Get theme colors
        theme = ThemeManager.instance().current_theme
        text_secondary_color = QColor(theme.text_secondary)
        text_color = QColor(theme.text)

        # Disable updates during batch population
        self._tracks_table.setUpdatesEnabled(False)
        self._tracks_table.setRowCount(0)
        self._current_tracks = []

        for item in favorites:
            row = self._tracks_table.rowCount()
            self._tracks_table.insertRow(row)

            # Determine if this is an undownloaded cloud file
            is_undownloaded_cloud = item.get("type") == "cloud" and not item.get("track_id")

            # Store item data for playback
            # Use track_id if available, otherwise fall back to cloud_file_id
            if item.get("track_id"):
                track_data = item.get("track_id")  # Just store the ID for consistency with _populate_table
            else:
                track_data = {
                    "type": "cloud",
                    "id": None,
                    "track_id": None,
                    "cloud_file_id": item.get("cloud_file_id"),
                    "cloud_account_id": item.get("cloud_account_id"),
                    "title": item.get("title", ""),
                    "artist": item.get("artist", ""),
                    "album": item.get("album", ""),
                    "duration": item.get("duration", 0),
                    "path": item.get("path", ""),
                }
            self._current_tracks.append(track_data)

            # Cloud items have gray text
            text_brush = QBrush(text_secondary_color) if is_undownloaded_cloud else QBrush(text_color)

            # Source
            source_value = item.get("source", "Local")
            source_key_map = {"Local": "source_local", "QUARK": "source_quark", "BAIDU": "source_baidu",
                              "QQ": "source_qq"}
            source_text = t(source_key_map.get(source_value, "source_local"))
            source_item = QTableWidgetItem(source_text)
            source_item.setForeground(text_brush)
            source_item.setData(Qt.UserRole, track_data)
            self._tracks_table.setItem(row, 0, source_item)

            # Title
            title_item = QTableWidgetItem(item.get("title", ""))
            title_item.setForeground(text_brush)
            self._tracks_table.setItem(row, 1, title_item)

            # Artist
            artist_item = QTableWidgetItem(item.get("artist", "") or t("unknown"))
            artist_item.setForeground(text_brush)
            self._tracks_table.setItem(row, 2, artist_item)

            # Album
            album_item = QTableWidgetItem(item.get("album", "") or t("unknown"))
            album_item.setForeground(text_brush)
            self._tracks_table.setItem(row, 3, album_item)

            # Genre
            genre_item = QTableWidgetItem(item.get("genre", "") or t("unknown"))
            genre_item.setForeground(text_brush)
            self._tracks_table.setItem(row, 4, genre_item)

            # Duration
            # format_duration imported at top
            duration_item = QTableWidgetItem(format_duration(item.get("duration", 0)))
            duration_item.setForeground(text_brush)
            self._tracks_table.setItem(row, 5, duration_item)

        # Re-enable updates after batch population
        self._tracks_table.setUpdatesEnabled(True)

    def _load_history(self):
        """Load play history."""
        self._loading_label.setVisible(True)
        self._stacked_widget.setVisible(False)

        history = self._play_history_service.get_history()

        # Batch query tracks by IDs (avoid N+1 query)
        track_ids = [entry.track_id for entry in history]
        tracks_map = {t.id: t for t in self._library_service.get_tracks_by_ids(track_ids)}

        tracks = []
        self._history_played_at_map = {}
        for entry in history:
            track = tracks_map.get(entry.track_id)
            if track:
                tracks.append(track)
                self._history_played_at_map[track.id] = entry.played_at

        # Check current view mode
        view_mode = self._config.get("view/history_view_mode", "table")

        if view_mode == "list":
            # Load into list view
            favorite_ids = self._favorites_service.get_all_favorite_track_ids()
            self._history_list_view.load_tracks(tracks, self._history_played_at_map, favorite_ids)
            self._stacked_widget.setCurrentIndex(1)  # Show list view
        else:
            # Load into table view
            self._populate_table(tracks)
            self._stacked_widget.setCurrentIndex(0)  # Show table view

        self._status_label.setText(f"{len(tracks)} {t('recently_played')}")

        self._loading_label.setVisible(False)
        self._stacked_widget.setVisible(True)

        # Apply current playing indicator after loading (only for table view)
        if view_mode == "table" and self._current_playing_track_id:
            self._set_track_playing_status(self._current_playing_track_id, True)
            self._scroll_to_playing_track()

    def _load_artists(self):
        """Load artists view."""
        # Get all unique artists
        tracks = self._library_service.get_all_tracks()
        artists = {}
        for track in tracks:
            if track.artist not in artists:
                artists[track.artist] = []
            artists[track.artist].append(track)

        # For now, show first track per artist
        # In a full implementation, this would show artist cards
        artist_tracks = []
        for artist, track_list in sorted(artists.items()):
            if track_list:
                artist_tracks.append(track_list[0])

        self._populate_table(artist_tracks)
        self._status_label.setText(f"{len(artists)} {t('artists_count')}")

    def _load_albums(self):
        """Load albums view."""
        # Get all unique albums
        tracks = self._library_service.get_all_tracks()
        albums = {}
        for track in tracks:
            key = f"{track.artist} - {track.album}"
            if key not in albums:
                albums[key] = []
            albums[key].append(track)

        # For now, show first track per album
        album_tracks = []
        for album, track_list in sorted(albums.items()):
            if track_list:
                album_tracks.append(track_list[0])

        self._populate_table(album_tracks)
        self._status_label.setText(f"{len(albums)} {t('albums_count')}")

    def _populate_table(self, tracks: List[Track]):
        """Populate the table with tracks."""
        # format_duration imported at top
        from PySide6.QtGui import QBrush, QColor
        from system.theme import ThemeManager

        # Get theme colors for consistent styling
        theme = ThemeManager.instance().current_theme
        text_secondary_color = QColor(theme.text_secondary)
        text_color = QColor(theme.text)
        highlight_color = QColor(theme.highlight)

        # Clear and rebuild track_id -> row mapping for O(1) lookup
        self._track_id_to_row.clear()

        # Batch load all favorite track IDs for O(1) lookup (N queries -> 1 query)
        favorite_ids = self._favorites_service.get_all_favorite_track_ids()

        # Block UI updates during population
        self._tracks_table.setUpdatesEnabled(False)
        self._tracks_table.setRowCount(len(tracks))

        try:
            # Batch size for UI updates (process in chunks to avoid blocking)
            batch_size = 50
            for row, track in enumerate(tracks):
                # Build track_id -> row mapping
                self._track_id_to_row[track.id] = row

                # Source
                source_value = track.source.value if hasattr(track, 'source') and track.source else "Local"
                source_key_map = {"Local": "source_local", "QUARK": "source_quark", "BAIDU": "source_baidu",
                                  "QQ": "source_qq"}
                source_text = t(source_key_map.get(source_value, "source_local"))
                source_item = QTableWidgetItem(source_text)
                source_item.setForeground(QBrush(text_secondary_color))
                source_item.setData(Qt.UserRole, track.id)
                self._tracks_table.setItem(row, 0, source_item)

                # Title - add play icon if currently playing
                is_currently_playing = track.id == self._current_playing_track_id
                if is_currently_playing:
                    playing_row = row

                # Determine icon based on player state
                icon_prefix = ""
                if is_currently_playing:
                    if self._player.engine.state == PlaybackState.PLAYING:
                        icon_prefix = "▶️ "
                    else:
                        icon_prefix = "⏸️ "

                title_text = f"{icon_prefix}{track.title or track.path.split('/')[-1]}"
                title_item = QTableWidgetItem(title_text)
                title_item.setForeground(QBrush(text_color))

                # Make currently playing row bold and green
                if is_currently_playing:
                    from PySide6.QtGui import QFont

                    font = title_item.font()
                    font.setBold(True)
                    title_item.setFont(font)
                    title_item.setForeground(QBrush(highlight_color))

                self._tracks_table.setItem(row, 1, title_item)

                # Artist
                artist_item = QTableWidgetItem(track.artist or t("unknown"))
                artist_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 2, artist_item)

                # Album
                album_item = QTableWidgetItem(track.album or t("unknown"))
                album_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 3, album_item)

                # Genre
                genre_item = QTableWidgetItem(track.genre or t("unknown"))
                genre_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 4, genre_item)

                # Duration
                duration_item = QTableWidgetItem(format_duration(track.duration))
                duration_item.setForeground(QBrush(text_secondary_color))
                self._tracks_table.setItem(row, 5, duration_item)

                # Favorite indicator (check if actually favorited) - O(1) set lookup
                is_fav = track.id in favorite_ids
                fav_text = "★" if is_fav else ""
                fav_item = QTableWidgetItem(fav_text)
                from system.theme import ThemeManager
                tm = ThemeManager.instance()
                fav_item.setForeground(
                    QBrush(QColor(tm.current_theme.highlight if is_fav else tm.current_theme.border))
                )
                self._tracks_table.setItem(row, 6, fav_item)

                # Process events periodically to keep UI responsive
                if (row + 1) % batch_size == 0:
                    from PySide6.QtWidgets import QApplication

                    QApplication.processEvents()

        finally:
            # Re-enable updates
            self._tracks_table.setUpdatesEnabled(True)

    def _filter_tracks_by_query(self, tracks: List[Track], query: str) -> List[Track]:
        """Filter a list of tracks by search query."""
        query_lower = query.lower()
        return [
            track for track in tracks if self._track_matches_query(track, query_lower)
        ]

    def _track_matches_query(self, track: Track, query: str) -> bool:
        """Check if a track matches the search query."""
        query_lower = query.lower() if isinstance(query, str) else query

        return (
                (track.title and query_lower in track.title.lower())
                or (track.artist and query_lower in track.artist.lower())
                or (track.album and query_lower in track.album.lower())
        )

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                if unit == "B":
                    return f"{size_bytes} {unit}"
                else:
                    return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _restore_track_selection(self, track_ids: list):
        """Restore selection for given track IDs after table refresh."""
        if not track_ids:
            return

        def restore_selection():
            # Clear current selection
            self._tracks_table.clearSelection()

            # Find and select each track using O(1) lookup
            for track_id in track_ids:
                row = self._track_id_to_row.get(track_id)
                if row is not None:
                    # Select the row
                    self._tracks_table.selectRow(row)

            # Scroll to first selected item
            selected_items = self._tracks_table.selectedItems()
            if selected_items:
                self._tracks_table.scrollToItem(selected_items[0])

        # Use QTimer to delay restoration until after table is fully updated
        QTimer.singleShot(50, restore_selection)

    def _on_search_text_changed(self, text: str):
        """Debounce search - restart timer on each keystroke."""
        self._search_timer.start()

    def _on_source_filter_changed(self):
        """Handle source filter change."""
        # Reload tracks with new filter
        if self._current_view == "all":
            self._load_all_tracks()

    def _on_search(self, query: str = ""):
        """Handle search based on current view (debounced)."""
        query = query or self._search_input.text()
        # 保存当前视图的搜索文本
        self._view_search_texts[self._current_view] = query

        if not query:
            # 清空搜索时也清空保存的文本
            self._view_search_texts[self._current_view] = ""
            self.refresh()
            return

        # 根据当前视图决定搜索范围
        if self._current_view == "all":
            # 在所有 tracks 中搜索
            tracks = self._library_service.search_tracks(query)
            status_text = f'{len(tracks)} {t("results_for")} "{query}"'

        elif self._current_view == "favorites":
            # 在收藏的 tracks 中搜索
            all_favorites = self._favorites_service.get_favorites()
            tracks = self._filter_tracks_by_query(all_favorites, query)
            status_text = (
                f'{len(tracks)} {t("results_for")} "{query}" {t("in_favorites")}'
            )

        elif self._current_view == "history":
            # 在历史记录中搜索
            history = self._play_history_service.get_history()
            # Batch query tracks by IDs (avoid N+1 query)
            track_ids = [entry.track_id for entry in history]
            tracks_map = {t.id: t for t in self._library_service.get_tracks_by_ids(track_ids)}
            tracks = []
            for entry in history:
                track = tracks_map.get(entry.track_id)
                if track and self._track_matches_query(track, query):
                    tracks.append(track)
            status_text = (
                f'{len(tracks)} {t("results_for")} "{query}" {t("in_history")}'
            )
        else:
            tracks = []
            status_text = f'0 {t("results_for")} "{query}"'

        self._populate_table(tracks)
        self._status_label.setText(status_text)

    def _on_current_track_changed(self, track_dict: dict):
        """Handle current track change from player."""
        if track_dict:
            new_track_id = track_dict.get("id")
            old_track_id = self._current_playing_track_id

            # For cloud files, try to find the track_id from database
            if new_track_id is None:
                cloud_file_id = track_dict.get("cloud_file_id")
                local_path = track_dict.get("path")

                if cloud_file_id:
                    track = self._library_service.get_track_by_cloud_file_id(cloud_file_id)
                    if track:
                        new_track_id = track.id
                elif local_path:
                    track = self._library_service.get_track_by_path(local_path)
                    if track:
                        new_track_id = track.id

            self._current_playing_track_id = new_track_id

            # Update the playing indicator in the table without reloading
            self._update_playing_indicator_in_table(old_track_id, new_track_id)

            # Scroll to the playing track
            self._scroll_to_playing_track()

    def _on_player_state_changed(self, state: PlaybackState):
        """Handle player state change (play/pause)."""
        # Update the icon when playing/paused without reloading
        self._update_playing_icon_state()

    def _update_playing_indicator_in_table(
            self, old_track_id: Optional[int], new_track_id: Optional[int]
    ):
        """Update playing indicator by modifying existing items instead of reloading."""

        # Remove playing indicator from old track
        if old_track_id is not None:
            self._set_track_playing_status(old_track_id, False)

        # Add playing indicator to new track
        if new_track_id is not None:
            self._set_track_playing_status(new_track_id, True)

    def _update_playing_icon_state(self):
        """Update the playing/paused icon for current track."""
        if self._current_playing_track_id is not None:
            self._set_track_playing_status(
                self._current_playing_track_id, True, update_icon_only=True
            )

    def _set_track_playing_status(
            self, track_id: int, is_playing: bool, update_icon_only: bool = False
    ):
        """Set the playing status for a specific track in the table."""
        from PySide6.QtGui import QBrush, QColor
        from system.theme import ThemeManager

        # Get theme colors
        theme = ThemeManager.instance().current_theme
        highlight_color = QColor(theme.highlight)
        text_color = QColor(theme.text)

        # O(1) lookup by track_id
        row = self._track_id_to_row.get(track_id)
        if row is None:
            return

        title_item = self._tracks_table.item(row, 1)
        if not title_item:
            return

        # Get the original title without icon
        current_text = title_item.text()
        # Remove any existing icons
        original_title = current_text.replace("▶️ ", "").replace("⏸️ ", "")

        if is_playing:
            # Determine which icon to show
            if self._player.engine.state == PlaybackState.PLAYING:
                icon = "▶️ "
            else:
                icon = "⏸️ "

            new_text = f"{icon}{original_title}"

            # Update text
            title_item.setText(new_text)

            # Update font and color
            if not update_icon_only:
                font = title_item.font()
                font.setBold(True)
                title_item.setFont(font)
                title_item.setForeground(QBrush(highlight_color))
        else:
            # Remove playing indicator
            title_item.setText(original_title)

            # Reset font and color
            if not update_icon_only:
                font = title_item.font()
                font.setBold(False)
                title_item.setFont(font)
                title_item.setForeground(QBrush(text_color))

    def _scroll_to_playing_track(self):
        """Scroll to the currently playing track."""
        if self._current_playing_track_id is None:
            return

        # O(1) lookup by track_id
        row = self._track_id_to_row.get(self._current_playing_track_id)
        if row is None:
            return

        item = self._tracks_table.item(row, 0)
        if item:
            # Select the row
            self._tracks_table.selectRow(row)
            # Scroll to the item
            self._tracks_table.scrollToItem(item)

    def _select_track_by_id(self, track_id: int):
        """
        Select a track by its ID.

        Args:
            track_id: Track ID to select
        """
        # O(1) lookup by track_id
        row = self._track_id_to_row.get(track_id)
        if row is None:
            return

        # Clear previous selection
        self._tracks_table.clearSelection()
        # Select the row
        self._tracks_table.selectRow(row)

    def _select_and_scroll_to_current(self):
        """Select and scroll to the currently playing track."""
        if self._current_playing_track_id is None:
            return

        # O(1) lookup by track_id
        row = self._track_id_to_row.get(self._current_playing_track_id)
        if row is None:
            return

        item = self._tracks_table.item(row, 0)
        if item:
            # Clear previous selection and select this row
            self._tracks_table.clearSelection()
            self._tracks_table.selectRow(row)
            # Scroll to the item with center positioning
            self._tracks_table.scrollToItem(item)

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """Handle item double click."""
        # Get track data from the first column
        row = item.row()
        item = self._tracks_table.item(row, 0)
        if item:
            track_data = item.data(Qt.UserRole)
            if track_data:
                if isinstance(track_data, dict) and track_data.get("type") == "cloud":
                    # Undownloaded cloud file
                    self.cloud_file_double_clicked.emit(
                        track_data.get("cloud_file_id", ""),
                        track_data.get("cloud_account_id", 0)
                    )
                elif isinstance(track_data, dict):
                    # Local track (dict format) - shouldn't happen with new code
                    track_id = track_data.get("id") or track_data.get("track_id")
                    if track_id:
                        self.track_double_clicked.emit(track_id)
                else:
                    # Local track or downloaded cloud file (int format)
                    self.track_double_clicked.emit(track_data)

    def _show_context_menu(self, pos):
        """Show context menu for tracks."""
        item = self._tracks_table.itemAt(pos)
        if not item:
            return

        # Get selected items and check if already favorited
        selected_items = self._tracks_table.selectedItems()
        track_id = None
        for it in selected_items:
            if it.column() == 0:
                track_id = it.data(Qt.UserRole)
                break

        is_favorited = False
        is_cloud = False
        is_qq_source = False  # QQ Music source
        cloud_file_id = None
        if track_id:
            if isinstance(track_id, dict):
                is_cloud = track_id.get("type") == "cloud"
                if is_cloud:
                    cloud_file_id = track_id.get("cloud_file_id")
                    is_favorited = self._favorites_service.is_favorite(cloud_file_id=cloud_file_id)
                else:
                    tid = track_id.get("id")
                    if tid:
                        is_favorited = self._favorites_service.is_favorite(track_id=tid)
                        # Check if QQ Music source
                        track = self._library_service.get_track(tid)
                        if track and hasattr(track, 'source') and track.source and track.source.value == "QQ":
                            is_qq_source = True
            else:
                is_favorited = self._favorites_service.is_favorite(track_id=track_id)
                # Check if QQ Music source
                track = self._library_service.get_track(track_id)
                if track and hasattr(track, 'source') and track.source and track.source.value == "QQ":
                    is_qq_source = True

        menu = QMenu(self)
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._CONTEXT_MENU_STYLE))

        # Play action
        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self._play_selected_track())

        # Insert to queue action (insert after current playing track)
        insert_action = menu.addAction(t("insert_to_queue"))
        insert_action.triggered.connect(lambda: self._insert_selected_to_queue())

        # Add to queue action
        add_action = menu.addAction(t("add_to_queue"))
        add_action.triggered.connect(lambda: self._add_selected_to_queue())

        menu.addSeparator()

        # Add to playlist action
        add_to_playlist_action = menu.addAction(t("add_to_playlist"))
        add_to_playlist_action.triggered.connect(lambda: self._add_to_playlist())

        # Favorite action - check if already favorited
        if self._current_view == "favorites" or is_favorited:
            favorite_action = menu.addAction(t("remove_from_favorites"))
        else:
            favorite_action = menu.addAction(t("add_to_favorites"))
        favorite_action.triggered.connect(lambda: self._toggle_favorite_selected())

        menu.addSeparator()

        # Edit media info action (disabled for QQ Music source)
        edit_action = menu.addAction(t("edit_media_info"))
        edit_action.triggered.connect(lambda: self._edit_media_info())

        # AI enhance metadata action (only for local tracks, disabled for QQ Music)
        if not is_cloud and self._config and not is_qq_source:
            ai_enabled = self._config.get_ai_enabled()
            ai_enhance_action = menu.addAction(t("ai_enhance_metadata"))
            ai_enhance_action.setEnabled(ai_enabled)
            if ai_enabled:
                ai_enhance_action.triggered.connect(lambda: self._ai_enhance_selected())
            else:
                ai_enhance_action.setToolTip(t("ai_enable_first"))

            # AcoustID identify action (only for local tracks, disabled for QQ Music)
            acoustid_enabled = self._config.get_acoustid_enabled()
            acoustid_action = menu.addAction(t("acoustid_identify"))
            acoustid_action.setEnabled(acoustid_enabled)
            if acoustid_enabled:
                acoustid_action.triggered.connect(lambda: self._acoustid_identify_selected())
            else:
                acoustid_action.setToolTip(t("acoustid_enable_first"))

        # Download cover action (only for local tracks, disabled for QQ Music)
        if not is_cloud and self._cover_service and not is_qq_source:
            download_cover_action = menu.addAction(t("download_cover_manual"))
            download_cover_action.triggered.connect(lambda: self._download_cover())

        menu.addSeparator()

        # Organize files action (only for local tracks)
        if not is_cloud:
            organize_action = menu.addAction(t("organize_files"))
            organize_action.triggered.connect(lambda: self._organize_selected_files())

        # Open file location action
        open_location_action = menu.addAction(t("open_file_location"))
        open_location_action.triggered.connect(lambda: self._open_file_location())

        menu.addSeparator()

        # Remove from library action (only removes from database, not files)
        remove_action = menu.addAction(t("remove_from_library"))
        remove_action.triggered.connect(lambda: self._remove_from_library())

        # Delete file action (deletes from database and disk) - only for local tracks
        if not is_cloud:
            delete_file_action = menu.addAction(t("delete_file"))
            delete_file_action.triggered.connect(lambda: self._delete_file())

        menu.exec_(self._tracks_table.mapToGlobal(pos))

    def _insert_selected_to_queue(self):
        """Insert selected tracks after current playing track."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            # Only process items from the first column to avoid duplicates
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    # Only add local tracks to queue for now
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if track_ids:
            self.insert_to_queue.emit(track_ids)

    def _add_selected_to_queue(self):
        """Add selected tracks to queue."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            # Only process items from the first column to avoid duplicates
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    # Only add local tracks to queue for now
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if track_ids:
            self.add_to_queue.emit(track_ids)

    def _play_selected_track(self):
        """Play the first selected track."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Find first item from first column
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") == "cloud":
                            self.cloud_file_double_clicked.emit(
                                track_data.get("cloud_file_id", ""),
                                track_data.get("cloud_account_id", 0)
                            )
                        else:
                            tid = track_data.get("id")
                            if tid:
                                self.track_double_clicked.emit(tid)
                    else:
                        self.track_double_clicked.emit(track_data)
                    break

    def _toggle_favorite_selected(self):
        """Toggle favorite status for selected tracks."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Collect rows and their track data
        rows_to_update = {}  # row -> (track_id/cloud_file_id, is_cloud)
        track_ids = []
        cloud_files = []

        for item in selected_items:
            if item.column() == 0:
                row = item.row()
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") == "cloud":
                            cloud_file_id = track_data.get("cloud_file_id")
                            cloud_account_id = track_data.get("cloud_account_id")
                            cloud_files.append({
                                "cloud_file_id": cloud_file_id,
                                "cloud_account_id": cloud_account_id,
                                "row": row
                            })
                            rows_to_update[row] = (cloud_file_id, True)
                        else:
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append({"id": tid, "row": row})
                                rows_to_update[row] = (tid, False)
                    else:
                        track_ids.append({"id": track_data, "row": row})
                        rows_to_update[row] = (track_data, False)

        if not track_ids and not cloud_files:
            return

        added_count = 0
        removed_count = 0
        bus = EventBus.instance()
        rows_to_remove = []  # Rows to remove when in favorites view

        # Process local tracks
        for track_info in track_ids:
            track_id = track_info["id"]
            row = track_info["row"]
            if self._favorites_service.is_favorite(track_id=track_id):
                self._favorites_service.remove_favorite(track_id=track_id)
                removed_count += 1
                bus.emit_favorite_change(track_id, False, is_cloud=False)
                if self._current_view == "favorites":
                    rows_to_remove.append(row)
            else:
                self._favorites_service.add_favorite(track_id=track_id)
                added_count += 1
                bus.emit_favorite_change(track_id, True, is_cloud=False)

        # Process cloud files
        for cloud_file in cloud_files:
            cloud_file_id = cloud_file.get("cloud_file_id")
            cloud_account_id = cloud_file.get("cloud_account_id")
            row = cloud_file.get("row")
            if cloud_file_id:
                if self._favorites_service.is_favorite(cloud_file_id=cloud_file_id):
                    self._favorites_service.remove_favorite(cloud_file_id=cloud_file_id)
                    removed_count += 1
                    bus.emit_favorite_change(cloud_file_id, False, is_cloud=True)
                    if self._current_view == "favorites":
                        rows_to_remove.append(row)
                else:
                    self._favorites_service.add_favorite(cloud_file_id=cloud_file_id, cloud_account_id=cloud_account_id)
                    added_count += 1
                    bus.emit_favorite_change(cloud_file_id, True, is_cloud=True)

        total_count = added_count + removed_count
        if total_count == 0:
            return

        # Update UI
        if self._current_view == "favorites" and rows_to_remove:
            # Remove rows from table (in reverse order to maintain indices)
            for row in sorted(rows_to_remove, reverse=True):
                self._tracks_table.removeRow(row)
            # Update status label
            remaining = self._tracks_table.rowCount()
            self._status_label.setText(f"{remaining} {t('favorites_word')}")
        else:
            # Update only the favorite column for affected rows
            for row, (item_id, is_cloud) in rows_to_update.items():
                if is_cloud:
                    is_fav = self._favorites_service.is_favorite(cloud_file_id=item_id)
                else:
                    is_fav = self._favorites_service.is_favorite(track_id=item_id)
                self._update_favorite_cell(row, is_fav)

        if added_count > 0 and removed_count == 0:
            message = format_count_message("added_x_tracks_to_favorites", added_count)
            MessageDialog.information(
                self,
                t("added_to_favorites"),
                message,
            )
        elif removed_count > 0 and added_count == 0:
            message = format_count_message(
                "removed_x_tracks_from_favorites", removed_count
            )
            MessageDialog.information(
                self,
                t("removed_from_favorites"),
                message,
            )
        else:
            message = t("added_x_removed_y").format(
                added=added_count, removed=removed_count
            )
            MessageDialog.information(
                self,
                t("updated_favorites"),
                message,
            )

    def _update_favorite_cell(self, row: int, is_favorite: bool):
        """Update the favorite indicator in a specific row."""
        fav_text = "★" if is_favorite else ""
        fav_item = QTableWidgetItem(fav_text)
        from system.theme import ThemeManager
        tm = ThemeManager.instance()
        fav_item.setForeground(
            QBrush(QColor(tm.current_theme.highlight if is_favorite else tm.current_theme.border))
        )
        self._tracks_table.setItem(row, 5, fav_item)

    def _add_to_playlist(self):
        """Add selected tracks to a playlist."""
        from app.bootstrap import Bootstrap
        from utils.playlist_utils import add_tracks_to_playlist

        # Get selected track IDs
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    # Only local tracks can be added to playlists
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            return

        # Get library service
        bootstrap = Bootstrap.instance()
        add_tracks_to_playlist(
            self,
            bootstrap.library_service,
            track_ids,
            "[LibraryView]"
        )

    def _edit_media_info(self):
        """Edit media information for selected tracks (batch edit support)."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Get all selected track IDs
        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    # Only local tracks can be edited
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            return

        dialog = EditMediaInfoDialog(track_ids, self._library_service, self)
        dialog.tracks_updated.connect(self._refresh_tracks_in_table)
        dialog.exec()

    def _open_file_location(self):
        """Open the file location in system file manager."""
        import platform
        import subprocess
        from pathlib import Path

        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Get first selected track
        track_data = None
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                break

        if not track_data:
            return

        # Extract track ID and check if cloud file
        if isinstance(track_data, dict):
            is_cloud = track_data.get("type") == "cloud"
            if is_cloud:
                MessageDialog.information(self, t("info"), t("cloud_lyrics_location_not_supported"))
                return
            track_id = track_data.get("id")
        else:
            track_id = track_data

        if not track_id:
            return

        track = self._library_service.get_track(track_id)
        if not track:
            return

        # Check if track has a local path (skip online/cloud tracks)
        if not track.path or not track.path.strip():
            MessageDialog.warning(self, "Error", t("no_local_file"))
            return

        file_path = Path(track.path)
        if not file_path.exists():
            MessageDialog.warning(self, "Error", t("file_not_found"))
            return

        try:
            system = platform.system()

            if system == "Windows":
                subprocess.Popen(["explorer", f"/select,{file_path}"])

            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(file_path)])

            else:
                # Linux
                # Try to select file in supported file managers
                file_managers = {
                    "nautilus": ["nautilus", "--select", str(file_path)],
                    "dolphin": ["dolphin", "--select", str(file_path)],
                    "caja": ["caja", "--select", str(file_path)],
                    "nemo": ["nemo", str(file_path)],
                }

                for fm, cmd in file_managers.items():
                    if shutil.which(fm):
                        subprocess.Popen(cmd)
                        return

                # fallback
                subprocess.Popen(["xdg-open", str(file_path.parent)])

        except Exception as e:
            logger.error(f"Failed to open file location: {e}", exc_info=True)
            MessageDialog.warning(self, "Error", f"{t('open_file_location_failed')}: {e}")

    def _remove_from_library(self):
        """Remove selected tracks from library (does not delete files)."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        cloud_file_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") == "cloud":
                            cloud_file_ids.append(track_data.get("cloud_file_id"))
                        else:
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids and not cloud_file_ids:
            return

        # format_count_message imported at top

        total_count = len(track_ids) + len(cloud_file_ids)
        confirm_message = format_count_message("remove_from_library_confirm", total_count)

        reply = MessageDialog.question(
            self,
            t("remove_from_library"),
            confirm_message,
            Yes | No,
        )

        if reply != Yes:
            return

        removed_count = 0
        # Remove local tracks in batch for better performance
        if track_ids:
            removed_count = self._library_service.delete_tracks(track_ids)

        # Remove cloud file favorites
        for cloud_file_id in cloud_file_ids:
            if cloud_file_id:
                self._favorites_service.remove_favorite(cloud_file_id=cloud_file_id)
                removed_count += 1

        if removed_count > 0:
            success_message = format_count_message(
                "remove_from_library_success", removed_count
            )
            MessageDialog.information(
                self,
                t("remove_from_library"),
                success_message,
            )
            self.refresh()

    def _delete_file(self):
        """Delete selected tracks from library and remove files from disk."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        # Only delete local tracks, not cloud tracks
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            return

        # Get track info for confirmation and later updates
        track_info_list = []
        for track_id in track_ids:
            track = self._library_service.get_track(track_id)
            if track:
                track_info_list.append((track_id, track))

        if not track_info_list:
            return

        # Show confirmation dialog with file paths
        total_count = len(track_info_list)
        confirm_message = format_count_message("delete_file_confirm", total_count)

        reply = MessageDialog.question(
            self,
            t("delete_file"),
            confirm_message,
            Yes | No,
        )

        if reply != Yes:
            return

        # Delete files
        deleted_count = 0
        failed_count = 0
        for track_id, track in track_info_list:
            try:
                # Remove from database first
                if self._library_service.delete_track(track_id):
                    # Try to delete the file from disk (skip if no local path - online tracks)
                    try:
                        # Skip if no local path (online/cloud tracks)
                        if not track.path or not track.path.strip():
                            # No local file to delete, but we removed it from DB
                            deleted_count += 1
                            continue

                        path_obj = Path(track.path)
                        if path_obj.exists():
                            # Delete all lyrics files (.lrc, .yrc, .qrc) if they exist
                            for ext in ['.lrc', '.yrc', '.qrc']:
                                lyrics_path = path_obj.with_suffix(ext)
                                if lyrics_path.exists():
                                    lyrics_path.unlink()

                            # Delete the audio file
                            path_obj.unlink()
                            deleted_count += 1
                        else:
                            # File doesn't exist, but we removed it from DB
                            deleted_count += 1
                    except Exception as e:
                        logger.error(f"Error deleting file {track.path}: {e}")
                        failed_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error deleting track {track_id}: {e}")
                failed_count += 1

        # Show result message
        if deleted_count > 0:
            if failed_count > 0:
                MessageDialog.warning(
                    self,
                    t("warning"),
                    f"{t('delete_file_success')} ({deleted_count})\n{t('delete_file_failed')} ({failed_count})",
                )
            else:
                success_message = format_count_message(
                    "delete_file_success", deleted_count
                )
                MessageDialog.information(
                    self,
                    t("success"),
                    success_message,
                )
            self.refresh()

    def _ai_enhance_selected(self):
        """Enhance metadata for selected tracks using AI (batch mode)."""
        if not self._config:
            MessageDialog.warning(self, t("warning"), t("ai_config_not_found"))
            return

        if not self._config.get_ai_enabled():
            MessageDialog.warning(self, t("warning"), t("ai_enable_first"))
            return

        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Collect track IDs
        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            MessageDialog.information(self, t("info"), t("ai_no_tracks_selected"))
            return

        # Get AI config
        base_url = self._config.get_ai_base_url()
        api_key = self._config.get_ai_api_key()
        model = self._config.get_ai_model()

        # Create progress dialog
        progress_dialog = ProgressDialog(
            t("ai_enhance_metadata"), t("ai_enhancing"), t("cancel"), 0, len(track_ids), self
        )

        # Create and start worker
        worker = AIEnhanceWorker(track_ids, self._library_service, base_url, api_key, model)

        def on_progress(current, total):
            progress_dialog.setValue(current)
            progress_dialog.setLabelText(f"{t('ai_enhancing')} {current}/{total}")

        def on_finished(enhanced_ids, enhanced_count, failed_count):
            progress_dialog.close()
            message = t("ai_enhance_result").format(enhanced=enhanced_count, failed=failed_count)
            MessageDialog.information(self, t("ai_enhance_metadata"), message)
            if enhanced_ids:
                self._refresh_tracks_in_table(enhanced_ids)

        def on_cancel():
            worker.cancel()
            worker.quit()
            worker.wait()

        worker.progress.connect(on_progress)
        worker.finished_signal.connect(on_finished)
        progress_dialog.canceled.connect(on_cancel)

        progress_dialog.show()
        worker.start()

    def _refresh_tracks_in_table(self, track_ids: List[int]):
        """
        Refresh specific tracks in the table without reloading all data.

        Args:
            track_ids: List of track IDs to refresh
        """
        # format_duration imported at top
        from PySide6.QtGui import QBrush, QColor

        # Use O(1) lookup for each track_id
        for track_id in track_ids:
            row = self._track_id_to_row.get(track_id)
            if row is None:
                continue

            # Get updated track from database
            track = self._library_service.get_track(track_id)
            if not track:
                continue

            title_item = self._tracks_table.item(row, 1)
            if not title_item:
                continue

            # Update title
            is_currently_playing = track.id == self._current_playing_track_id
            icon_prefix = ""
            if is_currently_playing:
                if self._player.engine.state == PlaybackState.PLAYING:
                    icon_prefix = "▶️ "
                else:
                    icon_prefix = "⏸️ "

            title_text = f"{icon_prefix}{track.title or track.path.split('/')[-1]}"
            title_item.setText(title_text)
            from system.theme import ThemeManager
            tm = ThemeManager.instance()
            title_item.setForeground(
                QBrush(QColor(tm.current_theme.highlight if is_currently_playing else tm.current_theme.text)))

            if is_currently_playing:
                font = title_item.font()
                font.setBold(True)
                title_item.setFont(font)
            else:
                font = title_item.font()
                font.setBold(False)
                title_item.setFont(font)

            # Update artist
            artist_item = self._tracks_table.item(row, 2)
            if artist_item:
                artist_item.setText(track.artist or t("unknown"))

            # Update album
            album_item = self._tracks_table.item(row, 3)
            if album_item:
                album_item.setText(track.album or t("unknown"))

            logger.debug(f"Refreshed row {row} for track {track_id}")

    def _acoustid_identify_selected(self):
        """Identify selected tracks using AcoustID fingerprinting."""
        if not self._config:
            MessageDialog.warning(self, t("warning"), t("ai_config_not_found"))
            return

        if not self._config.get_acoustid_enabled():
            MessageDialog.warning(self, t("warning"), t("acoustid_enable_first"))
            return

        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Collect track IDs
        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            MessageDialog.information(self, t("info"), t("ai_no_tracks_selected"))
            return

        # Get AcoustID API key
        api_key = self._config.get_acoustid_api_key()
        if not api_key:
            MessageDialog.warning(self, t("warning"), t("acoustid_api_key_required"))
            return

        # Create progress dialog
        progress_dialog = ProgressDialog(
            t("acoustid_identify"), t("acoustid_identifying"), t("cancel"), 0, len(track_ids), self
        )

        # Create and start worker
        worker = AcoustIDWorker(track_ids, self._library_service, api_key)

        def on_progress(current, total, track_id):
            progress_dialog.setValue(current)
            progress_dialog.setLabelText(f"{t('acoustid_identifying')} {current + 1}/{total}")

        def on_finished(identified_ids, success_count, failed_count):
            progress_dialog.close()
            message = t("acoustid_result").format(identified=success_count, failed=failed_count)
            MessageDialog.information(self, t("acoustid_identify"), message)
            if identified_ids:
                self._refresh_tracks_in_table(identified_ids)

        def on_cancel():
            worker.cancel()
            worker.quit()
            worker.wait()

        worker.progress.connect(on_progress)
        worker.finished_signal.connect(on_finished)
        progress_dialog.canceled.connect(on_cancel)

        progress_dialog.show()
        worker.start()

    def _download_cover(self):
        """Download cover art for selected tracks."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Get selected tracks
        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            return

        # Get track objects
        tracks = []
        for track_id in track_ids:
            track = self._library_service.get_track(track_id)
            if track:
                tracks.append(track)

        if not tracks:
            return

        # Show cover download dialog
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.track_search_strategy import TrackSearchStrategy
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        strategy = TrackSearchStrategy(
            tracks,
            bootstrap.track_repo,
            bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, self._cover_service, self)
        dialog.exec()

    def _organize_selected_files(self):
        """Organize selected files into structured directories."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Get selected tracks (only local tracks)
        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_data = item.data(Qt.UserRole)
                if track_data:
                    if isinstance(track_data, dict):
                        if track_data.get("type") != "cloud":
                            tid = track_data.get("id")
                            if tid:
                                track_ids.append(tid)
                    else:
                        track_ids.append(track_data)

        if not track_ids:
            return

        # Get track objects
        tracks = []
        for track_id in track_ids:
            track = self._library_service.get_track(track_id)
            if track:
                tracks.append(track)

        if not tracks:
            return

        # Get file organization service from Bootstrap
        from app import Application
        app = Application.instance()
        if not app or not app.bootstrap or not hasattr(app.bootstrap, 'file_org_service'):
            MessageDialog.warning(
                self,
                t("error"),
                t("file_org_service_not_available")
            )
            return

        # Show organize files dialog
        from ui.dialogs.organize_files_dialog import OrganizeFilesDialog
        dialog = OrganizeFilesDialog(tracks, app.bootstrap.file_org_service, self._config, self)
        if dialog.exec() == QDialog.Accepted:
            # Refresh the view after organization
            self.refresh()

    def _on_tracks_organized(self, result: dict):
        """Handle file organization completion event."""
        success = result.get('success', 0)
        failed = result.get('failed', 0)
        if success > 0:
            # Refresh the view to show updated paths
            self.refresh()

    def _load_view_mode(self):
        """Load view mode preference from config."""
        view_mode = self._config.get("view/history_view_mode", "table")
        self._update_view_toggle_icon()

    def _toggle_history_view_mode(self):
        """Toggle between table and list view for history."""
        current_mode = self._config.get("view/history_view_mode", "table")
        new_mode = "list" if current_mode == "table" else "table"
        self._config.set("view/history_view_mode", new_mode)
        self._update_view_toggle_icon()

        # Reload history with new view mode
        if self._current_view == "history":
            self._load_history()

    def _update_view_toggle_icon(self):
        """Update view toggle button icon."""
        view_mode = self._config.get("view/history_view_mode", "table")
        theme = ThemeManager.instance().current_theme

        if view_mode == "list":
            icon = get_icon(IconName.GRID, theme.text_secondary)
            self._view_toggle_btn.setToolTip(t("switch_to_table_view"))
        else:
            icon = get_icon(IconName.LIST, theme.text_secondary)
            self._view_toggle_btn.setToolTip(t("switch_to_list_view"))

        self._view_toggle_btn.setIcon(icon)

    def _on_history_track_activated(self, track: Track):
        """Handle track activation from history list view."""
        from domain import PlaylistItem
        item = PlaylistItem(track_id=track.id)
        self._player.engine.set_playlist([item])
        self._player.engine.play()

    def _on_history_play_requested(self, tracks: list):
        """Play requested tracks from history list view."""
        if not tracks:
            return
        from domain import PlaylistItem
        items = [PlaylistItem(track_id=track.id) for track in tracks if track.id]
        if items:
            self._player.engine.set_playlist(items)
            self._player.engine.play()

    def _on_history_insert_to_queue(self, tracks: list):
        """Insert tracks after current in queue."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self.insert_to_queue.emit(track_ids)

    def _on_history_add_to_queue(self, tracks: list):
        """Add tracks to queue."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self.add_to_queue.emit(track_ids)

    def _on_history_add_to_playlist(self, tracks: list):
        """Add tracks to playlist."""
        from utils.playlist_utils import add_tracks_to_playlist
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            add_tracks_to_playlist(self, self._library_service, track_ids, "[HistoryListView]")

    def _on_history_favorites_toggle(self, tracks: list, all_favorited: bool):
        """Toggle favorites for tracks from history."""
        bus = EventBus.instance()
        for track in tracks:
            if not track.id:
                continue
            if all_favorited:
                self._favorites_service.remove_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, False, is_cloud=False)
            else:
                self._favorites_service.add_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, True, is_cloud=False)

    def _on_history_edit_info(self, track):
        """Edit media info for a history track."""
        if not track or not track.id:
            return
        dialog = EditMediaInfoDialog([track.id], self._library_service, self)
        dialog.tracks_updated.connect(self._refresh_tracks_in_table)
        dialog.exec()

    def _on_history_download_cover(self, track):
        """Download cover for a history track."""
        if not track or not track.id:
            return
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.track_search_strategy import TrackSearchStrategy
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        strategy = TrackSearchStrategy(
            [track], bootstrap.track_repo, bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, self._cover_service, self)
        dialog.exec()

    def _on_history_open_file_location(self, track):
        """Open file location for a history track."""
        if not track or not track.path or not track.path.strip():
            MessageDialog.warning(self, "Error", t("no_local_file"))
            return
        file_path = Path(track.path)
        if not file_path.exists():
            MessageDialog.warning(self, "Error", t("file_not_found"))
            return
        import platform, subprocess
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.Popen(["explorer", f"/select,{file_path}"])
            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(file_path)])
            else:
                file_managers = {
                    "nautilus": ["nautilus", "--select", str(file_path)],
                    "dolphin": ["dolphin", "--select", str(file_path)],
                    "caja": ["caja", "--select", str(file_path)],
                    "nemo": ["nemo", str(file_path)],
                }
                for fm, cmd in file_managers.items():
                    if shutil.which(fm):
                        subprocess.Popen(cmd)
                        return
                subprocess.Popen(["xdg-open", str(file_path.parent)])
        except Exception as e:
            logger.error(f"Failed to open file location: {e}", exc_info=True)
            MessageDialog.warning(self, "Error", f"{t('open_file_location_failed')}: {e}")

    def _on_history_remove_from_library(self, tracks: list):
        """Remove tracks from library."""
        track_ids = [t.id for t in tracks if t.id]
        if not track_ids:
            return
        confirm_message = format_count_message("remove_from_library_confirm", len(track_ids))
        reply = MessageDialog.question(
            self, t("remove_from_library"), confirm_message, Yes | No)
        if reply != Yes:
            return
        removed_count = self._library_service.delete_tracks(track_ids)
        if removed_count > 0:
            success_message = format_count_message("remove_from_library_success", removed_count)
            MessageDialog.information(self, t("remove_from_library"), success_message)
            self.refresh()

    def _on_history_delete_file(self, tracks: list):
        """Delete files from disk and library."""
        if not tracks:
            return
        confirm_message = format_count_message("delete_file_confirm", len(tracks))
        reply = MessageDialog.question(
            self, t("delete_file"), confirm_message, Yes | No)
        if reply != Yes:
            return
        import os
        for track in tracks:
            if not track or not track.id:
                continue
            if track.path and os.path.exists(track.path):
                os.remove(track.path)
            self._library_service.delete_track(track.id)
        self.refresh()

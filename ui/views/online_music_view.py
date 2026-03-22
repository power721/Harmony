"""
Online music view for searching and browsing online music.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTabWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QStackedWidget,
    QAbstractItemView,
    QMenu,
    QMessageBox,
    QProgressBar,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QFrame,
    QCompleter,
    QListView,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QStringListModel
from PySide6.QtGui import QCursor, QColor, QBrush, QAction


class CustomQCompleter(QCompleter):
    """自定义QCompleter用于搜索建议."""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置列表样式
        self.popup().setStyleSheet("""
            QListView {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
                color: #e0e0e0;
                selection-background-color: #1db954;
                selection-color: #ffffff;
                outline: none;
            }
            QListView::item {
                padding: 8px 12px;
                border-bottom: 1px solid #3a3a3a;
            }
            QListView::item:selected {
                background-color: #1db954;
                color: #ffffff;
            }
            QListView::item:hover {
                background-color: #333;
            }
        """)

from domain.online_music import (
    OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist,
    SearchResult, SearchType
)
from services.online import OnlineMusicService, OnlineDownloadService
from system.i18n import t
from system.event_bus import EventBus
from ui.icons import IconName, get_icon
from ui.views.online_grid_view import OnlineGridView
from ui.views.online_detail_view import OnlineDetailView
from utils import format_duration

logger = logging.getLogger(__name__)


class SearchWorker(QThread):
    """Background worker for searching."""

    search_completed = Signal(object)  # SearchResult
    search_failed = Signal(str)

    def __init__(self, service: OnlineMusicService, keyword: str,
                 search_type: str, page: int = 1, page_size: int = 50):
        super().__init__()
        self._service = service
        self._keyword = keyword
        self._search_type = search_type
        self._page = page
        self._page_size = page_size

    def run(self):
        try:
            result = self._service.search(
                self._keyword,
                self._search_type,
                self._page,
                self._page_size
            )
            self.search_completed.emit(result)
        except Exception as e:
            self.search_failed.emit(str(e))


class TopListWorker(QThread):
    """Background worker for loading top lists."""

    top_list_loaded = Signal(list)  # List of top lists
    top_songs_loaded = Signal(int, list)  # (top_id, list of tracks)

    def __init__(self, service: OnlineMusicService, top_id: Optional[int] = None):
        super().__init__()
        self._service = service
        self._top_id = top_id

    def run(self):
        try:
            if self._top_id is None:
                # Get list of top lists
                top_lists = self._service.get_top_lists()
                self.top_list_loaded.emit(top_lists)
            else:
                # Get songs for specific top list
                songs = self._service.get_top_list_songs(self._top_id)
                self.top_songs_loaded.emit(self._top_id, songs)
        except Exception as e:
            logger.error(f"Failed to load top list: {e}")


class CompletionWorker(QThread):
    """Background worker for search completion."""

    completion_ready = Signal(list)  # List of completion suggestions

    def __init__(self, qqmusic_service, keyword: str):
        super().__init__()
        self._qqmusic_service = qqmusic_service
        self._keyword = keyword

    def run(self):
        try:
            # Try to get completion suggestions
            if self._qqmusic_service:
                suggestions = self._qqmusic_service.complete(self._keyword)
                self.completion_ready.emit(suggestions)
            else:
                # No QQ Music service configured
                logger.debug("No QQ Music service available for completion")
                self.completion_ready.emit([])
        except Exception as e:
            logger.error(f"Search completion failed: {e}")
            self.completion_ready.emit([])


class OnlineMusicView(QWidget):
    """View for searching and browsing online music."""

    # Signals
    play_online_track = Signal(str, str, object)  # (song_mid, local_path, metadata_dict)
    insert_to_queue = Signal(str, object)  # (song_mid, metadata_dict)
    add_to_queue = Signal(str, object)  # (song_mid, metadata_dict)
    play_online_tracks = Signal(int, list)  # (start_index, list of (song_mid, metadata_dict))

    def __init__(
        self,
        config_manager=None,
        qqmusic_service=None,
        parent=None
    ):
        super().__init__(parent)

        self._config = config_manager
        self._qqmusic_service = qqmusic_service

        # Create services
        self._service = OnlineMusicService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service
        )
        self._download_service = OnlineDownloadService(
            config_manager=config_manager,
            qqmusic_service=qqmusic_service,
            online_music_service=self._service
        )

        # State
        self._current_search_type = SearchType.SONG
        self._current_page = 1
        self._current_keyword = ""
        self._current_result: Optional[SearchResult] = None
        self._current_tracks: List[OnlineTrack] = []
        self._search_worker: Optional[SearchWorker] = None
        self._top_list_worker: Optional[TopListWorker] = None
        self._completion_worker: Optional[CompletionWorker] = None
        self._completion_timer: Optional[QTimer] = None
        self._selected_top_id: Optional[int] = None
        self._top_lists_loaded = False  # Track if top lists have been loaded
        self._is_top_list_view = True  # True when viewing top list, False when viewing search results

        # State for non-song search (load more)
        self._grid_page = 1  # Current page for grid views (singer/album/playlist)
        self._grid_total = 0  # Total results for current grid search
        self._grid_page_size = 30  # Page size for grid views

        # Event bus
        self._event_bus = EventBus.instance()

        # Setup completion timer
        self._completion_timer = QTimer()
        self._completion_timer.setSingleShot(True)
        self._completion_timer.timeout.connect(self._trigger_completion)

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(10)

        # Header with login status
        header = self._create_header()
        layout.addWidget(header)

        # Search bar
        search_bar = self._create_search_bar()
        layout.addWidget(search_bar)

        # Type tabs (hidden by default)
        self._tabs = self._create_type_tabs()
        self._tabs.hide()
        layout.addWidget(self._tabs)

        # Content area
        self._stack = QStackedWidget()

        # Top lists page (default)
        self._top_list_page = self._create_top_list_page()
        self._stack.addWidget(self._top_list_page)

        # Search results page
        self._results_page = self._create_results_page()
        self._stack.addWidget(self._results_page)

        # Detail view page
        self._detail_view = OnlineDetailView(
            config_manager=self._config,
            qqmusic_service=self._qqmusic_service,
            parent=self
        )
        self._detail_view.back_requested.connect(self._on_back_from_detail)
        # Connect play_all and add_all_to_queue signals
        self._detail_view.play_all.connect(self._on_play_all_from_detail)
        self._detail_view.insert_all_to_queue.connect(self._on_insert_all_to_queue_from_detail)
        self._detail_view.add_all_to_queue.connect(self._on_add_all_to_queue_from_detail)
        self._stack.addWidget(self._detail_view)

        layout.addWidget(self._stack)

        # Apply styles
        self._apply_styles()

    def showEvent(self, event):
        """Handle show event - load top lists on first display."""
        super().showEvent(event)
        if not self._top_lists_loaded:
            self._top_lists_loaded = True
            self._load_top_lists()

    def _create_header(self) -> QWidget:
        """Create header with QQ Music login status."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        self._online_music_title = QLabel(t("online_music"))
        self._online_music_title.setStyleSheet("""
            color: #1db954;
            font-size: 24px;
            font-weight: bold;
        """)
        layout.addWidget(self._online_music_title)

        layout.addStretch()

        # QQ Music login status
        self._login_status_label = QLabel()
        self._login_status_label.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(self._login_status_label)

        # Login/Logout button
        self._login_btn = QPushButton()
        self._login_btn.setCursor(Qt.PointingHandCursor)
        self._login_btn.clicked.connect(self._on_login_clicked)
        layout.addWidget(self._login_btn)

        self._update_login_status()

        return widget

    def _create_search_bar(self) -> QWidget:
        """Create search bar."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Search input with built-in clear button
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("search_online_music"))
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.setFixedHeight(50)
        self._search_input.setClearButtonEnabled(True)

        # Setup completer for search suggestions
        self._completer = CustomQCompleter(self)
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        # Use PopupCompletion mode to show all matching suggestions
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        self._completer.setMaxVisibleItems(10)
        # Set filter mode to show anything that contains the typed text
        self._completer.setFilterMode(Qt.MatchContains)
        self._search_input.setCompleter(self._completer)

        # Connect completion activation
        self._completer.activated.connect(self._on_completion_selected)

        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 2px solid #3a3a3a;
                border-radius: 25px;
                padding: 10px 20px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #1db954;
                background-color: #2d2d2d;
            }
            QLineEdit::placeholder {
                color: #808080;
            }
            QLineEdit::clear-button {
                subcontrol-origin: padding;
                subcontrol-position: right;
                width: 20px;
                height: 20px;
                margin-right: 10px;
                border-radius: 10px;
                background-color: #505050;
            }
            QLineEdit::clear-button:hover {
                background-color: #606060;
                border: 1px solid #707070;
                cursor: pointer;
            }
            QLineEdit::clear-button:pressed {
                background-color: #404040;
            }
        """)
        layout.addWidget(self._search_input, 1)

        # Search button
        self._search_btn = QPushButton(t("search"))
        self._search_btn.setCursor(Qt.PointingHandCursor)
        self._search_btn.clicked.connect(self._on_search)
        layout.addWidget(self._search_btn)

        return widget

    def _create_type_tabs(self) -> QTabBar:
        """Create search type tabs."""
        tabs = QTabBar()
        tabs.setObjectName("searchTypeTabs")
        tabs.setExpanding(False)

        # Add tabs
        tabs.addTab(t("songs"))
        tabs.addTab(t("singers"))
        tabs.addTab(t("albums"))
        tabs.addTab(t("playlists"))

        tabs.currentChanged.connect(self._on_tab_changed)
        tabs.setStyleSheet("""
            QTabBar::tab {
                background: transparent;
                color: #808080;
                padding: 8px 20px;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                color: #1db954;
                border-bottom: 2px solid #1db954;
            }
            QTabBar::tab:hover {
                color: #1db954;
            }
        """)

        return tabs

    def _create_top_list_page(self) -> QWidget:
        """Create top list page (default view)."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Left: list of top lists
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self._rankings_title = QLabel(t("rankings"))
        self._rankings_title.setStyleSheet("color: #1db954; font-size: 16px; font-weight: bold;")
        left_layout.addWidget(self._rankings_title)

        self._top_list_list = QListWidget()
        self._top_list_list.setObjectName("topListList")
        self._top_list_list.currentRowChanged.connect(self._on_top_list_selected)
        left_layout.addWidget(self._top_list_list)

        layout.addWidget(left_widget, 1)

        # Right: songs in selected top list
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        self._top_list_title = QLabel(t("select_ranking"))
        self._top_list_title.setStyleSheet("color: #1db954; font-size: 16px; font-weight: bold;")
        right_layout.addWidget(self._top_list_title)

        self._top_songs_table = self._create_songs_table()
        right_layout.addWidget(self._top_songs_table)

        layout.addWidget(right_widget, 3)

        return widget

    def _create_results_page(self) -> QWidget:
        """Create search results page with different views for each type."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Results info
        self._results_info = QLabel()
        self._results_info.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(self._results_info)

        # Stacked widget for different result types
        self._results_stack = QStackedWidget()

        # Songs page - table view
        self._songs_page = self._create_songs_result_page()
        self._results_stack.addWidget(self._songs_page)

        # Singers page - grid view with circular avatars
        self._singers_page = OnlineGridView(data_type="singer", parent=self)
        self._singers_page.item_clicked.connect(self._on_artist_clicked)
        self._singers_page.load_more_requested.connect(self._on_load_more_artists)
        self._results_stack.addWidget(self._singers_page)

        # Albums page - grid view with rounded covers
        self._albums_page = OnlineGridView(data_type="album", parent=self)
        self._albums_page.item_clicked.connect(self._on_album_clicked)
        self._albums_page.load_more_requested.connect(self._on_load_more_albums)
        self._results_stack.addWidget(self._albums_page)

        # Playlists page - grid view with rounded covers
        self._playlists_page = OnlineGridView(data_type="playlist", parent=self)
        self._playlists_page.item_clicked.connect(self._on_playlist_clicked)
        self._playlists_page.load_more_requested.connect(self._on_load_more_playlists)
        self._results_stack.addWidget(self._playlists_page)

        layout.addWidget(self._results_stack)

        # Pagination (only for songs)
        pagination = self._create_pagination()
        layout.addWidget(pagination)

        return widget

    def _create_songs_result_page(self) -> QWidget:
        """Create songs result page with table."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Results table
        self._results_table = self._create_songs_table()
        layout.addWidget(self._results_table)

        return widget

    def _create_songs_table(self) -> QTableWidget:
        """Create songs table widget."""
        table = QTableWidget()
        table.setObjectName("songsTable")
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
        table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        table.setAlternatingRowColors(True)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.doubleClicked.connect(self._on_track_double_clicked)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(self._show_track_context_menu)

        # Same style as library view
        table.setStyleSheet("""
            QTableWidget#songsTable {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget#songsTable::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            QTableWidget#songsTable::item:alternate {
                background-color: #252525;
            }
            QTableWidget#songsTable::item:!alternate {
                background-color: #1e1e1e;
            }
            QTableWidget#songsTable::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget#songsTable::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget#songsTable::item:selected:alternate {
                background-color: #1ed760;
            }
            QTableWidget#songsTable::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget#songsTable::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#songsTable::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget#songsTable:focus {
                outline: none;
                border: none;
            }
            QTableWidget#songsTable QHeaderView::section {
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
            QTableWidget#songsTable QTableCornerButton::section {
                background-color: #2a2a2a;
                border: none;
                border-right: 1px solid #3a3a3a;
                border-bottom: 2px solid #1db954;
            }
            QTableWidget#songsTable QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QTableWidget#songsTable QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget#songsTable QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QTableWidget#songsTable QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border-radius: 6px;
            }
            QTableWidget#songsTable QScrollBar::handle:horizontal {
                background-color: #404040;
                border-radius: 6px;
                min-width: 40px;
            }
            QTableWidget#songsTable QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            QTableWidget#songsTable QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
                width: 0px;
            }
        """)

        return table

    def _create_pagination(self) -> QWidget:
        """Create pagination widget."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch()

        self._prev_btn = QPushButton("← " + t("previous_page"))
        self._prev_btn.setFixedHeight(36)
        self._prev_btn.setCursor(Qt.PointingHandCursor)
        self._prev_btn.clicked.connect(self._on_prev_page)
        layout.addWidget(self._prev_btn)

        self._page_label = QLabel("1")
        self._page_label.setStyleSheet("color: #808080; padding: 0 10px;")
        layout.addWidget(self._page_label)

        self._next_btn = QPushButton(t("next_page") + " →")
        self._next_btn.setFixedHeight(36)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_btn)

        layout.addStretch()

        return widget

    def _apply_styles(self):
        """Apply styles to the view."""
        self.setStyleSheet("""
            QPushButton {
                background: #333;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #444;
            }
            QPushButton:pressed {
                background: #555;
            }
            QListWidget {
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 10px;
                color: white;
            }
            QListWidget::item:selected {
                background: #1db954;
                color: white;
            }
            QListWidget::item:hover {
                background: #2a2a2a;
            }
        """)

    def _refresh_qqmusic_service(self):
        """Refresh QQ Music service with current credentials."""
        import json
        from services.cloud.qqmusic.qqmusic_service import QQMusicService

        qqmusic_credential = self._config.get("qqmusic.credential") if self._config else None
        if qqmusic_credential:
            try:
                cred_dict = json.loads(qqmusic_credential) if isinstance(qqmusic_credential, str) else qqmusic_credential
                self._qqmusic_service = QQMusicService(cred_dict)
                # Update service reference
                self._service._qqmusic = self._qqmusic_service
                # Update download service reference too
                self._download_service._qqmusic = self._qqmusic_service
                logger.debug("QQ Music service refreshed with credentials")
            except Exception as e:
                logger.error(f"Failed to refresh QQ Music service: {e}")

    def _update_login_status(self):
        """Update QQ Music login status display."""
        has_credential = self._service._has_qqmusic_credential()

        if has_credential:
            # Refresh QQ Music service with new credentials
            self._refresh_qqmusic_service()

            # Get user info if possible
            credential = self._config.get("qqmusic.credential") if self._config else None
            nick = ""
            if credential:
                try:
                    import json
                    cred_dict = json.loads(credential) if isinstance(credential, str) else credential
                    nick = cred_dict.get("nick", "") if isinstance(cred_dict, dict) else ""
                except Exception:
                    pass

            if nick:
                self._login_status_label.setText(t("qqmusic_logged_in_as").format(nick=nick))
            else:
                self._login_status_label.setText(t("qqmusic_logged_in"))

            self._login_btn.setText(t("logout"))
        else:
            self._login_status_label.setText(t("qqmusic_not_logged_in"))
            self._login_btn.setText(t("login"))

    def _on_login_clicked(self):
        """Handle login button click."""
        if self._service._has_qqmusic_credential():
            # Logout
            if self._config:
                self._config.delete("qqmusic.credential")
                self._config.delete("qqmusic.musicid")
                self._config.delete("qqmusic.musickey")
                self._config.delete("qqmusic.login_type")
            self._update_login_status()
            QMessageBox.information(self, t("logout"), t("logout_success"))
        else:
            # Show login dialog
            self._show_login_dialog()

    def _show_login_dialog(self):
        """Show QQ Music login dialog."""
        from ui.dialogs.qqmusic_qr_login_dialog import QQMusicQRLoginDialog

        dialog = QQMusicQRLoginDialog(self)
        if dialog.exec():
            # Dialog already saved credentials and refreshed the client
            self._update_login_status()

    def _on_search(self):
        """Handle search."""
        keyword = self._search_input.text().strip()
        if not keyword:
            return

        self._current_keyword = keyword
        self._current_page = 1
        self._grid_page = 1  # Reset grid page for new search
        self._tabs.show()

        # Immediately switch to results page and show searching state
        self._stack.setCurrentWidget(self._results_page)
        self._results_info.setText(t("searching"))
        self._results_table.setRowCount(0)
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)

        self._do_search()

    def _on_search_text_changed(self, text: str):
        """Handle search text change - show top lists when cleared."""
        if not text and self._current_keyword:
            # Text was cleared, go back to top lists
            self._current_keyword = ""
            self._current_page = 1
            self._grid_page = 1
            self._grid_total = 0
            # Don't clear _current_tracks - keep the top list songs that were already loaded
            self._tabs.hide()
            # Clear grid views
            self._singers_page.clear()
            self._albums_page.clear()
            self._playlists_page.clear()
            # Switch to top list page
            self._stack.setCurrentWidget(self._top_list_page)
        elif text and len(text) >= 1 and self._qqmusic_service:
            # Trigger completion after delay (debounce)
            self._completion_timer.start(300)  # 300ms delay

    def _trigger_completion(self):
        """Trigger search completion request."""
        keyword = self._search_input.text().strip()
        if not keyword or len(keyword) < 1:
            return

        # Cancel previous completion worker
        if self._completion_worker and self._completion_worker.isRunning():
            self._completion_worker.terminate()

        # Note: Completion API works without login too
        self._completion_worker = CompletionWorker(self._qqmusic_service, keyword)
        self._completion_worker.completion_ready.connect(self._on_completion_ready)
        self._completion_worker.start()

    def _on_completion_ready(self, suggestions: List[Dict[str, Any]]):
        """Handle completion suggestions ready."""
        if not suggestions:
            return

        # Extract suggestion hints (the text to display)
        suggestion_texts = [s.get('hint', '') for s in suggestions if s.get('hint')]

        logger.info(f"Search completion: {len(suggestion_texts)} suggestions - {suggestion_texts[:3]}")

        # Update completer model
        model = QStringListModel(suggestion_texts)
        self._completer.setModel(model)

        # Set the completion prefix to current text so matches work correctly
        current_text = self._search_input.text()
        self._completer.setCompletionPrefix(current_text)

        # Show completion popup - ensure the input still has focus
        if suggestion_texts and self._search_input.hasFocus():
            self._completer.complete()
        elif suggestion_texts:
            # Input doesn't have focus, don't show popup
            logger.debug("Search input lost focus, not showing completion")

    def _on_completion_selected(self, text: str):
        """Handle completion selection."""
        # Set the selected text and trigger search
        self._search_input.setText(text)
        self._on_search()

    def _do_search(self):
        """Execute search."""
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.terminate()
            self._search_worker = None

        self._search_worker = SearchWorker(
            self._service,
            self._current_keyword,
            self._current_search_type,
            self._current_page,
            30
        )
        self._search_worker.search_completed.connect(self._on_search_completed)
        self._search_worker.search_failed.connect(self._on_search_failed)
        self._search_worker.start()

    def _on_search_completed(self, result: SearchResult):
        """Handle search completion."""
        self._current_result = result
        self._stack.setCurrentWidget(self._results_page)
        self._is_top_list_view = False  # Now viewing search results

        if self._current_search_type == SearchType.SONG:
            self._current_tracks = result.tracks
            self._display_tracks(result.tracks)
            self._results_stack.setCurrentWidget(self._songs_page)
        elif self._current_search_type == SearchType.SINGER:
            self._grid_total = result.total
            self._display_artists(result.artists, is_append=False)
            self._results_stack.setCurrentWidget(self._singers_page)
        elif self._current_search_type == SearchType.ALBUM:
            self._grid_total = result.total
            self._display_albums(result.albums, is_append=False)
            self._results_stack.setCurrentWidget(self._albums_page)
        elif self._current_search_type == SearchType.PLAYLIST:
            self._grid_total = result.total
            self._display_playlists(result.playlists, is_append=False)
            self._results_stack.setCurrentWidget(self._playlists_page)

        # Update results info
        self._results_info.setText(
            f"{t('search_result')}: {result.total} {t('results')}"
        )

        # Update pagination (only for songs)
        self._page_label.setText(str(self._current_page))
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(len(result.tracks) == 30)

        # Hide pagination for non-song results
        if self._current_search_type != SearchType.SONG:
            self._prev_btn.parentWidget().hide()
        else:
            self._prev_btn.parentWidget().show()

    def _on_search_failed(self, error: str):
        """Handle search failure."""
        logger.error(f"Search failed: {error}")
        QMessageBox.warning(self, t("error"), t("search_failed") + f": {error}")

    def _display_tracks(self, tracks: List[OnlineTrack]):
        """Display tracks in table."""
        self._results_table.setRowCount(len(tracks))
        self._results_table.setColumnCount(5)

        for i, track in enumerate(tracks):
            # Index
            self._results_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            # Title
            title_item = QTableWidgetItem(track.title)
            if track.is_vip:
                title_item.setForeground(QBrush(QColor("#ffd700")))
            self._results_table.setItem(i, 1, title_item)

            # Artist
            self._results_table.setItem(i, 2, QTableWidgetItem(track.singer_name))

            # Album
            self._results_table.setItem(i, 3, QTableWidgetItem(track.album_name))

            # Duration
            duration_str = format_duration(track.duration) if track.duration else ""
            self._results_table.setItem(i, 4, QTableWidgetItem(duration_str))

    def _display_artists(self, artists: List[OnlineArtist], is_append: bool = False):
        """Display artists in grid view."""
        logger.info(f"[OnlineMusicView] Displaying {len(artists)} artists")
        if artists:
            first = artists[0]
            logger.info(f"[OnlineMusicView] First artist - name: '{first.name}', mid: '{first.mid}', songs: {first.song_count}, albums: {first.album_count}, avatar: '{first.avatar_url}'")
            logger.info(f"[OnlineMusicView] First artist object: {first}")

        if is_append:
            self._singers_page.append_data(artists)
        else:
            self._singers_page.load_data(artists)

        # Show "load more" button if there are more results
        has_more = len(artists) >= self._grid_page_size and (
            self._grid_total == 0 or  # Unknown total, assume more
            self._grid_page * self._grid_page_size < self._grid_total
        )
        self._singers_page.set_has_more(has_more)

    def _display_albums(self, albums: List[OnlineAlbum], is_append: bool = False):
        """Display albums in grid view."""
        if is_append:
            self._albums_page.append_data(albums)
        else:
            self._albums_page.load_data(albums)

        # Show "load more" button if there are more results
        has_more = len(albums) >= self._grid_page_size and (
            self._grid_total == 0 or
            self._grid_page * self._grid_page_size < self._grid_total
        )
        self._albums_page.set_has_more(has_more)

    def _display_playlists(self, playlists: List[OnlinePlaylist], is_append: bool = False):
        """Display playlists in grid view."""
        if is_append:
            self._playlists_page.append_data(playlists)
        else:
            self._playlists_page.load_data(playlists)

        # Show "load more" button if there are more results
        has_more = len(playlists) >= self._grid_page_size and (
            self._grid_total == 0 or
            self._grid_page * self._grid_page_size < self._grid_total
        )
        self._playlists_page.set_has_more(has_more)

    def _on_tab_changed(self, index: int):
        """Handle tab change."""
        type_map = {
            0: SearchType.SONG,
            1: SearchType.SINGER,
            2: SearchType.ALBUM,
            3: SearchType.PLAYLIST,
        }
        self._current_search_type = type_map.get(index, SearchType.SONG)

        # Re-search if there's a keyword
        if self._current_keyword:
            self._current_page = 1
            self._grid_page = 1  # Reset grid page for new tab
            self._do_search()

    def _on_artist_clicked(self, artist: OnlineArtist):
        """Handle artist click - show artist detail view."""
        logger.info(f"Artist clicked: {artist.name}, mid: {artist.mid}")
        self._detail_view.load_artist(artist.mid, artist.name)
        self._stack.setCurrentWidget(self._detail_view)

    def _on_album_clicked(self, album: OnlineAlbum):
        """Handle album click - show album detail view."""
        logger.info(f"Album clicked: {album.name}, mid: {album.mid}")
        self._detail_view.load_album(album.mid, album.name, album.singer_name)
        self._stack.setCurrentWidget(self._detail_view)

    def _on_playlist_clicked(self, playlist: OnlinePlaylist):
        """Handle playlist click - show playlist detail view."""
        logger.info(f"Playlist clicked: {playlist.title}, id: {playlist.id}")
        self._detail_view.load_playlist(playlist.id, playlist.title, playlist.creator)
        self._stack.setCurrentWidget(self._detail_view)

    def _on_load_more_artists(self):
        """Load more artists."""
        self._grid_page += 1
        self._singers_page.show_loading()
        self._load_more_grid(SearchType.SINGER)

    def _on_load_more_albums(self):
        """Load more albums."""
        self._grid_page += 1
        self._albums_page.show_loading()
        self._load_more_grid(SearchType.ALBUM)

    def _on_load_more_playlists(self):
        """Load more playlists."""
        self._grid_page += 1
        self._playlists_page.show_loading()
        self._load_more_grid(SearchType.PLAYLIST)

    def _load_more_grid(self, search_type: str):
        """Load more items for grid view."""
        if self._search_worker and self._search_worker.isRunning():
            self._search_worker.terminate()
            self._search_worker = None

        self._search_worker = SearchWorker(
            self._service,
            self._current_keyword,
            search_type,
            self._grid_page,
            self._grid_page_size
        )
        self._search_worker.search_completed.connect(
            lambda result: self._on_load_more_completed(result, search_type)
        )
        self._search_worker.search_failed.connect(self._on_load_more_failed)
        self._search_worker.start()

    def _on_load_more_completed(self, result: SearchResult, search_type: str):
        """Handle load more completion."""
        if search_type == SearchType.SINGER:
            self._singers_page.hide_loading()
            self._display_artists(result.artists, is_append=True)
        elif search_type == SearchType.ALBUM:
            self._albums_page.hide_loading()
            self._display_albums(result.albums, is_append=True)
        elif search_type == SearchType.PLAYLIST:
            self._playlists_page.hide_loading()
            self._display_playlists(result.playlists, is_append=True)

        # Update total
        self._grid_total = result.total

    def _on_load_more_failed(self, error: str):
        """Handle load more failure."""
        logger.error(f"Load more failed: {error}")
        # Hide loading on all grid views
        self._singers_page.hide_loading()
        self._albums_page.hide_loading()
        self._playlists_page.hide_loading()
        QMessageBox.warning(self, t("error"), t("search_failed") + f": {error}")

    def _on_back_from_detail(self):
        """Handle back button clicked in detail view."""
        # Return to search results page
        self._stack.setCurrentWidget(self._results_page)

    def _on_play_all_from_detail(self, tracks: List[OnlineTrack]):
        """Handle play all from detail view."""
        if not tracks:
            return

        # Build list of (song_mid, metadata) for all tracks
        tracks_data = []
        for track in tracks:
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            }
            tracks_data.append((track.mid, metadata))

        # Emit signal to play all tracks, starting from first
        self.play_online_tracks.emit(0, tracks_data)

    def _on_add_all_to_queue_from_detail(self, tracks: List[OnlineTrack]):
        """Handle add all to queue from detail view."""
        for track in tracks:
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            }
            self.add_to_queue.emit(track.mid, metadata)

    def _on_insert_all_to_queue_from_detail(self, tracks: List[OnlineTrack]):
        """Handle insert all to queue from detail view."""
        for track in tracks:
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            }
            self.insert_to_queue.emit(track.mid, metadata)

    def _on_prev_page(self):
        """Go to previous page."""
        if self._current_page > 1:
            self._current_page -= 1
            self._do_search()

    def _on_next_page(self):
        """Go to next page."""
        self._current_page += 1
        self._do_search()

    def _on_track_double_clicked(self, index):
        """Handle track double click."""
        row = index.row()
        if row < 0 or row >= len(self._current_tracks):
            return

        # If viewing top list, play all songs starting from clicked
        if self._is_top_list_view:
            self._play_all_from_top_list(row)
        else:
            track = self._current_tracks[row]
            self._play_track(track)

    def _play_all_from_top_list(self, start_index: int):
        """Play all songs from top list starting from given index."""
        tracks_data = []
        for track in self._current_tracks:
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            }
            tracks_data.append((track.mid, metadata))

        self.play_online_tracks.emit(start_index, tracks_data)

    def _play_track(self, track: OnlineTrack):
        """Play an online track."""
        # Build metadata from track info
        metadata = {
            "title": track.title,
            "artist": track.singer_name,
            "album": track.album_name,
            "duration": track.duration,
            "album_mid": track.album.mid if track.album else "",
        }

        # Check cache
        if self._download_service.is_cached(track.mid):
            cached_path = self._download_service.get_cached_path(track.mid)
            self.play_online_track.emit(track.mid, cached_path, metadata)
            return

        # Download first
        self._download_and_play(track)

    def _download_and_play(self, track: OnlineTrack):
        """Download track and then play."""
        from PySide6.QtWidgets import QProgressDialog

        # Show progress dialog
        self._download_progress = QProgressDialog(f"{t('downloading')}: {track.title}", t("cancel"), 0, 0, self)
        self._download_progress.setWindowTitle(t("downloading"))
        self._download_progress.setWindowModality(Qt.WindowModal)
        self._download_progress.setMinimumDuration(0)

        # Store current track for callback
        self._downloading_track = track

        # Create download worker
        self._download_worker = DownloadWorker(
            self._download_service, track.mid, track.title
        )
        self._download_worker.download_finished.connect(self._on_download_finished)
        self._download_worker.start()

    def _on_download_finished(self, song_mid: str, local_path: str):
        """Handle download finished."""
        logger.info(f"Download finished callback: mid={song_mid}, path={local_path}")

        # Close progress dialog
        if hasattr(self, '_download_progress') and self._download_progress:
            self._download_progress.close()

        # Get stored track
        track = getattr(self, '_downloading_track', None)
        if not track:
            logger.error("No downloading_track found")
            return

        if song_mid == track.mid and local_path:
            logger.info(f"Emitting play_online_track: {song_mid}, {local_path}")
            # Build metadata from track info
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            }
            self.play_online_track.emit(song_mid, local_path, metadata)
        else:
            logger.warning(f"Download failed or mismatch: mid={song_mid}, track.mid={track.mid}, path={local_path}")
            QMessageBox.warning(self, t("error"), t("download_failed"))

    def _cancel_download(self, song_mid: str):
        """Cancel ongoing download."""
        pass

    def _show_track_context_menu(self, pos):
        """Show context menu for track."""
        # Determine which table sent the signal
        sender_table = self.sender()
        if sender_table == self._top_songs_table:
            table = self._top_songs_table
            is_top_list = True
        else:
            table = self._results_table
            is_top_list = False

        # Get selected rows
        selected_items = table.selectedItems()
        if not selected_items:
            logger.debug(f"No items selected in {'top list' if is_top_list else 'search'} table")
            return

        # Get unique row indices
        selected_rows = sorted(set(item.row() for item in selected_items))
        if not selected_rows:
            return

        # Validate row indices
        if selected_rows[0] < 0 or selected_rows[-1] >= len(self._current_tracks):
            logger.warning(f"Invalid row indices: {selected_rows}, tracks count: {len(self._current_tracks)}")
            return

        tracks = [self._current_tracks[r] for r in selected_rows if 0 <= r < len(self._current_tracks)]
        if not tracks:
            logger.warning("No valid tracks found for selected rows")
            return

        logger.debug(f"Showing context menu for {len(tracks)} tracks in {'top list' if is_top_list else 'search'}")

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
        play_action.triggered.connect(lambda: self._play_selected_tracks(tracks))

        insert_to_queue_action = menu.addAction(t("insert_to_queue"))
        insert_to_queue_action.triggered.connect(lambda: self._insert_selected_to_queue(tracks))

        add_to_queue_action = menu.addAction(t("add_to_queue"))
        add_to_queue_action.triggered.connect(lambda: self._add_selected_to_queue(tracks))

        menu.addSeparator()

        download_action = menu.addAction(t("download"))
        download_action.triggered.connect(lambda: self._download_selected_tracks(tracks))

        menu.exec(table.viewport().mapToGlobal(pos))

    def _download_selected_tracks(self, tracks: List[OnlineTrack]):
        """Download selected tracks."""
        if not tracks:
            return

        # Download each track
        for track in tracks:
            if not self._download_service.is_cached(track.mid):
                self._start_download(track)

    def _start_download(self, track: OnlineTrack):
        """Start downloading a track."""
        worker = DownloadWorker(self._download_service, track.mid, track.title)
        worker.download_finished.connect(self._on_batch_download_finished)
        worker.start()
        # Keep reference to prevent garbage collection
        if not hasattr(self, '_download_workers'):
            self._download_workers = []
        self._download_workers.append(worker)

    def _on_batch_download_finished(self, song_mid: str, local_path: str):
        """Handle batch download finished."""
        if local_path:
            logger.info(f"Download completed: {song_mid} -> {local_path}")
        else:
            logger.warning(f"Download failed: {song_mid}")

    def _play_selected_tracks(self, tracks: List[OnlineTrack]):
        """Play selected tracks."""
        if not tracks:
            return
        # Play first track and add rest to queue
        self._play_track(tracks[0])
        for track in tracks[1:]:
            self.add_to_queue.emit(track.mid, {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            })

    def _add_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Add selected tracks to queue."""
        for track in tracks:
            self.add_to_queue.emit(track.mid, {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            })

    def _insert_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Insert selected tracks after current playing track."""
        for track in tracks:
            self.insert_to_queue.emit(track.mid, {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
            })

    def _load_top_lists(self):
        """Load top lists."""
        if self._top_list_worker and self._top_list_worker.isRunning():
            self._top_list_worker.terminate()

        self._top_list_worker = TopListWorker(self._service)
        self._top_list_worker.top_list_loaded.connect(self._on_top_lists_loaded)
        self._top_list_worker.start()

    def _on_top_lists_loaded(self, top_lists: List[Dict]):
        """Handle top lists loaded."""
        self._top_list_list.clear()

        for top_list in top_lists:
            item = QListWidgetItem(top_list.get("title", ""))
            item.setData(Qt.UserRole, top_list.get("id"))
            self._top_list_list.addItem(item)

        # Select first item
        if self._top_list_list.count() > 0:
            self._top_list_list.setCurrentRow(0)

    def _on_top_list_selected(self, row: int):
        """Handle top list selection."""
        item = self._top_list_list.item(row)
        if not item:
            return

        top_id = item.data(Qt.UserRole)
        if not top_id:
            return

        self._selected_top_id = int(top_id)
        self._top_list_title.setText(item.text())

        # Load songs
        if self._top_list_worker and self._top_list_worker.isRunning():
            self._top_list_worker.terminate()

        self._top_list_worker = TopListWorker(self._service, self._selected_top_id)
        self._top_list_worker.top_songs_loaded.connect(self._on_top_songs_loaded)
        self._top_list_worker.start()

    def _on_top_songs_loaded(self, top_id: int, songs: List[OnlineTrack]):
        """Handle top songs loaded."""
        if top_id != self._selected_top_id:
            return

        self._current_tracks = songs
        self._is_top_list_view = True  # Now viewing top list
        self._display_top_songs(songs)

    def _display_top_songs(self, songs: List[OnlineTrack]):
        """Display top songs in table."""
        self._top_songs_table.setRowCount(len(songs))

        for i, song in enumerate(songs):
            # Rank
            self._top_songs_table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            # Title
            title_item = QTableWidgetItem(song.title)
            if song.is_vip:
                title_item.setForeground(QBrush(QColor("#ffd700")))
            self._top_songs_table.setItem(i, 1, title_item)

            # Artist
            self._top_songs_table.setItem(i, 2, QTableWidgetItem(song.singer_name))

            # Album
            self._top_songs_table.setItem(i, 3, QTableWidgetItem(song.album_name))

            # Duration
            duration_str = format_duration(song.duration) if song.duration else ""
            self._top_songs_table.setItem(i, 4, QTableWidgetItem(duration_str))

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update titles
        if hasattr(self, '_online_music_title'):
            self._online_music_title.setText(t("online_music"))
        if hasattr(self, '_rankings_title'):
            self._rankings_title.setText(t("rankings"))

        # Update search placeholder
        if hasattr(self, '_search_input'):
            self._search_input.setPlaceholderText(t("search_online_music"))

        # Update search button
        if hasattr(self, '_search_btn'):
            self._search_btn.setText(t("search"))

        # Update login button
        self._update_login_status()

        # Update type tabs
        if hasattr(self, '_tabs'):
            self._tabs.setTabText(0, t("songs"))
            self._tabs.setTabText(1, t("singers"))
            self._tabs.setTabText(2, t("albums"))
            self._tabs.setTabText(3, t("playlists"))

        # Update table headers for both tables
        if hasattr(self, '_results_table'):
            header = self._results_table.horizontalHeader()
            if header.count() >= 5:
                header.model().setHeaderData(0, Qt.Horizontal, "#")
                header.model().setHeaderData(1, Qt.Horizontal, t("title"))
                header.model().setHeaderData(2, Qt.Horizontal, t("artist"))
                header.model().setHeaderData(3, Qt.Horizontal, t("album"))
                header.model().setHeaderData(4, Qt.Horizontal, t("duration"))
        if hasattr(self, '_top_songs_table'):
            header = self._top_songs_table.horizontalHeader()
            if header.count() >= 5:
                header.model().setHeaderData(0, Qt.Horizontal, "#")
                header.model().setHeaderData(1, Qt.Horizontal, t("title"))
                header.model().setHeaderData(2, Qt.Horizontal, t("artist"))
                header.model().setHeaderData(3, Qt.Horizontal, t("album"))
                header.model().setHeaderData(4, Qt.Horizontal, t("duration"))

        # Update pagination buttons
        if hasattr(self, '_prev_btn'):
            self._prev_btn.setText("← " + t("previous_page"))
        if hasattr(self, '_next_btn'):
            self._next_btn.setText(t("next_page") + " →")

        # Update top list title if showing "select_ranking" placeholder
        if hasattr(self, '_top_list_title'):
            current_text = self._top_list_title.text()
            # Only update if it's the placeholder text
            if current_text == t("select_ranking") or current_text == "选择排行榜":
                self._top_list_title.setText(t("select_ranking"))

        # Update grid views
        if hasattr(self, '_singers_page'):
            self._singers_page.refresh_ui()
        if hasattr(self, '_albums_page'):
            self._albums_page.refresh_ui()
        if hasattr(self, '_playlists_page'):
            self._playlists_page.refresh_ui()

        # Update detail view
        if hasattr(self, '_detail_view'):
            self._detail_view.refresh_ui()


class DownloadWorker(QThread):
    """Background worker for downloading online music."""

    download_finished = Signal(str, str)  # (song_mid, local_path)

    def __init__(self, download_service, song_mid: str, song_title: str):
        super().__init__()
        self._download_service = download_service
        self._song_mid = song_mid
        self._song_title = song_title

    def run(self):
        """Run download."""
        try:
            result = self._download_service.download(self._song_mid, self._song_title)
            self.download_finished.emit(self._song_mid, result or "")
        except Exception as e:
            logger.error(f"Download worker error: {e}")
            self.download_finished.emit(self._song_mid, "")
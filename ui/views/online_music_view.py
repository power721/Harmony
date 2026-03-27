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
    QScrollArea,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QStringListModel, QPoint
from PySide6.QtGui import QCursor, QColor, QBrush, QAction

from ui.widgets.recommend_card import RecommendSection


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


class HotkeyWorker(QThread):
    """Background worker for fetching hot search keywords."""

    hotkey_ready = Signal(list)  # List of hotkey suggestions

    def __init__(self, qqmusic_service):
        super().__init__()
        self._qqmusic_service = qqmusic_service

    def run(self):
        try:
            if self._qqmusic_service:
                hotkeys = self._qqmusic_service.get_hotkey()
                self.hotkey_ready.emit(hotkeys)
            else:
                logger.debug("No QQ Music service available for hotkey")
                self.hotkey_ready.emit([])
        except Exception as e:
            logger.error(f"Get hotkey failed: {e}")
            self.hotkey_ready.emit([])


class RecommendWorker(QThread):
    """Background worker for fetching recommendations."""

    recommend_ready = Signal(str, list)  # (recommend_type, list of recommendations)

    def __init__(self, qqmusic_service, recommend_type: str):
        super().__init__()
        self._qqmusic_service = qqmusic_service
        self._recommend_type = recommend_type

    def run(self):
        try:
            if not self._qqmusic_service:
                self.recommend_ready.emit(self._recommend_type, [])
                return

            result = []
            if self._recommend_type == "home_feed":
                result = self._qqmusic_service.get_home_feed()
            elif self._recommend_type == "guess":
                result = self._qqmusic_service.get_guess_recommend()
            elif self._recommend_type == "radar":
                result = self._qqmusic_service.get_radar_recommend()
            elif self._recommend_type == "songlist":
                result = self._qqmusic_service.get_recommend_songlist()
            elif self._recommend_type == "newsong":
                result = self._qqmusic_service.get_recommend_newsong()

            self.recommend_ready.emit(self._recommend_type, result)
        except Exception as e:
            logger.error(f"Get recommendation {self._recommend_type} failed: {e}")
            self.recommend_ready.emit(self._recommend_type, [])


class FavWorker(QThread):
    """Background worker for loading favorites."""

    fav_ready = Signal(str, list)  # (fav_type, list of items)

    def __init__(self, qqmusic_service, fav_type: str, page: int = 1, num: int = 30):
        super().__init__()
        self._qqmusic_service = qqmusic_service
        self._fav_type = fav_type
        self._page = page
        self._num = num

    def run(self):
        try:
            if not self._qqmusic_service:
                self.fav_ready.emit(self._fav_type, [])
                return
            result = []
            if self._fav_type == "fav_songs":
                result = self._qqmusic_service.get_my_fav_songs(page=self._page, num=self._num)
            elif self._fav_type == "created_playlists":
                result = self._qqmusic_service.get_my_created_songlists()
            elif self._fav_type == "fav_playlists":
                result = self._qqmusic_service.get_my_fav_songlists(page=self._page, num=self._num)
            elif self._fav_type == "fav_albums":
                result = self._qqmusic_service.get_my_fav_albums(page=self._page, num=self._num)
            self.fav_ready.emit(self._fav_type, result)
        except Exception as e:
            logger.error(f"Get favorites {self._fav_type} failed: {e}")
            self.fav_ready.emit(self._fav_type, [])


class HotkeyPopup(QWidget):
    """Popup widget for displaying hot search keywords."""

    hotkey_clicked = Signal(str)  # Emitted when a hotkey is clicked

    def __init__(self, parent=None):
        super().__init__(parent)
        # 使用 Window 标志，允许交互但不显示在任务栏
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)  # 显示时不激活窗口

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Container with border
        container = QWidget()
        container.setObjectName("hotkeyContainer")
        container.setStyleSheet("""
            #hotkeyContainer {
                background-color: #2a2a2a;
                border: 1px solid #3a3a3a;
                border-radius: 8px;
            }
        """)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(4)

        # Title
        title = QLabel("🔥 " + t("hot_search"))
        title.setStyleSheet("color: #1db954; font-size: 14px; font-weight: bold;")
        container_layout.addWidget(title)

        # Hotkey list container (using flow layout with tags)
        self._hotkey_container = QWidget()
        self._hotkey_layout = QHBoxLayout(self._hotkey_container)
        self._hotkey_layout.setContentsMargins(0, 0, 0, 0)
        self._hotkey_layout.setSpacing(8)
        self._hotkey_layout.addStretch()
        container_layout.addWidget(self._hotkey_container)

        layout.addWidget(container)

    def set_hotkeys(self, hotkeys: List[Dict[str, Any]]):
        """Set hotkey list."""
        # Clear existing buttons
        while self._hotkey_layout.count() > 1:
            item = self._hotkey_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add hotkey buttons (limit to 10)
        for i, item in enumerate(hotkeys[:10]):
            title = item.get('title', '')
            query = item.get('query', title)  # query是实际搜索词
            if not title:
                continue

            btn = QPushButton(f"{i + 1}. {title}")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3a3a3a;
                    color: #e0e0e0;
                    border: none;
                    border-radius: 12px;
                    padding: 6px 12px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #1db954;
                    color: #ffffff;
                }
            """)
            # 使用query字段进行搜索
            btn.clicked.connect(lambda checked, q=query: self._on_hotkey_clicked(q))
            self._hotkey_layout.insertWidget(self._hotkey_layout.count() - 1, btn)

    def _on_hotkey_clicked(self, query: str):
        """Handle hotkey button click."""
        self.hide()
        self.hotkey_clicked.emit(query)

    def show_at(self, global_pos: QPoint):
        """Show popup at global position."""
        self.move(global_pos)
        self.show()


class SearchInputWithHotkey(QLineEdit):
    """Custom search input that emits focus events."""

    focus_gained = Signal()
    focus_lost = Signal()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_gained.emit()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_lost.emit()


class OnlineMusicView(QWidget):
    """View for searching and browsing online music."""

    # Signals
    play_online_track = Signal(str, str, object)  # (song_mid, local_path, metadata_dict)
    insert_to_queue = Signal(str, object)  # (song_mid, metadata_dict)
    add_to_queue = Signal(str, object)  # (song_mid, metadata_dict)
    add_multiple_to_queue = Signal(list)  # list of (song_mid, metadata_dict)
    insert_multiple_to_queue = Signal(list)  # list of (song_mid, metadata_dict)
    play_online_tracks = Signal(int, list)  # (start_index, list of (song_mid, metadata_dict))

    def __init__(
        self,
        config_manager=None,
        db_manager=None,
        qqmusic_service=None,
        parent=None
    ):
        super().__init__(parent)

        self._config = config_manager
        self._db = db_manager
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

        # Hotkey state
        self._hotkey_worker: Optional[HotkeyWorker] = None
        self._hotkey_popup: Optional[HotkeyPopup] = None
        self._hotkeys: List[Dict[str, Any]] = []  # Cached hotkeys

        # Recommend state
        self._recommend_workers: List[RecommendWorker] = []
        self._recommendations: Dict[str, List[Dict[str, Any]]] = {}
        self._recommendations_loaded = False

        # Favorites state
        self._fav_workers: List[FavWorker] = []
        self._fav_loaded = False
        self._fav_data: Dict[str, list] = {}  # Store loaded favorites data

        # Navigation history stack - tracks where user came from
        # Each entry is a dict: {'page': 'top_list'|'results'|'playlists'|'albums', 'data': ...}
        self._navigation_stack: List[Dict[str, Any]] = []

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

        # My Favorites section (shown when logged in, above recommendations)
        # 4 cards: fav_songs, created_playlists, fav_playlists, fav_albums
        self._favorites_section = RecommendSection(title=t("my_favorites"), parent=self)
        self._favorites_section.recommendation_clicked.connect(self._on_favorites_card_clicked)
        self._favorites_section.hide()
        layout.addWidget(self._favorites_section)

        # Recommendations section (shown when logged in)
        self._recommend_section = RecommendSection(title=t("recommendations"), parent=self)
        self._recommend_section.recommendation_clicked.connect(self._on_recommendation_clicked)
        layout.addWidget(self._recommend_section)

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
            db_manager=self._db,
            qqmusic_service=self._qqmusic_service,
            parent=self
        )
        self._detail_view.back_requested.connect(self._on_back_from_detail)
        # Connect play_all and add_all_to_queue signals
        self._detail_view.play_all.connect(self._on_play_all_from_detail)
        self._detail_view.insert_all_to_queue.connect(self._on_insert_all_to_queue_from_detail)
        self._detail_view.add_all_to_queue.connect(self._on_add_all_to_queue_from_detail)
        # Connect album click from artist detail view
        self._detail_view.album_clicked.connect(self._on_album_clicked)
        self._stack.addWidget(self._detail_view)

        layout.addWidget(self._stack, 1)  # Give stretch factor so it doesn't push other widgets

        # Apply styles
        self._apply_styles()

        # Load recommendations if logged in (after UI is fully set up)
        if self._service._has_qqmusic_credential():
            self._load_recommendations()
            self._load_favorites()

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
        self._search_input = SearchInputWithHotkey()
        self._search_input.setPlaceholderText(t("search_online_music"))
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.setFixedHeight(50)
        self._search_input.setClearButtonEnabled(True)

        # Connect focus events for hotkey popup
        self._search_input.focus_gained.connect(self._on_search_focus_gained)
        self._search_input.focus_lost.connect(self._on_search_focus_lost)

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

        # Header with back button and results info
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)

        # Back button (hidden by default, shown for favorites views)
        self._fav_back_btn = QPushButton(f"← {t('back')}")
        self._fav_back_btn.setCursor(Qt.PointingHandCursor)
        self._fav_back_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #1db954;
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 4px 8px;
            }
            QPushButton:hover {
                color: #1ed760;
            }
        """)
        self._fav_back_btn.clicked.connect(self._on_fav_back_clicked)
        self._fav_back_btn.hide()
        header_layout.addWidget(self._fav_back_btn)

        # Results info
        self._results_info = QLabel()
        self._results_info.setStyleSheet("color: #808080; font-size: 12px;")
        header_layout.addWidget(self._results_info)
        header_layout.addStretch()

        layout.addWidget(header_widget)

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
                # Update detail view service references
                if hasattr(self, '_detail_view') and self._detail_view:
                    self._detail_view._service._qqmusic = self._qqmusic_service
                    self._detail_view._download_service._qqmusic = self._qqmusic_service
                logger.info(f"QQ Music service refreshed, musicid={cred_dict.get('musicid')}, "
                            f"has_refresh_key={bool(cred_dict.get('refresh_key'))}")
            except Exception as e:
                logger.error(f"Failed to refresh QQ Music service: {e}")

    def _update_login_status(self):
        """Update QQ Music login status display."""
        has_credential = self._service._has_qqmusic_credential()

        if has_credential:
            # Refresh QQ Music service with new credentials
            self._refresh_qqmusic_service()

            # Get nickname from config
            nick = self._config.get_qqmusic_nick() if self._config else ""

            if nick:
                self._login_status_label.setText(t("qqmusic_logged_in_as").format(nick=nick))
            else:
                self._login_status_label.setText(t("qqmusic_logged_in"))

            self._login_btn.setText(t("logout"))

            # Load recommendations when logged in (only if UI is fully set up)
            if hasattr(self, '_recommend_section'):
                self._load_recommendations()
        else:
            self._login_status_label.setText(t("qqmusic_not_logged_in"))
            self._login_btn.setText(t("login"))

            # Hide recommendations when not logged in
            if hasattr(self, '_recommend_section'):
                self._recommend_section.hide()

    def _on_login_clicked(self):
        """Handle login button click."""
        if self._service._has_qqmusic_credential():
            # Logout
            if self._config:
                self._config.clear_qqmusic_credential()
            self._update_login_status()
            QMessageBox.information(self, t("logout"), t("logout_success"))
        else:
            # Show login dialog
            self._show_login_dialog()

    def _show_login_dialog(self):
        """Show QQ Music login dialog."""
        from ui.dialogs.qqmusic_qr_login_dialog import QQMusicQRLoginDialog

        dialog = QQMusicQRLoginDialog(self)
        # Connect to credentials signal to refresh immediately on success
        dialog.credentials_obtained.connect(self._on_credentials_obtained)
        dialog.exec()

    def _on_credentials_obtained(self, credential: dict):
        """Handle credentials obtained from login dialog."""
        logger.info("QQ Music credentials obtained, refreshing service...")
        self._refresh_qqmusic_service()
        self._update_login_status()
        # Reload favorites with new credentials
        self._fav_loaded = False
        self._load_favorites()

    def _load_recommendations(self):
        """Load all 5 types of recommendations."""
        if self._recommendations_loaded:
            return

        self._recommend_section.show_loading()
        self._recommendations_loaded = True

        # Define 5 recommendation types with their display titles
        recommend_types = [
            ("home_feed", t("home_recommend")),
            ("guess", t("guess_you_like")),
            ("radar", t("radar_recommend")),
            ("songlist", t("recommend_playlists")),
            ("newsong", t("new_songs")),
        ]

        for recommend_type, title in recommend_types:
            worker = RecommendWorker(self._qqmusic_service, recommend_type)
            worker.recommend_ready.connect(self._on_recommend_ready)
            self._recommend_workers.append(worker)
            worker.start()

    def _on_recommend_ready(self, recommend_type: str, data: Any):
        """Handle recommendation data ready."""
        logger.info(f"Recommendation {recommend_type} loaded: {type(data)}")

        # Debug: Log the actual data structure
        if isinstance(data, dict):
            logger.debug(f"  Dict keys: {list(data.keys())[:10]}")
        elif isinstance(data, list):
            logger.debug(f"  List length: {len(data)}")
            if data and isinstance(data[0], dict):
                logger.debug(f"  First item keys: {list(data[0].keys())[:10]}")

        # Store raw data for parsing
        self._recommendations[recommend_type] = data

        # Check if all recommendations are loaded
        expected_types = ["home_feed", "guess", "radar", "songlist", "newsong"]
        loaded_count = sum(1 for t in expected_types if t in self._recommendations)

        # Only display when all 5 are loaded
        if loaded_count == len(expected_types):
            self._display_recommendations()

    def _display_recommendations(self):
        """Parse and display all loaded recommendations."""
        cards = []

        # Define order and titles
        recommend_config = [
            ("home_feed", t("home_recommend")),
            ("guess", t("guess_you_like")),
            ("radar", t("radar_recommend")),
            ("songlist", t("recommend_playlists")),
            ("newsong", t("new_songs")),
        ]

        for recommend_type, title in recommend_config:
            data = self._recommendations.get(recommend_type)
            if not data:
                continue

            parsed = self._parse_recommendation(recommend_type, data)
            if parsed:
                parsed['recommend_type'] = recommend_type
                parsed['title'] = title
                cards.append(parsed)
                logger.info(f"Added card for {recommend_type}: cover_url={parsed.get('cover_url')}")

        logger.info(f"Total cards to display: {len(cards)}")
        if cards:
            self._recommend_section.load_recommendations(cards)

    def _load_favorites(self):
        """Load user's favorites counts and display 4 summary cards."""
        if self._fav_loaded:
            return

        if not self._qqmusic_service or not self._qqmusic_service._credential:
            return

        self._fav_loaded = True
        self._favorites_section.show_loading()
        self._fav_data = {}  # Store data for click handling

        for fav_type in ["fav_songs", "created_playlists", "fav_playlists", "fav_albums"]:
            worker = FavWorker(self._qqmusic_service, fav_type)
            worker.fav_ready.connect(self._on_fav_ready)
            self._fav_workers.append(worker)
            worker.start()

    def _on_fav_ready(self, fav_type: str, data: list):
        """Handle favorites data ready - store for later use."""
        self._fav_data[fav_type] = data

        # Check if all 4 types loaded
        if len(self._fav_data) == 4:
            self._display_favorites_cards()

    def _get_random_cover(self, items: list) -> str:
        """Get a random cover from a list of items."""
        import random

        if not items:
            return ""

        # Filter items that have cover_url
        items_with_cover = [item for item in items if item.get("cover_url")]

        if not items_with_cover:
            return ""

        # Select a random item
        random_item = random.choice(items_with_cover)
        return random_item.get("cover_url", "")

    def _get_random_cover_from_items(self, data: list, recommend_type: str) -> str:
        """Extract a random cover from recommendation data based on type."""
        import random

        if not data:
            return ""

        # Filter items that have valid cover data
        valid_items = []
        for item in data:
            if not isinstance(item, dict):
                continue

            cover_url = None

            if recommend_type == 'songlist':
                # Playlist structure
                playlist_info = item.get('Playlist', item)
                if isinstance(playlist_info, dict):
                    # Try basic/content structures
                    if 'basic' in playlist_info:
                        basic = playlist_info.get('basic', {})
                        if isinstance(basic, dict):
                            cover = basic.get('cover_url') or basic.get('cover') or basic.get('picurl')
                            if cover:
                                if isinstance(cover, dict):
                                    cover_url = cover.get('default_url') or cover.get('small_url')
                                else:
                                    cover_url = cover

                    if not cover_url and 'content' in playlist_info:
                        content = playlist_info.get('content', {})
                        if isinstance(content, dict):
                            cover = content.get('cover_url') or content.get('cover')
                            if cover:
                                if isinstance(cover, dict):
                                    cover_url = cover.get('default_url') or cover.get('small_url')
                                else:
                                    cover_url = cover

                    if not cover_url:
                        cover = (playlist_info.get('cover_url') or playlist_info.get('cover') or
                                playlist_info.get('picurl') or playlist_info.get('pic'))
                        if cover:
                            if isinstance(cover, dict):
                                cover_url = cover.get('default_url') or cover.get('small_url')
                            else:
                                cover_url = cover

                    # Try to get from songlist
                    if not cover_url:
                        song_list = playlist_info.get('songlist', [])
                        if song_list:
                            album = song_list[0].get('album', {})
                            if isinstance(album, dict):
                                album_mid = album.get('mid')
                                if album_mid:
                                    cover_url = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg"

            elif recommend_type == 'radar':
                # Radar structure
                track_info = item.get('Track', {})
                if isinstance(track_info, dict):
                    album = track_info.get('album', {})
                    if isinstance(album, dict):
                        album_mid = album.get('mid')
                        if album_mid:
                            cover_url = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg"

            else:
                # Song structure (guess, home_feed, newsong)
                cover_url = (item.get('cover') or item.get('picurl') or
                            item.get('cover_url') or item.get('pic'))

                if not cover_url:
                    album_mid = None
                    album = item.get('album', {})
                    if isinstance(album, dict):
                        album_mid = album.get('mid')
                    if not album_mid:
                        album_mid = item.get('albummid') or item.get('album_mid')

                    if album_mid:
                        cover_url = f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{album_mid}.jpg"

            if cover_url:
                valid_items.append(cover_url)

        if valid_items:
            return random.choice(valid_items)

        return ""

    def _display_favorites_cards(self):
        """Display 4 summary cards in the favorites section."""
        from ui.icons import get_icon, IconName

        cards = []

        # Card 1: 收藏歌曲
        fav_songs = self._fav_data.get("fav_songs", [])
        cards.append({
            "id": "fav_songs",
            "title": t("fav_songs"),
            "subtitle": f"{len(fav_songs)} {t('songs')}",
            "cover_url": self._get_random_cover(fav_songs),
            "card_type": "fav_songs",
        })

        # Card 2: 创建的歌单
        created_pl = self._fav_data.get("created_playlists", [])
        cards.append({
            "id": "created_playlists",
            "title": t("created_playlists"),
            "subtitle": f"{len(created_pl)} {t('playlists')}",
            "cover_url": self._get_random_cover(created_pl),
            "card_type": "created_playlists",
        })

        # Card 3: 收藏的歌单
        fav_pl = self._fav_data.get("fav_playlists", [])
        cards.append({
            "id": "fav_playlists",
            "title": t("fav_playlists"),
            "subtitle": f"{len(fav_pl)} {t('playlists')}",
            "cover_url": self._get_random_cover(fav_pl),
            "card_type": "fav_playlists",
        })

        # Card 4: 收藏专辑
        fav_albums = self._fav_data.get("fav_albums", [])
        cards.append({
            "id": "fav_albums",
            "title": t("fav_albums"),
            "subtitle": f"{len(fav_albums)} {t('albums')}",
            "cover_url": self._get_random_cover(fav_albums),
            "card_type": "fav_albums",
        })

        self._favorites_section.load_recommendations(cards)

    def _parse_recommendation(self, recommend_type: str, data: Any) -> Optional[Dict[str, Any]]:
        """Parse recommendation data to extract card info."""
        try:
            # Handle list response (API returns list of songs/playlists)
            if isinstance(data, list):
                if not data:
                    return None

                # Get first item for structure analysis
                first_item = data[0]
                if not isinstance(first_item, dict):
                    return None

                logger.debug(f"Parsing {recommend_type} list item: keys={list(first_item.keys())[:15]}")

                # Get a random cover from all items
                cover_url = self._get_random_cover_from_items(data, recommend_type)
                playlist_id = None

                # Handle different response structures based on type
                if recommend_type == 'songlist':
                    # Playlist structure: {'Playlist': {...}, 'WhereFrom': ..., 'ext': ...}
                    # or direct structure with tid/id/disstid
                    logger.debug(f"songlist first_item keys: {list(first_item.keys())}")

                    playlist_info = first_item.get('Playlist', {})
                    if isinstance(playlist_info, dict) and playlist_info:
                        logger.debug(f"songlist Playlist keys: {list(playlist_info.keys())}")

                        # Try nested structures first (basic/content)
                        if 'basic' in playlist_info:
                            basic = playlist_info.get('basic', {})
                            if isinstance(basic, dict):
                                playlist_id = basic.get('tid') or basic.get('id') or basic.get('disstid')

                        if not playlist_id and 'content' in playlist_info:
                            content = playlist_info.get('content', {})
                            if isinstance(content, dict):
                                playlist_id = content.get('tid') or content.get('id') or content.get('disstid')

                        # Fallback to direct fields
                        if not playlist_id:
                            playlist_id = playlist_info.get('tid') or playlist_info.get('id') or playlist_info.get('disstid')

                        logger.debug(f"songlist from Playlist: id={playlist_id}")
                    else:
                        # Try direct structure - check for various ID fields
                        playlist_id = (first_item.get('tid') or first_item.get('id') or
                                      first_item.get('disstid') or first_item.get('dissid'))
                        logger.debug(f"songlist direct: id={playlist_id}")

                elif recommend_type == 'radar':
                    # Radar structure: {'Track': {...}, 'Abt': ..., 'Ext': ...}
                    # Cover is already extracted by _get_random_cover_from_items
                    pass

                else:
                    # Song structure: {'album': {...}, 'singer': [...], ...}
                    # This handles guess, home_feed, newsong types
                    logger.debug(f"{recommend_type} first_item keys: {list(first_item.keys())}")

                    # Cover is already extracted by _get_random_cover_from_items
                    # Get playlist ID if available (for playlist-based recommendations)
                    playlist_id = (first_item.get('id') or first_item.get('disstid') or
                                  first_item.get('tid') or first_item.get('playlist_id'))

                    logger.debug(f"{recommend_type}: cover_url={cover_url}, playlist_id={playlist_id}")

                return {
                    'id': playlist_id,
                    'cover_url': cover_url,
                    'raw_data': first_item,  # Save first item for click handling
                    'full_data': data,  # Save full data list for song-based recommendations
                    'recommend_type': recommend_type,
                }

            # Handle dict response (API returns dict with embedded list)
            if isinstance(data, dict):
                # Log the structure for debugging
                logger.debug(f"Parsing {recommend_type} dict: keys={list(data.keys())[:10]}")

                # Try to find the main content
                content = None
                for key in ['songlist', 'songs', 'list', 'data', 'items', 'playlist']:
                    if key in data:
                        content = data[key]
                        break

                if content and isinstance(content, list) and content:
                    first_item = content[0]
                    if isinstance(first_item, dict):
                        logger.debug(f"  First item keys: {list(first_item.keys())[:15]}")

                        # Get a random cover from all items
                        cover_url = self._get_random_cover_from_items(content, recommend_type)
                        playlist_id = (first_item.get('id') or first_item.get('disstid') or
                                      first_item.get('tid') or data.get('id'))

                        return {
                            'id': playlist_id,
                            'cover_url': cover_url,
                            'raw_data': first_item,  # Save first item for click handling
                            'full_data': content,  # Save full data list for song-based recommendations
                            'recommend_type': recommend_type,
                        }

                # Check for playlist info directly
                playlist_id = data.get('id') or data.get('disstid')
                cover_url = data.get('cover') or data.get('picurl') or data.get('pic')

                return {
                    'id': playlist_id,
                    'cover_url': cover_url,
                    'raw_data': data,
                    'recommend_type': recommend_type,
                }

            return None
        except Exception as e:
            logger.error(f"Failed to parse recommendation {recommend_type}: {e}")
            return None

    def _on_favorites_card_clicked(self, data: Dict[str, Any]):
        """Handle favorites section card click."""
        card_type = data.get("card_type", "")

        # Hide favorites and recommendations when viewing any favorites content
        self._favorites_section.hide()
        self._recommend_section.hide()
        # Show back button
        self._fav_back_btn.show()

        if card_type == "fav_songs":
            tracks = self._fav_data.get("fav_songs", [])
            self._show_fav_songs_in_table(tracks)
        elif card_type == "created_playlists":
            playlists = self._fav_data.get("created_playlists", [])
            self._show_playlist_list_in_detail(t("created_playlists"), playlists)
        elif card_type == "fav_playlists":
            playlists = self._fav_data.get("fav_playlists", [])
            self._show_playlist_list_in_detail(t("fav_playlists"), playlists)
        elif card_type == "fav_albums":
            albums = self._fav_data.get("fav_albums", [])
            self._show_album_list_in_detail(t("fav_albums"), albums)

    def _show_fav_songs_in_table(self, tracks: list):
        """Show favorite songs in the detail view with play all / add to queue buttons."""
        # Convert to the format expected by load_songs_directly
        songs = []
        cover_url = ""
        for t_data in tracks:
            song = {
                "mid": t_data.get("mid", ""),
                "songmid": t_data.get("mid", ""),
                "title": t_data.get("title", ""),
                "songname": t_data.get("title", ""),
                "name": t_data.get("title", ""),
                "singer": [{"mid": "", "name": t_data.get("singer", "")}] if t_data.get("singer") else [],
                "album": {
                    "mid": t_data.get("album_mid", ""),
                    "name": t_data.get("album", ""),
                },
                "interval": t_data.get("duration", 0),
            }
            songs.append(song)
            # Use first song's cover
            if not cover_url and t_data.get("cover_url"):
                cover_url = t_data.get("cover_url")

        # Use detail view to show songs with play all / add to queue buttons
        self._detail_view.load_songs_directly(songs, t("fav_songs"), cover_url)
        self._stack.setCurrentWidget(self._detail_view)

    def _show_playlist_list_in_detail(self, title: str, playlists: list):
        """Show a list of playlists in the grid view."""
        from domain.online_music import OnlinePlaylist

        # Clear previous data
        self._playlists_page.clear()

        # Convert dicts to OnlinePlaylist objects
        online_playlists = []
        for pl in playlists:
            online_playlists.append(OnlinePlaylist(
                id=str(pl.get("id", "")),
                title=pl.get("title", ""),
                cover_url=pl.get("cover_url", ""),
                creator=pl.get("creator", ""),
                song_count=pl.get("song_count", 0),
            ))

        self._playlists_page.load_data(online_playlists)
        self._results_info.setText(title)
        self._tabs.hide()
        self._is_top_list_view = False
        self._results_stack.setCurrentWidget(self._playlists_page)
        self._stack.setCurrentWidget(self._results_page)

        # Push navigation state
        self._navigation_stack.append({
            'page': 'playlists',
            'title': title,
            'data': playlists
        })

    def _show_album_list_in_detail(self, title: str, albums: list):
        """Show a list of albums in the grid view."""
        from domain.online_music import OnlineAlbum

        # Clear previous data
        self._albums_page.clear()

        # Convert dicts to OnlineAlbum objects
        online_albums = []
        for album in albums:
            singer_name = album.get("singer_name", "")
            online_albums.append(OnlineAlbum(
                mid=album.get("mid", ""),
                name=album.get("title", ""),
                singer_mid="",
                singer_name=singer_name,
                cover_url=album.get("cover_url", ""),
                song_count=album.get("song_count", 0),
            ))

        self._albums_page.load_data(online_albums)
        self._results_info.setText(title)
        self._tabs.hide()
        self._is_top_list_view = False
        self._results_stack.setCurrentWidget(self._albums_page)
        self._stack.setCurrentWidget(self._results_page)

        # Push navigation state
        self._navigation_stack.append({
            'page': 'albums',
            'title': title,
            'data': albums
        })

    def _on_recommendation_clicked(self, data: Dict[str, Any]):
        """Handle recommendation card click."""
        # Hide favorites and recommendations when viewing details
        self._favorites_section.hide()
        self._recommend_section.hide()
        # Show back button for playlist list view
        self._fav_back_btn.show()

        recommend_type = data.get('recommend_type', '')
        raw_data = data.get('raw_data')
        card_id = data.get('id')
        full_data = data.get('full_data')  # Full song list for song-based recommendations

        logger.info(f"Recommendation clicked: {recommend_type}, id={card_id}")

        title = data.get('title', '')
        cover_url = data.get('cover_url', '')

        if not isinstance(raw_data, dict):
            logger.warning(f"Invalid raw_data type: {type(raw_data)}")
            return

        # Handle songlist type - show list of playlists
        if recommend_type == 'songlist':
            # full_data contains the list of playlists
            if full_data and isinstance(full_data, list):
                playlists = []
                for item in full_data:
                    if isinstance(item, dict):
                        # Extract playlist info from nested structure
                        playlist_info = item.get('Playlist', item)
                        if not isinstance(playlist_info, dict):
                            continue

                        # Try to get playlist details from various nested structures
                        # Structure: basic/content/diy
                        playlist_id = None
                        playlist_title = None
                        cover_url = None
                        song_count = 0

                        # Try basic structure first
                        if 'basic' in playlist_info:
                            basic = playlist_info.get('basic', {})
                            if isinstance(basic, dict):
                                playlist_id = basic.get('tid') or basic.get('id') or basic.get('disstid')
                                playlist_title = basic.get('title') or basic.get('name')
                                # Cover can be URL string or dict
                                cover = basic.get('cover_url') or basic.get('cover') or basic.get('picurl')
                                if cover:
                                    if isinstance(cover, dict):
                                        cover_url = cover.get('default_url') or cover.get('small_url')
                                    else:
                                        cover_url = cover

                        # Try content structure
                        if not playlist_id and 'content' in playlist_info:
                            content = playlist_info.get('content', {})
                            if isinstance(content, dict):
                                playlist_id = content.get('tid') or content.get('id') or content.get('disstid')
                                if not playlist_title:
                                    playlist_title = content.get('title') or content.get('name')
                                if not cover_url:
                                    cover = content.get('cover_url') or content.get('cover')
                                    if cover:
                                        if isinstance(cover, dict):
                                            cover_url = cover.get('default_url') or cover.get('small_url')
                                        else:
                                            cover_url = cover

                        # Fallback to direct fields
                        if not playlist_id:
                            playlist_id = (playlist_info.get('tid') or playlist_info.get('id') or
                                          playlist_info.get('disstid') or playlist_info.get('dissid'))
                        if not playlist_title:
                            playlist_title = playlist_info.get('title') or playlist_info.get('name')
                        if not cover_url:
                            cover = (playlist_info.get('cover_url') or playlist_info.get('cover') or
                                    playlist_info.get('picurl') or playlist_info.get('pic'))
                            if cover:
                                if isinstance(cover, dict):
                                    cover_url = cover.get('default_url') or cover.get('small_url')
                                else:
                                    cover_url = cover

                        # Try to get song count from various fields
                        song_count = 0

                        # Check basic/content for song_count - try multiple field name variations
                        if 'basic' in playlist_info:
                            basic = playlist_info.get('basic', {})
                            if isinstance(basic, dict):
                                song_count = (basic.get('song_count') or basic.get('song_num') or
                                             basic.get('songNum') or basic.get('song_cnt') or 0)
                        if not song_count and 'content' in playlist_info:
                            content = playlist_info.get('content', {})
                            if isinstance(content, dict):
                                song_count = (content.get('song_count') or content.get('song_num') or
                                             content.get('songNum') or content.get('song_cnt') or 0)
                        # Check songlist if exists
                        if not song_count:
                            song_list = playlist_info.get('songlist', [])
                            if song_list:
                                song_count = len(song_list)
                        # Fallback to direct field - try multiple field name variations
                        if not song_count:
                            song_count = (playlist_info.get('song_count') or playlist_info.get('song_num') or
                                         playlist_info.get('songNum') or playlist_info.get('song_cnt') or
                                         playlist_info.get('songnum') or 0)

                        if playlist_id:
                            playlists.append({
                                'id': str(playlist_id),
                                'title': playlist_title or '',
                                'cover_url': cover_url or '',
                                'song_count': song_count,
                            })

                logger.info(f"Showing {len(playlists)} recommended playlists")
                if playlists:
                    self._show_playlist_list_in_detail(title, playlists)
                else:
                    logger.warning("No valid playlists found in songlist data")
            else:
                logger.warning(f"Invalid full_data for songlist: {type(full_data)}")
            return

        # Handle radar type - Track info, show all radar songs
        if recommend_type == 'radar':
            if full_data and isinstance(full_data, list):
                # Radar data format: [{'Track': {...}, 'Abt': ..., 'Ext': ...}, ...]
                # Need to extract Track from each item
                songs = []
                for item in full_data:
                    if isinstance(item, dict):
                        track = item.get('Track', item)
                        if isinstance(track, dict):
                            songs.append(track)
                logger.info(f"Loading radar songs: {len(songs)} songs")
                if songs:
                    self._detail_view.load_songs_directly(songs, title, cover_url)
                    self._stack.setCurrentWidget(self._detail_view)
                else:
                    logger.warning("No valid radar songs found")
            else:
                # Fallback to album
                track_info = raw_data.get('Track', raw_data)
                album = track_info.get('album', {})
                if isinstance(album, dict) and album.get('mid'):
                    logger.info(f"Loading radar album: {album.get('mid')}")
                    self._detail_view.load_album(album.get('mid'), album.get('name', title), "")
                    self._stack.setCurrentWidget(self._detail_view)
            return

        # Handle guess, home_feed, newsong types - these return songs, show all songs
        if recommend_type in ('guess', 'home_feed', 'newsong'):
            if full_data and isinstance(full_data, list):
                logger.info(f"Loading {recommend_type} songs: {len(full_data)} songs")
                self._detail_view.load_songs_directly(full_data, title, cover_url)
                self._stack.setCurrentWidget(self._detail_view)
                return

            # Fallback to album if no full_data
            album = raw_data.get('album', {})
            if isinstance(album, dict) and album.get('mid'):
                logger.info(f"Loading album from {recommend_type}: {album.get('mid')}")
                self._detail_view.load_album(album.get('mid'), album.get('name', title), "")
                self._stack.setCurrentWidget(self._detail_view)
                return

        logger.warning(f"Could not determine how to handle recommendation: {recommend_type}")

    def _on_search(self):
        """Handle search."""
        keyword = self._search_input.text().strip()
        if not keyword:
            return

        # Hide favorites and recommendations sections when searching
        self._favorites_section.hide()
        self._recommend_section.hide()

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

        # Clear all result pages (not just songs)
        self._singers_page.clear()
        self._albums_page.clear()
        self._playlists_page.clear()

        self._do_search()

    def _on_search_focus_gained(self):
        """Handle search input focus gained - show hotkey popup if empty."""
        text = self._search_input.text().strip()
        if not text and self._qqmusic_service:
            self._show_hotkey_popup()

    def _on_search_focus_lost(self):
        """Handle search input focus lost - hide hotkey popup."""
        # Delay hiding to allow click on hotkey items
        QTimer.singleShot(100, self._hide_hotkey_popup)

    def _show_hotkey_popup(self):
        """Show hotkey popup below search input."""
        if not self._hotkey_popup:
            self._hotkey_popup = HotkeyPopup(self)
            self._hotkey_popup.hotkey_clicked.connect(self._on_hotkey_clicked)

        # Use cached hotkeys if available
        if self._hotkeys:
            self._hotkey_popup.set_hotkeys(self._hotkeys)
            # Position popup below search input
            input_rect = self._search_input.rect()
            global_pos = self._search_input.mapToGlobal(input_rect.bottomLeft())
            self._hotkey_popup.show_at(global_pos)
        else:
            # Fetch hotkeys
            self._load_hotkeys()

    def _hide_hotkey_popup(self):
        """Hide hotkey popup."""
        if self._hotkey_popup and self._hotkey_popup.isVisible():
            # Only hide if search input doesn't have focus anymore
            if not self._search_input.hasFocus():
                self._hotkey_popup.hide()

    def _load_hotkeys(self):
        """Load hotkey suggestions from QQ Music."""
        if not self._qqmusic_service:
            return

        if self._hotkey_worker and self._hotkey_worker.isRunning():
            self._hotkey_worker.terminate()

        self._hotkey_worker = HotkeyWorker(self._qqmusic_service)
        self._hotkey_worker.hotkey_ready.connect(self._on_hotkey_ready)
        self._hotkey_worker.start()

    def _on_hotkey_ready(self, hotkeys: List[Dict[str, Any]]):
        """Handle hotkey suggestions ready."""
        if hotkeys:
            self._hotkeys = hotkeys
            # Show popup if search input is still empty and focused
            text = self._search_input.text().strip()
            if not text and self._search_input.hasFocus():
                if not self._hotkey_popup:
                    self._hotkey_popup = HotkeyPopup(self)
                    self._hotkey_popup.hotkey_clicked.connect(self._on_hotkey_clicked)
                self._hotkey_popup.set_hotkeys(hotkeys)
                # Position popup below search input
                input_rect = self._search_input.rect()
                global_pos = self._search_input.mapToGlobal(input_rect.bottomLeft())
                self._hotkey_popup.show_at(global_pos)

    def _on_hotkey_clicked(self, title: str):
        """Handle hotkey button click."""
        self._search_input.setText(title)
        self._on_search()

    def _on_search_text_changed(self, text: str):
        """Handle search text change - show top lists when cleared."""
        # Hide hotkey popup when user starts typing
        if text and self._hotkey_popup and self._hotkey_popup.isVisible():
            self._hotkey_popup.hide()

        if not text and self._current_keyword:
            # Text was cleared, go back to top lists
            self._current_keyword = ""
            self._current_page = 1
            self._grid_page = 1
            self._grid_total = 0
            # Don't clear _current_tracks - keep the top list songs that were already loaded
            self._tabs.hide()
            # Hide back button
            self._fav_back_btn.hide()
            # Clear grid views
            self._singers_page.clear()
            self._albums_page.clear()
            self._playlists_page.clear()
            # Switch to top list page
            self._stack.setCurrentWidget(self._top_list_page)
            # Show favorites and recommendations when returning to main view
            if self._fav_loaded and self._fav_data:
                self._favorites_section.show()
            if self._recommendations_loaded:
                self._recommend_section.show()
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
        # Pop from navigation stack if available
        if self._navigation_stack:
            prev_state = self._navigation_stack.pop()
            page = prev_state.get('page')

            if page == 'playlists':
                # Return to playlist list
                title = prev_state.get('title', '')
                playlists = prev_state.get('data', [])
                self._show_playlist_list_in_detail(title, playlists)
                return
            elif page == 'albums':
                # Return to album list
                title = prev_state.get('title', '')
                albums = prev_state.get('data', [])
                self._show_album_list_in_detail(title, albums)
                return

        # Default behavior: return to previous page based on context
        # If tabs are visible, we came from search results
        # Otherwise, return to top list page
        if self._tabs.isVisible():
            self._stack.setCurrentWidget(self._results_page)
        else:
            self._stack.setCurrentWidget(self._top_list_page)
            # Show favorites and recommendations when returning to main view
            if self._fav_loaded and self._fav_data:
                self._favorites_section.show()
            if self._recommendations_loaded:
                self._recommend_section.show()

    def _on_fav_back_clicked(self):
        """Handle back button click from favorites view."""
        # Hide back button
        self._fav_back_btn.hide()
        # Clear navigation stack when returning to main view
        self._navigation_stack.clear()
        # Show favorites and recommendations
        if self._fav_loaded and self._fav_data:
            self._favorites_section.show()
        if self._recommendations_loaded:
            self._recommend_section.show()
        # Return to top list page
        self._stack.setCurrentWidget(self._top_list_page)

    def _get_cover_url(self, track: OnlineTrack) -> str:
        """Get cover URL for online track."""
        if track.album and track.album.mid:
            return f"https://y.qq.com/music/photo_new/T002R300x300M000{track.album.mid}.jpg"
        return ""

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
                "cover_url": self._get_cover_url(track),
            }
            tracks_data.append((track.mid, metadata))

        # Emit signal to play all tracks, starting from first
        self.play_online_tracks.emit(0, tracks_data)

    def _on_add_all_to_queue_from_detail(self, tracks: List[OnlineTrack]):
        """Handle add all to queue from detail view."""
        tracks_data = []
        for track in tracks:
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
                "cover_url": self._get_cover_url(track),
            }
            tracks_data.append((track.mid, metadata))
        self.add_multiple_to_queue.emit(tracks_data)

    def _on_insert_all_to_queue_from_detail(self, tracks: List[OnlineTrack]):
        """Handle insert all to queue from detail view."""
        tracks_data = []
        for track in tracks:
            metadata = {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
                "cover_url": self._get_cover_url(track),
            }
            tracks_data.append((track.mid, metadata))
        self.insert_multiple_to_queue.emit(tracks_data)

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
                "cover_url": self._get_cover_url(track),
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
            "cover_url": self._get_cover_url(track),
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
                "cover_url": self._get_cover_url(track),
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

        # Add to favorites action
        add_to_favorites_action = menu.addAction(t("add_to_favorites"))
        add_to_favorites_action.triggered.connect(lambda: self._add_selected_to_favorites(tracks))

        # Add to playlist action
        add_to_playlist_action = menu.addAction(t("add_to_playlist"))
        add_to_playlist_action.triggered.connect(lambda: self._add_selected_to_playlist(tracks))

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

    def _add_selected_to_favorites(self, tracks: List[OnlineTrack]):
        """Add selected online tracks to favorites."""
        if not tracks:
            return

        from app.bootstrap import Bootstrap

        added_count = 0

        for track in tracks:
            track_id = self._add_online_track_to_library(track)
            if track_id:
                # Add to favorites
                if self._db:
                    self._db.add_favorite(track_id=track_id)
                    added_count += 1

        if added_count > 0:
            logger.info(f"[OnlineMusicView] Added {added_count} tracks to favorites")
            QMessageBox.information(
                self,
                t("success"),
                t("added_x_tracks_to_favorites").format(count=added_count)
            )

    def _add_selected_to_playlist(self, tracks: List[OnlineTrack]):
        """Add selected online tracks to playlist."""
        if not tracks:
            return

        from app.bootstrap import Bootstrap
        from utils.playlist_utils import add_tracks_to_playlist

        bootstrap = Bootstrap.instance()

        # Add tracks to library first and collect track IDs
        track_ids = []
        for track in tracks:
            track_id = self._add_online_track_to_library(track)
            if track_id:
                track_ids.append(track_id)

        if not track_ids:
            return

        add_tracks_to_playlist(
            self,
            bootstrap.library_service,
            track_ids,
            "[OnlineMusicView]"
        )

    def _add_online_track_to_library(self, track: OnlineTrack) -> Optional[int]:
        """Add online track to library, return track_id."""
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        if not bootstrap.library_service:
            return None

        cover_url = self._get_cover_url(track)

        return bootstrap.library_service.add_online_track(
            song_mid=track.mid,
            title=track.title,
            artist=track.singer_name,
            album=track.album_name,
            duration=float(track.duration),
            cover_url=cover_url
        )

    def _get_cover_url(self, track: OnlineTrack) -> str:
        """Get cover URL for online track."""
        if track.album and track.album.mid:
            return f"https://y.qq.com/music/photo_new/T002R300x300M000{track.album.mid}.jpg"
        return ""

    def _play_selected_tracks(self, tracks: List[OnlineTrack]):
        """Play selected tracks."""
        if not tracks:
            return
        # Play first track and add rest to queue
        self._play_track(tracks[0])
        if len(tracks) > 1:
            tracks_data = []
            for track in tracks[1:]:
                tracks_data.append((track.mid, {
                    "title": track.title,
                    "artist": track.singer_name,
                    "album": track.album_name,
                    "duration": track.duration,
                    "album_mid": track.album.mid if track.album else "",
                    "cover_url": self._get_cover_url(track),
                }))
            self.add_multiple_to_queue.emit(tracks_data)

    def _add_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Add selected tracks to queue."""
        tracks_data = []
        for track in tracks:
            tracks_data.append((track.mid, {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
                "cover_url": self._get_cover_url(track),
            }))
        self.add_multiple_to_queue.emit(tracks_data)

    def _insert_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Insert selected tracks after current playing track."""
        tracks_data = []
        for track in tracks:
            tracks_data.append((track.mid, {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
                "album_mid": track.album.mid if track.album else "",
                "cover_url": self._get_cover_url(track),
            }))
        self.insert_multiple_to_queue.emit(tracks_data)

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

        # Update recommend section
        if hasattr(self, '_recommend_section'):
            self._recommend_section.refresh_ui()

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
"""
Online music view for searching and browsing online music.
"""

import logging
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QThread, QTimer, QStringListModel, QPoint, QEvent
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QStackedWidget,
    QAbstractItemView,
    QMenu,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QCompleter,
    QApplication,
)
from shiboken6 import isValid

from ui.dialogs.message_dialog import MessageDialog
from ui.widgets.recommend_card import RecommendSection
from ui.views.online_tracks_list_view import OnlineTracksListView
from ui.icons import IconName, get_icon
from system.theme import ThemeManager


class CustomQCompleter(QCompleter):
    """自定义QCompleter用于搜索建议."""

    _STYLE_POPUP = """
        QListView {
            background-color: %background_hover%;
            border: 1px solid %border%;
            border-radius: 8px;
            color: %text%;
            selection-background-color: %highlight%;
            selection-color: %background%;
            outline: none;
        }
        QListView::item {
            padding: 8px 12px;
            border-bottom: 1px solid %border%;
        }
        QListView::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
        QListView::item:hover {
            background-color: %border%;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Set themed popup style
        self._apply_theme()

    def _apply_theme(self):
        """Apply themed styles to popup."""
        from system.theme import ThemeManager
        self.popup().setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_POPUP))

    def refresh_theme(self):
        """Refresh popup styles."""
        self._apply_theme()


from domain.online_music import (
    OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist,
    SearchResult, SearchType
)
from services.online import OnlineMusicService, OnlineDownloadService
from system.i18n import t
from system.event_bus import EventBus
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
            elif self._fav_type == "followed_singers":
                result = self._qqmusic_service.get_followed_singers(page=self._page, size=self._num)
            self.fav_ready.emit(self._fav_type, result)
        except Exception as e:
            logger.error(f"Get favorites {self._fav_type} failed: {e}")
            self.fav_ready.emit(self._fav_type, [])


class HotkeyPopup(QWidget):
    """Popup widget for displaying hot search keywords - autocomplete style."""

    hotkey_clicked = Signal(str)  # Emitted when a hotkey is clicked
    clear_history_requested = Signal()  # Emitted when clear history is requested
    delete_history_requested = Signal(str)  # Emitted when delete a history item is requested

    _STYLE_CONTAINER = """
        #hotkeyContainer {
            background-color: %background_hover%;
            border: 1px solid %border%;
            border-radius: 8px;
        }
    """
    _STYLE_TITLE = """
        QLabel {
            color: %highlight%;
            font-size: 13px;
            font-weight: bold;
            padding: 10px 12px 6px 12px;
        }
    """
    _STYLE_TITLE_NO_PADDING = """
        QLabel {
            color: %highlight%;
            font-size: 13px;
            font-weight: bold;
        }
    """
    _STYLE_CLEAR_BTN = """
        QPushButton {
            color: %text_secondary%;
            font-size: 12px;
            border: none;
            padding: 2px 8px;
            background: transparent;
        }
        QPushButton:hover {
            color: %highlight%;
            text-decoration: underline;
        }
    """
    _STYLE_SEPARATOR = "background-color: %border%; border: none; max-height: 1px;"
    _STYLE_HISTORY_LABEL = """
        QLabel {
            color: %text%;
            font-size: 13px;
            background: transparent;
        }
    """
    _STYLE_DELETE_BTN = """
        QPushButton {
            color: %text_secondary%;
            font-size: 12px;
            border: none;
            padding: 2px 8px;
            background: transparent;
        }
        QPushButton:hover {
            color: #ff4444;
            text-decoration: underline;
        }
    """
    _STYLE_HISTORY_ITEM = """
        QWidget {
            background-color: transparent;
            border-radius: 4px;
        }
        QWidget:hover {
            background-color: %border%;
        }
    """
    _STYLE_HOTKEY_ITEM = """
        QLabel {
            color: %text%;
            font-size: 13px;
            padding: 8px 12px;
            border-radius: 4px;
        }
        QLabel:hover {
            background-color: %border%;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self._setup_ui()

        # Register with theme system
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Setup UI components."""
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)

        self._container = QWidget()
        self._container.setObjectName("hotkeyContainer")
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.setSpacing(0)

        self._main_layout.addWidget(self._container)

        # Apply initial theme
        self.refresh_theme()

    def refresh_theme(self):
        """Refresh all styles using current theme tokens."""
        from system.theme import ThemeManager
        tm = ThemeManager.instance()

        # Container
        self._container.setStyleSheet(tm.get_qss(self._STYLE_CONTAINER))

    def set_hotkeys(self, hotkeys: List[Dict[str, Any]]):
        """Set hotkey list."""
        self._clear_container()

        # Title
        title = QLabel(f"🔥 {t('hot_search')}")
        from system.theme import ThemeManager
        title.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TITLE))
        self._container_layout.addWidget(title)

        # Hotkey items
        for item in hotkeys[:10]:
            title_text = item.get('title', '')
            query = item.get('query', title_text)
            if not title_text:
                continue
            self._add_hotkey_item(title_text, query)

        self._adjust_size()

    def set_search_history(self, history: List[str]):
        """Set search history list."""
        self._clear_container()

        # Title with clear button
        title_layout = QHBoxLayout()
        title_layout.setContentsMargins(12, 10, 12, 6)

        title = QLabel(f"📝 {t('search_history')}")
        from system.theme import ThemeManager
        title.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TITLE_NO_PADDING))
        title_layout.addWidget(title)

        title_layout.addStretch()

        clear_btn = QPushButton(t("clear_all"))
        clear_btn.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_CLEAR_BTN))
        clear_btn.setCursor(Qt.PointingHandCursor)
        clear_btn.clicked.connect(self._on_clear_clicked)
        title_layout.addWidget(clear_btn)

        title_widget = QWidget()
        title_widget.setLayout(title_layout)
        self._container_layout.addWidget(title_widget)

        # History items
        for keyword in history:
            if not keyword:
                continue
            self._add_history_item(keyword)

        self._adjust_size()

    def set_combined(self, history: List[str], hotkeys: List[Dict[str, Any]]):
        """Set both search history and hotkeys in one popup."""
        self._clear_container()

        from system.theme import ThemeManager
        tm = ThemeManager.instance()

        # Add search history section
        if history:
            # Title with clear button
            title_layout = QHBoxLayout()
            title_layout.setContentsMargins(12, 10, 12, 6)

            title = QLabel(f"📝 {t('search_history')}")
            title.setStyleSheet(tm.get_qss(self._STYLE_TITLE_NO_PADDING))
            title_layout.addWidget(title)

            title_layout.addStretch()

            clear_btn = QPushButton(t("clear_all"))
            clear_btn.setStyleSheet(tm.get_qss(self._STYLE_CLEAR_BTN))
            clear_btn.setCursor(Qt.PointingHandCursor)
            clear_btn.clicked.connect(self._on_clear_clicked)
            title_layout.addWidget(clear_btn)

            title_widget = QWidget()
            title_widget.setLayout(title_layout)
            self._container_layout.addWidget(title_widget)

            for keyword in history:
                if not keyword:
                    continue
                self._add_history_item(keyword)

        # Add separator if both sections exist
        if history and hotkeys:
            separator = QFrame()
            separator.setFrameShape(QFrame.HLine)
            separator.setStyleSheet(tm.get_qss(self._STYLE_SEPARATOR))
            self._container_layout.addWidget(separator)

        # Add hot search section
        if hotkeys:
            # Title
            hotkey_title = QLabel(f"🔥 {t('hot_search')}")
            hotkey_title.setStyleSheet(tm.get_qss(self._STYLE_TITLE))
            self._container_layout.addWidget(hotkey_title)

            for item in hotkeys[:5]:  # Limit to 5 hotkeys when combined
                title_text = item.get('title', '')
                query = item.get('query', title_text)
                if not title_text:
                    continue
                self._add_hotkey_item(title_text, query)

        self._adjust_size()

    def _add_history_item(self, keyword: str):
        """Add a history item with delete button."""
        from system.theme import ThemeManager
        tm = ThemeManager.instance()

        item_widget = QWidget()
        item_layout = QHBoxLayout(item_widget)
        item_layout.setContentsMargins(12, 4, 8, 4)
        item_layout.setSpacing(8)

        # Keyword label
        label = QLabel(keyword)
        label.setStyleSheet(tm.get_qss(self._STYLE_HISTORY_LABEL))
        item_layout.addWidget(label)

        item_layout.addStretch()

        # Delete button - same style as clear button
        delete_btn = QPushButton(t("delete"))
        delete_btn.setStyleSheet(tm.get_qss(self._STYLE_DELETE_BTN))
        delete_btn.setCursor(Qt.PointingHandCursor)
        delete_btn.clicked.connect(lambda: self._on_delete_clicked(keyword))
        item_layout.addWidget(delete_btn)

        item_widget.setStyleSheet(tm.get_qss(self._STYLE_HISTORY_ITEM))
        item_widget.setCursor(Qt.PointingHandCursor)
        item_widget.mousePressEvent = lambda e: self._on_item_clicked(keyword)

        self._container_layout.addWidget(item_widget)

    def _add_hotkey_item(self, title: str, query: str):
        """Add a hotkey item."""
        from system.theme import ThemeManager
        label = QLabel(f"  {title}")
        label.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_HOTKEY_ITEM))
        label.setCursor(Qt.PointingHandCursor)
        label.mousePressEvent = lambda e: self._on_item_clicked(query)

        self._container_layout.addWidget(label)

    def _clear_container(self):
        """Clear all items from container."""
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_item_clicked(self, query: str):
        """Handle item click."""
        self.hide()
        self.hotkey_clicked.emit(query)

    def _on_clear_clicked(self):
        """Handle clear button click."""
        self.hide()
        self.clear_history_requested.emit()

    def _on_delete_clicked(self, keyword: str):
        """Handle delete button click."""
        self.delete_history_requested.emit(keyword)

    def _adjust_size(self):
        """Adjust popup size to fit content."""
        if self._container_layout.count() == 0:
            self.hide()
            return

        # Force layout update
        self._container_layout.update()
        self._container.adjustSize()
        self.adjustSize()

        # Set a minimum width
        if self.width() < 200:
            self.setMinimumWidth(200)

        # Limit max height
        if self.height() > 400:
            self.setFixedHeight(400)

    def show_at(self, global_pos: QPoint, input_width: int = 0):
        """Show popup at global position."""
        if input_width > 0:
            self.setMinimumWidth(input_width)
            self.setMaximumWidth(input_width)
        self.move(global_pos)
        self.show()
        self.raise_()  # Ensure it's on top


class SearchInputWithHotkey(QLineEdit):
    """Custom search input that emits focus events."""

    focus_gained = Signal()
    focus_lost = Signal()
    escape_pressed = Signal()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.focus_gained.emit()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_lost.emit()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            # Emit escape signal and accept the event
            self.escape_pressed.emit()
            event.accept()
        else:
            # Pass other keys to parent
            super().keyPressEvent(event)


class OnlineMusicView(QWidget):
    """View for searching and browsing online music."""

    # Signals
    play_online_track = Signal(str, str, object)  # (song_mid, local_path, metadata_dict)
    insert_to_queue = Signal(str, object)  # (song_mid, metadata_dict)
    add_to_queue = Signal(str, object)  # (song_mid, metadata_dict)
    add_multiple_to_queue = Signal(list)  # list of (song_mid, metadata_dict)
    insert_multiple_to_queue = Signal(list)  # list of (song_mid, metadata_dict)
    play_online_tracks = Signal(int, list)  # (start_index, list of (song_mid, metadata_dict))

    _STYLE_TITLE = "color: %highlight%; font-size: 24px; font-weight: bold;"
    _STYLE_STATUS_LABEL = "color: %text_secondary%; font-size: 12px;"
    _STYLE_SEARCH_INPUT = """
        QLineEdit {
            background-color: %background_hover%;
            color: %text%;
            border: 2px solid %border%;
            border-radius: 25px;
            padding: 10px 20px;
            font-size: 14px;
        }
        QLineEdit:focus {
            border: 2px solid %highlight%;
            background-color: %background_alt%;
        }
        QLineEdit::placeholder {
            color: %text_secondary%;
        }
        QLineEdit::clear-button {
            subcontrol-origin: padding;
            subcontrol-position: right;
            width: 20px;
            height: 20px;
            margin-right: 10px;
            border-radius: 10px;
            background-color: %border%;
        }
        QLineEdit::clear-button:hover {
            background-color: %text_secondary%;
            border: 1px solid %text%;
            cursor: pointer;
        }
        QLineEdit::clear-button:pressed {
            background-color: %background_hover%;
        }
    """
    _STYLE_TABS = """
        QTabBar::tab {
            background: transparent;
            color: %text_secondary%;
            padding: 8px 20px;
            border-bottom: 2px solid transparent;
        }
        QTabBar::tab:selected {
            color: %highlight%;
            border-bottom: 2px solid %highlight%;
        }
        QTabBar::tab:hover {
            color: %highlight%;
        }
    """
    _STYLE_RANKINGS_TITLE = "color: %highlight%; font-size: 16px; font-weight: bold;"
    _STYLE_FAV_BACK_BTN = """
        QPushButton {
            background-color: transparent;
            color: %highlight%;
            border: none;
            font-size: 14px;
            font-weight: bold;
            padding: 4px 8px;
        }
        QPushButton:hover {
            color: %highlight_hover%;
        }
    """
    _STYLE_RESULTS_INFO = "color: %text_secondary%; font-size: 12px;"
    _STYLE_SONGS_TABLE = """
        QTableWidget#songsTable {
            background-color: %background_alt%;
            border: none;
            border-radius: 8px;
            gridline-color: %background_hover%;
        }
        QTableWidget#songsTable::item {
            padding: 12px 8px;
            color: %text%;
            border: none;
            border-bottom: 1px solid %background_hover%;
        }
        QTableWidget#songsTable::item:alternate {
            background-color: %background_hover%;
        }
        QTableWidget#songsTable::item:!alternate {
            background-color: %background_alt%;
        }
        QTableWidget#songsTable::item:selected {
            background-color: %highlight%;
            color: %background%;
            font-weight: 500;
        }
        QTableWidget#songsTable::item:selected:!alternate {
            background-color: %highlight%;
        }
        QTableWidget#songsTable::item:selected:alternate {
            background-color: %highlight_hover%;
        }
        QTableWidget#songsTable::item:hover {
            background-color: %border%;
        }
        QTableWidget#songsTable::item:selected:hover {
            background-color: %highlight_hover%;
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
            background-color: %background_hover%;
            color: %highlight%;
            padding: 14px 12px;
            border: none;
            border-bottom: 2px solid %highlight%;
            font-weight: bold;
            font-size: 12px;
            letter-spacing: 0.5px;
        }
        QTableWidget#songsTable QTableCornerButton::section {
            background-color: %background_hover%;
            border: none;
            border-right: 1px solid %border%;
            border-bottom: 2px solid %highlight%;
        }
        QTableWidget#songsTable QScrollBar:vertical {
            background-color: %background_alt%;
            width: 12px;
            border-radius: 6px;
            margin: 0px;
        }
        QTableWidget#songsTable QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 40px;
        }
        QTableWidget#songsTable QScrollBar::handle:vertical:hover {
            background-color: %text_secondary%;
        }
        QTableWidget#songsTable QScrollBar:horizontal {
            background-color: %background_alt%;
            height: 12px;
            border-radius: 6px;
        }
        QTableWidget#songsTable QScrollBar::handle:horizontal {
            background-color: %border%;
            border-radius: 6px;
            min-width: 40px;
        }
        QTableWidget#songsTable QScrollBar::handle:horizontal:hover {
            background-color: %text_secondary%;
        }
        QTableWidget#songsTable QScrollBar::add-line, QScrollBar::sub-line {
            height: 0px;
            width: 0px;
        }
    """
    _STYLE_PAGE_LABEL = "color: %text_secondary%; padding: 0 10px;"
    _STYLE_BUTTONS = """
        QPushButton {
            background: %background_alt%;
            color: %text%;
            border: none;
            padding: 8px 15px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background: %border%;
        }
        QPushButton:pressed {
            background: %text_secondary%;
        }
        QListWidget {
            background: %background_alt%;
            border: 1px solid %border%;
            border-radius: 4px;
        }
        QListWidget::item {
            padding: 10px;
            color: %text%;
        }
        QListWidget::item:selected {
            background: %highlight%;
            color: %background%;
        }
        QListWidget::item:hover {
            background: %background_hover%;
        }
        QListWidget::item:selected:hover {
            background-color: %highlight_hover%;
            color: %background%;
        }
    """
    _STYLE_MENU = """
        QMenu {
            background: %background_hover%;
            color: %text%;
            border: 1px solid %border%;
        }
        QMenu::item:selected {
            background: %highlight%;
            color: %background%;
        }
    """

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
        self._search_request_id = 0
        self._top_list_worker: Optional[TopListWorker] = None
        self._completion_worker: Optional[CompletionWorker] = None
        self._completion_request_id = 0
        self._completion_timer: Optional[QTimer] = None
        self._selected_top_id: Optional[int] = None
        self._top_lists_loaded = False  # Track if top lists have been loaded
        self._is_top_list_view = True  # True when viewing top list, False when viewing search results

        # Hotkey state
        self._hotkey_worker: Optional[HotkeyWorker] = None
        self._hotkey_request_id = 0
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
        self._focus_filter_registered = False
        self._register_focus_clear_filter()

        # Register with theme system
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)
        self.refresh_theme()

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
            qqmusic_service=self._qqmusic_service,
            parent=self
        )
        self._detail_view.back_requested.connect(self._on_back_from_detail)
        # Connect play_all and add_all_to_queue signals
        self._detail_view.play_all.connect(self._on_play_all_from_detail)
        self._detail_view.insert_all_to_queue.connect(self._on_insert_all_to_queue_from_detail)
        self._detail_view.add_all_to_queue.connect(self._on_add_all_to_queue_from_detail)
        # Connect all tracks signals (from all pages)
        self._detail_view.play_all_tracks.connect(self._on_play_all_from_detail)
        self._detail_view.insert_all_tracks_to_queue.connect(self._on_insert_all_to_queue_from_detail)
        self._detail_view.add_all_tracks_to_queue.connect(self._on_add_all_to_queue_from_detail)
        # Connect album click from artist detail view
        self._detail_view.album_clicked.connect(self._on_album_clicked)
        self._stack.addWidget(self._detail_view)

        layout.addWidget(self._stack, 1)  # Give stretch factor so it doesn't push other widgets

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

    def closeEvent(self, event):
        """Handle close event and unregister global event filter."""
        self._unregister_focus_clear_filter()
        super().closeEvent(event)

    def _register_focus_clear_filter(self):
        """Install app-level event filter for clearing search focus on outside click."""
        app = QApplication.instance()
        if app and not self._focus_filter_registered:
            app.installEventFilter(self)
            self._focus_filter_registered = True

    def _unregister_focus_clear_filter(self):
        """Remove app-level event filter."""
        app = QApplication.instance()
        if app and self._focus_filter_registered:
            app.removeEventFilter(self)
            self._focus_filter_registered = False

    def eventFilter(self, watched, event):
        """Clear search input focus when clicking outside search-related popups."""
        if (
            event.type() == QEvent.MouseButtonPress
            and hasattr(self, "_search_input")
            and self._search_input
            and self._search_input.hasFocus()
            and self.isVisible()
        ):
            global_pos = event.globalPosition().toPoint()
            clicked_widget = QApplication.widgetAt(global_pos)
            if clicked_widget and not self._is_search_related_widget(clicked_widget):
                self._search_input.clearFocus()

        return super().eventFilter(watched, event)

    def _is_search_related_widget(self, widget: QWidget) -> bool:
        """Return whether clicked widget belongs to search input or its related popups."""
        if widget is self._search_input or self._search_input.isAncestorOf(widget):
            return True

        if (
            self._hotkey_popup
            and (widget is self._hotkey_popup or self._hotkey_popup.isAncestorOf(widget))
        ):
            return True

        if self._completer:
            popup = self._completer.popup()
            if popup and (widget is popup or popup.isAncestorOf(widget)):
                return True

        return False

    def _create_header(self) -> QWidget:
        """Create header with QQ Music login status."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        self._online_music_title = QLabel(t("online_music"))
        layout.addWidget(self._online_music_title)

        layout.addStretch()

        # QQ Music login status
        self._login_status_label = QLabel()
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
        self._search_input.escape_pressed.connect(self._on_escape_pressed)

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
        tabs.setCursor(Qt.PointingHandCursor)

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
        left_layout.addWidget(self._rankings_title)

        self._top_list_list = QListWidget()
        self._top_list_list.setObjectName("topListList")
        self._top_list_list.setMouseTracking(True)
        self._top_list_list.setCursor(Qt.PointingHandCursor)
        self._top_list_list.currentRowChanged.connect(self._on_top_list_selected)
        left_layout.addWidget(self._top_list_list)

        layout.addWidget(left_widget, 1)

        # Right: songs in selected top list
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 0, 0, 0)

        # Header with title and view toggle
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        self._top_list_title = QLabel(t("select_ranking"))
        header_layout.addWidget(self._top_list_title)

        header_layout.addStretch()

        # View toggle button
        self._ranking_view_toggle_btn = QPushButton()
        self._ranking_view_toggle_btn.setFixedSize(32, 32)
        self._ranking_view_toggle_btn.setToolTip(t("toggle_view"))
        self._ranking_view_toggle_btn.setCursor(Qt.PointingHandCursor)
        self._ranking_view_toggle_btn.clicked.connect(self._toggle_ranking_view_mode)
        header_layout.addWidget(self._ranking_view_toggle_btn)

        right_layout.addLayout(header_layout)

        # Stacked widget for table and list views
        self._ranking_stacked_widget = QStackedWidget()

        self._top_songs_table = self._create_songs_table()
        self._ranking_stacked_widget.addWidget(self._top_songs_table)

        self._ranking_list_view = OnlineTracksListView()
        self._ranking_list_view.track_activated.connect(self._on_ranking_track_activated)
        self._ranking_list_view.play_requested.connect(self._play_selected_tracks)
        self._ranking_list_view.insert_to_queue_requested.connect(self._insert_selected_to_queue)
        self._ranking_list_view.add_to_queue_requested.connect(self._add_selected_to_queue)
        self._ranking_list_view.add_to_playlist_requested.connect(self._add_selected_to_playlist)
        self._ranking_list_view.favorites_toggle_requested.connect(self._on_ranking_favorites_toggle)
        self._ranking_list_view.download_requested.connect(self._download_selected_tracks)
        self._ranking_list_view.favorite_toggled.connect(self._on_ranking_favorite_toggled)
        self._ranking_stacked_widget.addWidget(self._ranking_list_view)

        right_layout.addWidget(self._ranking_stacked_widget)

        layout.addWidget(right_widget, 3)

        # Load view mode preference
        self._load_ranking_view_mode()

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
        self._fav_back_btn.clicked.connect(self._on_fav_back_clicked)
        self._fav_back_btn.hide()
        header_layout.addWidget(self._fav_back_btn)

        # Results info
        self._results_info = QLabel()
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
        layout.addWidget(self._page_label)

        self._next_btn = QPushButton(t("next_page") + " →")
        self._next_btn.setFixedHeight(36)
        self._next_btn.setCursor(Qt.PointingHandCursor)
        self._next_btn.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_btn)

        layout.addStretch()

        return widget

    def refresh_theme(self):
        """Refresh all styles using current theme tokens."""
        from system.theme import ThemeManager
        tm = ThemeManager.instance()

        # Main widget styles
        self.setStyleSheet(tm.get_qss(self._STYLE_BUTTONS))

        # Header
        self._online_music_title.setStyleSheet(tm.get_qss(self._STYLE_TITLE))
        self._login_status_label.setStyleSheet(tm.get_qss(self._STYLE_STATUS_LABEL))

        # Search input
        self._search_input.setStyleSheet(tm.get_qss(self._STYLE_SEARCH_INPUT))

        # Tabs
        self._tabs.setStyleSheet(tm.get_qss(self._STYLE_TABS))

        # Top list page
        self._rankings_title.setStyleSheet(tm.get_qss(self._STYLE_RANKINGS_TITLE))
        self._top_list_title.setStyleSheet(tm.get_qss(self._STYLE_RANKINGS_TITLE))

        # Results page
        self._fav_back_btn.setStyleSheet(tm.get_qss(self._STYLE_FAV_BACK_BTN))
        self._results_info.setStyleSheet(tm.get_qss(self._STYLE_RESULTS_INFO))

        # Songs tables
        self._top_songs_table.setStyleSheet(tm.get_qss(self._STYLE_SONGS_TABLE))
        self._results_table.setStyleSheet(tm.get_qss(self._STYLE_SONGS_TABLE))

        # Pagination
        self._page_label.setStyleSheet(tm.get_qss(self._STYLE_PAGE_LABEL))

        # Refresh completer popup
        if hasattr(self, '_completer') and self._completer:
            self._completer.refresh_theme()

        # Refresh hotkey popup
        if self._hotkey_popup:
            self._hotkey_popup.refresh_theme()

    def _refresh_qqmusic_service(self):
        """Refresh QQ Music service with current credentials."""
        import json
        from services.cloud.qqmusic.qqmusic_service import QQMusicService

        qqmusic_credential = self._config.get("qqmusic.credential") if self._config else None
        if qqmusic_credential:
            try:
                cred_dict = json.loads(qqmusic_credential) if isinstance(qqmusic_credential,
                                                                         str) else qqmusic_credential
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
            MessageDialog.information(self, t("logout"), t("logout_success"))
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
            ("newsong", t("new_songs")),
            ("songlist", t("recommend_playlists")),
        ]

        for recommend_type, title in recommend_types:
            worker = RecommendWorker(self._qqmusic_service, recommend_type)
            worker.recommend_ready.connect(self._on_recommend_ready)
            self._recommend_workers.append(worker)
            worker.start()

    def _on_recommend_ready(self, recommend_type: str, data: Any):
        """Handle recommendation data ready."""
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
            ("newsong", t("new_songs")),
            ("songlist", t("recommend_playlists")),
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

        if cards:
            self._recommend_section.load_recommendations(cards)
            # Show recommendations section after loading
            self._recommend_section.show()

    def _load_favorites(self):
        """Load user's favorites counts and display 4 summary cards."""
        if self._fav_loaded:
            return

        if not self._qqmusic_service or not self._qqmusic_service._credential:
            return

        self._fav_loaded = True
        self._favorites_section.show_loading()
        self._fav_data = {}  # Store data for click handling

        for fav_type in ["fav_songs", "created_playlists", "fav_playlists", "fav_albums", "followed_singers"]:
            worker = FavWorker(self._qqmusic_service, fav_type)
            worker.fav_ready.connect(self._on_fav_ready)
            self._fav_workers.append(worker)
            worker.start()

    def _on_fav_ready(self, fav_type: str, data: list):
        """Handle favorites data ready - store for later use."""
        self._fav_data[fav_type] = data

        # Check if all 5 types loaded (initial load)
        if len(self._fav_data) == 5:
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

        # Card 5: 关注歌手
        followed_singers = self._fav_data.get("followed_singers", [])
        cards.append({
            "id": "followed_singers",
            "title": t("followed_singers"),
            "subtitle": f"{len(followed_singers)} {t('singers')}",
            "cover_url": self._get_random_cover(followed_singers),
            "card_type": "followed_singers",
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

                # Get a random cover from all items
                cover_url = self._get_random_cover_from_items(data, recommend_type)
                playlist_id = None

                # Handle different response structures based on type
                if recommend_type == 'songlist':
                    # Playlist structure: {'Playlist': {...}, 'WhereFrom': ..., 'ext': ...}
                    # or direct structure with tid/id/disstid

                    playlist_info = first_item.get('Playlist', {})
                    if isinstance(playlist_info, dict) and playlist_info:

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
                            playlist_id = playlist_info.get('tid') or playlist_info.get('id') or playlist_info.get(
                                'disstid')

                    else:
                        # Try direct structure - check for various ID fields
                        playlist_id = (first_item.get('tid') or first_item.get('id') or
                                       first_item.get('disstid') or first_item.get('dissid'))

                elif recommend_type == 'radar':
                    # Radar structure: {'Track': {...}, 'Abt': ..., 'Ext': ...}
                    # Cover is already extracted by _get_random_cover_from_items
                    pass

                elif recommend_type == 'home_feed':
                    # Home feed returns recommendation cards (playlists, rankings, songs)
                    # Each card has type: 200=song, 500=playlist, 700=guess, 1000=ranking
                    playlist_id = first_item.get('id')

                else:
                    # Song structure: {'album': {...}, 'singer': [...], ...}
                    # This handles guess, newsong types

                    # Cover is already extracted by _get_random_cover_from_items
                    # Get playlist ID if available (for playlist-based recommendations)
                    playlist_id = (first_item.get('id') or first_item.get('disstid') or
                                   first_item.get('tid') or first_item.get('playlist_id'))

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

                # Try to find the main content
                content = None
                for key in ['songlist', 'songs', 'list', 'data', 'items', 'playlist']:
                    if key in data:
                        content = data[key]
                        break

                if content and isinstance(content, list) and content:
                    first_item = content[0]
                    if isinstance(first_item, dict):
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
        elif card_type == "followed_singers":
            singers = self._fav_data.get("followed_singers", [])
            self._show_singer_list_in_detail(t("followed_singers"), singers)

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
        online_playlists = [OnlinePlaylist(
                id=str(pl.get("id", "")),
                title=pl.get("title", ""),
                cover_url=pl.get("cover_url", ""),
                creator=pl.get("creator", ""),
                song_count=pl.get("song_count", 0),
                play_count=pl.get("play_count", 0),
            ) for pl in playlists]

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

    def _show_singer_list_in_detail(self, title: str, singers: list):
        """Show a list of followed singers in the grid view."""
        from domain.online_music import OnlineArtist

        # Clear previous data
        self._singers_page.clear()

        # Convert dicts to OnlineArtist objects
        artists = [OnlineArtist(
                mid=singer.get("mid", ""),
                name=singer.get("name", ""),
                avatar_url=singer.get("cover_url", ""),
                fan_count=singer.get("fan_count", 0),
            ) for singer in singers]

        self._singers_page.load_data(artists)
        self._results_info.setText(title)
        self._tabs.hide()
        self._is_top_list_view = False
        self._results_stack.setCurrentWidget(self._singers_page)
        self._stack.setCurrentWidget(self._results_page)

        # Push navigation state
        self._navigation_stack.append({
            'page': 'singers',
            'title': title,
            'data': singers
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

                        # Try to get play count
                        play_count = 0
                        if 'basic' in playlist_info:
                            basic = playlist_info.get('basic', {})
                            if isinstance(basic, dict):
                                play_count = (basic.get('play_cnt') or basic.get('listennum') or
                                              basic.get('play_count') or 0)
                        if not play_count and 'content' in playlist_info:
                            content = playlist_info.get('content', {})
                            if isinstance(content, dict):
                                play_count = (content.get('play_cnt') or content.get('listennum') or
                                              content.get('play_count') or 0)
                        if not play_count:
                            play_count = (playlist_info.get('play_cnt') or playlist_info.get('listennum') or
                                          playlist_info.get('play_count') or 0)

                        if playlist_id:
                            playlists.append({
                                'id': str(playlist_id),
                                'title': playlist_title or '',
                                'cover_url': cover_url or '',
                                'song_count': song_count,
                                'play_count': play_count or 0,
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
            self._search_input.clearFocus()
            return

        # Save to search history
        if self._config:
            self._config.add_search_history(keyword)

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
        if not text:
            # Always show popup when gaining focus and input is empty
            # Even if popup is already visible
            self._show_hotkey_popup()

    def _on_search_focus_lost(self):
        """Handle search input focus lost - hide hotkey popup."""
        # Delay hiding to allow click on hotkey items
        QTimer.singleShot(200, self._hide_hotkey_popup)

    def _show_hotkey_popup(self):
        """Show hotkey popup below search input with search history and hotkeys."""
        if not self._hotkey_popup:
            self._hotkey_popup = HotkeyPopup(self)
            self._hotkey_popup.hotkey_clicked.connect(self._on_hotkey_clicked)
            self._hotkey_popup.clear_history_requested.connect(self._on_clear_history)
            self._hotkey_popup.delete_history_requested.connect(self._on_delete_history_item)

        # Get search history
        history = self._config.get_search_history() if self._config else []

        # If we have both history and hotkeys cached, show combined
        if history and self._hotkeys:
            self._hotkey_popup.set_combined(history, self._hotkeys)
            input_rect = self._search_input.rect()
            global_pos = self._search_input.mapToGlobal(input_rect.bottomLeft())
            self._hotkey_popup.show_at(global_pos, self._search_input.width())
        # If we have history but no hotkeys, show history and load hotkeys
        elif history:
            self._hotkey_popup.set_search_history(history)
            input_rect = self._search_input.rect()
            global_pos = self._search_input.mapToGlobal(input_rect.bottomLeft())
            self._hotkey_popup.show_at(global_pos, self._search_input.width())
            # Load hotkeys in background
            if not self._hotkeys and self._qqmusic_service:
                self._load_hotkeys()
        # If we have hotkeys but no history, show hotkeys
        elif self._hotkeys:
            self._hotkey_popup.set_hotkeys(self._hotkeys)
            input_rect = self._search_input.rect()
            global_pos = self._search_input.mapToGlobal(input_rect.bottomLeft())
            self._hotkey_popup.show_at(global_pos, self._search_input.width())
        # No history and no hotkeys - load hotkeys
        elif self._qqmusic_service:
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

        self._hotkey_request_id += 1
        request_id = self._hotkey_request_id

        self._hotkey_worker = HotkeyWorker(self._qqmusic_service)
        self._hotkey_worker.hotkey_ready.connect(
            lambda hotkeys, rid=request_id: self._on_hotkey_ready(hotkeys, rid)
        )
        self._hotkey_worker.start()

    def _on_hotkey_ready(
            self,
            hotkeys: List[Dict[str, Any]],
            request_id: int | None = None
    ):
        """Handle hotkey suggestions ready."""
        if request_id is not None and request_id != self._hotkey_request_id:
            return

        if hotkeys:
            self._hotkeys = hotkeys
            # Show popup if search input is still empty and focused
            text = self._search_input.text().strip()
            if not text and self._search_input.hasFocus():
                if not self._hotkey_popup:
                    self._hotkey_popup = HotkeyPopup(self)
                    self._hotkey_popup.hotkey_clicked.connect(self._on_hotkey_clicked)
                    self._hotkey_popup.clear_history_requested.connect(self._on_clear_history)
                    self._hotkey_popup.delete_history_requested.connect(self._on_delete_history_item)

                # Get search history and show combined
                history = self._config.get_search_history() if self._config else []
                if history and hotkeys:
                    self._hotkey_popup.set_combined(history, hotkeys)
                elif history:
                    self._hotkey_popup.set_search_history(history)
                else:
                    self._hotkey_popup.set_hotkeys(hotkeys)

                # Position popup below search input
                input_rect = self._search_input.rect()
                global_pos = self._search_input.mapToGlobal(input_rect.bottomLeft())
                self._hotkey_popup.show_at(global_pos, self._search_input.width())

    def _on_hotkey_clicked(self, title: str):
        """Handle hotkey button click."""
        self._search_input.setText(title)
        self._on_search()

    def _on_clear_history(self):
        """Handle clear all search history."""
        if self._config:
            self._config.clear_search_history()
            # Refresh popup if it's visible
            if self._hotkey_popup and self._hotkey_popup.isVisible():
                self._show_hotkey_popup()

    def _on_delete_history_item(self, keyword: str):
        """Handle delete a search history item."""
        if self._config:
            self._config.remove_search_history_item(keyword)
            # Refresh popup
            self._show_hotkey_popup()

    def _on_escape_pressed(self):
        """Handle Escape key press - hide both hotkey popup and completer popup, then clear focus."""
        # Hide hotkey popup
        if self._hotkey_popup and self._hotkey_popup.isVisible():
            self._hotkey_popup.hide()

        # Hide completer popup
        if self._completer and self._completer.popup().isVisible():
            self._completer.popup().hide()

        # Clear focus from search input
        self._search_input.clearFocus()

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

        self._completion_request_id += 1
        request_id = self._completion_request_id

        # Note: Completion API works without login too
        self._completion_worker = CompletionWorker(self._qqmusic_service, keyword)
        self._completion_worker.completion_ready.connect(
            lambda suggestions, rid=request_id: self._on_completion_ready(suggestions, rid)
        )
        self._completion_worker.start()

    def _on_completion_ready(
            self,
            suggestions: List[Dict[str, Any]],
            request_id: int | None = None
    ):
        """Handle completion suggestions ready."""
        if request_id is not None and request_id != self._completion_request_id:
            return

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
        self._search_request_id += 1
        request_id = self._search_request_id

        self._search_worker = SearchWorker(
            self._service,
            self._current_keyword,
            self._current_search_type,
            self._current_page,
            30
        )
        self._search_worker.search_completed.connect(
            lambda result, rid=request_id: self._on_search_completed(result, rid)
        )
        self._search_worker.search_failed.connect(
            lambda error, rid=request_id: self._on_search_failed(error, rid)
        )
        self._search_worker.start()

    def _on_search_completed(self, result: SearchResult, request_id: int | None = None):
        """Handle search completion."""
        if request_id is not None and request_id != self._search_request_id:
            return

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

    def _on_search_failed(self, error: str, request_id: int | None = None):
        """Handle search failure."""
        if request_id is not None and request_id != self._search_request_id:
            return

        logger.error(f"Search failed: {error}")
        MessageDialog.warning(self, t("error"), t("search_failed") + f": {error}")

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
        # Push navigation state if we're coming from search results or grid view
        if self._stack.currentWidget() in [self._results_page]:
            self._navigation_stack.append({
                'page': 'results',
                'tab': 'artists' if self._results_stack.currentWidget() == self._singers_page else 'other'
            })
        self._detail_view.load_artist(artist.mid, artist.name)
        self._stack.setCurrentWidget(self._detail_view)

    def _on_album_clicked(self, album: OnlineAlbum):
        """Handle album click - show album detail view."""
        # Push navigation state if we're coming from search results or detail view
        current_widget = self._stack.currentWidget()
        if current_widget == self._results_page:
            self._navigation_stack.append({
                'page': 'results',
                'tab': 'albums' if self._results_stack.currentWidget() == self._albums_page else 'other'
            })
        elif current_widget == self._detail_view:
            # Coming from artist detail - push detail state
            self._navigation_stack.append({
                'page': 'detail',
                'type': self._detail_view._detail_type,
                'mid': self._detail_view._mid
            })
        self._detail_view.load_album(album.mid, album.name, album.singer_name)
        self._stack.setCurrentWidget(self._detail_view)

    def _on_playlist_clicked(self, playlist: OnlinePlaylist):
        """Handle playlist click - show playlist detail view."""
        # Push navigation state if we're coming from search results or detail view
        current_widget = self._stack.currentWidget()
        if current_widget == self._results_page:
            self._navigation_stack.append({
                'page': 'results',
                'tab': 'playlists' if self._results_stack.currentWidget() == self._playlists_page else 'other'
            })
        elif current_widget == self._detail_view:
            # Coming from artist detail - push detail state
            self._navigation_stack.append({
                'page': 'detail',
                'type': self._detail_view._detail_type,
                'mid': self._detail_view._mid
            })
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
        self._search_request_id += 1
        request_id = self._search_request_id

        self._search_worker = SearchWorker(
            self._service,
            self._current_keyword,
            search_type,
            self._grid_page,
            self._grid_page_size
        )
        self._search_worker.search_completed.connect(
            lambda result, rid=request_id: self._on_load_more_completed(result, search_type, rid)
        )
        self._search_worker.search_failed.connect(
            lambda error, rid=request_id: self._on_load_more_failed(error, rid)
        )
        self._search_worker.start()

    def _on_load_more_completed(
            self,
            result: SearchResult,
            search_type: str,
            request_id: int | None = None
    ):
        """Handle load more completion."""
        if request_id is not None and request_id != self._search_request_id:
            return

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

    def _on_load_more_failed(self, error: str, request_id: int | None = None):
        """Handle load more failure."""
        if request_id is not None and request_id != self._search_request_id:
            return

        logger.error(f"Load more failed: {error}")
        # Hide loading on all grid views
        self._singers_page.hide_loading()
        self._albums_page.hide_loading()
        self._playlists_page.hide_loading()
        MessageDialog.warning(self, t("error"), t("search_failed") + f": {error}")

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
            elif page == 'results':
                # Return to search results
                self._stack.setCurrentWidget(self._results_page)
                # Restore correct tab if specified
                tab = prev_state.get('tab', '')
                if tab == 'artists':
                    self._results_stack.setCurrentWidget(self._singers_page)
                elif tab == 'albums':
                    self._results_stack.setCurrentWidget(self._albums_page)
                elif tab == 'playlists':
                    self._results_stack.setCurrentWidget(self._playlists_page)
                return
            elif page == 'detail':
                # Return to previous detail view (e.g., artist detail)
                detail_type = prev_state.get('type', '')
                mid = prev_state.get('mid')
                if detail_type == 'artist' and mid:
                    # Reload artist detail
                    self._detail_view.load_artist(mid)
                    return
                elif detail_type == 'album' and mid:
                    # Reload album detail
                    self._detail_view.load_album(mid)
                    return
                elif detail_type == 'playlist' and mid:
                    # Reload playlist detail
                    self._detail_view.load_playlist(mid)
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

    def _build_track_metadata(self, track: OnlineTrack) -> Dict[str, Any]:
        """Build standardized metadata payload for online track playback/queue actions."""
        return {
            "title": track.title,
            "artist": track.singer_name,
            "album": track.album_name,
            "duration": track.duration,
            "album_mid": track.album.mid if track.album else "",
            "cover_url": self._get_cover_url(track),
        }

    def _build_tracks_payload(self, tracks: List[OnlineTrack]) -> List[tuple[str, Dict[str, Any]]]:
        """Build `(song_mid, metadata)` payload list while preserving input order."""
        return [(track.mid, self._build_track_metadata(track)) for track in tracks]

    def _on_play_all_from_detail(self, tracks: List[OnlineTrack], index: int = 0):
        """Handle play all from detail view."""
        if not tracks:
            return

        # Build list of (song_mid, metadata) for all tracks
        tracks_data = self._build_tracks_payload(tracks)

        # Emit signal to play all tracks, starting from first
        self.play_online_tracks.emit(index, tracks_data)

    def _on_add_all_to_queue_from_detail(self, tracks: List[OnlineTrack]):
        """Handle add all to queue from detail view."""
        tracks_data = self._build_tracks_payload(tracks)
        self.add_multiple_to_queue.emit(tracks_data)

    def _on_insert_all_to_queue_from_detail(self, tracks: List[OnlineTrack]):
        """Handle insert all to queue from detail view."""
        tracks_data = self._build_tracks_payload(tracks)
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
        tracks_data = self._build_tracks_payload(self._current_tracks)

        self.play_online_tracks.emit(start_index, tracks_data)

    def _play_track(self, track: OnlineTrack):
        """Play an online track."""
        # Build metadata from track info
        metadata = self._build_track_metadata(track)

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
        self._download_progress.canceled.connect(lambda: self._cancel_download(track.mid))

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

        # Skip if download was cancelled
        if hasattr(self, '_download_worker') and self._download_worker._cancelled:
            logger.info(f"Download cancelled: {song_mid}")
            return

        if song_mid == track.mid and local_path:
            logger.info(f"Emitting play_online_track: {song_mid}, {local_path}")
            # Build metadata from track info
            metadata = self._build_track_metadata(track)
            self.play_online_track.emit(song_mid, local_path, metadata)
        else:
            logger.warning(f"Download failed or mismatch: mid={song_mid}, track.mid={track.mid}, path={local_path}")
            MessageDialog.warning(self, t("error"), t("download_failed"))

    def _cancel_download(self, song_mid: str):
        """Cancel ongoing download."""
        if hasattr(self, '_download_worker') and self._download_worker:
            self._download_worker.cancel()
        if hasattr(self, '_download_progress') and self._download_progress:
            self._download_progress.close()

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
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_MENU))

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

        added_count = 0
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        favorites_service = bootstrap.favorites_service

        for track in tracks:
            track_id = self._add_online_track_to_library(track)
            if track_id:
                favorites_service.add_favorite(track_id=track_id)
                added_count += 1
                # Update ranking view UI if track is visible
                if hasattr(self, '_ranking_list_view'):
                    self._ranking_list_view.set_track_favorite(track.mid, True)

        if added_count > 0:
            logger.info(f"[OnlineMusicView] Added {added_count} tracks to favorites")
            MessageDialog.information(
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

    def _play_selected_tracks(self, tracks: List[OnlineTrack]):
        """Play selected tracks."""
        if not tracks:
            return
        # Play first track and add rest to queue
        self._play_track(tracks[0])
        if len(tracks) > 1:
            tracks_data = self._build_tracks_payload(tracks[1:])
            self.add_multiple_to_queue.emit(tracks_data)

    def _add_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Add selected tracks to queue."""
        tracks_data = self._build_tracks_payload(tracks)
        self.add_multiple_to_queue.emit(tracks_data)

    def _insert_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Insert selected tracks after current playing track."""
        tracks_data = self._build_tracks_payload(tracks)
        self.insert_multiple_to_queue.emit(tracks_data)

    def _load_top_lists(self):
        """Load top lists."""
        self._stop_worker(self._top_list_worker, "top_list_worker")

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
        self._stop_worker(self._top_list_worker, "top_list_worker")

        self._top_list_worker = TopListWorker(self._service, self._selected_top_id)
        self._top_list_worker.top_songs_loaded.connect(self._on_top_songs_loaded)
        self._top_list_worker.start()

    def _stop_worker(self, worker, worker_name: str):
        """Stop a running worker cooperatively without force-terminating threads."""
        if not worker or not isValid(worker):
            return
        if not worker.isRunning():
            return

        try:
            worker.requestInterruption()
        except Exception:
            logger.debug(f"[OnlineMusicView] requestInterruption failed for {worker_name}", exc_info=True)

        try:
            worker.quit()
        except Exception:
            logger.debug(f"[OnlineMusicView] quit failed for {worker_name}", exc_info=True)

        try:
            if not worker.wait(1500):
                logger.warning(f"[OnlineMusicView] Worker did not stop in time: {worker_name}")
        except Exception:
            logger.debug(f"[OnlineMusicView] wait failed for {worker_name}", exc_info=True)

    def _on_top_songs_loaded(self, top_id: int, songs: List[OnlineTrack]):
        """Handle top songs loaded."""
        if top_id != self._selected_top_id:
            return

        self._current_tracks = songs
        self._is_top_list_view = True  # Now viewing top list
        self._display_top_songs(songs)

    def _display_top_songs(self, songs: List[OnlineTrack]):
        """Display top songs in both table and list views."""
        # Update table view
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

        # Update list view
        self._ranking_list_view.load_tracks(songs)

    def _load_ranking_view_mode(self):
        """Load ranking view mode preference from config."""
        view_mode = self._config.get("view/ranking_view_mode", "table") if self._config else "table"
        self._update_ranking_view_toggle_icon()
        self._ranking_stacked_widget.setCurrentIndex(0 if view_mode == "table" else 1)

    def _toggle_ranking_view_mode(self):
        """Toggle between table and list view for rankings."""
        current_mode = self._config.get("view/ranking_view_mode", "table") if self._config else "table"
        new_mode = "list" if current_mode == "table" else "table"
        if self._config:
            self._config.set("view/ranking_view_mode", new_mode)
        self._update_ranking_view_toggle_icon()
        self._ranking_stacked_widget.setCurrentIndex(0 if new_mode == "table" else 1)

    def _update_ranking_view_toggle_icon(self):
        """Update ranking view toggle button icon."""
        view_mode = self._config.get("view/ranking_view_mode", "table") if self._config else "table"
        theme = ThemeManager.instance().current_theme

        if view_mode == "list":
            icon = get_icon(IconName.GRID, theme.text_secondary)
            self._ranking_view_toggle_btn.setToolTip(t("switch_to_table_view"))
        else:
            icon = get_icon(IconName.LIST, theme.text_secondary)
            self._ranking_view_toggle_btn.setToolTip(t("switch_to_list_view"))

        self._ranking_view_toggle_btn.setIcon(icon)

    def _on_ranking_track_activated(self, track):
        """Handle track activation from ranking list view."""
        logger.info(f"Ranking track activated: {track.title}")
        self._play_track(track)

    def _on_ranking_favorite_toggled(self, track, is_favorite: bool):
        """Handle favorite toggle from ranking list view star click."""
        if not track:
            return
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        favorites_service = bootstrap.favorites_service

        if is_favorite:
            track_id = self._add_online_track_to_library(track)
            if track_id:
                favorites_service.add_favorite(track_id=track_id)
                self._ranking_list_view.set_track_favorite(track.mid, True)
        else:
            library_track = bootstrap.library_service.get_track_by_cloud_file_id(track.mid)
            if library_track:
                favorites_service.remove_favorite(track_id=library_track.id)
                self._ranking_list_view.set_track_favorite(track.mid, False)

    def _on_ranking_favorites_toggle(self, tracks: list, all_favorited: bool):
        """Handle favorite toggle from ranking list view context menu."""
        for track in tracks:
            self._on_ranking_favorite_toggled(track, not all_favorited)


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
        self._cancelled = False

    def cancel(self):
        """Cancel the download."""
        self._cancelled = True

    def run(self):
        """Run download."""
        if self._cancelled:
            self.download_finished.emit(self._song_mid, "")
            return
        try:
            result = self._download_service.download(self._song_mid, self._song_title)
            self.download_finished.emit(self._song_mid, result or "")
        except Exception as e:
            logger.error(f"Download worker error: {e}")
            self.download_finished.emit(self._song_mid, "")

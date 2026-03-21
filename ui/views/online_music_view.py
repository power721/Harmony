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
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QCursor, QColor, QBrush, QAction

from domain.online_music import (
    OnlineTrack, OnlineArtist, OnlineAlbum, OnlinePlaylist,
    SearchResult, SearchType
)
from services.online import OnlineMusicService, OnlineDownloadService
from system.i18n import t
from system.event_bus import EventBus
from ui.icons import IconName, get_icon
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


class OnlineMusicView(QWidget):
    """View for searching and browsing online music."""

    # Signals
    play_online_track = Signal(str, str, object)  # (song_mid, local_path, metadata_dict)
    add_to_queue = Signal(str, object)  # (song_mid, metadata_dict)

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
        self._selected_top_id: Optional[int] = None

        # Event bus
        self._event_bus = EventBus.instance()

        self._setup_ui()
        self._load_top_lists()

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

        layout.addWidget(self._stack)

        # Apply styles
        self._apply_styles()

    def _create_header(self) -> QWidget:
        """Create header with QQ Music login status."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel(t("online_music"))
        title.setStyleSheet("""
            color: #1db954;
            font-size: 24px;
            font-weight: bold;
        """)
        layout.addWidget(title)

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

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("search_online_music"))
        self._search_input.returnPressed.connect(self._on_search)
        self._search_input.setFixedHeight(50)
        self._search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 15px;
                border: 1px solid #333;
                border-radius: 20px;
                background: #1a1a1a;
                color: white;
                font-size: 14px;
            }
            QLineEdit:focus {
                border-color: #1db954;
            }
        """)
        layout.addWidget(self._search_input, 1)

        # Clear button
        self._clear_btn = QPushButton("✕")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.setFixedWidth(35)
        self._clear_btn.clicked.connect(self._on_clear_search)
        self._clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #808080;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                color: #1db954;
            }
        """)
        layout.addWidget(self._clear_btn)

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

        left_title = QLabel(t("rankings"))
        left_title.setStyleSheet("color: #1db954; font-size: 16px; font-weight: bold;")
        left_layout.addWidget(left_title)

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
        """Create search results page."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 10, 0, 0)

        # Results info
        self._results_info = QLabel()
        self._results_info.setStyleSheet("color: #808080; font-size: 12px;")
        layout.addWidget(self._results_info)

        # Results table
        self._results_table = self._create_songs_table()
        layout.addWidget(self._results_table)

        # Pagination
        pagination = self._create_pagination()
        layout.addWidget(pagination)

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
                self._login_status_label.setText(f"QQ音乐: {nick}")
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
        self._tabs.show()

        # Immediately switch to results page and show searching state
        self._stack.setCurrentWidget(self._results_page)
        self._results_info.setText(t("searching"))
        self._results_table.setRowCount(0)
        self._prev_btn.setEnabled(False)
        self._next_btn.setEnabled(False)

        self._do_search()

    def _on_clear_search(self):
        """Clear search and show top lists."""
        self._search_input.clear()
        self._current_keyword = ""
        self._current_page = 1
        self._current_tracks = []
        self._tabs.hide()
        # Switch to top list page
        self._stack.setCurrentWidget(self._top_list_page)

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

        if self._current_search_type == SearchType.SONG:
            self._current_tracks = result.tracks
            self._display_tracks(result.tracks)
        elif self._current_search_type == SearchType.SINGER:
            self._display_artists(result.artists)
        elif self._current_search_type == SearchType.ALBUM:
            self._display_albums(result.albums)
        elif self._current_search_type == SearchType.PLAYLIST:
            self._display_playlists(result.playlists)

        # Update results info
        self._results_info.setText(
            f"{t('search_result')}: {result.total} {t('results')}"
        )

        # Update pagination
        self._page_label.setText(str(self._current_page))
        self._prev_btn.setEnabled(self._current_page > 1)
        self._next_btn.setEnabled(len(result.tracks) == 30)

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

    def _display_artists(self, artists: List[OnlineArtist]):
        """Display artists in table."""
        self._results_table.setRowCount(len(artists))
        self._results_table.setColumnCount(4)
        self._results_table.setHorizontalHeaderLabels([
            t("name"), t("song_count"), t("album_count"), ""
        ])

        for i, artist in enumerate(artists):
            self._results_table.setItem(i, 0, QTableWidgetItem(artist.name))
            self._results_table.setItem(i, 1, QTableWidgetItem(str(artist.song_count)))
            self._results_table.setItem(i, 2, QTableWidgetItem(str(artist.album_count)))
            self._results_table.setItem(i, 3, QTableWidgetItem(""))

    def _display_albums(self, albums: List[OnlineAlbum]):
        """Display albums in table."""
        self._results_table.setRowCount(len(albums))
        self._results_table.setColumnCount(4)
        self._results_table.setHorizontalHeaderLabels([
            t("name"), t("artist"), t("song_count"), ""
        ])

        for i, album in enumerate(albums):
            self._results_table.setItem(i, 0, QTableWidgetItem(album.name))
            self._results_table.setItem(i, 1, QTableWidgetItem(album.singer_name))
            self._results_table.setItem(i, 2, QTableWidgetItem(str(album.song_count)))
            self._results_table.setItem(i, 3, QTableWidgetItem(""))

    def _display_playlists(self, playlists: List[OnlinePlaylist]):
        """Display playlists in table."""
        self._results_table.setRowCount(len(playlists))
        self._results_table.setColumnCount(4)
        self._results_table.setHorizontalHeaderLabels([
            t("title"), t("creator"), t("song_count"), ""
        ])

        for i, playlist in enumerate(playlists):
            self._results_table.setItem(i, 0, QTableWidgetItem(playlist.title))
            self._results_table.setItem(i, 1, QTableWidgetItem(playlist.creator))
            self._results_table.setItem(i, 2, QTableWidgetItem(str(playlist.song_count)))
            self._results_table.setItem(i, 3, QTableWidgetItem(""))

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
            self._do_search()

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

        track = self._current_tracks[row]
        self._play_track(track)

    def _play_track(self, track: OnlineTrack):
        """Play an online track."""
        # Build metadata from track info
        metadata = {
            "title": track.title,
            "artist": track.singer_name,
            "album": track.album_name,
            "duration": track.duration,
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
        else:
            table = self._results_table

        selected_rows = [idx.row() for idx in table.selectedIndexes()
                         if idx.column() == 0]
        if not selected_rows:
            return

        tracks = [self._current_tracks[r] for r in selected_rows if 0 <= r < len(self._current_tracks)]
        if not tracks:
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
            })

    def _add_selected_to_queue(self, tracks: List[OnlineTrack]):
        """Add selected tracks to queue."""
        for track in tracks:
            self.add_to_queue.emit(track.mid, {
                "title": track.title,
                "artist": track.singer_name,
                "album": track.album_name,
                "duration": track.duration,
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

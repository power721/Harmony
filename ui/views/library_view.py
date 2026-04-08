"""
Library view widget for browsing the music library.
"""
import logging
import platform
import shutil
import subprocess
from pathlib import Path
from typing import List

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QStackedWidget,
)

from domain.playback import PlaybackState
from domain.track import Track
from services.metadata import CoverService
from services.playback import PlaybackService
from system.config import ConfigManager
from system.event_bus import EventBus
from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.edit_media_info_dialog import EditMediaInfoDialog
from ui.dialogs.message_dialog import MessageDialog, Yes, No
from ui.dialogs.redownload_dialog import RedownloadDialog
from ui.views.history_list_view import HistoryListView
from ui.views.local_tracks_list_view import LocalTracksListView
from utils import format_count_message

# Configure logging
logger = logging.getLogger(__name__)


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
    """

    track_double_clicked = Signal(int)  # Signal when track is double-clicked
    cloud_file_double_clicked = Signal(str, int)  # Signal when cloud file is double-clicked (file_id, account_id)
    insert_to_queue = Signal(list)  # Signal when tracks should be inserted after current
    add_to_queue = Signal(list)  # Signal when tracks should be added to queue
    add_to_playlist_signal = Signal(
        list
    )  # Signal when tracks should be added to a playlist
    ALL_TRACKS_PAGE_SIZE = 500

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
        self._history_list_view = None  # History list view widget
        self._history_played_at_map = {}  # track_id -> played_at datetime
        self._view_search_texts = {
            "all": "",
            "favorites": "",
            "history": "",
        }  # 保存每个视图的搜索文本
        self._all_tracks_total_count = 0
        self._all_tracks_offset = 0
        self._all_tracks_has_more = False
        self._all_tracks_loading = False
        self._all_tracks_query = ""
        self._all_tracks_source = None
        self._pending_redownload_mids: set[str] = set()

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

        header_layout.addStretch()

        # Source filter dropdown
        from PySide6.QtWidgets import QComboBox
        self._source_filter = QComboBox()
        self._source_filter.addItem(t("all_sources"), "all")
        self._source_filter.addItem(t("source_local"), "Local")
        self._source_filter.addItem(t("source_quark"), "QUARK")
        self._source_filter.addItem(t("source_baidu"), "BAIDU")
        self._source_filter.addItem(t("online_track"), "ONLINE")
        self._source_filter.setFixedWidth(120)
        self._source_filter.setProperty("compact", True)
        header_layout.addWidget(self._source_filter)

        # Add spacing between filter and search box
        header_layout.addSpacing(10)

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText(t("search_tracks"))
        self._search_input.setFixedWidth(300)
        self._search_input.setClearButtonEnabled(True)  # 启用清除按钮
        self._search_input.setProperty("variant", "search")
        header_layout.addWidget(self._search_input)

        layout.addLayout(header_layout)

        # Stacked widget for library/favorites/history list pages
        self._stacked_widget = QStackedWidget()
        layout.addWidget(self._stacked_widget)

        # All tracks list view
        self._all_tracks_list_view = LocalTracksListView(show_index=True, show_source=True)
        self._stacked_widget.addWidget(self._all_tracks_list_view)

        # Favorites list view
        self._favorites_list_view = LocalTracksListView(show_index=True, show_source=True)
        self._stacked_widget.addWidget(self._favorites_list_view)

        # History list view
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
        self._all_tracks_list_view.track_activated.connect(self._on_all_tracks_track_activated)
        self._all_tracks_list_view.play_requested.connect(self._on_all_tracks_play_requested)
        self._all_tracks_list_view.insert_to_queue_requested.connect(self._on_all_tracks_insert_to_queue)
        self._all_tracks_list_view.add_to_queue_requested.connect(self._on_all_tracks_add_to_queue)
        self._all_tracks_list_view.add_to_playlist_requested.connect(self._on_all_tracks_add_to_playlist)
        self._all_tracks_list_view.favorites_toggle_requested.connect(self._on_all_tracks_favorites_toggle)
        self._all_tracks_list_view.edit_info_requested.connect(self._on_all_tracks_edit_info)
        self._all_tracks_list_view.download_cover_requested.connect(self._on_all_tracks_download_cover)
        self._all_tracks_list_view.organize_files_requested.connect(self._on_all_tracks_organize_files)
        self._all_tracks_list_view.open_file_location_requested.connect(self._on_all_tracks_open_file_location)
        self._all_tracks_list_view.remove_from_library_requested.connect(self._on_all_tracks_remove_from_library)
        self._all_tracks_list_view.delete_file_requested.connect(self._on_all_tracks_delete_file)
        self._all_tracks_list_view.redownload_requested.connect(self._redownload_online_track)
        self._all_tracks_list_view._list_view.verticalScrollBar().valueChanged.connect(
            self._on_all_tracks_scroll_changed
        )

        # Favorites list view
        self._favorites_list_view.track_activated.connect(self._on_favorites_track_activated)
        self._favorites_list_view.play_requested.connect(self._on_all_tracks_play_requested)
        self._favorites_list_view.insert_to_queue_requested.connect(self._on_all_tracks_insert_to_queue)
        self._favorites_list_view.add_to_queue_requested.connect(self._on_all_tracks_add_to_queue)
        self._favorites_list_view.add_to_playlist_requested.connect(self._on_all_tracks_add_to_playlist)
        self._favorites_list_view.favorites_toggle_requested.connect(self._on_favorites_favorites_toggle)
        self._favorites_list_view.edit_info_requested.connect(self._on_all_tracks_edit_info)
        self._favorites_list_view.download_cover_requested.connect(self._on_all_tracks_download_cover)
        self._favorites_list_view.organize_files_requested.connect(self._on_all_tracks_organize_files)
        self._favorites_list_view.open_file_location_requested.connect(self._on_all_tracks_open_file_location)
        self._favorites_list_view.remove_from_library_requested.connect(self._on_all_tracks_remove_from_library)
        self._favorites_list_view.delete_file_requested.connect(self._on_all_tracks_delete_file)
        self._favorites_list_view.redownload_requested.connect(self._redownload_online_track)

        # History list view
        self._history_list_view.track_activated.connect(self._on_history_track_activated)
        self._history_list_view.play_requested.connect(self._on_history_play_requested)
        self._history_list_view.insert_to_queue_requested.connect(self._on_history_insert_to_queue)
        self._history_list_view.add_to_queue_requested.connect(self._on_history_add_to_queue)
        self._history_list_view.add_to_playlist_requested.connect(self._on_history_add_to_playlist)
        self._history_list_view.favorites_toggle_requested.connect(self._on_history_favorites_toggle)
        self._history_list_view.edit_info_requested.connect(self._on_history_edit_info)
        self._history_list_view.download_cover_requested.connect(self._on_history_download_cover)
        self._history_list_view.organize_files_requested.connect(self._on_history_organize_files)
        self._history_list_view.open_file_location_requested.connect(self._on_history_open_file_location)
        self._history_list_view.remove_from_library_requested.connect(self._on_history_remove_from_library)
        self._history_list_view.delete_file_requested.connect(self._on_history_delete_file)
        self._history_list_view.redownload_requested.connect(self._redownload_online_track)

        # Connect to player engine signals
        self._player.engine.current_track_changed.connect(
            self._on_current_track_changed
        )
        self._player.engine.current_track_pending.connect(
            self._on_current_track_changed
        )
        self._player.engine.state_changed.connect(self._on_player_state_changed)

        # Connect to file organization events
        event_bus = EventBus.instance()
        event_bus.tracks_organized.connect(self._on_tracks_organized)
        event_bus.favorite_changed.connect(self._on_favorite_changed)

        from services.download.download_manager import DownloadManager
        manager = DownloadManager.instance()
        manager.download_completed.connect(self._on_redownload_completed)
        manager.download_failed.connect(self._on_redownload_failed)

    @staticmethod
    def _disconnect_signal(signal, slot):
        """Best-effort signal disconnection for shutdown cleanup."""
        try:
            signal.disconnect(slot)
        except (RuntimeError, TypeError):
            pass

    def closeEvent(self, event):
        """Release external signal connections that outlive the view."""
        engine = getattr(getattr(self, "_player", None), "engine", None)
        if engine is not None:
            self._disconnect_signal(engine.current_track_changed, self._on_current_track_changed)
            self._disconnect_signal(engine.current_track_pending, self._on_current_track_changed)
            self._disconnect_signal(engine.state_changed, self._on_player_state_changed)

        event_bus = EventBus.instance()
        self._disconnect_signal(event_bus.tracks_organized, self._on_tracks_organized)
        self._disconnect_signal(event_bus.favorite_changed, self._on_favorite_changed)
        from services.download.download_manager import DownloadManager
        manager = DownloadManager.instance()
        self._disconnect_signal(manager.download_completed, self._on_redownload_completed)
        self._disconnect_signal(manager.download_failed, self._on_redownload_failed)

        search_timer = getattr(self, "_search_timer", None)
        if search_timer is not None:
            search_timer.stop()

        super().closeEvent(event)

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

        # Update title based on current view
        if self._current_view == "all":
            self._title_label.setText(t("library"))
        elif self._current_view == "favorites":
            self._title_label.setText(t("favorites"))
        elif self._current_view == "history":
            self._title_label.setText(t("history"))

        # Reload data
        if self._current_view == "all":
            self._stacked_widget.setCurrentWidget(self._all_tracks_list_view)
            self._load_all_tracks()
        elif self._current_view == "favorites":
            self._stacked_widget.setCurrentWidget(self._favorites_list_view)
            self._load_favorites()
        elif self._current_view == "history":
            self._stacked_widget.setCurrentWidget(self._history_list_view)
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
        self._stacked_widget.setCurrentWidget(self._all_tracks_list_view)

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
        self._stacked_widget.setCurrentWidget(self._favorites_list_view)

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
        self._stacked_widget.setCurrentWidget(self._history_list_view)

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

    def _current_list_view(self):
        """Return the active list view for the current library subview."""
        if self._current_view == "favorites":
            return self._favorites_list_view
        if self._current_view == "history":
            return self._history_list_view
        return self._all_tracks_list_view

    def _reload_current_list_view(self):
        """Reload the active library subview while preserving current search text."""
        query = self._search_input.text().strip()
        if query:
            self._on_search(query)
        elif self._current_view == "favorites":
            self._load_favorites()
        elif self._current_view == "history":
            self._load_history()
        else:
            self._load_all_tracks()

    def _load_all_tracks(self):
        """Load the first page of all tracks into the virtualized list view."""
        self._loading_label.setVisible(True)
        self._stacked_widget.setVisible(False)

        self._all_tracks_offset = 0
        self._all_tracks_query = self._search_input.text().strip()
        self._all_tracks_source = self._source_filter.currentData()
        if self._all_tracks_source == "all":
            self._all_tracks_source = None

        if self._all_tracks_query:
            self._all_tracks_total_count = self._library_service.get_search_track_count(
                self._all_tracks_query, source=self._all_tracks_source
            )
        else:
            self._all_tracks_total_count = self._library_service.get_track_count(source=self._all_tracks_source)

        favorite_ids = self._favorites_service.get_all_favorite_track_ids()
        self._all_tracks_list_view.load_tracks([], favorite_ids)
        self._all_tracks_has_more = self._all_tracks_total_count > 0

        if self._all_tracks_total_count == 0:
            if self._all_tracks_query:
                self._status_label.setText(f'0 {t("results_for")} "{self._all_tracks_query}"')
            else:
                self._status_label.setText(f"0 {t('tracks')}")
            self._loading_label.setVisible(False)
            self._stacked_widget.setVisible(True)
            return

        self._load_next_all_tracks_page()

    def _load_next_all_tracks_page(self):
        """Load the next page of tracks for the library list."""
        if self._all_tracks_loading or not self._all_tracks_has_more:
            return

        self._all_tracks_loading = True
        query = self._all_tracks_query
        source = self._all_tracks_source

        if query:
            tracks = self._library_service.search_tracks(
                query,
                limit=self.ALL_TRACKS_PAGE_SIZE,
                offset=self._all_tracks_offset,
                source=source,
            )
        else:
            tracks = self._library_service.get_all_tracks(
                limit=self.ALL_TRACKS_PAGE_SIZE,
                offset=self._all_tracks_offset,
                source=source,
            )

        if self._all_tracks_offset == 0:
            favorite_ids = self._favorites_service.get_all_favorite_track_ids()
            self._all_tracks_list_view.load_tracks(tracks, favorite_ids)
        else:
            self._all_tracks_list_view.append_tracks(tracks)

        self._all_tracks_offset += len(tracks)
        self._all_tracks_has_more = self._all_tracks_offset < self._all_tracks_total_count and bool(tracks)
        self._all_tracks_loading = False

        loaded_count = self._all_tracks_list_view.row_count()
        if query:
            self._status_label.setText(
                f'{loaded_count}/{self._all_tracks_total_count} {t("results_for")} "{query}"'
            )
        else:
            self._status_label.setText(f"{loaded_count}/{self._all_tracks_total_count} {t('tracks')}")

        self._loading_label.setVisible(False)
        self._stacked_widget.setVisible(True)

    def _on_all_tracks_scroll_changed(self, value: int):
        """Lazy-load additional library pages when the list nears the bottom."""
        if self._current_view != "all":
            return
        scrollbar = self._all_tracks_list_view._list_view.verticalScrollBar()
        if value >= max(0, scrollbar.maximum() - 200):
            self._load_next_all_tracks_page()

    def _load_favorites(self):
        """Load favorite tracks into the favorites list view."""
        self._loading_label.setVisible(True)
        self._stacked_widget.setVisible(False)

        favorites = self._favorites_service.get_favorites()
        favorite_ids = self._favorites_service.get_all_favorite_track_ids()
        self._favorites_list_view.load_tracks(favorites, favorite_ids)
        self._status_label.setText(f"{len(favorites)} {t('favorites_word')}")

        self._loading_label.setVisible(False)
        self._stacked_widget.setVisible(True)

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

        favorite_ids = self._favorites_service.get_all_favorite_track_ids()
        self._history_list_view.load_tracks(tracks, self._history_played_at_map, favorite_ids)
        self._stacked_widget.setCurrentWidget(self._history_list_view)

        self._status_label.setText(f"{len(tracks)} {t('recently_played')}")

        self._loading_label.setVisible(False)
        self._stacked_widget.setVisible(True)
        self._scroll_to_playing_track()

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
            self._load_all_tracks()
            return

        elif self._current_view == "favorites":
            all_favorites = self._favorites_service.get_favorites()
            tracks = self._filter_tracks_by_query(all_favorites, query)
            favorite_ids = self._favorites_service.get_all_favorite_track_ids()
            self._favorites_list_view.load_tracks(tracks, favorite_ids)
            status_text = (
                f'{len(tracks)} {t("results_for")} "{query}" {t("in_favorites")}'
            )

        elif self._current_view == "history":
            history = self._play_history_service.get_history()
            track_ids = [entry.track_id for entry in history]
            tracks_map = {t.id: t for t in self._library_service.get_tracks_by_ids(track_ids)}
            tracks = []
            played_at_map = {}
            for entry in history:
                track = tracks_map.get(entry.track_id)
                if track and self._track_matches_query(track, query):
                    tracks.append(track)
                    played_at_map[track.id] = entry.played_at
            favorite_ids = self._favorites_service.get_all_favorite_track_ids()
            self._history_played_at_map = played_at_map
            self._history_list_view.load_tracks(tracks, played_at_map, favorite_ids)
            status_text = (
                f'{len(tracks)} {t("results_for")} "{query}" {t("in_history")}'
            )
        else:
            tracks = []
            status_text = f'0 {t("results_for")} "{query}"'

        self._status_label.setText(status_text)

    def _on_current_track_changed(self, track_dict: dict):
        """Handle current track change from player."""
        if track_dict:
            new_track_id = track_dict.get("id")

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
            self._scroll_to_playing_track()

    def _on_player_state_changed(self, state: PlaybackState):
        """Handle player state change (play/pause)."""
        del state

    def _scroll_to_playing_track(self):
        """Scroll to the currently playing track."""
        if self._current_playing_track_id is None:
            return

        current_list_view = self._current_list_view()
        if current_list_view.select_track_by_id(self._current_playing_track_id):
            current_list_view.scroll_to_track_id(self._current_playing_track_id)

    def _select_track_by_id(self, track_id: int):
        """
        Select a track by its ID.

        Args:
            track_id: Track ID to select
        """
        self._current_list_view().select_track_by_id(track_id)

    def _select_and_scroll_to_current(self):
        """Select and scroll to the currently playing track."""
        if self._current_playing_track_id is None:
            return

        current_list_view = self._current_list_view()
        if current_list_view.select_track_by_id(self._current_playing_track_id):
            current_list_view.scroll_to_track_id(self._current_playing_track_id)

    def _refresh_tracks_in_table(self, track_ids: List[int]):
        """
        Refresh tracks in the active list view.

        Args:
            track_ids: List of track IDs to refresh
        """
        del track_ids
        self._reload_current_list_view()

    def _on_tracks_organized(self, result: dict):
        """Handle file organization completion event."""
        success = result.get('success', 0)
        if success > 0:
            # Refresh the view to show updated paths
            self.refresh()

    def _on_favorite_changed(self, item_id, is_favorite: bool, is_cloud: bool):
        """Reload the favorites page when its membership changes."""
        del item_id, is_favorite, is_cloud
        if self._current_view == "favorites":
            self._reload_current_list_view()

    def _on_history_track_activated(self, track: Track):
        """Handle track activation from history list view."""
        if not track or not track.id:
            return

        queue_index = self._find_queue_index(track.id)
        if queue_index is not None:
            self._player.engine.play_at(queue_index)
            if hasattr(self._player, "save_queue"):
                self._player.save_queue()
            return

        recent_tracks = self._play_history_service.get_history_tracks(limit=100)
        self._play_track_collection(recent_tracks, track.id)

    def _on_favorites_track_activated(self, track: Track):
        """Play a track activated from the favorites list."""
        if not track or not track.id:
            return
        favorite_tracks = self._favorites_service.get_favorites()
        self._play_track_collection(favorite_tracks, track.id)

    def _on_all_tracks_track_activated(self, track: Track):
        """Play a track activated from the all-tracks virtualized list."""
        if track and track.id:
            self.track_double_clicked.emit(track.id)

    def _find_queue_index(self, track_id: int):
        """Return the first queue index for a track ID, if present."""
        for index, item in enumerate(getattr(self._player.engine, "playlist_items", []) or []):
            if getattr(item, "track_id", None) == track_id:
                return index
        return None

    def _play_track_collection(self, tracks: List[Track], start_track_id: int):
        """Load a track collection into the queue and start from the selected track."""
        track_ids = [track.id for track in tracks if track and track.id]
        if not track_ids or start_track_id not in track_ids:
            return
        start_index = track_ids.index(start_track_id)
        self._player.play_local_tracks(track_ids, start_index=start_index)

    def _on_all_tracks_play_requested(self, tracks: list):
        """Play requested tracks from the all-tracks list."""
        if not tracks:
            return
        track_ids = [track.id for track in tracks if track.id]
        if not track_ids:
            return
        if len(track_ids) == 1:
            self._on_favorites_track_activated(tracks[0])
        else:
            self.track_double_clicked.emit(track_ids[0])

    def _on_all_tracks_insert_to_queue(self, tracks: list):
        """Insert tracks after the current queue item."""
        track_ids = [track.id for track in tracks if track.id]
        if track_ids:
            self.insert_to_queue.emit(track_ids)

    def _on_all_tracks_add_to_queue(self, tracks: list):
        """Append tracks to the playback queue."""
        track_ids = [track.id for track in tracks if track.id]
        if track_ids:
            self.add_to_queue.emit(track_ids)

    def _on_all_tracks_add_to_playlist(self, tracks: list):
        """Add tracks from the all-tracks list to a playlist."""
        from utils.playlist_utils import add_tracks_to_playlist

        track_ids = [track.id for track in tracks if track.id]
        if track_ids:
            add_tracks_to_playlist(self, self._library_service, track_ids, "[LibraryAllTracksListView]")

    def _on_all_tracks_favorites_toggle(self, tracks: list, all_favorited: bool):
        """Toggle favorite state for tracks from the all-tracks list."""
        bus = EventBus.instance()
        for track in tracks:
            if not track or not track.id:
                continue
            if all_favorited:
                self._favorites_service.remove_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, False, is_cloud=False)
            else:
                self._favorites_service.add_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, True, is_cloud=False)

    def _on_favorites_favorites_toggle(self, tracks: list, all_favorited: bool):
        """Toggle favorites from the favorites list and reload the page."""
        self._on_all_tracks_favorites_toggle(tracks, all_favorited)

    def _on_all_tracks_edit_info(self, track):
        """Edit metadata for a track from the all-tracks list."""
        if not track or not track.id:
            return
        dialog = EditMediaInfoDialog([track.id], self._library_service, self)
        dialog.tracks_updated.connect(self._refresh_tracks_in_table)
        dialog.exec()

    def _on_all_tracks_download_cover(self, track):
        """Download cover art for a track from the all-tracks list."""
        self._on_history_download_cover(track)

    def _on_all_tracks_open_file_location(self, track):
        """Open file location for a track from the all-tracks list."""
        self._on_history_open_file_location(track)

    def _on_all_tracks_organize_files(self, tracks: list):
        """Open the organize-files dialog from the all-tracks list."""
        self._open_organize_files_dialog(tracks)

    def _on_all_tracks_remove_from_library(self, tracks: list):
        """Remove tracks from the library from the all-tracks list."""
        self._on_history_remove_from_library(tracks)

    def _on_all_tracks_delete_file(self, tracks: list):
        """Delete files from disk from the all-tracks list."""
        self._on_history_delete_file(tracks)

    def _on_history_play_requested(self, tracks: list):
        """Play requested tracks from history list view."""
        if not tracks:
            return
        from domain import PlaylistItem
        items = [PlaylistItem.from_track(track) for track in tracks if track.id]
        if items:
            if len(items) == 1:
                self._on_history_track_activated(tracks[0])
            else:
                self._player.engine.load_playlist_items(items)
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

    def _on_history_organize_files(self, tracks: list):
        """Open the organize-files dialog from the history list."""
        self._open_organize_files_dialog(tracks)

    def _open_organize_files_dialog(self, tracks: list):
        """Open the organize-files dialog for the selected tracks."""
        if not tracks:
            return

        from app.application import Application

        app = Application.instance()
        if not app or not app.bootstrap or not hasattr(app.bootstrap, 'file_org_service'):
            MessageDialog.warning(
                self,
                t("error"),
                t("file_org_service_not_available")
            )
            return

        from ui.dialogs.organize_files_dialog import OrganizeFilesDialog

        dialog = OrganizeFilesDialog(
            tracks,
            app.bootstrap.file_org_service,
            self._config,
            self,
        )
        if dialog.exec() == QDialog.Accepted:
            self.refresh()

    def _redownload_online_track(self, track):
        """Request plugin-driven online re-download for a single track."""
        if not track or not track.is_online:
            self._status_label.setText(t("not_supported_yet"))
            return

        song_mid = str(track.cloud_file_id or "").strip()
        provider_id = str(track.online_provider_id or "").strip()
        if not song_mid or not provider_id:
            self._status_label.setText(t("not_supported_yet"))
            return

        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        service = getattr(bootstrap, "online_download_service", None)
        if not service:
            self._status_label.setText(t("not_supported_yet"))
            return

        quality_options = service.get_download_qualities(song_mid, provider_id=provider_id)
        selected_quality = RedownloadDialog.show_dialog(
            track.title or song_mid,
            quality_options=quality_options,
            parent=self,
        )
        if not selected_quality:
            return

        from services.download.download_manager import DownloadManager
        started = DownloadManager.instance().redownload_online_track(
            song_mid=song_mid,
            title=track.title or "",
            provider_id=provider_id,
            quality=selected_quality,
        )
        if started:
            self._pending_redownload_mids.add(song_mid)
            self._status_label.setText(t("redownload"))
        else:
            self._status_label.setText(t("download_failed"))

    def _on_redownload_completed(self, song_mid: str, local_path: str):
        """Handle re-download completion."""
        if song_mid not in self._pending_redownload_mids:
            return
        self._pending_redownload_mids.discard(song_mid)
        del local_path
        self._status_label.setText(t("download_complete"))

    def _on_redownload_failed(self, song_mid: str):
        """Handle re-download failure."""
        if song_mid not in self._pending_redownload_mids:
            return
        self._pending_redownload_mids.discard(song_mid)
        self._status_label.setText(t("download_failed"))

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

"""
Main application window for the music player.

Refactored to use modular components:
- Sidebar: Navigation panel
- LyricsPanel + LyricsController: Lyrics display and management
- OnlineMusicHandler: Online track playback
- ScanDialog: Music folder scanning
"""
import logging
import time
from contextlib import suppress
from typing import Optional

from app import Bootstrap
from domain.playback import PlaybackState
from domain.playlist_item import PlaylistItem
from domain.track import TrackSource
from PySide6.QtCore import Qt, Signal, QSettings, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QSizeGrip,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)
from system.event_bus import EventBus
from system.hotkeys import GlobalHotkeys, setup_media_key_handler
from system.i18n import t, set_language
from system.theme import ThemeManager
from ui.dialogs.message_dialog import MessageDialog, Yes, No
from ui.dialogs.settings_dialog import GeneralSettingsDialog
from ui.dialogs.welcome_dialog import WelcomeDialog
from ui.views.album_view import AlbumView
from ui.views.albums_view import AlbumsView
from ui.views.artist_view import ArtistView
from ui.views.artists_view import ArtistsView
from ui.views.cloud import CloudDriveView
from ui.views.genre_view import GenreView
from ui.views.genres_view import GenresView
from ui.views.library_view import LibraryView
from ui.views.playlist_view import PlaylistView
from ui.views.queue_view import QueueView
from ui.widgets.player_controls import PlayerControls
from ui.widgets.title_bar import TitleBar
from utils import format_count_message

# Import from specific submodules to avoid circular import
from .mini_player import MiniPlayer
from .now_playing_window import NowPlayingWindow
from .components import Sidebar, LyricsPanel, LyricsController, OnlineMusicHandler, ScanDialog

# Configure logging
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    play_track = Signal(int)  # Signal to play a track by ID
    lyricsHtmlReady = Signal(str)
    _cover_color_extracted = Signal(object)  # QColor from ColorWorker

    _STYLE_TEMPLATE = """
        QMainWindow {
            background-color: %background%;
            color: %text%;
        }
        QWidget#sidebar {
            background-color: %background%;
            border-right: 1px solid %background_hover%;
        }
        QLabel#logo {
            color: %highlight%;
            font-size: 24px;
            font-weight: bold;
        }
        QPushButton#addMusicBtn {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 14px;
            border-radius: 25px;
            font-weight: bold;
            font-size: 14px;
        }
        QPushButton#addMusicBtn:hover {
            background-color: %highlight_hover%;
        }
        QPushButton#downloadLyricsBtn {
            background: transparent;
            border: 2px solid %border%;
            color: %text_secondary%;
            padding: 6px 14px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
        }
        QPushButton#downloadLyricsBtn:hover {
            border-color: %highlight%;
            color: %highlight%;
            background-color: %selection%;
        }
        QWidget#lyricsPanel {
            background-color: %background_alt%;
            border-left: 1px solid %background_hover%;
        }
        QLabel#lyricsTitle {
            color: %highlight%;
            font-size: 16px;
            font-weight: bold;
            margin-bottom: 15px;
        }
        /* Splitter styling */
        QSplitter::handle {
            background-color: %background_hover%;
            width: 2px;
        }
        QSplitter::handle:hover {
            background-color: %highlight%;
        }
        /* Stacked widget background */
        QStackedWidget {
            background-color: %background%;
            border-radius: 8px;
        }
        /* Status bar styling */
        QStatusBar {
            color: %text%;
        }
        QStatusBar::item {
            border: none;
        }
        QStatusBar QLabel {
            color: %text%;
        }
    """

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Get all services from Bootstrap (singleton)
        bootstrap = Bootstrap.instance()
        self._bootstrap = bootstrap
        self._config = bootstrap.config
        self._playback = bootstrap.playback_service
        self._library_service = bootstrap.library_service
        self._favorites_service = bootstrap.favorites_service
        self._play_history_service = bootstrap.play_history_service
        self._cloud_account_service = bootstrap.cloud_account_service
        self._cloud_file_service = bootstrap.cloud_file_service

        # Initialize QSettings for window geometry/splitter (Qt native format)
        self._settings = QSettings("HarmonyPlayer", "Harmony")

        # Initialize language from config
        saved_lang = self._config.get_language()
        set_language(saved_lang)

        # Keep reference to core services for backward compatibility wrappers
        playback = self._playback
        library_service = self._library_service

        class PlayerProxy:
            """Proxy class for backward compatibility with components expecting old PlayerController interface."""

            @property
            def engine(self):
                return playback.engine

            @property
            def current_source(self):
                return playback.current_source

            @property
            def current_track(self):
                return playback.current_track

            @property
            def state(self):
                return playback.state

            @property
            def volume(self):
                return playback.volume

            @property
            def play_mode(self):
                return playback.play_mode

            @property
            def current_track_id(self):
                item = playback.current_track
                # Return track_id for both local tracks and downloaded cloud files
                return item.track_id if item else None

            @property
            def current_cloud_file_id(self):
                item = playback.current_track
                # Only return cloud_file_id if there's no track_id (not yet downloaded)
                return item.cloud_file_id if item and item.is_cloud and not item.track_id else None

            def play_track(self, track_id):
                return playback.play_local_track(track_id)

            def play_local_tracks(self, track_ids, start_index=0):
                return playback.play_local_tracks(track_ids, start_index=start_index)

            def play(self):
                return playback.play()

            def pause(self):
                return playback.pause()

            def stop(self):
                return playback.stop()

            def play_next(self):
                return playback.play_next()

            def play_previous(self):
                return playback.play_previous()

            def seek(self, pos):
                return playback.seek(pos)

            def set_volume(self, vol):
                return playback.set_volume(vol)

            def set_play_mode(self, mode):
                return playback.set_play_mode(mode)

            def is_favorite(self, track_id=None, cloud_file_id=None):
                return playback.is_favorite(track_id, cloud_file_id)

            def toggle_favorite(self, track_id=None, cloud_file_id=None, cloud_account_id=None):
                return playback.toggle_favorite(track_id, cloud_file_id, cloud_account_id)

            def load_playlist(self, playlist_id):
                return playback.load_playlist(playlist_id)

            def save_queue(self, force: bool = False):
                return playback.save_queue(force=force)

            def restore_queue(self):
                return playback.restore_queue()

            @property
            def cover_service(self):
                return playback.cover_service

            def get_track_cover(self, track_path: str, title: str, artist: str, album: str = "",
                                source: str = "", cloud_file_id: str = "",
                                online_provider_id: str = "",
                                skip_online: bool = False):
                if source == TrackSource.ONLINE.name and cloud_file_id:
                    return playback.get_online_track_cover(
                        provider_id=online_provider_id,
                        cloud_file_id=cloud_file_id,
                        artist=artist,
                        title=title,
                    )
                return playback.get_track_cover(track_path, title, artist, album, skip_online=skip_online)

            def save_cover_from_metadata(self, track_path: str, cover_data: bytes):
                return playback.save_cover_from_metadata(track_path, cover_data)

            def get_track(self, track_id):
                return library_service.get_track(track_id)

            def get_track_by_path(self, path: str):
                return library_service.get_track_by_path(path)

            def get_track_by_cloud_file_id(self, cloud_file_id: str):
                return library_service.get_track_by_cloud_file_id(cloud_file_id)

        self._player = PlayerProxy()

        # Event bus for signals
        self._event_bus = EventBus.instance()

        # Mini player (hidden by default)
        self._mini_player: Optional[MiniPlayer] = None
        self._now_playing_window: Optional[NowPlayingWindow] = None
        self._is_closing = False
        self._force_quit_requested = False

        # Lyrics controller (will be initialized in _setup_ui)
        self._lyrics_controller: Optional[LyricsController] = None

        # Online music handler (will be initialized in _setup_ui)
        self._online_music_handler: Optional[OnlineMusicHandler] = None
        self._pending_redownload_mids: set[str] = set()

        # Scan controller reference (prevent GC)
        self._scan_controller = None

        self._current_index = -1

        # Cloud account for current playback
        self._current_cloud_account = None

        # Current track title for window title
        self._current_track_title: str = ""

        # Frameless window with custom title bar
        self.setWindowFlags(Qt.FramelessWindowHint)

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._setup_system_tray()
        self._setup_hotkeys()

        # Restore geometry
        self._restore_settings()

        # Register for theme change notifications
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Custom title bar
        self._title_bar = TitleBar(self)
        main_layout.addWidget(self._title_bar)

        # Create content area
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Sidebar (navigation)
        self._sidebar = self._create_sidebar()
        content_layout.addWidget(self._sidebar, 1)

        # Main content area (splitter)
        self._splitter = QSplitter(Qt.Horizontal)

        # Library/playlist view
        self._stacked_widget = QStackedWidget()
        self._nav_stack: list[int] = []

        bootstrap = Bootstrap.instance()

        self._library_view = LibraryView(
            self._library_service,
            self._favorites_service,
            self._play_history_service,
            self._player,
            self._config,
            bootstrap.cover_service
        )
        self._cloud_drive_view = CloudDriveView(
            self._cloud_account_service,
            self._cloud_file_service,
            self._library_service,
            self._player,
            self._config,
            bootstrap.cover_service
        )
        self._playlist_view = PlaylistView(
            bootstrap.playlist_service,
            bootstrap.favorites_service,
            bootstrap.library_service,
            self._player
        )
        self._queue_view = QueueView(
            self._player,
            bootstrap.library_service,
            bootstrap.favorites_service,
            bootstrap.playlist_service
        )
        self._albums_view = AlbumsView(bootstrap.library_service, bootstrap.cover_service)
        self._artists_view = ArtistsView(bootstrap.library_service, bootstrap.cover_service)
        self._artist_view = ArtistView(bootstrap.library_service, self._playback, bootstrap.cover_service)
        self._album_view = AlbumView(bootstrap.library_service, self._playback, bootstrap.cover_service)
        self._genres_view = GenresView(bootstrap.library_service, bootstrap.cover_service)
        self._genre_view = GenreView(bootstrap.library_service, self._playback, bootstrap.cover_service)

        self._stacked_widget.addWidget(self._library_view)  # 0
        self._stacked_widget.addWidget(self._cloud_drive_view)  # 1
        self._stacked_widget.addWidget(self._playlist_view)  # 2
        self._stacked_widget.addWidget(self._queue_view)  # 3
        self._stacked_widget.addWidget(self._albums_view)  # 4
        self._stacked_widget.addWidget(self._artists_view)  # 5
        self._stacked_widget.addWidget(self._artist_view)  # 6
        self._stacked_widget.addWidget(self._album_view)  # 7
        self._stacked_widget.addWidget(self._genres_view)  # 8
        self._stacked_widget.addWidget(self._genre_view)  # 9
        self._mount_plugin_pages()

        self._stacked_widget.setMinimumWidth(200)
        self._splitter.addWidget(self._stacked_widget)

        # Lyrics panel
        self._lyrics_panel = self._create_lyrics_panel()
        self._lyrics_panel.setMinimumWidth(250)  # Prevent lyrics panel from collapsing
        self._lyrics_panel.setMaximumWidth(1200)
        self._splitter.addWidget(self._lyrics_panel)

        # Set splitter proportions
        self._splitter.setStretchFactor(0, 2)  # Library gets 2/3
        self._splitter.setStretchFactor(1, 1)  # Lyrics gets 1/3
        self._splitter.setSizes([700, 500])  # Initial sizes
        self._splitter.setChildrenCollapsible(False)

        self._stacked_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._lyrics_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        content_layout.addWidget(self._splitter, 4)

        main_layout.addWidget(content_widget, 1)

        # Player controls
        self._player_controls = PlayerControls(self._player, instance_name="main")
        main_layout.addWidget(self._player_controls)

        # Resize grip for frameless window
        self._resize_grip = QSizeGrip(self)
        self._resize_grip.setFixedSize(16, 16)
        self._resize_grip.setStyleSheet("background: transparent;")

        # Apply themed styling
        self.refresh_theme()

    def _create_sidebar(self) -> QWidget:
        """Create the sidebar navigation using Sidebar component."""
        sidebar = Sidebar(config_manager=self._config)

        # Connect sidebar signals
        sidebar.page_requested.connect(self._on_sidebar_page_requested)
        sidebar.language_toggled.connect(self._toggle_language)
        sidebar.settings_requested.connect(self._show_settings)
        sidebar.add_music_requested.connect(self._add_music)

        return sidebar

    def _mount_plugin_pages(self) -> None:
        """Mount plugin-provided pages into the stacked widget and sidebar."""
        self._plugin_page_keys = {}
        self._plugin_pages = {}
        self._plugin_page_specs = {}
        self._plugin_page_loading = set()
        self._plugin_prewarm_scheduled = False
        self._plugin_prewarm_timer = None
        bootstrap = Bootstrap.instance()
        for spec in bootstrap.plugin_manager.registry.sidebar_entries():
            page_index = self._stacked_widget.count()
            host = QWidget(self)
            host_layout = QVBoxLayout(host)
            host_layout.setContentsMargins(0, 0, 0, 0)
            loading_label = QLabel(t("loading", "Loading..."), host)
            loading_label.setAlignment(Qt.AlignCenter)
            host_layout.addWidget(loading_label)
            self._stacked_widget.addWidget(host)
            self._sidebar.add_plugin_entry(
                page_index=page_index,
                title=spec.title_provider() if callable(getattr(spec, "title_provider", None)) else spec.title,
                icon_name=spec.icon_name,
                icon_path=getattr(spec, "icon_path", None),
                title_provider=getattr(spec, "title_provider", None),
            )
            self._plugin_page_keys[page_index] = spec.plugin_id
            self._plugin_page_specs[page_index] = spec
            logger.info(
                "[PluginUI] Mounted placeholder for plugin page %s at index %s",
                spec.plugin_id,
                page_index,
            )
        self._prewarm_plugin_page()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_plugin_page_prewarm()

    def _schedule_plugin_page_prewarm(self) -> None:
        if getattr(self, "_plugin_prewarm_scheduled", False):
            return
        if not getattr(self, "_plugin_page_specs", None):
            return
        self._plugin_prewarm_scheduled = True
        if self._plugin_prewarm_timer is None:
            self._plugin_prewarm_timer = QTimer(self)
            self._plugin_prewarm_timer.setSingleShot(True)
            self._plugin_prewarm_timer.timeout.connect(self._prewarm_plugin_page)
        self._plugin_prewarm_timer.start(0)

    def _prewarm_plugin_page(self) -> None:
        for index in sorted(self._plugin_page_specs):
            if index not in self._plugin_pages:
                logger.info("[PluginUI] Prewarming plugin page at index %s", index)
                self._ensure_plugin_page_loaded(index)
                break

    def _ensure_plugin_page_loaded(self, index: int) -> None:
        spec = getattr(self, "_plugin_page_specs", {}).get(index)
        if spec is None or index in self._plugin_pages:
            return
        if index in self._plugin_page_loading:
            return

        self._plugin_page_loading.add(index)
        started_at = time.perf_counter()
        try:
            bootstrap = Bootstrap.instance()
            logger.info(
                "[PluginUI] Materializing plugin page %s at index %s",
                spec.plugin_id,
                index,
            )
            host = self._stacked_widget.widget(index)
            widget = spec.page_factory(bootstrap.plugin_manager, host)
            layout = host.layout() if isinstance(host, QWidget) else None
            if layout is not None:
                while layout.count():
                    item = layout.takeAt(0)
                    child = item.widget()
                    if child is not None:
                        child.deleteLater()
                layout.addWidget(widget)
            self._connect_plugin_page_signals(widget)
            self._plugin_pages[index] = widget
            logger.info(
                "[PluginUI] Plugin page %s ready at index %s in %.1fms",
                spec.plugin_id,
                index,
                (time.perf_counter() - started_at) * 1000,
            )
        except Exception:
            logger.exception(
                "[PluginUI] Failed to materialize plugin page %s at index %s",
                getattr(spec, "plugin_id", "<unknown>"),
                index,
            )
        finally:
            self._plugin_page_loading.discard(index)

    def _connect_plugin_page_signals(self, widget: QWidget) -> None:
        signal_map = (
            ("play_online_track", self._play_online_track),
            ("add_to_queue", self._add_online_track_to_queue),
            ("insert_to_queue", self._insert_online_track_to_queue),
            ("add_multiple_to_queue", self._add_multiple_online_tracks_to_queue),
            ("insert_multiple_to_queue", self._insert_multiple_online_tracks_to_queue),
            ("play_online_tracks", self._play_online_tracks),
        )
        for signal_name, handler in signal_map:
            signal = getattr(widget, signal_name, None)
            if signal is None or not hasattr(signal, "connect"):
                continue
            signal.connect(handler)

    def _on_sidebar_page_requested(self, page_index: int):
        """Handle sidebar page request."""
        self._nav_stack.clear()
        if page_index == Sidebar.PAGE_FAVORITES:
            self._show_favorites()
        elif page_index == Sidebar.PAGE_HISTORY:
            self._show_history()
        else:
            self._show_page(page_index)

    def _create_lyrics_panel(self) -> QWidget:
        """Create the lyrics display panel using LyricsPanel component."""
        panel = LyricsPanel()

        # Create lyrics controller
        self._lyrics_controller = LyricsController(
            lyrics_panel=panel,
            playback_service=self._playback,
            library_service=self._library_service
        )

        return panel

    def _setup_connections(self):
        """Setup signal connections."""
        # Cover color extraction → title bar
        self._cover_color_extracted.connect(self._on_cover_color_extracted)

        # Navigation - sidebar signals are connected in _create_sidebar
        # These connections are kept for backward compatibility with _show_page calls
        # from various parts of the code that call these methods directly

        # Player connections - use EventBus for centralized signal handling
        self._event_bus.track_changed.connect(self._on_track_changed)
        self._event_bus.position_changed.connect(self._on_position_changed)
        self._event_bus.playback_state_changed.connect(self._on_playback_state_changed)
        self._playback.engine.current_track_pending.connect(self._on_pending_track_changed)
        from services.download.download_manager import DownloadManager
        manager = DownloadManager.instance()
        manager.download_completed.connect(self._on_playlist_redownload_completed)
        manager.download_failed.connect(self._on_playlist_redownload_failed)

        # Cloud download events
        self._event_bus.download_completed.connect(self._on_cloud_download_completed)

        # View connections
        self._library_view.track_double_clicked.connect(self._play_track)
        self._library_view.cloud_file_double_clicked.connect(self._play_cloud_favorite)
        self._library_view.insert_to_queue.connect(self._insert_to_queue)
        self._library_view.add_to_queue.connect(self._add_to_queue)
        self._playlist_view.playlist_track_double_clicked.connect(self._play_playlist_track)
        self._playlist_view.insert_to_queue.connect(self._insert_to_queue)
        self._playlist_view.add_to_queue.connect(self._add_to_queue)
        self._playlist_view.download_cover_requested.connect(self._on_playlist_download_cover)
        self._playlist_view.redownload_requested.connect(self._on_playlist_redownload)
        self._queue_view.play_track.connect(self._play_track)
        self._queue_view.queue_reordered.connect(self._on_queue_reordered)
        self._cloud_drive_view.track_double_clicked.connect(self._play_cloud_track)
        self._cloud_drive_view.play_cloud_files.connect(self._play_cloud_playlist)

        # Initialize online music handler with download service
        self._online_music_handler = OnlineMusicHandler(
            playback_service=self._playback,
            status_callback=self._show_status_message
        )

        # Albums view connections
        self._albums_view.album_clicked.connect(self._on_album_clicked)
        self._albums_view.play_album.connect(self._play_tracks)
        self._albums_view.download_cover_requested.connect(self._on_download_album_cover)
        self._albums_view.rename_album_requested.connect(self._on_rename_album)

        # Artists view connections
        self._artists_view.artist_clicked.connect(self._on_artist_clicked)
        self._artists_view.download_cover_requested.connect(self._on_download_artist_cover)
        self._artists_view.rename_artist_requested.connect(self._on_rename_artist)

        # Artist view connections
        self._artist_view.play_tracks.connect(self._play_tracks)
        self._artist_view.insert_to_queue.connect(self._insert_tracks_to_queue)
        self._artist_view.add_to_queue.connect(self._add_tracks_to_queue)
        self._artist_view.add_to_playlist.connect(self._add_tracks_to_playlist)
        self._artist_view.download_cover_requested.connect(self._on_download_album_cover)
        self._artist_view.album_clicked.connect(self._on_album_clicked)
        self._artist_view.remove_from_library_requested.connect(
            lambda tracks: self._on_album_remove_from_library(tracks, self._refresh_current_artist_detail)
        )
        self._artist_view.delete_file_requested.connect(
            lambda tracks: self._on_album_delete_file(tracks, self._refresh_current_artist_detail)
        )
        self._artist_view.back_clicked.connect(self._on_back)

        # Album view connections
        self._album_view.play_tracks.connect(self._play_tracks)
        self._album_view.insert_to_queue.connect(self._insert_tracks_to_queue)
        self._album_view.add_to_queue.connect(self._add_tracks_to_queue)
        self._album_view.add_to_playlist.connect(self._add_tracks_to_playlist)
        self._album_view.favorites_toggle_requested.connect(self._on_album_favorites_toggle)
        self._album_view.back_clicked.connect(self._on_back)
        self._album_view.edit_info_requested.connect(self._on_album_edit_media_info)
        self._album_view.download_cover_requested.connect(self._on_album_download_track_cover)
        self._album_view.open_file_location_requested.connect(self._on_album_open_file_location)
        self._album_view.remove_from_library_requested.connect(self._on_album_remove_from_library)
        self._album_view.delete_file_requested.connect(self._on_album_delete_file)

        # Genres view connections
        self._genres_view.genre_clicked.connect(self._on_genre_clicked)
        self._genres_view.play_genre.connect(self._play_tracks)
        self._genres_view.rename_genre_requested.connect(self._on_rename_genre)
        self._genres_view.download_cover_requested.connect(self._on_download_genre_cover)

        # Genre view connections
        self._genre_view.play_tracks.connect(self._play_tracks)
        self._genre_view.insert_to_queue.connect(self._insert_tracks_to_queue)
        self._genre_view.add_to_queue.connect(self._add_tracks_to_queue)
        self._genre_view.add_to_playlist.connect(self._add_tracks_to_playlist)
        self._genre_view.favorites_toggle_requested.connect(
            lambda tracks, all_favorited: self._on_album_favorites_toggle(
                tracks, all_favorited, self._refresh_current_genre_detail
            )
        )
        self._genre_view.edit_info_requested.connect(
            lambda track: self._on_album_edit_media_info(track, self._refresh_current_genre_detail)
        )
        self._genre_view.download_cover_requested.connect(self._on_album_download_track_cover)
        self._genre_view.open_file_location_requested.connect(self._on_album_open_file_location)
        self._genre_view.remove_from_library_requested.connect(
            lambda tracks: self._on_album_remove_from_library(tracks, self._refresh_current_genre_detail)
        )
        self._genre_view.delete_file_requested.connect(
            lambda tracks: self._on_album_delete_file(tracks, self._refresh_current_genre_detail)
        )
        self._genre_view.redownload_requested.connect(self._on_playlist_redownload)
        self._genre_view.back_clicked.connect(self._on_back)

        # Player controls connections
        self._player_controls.artist_clicked.connect(self._on_player_artist_clicked)
        self._player_controls.album_clicked.connect(self._on_player_album_clicked)
        self._player_controls.now_playing_requested.connect(self._show_now_playing)

    def _setup_system_tray(self):
        """Setup system tray icon."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self._tray_icon = QSystemTrayIcon(self)

        # Create icon
        icon = self.style().standardIcon(QStyle.SP_MediaVolume)
        self._tray_icon.setIcon(icon)

        # Create tray menu
        tray_menu = QMenu()

        show_action = tray_menu.addAction(t("show"))
        show_action.triggered.connect(self.show)

        play_pause_action = tray_menu.addAction(t("play_pause"))
        play_pause_action.triggered.connect(self._toggle_play_pause)

        next_action = tray_menu.addAction(t("next"))
        next_action.triggered.connect(self._player.engine.play_next)

        prev_action = tray_menu.addAction(t("previous"))
        prev_action.triggered.connect(self._player.engine.play_previous)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction(t("quit"))
        quit_action.triggered.connect(self.close)

        self._tray_icon.setContextMenu(tray_menu)
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def refresh_theme(self):
        """Apply themed styles using ThemeManager tokens."""
        style = ThemeManager.instance().get_qss(self._STYLE_TEMPLATE)
        self.setStyleSheet(style)

    def _show_page(self, index: int):
        """Show a page in the stacked widget."""
        # Update sidebar nav button states
        self._sidebar.set_current_page(index)

        # Switch view
        self._stacked_widget.setCurrentIndex(index)
        self._ensure_plugin_page_loaded(index)

        # Auto-select first playlist when showing playlists
        if index == 2:  # Playlists is now at index 2
            playlist_view = self._stacked_widget.widget(2)
            if playlist_view and hasattr(playlist_view, "ensure_default_playlist_selected"):
                playlist_view.ensure_default_playlist_selected()

        # Reset library view mode when showing library (delayed to avoid blocking)
        if index == 0:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(50, self._library_view.show_all)

    def _show_favorites(self):
        """Show favorite tracks."""
        # Switch to library view first
        self._stacked_widget.setCurrentIndex(0)

        # Update sidebar nav button states
        self._sidebar.set_current_page(Sidebar.PAGE_FAVORITES)

        # Load favorites with delay to avoid blocking
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._library_view.show_favorites)

    def _show_history(self):
        """Show play history."""
        # Switch to library view first
        self._stacked_widget.setCurrentIndex(0)

        # Update sidebar nav button states
        self._sidebar.set_current_page(Sidebar.PAGE_HISTORY)

        # Load history with delay to avoid blocking
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._library_view.show_history)

    def _on_album_clicked(self, album):
        """Handle album card click."""
        # Push current page to nav stack
        self._nav_stack.append(self._stacked_widget.currentIndex())
        # Show album detail view
        self._album_view.set_album(album)
        self._stacked_widget.setCurrentIndex(7)

        # Update nav button states - no active nav for detail views
        self._sidebar.set_current_page(-1)

    def _on_download_album_cover(self, album):
        """Handle download album cover request."""
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.album_search_strategy import AlbumSearchStrategy
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        strategy = AlbumSearchStrategy(
            album,
            bootstrap.library_service,
            bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(
            strategy,
            bootstrap.cover_service,
            self
        )

        def on_cover_saved(cover_path):
            # Clear the delegate's cover cache and refresh the view
            self._albums_view._delegate.clear_cache()
            self._albums_view._list_view.viewport().update()
            # Update album cards in artist view if visible
            for card in self._artist_view._album_cards:
                if card.get_album().name == album.name and card.get_album().artist == album.artist:
                    card.update_cover(cover_path)
                    break

        dialog.cover_saved.connect(on_cover_saved)
        dialog.exec()

    def _refresh_current_album_detail(self):
        """Refresh album detail after track metadata/library changes."""
        if self._album_view.get_album():
            self._album_view.set_album(self._album_view.get_album())

    def _refresh_current_artist_detail(self):
        """Refresh artist detail and artists list after library changes."""
        from app.bootstrap import Bootstrap

        current_artist = self._artist_view.get_artist()
        self._artists_view.refresh()
        if not current_artist:
            return

        bootstrap = Bootstrap.instance()
        latest = bootstrap.library_service.get_artist_by_name(current_artist.name)
        if latest:
            self._artist_view.set_artist(latest)
        elif self._stacked_widget.currentIndex() == 6:
            self._on_back()

    def _on_album_favorites_toggle(self, tracks: list, all_favorited: bool, refresh_callback=None):
        """Toggle favorite status for tracks in a detail view."""
        from app.bootstrap import Bootstrap
        from system.event_bus import EventBus

        bootstrap = Bootstrap.instance()
        if not bootstrap or not hasattr(bootstrap, 'favorites_service'):
            return

        service = bootstrap.favorites_service
        bus = EventBus.instance()

        for track in tracks:
            if not track or not track.id:
                continue
            if all_favorited:
                service.remove_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, False, is_cloud=False)
            else:
                service.add_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, True, is_cloud=False)

        if refresh_callback:
            refresh_callback()
        else:
            self._refresh_current_album_detail()

    def _on_album_edit_media_info(self, track, refresh_callback=None):
        """Edit media info for a track in a detail view."""
        if not track or not track.id:
            return
        from ui.dialogs import EditMediaInfoDialog
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        dialog = EditMediaInfoDialog([track.id], bootstrap.library_service, self)
        dialog.tracks_updated.connect(refresh_callback or self._refresh_current_album_detail)
        dialog.exec()

    def _on_album_download_track_cover(self, track):
        """Download cover for a track in album view."""
        if not track or not track.id:
            return
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.track_search_strategy import TrackSearchStrategy
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        strategy = TrackSearchStrategy(
            [track], bootstrap.track_repo, bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, bootstrap.cover_service, self)
        dialog.exec()

    def _on_album_open_file_location(self, track):
        """Open file location for a track in album view."""
        from pathlib import Path
        from ui.dialogs.message_dialog import MessageDialog
        import platform
        import subprocess
        import shutil

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

    def _on_album_remove_from_library(self, tracks: list, refresh_callback=None):
        """Remove tracks from library."""
        from ui.dialogs.message_dialog import MessageDialog, Yes, No
        from app.bootstrap import Bootstrap

        track_ids = [t.id for t in tracks if t.id]
        if not track_ids:
            return
        confirm_message = format_count_message("remove_from_library_confirm", len(track_ids))
        reply = MessageDialog.question(
            self, t("remove_from_library"), confirm_message, Yes | No)
        if reply != Yes:
            return
        bootstrap = Bootstrap.instance()
        removed_count = bootstrap.library_service.delete_tracks(track_ids)
        if removed_count > 0:
            success_message = format_count_message("remove_from_library_success", removed_count)
            MessageDialog.information(self, t("remove_from_library"), success_message)
            (refresh_callback or self._refresh_current_album_detail)()

    def _on_album_delete_file(self, tracks: list, refresh_callback=None):
        """Delete files from disk and library."""
        from ui.dialogs.message_dialog import MessageDialog, Yes, No
        from app.bootstrap import Bootstrap
        import os

        if not tracks:
            return
        confirm_message = format_count_message("delete_file_confirm", len(tracks))
        reply = MessageDialog.question(
            self, t("delete_file"), confirm_message, Yes | No)
        if reply != Yes:
            return
        bootstrap = Bootstrap.instance()
        for track in tracks:
            if not track or not track.id:
                continue
            if track.path and os.path.exists(track.path):
                os.remove(track.path)
            bootstrap.library_service.delete_track(track.id)
        (refresh_callback or self._refresh_current_album_detail)()

    def _refresh_current_genre_detail(self):
        """Refresh genre detail and genre list after track metadata/library changes."""
        from app.bootstrap import Bootstrap

        current_genre = self._genre_view.get_genre()
        self._genres_view.refresh()
        if not current_genre:
            return

        bootstrap = Bootstrap.instance()
        latest = bootstrap.library_service.get_genre_by_name(current_genre.name)
        if latest:
            self._genre_view.set_genre(latest)
        elif self._stacked_widget.currentIndex() == 9:
            self._on_back()

    def _on_artist_clicked(self, artist):
        """Handle artist card click."""
        # Push current page to nav stack
        self._nav_stack.append(self._stacked_widget.currentIndex())
        # Show artist detail view
        self._artist_view.set_artist(artist)
        self._stacked_widget.setCurrentIndex(6)

        # Update nav button states - no active nav for detail views
        self._sidebar.set_current_page(-1)

    def _on_genre_clicked(self, genre):
        """Handle genre card click."""
        # Push current page to nav stack
        self._nav_stack.append(self._stacked_widget.currentIndex())
        # Show genre detail view
        self._genre_view.set_genre(genre)
        self._stacked_widget.setCurrentIndex(9)

        # Update nav button states - no active nav for detail views
        self._sidebar.set_current_page(-1)

    def _on_back(self):
        """Handle back button - pop navigation stack."""
        if self._nav_stack:
            prev_page = self._nav_stack.pop()
            self._stacked_widget.setCurrentIndex(prev_page)
            self._sidebar.set_current_page(prev_page)
        else:
            # No history, go to default page
            self._show_page(0)

    def _on_player_artist_clicked(self, artist_name: str):
        """Handle artist label click from player controls."""
        if not artist_name:
            return
        # Get Artist object by name
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        artist = bootstrap.library_service.get_artist_by_name(artist_name)
        if artist:
            self._on_artist_clicked(artist)

    def _on_player_album_clicked(self, album_name: str, artist_name: str):
        """Handle album label click from player controls."""
        if not album_name:
            return
        # Get Album object by name and artist
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        album = None
        if artist_name:
            album = bootstrap.library_service.get_album_by_name(album_name, artist_name)
        if not album:
            # Try without artist (some albums may not have artist info)
            album = bootstrap.library_service.get_album_by_name(album_name)
        if album:
            self._on_album_clicked(album)

    def _on_download_artist_cover(self, artist):
        """Handle download artist cover request."""
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.artist_search_strategy import ArtistSearchStrategy
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        strategy = ArtistSearchStrategy(
            artist,
            bootstrap.library_service,
            bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(
            strategy,
            bootstrap.cover_service,
            self
        )

        def on_cover_saved(cover_path):
            # Clear the delegate's cover cache and refresh the view
            self._artists_view._delegate.clear_cache()
            self._artists_view._list_view.viewport().update()

        dialog.cover_saved.connect(on_cover_saved)
        dialog.exec()

    def _on_rename_artist(self, artist):
        """Handle rename artist request."""
        from ui.dialogs.artist_rename_dialog import ArtistRenameDialog
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        dialog = ArtistRenameDialog(
            artist,
            bootstrap.library_service,
            self
        )

        def on_artist_renamed(old_name, new_name):
            # Refresh the artists view
            self._artists_view.refresh()
            # Clear cover cache
            self._artists_view._delegate.clear_cache()
            self._artists_view._list_view.viewport().update()

        dialog.artist_renamed.connect(on_artist_renamed)
        dialog.exec()

    def _on_rename_album(self, album):
        """Handle rename album request."""
        from ui.dialogs.album_rename_dialog import AlbumRenameDialog
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        dialog = AlbumRenameDialog(
            album,
            bootstrap.library_service,
            self
        )

        def on_album_renamed(old_name, artist, new_name):
            # Refresh the albums view
            self._albums_view.refresh()
            # Clear cover cache
            self._albums_view._delegate.clear_cache()
            self._albums_view._list_view.viewport().update()

        dialog.album_renamed.connect(on_album_renamed)
        dialog.exec()

    def _on_rename_genre(self, genre):
        """Handle rename genre request."""
        from ui.dialogs.genre_rename_dialog import GenreRenameDialog
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        dialog = GenreRenameDialog(
            genre,
            bootstrap.library_service,
            self
        )

        def on_genre_renamed(old_name, new_name):
            self._genres_view.refresh()
            self._genres_view._delegate.clear_cache()
            self._genres_view._list_view.viewport().update()

        dialog.genre_renamed.connect(on_genre_renamed)
        dialog.exec()

    def _on_download_genre_cover(self, genre):
        """Handle download genre cover request."""
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.genre_search_strategy import GenreSearchStrategy
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        strategy = GenreSearchStrategy(
            genre,
            bootstrap.library_service,
            bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(
            strategy,
            bootstrap.cover_service,
            self
        )

        def on_cover_saved(_cover_path):
            # Refresh genres grid cards
            self._genres_view.refresh()
            self._genres_view._delegate.clear_cache()
            self._genres_view._list_view.viewport().update()

            # Refresh genre detail header if current detail matches.
            current_genre = self._genre_view.get_genre()
            if current_genre and current_genre.name == genre.name:
                latest = bootstrap.library_service.get_genre_by_name(genre.name)
                if latest:
                    self._genre_view.set_genre(latest)

        dialog.cover_saved.connect(on_cover_saved)
        dialog.exec()

    def _play_tracks(self, tracks, start_index=0):
        """Play a list of tracks starting from the given index."""
        if tracks:
            from domain.playlist_item import PlaylistItem
            from pathlib import Path

            # Create PlaylistItems with full track info (including local_path)
            items = []
            for track in tracks:
                if track.id and track.id > 0:
                    # Include online tracks (empty path) and existing local files
                    is_online = not track.path or not track.path.strip() or track.is_online
                    if is_online or Path(track.path).exists():
                        items.append(PlaylistItem.from_track(track))

            if items:
                self._playback.engine.clear_playlist()
                self._playback.engine.load_playlist_items(items)

                # Handle shuffle mode
                if self._playback.engine.is_shuffle_mode() and 0 <= start_index < len(items):
                    self._playback.engine.shuffle_and_play(items[start_index])
                    self._playback.engine.play_at(0)
                else:
                    self._playback.engine.play_at(min(start_index, len(items) - 1))

    def _add_music(self):
        """Add music to the library."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle(t("select_music_folder"))

        if dialog.exec():
            folder = dialog.selectedFiles()[0]
            self._scan_music_folder(folder)

    def _scan_music_folder(self, folder: str):
        """Scan a music folder and add tracks using ScanDialog component."""
        logger.info(f"[MainWindow] Scanning music folder: {folder}")

        # Get cover service
        cover_service = Bootstrap.instance().cover_service

        def on_scan_complete(payload: dict):
            """Callback when scan completes."""
            error = payload.get("error")
            if error:
                logger.error(f"[MainWindow] Scan failed: {error}")
                return

            stats = payload.get("stats", {})
            added = stats.get("added", 0)
            unchanged = stats.get("unchanged", 0)
            failed = stats.get("failed", 0)
            logger.info(
                f"[MainWindow] Scan complete: added={added}, unchanged={unchanged}, failed={failed}"
            )
            # Refresh views
            self._library_view.refresh()
            self._albums_view.refresh()
            self._artists_view.refresh()
            self._genres_view.refresh()

        # Keep reference to prevent GC
        self._scan_controller = ScanDialog.scan_folder(
            folder=folder,
            cover_service=cover_service,
            library_service=self._library_service,
            parent=self,
            batch_size=100,
            enable_cover_extraction=False,
            on_complete=on_scan_complete,
        )

    def _toggle_language(self):
        """Toggle between English and Chinese."""
        from system.i18n import get_language, set_language

        current_lang = get_language()
        new_lang = "zh" if current_lang == "en" else "en"
        set_language(new_lang)

        # Save language preference
        self._config.set_language(new_lang)

        EventBus.instance().language_changed.emit(new_lang)

        # Update language button in sidebar
        self._sidebar.update_language_button()

        # Refresh the UI to apply translations
        self._refresh_ui_texts()

    def _refresh_ui_texts(self):
        """Refresh UI texts after language change."""
        # Update window title
        self.setWindowTitle(t("app_title"))
        self._title_bar.clear_track_title()

        # Update sidebar navigation buttons (text only, icons stay the same)
        self._sidebar.refresh_texts()

        # Update lyrics panel
        self._lyrics_panel.refresh_texts()

        # Refresh player controls
        self._player_controls.refresh_ui()

        # Refresh views
        self._library_view.refresh()
        self._cloud_drive_view.refresh_ui()  # Refresh cloud drive view
        self._playlist_view.refresh_playlists()
        self._queue_view.refresh_queue()
        self._albums_view.refresh_ui()
        self._artists_view.refresh_ui()
        self._artist_view.refresh_ui()
        self._album_view.refresh_ui()
        self._genres_view.refresh_ui()
        self._genre_view.refresh_ui()
        for widget in getattr(self, "_plugin_pages", {}).values():
            refresh_ui = getattr(widget, "refresh_ui", None)
            if callable(refresh_ui):
                refresh_ui()
        for page_index, spec in getattr(self, "_plugin_page_specs", {}).items():
            title_provider = getattr(spec, "title_provider", None)
            if not callable(title_provider):
                continue
            for idx, btn in getattr(self._sidebar, "_nav_buttons", []):
                if idx == page_index:
                    btn.setText(title_provider())
                    break

        # Update settings button status in sidebar
        self._sidebar.update_settings_status(self._config.get_ai_enabled())

    def _show_settings(self):
        """Show general settings dialog."""
        dialog = GeneralSettingsDialog(self._config, self)
        if dialog.exec():
            # Update settings button status after settings change
            self._sidebar.update_settings_status(self._config.get_ai_enabled())

    def show_help(self):
        """Show help dialog."""
        from ui.dialogs.help_dialog import HelpDialog

        dialog = HelpDialog(self)
        dialog.exec()

    def _play_track(self, track_id: int):
        """Play a local track from library (loads entire library as playlist)."""
        self._playback.play_local_track(track_id)

    def _play_playlist_track(self, playlist_id: int, track_id: int):
        """Play a track from a specific playlist."""
        self._playback.play_playlist_track(playlist_id, track_id)

    def _on_playlist_download_cover(self, track):
        """Download cover for a playlist track."""
        if not track or not track.id:
            return
        from ui.dialogs.universal_cover_download_dialog import UniversalCoverDownloadDialog
        from ui.strategies.track_search_strategy import TrackSearchStrategy
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        strategy = TrackSearchStrategy(
            [track], bootstrap.track_repo, bootstrap.event_bus
        )
        dialog = UniversalCoverDownloadDialog(strategy, bootstrap.cover_service, self)
        dialog.exec()

    def _on_playlist_redownload(self, track):
        """Request plugin-driven re-download for playlist/genre online track."""
        if not track or not getattr(track, "is_online", False):
            self._status_label.setText(t("not_supported_yet"))
            return

        song_mid = str(getattr(track, "cloud_file_id", "") or "").strip()
        provider_id = str(getattr(track, "online_provider_id", "") or "").strip()
        if not song_mid or not provider_id:
            self._status_label.setText(t("not_supported_yet"))
            return

        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        service = getattr(bootstrap, "online_download_service", None)
        if not service:
            self._status_label.setText(t("not_supported_yet"))
            return

        from ui.dialogs.redownload_dialog import RedownloadDialog
        quality_options = service.get_download_qualities(song_mid, provider_id=provider_id)
        selected_quality = RedownloadDialog.show_dialog(
            getattr(track, "title", "") or song_mid,
            quality_options=quality_options,
            parent=self,
        )
        if not selected_quality:
            return

        from services.download.download_manager import DownloadManager
        started = DownloadManager.instance().redownload_online_track(
            song_mid=song_mid,
            title=getattr(track, "title", "") or "",
            provider_id=provider_id,
            quality=selected_quality,
        )
        if started:
            self._pending_redownload_mids.add(song_mid)
            self._status_label.setText(t("redownload"))
        else:
            self._status_label.setText(t("download_failed"))

    def _on_playlist_redownload_completed(self, song_mid: str, local_path: str):
        """Handle playlist re-download completion."""
        if song_mid not in self._pending_redownload_mids:
            return
        self._pending_redownload_mids.discard(song_mid)
        del local_path
        self._status_label.setText(t("download_complete"))

    def _on_playlist_redownload_failed(self, song_mid: str):
        """Handle playlist re-download failure."""
        if song_mid not in self._pending_redownload_mids:
            return
        self._pending_redownload_mids.discard(song_mid)
        self._status_label.setText(t("download_failed"))

    def _play_cloud_favorite(self, cloud_file_id: str, account_id: int):
        """Play a cloud file from favorites."""

        if not cloud_file_id or not account_id:
            return

        # Get cloud account
        account = self._cloud_account_service.get_account(account_id)
        if not account:
            logger.error(f"[MainWindow] Cloud account {account_id} not found")
            return

        # Get cloud file info
        cloud_file = self._cloud_file_service.get_file_by_file_id(cloud_file_id)
        if cloud_file:
            # Create PlaylistItem from cloud file
            item = PlaylistItem.from_cloud_file(cloud_file, account_id, provider=account.provider)
            self._playback.engine.load_playlist_items([item])
            self._playback.engine.play()
        else:
            # File not in cache, need to get from cloud
            logger.warning(f"[MainWindow] Cloud file {cloud_file_id} not found in cache")
            # Fallback: create basic item with file_id
            source = TrackSource.QUARK if account.provider.lower() == "quark" else TrackSource.BAIDU
            item = PlaylistItem(
                source=source,
                cloud_file_id=cloud_file_id,
                cloud_account_id=account_id,
                title="Cloud Track",
                needs_download=True
            )
            self._playback.engine.load_playlist_items([item])
            self._playback.engine.play()

    def _play_cloud_track(self, temp_path: str):
        """Play track from cloud (temp file) - backward compatible."""
        # Create a simple playlist item for single track
        item = PlaylistItem(
            source=TrackSource.QUARK,
            local_path=temp_path,
            title='Cloud Track',
            needs_download=False
        )
        self._playback.engine.load_playlist_items([item])
        self._playback.engine.play()

    def _play_online_track(self, song_mid: str, local_path: str, metadata: dict = None):
        """Play downloaded online track.

        Delegates to OnlineMusicHandler.

        Args:
            song_mid: Song MID
            local_path: Local file path
            metadata: Optional metadata dict with title, artist, album, duration
        """
        logger.info(f"Playing online track: mid={song_mid}, path={local_path}")
        if self._online_music_handler:
            self._online_music_handler.play_online_track(song_mid, local_path, metadata)

    def _add_online_track_to_queue(self, song_mid: str, metadata: dict):
        """Add online track to the play queue (deferred download).

        Delegates to OnlineMusicHandler.

        Args:
            song_mid: Song MID
            metadata: Metadata dict with title, artist, album, duration
        """
        if self._online_music_handler:
            self._online_music_handler.add_to_queue(song_mid, metadata)

    def _insert_online_track_to_queue(self, song_mid: str, metadata: dict):
        """Insert online track after current playing track.

        Delegates to OnlineMusicHandler.

        Args:
            song_mid: Song MID
            metadata: Metadata dict with title, artist, album, duration
        """
        if self._online_music_handler:
            self._online_music_handler.insert_to_queue(song_mid, metadata)

    def _add_multiple_online_tracks_to_queue(self, tracks_data: list):
        """Add multiple online tracks to the play queue (batch operation).

        Delegates to OnlineMusicHandler.

        Args:
            tracks_data: List of (song_mid, metadata_dict) tuples
        """
        if self._online_music_handler:
            self._online_music_handler.add_multiple_to_queue(tracks_data)

    def _insert_multiple_online_tracks_to_queue(self, tracks_data: list):
        """Insert multiple online tracks after current playing track (batch operation).

        Delegates to OnlineMusicHandler.

        Args:
            tracks_data: List of (song_mid, metadata_dict) tuples
        """
        if self._online_music_handler:
            self._online_music_handler.insert_multiple_to_queue(tracks_data)

    def _play_online_tracks(self, start_index: int, tracks_data: list):
        """Play multiple online tracks, clearing queue first.

        Delegates to OnlineMusicHandler.

        Args:
            start_index: Index of track to start playing
            tracks_data: List of (song_mid, metadata_dict) tuples
        """
        logger.info(f"Playing {len(tracks_data)} online tracks, starting at {start_index}")
        if self._online_music_handler:
            self._online_music_handler.play_online_tracks(start_index, tracks_data)

    def _play_cloud_playlist(self, temp_path: str, index: int, cloud_files, start_position: float = 0.0):
        """Play multiple cloud files as a playlist."""
        # Get current cloud account from CloudDriveView
        account = self._cloud_drive_view._current_account
        if not account:
            logger.error("[MainWindow] No cloud account available")
            return

        self._current_cloud_account = account

        # Use PlaybackService for cloud playback
        self._playback.play_cloud_playlist(cloud_files, index, account, temp_path, start_position)

    def _on_cloud_download_completed(self, file_id: str, local_path: str):
        """Handle cloud file download completion."""
        # Forward to playback service
        self._playback.on_cloud_file_downloaded(file_id, local_path)

    def _on_queue_reordered(self):
        """Handle queue reorder (drag-drop in queue view)."""
        # Sync playlist items from engine to playback service and save
        self._playback.save_queue()

    def _on_track_changed(self, track_item):
        """Handle track change.

        Args:
            track_item: Can be PlaylistItem or dict (for backward compatibility)
        """
        if isinstance(track_item, PlaylistItem):
            track_dict = track_item.to_dict()
            track_id = track_item.track_id
            title = track_item.title
            artist = track_item.artist
            path = track_item.local_path
        elif isinstance(track_item, int):
            # Handle case where track_item is just an ID
            track_id = track_item
            track_dict = None
            title = ""
            artist = ""
            path = ""
        else:
            track_dict = track_item
            track_id = track_dict.get("id") if track_dict else None
            title = track_dict.get("title", "") if track_dict else ""
            artist = track_dict.get("artist", "") if track_dict else ""
            path = track_dict.get("path", "") if track_dict else ""

        # Sync selection in both library and queue views
        if track_id and track_id > 0:
            # Select in library view
            self._library_view._select_track_by_id(track_id)
            # Select in queue view (if it exists in queue)
            self._queue_view._select_track_by_id(track_id)

        # Delegate lyrics loading to LyricsController
        if self._lyrics_controller:
            self._lyrics_controller.on_track_changed(track_item)
        else:
            # Fallback: clear lyrics if no controller
            self._lyrics_panel.set_no_lyrics()

        if not track_dict:
            return

        # Update title bar with track info
        if title:
            self._title_bar.set_track_title(title, artist)
            self._extract_cover_color(title, artist, path, track_dict)
        else:
            self._title_bar.clear_track_title()
            self._title_bar.clear_accent_color()

        # Save current track title for backward compat
        self._current_track_title = f"{title} - {artist}" if artist else title
        if self._current_track_title:
            self.setWindowTitle(self._current_track_title)

    def _on_pending_track_changed(self, track_item):
        """Handle lightweight UI updates while a selected track downloads."""
        if isinstance(track_item, PlaylistItem):
            track_id = track_item.track_id
            title = track_item.title
            artist = track_item.artist
        elif isinstance(track_item, dict):
            track_id = track_item.get("id")
            title = track_item.get("title", "")
            artist = track_item.get("artist", "")
        else:
            return

        if track_id and track_id > 0:
            self._library_view._select_track_by_id(track_id)
            self._queue_view._select_track_by_id(track_id)

        self._lyrics_panel.set_no_lyrics()

        if title:
            self._title_bar.set_track_title(title, artist)
            self._title_bar.clear_accent_color()
        else:
            self._title_bar.clear_track_title()
            self._title_bar.clear_accent_color()

        self._current_track_title = f"{title} - {artist}" if artist else title
        if self._current_track_title:
            self.setWindowTitle(self._current_track_title)

    def _on_playback_state_changed(self, state: str):
        """Handle playback state change to update window title.

        Args:
            state: "playing", "paused", or "stopped"
        """
        if state == "playing":
            # Update window title to show current track
            if self._current_track_title:
                self.setWindowTitle(self._current_track_title)
        elif state in ("paused", "stopped"):
            # Paused/stopped - restore original title
            self._title_bar.clear_track_title()
            self._title_bar.clear_accent_color()
            self.setWindowTitle(t("app_title"))

    def _on_cover_color_extracted(self, color):
        """Handle cover color extraction result."""
        if color:
            self._title_bar.set_accent_color(color)
        else:
            self._title_bar.clear_accent_color()

    def _extract_cover_color(self, title: str, artist: str, path: str, track_dict: dict):
        """Extract dominant color from album cover and apply to title bar.

        Uses background thread to fetch cover (avoiding UI blocking for online covers)
        and extract dominant color.
        """
        from PySide6.QtCore import QThreadPool
        from services.metadata.color_extractor import CoverFetchWorker

        skip_online = track_dict.get("needs_download", False) or (track_dict.get("is_cloud", False) and not path)
        source = track_dict.get("source", "")
        cloud_file_id = track_dict.get("cloud_file_id", "")

        # Use CoverFetchWorker to fetch cover and extract color in background thread
        worker = CoverFetchWorker(
            cover_fetcher=self._player.get_track_cover,
            title=title,
            artist=artist,
            path=path,
            album=track_dict.get("album", ""),
            source=source,
            cloud_file_id=cloud_file_id,
            skip_online=skip_online,
            result_signal=self._cover_color_extracted,
            fallback_fetcher=self._get_album_cover
        )
        QThreadPool.globalInstance().start(worker)

    def _get_album_cover(self, album: str, artist: str) -> str | None:
        """Get cover from albums table via LibraryService."""
        from pathlib import Path
        try:
            album_obj = self._library_service.get_album_by_name(album, artist)
            if album_obj and album_obj.cover_path and Path(album_obj.cover_path).exists():
                return album_obj.cover_path
        except Exception as e:
            logger.debug(f"[MainWindow] Error getting album cover: {e}")
        return None

    def _insert_to_queue(self, track_ids: list):
        """Insert tracks after current playing track."""
        self._queue_view.insert_tracks_after_current(track_ids)

        # Show notification
        count = len(track_ids)
        self._status_bar = self.statusBar()
        msg = t("inserted_to_queue").replace("{count}", str(count))
        self._status_bar.showMessage(msg, 3000)

    def _insert_tracks_to_queue(self, tracks: list):
        """Insert Track objects after current playing track."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self._insert_to_queue(track_ids)

    def _add_to_queue(self, track_ids: list):
        """Add tracks to the play queue."""
        self._queue_view.add_tracks(track_ids)

        # Show notification
        count = len(track_ids)
        self._status_bar = self.statusBar()
        s = "s" if count > 1 else ""
        msg = t("added_to_queue").replace("{count}", str(count)).replace("{s}", s)
        self._status_bar.showMessage(msg, 3000)

    def _show_status_message(self, message: str, timeout: int = 3000):
        """Show a status message in the status bar."""
        self._status_bar = self.statusBar()
        self._status_bar.showMessage(message, timeout)

    def _add_tracks_to_queue(self, tracks: list):
        """Add Track objects to the play queue."""
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self._add_to_queue(track_ids)

    def _add_tracks_to_playlist(self, tracks: list):
        """Add Track objects to a playlist."""
        from ui.dialogs.add_to_playlist_dialog import AddToPlaylistDialog
        from app.bootstrap import Bootstrap

        # Get track IDs from Track objects
        track_ids = [t.id for t in tracks if t.id]
        if not track_ids:
            return

        bootstrap = Bootstrap.instance()
        dialog = AddToPlaylistDialog(bootstrap.library_service, self)

        # Check if there are playlists
        if not dialog.has_playlists():
            dialog.deleteLater()
            reply = MessageDialog.question(
                self,
                t("no_playlists"),
                t("no_playlists_message"),
                Yes | No,
            )
            if reply == Yes:
                self._show_page(2)  # Show playlists page
            return

        # If only one playlist, add directly without showing dialog
        if dialog.has_single_playlist():
            playlist = dialog.get_single_playlist()
            dialog.deleteLater()
            if playlist:
                added_count = 0
                duplicate_count = 0
                for track_id in track_ids:
                    if self._library_service.add_track_to_playlist(playlist.id, track_id):
                        added_count += 1
                    else:
                        duplicate_count += 1

                if duplicate_count == 0:
                    msg = t("added_tracks_to_playlist").format(count=added_count, name=playlist.name)
                    MessageDialog.information(self, t("success"), msg)
                elif added_count == 0:
                    msg = t("all_tracks_duplicate").format(count=duplicate_count, name=playlist.name)
                    MessageDialog.warning(self, t("duplicate"), msg)
                else:
                    msg = t("added_skipped_duplicates").format(added=added_count, duplicates=duplicate_count)
                    MessageDialog.information(self, t("partially_added"), msg)
            return

        dialog.set_track_ids(track_ids)

        if dialog.exec() == QDialog.Accepted:
            playlist = dialog.get_selected_playlist()
            if playlist:
                added_count = 0
                duplicate_count = 0
                for track_id in track_ids:
                    if self._library_service.add_track_to_playlist(playlist.id, track_id):
                        added_count += 1
                    else:
                        duplicate_count += 1

                if duplicate_count == 0:
                    msg = t("added_tracks_to_playlist").format(count=added_count, name=playlist.name)
                    MessageDialog.information(self, t("success"), msg)
                elif added_count == 0:
                    msg = t("all_tracks_duplicate").format(count=duplicate_count, name=playlist.name)
                    MessageDialog.warning(self, t("duplicate"), msg)
                else:
                    msg = t("added_skipped_duplicates").format(added=added_count, duplicates=duplicate_count)
                    MessageDialog.information(self, t("partially_added"), msg)

    def _on_position_changed(self, position_ms):
        """Handle playback position change."""
        seconds = position_ms / 1000
        self._lyrics_panel.update_position(seconds)

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._playback.state == PlaybackState.PLAYING:
            self._playback.pause()
        else:
            self._playback.play()

    def _on_tray_activated(self, reason):
        """Handle system tray activation."""
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.activateWindow()

    def _setup_hotkeys(self):
        """Setup global hotkeys and media key support."""
        self._hotkeys = GlobalHotkeys(self._player, self)
        setup_media_key_handler(self._player)

    def _toggle_now_playing_view(self):
        """Toggle between main window and now-playing window."""
        if self._now_playing_window is not None and self._now_playing_window.isVisible():
            self._now_playing_window.close()
            return
        self._show_now_playing()

    def toggle_mini_mode(self):
        """Toggle mini player mode."""
        if self._mini_player is None:
            self._mini_player = MiniPlayer(self._player, self)
            self._mini_player.closed.connect(self._on_mini_player_closed)
            self._mini_player.show()
            self.hide()
        else:
            # Close mini player and show main window
            self._mini_player.close()

    def _on_mini_player_closed(self):
        """Handle mini player close."""
        self._mini_player = None
        self.show()
        self.activateWindow()

    def _show_now_playing(self):
        """Open now-playing view and hide the main window."""
        if self._now_playing_window is None:
            self._now_playing_window = NowPlayingWindow(self._playback, self)
            self._now_playing_window.closed.connect(self._on_now_playing_closed)

        self._now_playing_window.show()
        self._now_playing_window.raise_()
        self._now_playing_window.activateWindow()
        self._config.set_start_in_now_playing(True)
        self.hide()

    def _switch_now_playing_to_mini(self):
        """Switch from now-playing window directly to mini player."""
        if self._now_playing_window is not None and self._now_playing_window.isVisible():
            with suppress(Exception):
                self._now_playing_window.closed.disconnect(self._on_now_playing_closed)
            self._now_playing_window.close()
            self._now_playing_window.closed.connect(self._on_now_playing_closed)

        if self._mini_player is None:
            self._mini_player = MiniPlayer(self._player, self)
            self._mini_player.closed.connect(self._on_mini_player_closed)

        self._config.set_start_in_now_playing(False)
        self._mini_player.show()
        self._mini_player.raise_()
        self._mini_player.activateWindow()
        self.hide()

    def _switch_mini_to_now_playing(self):
        """Switch from mini player directly to now-playing window."""
        if self._mini_player is not None:
            with suppress(Exception):
                self._mini_player.closed.disconnect(self._on_mini_player_closed)
            self._mini_player.close()
            self._mini_player = None

        self._show_now_playing()

    def _quit_from_now_playing(self):
        """Quit app while persisting now-playing restore state."""
        self._config.set_start_in_now_playing(True)
        self._force_quit_requested = True
        self.close()

    def request_quit(self):
        """Request app quit from any window/shortcut path."""
        self._force_quit_requested = True
        self.close()

    def _on_now_playing_closed(self):
        """Restore main window when now-playing view is closed."""
        if self._is_closing:
            return
        self._config.set_start_in_now_playing(False)
        # Defer restoration until the now-playing window is fully closed.
        QTimer.singleShot(0, self._restore_main_window_foreground)

    def _restore_main_window_foreground(self):
        """Bring main window to the foreground after now-playing closes."""
        if self._is_closing:
            return
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    def _restore_settings(self):
        """Restore window settings."""
        # Use QSettings for geometry/splitter (Qt native format)
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = self._settings.value("splitter")
        if splitter_state:
            self._splitter.restoreState(splitter_state)

        # Volume is restored by PlaybackService, just update slider
        volume = self._config.get_volume()
        self._player_controls.set_volume(volume)

        # Restore view state (album/artist detail view)
        self._restore_view_state()

        # Restore playback state
        self._restore_playback_state()

        # Show welcome dialog on first run (empty library)
        self._check_first_run()

        # Restore now-playing window visibility state from previous session.
        if self._config.get_start_in_now_playing():
            QTimer.singleShot(150, self._show_now_playing)

    def _check_first_run(self):
        """Show welcome dialog if the library is empty (first run)."""
        from PySide6.QtCore import QTimer

        if self._library_service.get_track_count() > 0:
            return

        from PySide6.QtCore import QLocale
        language = QLocale.system().language()
        if "Chinese" in language.name:
            self._toggle_language()

        def _show_welcome():
            dialog = WelcomeDialog(parent=self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                folder = dialog.get_selected_folder()
                if folder:
                    self._scan_music_folder(folder)

        QTimer.singleShot(500, _show_welcome)

    def _save_view_state(self):
        """Save current view state to config."""
        import json

        current_index = self._stacked_widget.currentIndex()
        plugin_page_keys = getattr(self, "_plugin_page_keys", {})
        if current_index in plugin_page_keys:
            view_type = f"plugin:{plugin_page_keys[current_index]}"
        else:
            view_type = "library"
        view_data = {}

        if not view_type.startswith("plugin:"):
            # Map stacked-widget indices to their persisted view types.
            index_to_type = {
                0: "library",
                1: "cloud",
                2: "playlists",
                3: "queue",
                4: "albums",
                5: "artists",
                6: "artist",
                7: "album",
                8: "genres",
                9: "genre",
            }

            view_type = index_to_type.get(current_index, "library")

        # Special handling for library view - check if it's showing favorites or history
        if view_type == "library":
            current_view = self._library_view.get_current_view()
            if current_view in ("favorites", "history"):
                view_type = current_view

        # Save view-specific data
        if view_type == "album":
            album = self._album_view.get_album()
            if album:
                view_data = {
                    "name": album.name,
                    "artist": album.artist,
                }
        elif view_type == "artist":
            artist = self._artist_view.get_artist()
            if artist:
                view_data = {
                    "name": artist.name,
                }
        elif view_type == "genre":
            genre = self._genre_view.get_genre()
            if genre:
                view_data = {
                    "name": genre.name,
                }

        self._config.set_view_type(view_type)
        self._config.set_view_data(json.dumps(view_data))

    def _restore_view_state(self):
        """Restore view state from config."""
        from PySide6.QtCore import QTimer
        import json

        view_type = self._config.get_view_type()
        view_data_raw = self._config.get_view_data()

        if not view_type or view_type == "library":
            return

        # Handle both string and dict types from config
        if isinstance(view_data_raw, dict):
            view_data = view_data_raw
        elif isinstance(view_data_raw, str) and view_data_raw:
            try:
                view_data = json.loads(view_data_raw)
            except json.JSONDecodeError:
                view_data = {}
        else:
            view_data = {}

        def restore_view():
            if view_type == "album":
                name = view_data.get("name")
                artist = view_data.get("artist")
                if name and artist:
                    # Find album from library
                    from app.bootstrap import Bootstrap
                    bootstrap = Bootstrap.instance()
                    album = bootstrap.library_service.get_album_by_name(name, artist)
                    if album:
                        self._nav_stack.append(self._stacked_widget.currentIndex())
                        self._album_view.set_album(album)
                        self._stacked_widget.setCurrentIndex(7)
                        self._update_nav_buttons_for_detail_view()
            elif view_type == "artist":
                name = view_data.get("name")
                if name:
                    # Find artist from library
                    from app.bootstrap import Bootstrap
                    bootstrap = Bootstrap.instance()
                    artist = bootstrap.library_service.get_artist_by_name(name)
                    if artist:
                        self._nav_stack.append(self._stacked_widget.currentIndex())
                        self._artist_view.set_artist(artist)
                        self._stacked_widget.setCurrentIndex(6)
                        self._update_nav_buttons_for_detail_view()
            elif view_type == "cloud":
                self._show_page(1)
            elif view_type == "playlists":
                self._show_page(2)
            elif view_type == "queue":
                self._show_page(3)
            elif view_type == "albums":
                self._show_page(4)
            elif view_type == "artists":
                self._show_page(5)
            elif view_type == "online":
                if getattr(self, "_plugin_page_keys", None):
                    self._show_page(next(iter(self._plugin_page_keys)))
                else:
                    self._show_page(0)
            elif view_type.startswith("plugin:"):
                plugin_id = view_type.partition(":")[2]
                page_index = next(
                    (index for index, value in getattr(self, "_plugin_page_keys", {}).items() if value == plugin_id),
                    None,
                )
                if page_index is not None:
                    self._show_page(page_index)
                elif getattr(self, "_plugin_page_keys", None):
                    # Legacy fallback when the saved plugin is unavailable.
                    self._show_page(next(iter(self._plugin_page_keys)))
                else:
                    self._show_page(0)
            elif view_type == "genres":
                self._show_page(8)
            elif view_type == "genre":
                name = view_data.get("name")
                if name:
                    # Find genre from library
                    from app.bootstrap import Bootstrap
                    bootstrap = Bootstrap.instance()
                    genre = bootstrap.library_service.get_genre_by_name(name)
                    if genre:
                        self._nav_stack.append(self._stacked_widget.currentIndex())
                        self._genre_view.set_genre(genre)
                        self._stacked_widget.setCurrentIndex(9)
                        self._update_nav_buttons_for_detail_view()
            elif view_type == "favorites":
                self._show_favorites()
            elif view_type == "history":
                self._show_history()

        # Delay to ensure UI is ready
        QTimer.singleShot(100, restore_view)

    def _update_nav_buttons_for_detail_view(self):
        """Update navigation buttons for detail view (album/artist)."""
        self._sidebar.set_current_page(-1)  # No active nav for detail views

    @staticmethod
    def _normalize_restore_position(position_ms: int, duration_s: float | int | None) -> int:
        """
        Normalize restored position to avoid instant end-of-track auto-next.

        If the saved position is too close to the end, restart from 0 so the app
        restores the same song instead of immediately jumping to the next one.
        """
        if position_ms <= 0:
            return 0

        try:
            duration_ms = int(float(duration_s or 0) * 1000)
        except (TypeError, ValueError):
            duration_ms = 0

        if duration_ms <= 0:
            return position_ms

        if position_ms >= max(0, duration_ms - 3000):
            return 0

        return min(position_ms, max(0, duration_ms - 1))

    def _restore_playback_state(self):
        """Restore previous playback state."""
        from PySide6.QtCore import QTimer

        # Try to restore saved queue first
        if self._player.restore_queue():
            logger.debug("Restored play queue from database")
            # Guard against spurious end-of-media events during backend warm-up.
            # This prevents an immediate auto-advance before restore completes.
            with suppress(Exception):
                self._player.engine.set_prevent_auto_next(True)

            # Check if we should auto-play
            was_playing = self._config.get_was_playing()
            playback_position = self._config.get_playback_position()
            # Update navigation buttons immediately based on source
            # if source == "cloud":
            #     if hasattr(self, '_nav_cloud'):
            #         self._nav_cloud.setChecked(True)
            #     if hasattr(self, '_nav_library'):
            #         self._nav_library.setChecked(False)

            def restore_queue_state():
                # Re-enable auto-next after restoration completes
                with suppress(Exception):
                    self._player.engine.set_prevent_auto_next(False)

                current_item = self._player.current_track
                logger.debug(f"restore_queue_state: {current_item} playback_position={playback_position} was_playing={was_playing}")
                if current_item:
                    # Restore position if valid
                    if playback_position > 0:
                        seek_pos = self._normalize_restore_position(
                            playback_position,
                            getattr(current_item, "duration", 0),
                        )
                        self._player.engine.seek(seek_pos)

                    # Auto-play if was playing
                    if was_playing:
                        logger.debug("Auto-playing restored track")
                        QTimer.singleShot(300, self._player.play)

            QTimer.singleShot(200, restore_queue_state)
            return

        # Fall back to legacy restore logic
        # Check playback source
        source = self._config.get_playback_source()
        logger.debug(f"Playback source: {source}")

        if source == "cloud":
            # Restore cloud playback state
            account_id = self._config.get_cloud_account_id()
            logger.debug(f"Cloud account_id: {account_id}")
            if account_id:
                account = self._cloud_account_service.get_account(account_id)
                if account:
                    was_playing = self._config.get_was_playing()
                    logger.debug(f"Restoring cloud playback, account: {account_id}, was_playing: {was_playing}")

                    def restore_cloud_state():
                        # Re-enable auto-next after restoration completes
                        with suppress(Exception):
                            self._player.engine.set_prevent_auto_next(False)

                        # Extract parent_id from last_fid_path
                        # last_fid_path is like "/fid1/fid2/fid3", we need the last segment
                        fid_path = account.last_fid_path or "0"
                        if fid_path and fid_path != "0":
                            parent_id = fid_path.split("/")[-1] if "/" in fid_path else fid_path
                        else:
                            parent_id = "0"

                        # Restore cloud drive view state
                        self._cloud_drive_view.restore_playback_state(
                            account_id=account_id,
                            file_path=parent_id,
                            file_fid=account.last_playing_fid,
                            auto_play=was_playing,
                            start_position=account.last_position or 0.0,
                            local_path=account.last_playing_local_path or ""
                        )

                    QTimer.singleShot(200, restore_cloud_state)
                    return
                else:
                    logger.debug(f"Cloud account {account_id} not found, falling back to local")

        # Restore local track playback state
        current_track_id = self._config.get_current_track_id()
        playback_position = self._config.get_playback_position()
        was_playing = self._config.get_was_playing()
        logger.debug(
            f"Local restore: track_id={current_track_id}, position={playback_position}, was_playing={was_playing}")

        if current_track_id and current_track_id > 0:
            def restore_later():
                # Re-enable auto-next after restoration completes
                with suppress(Exception):
                    self._player.engine.set_prevent_auto_next(False)

                track = self._library_service.get_track(current_track_id)
                if track:
                    try:
                        logger.debug(f"Restoring local track: {current_track_id}")
                        self._player.play_track(current_track_id)

                        if playback_position > 0:
                            seek_pos = self._normalize_restore_position(
                                playback_position,
                                getattr(track, "duration", 0),
                            )
                            self._player.engine.seek(seek_pos)

                        if was_playing:
                            QTimer.singleShot(300, self._player.engine.play)
                    except Exception as e:
                        logger.error(f"Could not restore playback: {e}", exc_info=True)

            QTimer.singleShot(100, restore_later)

    def resizeEvent(self, event):
        """Position resize grip at bottom-right corner."""
        super().resizeEvent(event)
        if hasattr(self, '_resize_grip') and self._resize_grip:
            self._resize_grip.move(self.width() - 16, self.height() - 16)

    def closeEvent(self, event):
        """Handle window close."""
        self._is_closing = True
        is_now_playing_visible = self._now_playing_window is not None and self._now_playing_window.isVisible()
        self._config.set_start_in_now_playing(bool(is_now_playing_visible))
        if self._now_playing_window is not None and self._now_playing_window.isVisible():
            with suppress(Exception):
                self._now_playing_window.closed.disconnect(self._on_now_playing_closed)
            self._now_playing_window.close()

        # Save window settings using QSettings (Qt native format)
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter", self._splitter.saveState())

        # Save current view state
        self._save_view_state()

        # Check if playing cloud files BEFORE stopping
        is_playing_cloud = self._player.current_source == "cloud"
        is_playing = self._player.state == PlaybackState.PLAYING
        current_position = self._player.engine.position()
        current_index = self._player.engine.current_index
        current_volume = self._player.volume

        logger.debug(
            f"closeEvent: index={current_index}, playing={is_playing}, position={current_position}, volume={current_volume}")

        # Save volume
        self._config.set_volume(current_volume)

        # Save play queue and block any later async writes from overriding it
        try:
            self._playback.begin_shutdown()
            self._playback.save_queue(force=True)
        except Exception as e:
            logger.error(f"Error saving play queue: {e}")

        # Save playback position for queue restoration
        if current_position > 0:
            self._config.set_playback_position(current_position)

        # Save was_playing state
        self._config.set_was_playing(is_playing)

        try:
            if is_playing_cloud:
                # Save cloud playback state
                account_id = self._config.get_cloud_account_id()
                if account_id:
                    self._config.set_playback_source("cloud")
                    # Clear local track info when playing cloud
                    self._config.set_current_track_id(0)

                    # Save playback position to cloud_accounts table
                    current_item = self._player.current_track
                    if current_item and current_item.cloud_file_id:
                        position_seconds = current_position / 1000.0
                        self._cloud_account_service.update_playing_state(
                            account_id=account_id,
                            playing_fid=current_item.cloud_file_id,
                            position=position_seconds,
                            local_path=current_item.local_path or ''
                        )
            elif self._player.current_track:
                # Save local playback state
                current_item = self._player.current_track
                if current_item.is_local and current_item.track_id:
                    self._config.set_playback_source("local")
                    self._config.set_current_track_id(current_item.track_id)
                    # Clear cloud info when playing local
                    self._config.clear_cloud_account_id()
            else:
                # No track playing
                source = self._config.get_playback_source()
                if source != "cloud":
                    self._config.set_playback_source("local")
                    self._config.set_current_track_id(0)
                    self._config.set_playback_position(0)
                    self._config.set_was_playing(False)
                    self._config.clear_cloud_account_id()
        except Exception as e:
            logger.error(f"Error saving playback state: {e}")

        if self._force_quit_requested:
            event.accept()
            app = QApplication.instance()
            if app:
                app.quit()
            return

        # Stop playback AFTER saving state and explicitly shutdown backend resources.
        try:
            self._playback.shutdown()
        except Exception as e:
            logger.error(f"Error shutting down playback backend: {e}")

        # Clean up scan controller
        if hasattr(self, '_scan_controller') and self._scan_controller:
            # ScanController handles its own cleanup via deleteLater
            self._scan_controller = None

        # Clean up CloudDownloadService
        from services.cloud.download_service import CloudDownloadService
        try:
            CloudDownloadService.instance().cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up CloudDownloadService: {e}")

        # Clean up DownloadManager
        from services.download.download_manager import DownloadManager
        try:
            DownloadManager.instance().cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up DownloadManager: {e}")

        # Clean up lyrics controller threads
        if hasattr(self, '_lyrics_controller') and self._lyrics_controller:
            try:
                self._lyrics_controller.cleanup()
            except Exception as e:
                logger.error(f"Error cleaning up lyrics controller: {e}")

        # Disconnect EventBus signals to prevent memory leaks and callbacks to destroyed objects
        with suppress(RuntimeError):
            self._event_bus.track_changed.disconnect(self._on_track_changed)
        with suppress(RuntimeError):
            self._event_bus.position_changed.disconnect(self._on_position_changed)
        with suppress(RuntimeError):
            self._event_bus.playback_state_changed.disconnect(self._on_playback_state_changed)
        with suppress(RuntimeError):
            self._event_bus.download_completed.disconnect(self._on_cloud_download_completed)
        from services.download.download_manager import DownloadManager
        manager = DownloadManager.instance()
        with suppress(RuntimeError):
            manager.download_completed.disconnect(self._on_playlist_redownload_completed)
        with suppress(RuntimeError):
            manager.download_failed.disconnect(self._on_playlist_redownload_failed)

        # Close database
        self._bootstrap.shutdown_database()

        event.accept()

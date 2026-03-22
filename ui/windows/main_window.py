"""
Main application window for the music player.
"""
import logging

from app import Bootstrap
from domain.playback import PlaybackState
from infrastructure.database import DatabaseManager
from services import PlaybackService
from services.lyrics import LyricsLoader
from services.lyrics.lyrics_loader import LyricsDownloadWorker

# Configure logging
logger = logging.getLogger(__name__)

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QStackedWidget,
    QPushButton,
    QFileDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QStyle,
    QDialog,
)
from PySide6.QtCore import Qt, Signal, QThread, QSettings
from typing import Optional

from shiboken6 import isValid

from system.hotkeys import GlobalHotkeys, setup_media_key_handler
from system.i18n import t, set_language
from system.config import ConfigManager
from system.event_bus import EventBus
from ui.icons import IconName, IconButton, set_button_icon
from domain.track import Track
from domain.playlist_item import PlaylistItem
from domain.cloud import CloudProvider

# Import from specific submodules to avoid circular import
from .mini_player import MiniPlayer
from ui.views.library_view import LibraryView
from ui.views.playlist_view import PlaylistView
from ui.views.queue_view import QueueView
from ui.views.cloud_view import CloudDriveView
from ui.views.albums_view import AlbumsView
from ui.views.artists_view import ArtistsView
from ui.views.artist_view import ArtistView
from ui.views.album_view import AlbumView
from ui.views.online_music_view import OnlineMusicView
from ui.widgets.player_controls import PlayerControls
from ui.widgets.lyrics_widget_pro import LyricsWidget
from ui.dialogs.settings_dialog import GeneralSettingsDialog


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    play_track = Signal(int)  # Signal to play a track by ID
    lyricsHtmlReady = Signal(str)

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Initialize database
        self._db = DatabaseManager()

        # Initialize config manager
        self._config = ConfigManager(self._db)

        # Initialize QSettings for window geometry/splitter (Qt native format)
        self._settings = QSettings("HarmonyPlayer", "Harmony")

        # Initialize language from config
        saved_lang = self._config.get_language()
        set_language(saved_lang)

        # Initialize playback service with proper dependencies
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        self._playback = PlaybackService(
            self._db,
            self._config,
            cover_service=bootstrap.cover_service
        )

        # Keep reference to engine for backward compatibility
        # Use closures to capture self for methods that need access to db
        db = self._db
        playback = self._playback

        class PlayerProxy:
            """Proxy class for backward compatibility with components expecting old PlayerController interface."""

            @property
            def engine(self):
                return playback.engine

            @property
            def db(self):
                return db

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

            def save_queue(self):
                return playback.save_queue()

            def restore_queue(self):
                return playback.restore_queue()

            @property
            def cover_service(self):
                return playback.cover_service

            def get_track_cover(self, track_path: str, title: str, artist: str, album: str = "",
                                skip_online: bool = False):
                return playback.get_track_cover(track_path, title, artist, album, skip_online=skip_online)

            def save_cover_from_metadata(self, track_path: str, cover_data: bytes):
                return playback.save_cover_from_metadata(track_path, cover_data)

        self._player = PlayerProxy()

        # Event bus for signals
        self._event_bus = EventBus.instance()

        # Mini player (hidden by default)
        self._mini_player: Optional[MiniPlayer] = None

        # Lyrics sync
        self._current_lyric_line: Optional[int] = None

        # Lyrics loading thread (for async loading)
        self._lyrics_thread: Optional[QThread] = None
        # Lyrics load version - used to ignore stale thread results
        self._lyrics_load_version: int = 0
        # Lyrics download thread (for downloading from online)
        self._lyrics_download_thread: Optional[QThread] = None
        self._lyrics_download_path: str = ""
        self._lyrics_download_title: str = ""
        self._lyrics_download_artist: str = ""
        self._current_index = -1

        # Cloud account for current playback
        self._current_cloud_account = None

        # Original window title for restoring when paused
        self._original_title: str = ""

        # Current track title for window title
        self._current_track_title: str = ""

        # Setup UI
        self._setup_ui()
        self._setup_connections()
        self._setup_system_tray()
        self._setup_hotkeys()

        # Restore geometry
        self._restore_settings()

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

        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()

        self._library_view = LibraryView(self._db, self._player, self._config, bootstrap.cover_service)
        self._cloud_drive_view = CloudDriveView(self._db, self._player, self._config, bootstrap.cover_service)
        self._playlist_view = PlaylistView(self._db, self._player)
        self._queue_view = QueueView(self._player, self._db)
        self._albums_view = AlbumsView(bootstrap.library_service, bootstrap.cover_service)
        self._artists_view = ArtistsView(bootstrap.library_service, bootstrap.cover_service)
        self._artist_view = ArtistView(bootstrap.library_service, self._playback, bootstrap.cover_service)
        self._album_view = AlbumView(bootstrap.library_service, self._playback, bootstrap.cover_service)

        # Online music view with QQ Music service
        from services.cloud.qqmusic.qqmusic_service import QQMusicService
        qqmusic_credential = self._config.get("qqmusic.credential")
        qqmusic_service = None
        if qqmusic_credential:
            try:
                import json
                cred_dict = json.loads(qqmusic_credential) if isinstance(qqmusic_credential, str) else qqmusic_credential
                qqmusic_service = QQMusicService(cred_dict)
            except Exception:
                pass
        self._online_music_view = OnlineMusicView(self._config, qqmusic_service)

        self._stacked_widget.addWidget(self._library_view)       # 0
        self._stacked_widget.addWidget(self._cloud_drive_view)   # 1
        self._stacked_widget.addWidget(self._playlist_view)      # 2
        self._stacked_widget.addWidget(self._queue_view)         # 3
        self._stacked_widget.addWidget(self._albums_view)        # 4
        self._stacked_widget.addWidget(self._artists_view)       # 5
        self._stacked_widget.addWidget(self._artist_view)        # 6
        self._stacked_widget.addWidget(self._album_view)         # 7
        self._stacked_widget.addWidget(self._online_music_view)  # 8

        self._splitter.addWidget(self._stacked_widget)

        # Lyrics panel
        self._lyrics_panel = self._create_lyrics_panel()
        self._splitter.addWidget(self._lyrics_panel)

        # Set splitter proportions
        self._splitter.setStretchFactor(0, 2)  # Library gets 2/3
        self._splitter.setStretchFactor(1, 1)  # Lyrics gets 1/3
        self._splitter.setSizes([600, 400])  # Initial sizes

        content_layout.addWidget(self._splitter, 4)

        main_layout.addWidget(content_widget, 1)

        # Player controls
        self._player_controls = PlayerControls(self._player)
        main_layout.addWidget(self._player_controls)

        # Apply dark theme styling
        self._apply_styles()

    def _create_sidebar(self) -> QWidget:
        """Create the sidebar navigation."""
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")

        # Set sidebar width
        sidebar.setMinimumWidth(180)
        sidebar.setMaximumWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(5)

        # Logo
        logo_label = QLabel("Harmony")
        logo_label.setObjectName("logo")
        logo_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(logo_label)

        layout.addSpacing(20)

        # Navigation buttons with improved styling
        nav_style = """
            QPushButton {
                text-align: left;
                padding: 12px 18px;
                border-radius: 10px;
                background: transparent;
                color: #c0c0c0;
                border: 2px solid transparent;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #2a2a2a;
                color: #1db954;
                border: 2px solid #3a3a3a;
            }
            QPushButton:checked {
                background: #1db954;
                color: #000000;
                border: 2px solid #1db954;
                font-weight: bold;
            }
        """

        # Create navigation buttons with SVG icons (using IconButton for color changes)
        nav_buttons = [
            ("_nav_library", IconName.MUSIC, t("library")),
            ("_nav_albums", IconName.COMPACT_DISC, t("albums")),
            ("_nav_artists", IconName.MICROPHONE, t("artists")),
            ("_nav_cloud", IconName.CLOUD, t("cloud_drive")),
            ("_nav_online_music", IconName.GLOBE, t("online_music")),
            ("_nav_playlists", IconName.LIST, t("playlists")),
            ("_nav_queue", IconName.QUEUE, t("queue")),
            ("_nav_favorites", IconName.STAR, t("favorites")),
            ("_nav_history", IconName.CLOCK, t("history")),
        ]

        for attr_name, icon_name, text in nav_buttons:
            btn = IconButton(icon_name, text, size=18)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)

            btn.setStyleSheet(nav_style)
            setattr(self, attr_name, btn)
            layout.addWidget(btn)

        # Navigation buttons will be set correctly during restore
        # Default to library view initially
        self._nav_library.setChecked(True)

        layout.addStretch()

        # Language selector
        from system.i18n import get_language

        lang_text = "EN" if get_language() == "en" else "中文"
        self._language_btn = IconButton(IconName.GLOBE, lang_text, size=16)
        self._language_btn.setObjectName("languageBtn")
        self._language_btn.setCursor(Qt.PointingHandCursor)
        self._language_btn.setFixedHeight(32)
        self._language_btn.setStyleSheet("""
            QPushButton#languageBtn {
                background-color: #2a2a2a;
                color: #c0c0c0;
                border: 2px solid #3a3a3a;
                border-radius: 16px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton#languageBtn:hover {
                background-color: #3a3a3a;
                border: 2px solid #1db954;
                color: #1db954;
            }
        """)
        self._language_btn.clicked.connect(self._toggle_language)
        layout.addWidget(self._language_btn)

        # General Settings button
        settings_status = "✅" if self._config.get_ai_enabled() else "⚙️"
        self._settings_btn = QPushButton(f"⚙️ {t('settings')} {settings_status}")
        self._settings_btn.setObjectName("settingsBtn")
        self._settings_btn.setCursor(Qt.PointingHandCursor)
        self._settings_btn.setFixedHeight(32)
        self._settings_btn.setStyleSheet("""
            QPushButton#settingsBtn {
                background-color: #2a2a2a;
                color: #c0c0c0;
                border: 2px solid #3a3a3a;
                border-radius: 16px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton#settingsBtn:hover {
                background-color: #3a3a3a;
                border: 2px solid #1db954;
                color: #1db954;
            }
        """)
        self._settings_btn.clicked.connect(self._show_settings)
        layout.addWidget(self._settings_btn)

        # Add music button
        self._add_music_btn = QPushButton(t("add_music"))
        self._add_music_btn.setObjectName("addMusicBtn")
        self._add_music_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._add_music_btn)

        return sidebar

    def _create_lyrics_panel(self) -> QWidget:
        """Create the lyrics display panel."""
        panel = QWidget()
        panel.setObjectName("lyricsPanel")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(15, 20, 15, 20)

        # Title with download button
        title_layout = QHBoxLayout()

        self._lyrics_title = QLabel(t("lyrics"))
        self._lyrics_title.setObjectName("lyricsTitle")
        self._lyrics_title.setAlignment(Qt.AlignLeft)
        title_layout.addWidget(self._lyrics_title)

        title_layout.addStretch()

        # Download lyrics button
        self._download_lyrics_btn = QPushButton(t("download"))
        self._download_lyrics_btn.setObjectName("downloadLyricsBtn")
        self._download_lyrics_btn.setFixedHeight(28)
        self._download_lyrics_btn.clicked.connect(self._download_lyrics)
        title_layout.addWidget(self._download_lyrics_btn)

        layout.addLayout(title_layout)

        # Lyrics text browser (has built-in scrolling)
        self._lyrics_view = LyricsWidget()
        self._lyrics_view.setObjectName("lyricsContent")
        self._lyrics_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self._lyrics_view.customContextMenuRequested.connect(
            self._show_lyrics_context_menu
        )
        self._lyrics_view.setFocusPolicy(Qt.NoFocus)  # Prevent stealing focus

        layout.addWidget(self._lyrics_view, 1)  # Give it stretch to fill space

        return panel

    def _setup_connections(self):
        """Setup signal connections."""
        # Navigation
        self._nav_library.clicked.connect(lambda: self._show_page(0))
        self._nav_online_music.clicked.connect(lambda: self._show_page(8))
        self._nav_cloud.clicked.connect(lambda: self._show_page(1))
        self._nav_playlists.clicked.connect(lambda: self._show_page(2))
        self._nav_queue.clicked.connect(lambda: self._show_page(3))
        self._nav_albums.clicked.connect(lambda: self._show_page(4))
        self._nav_artists.clicked.connect(lambda: self._show_page(5))
        self._nav_favorites.clicked.connect(self._show_favorites)
        self._nav_history.clicked.connect(self._show_history)
        self._lyrics_view.seekRequested.connect(self._playback.seek)

        # Add music
        self._add_music_btn.clicked.connect(self._add_music)

        # Player connections - use EventBus for centralized signal handling
        self._event_bus.track_changed.connect(self._on_track_changed)
        self._event_bus.position_changed.connect(self._on_position_changed)
        self._event_bus.playback_state_changed.connect(self._on_playback_state_changed)

        # Cloud download events
        self._event_bus.download_completed.connect(self._on_cloud_download_completed)

        # View connections
        self._library_view.track_double_clicked.connect(self._play_track)
        self._library_view.cloud_file_double_clicked.connect(self._play_cloud_favorite)
        self._library_view.insert_to_queue.connect(self._insert_to_queue)
        self._library_view.add_to_queue.connect(self._add_to_queue)
        self._playlist_view.playlist_track_double_clicked.connect(self._play_playlist_track)
        self._queue_view.play_track.connect(self._play_track)
        self._queue_view.queue_reordered.connect(self._on_queue_reordered)
        self._cloud_drive_view.track_double_clicked.connect(self._play_cloud_track)
        self._cloud_drive_view.play_cloud_files.connect(self._play_cloud_playlist)

        # Online music view connections
        self._online_music_view.play_online_track.connect(self._play_online_track)
        self._online_music_view.insert_to_queue.connect(self._insert_online_track_to_queue)
        self._online_music_view.add_to_queue.connect(self._add_online_track_to_queue)
        self._online_music_view.play_online_tracks.connect(self._play_online_tracks)

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
        self._artist_view.track_double_clicked.connect(self._play_track)
        self._artist_view.insert_to_queue.connect(self._insert_tracks_to_queue)
        self._artist_view.add_to_queue.connect(self._add_tracks_to_queue)
        self._artist_view.add_to_playlist.connect(self._add_tracks_to_playlist)
        self._artist_view.download_cover_requested.connect(self._on_download_album_cover)

        # Album view connections
        self._album_view.play_tracks.connect(self._play_tracks)
        self._album_view.track_double_clicked.connect(self._play_track)
        self._album_view.insert_to_queue.connect(self._insert_tracks_to_queue)
        self._album_view.add_to_queue.connect(self._add_tracks_to_queue)
        self._album_view.add_to_playlist.connect(self._add_tracks_to_playlist)

        # Player controls connections
        self._player_controls.artist_clicked.connect(self._on_player_artist_clicked)
        self._player_controls.album_clicked.connect(self._on_player_album_clicked)

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

    def _apply_styles(self):
        """Apply modern dark theme styles with better colors."""
        style = """
            QMainWindow {
                background-color: #0a0a0a;
                color: #e0e0e0;
            }
            QWidget#sidebar {
                background-color: #141414;
                border-right: 1px solid #2a2a2a;
            }
            QLabel#logo {
                color: #1db954;
                font-size: 24px;
                font-weight: bold;
                text-shadow: 0 0 10px rgba(29, 185, 84, 0.3);
            }
            QPushButton#addMusicBtn {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 14px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton#addMusicBtn:hover {
                background-color: #1ed760;
                transform: scale(1.02);
            }
            QPushButton#downloadLyricsBtn {
                background: transparent;
                border: 2px solid #404040;
                color: #c0c0c0;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#downloadLyricsBtn:hover {
                border-color: #1db954;
                color: #1db954;
                background-color: rgba(29, 185, 84, 0.1);
            }
            QWidget#lyricsPanel {
                background-color: #1a1a1a;
                border-left: 1px solid #2a2a2a;
            }
            QLabel#lyricsTitle {
                color: #1db954;
                font-size: 16px;
                font-weight: bold;
                margin-bottom: 15px;
            }
            /* Splitter styling */
            QSplitter::handle {
                background-color: #2a2a2a;
                width: 2px;
            }
            QSplitter::handle:hover {
                background-color: #1db954;
            }
            /* Stacked widget background */
            QStackedWidget {
                background-color: #141414;
                border-radius: 8px;
            }
        """
        self.setStyleSheet(style)

    def _show_page(self, index: int):
        """Show a page in the stacked widget."""
        # Update nav button states
        self._nav_library.setChecked(index == 0)
        self._nav_cloud.setChecked(index == 1)
        self._nav_playlists.setChecked(index == 2)
        self._nav_queue.setChecked(index == 3)
        self._nav_albums.setChecked(index == 4)
        self._nav_artists.setChecked(index == 5)
        self._nav_online_music.setChecked(index == 8)
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(False)

        # Switch view
        self._stacked_widget.setCurrentIndex(index)

        # Auto-select first playlist when showing playlists
        if index == 2:  # Playlists is now at index 2
            playlist_view = self._stacked_widget.widget(2)
            if playlist_view and playlist_view._playlist_list.count() > 0:
                if playlist_view._current_playlist_id is None:
                    playlist_view._playlist_list.setCurrentRow(0)
                    first_item = playlist_view._playlist_list.item(0)
                    if first_item:
                        playlist_view._load_playlist(first_item.data(Qt.UserRole))

        # Reset library view mode when showing library (delayed to avoid blocking)
        if index == 0:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(50, self._library_view.show_all)

    def _show_favorites(self):
        """Show favorite tracks."""
        # Switch to library view first
        self._stacked_widget.setCurrentIndex(0)

        # Update nav button states
        self._nav_library.setChecked(False)
        self._nav_cloud.setChecked(False)
        self._nav_playlists.setChecked(False)
        self._nav_queue.setChecked(False)
        self._nav_albums.setChecked(False)
        self._nav_artists.setChecked(False)
        self._nav_favorites.setChecked(True)
        self._nav_history.setChecked(False)
        self._nav_online_music.setChecked(False)

        # Load favorites with delay to avoid blocking
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._library_view.show_favorites)

    def _show_history(self):
        """Show play history."""
        # Switch to library view first
        self._stacked_widget.setCurrentIndex(0)

        # Update nav button states
        self._nav_library.setChecked(False)
        self._nav_cloud.setChecked(False)
        self._nav_playlists.setChecked(False)
        self._nav_queue.setChecked(False)
        self._nav_albums.setChecked(False)
        self._nav_artists.setChecked(False)
        self._nav_favorites.setChecked(False)
        self._nav_online_music.setChecked(False)
        self._nav_history.setChecked(True)

        # Load history with delay to avoid blocking
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._library_view.show_history)

    def _on_album_clicked(self, album):
        """Handle album card click."""
        # Show album detail view
        self._album_view.set_album(album)
        self._stacked_widget.setCurrentIndex(7)

        # Update nav button states
        self._nav_library.setChecked(False)
        self._nav_cloud.setChecked(False)
        self._nav_playlists.setChecked(False)
        self._nav_queue.setChecked(False)
        self._nav_albums.setChecked(False)
        self._nav_artists.setChecked(False)
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(False)

    def _on_download_album_cover(self, album):
        """Handle download album cover request."""
        from ui.dialogs.album_cover_download_dialog import AlbumCoverDownloadDialog
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        dialog = AlbumCoverDownloadDialog(
            album,
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

    def _on_artist_clicked(self, artist):
        """Handle artist card click."""
        # Show artist detail view
        self._artist_view.set_artist(artist)
        self._stacked_widget.setCurrentIndex(6)

        # Update nav button states
        self._nav_library.setChecked(False)
        self._nav_cloud.setChecked(False)
        self._nav_playlists.setChecked(False)
        self._nav_queue.setChecked(False)
        self._nav_albums.setChecked(False)
        self._nav_artists.setChecked(False)
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(False)

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
        if not album_name or not artist_name:
            return
        # Get Album object by name and artist
        from app.bootstrap import Bootstrap
        bootstrap = Bootstrap.instance()
        album = bootstrap.library_service.get_album_by_name(album_name, artist_name)
        if album:
            self._on_album_clicked(album)

    def _on_download_artist_cover(self, artist):
        """Handle download artist cover request."""
        from ui.dialogs.artist_cover_download_dialog import ArtistCoverDownloadDialog
        from app.bootstrap import Bootstrap

        bootstrap = Bootstrap.instance()
        dialog = ArtistCoverDownloadDialog(
            artist,
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

    def _play_tracks(self, tracks):
        """Play a list of tracks."""
        if tracks:
            from domain.playlist_item import PlaylistItem
            from pathlib import Path

            # Create PlaylistItems with full track info (including local_path)
            items = []
            for track in tracks:
                if track.id and track.id > 0 and Path(track.path).exists():
                    items.append(PlaylistItem.from_track(track))

            if items:
                self._playback.engine.clear_playlist()
                self._playback.engine.load_playlist_items(items)
                self._playback.engine.play_at(0)

    def _add_music(self):
        """Add music to the library."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle(t("select_music_folder"))

        if dialog.exec():
            folder = dialog.selectedFiles()[0]
            self._scan_music_folder(folder)

    def _scan_music_folder(self, folder: str):
        """Scan a music folder and add tracks."""
        from pathlib import Path
        from PySide6.QtCore import QThread, Signal, QObject
        from services import MetadataService
        from datetime import datetime

        logger.info(f"[MainWindow] Scanning music folder: {folder}")

        # Create worker class for scanning
        # Get cover service for saving covers
        cover_service = Bootstrap.instance().cover_service

        class ScanWorker(QObject):
            progress = Signal(int, str)  # value, filename
            finished = Signal(int, int)  # added, skipped

            def __init__(self, folder_path, db, cover_svc):
                super().__init__()
                self.folder_path = folder_path
                self.db = db
                self.cover_service = cover_svc
                self._cancelled = False

            def cancel(self):
                self._cancelled = True

            def run(self):
                folder_path = Path(self.folder_path)
                supported_formats = MetadataService.SUPPORTED_FORMATS

                # Find all audio files
                audio_files = []
                for ext in supported_formats:
                    audio_files.extend(folder_path.rglob(f"*{ext}"))

                total_files = len(audio_files)

                if total_files == 0:
                    self.finished.emit(0, 0)
                    return

                added_count = 0
                skipped_count = 0

                for i, audio_file in enumerate(audio_files):
                    if self._cancelled:
                        break

                    # Emit progress
                    self.progress.emit(int((i / total_files) * 100), audio_file.name)

                    try:
                        # Check if track already exists
                        existing = self.db.get_track_by_path(str(audio_file))
                        if existing:
                            skipped_count += 1
                            continue

                        # Extract metadata
                        metadata = MetadataService.extract_metadata(str(audio_file))

                        # Save cover art from metadata
                        cover_path = self.cover_service.save_cover_from_metadata(
                            str(audio_file), metadata.get("cover")
                        )

                        # Create track object
                        track = Track(
                            path=str(audio_file),
                            title=metadata.get("title", audio_file.stem),
                            artist=metadata.get("artist", ""),
                            album=metadata.get("album", ""),
                            duration=metadata.get("duration", 0.0),
                            cover_path=cover_path,
                            created_at=datetime.now(),
                        )

                        # Add to database
                        self.db.add_track(track)
                        added_count += 1

                    except Exception as e:
                        logger.error(f"Error adding track {audio_file}: {e}")
                        skipped_count += 1

                self.finished.emit(added_count, skipped_count)

        # Create progress dialog
        from PySide6.QtWidgets import QProgressDialog
        progress = QProgressDialog(t("scanning"), t("cancel"), 0, 100, self)
        progress.setWindowTitle(t("scanning"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        progress.show()

        # Create worker and thread
        self._scan_worker = ScanWorker(folder, self._db, cover_service)
        self._scan_thread = QThread()
        self._scan_worker.moveToThread(self._scan_thread)

        # Connect signals
        def on_progress(value, filename):
            if not progress.wasCanceled():
                progress.setValue(value)
                progress.setLabelText(f"{t('scanning')}: {filename}")

        def on_finished(added, skipped):
            progress.close()
            logger.info(f"[MainWindow] Scan complete: {added} added, {skipped} skipped")
            # Refresh albums and artists tables after scanning
            if added > 0:
                self._db.refresh_albums()
                self._db.refresh_artists()
            self._library_view.refresh()
            self._albums_view.refresh()
            self._artists_view.refresh()
            self._scan_thread.quit()
            self._scan_thread.wait()

        def on_cancel():
            self._scan_worker.cancel()

        self._scan_worker.progress.connect(on_progress)
        self._scan_worker.finished.connect(on_finished)
        progress.canceled.connect(on_cancel)
        self._scan_thread.started.connect(self._scan_worker.run)

        # Start thread
        self._scan_thread.start()

    def _toggle_language(self):
        """Toggle between English and Chinese."""
        from system.i18n import get_language, set_language

        current_lang = get_language()
        new_lang = "zh" if current_lang == "en" else "en"
        set_language(new_lang)

        # Save language preference
        self._config.set_language(new_lang)

        # Update button text
        self._language_btn.setText("EN" if new_lang == "en" else "中文")

        # Refresh the UI to apply translations
        self._refresh_ui_texts()

    def _refresh_ui_texts(self):
        """Refresh UI texts after language change."""
        # Update window title
        self.setWindowTitle(t("app_title"))

        # Update sidebar navigation buttons (text only, icons stay the same)
        self._nav_library.setText(t("library"))
        self._nav_albums.setText(t("albums"))
        self._nav_artists.setText(t("artists"))
        self._nav_cloud.setText(t("cloud_drive"))
        self._nav_playlists.setText(t("playlists"))
        self._nav_queue.setText(t("queue"))
        self._nav_favorites.setText(t("favorites"))
        self._nav_history.setText(t("history"))
        self._add_music_btn.setText(t("add_music"))
        self._nav_online_music.setText(t("online_music"))

        # Update lyrics panel
        self._lyrics_title.setText(t("lyrics"))
        self._download_lyrics_btn.setText(t("download"))

        # Refresh player controls
        self._player_controls.refresh_ui()

        # Refresh views
        self._library_view.refresh()
        self._cloud_drive_view.refresh_ui()  # Refresh cloud drive view
        self._playlist_view._refresh_playlists()
        self._queue_view.refresh_queue()
        self._albums_view.refresh_ui()
        self._artists_view.refresh_ui()
        self._artist_view.refresh_ui()
        self._album_view.refresh_ui()
        self._online_music_view.refresh_ui()  # Refresh online music view

        # Update settings button status
        settings_status = "✅" if self._config.get_ai_enabled() else "⚙️"
        self._settings_btn.setText(f"⚙️ {t('settings')} {settings_status}")

    def _show_settings(self):
        """Show general settings dialog."""

        dialog = GeneralSettingsDialog(self._config, self)
        if dialog.exec_():
            # Update settings button status after settings change
            settings_status = "✅" if self._config.get_ai_enabled() else "⚙️"
            self._settings_btn.setText(f"⚙️ {t('settings')} {settings_status}")

    def show_help(self):
        """Show help dialog."""
        from ui.dialogs.help_dialog import HelpDialog

        dialog = HelpDialog(self)
        dialog.exec_()

    def _play_track(self, track_id: int):
        """Play a local track from library (loads entire library as playlist)."""
        self._playback.play_local_track(track_id)

    def _play_playlist_track(self, playlist_id: int, track_id: int):
        """Play a track from a specific playlist."""
        self._playback.play_playlist_track(playlist_id, track_id)

    def _play_cloud_favorite(self, cloud_file_id: str, account_id: int):
        """Play a cloud file from favorites."""

        if not cloud_file_id or not account_id:
            return

        # Get cloud account
        account = self._db.get_cloud_account(account_id)
        if not account:
            logger.error(f"[MainWindow] Cloud account {account_id} not found")
            return

        # Get cloud file info
        cloud_file = self._db.get_cloud_file_by_file_id(cloud_file_id)
        if cloud_file:
            # Create PlaylistItem from cloud file
            item = PlaylistItem.from_cloud_file(cloud_file, account_id)
            self._playback.engine.load_playlist_items([item])
            self._playback.engine.play()
        else:
            # File not in cache, need to get from cloud
            logger.warning(f"[MainWindow] Cloud file {cloud_file_id} not found in cache")
            # Fallback: create basic item with file_id
            item = PlaylistItem(
                source_type=CloudProvider.QUARK,
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
            source_type=CloudProvider.QUARK,
            local_path=temp_path,
            title='Cloud Track',
            needs_download=False
        )
        self._playback.engine.load_playlist_items([item])
        self._playback.engine.play()

    def _play_online_track(self, song_mid: str, local_path: str, metadata: dict = None):
        """Play downloaded online track.

        Args:
            song_mid: Song MID
            local_path: Local file path
            metadata: Optional metadata dict with title, artist, album, duration
        """
        logger.info(f"Playing online track: mid={song_mid}, path={local_path}")

        if not local_path:
            logger.error("No local path for online track")
            return

        # Get metadata from argument or use defaults
        title = "Online Track"
        artist = ""
        album = ""
        duration = 0.0

        if metadata:
            title = metadata.get("title") or title
            artist = metadata.get("artist") or ""
            album = metadata.get("album") or ""
            duration = metadata.get("duration") or 0.0

        # Create a playlist item for the downloaded track
        # Use ONLINE provider for online music
        item = PlaylistItem(
            source_type=CloudProvider.ONLINE,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,
            needs_download=False
        )
        self._playback.engine.load_playlist_items([item])
        self._playback.engine.play()

    def _add_online_track_to_queue(self, song_mid: str, metadata: dict):
        """Add online track to the play queue (deferred download).

        Args:
            song_mid: Song MID
            metadata: Metadata dict with title, artist, album, duration
        """
        title = metadata.get("title", "Online Track")
        artist = metadata.get("artist", "")
        album = metadata.get("album", "")
        duration = metadata.get("duration", 0.0)

        # Check if already cached
        download_service = self._online_music_view._download_service
        local_path = ""
        needs_download = True

        if download_service.is_cached(song_mid):
            local_path = download_service.get_cached_path(song_mid)
            needs_download = False

        item = PlaylistItem(
            source_type=CloudProvider.ONLINE,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,
            needs_download=needs_download
        )

        self._playback.engine.add_track(item)

        # Save queue
        self._playback.save_queue()

        # Show notification
        self._status_bar = self.statusBar()
        if needs_download:
            self._status_bar.showMessage(f"✓ {t('added_to_queue')}: {title}", 3000)
        else:
            self._status_bar.showMessage(f"✓ {t('added_to_queue')}: {title}", 3000)

    def _insert_online_track_to_queue(self, song_mid: str, metadata: dict):
        """Insert online track after current playing track.

        Args:
            song_mid: Song MID
            metadata: Metadata dict with title, artist, album, duration
        """
        title = metadata.get("title", "Online Track")
        artist = metadata.get("artist", "")
        album = metadata.get("album", "")
        duration = metadata.get("duration", 0.0)

        # Check if already cached
        download_service = self._online_music_view._download_service
        local_path = ""
        needs_download = True

        if download_service.is_cached(song_mid):
            local_path = download_service.get_cached_path(song_mid)
            needs_download = False

        item = PlaylistItem(
            source_type=CloudProvider.ONLINE,
            local_path=local_path,
            title=title,
            artist=artist,
            album=album,
            duration=duration,
            cloud_file_id=song_mid,
            needs_download=needs_download
        )

        # Insert after current track
        current_index = self._playback.engine.current_index
        insert_index = current_index + 1 if current_index >= 0 else 0
        self._playback.engine.insert_track(insert_index, item)

        # Save queue
        self._playback.save_queue()

        # Show notification
        self._status_bar = self.statusBar()
        self._status_bar.showMessage(f"✓ {t('insert_to_queue')}: {title}", 3000)

    def _play_online_tracks(self, start_index: int, tracks_data: list):
        """Play multiple online tracks, clearing queue first.

        Args:
            start_index: Index of track to start playing
            tracks_data: List of (song_mid, metadata_dict) tuples
        """
        logger.info(f"Playing {len(tracks_data)} online tracks, starting at {start_index}")

        download_service = self._online_music_view._download_service
        items = []

        for song_mid, metadata in tracks_data:
            title = metadata.get("title", "Online Track")
            artist = metadata.get("artist", "")
            album = metadata.get("album", "")
            duration = metadata.get("duration", 0.0)

            # Check if already cached
            local_path = ""
            needs_download = True

            if download_service.is_cached(song_mid):
                local_path = download_service.get_cached_path(song_mid)
                needs_download = False

            item = PlaylistItem(
                source_type=CloudProvider.ONLINE,
                local_path=local_path,
                title=title,
                artist=artist,
                album=album,
                duration=duration,
                cloud_file_id=song_mid,
                needs_download=needs_download
            )
            items.append(item)

        # Clear queue and load all items
        self._playback.engine.load_playlist_items(items)
        self._playback.save_queue()

        # Play from start index
        if 0 <= start_index < len(items):
            self._playback.engine.play_at(start_index)

        # Show notification
        self._status_bar = self.statusBar()
        self._status_bar.showMessage(f"✓ {t('playing')}: {tracks_data[start_index][1].get('title', 'Online Track')}", 3000)

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

        # If first file is already downloaded, update it
        if temp_path and index < len(cloud_files):
            self._playback.on_cloud_file_downloaded(cloud_files[index].file_id, temp_path)

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
        from domain.cloud import CloudProvider

        # Reset lyric line tracking
        self._current_lyric_line = None

        # Convert to dict for backward compatibility
        song_mid = None
        is_online = False

        if isinstance(track_item, PlaylistItem):
            track_dict = track_item.to_dict()
            track_id = track_item.track_id
            title = track_item.title
            artist = track_item.artist
            path = track_item.local_path
            is_cloud = track_item.is_cloud
            needs_metadata = track_item.needs_metadata
            song_mid = track_item.cloud_file_id
            is_online = track_item.source_type == CloudProvider.ONLINE
        elif isinstance(track_item, int):
            # Handle case where track_item is just an ID
            track_id = track_item
            track_dict = None
            title = ""
            artist = ""
            path = ""
            is_cloud = False
            needs_metadata = False
        else:
            track_dict = track_item
            track_id = track_dict.get("id") if track_dict else None
            title = track_dict.get("title", "") if track_dict else ""
            artist = track_dict.get("artist", "") if track_dict else ""
            path = track_dict.get("path", "") if track_dict else ""
            is_cloud = not track_id or track_id < 0
            needs_metadata = track_dict.get("needs_metadata", False) if track_dict else False
            # Check if online track from dict
            source_type = track_dict.get("source_type", "")
            is_online = source_type == "online" or source_type == CloudProvider.ONLINE.value
            song_mid = track_dict.get("cloud_file_id")

        # Sync selection in both library and queue views
        if track_id and track_id > 0:
            # Select in library view
            self._library_view._select_track_by_id(track_id)
            # Select in queue view (if it exists in queue)
            self._queue_view._select_track_by_id(track_id)

        self._lyrics_view.set_lyrics(t("no_lyrics"))
        if not track_dict:
            return

        # Save current track title for window title update
        self._current_track_title = f"{title} - {artist}" if artist else title

        # For online tracks, always try to load lyrics (even without local path)
        if is_online and song_mid:
            logger.debug(f"[MainWindow] Loading lyrics for online track: song_mid={song_mid}")
            self._load_lyrics_async(path, title, artist, song_mid=song_mid, is_online=True)
            return

        # Skip loading lyrics for cloud files without local path
        if not path or path.strip() in ('', '.', '/'):
            return

        # Skip loading lyrics only if metadata is pending AND file is being downloaded
        # If local_path exists, try to load lyrics (will retry after metadata update if needed)
        if needs_metadata and is_cloud and not track_id:
            logger.debug(f"[MainWindow] Skipping lyrics load, metadata pending for: {title}")
            return

        # Load lyrics asynchronously using LyricsLoader
        self._load_lyrics_async(path, title, artist)

    def _on_playback_state_changed(self, state: str):
        """Handle playback state change to update window title.

        Args:
            state: "playing", "paused", or "stopped"
        """
        if state == "playing":
            # Save original title if not saved yet
            if not self._original_title:
                self._original_title = self.windowTitle()
            # Update window title to show current track
            if self._current_track_title:
                self.setWindowTitle(self._current_track_title)
        else:
            # Paused or stopped - restore original title
            if self._original_title:
                self.setWindowTitle(self._original_title)

    def _load_lyrics_async(self, path: str, title: str, artist: str,
                           song_mid: str = None, is_online: bool = False):
        """Load lyrics asynchronously.

        Uses version-based mechanism to avoid blocking UI.
        Old threads are allowed to finish but their results are ignored.

        Args:
            path: Path to the audio file
            title: Track title
            artist: Track artist
            song_mid: QQ Music song MID (for online tracks)
            is_online: Whether this is an online QQ Music track
        """
        # Increment version to invalidate any pending results
        self._lyrics_load_version += 1
        current_version = self._lyrics_load_version

        # Clean up old thread before creating new one
        if self._lyrics_thread and isValid(self._lyrics_thread):
            if self._lyrics_thread.isRunning():
                self._lyrics_thread.requestInterruption()
                # Wait for thread to finish to avoid "Destroyed while running" error
                if not self._lyrics_thread.wait(500):  # Wait up to 500ms
                    self._lyrics_thread.terminate()
                    self._lyrics_thread.wait(100)
            # Disconnect signals and delete old thread
            try:
                self._lyrics_thread.finished.disconnect()
                self._lyrics_thread.lyrics_ready.disconnect()
            except RuntimeError:
                pass  # Already disconnected
            self._lyrics_thread.deleteLater()
            self._lyrics_thread = None

        # Create new lyrics loader (LyricsLoader extends QThread, no need for moveToThread)
        self._lyrics_thread = LyricsLoader(path, title, artist, song_mid=song_mid, is_online=is_online)
        # Store version with the thread for result validation
        self._lyrics_thread._load_version = current_version

        # Connect signals
        self._lyrics_thread.lyrics_ready.connect(
            lambda lyrics: self._on_lyrics_ready_v2(lyrics, current_version)
        )
        self._lyrics_thread.finished.connect(self._on_lyrics_thread_finished)

        # Start loading
        self._lyrics_thread.start()

    def _on_lyrics_ready_v2(self, lyrics: str, version: int):
        """Handle lyrics loaded asynchronously with version check."""
        # Ignore if this is from an old thread
        if version != self._lyrics_load_version:
            logger.debug(f"[MainWindow] Ignoring stale lyrics result (version {version}, current {self._lyrics_load_version})")
            return

        if lyrics:
            self._lyrics_view.set_lyrics(lyrics)
        else:
            self._lyrics_view.set_lyrics(t("no_lyrics"))

    def _on_lyrics_thread_finished(self):
        """Handle lyrics thread finished."""
        sender = self.sender()
        if sender:
            # Always delete the finished thread, not just current one
            sender.deleteLater()
            # Only clear reference if this is the current thread
            if sender == self._lyrics_thread:
                self._lyrics_thread = None

    def _download_lyrics(self):
        """Download lyrics for current track - shows search dialog for user to select."""
        from ui.dialogs.lyrics_download_dialog import LyricsDownloadDialog

        # Get current track
        current_item = self._playback.current_track
        if not current_item:
            return

        track_path = current_item.local_path
        track_title = current_item.title
        track_artist = current_item.artist
        track_album = current_item.album
        track_duration = current_item.duration

        if not track_path:
            QMessageBox.warning(self, t("error"), t("cloud_lyrics_download_not_supported"))
            return

        # Store track info for later use
        self._lyrics_download_path = track_path
        self._lyrics_download_title = track_title
        self._lyrics_download_artist = track_artist

        # Show selection dialog (dialog handles search internally)
        result = LyricsDownloadDialog.show_dialog(
            track_title,
            track_artist,
            track_path,
            track_album,
            track_duration,
            self
        )

        if result:
            selected_song, download_cover = result
            self._download_lyrics_for_song(selected_song, download_cover)

    def _download_lyrics_for_song(self, song_info: dict, download_cover: bool = True):
        """Download lyrics for a specific song.

        Args:
            song_info: Dictionary with song information (id, title, artist, source, etc.)
            download_cover: Whether to download cover art (default: True)
        """
        # Clean up existing download thread if any
        if self._lyrics_download_thread and isValid(
                self._lyrics_download_thread) and self._lyrics_download_thread.isRunning():
            self._lyrics_download_thread.quit()
            self._lyrics_download_thread.wait(100)

        # Don't clear current lyrics - wait for download to complete
        # self._lyrics_view.set_lyrics(t("downloading") + "...")

        # Create download worker with specific song info
        self._lyrics_download_thread = LyricsDownloadWorker(
            self._lyrics_download_path,
            self._lyrics_download_title,
            self._lyrics_download_artist,
            song_id=song_info['id'],
            source=song_info['source'],
            accesskey=song_info.get('accesskey'),
            download_cover=download_cover,
            cover_service=self._playback.cover_service,
            lyrics_data=song_info.get('lyrics')  # Pre-fetched lyrics for LRCLIB
        )

        self._lyrics_download_thread.lyrics_downloaded.connect(self._on_lyrics_downloaded)
        self._lyrics_download_thread.download_failed.connect(self._on_lyrics_download_failed)

        # Only connect cover_downloaded if download_cover is True
        if download_cover:
            self._lyrics_download_thread.cover_downloaded.connect(self._on_cover_downloaded)

        self._lyrics_download_thread.finished.connect(self._lyrics_download_thread.deleteLater)
        self._lyrics_download_thread.start()

    def _on_lyrics_downloaded(self, path: str, lyrics: str):
        """Handle lyrics download success."""
        self._lyrics_view.set_lyrics(lyrics)

    def _on_cover_downloaded(self, cover_path: str):
        """Handle cover download success - update database and UI."""
        logger.info(f"[MainWindow] _on_cover_downloaded called with cover_path: {cover_path}")

        if not cover_path:
            logger.warning("[MainWindow] cover_path is empty, returning")
            return

        # Use the stored download path to find the track in database
        track_path = self._lyrics_download_path
        if not track_path:
            logger.warning("[MainWindow] No track path stored, cannot find track in database")
            return

        logger.info(f"[MainWindow] Looking for track with path: {track_path}")

        # Find track by path in database
        track = self._db.get_track_by_path(track_path)
        if not track:
            logger.warning(f"[MainWindow] No track found in database with path: {track_path}")
            return

        track_id = track.id
        logger.info(f"[MainWindow] Found track in database: id={track_id}, title={track.title}")

        # Update cover_path in database
        try:
            logger.info(f"[MainWindow] Updating cover_path for track {track_id}: {cover_path}")
            success = self._db.update_track_cover_path(track_id, cover_path)
            logger.info(f"[MainWindow] Database update result: {success}")

            if success:
                # Update current track item's cover_path if it exists
                current_item = self._playback.current_track
                if current_item:
                    # Match by track_id OR by local path (for cloud downloads)
                    is_match = (current_item.track_id == track_id or
                                current_item.local_path == track_path)
                    if is_match:
                        old_cover = current_item.cover_path
                        current_item.cover_path = cover_path
                        logger.info(f"[MainWindow] Updated current item's cover_path: {old_cover} -> {cover_path}")

                        # Also update track_id if it was None (for newly saved cloud tracks)
                        if not current_item.track_id:
                            current_item.track_id = track_id
                            logger.info(f"[MainWindow] Updated current item's track_id: {track_id}")

                # Emit event to refresh UI
                self._event_bus.metadata_updated.emit(track_id)
                logger.info(f"[MainWindow] Emitted metadata_updated event for track {track_id}")
            else:
                logger.warning(f"[MainWindow] Database update returned False for track {track_id}")

        except Exception as e:
            logger.error(f"[MainWindow] Error updating cover path: {e}", exc_info=True)

    def _on_lyrics_download_failed(self, error: str):
        """Handle lyrics download failure."""
        self._lyrics_view.set_lyrics(t("no_lyrics"))

    def _on_lyrics_download_success(self, lyrics):
        """Handle successful lyrics download."""
        self._lyrics_view.set_lyrics(lyrics)

    def _on_lyrics_download_error(self, error_type: str):
        """Handle lyrics download error."""
        if error_type == "parse_failed":
            self._lyrics_view.set_lyrics(t("lyrics_downloaded_parsing_failed"))
        else:  # not_found
            self._lyrics_view.set_lyrics(t("lyrics_not_found"))

    def _show_lyrics_context_menu(self, pos):
        """Show context menu for lyrics panel."""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #282828;
                color: #ffffff;
                border: 1px solid #404040;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #1db954;
            }
        """)

        # 下载歌词
        download_action = menu.addAction(t("download_lyrics"))
        download_action.triggered.connect(self._download_lyrics)

        # 手动输入歌词
        edit_action = menu.addAction(t("edit_lyrics"))
        edit_action.triggered.connect(self._edit_lyrics)

        # 删除歌词文件
        delete_action = menu.addAction(t("delete_lyrics"))
        delete_action.triggered.connect(self._delete_lyrics)

        menu.addSeparator()

        # 打开文件位置
        open_location_action = menu.addAction(t("open_file_location"))
        open_location_action.triggered.connect(self._open_lyrics_file_location)

        # 刷新歌词
        refresh_action = menu.addAction(t("refresh"))
        refresh_action.triggered.connect(self._refresh_lyrics)

        menu.exec_(self._lyrics_view.mapToGlobal(pos))

    def _refresh_lyrics(self):
        """Refresh lyrics display."""
        # First check if we have a current track from the engine (works for both local and cloud)
        current_track = self._player.engine.current_track
        if current_track:
            self._on_track_changed(current_track)
            return

        # Fallback to database lookup for local files
        if self._player.current_track_id:
            track = self._db.get_track(self._player.current_track_id)
            if track:
                track_dict = {
                    "path": track.path,
                    "title": track.title,
                    "artist": track.artist,
                    "id": track.id,
                }
                self._on_track_changed(track_dict)

    def _edit_lyrics(self):
        """Edit lyrics manually."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QTextEdit,
            QPushButton,
            QLabel,
            QMessageBox,
        )
        from services import LyricsService
        from utils.lrc_parser import detect_and_parse, detect_format

        # Check if we're playing a track
        current_track = self._player.engine.current_track
        if not current_track:
            QMessageBox.information(self, t("info"), t("no_track_playing"))
            return

        # Check if this is a cloud file (no id or empty id)
        is_cloud_file = not current_track.get("id")

        if is_cloud_file:
            # For cloud files, use the current track info directly
            track_path = current_track.get("path", "")
            track_title = current_track.get("title", "Unknown")
            track_artist = current_track.get("artist", "Unknown")

            if not track_path:
                QMessageBox.warning(self, t("error"), t("cloud_lyrics_edit_not_supported"))
                return
        else:
            # For local files, get from database
            if not self._player.current_track_id:
                return

            track = self._db.get_track(self._player.current_track_id)
            if not track:
                return

            track_path = track.path
            track_title = track.title
            track_artist = track.artist

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(t("edit_lyrics_title"))
        dialog.setMinimumSize(600, 500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #282828;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QTextEdit {
                background-color: #181818;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton[role="cancel"] {
                background-color: #404040;
                color: #ffffff;
            }
            QPushButton[role="cancel"]:hover {
                background-color: #505050;
            }
        """)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(f"{track_title} - {track_artist}")
        info_label.setStyleSheet("color: #1db954; font-size: 14px; padding: 5px;")
        layout.addWidget(info_label)

        # Help text
        help_label = QLabel(t("lyrics_format_help"))
        help_label.setStyleSheet("color: #808080; font-size: 11px; padding: 5px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Text editor
        text_edit = QTextEdit()
        text_edit.setPlaceholderText(t("enter_lyrics_here"))

        # Load existing lyrics if available (read directly from file to ensure fresh content)
        from pathlib import Path

        track_file = Path(track_path)

        lyrics_content = None

        # Try multiple encodings
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16']

        # Try different lyrics file extensions in priority order: .yrc, .qrc, .lrc
        for ext in ['.yrc', '.qrc', '.lrc']:
            lyrics_path = track_file.with_suffix(ext)
            if lyrics_path.exists():
                for encoding in encodings:
                    try:
                        with open(lyrics_path, 'r', encoding=encoding) as f:
                            lyrics_content = f.read()
                        print(f"Loaded lyrics from {lyrics_path} with {encoding} encoding")
                        break
                    except (UnicodeDecodeError, UnicodeError):
                        continue
                    except Exception as e:
                        logger.error(f"Error reading {lyrics_path}: {e}", exc_info=True)
                        break
                if lyrics_content:
                    break

        # Load lyrics into editor if found
        if lyrics_content and lyrics_content.strip():
            text_edit.setPlainText(lyrics_content)

        layout.addWidget(text_edit)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")

        save_btn = QPushButton(t("save"))
        save_btn.setObjectName("saveBtn")

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)

        layout.addLayout(button_layout)

        # Save function
        def save_lyrics():
            content = text_edit.toPlainText().strip()
            if not content:
                QMessageBox.warning(dialog, t("warning"), t("lyrics_cannot_be_empty"))
                return

            # Parse lyrics using detect_and_parse (supports LRC, YRC, QRC formats)
            parsed_lyrics = detect_and_parse(content)
            if not parsed_lyrics:
                QMessageBox.warning(dialog, t("warning"), t("invalid_lyrics_format"))
                return

            # Detect format and save with appropriate extension
            lyrics_format = detect_format(content)

            # Save lyrics with correct extension
            from pathlib import Path
            track_file = Path(track_path)

            if lyrics_format == 'yrc':
                save_path = track_file.with_suffix('.yrc')
            elif lyrics_format == 'qrc':
                save_path = track_file.with_suffix('.qrc')
            else:
                save_path = track_file.with_suffix('.lrc')

            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(content)

                # Delete old lyrics files with different extensions
                for ext in ['.lrc', '.yrc', '.qrc']:
                    old_path = track_file.with_suffix(ext)
                    if old_path.exists() and old_path != save_path:
                        try:
                            old_path.unlink()
                        except Exception:
                            pass

                QMessageBox.information(dialog, t("success"), t("lyrics_saved"))
                # Refresh lyrics display
                self._refresh_lyrics()
                dialog.accept()
            except Exception as e:
                logger.error(f"Error saving lyrics: {e}", exc_info=True)
                QMessageBox.warning(dialog, "Error", t("lyrics_save_failed"))

        save_btn.clicked.connect(save_lyrics)
        cancel_btn.clicked.connect(dialog.reject)

        dialog.exec()

    def _delete_lyrics(self):
        """Delete lyrics file."""
        from PySide6.QtWidgets import QMessageBox
        from services import LyricsService

        # Check if we're playing a track
        current_track = self._player.engine.current_track
        if not current_track:
            QMessageBox.information(self, t("info"), t("no_track_playing"))
            return

        # Check if this is a cloud file (no id or empty id)
        is_cloud_file = not current_track.get("id")

        if is_cloud_file:
            # For cloud files, use the current track info directly
            track_path = current_track.get("path", "")

            if not track_path:
                QMessageBox.warning(self, t("error"), t("cloud_lyrics_delete_not_supported"))
                return
        else:
            # For local files, get from database
            if not self._player.current_track_id:
                return

            track = self._db.get_track(self._player.current_track_id)
            if not track:
                return

            track_path = track.path

        # Check if lyrics file exists
        if not LyricsService.lyrics_file_exists(track_path):
            QMessageBox.information(self, t("info"), t("no_lyrics_file_to_delete"))
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            t("confirm_delete_lyrics"),
            t("confirm_delete_lyrics_message"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if LyricsService.delete_lyrics(track_path):
                # Clear lyrics immediately and reset state
                self._current_lyric_line = None
                self._lyrics_view.set_lyrics(t("no_lyrics"))
                QMessageBox.information(self, t("success"), t("lyrics_deleted"))
            else:
                QMessageBox.warning(self, "Error", t("lyrics_delete_failed"))

    def _open_lyrics_file_location(self):
        """Open the lyrics file location for the current track."""
        import platform
        import subprocess
        import shutil
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox

        # Check if we're playing a track
        current_track = self._player.engine.current_track
        if not current_track:
            QMessageBox.information(self, t("info"), t("no_track_playing"))
            return

        # Check if this is a cloud file (no id or empty id)
        is_cloud_file = not current_track.get("id")

        if is_cloud_file:
            # For cloud files, use the current track info directly
            track_path = current_track.get("path", "")

            if not track_path:
                QMessageBox.warning(self, t("error"), t("cloud_lyrics_location_not_supported"))
                return
        else:
            # For local files, get from database
            if not self._player.current_track_id:
                return

            track = self._db.get_track(self._player.current_track_id)
            if not track:
                return

            track_path = track.path

        track_file = Path(track_path)

        # Find lyrics file (check .yrc, .qrc, .lrc in priority order)
        lyrics_path = None
        for ext in ['.yrc', '.qrc', '.lrc']:
            candidate = track_file.with_suffix(ext)
            if candidate.exists():
                lyrics_path = candidate
                break

        if not lyrics_path:
            QMessageBox.information(self, t("info"), t("lyrics_file_not_found"))
            return

        try:
            system = platform.system()

            if system == "Windows":
                subprocess.Popen(["explorer", f"/select,{lyrics_path}"])

            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(lyrics_path)])

            else:
                # Linux
                # Try to select file in supported file managers
                file_managers = {
                    "nautilus": ["nautilus", "--select", str(lyrics_path)],
                    "dolphin": ["dolphin", "--select", str(lyrics_path)],
                    "caja": ["caja", "--select", str(lyrics_path)],
                    "nemo": ["nemo", str(lyrics_path)],
                }

                for fm, cmd in file_managers.items():
                    if shutil.which(fm):
                        subprocess.Popen(cmd)
                        return

                # fallback
                subprocess.Popen(["xdg-open", str(lyrics_path.parent)])

        except Exception as e:
            logger.error(f"Failed to open file location: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"{t('open_file_location_failed')}: {e}")

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
            reply = QMessageBox.question(
                self,
                t("no_playlists"),
                t("no_playlists_message"),
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._nav_playlists.click()
            return

        # If only one playlist, add directly without showing dialog
        if dialog.has_single_playlist():
            playlist_name = dialog.get_single_playlist()
            dialog.deleteLater()
            playlists = bootstrap.library_service.get_all_playlists()
            playlist = next((p for p in playlists if p.name == playlist_name), None)
            if playlist:
                added_count = 0
                duplicate_count = 0
                for track_id in track_ids:
                    if self._db.add_track_to_playlist(playlist.id, track_id):
                        added_count += 1
                    else:
                        duplicate_count += 1

                if duplicate_count == 0:
                    msg = t("added_tracks_to_playlist").format(count=added_count, name=playlist_name)
                    QMessageBox.information(self, t("success"), msg)
                elif added_count == 0:
                    msg = t("all_tracks_duplicate").format(count=duplicate_count, name=playlist_name)
                    QMessageBox.warning(self, t("duplicate"), msg)
                else:
                    msg = t("added_skipped_duplicates").format(added=added_count, duplicates=duplicate_count)
                    QMessageBox.information(self, t("partially_added"), msg)
            return

        dialog.set_track_ids(track_ids)

        if dialog.exec() == QDialog.Accepted:
            playlist_name = dialog.get_selected_playlist()
            if playlist_name:
                playlists = bootstrap.library_service.get_all_playlists()
                playlist = next((p for p in playlists if p.name == playlist_name), None)
                if playlist:
                    added_count = 0
                    duplicate_count = 0
                    for track_id in track_ids:
                        if self._db.add_track_to_playlist(playlist.id, track_id):
                            added_count += 1
                        else:
                            duplicate_count += 1

                    if duplicate_count == 0:
                        msg = t("added_tracks_to_playlist").format(count=added_count, name=playlist_name)
                        QMessageBox.information(self, t("success"), msg)
                    elif added_count == 0:
                        msg = t("all_tracks_duplicate").format(count=duplicate_count, name=playlist_name)
                        QMessageBox.warning(self, t("duplicate"), msg)
                    else:
                        msg = t("added_skipped_duplicates").format(added=added_count, duplicates=duplicate_count)
                        QMessageBox.information(self, t("partially_added"), msg)

    def _on_position_changed(self, position_ms):
        """Handle playback position change."""
        seconds = position_ms / 1000
        self._lyrics_view.update_position(seconds)

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

    def toggle_mini_mode(self):
        """Toggle mini player mode."""
        if self._mini_player is None:
            # Show mini player
            self._mini_player = MiniPlayer(self._player)
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

    def _save_view_state(self):
        """Save current view state to config."""
        import json

        current_index = self._stacked_widget.currentIndex()
        view_type = "library"
        view_data = {}

        # Map index to view type
        index_to_type = {
            0: "library",
            1: "cloud",
            2: "playlists",
            3: "queue",
            4: "albums",
            5: "artists",
            6: "artist",
            7: "album",
            8: "online",
        }

        view_type = index_to_type.get(current_index, "library")

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
                    albums = bootstrap.library_service.get_albums()
                    for album in albums:
                        if album.name == name and album.artist == artist:
                            self._album_view.set_album(album)
                            self._stacked_widget.setCurrentIndex(7)
                            self._update_nav_buttons_for_detail_view()
                            break
            elif view_type == "artist":
                name = view_data.get("name")
                if name:
                    # Find artist from library
                    from app.bootstrap import Bootstrap
                    bootstrap = Bootstrap.instance()
                    artists = bootstrap.library_service.get_artists()
                    for artist in artists:
                        if artist.name == name:
                            self._artist_view.set_artist(artist)
                            self._stacked_widget.setCurrentIndex(6)
                            self._update_nav_buttons_for_detail_view()
                            break
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
                self._show_page(8)
            elif view_type == "favorites":
                self._show_favorites()
            elif view_type == "history":
                self._show_history()


        # Delay to ensure UI is ready
        QTimer.singleShot(100, restore_view)

    def _update_nav_buttons_for_detail_view(self):
        """Update navigation buttons for detail view (album/artist)."""
        self._nav_library.setChecked(False)
        self._nav_cloud.setChecked(False)
        self._nav_playlists.setChecked(False)
        self._nav_queue.setChecked(False)
        self._nav_albums.setChecked(False)
        self._nav_artists.setChecked(False)
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(False)

    def _restore_playback_state(self):
        """Restore previous playback state."""
        from PySide6.QtCore import QTimer

        # Try to restore saved queue first
        if self._player.restore_queue():
            print(f"[DEBUG] Restored play queue from database")

            # Check if we should auto-play
            was_playing = self._config.get_was_playing()
            playback_position = self._config.get_playback_position()
            source = self._config.get_playback_source()

            # Update navigation buttons immediately based on source
            # if source == "cloud":
            #     if hasattr(self, '_nav_cloud'):
            #         self._nav_cloud.setChecked(True)
            #     if hasattr(self, '_nav_library'):
            #         self._nav_library.setChecked(False)

            def restore_queue_state():
                current_item = self._player.current_track
                if current_item:
                    # Restore position if valid
                    if playback_position > 0:
                        self._player.engine.seek(playback_position)

                    # Auto-play if was playing
                    if was_playing:
                        print(f"[DEBUG] Auto-playing restored track")
                        QTimer.singleShot(300, self._player.play)

                    # If cloud source, update cloud view
                    # if source == "cloud" and current_item.cloud_account_id:
                    #     account = self._db.get_cloud_account(current_item.cloud_account_id)
                    #     if account:
                    #         self._stacked_widget.setCurrentWidget(self._cloud_drive_view)

            QTimer.singleShot(200, restore_queue_state)
            return

        # Fall back to legacy restore logic
        # Check playback source
        source = self._config.get_playback_source()
        print(f"[DEBUG] Playback source: {source}")

        if source == "cloud":
            # Restore cloud playback state
            account_id = self._config.get_cloud_account_id()
            print(f"[DEBUG] Cloud account_id: {account_id}")
            if account_id:
                account = self._db.get_cloud_account(account_id)
                if account:
                    was_playing = self._config.get_was_playing()
                    print(f"[DEBUG] Restoring cloud playback, account: {account_id}, was_playing: {was_playing}")

                    def restore_cloud_state():
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
                    print(f"[DEBUG] Cloud account {account_id} not found, falling back to local")

        # Restore local track playback state
        current_track_id = self._config.get_current_track_id()
        playback_position = self._config.get_playback_position()
        was_playing = self._config.get_was_playing()
        print(
            f"[DEBUG] Local restore: track_id={current_track_id}, position={playback_position}, was_playing={was_playing}")

        if current_track_id and current_track_id > 0:
            def restore_later():
                track = self._db.get_track(current_track_id)
                if track:
                    try:
                        print(f"[DEBUG] Restoring local track: {current_track_id}")
                        self._player.play_track(current_track_id)

                        if playback_position > 0:
                            self._player.engine.seek(playback_position)

                        if was_playing:
                            QTimer.singleShot(300, self._player.engine.play)
                    except Exception as e:
                        logger.error(f"Could not restore playback: {e}", exc_info=True)

            QTimer.singleShot(100, restore_later)

    def closeEvent(self, event):
        """Handle window close."""
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

        print(
            f"[DEBUG] closeEvent: index={current_index}, playing={is_playing}, position={current_position}, volume={current_volume}")

        # Save volume
        self._config.set_volume(current_volume)

        # Save play queue
        try:
            self._player.save_queue()
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
                        self._db.update_cloud_account_playing_state(
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

        # Stop playback AFTER saving state
        self._player.engine.stop()

        # Clean up lyrics threads
        if self._lyrics_thread:
            if isValid(self._lyrics_thread) and self._lyrics_thread.isRunning():
                self._lyrics_thread.requestInterruption()
                self._lyrics_thread.quit()
                if not self._lyrics_thread.wait(1000):
                    self._lyrics_thread.terminate()
                    self._lyrics_thread.wait()

        if self._lyrics_download_thread and isValid(
                self._lyrics_download_thread) and self._lyrics_download_thread.isRunning():
            self._lyrics_download_thread.requestInterruption()
            self._lyrics_download_thread.quit()
            if not self._lyrics_download_thread.wait(1000):
                self._lyrics_download_thread.terminate()
                self._lyrics_download_thread.wait()

        # Close database
        self._db.close()

        event.accept()

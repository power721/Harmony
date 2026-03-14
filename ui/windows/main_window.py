"""
Main application window for the music player.
"""
import logging

from domain.playback import PlaybackState
from infrastructure.database import DatabaseManager
from services import PlaybackService
from services.lyrics import LyricsLoader
from services.lyrics.lyrics_loader import LyricsSearchWorker, LyricsDownloadWorker

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
)
from PySide6.QtCore import Qt, Signal, QThread, QSettings
from typing import Optional

from shiboken6 import isValid

from system.hotkeys import GlobalHotkeys, setup_media_key_handler
from system.i18n import t, set_language
from system.config import ConfigManager
from system.event_bus import EventBus
from domain.track import Track
from domain.playlist_item import PlaylistItem
from domain.cloud import CloudProvider

# Import from specific submodules to avoid circular import
from .mini_player import MiniPlayer
from ui.views.library_view import LibraryView
from ui.views.playlist_view import PlaylistView
from ui.views.queue_view import QueueView
from ui.views.cloud_view import CloudDriveView
from ui.widgets.player_controls import PlayerControls
from ui.widgets.lyrics_widget_pro import LyricsWidget
from ui.widgets.ai_settings_dialog import AISettingsDialog


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

            def get_track_cover(self, track_path: str, title: str, artist: str, album: str = ""):
                return playback.get_track_cover(track_path, title, artist, album)

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
        # Lyrics download thread (for downloading from online)
        self._lyrics_download_thread: Optional[QThread] = None
        self._lyrics_search_thread: Optional[QThread] = None
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

        self._stacked_widget.addWidget(self._library_view)
        self._stacked_widget.addWidget(self._cloud_drive_view)
        self._stacked_widget.addWidget(self._playlist_view)
        self._stacked_widget.addWidget(self._queue_view)

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
        from PySide6.QtGui import QFontDatabase, QFont

        sidebar = QWidget()
        sidebar.setObjectName("sidebar")

        # Set sidebar width
        sidebar.setMinimumWidth(180)
        sidebar.setMaximumWidth(220)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(5)

        # Get emoji-supporting font
        emoji_fonts = [
            "Segoe UI Emoji",
            "Apple Color Emoji",
            "Noto Color Emoji",
            "Symbola",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        available_families = QFontDatabase.families()
        emoji_font = None
        for font_name in emoji_fonts:
            if any(font_name.lower() in f.lower() for f in available_families):
                emoji_font = font_name
                break

        # Logo
        logo_label = QLabel("🎵 Harmony")
        logo_label.setObjectName("logo")
        logo_label.setAlignment(Qt.AlignCenter)

        # Set emoji font for logo
        if emoji_font:
            logo_font = QFont()
            logo_font.setFamily(emoji_font)
            logo_font.setPointSize(16)
            logo_font.setBold(True)
            logo_label.setFont(logo_font)

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

        # Create navigation buttons with emoji font
        nav_buttons = [
            ("_nav_library", "🎼 " + t("library")),
            ("_nav_cloud", "☁️ " + t("cloud_drive")),
            ("_nav_playlists", "📋 " + t("playlists")),
            ("_nav_queue", "🎶 " + t("queue")),
            ("_nav_favorites", "⭐ " + t("favorites")),
            ("_nav_history", "🕐 " + t("history")),
        ]

        for attr_name, text in nav_buttons:
            btn = QPushButton(text)
            btn.setCheckable(True)

            # Set emoji font
            if emoji_font:
                btn_font = QFont()
                btn_font.setFamily(emoji_font)
                btn_font.setPointSize(14)
                btn.setFont(btn_font)

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
        self._language_btn = QPushButton("🌐 " + lang_text)
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

        # AI Settings button
        ai_status = "✅" if self._config.get_ai_enabled() else "❌"
        self._ai_settings_btn = QPushButton(f"🤖 AI {ai_status}")
        self._ai_settings_btn.setObjectName("aiSettingsBtn")
        self._ai_settings_btn.setCursor(Qt.PointingHandCursor)
        self._ai_settings_btn.setFixedHeight(32)
        self._ai_settings_btn.setStyleSheet("""
            QPushButton#aiSettingsBtn {
                background-color: #2a2a2a;
                color: #c0c0c0;
                border: 2px solid #3a3a3a;
                border-radius: 16px;
                padding: 6px 16px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton#aiSettingsBtn:hover {
                background-color: #3a3a3a;
                border: 2px solid #1db954;
                color: #1db954;
            }
        """)
        self._ai_settings_btn.clicked.connect(self._show_ai_settings)
        layout.addWidget(self._ai_settings_btn)

        # Add music button
        self._add_music_btn = QPushButton(t("add_music"))
        self._add_music_btn.setObjectName("addMusicBtn")
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
        self._nav_cloud.clicked.connect(lambda: self._show_page(1))
        self._nav_playlists.clicked.connect(lambda: self._show_page(2))
        self._nav_queue.clicked.connect(lambda: self._show_page(3))
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
        self._library_view.add_to_queue.connect(self._add_to_queue)
        self._playlist_view.playlist_track_double_clicked.connect(self._play_playlist_track)
        self._queue_view.play_track.connect(self._play_track)
        self._queue_view.queue_reordered.connect(self._on_queue_reordered)
        self._cloud_drive_view.track_double_clicked.connect(self._play_cloud_track)
        self._cloud_drive_view.play_cloud_files.connect(self._play_cloud_playlist)

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
        self._nav_favorites.setChecked(True)
        self._nav_history.setChecked(False)

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
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(True)

        # Load history with delay to avoid blocking
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._library_view.show_history)

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
        class ScanWorker(QObject):
            progress = Signal(int, str)  # value, filename
            finished = Signal(int, int)  # added, skipped

            def __init__(self, folder_path, db):
                super().__init__()
                self.folder_path = folder_path
                self.db = db
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
                        cover_path = self._playback.save_cover_from_metadata(
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
        self._scan_worker = ScanWorker(folder, self._db)
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
            self._library_view.refresh()
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
        self._language_btn.setText("🌐 " + ("EN" if new_lang == "en" else "中文"))

        # Refresh the UI to apply translations
        self._refresh_ui_texts()

    def _refresh_ui_texts(self):
        """Refresh UI texts after language change."""
        # Update window title
        self.setWindowTitle(t("app_title"))

        # Update sidebar
        self._nav_library.setText("🎼 " + t("library"))
        self._nav_cloud.setText("☁️ " + t("cloud_drive"))
        self._nav_playlists.setText("📋 " + t("playlists"))
        self._nav_queue.setText("🎶 " + t("queue"))
        self._nav_favorites.setText("⭐ " + t("favorites"))
        self._nav_history.setText("🕐 " + t("history"))
        self._add_music_btn.setText(t("add_music"))

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

        # Update AI button status
        ai_status = "✅" if self._config.get_ai_enabled() else "❌"
        self._ai_settings_btn.setText(f"🤖 AI {ai_status}")

    def _show_ai_settings(self):
        """Show AI settings dialog."""

        dialog = AISettingsDialog(self._config, self)
        if dialog.exec_():
            # Update AI button status after settings change
            ai_status = "✅" if self._config.get_ai_enabled() else "❌"
            self._ai_settings_btn.setText(f"🤖 AI {ai_status}")

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
        # Reset lyric line tracking
        self._current_lyric_line = None

        # Convert to dict for backward compatibility
        if isinstance(track_item, PlaylistItem):
            track_dict = track_item.to_dict()
            track_id = track_item.track_id
            title = track_item.title
            artist = track_item.artist
            path = track_item.local_path
            is_cloud = track_item.is_cloud
        elif isinstance(track_item, int):
            # Handle case where track_item is just an ID
            track_id = track_item
            track_dict = None
            title = ""
            artist = ""
            path = ""
            is_cloud = False
        else:
            track_dict = track_item
            track_id = track_dict.get("id") if track_dict else None
            title = track_dict.get("title", "") if track_dict else ""
            artist = track_dict.get("artist", "") if track_dict else ""
            path = track_dict.get("path", "") if track_dict else ""
            is_cloud = not track_id or track_id < 0

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

        # Skip loading lyrics for cloud files without local path
        if not path or path.strip() in ('', '.', '/'):
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

    def _load_lyrics_async(self, path: str, title: str, artist: str):
        """Load lyrics asynchronously."""
        # Cancel previous lyrics loading if any
        if self._lyrics_thread and isValid(self._lyrics_thread) and self._lyrics_thread.isRunning():
            self._lyrics_thread.requestInterruption()
            self._lyrics_thread.quit()
            if not self._lyrics_thread.wait(500):  # Wait up to 500ms
                self._lyrics_thread.terminate()  # Force terminate if not responding
                self._lyrics_thread.wait()

        # Create new lyrics loader (LyricsLoader extends QThread, no need for moveToThread)
        self._lyrics_thread = LyricsLoader(path, title, artist)

        # Connect signals
        self._lyrics_thread.lyrics_ready.connect(self._on_lyrics_ready)
        self._lyrics_thread.finished.connect(self._on_lyrics_thread_finished)

        # Start loading
        self._lyrics_thread.start()

    def _on_lyrics_thread_finished(self):
        """Handle lyrics thread finished."""
        sender = self.sender()
        if sender and sender == self._lyrics_thread:
            self._lyrics_thread.deleteLater()
            self._lyrics_thread = None

    def _on_lyrics_ready(self, lyrics: str):
        """Handle lyrics loaded asynchronously."""
        if lyrics:
            self._lyrics_view.set_lyrics(lyrics)
        else:
            self._lyrics_view.set_lyrics(t("no_lyrics"))

    def _download_lyrics(self):
        """Download lyrics for current track - shows search dialog for user to select."""
        # Get current track
        current_item = self._playback.current_track
        if not current_item:
            return

        track_path = current_item.local_path
        track_title = current_item.title
        track_artist = current_item.artist

        if not track_path:
            QMessageBox.warning(self, t("error"), t("cloud_lyrics_download_not_supported"))
            return

        # Store track info for later use
        self._lyrics_download_path = track_path
        self._lyrics_download_title = track_title
        self._lyrics_download_artist = track_artist

        # Clean up existing search thread if any
        if hasattr(self, '_lyrics_search_thread') and self._lyrics_search_thread and isValid(self._lyrics_search_thread) and self._lyrics_search_thread.isRunning():
            self._lyrics_search_thread.quit()
            self._lyrics_search_thread.wait(100)

        # Don't clear current lyrics, just start searching in background
        # The lyrics view will be updated when search completes and user selects a song

        # Create search worker
        self._lyrics_search_thread = LyricsSearchWorker(track_title, track_artist, limit=10)
        self._lyrics_search_thread.search_results_ready.connect(self._on_lyrics_search_results)
        self._lyrics_search_thread.search_failed.connect(self._on_lyrics_search_failed)
        self._lyrics_search_thread.finished.connect(self._lyrics_search_thread.deleteLater)
        self._lyrics_search_thread.start()

    def _on_lyrics_search_results(self, results: list):
        """Handle lyrics search results - show selection dialog."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QListWidget,
            QListWidgetItem,
            QPushButton,
            QLabel,
            QCheckBox,
        )

        if not results:
            self._lyrics_view.set_lyrics(t("no_lyrics_found"))
            return

        # Create selection dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(t("select_song"))
        dialog.setMinimumWidth(600)
        dialog.setMinimumHeight(500)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QListWidget {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 4px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #303030;
            }
            QListWidget::item:selected {
                background-color: #1db954;
                color: #000000;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton[role="cancel"] {
                background-color: #404040;
                color: #e0e0e0;
            }
            QCheckBox {
                color: #e0e0e0;
                font-size: 13px;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #404040;
                background-color: #1a1a1a;
            }
            QCheckBox::indicator:checked {
                background-color: #1db954;
                border-color: #1db954;
            }
        """)

        layout = QVBoxLayout(dialog)

        # Info label
        info_label = QLabel(f"{t('search_results_for')}: {self._lyrics_download_title} - {self._lyrics_download_artist}")
        layout.addWidget(info_label)

        # Song list
        song_list = QListWidget()
        for result in results:
            item_text = f"{result['title']} - {result['artist']}"
            # Only show album if it exists, is not empty, and is not "-"
            album = result.get('album', '')
            if album and album.strip() and album.strip() != '-':
                item_text += f" ({album})"

            # Add duration for LRCLIB and NetEase results (if available)
            if result.get('duration') and result.get('duration') > 0:
                duration = result['duration']
                minutes = int(duration // 60)
                seconds = int(duration % 60)
                item_text += f" [{minutes}:{seconds:02d}]"

            item_text += f" [{result['source']}]"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, result)
            song_list.addItem(item)

        song_list.itemDoubleClicked.connect(dialog.accept)
        layout.addWidget(song_list)

        # Checkbox for downloading cover
        download_cover_checkbox = QCheckBox(t("download_cover"))
        download_cover_checkbox.setChecked(True)  # Default to checked
        download_cover_checkbox.setToolTip(t("download_cover_tooltip"))
        layout.addWidget(download_cover_checkbox)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.clicked.connect(dialog.reject)
        download_btn = QPushButton(t("download"))
        download_btn.clicked.connect(dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(download_btn)
        layout.addLayout(button_layout)

        # Show dialog
        if dialog.exec_() != QDialog.Accepted:
            return

        # Get selected song
        current_item = song_list.currentItem()
        if not current_item:
            return

        selected_song = current_item.data(Qt.UserRole)

        # Pass the checkbox state to download function
        self._download_lyrics_for_song(selected_song, download_cover_checkbox.isChecked())

    def _download_lyrics_for_song(self, song_info: dict, download_cover: bool = True):
        """Download lyrics for a specific song.

        Args:
            song_info: Dictionary with song information (id, title, artist, source, etc.)
            download_cover: Whether to download cover art (default: True)
        """
        # Clean up existing download thread if any
        if self._lyrics_download_thread and isValid(self._lyrics_download_thread) and self._lyrics_download_thread.isRunning():
            self._lyrics_download_thread.quit()
            self._lyrics_download_thread.wait(100)

        self._lyrics_view.set_lyrics(t("downloading") + "...")

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

    def _on_lyrics_search_failed(self, error: str):
        """Handle lyrics search failure."""
        self._lyrics_view.set_lyrics(t("no_lyrics_found"))

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
        from utils import parse_lrc

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
        lrc_path = track_file.with_suffix('.lrc')

        lyrics_content = None

        # Try multiple encodings
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'utf-16']

        # Try main location first
        if lrc_path.exists():
            for encoding in encodings:
                try:
                    with open(lrc_path, 'r', encoding=encoding) as f:
                        lyrics_content = f.read()
                    print(f"Loaded lyrics from {lrc_path} with {encoding} encoding")
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
                except Exception as e:
                    logger.error(f"Error reading {lrc_path}: {e}", exc_info=True)
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

            # Parse lyrics
            parsed_lyrics = parse_lrc(content)
            if not parsed_lyrics:
                QMessageBox.warning(dialog, t("warning"), t("invalid_lyrics_format"))
                return

            # Save lyrics
            if LyricsService.save_lyrics(track_path, content):
                QMessageBox.information(dialog, t("success"), t("lyrics_saved"))
                # Refresh lyrics display
                self._refresh_lyrics()
                dialog.accept()
            else:
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

        # Find lyrics file
        lrc_path = track_file.with_suffix(".lrc")

        if not lrc_path.exists():
            QMessageBox.information(self, t("info"), t("lyrics_file_not_found"))
            return

        try:
            system = platform.system()

            if system == "Windows":
                subprocess.Popen(["explorer", f"/select,{lrc_path}"])

            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(lrc_path)])

            else:
                # Linux
                # Try to select file in supported file managers
                file_managers = {
                    "nautilus": ["nautilus", "--select", str(lrc_path)],
                    "dolphin": ["dolphin", "--select", str(lrc_path)],
                    "caja": ["caja", "--select", str(lrc_path)],
                    "nemo": ["nemo", str(lrc_path)],
                }

                for fm, cmd in file_managers.items():
                    if shutil.which(fm):
                        subprocess.Popen(cmd)
                        return

                # fallback
                subprocess.Popen(["xdg-open", str(lrc_path.parent)])

        except Exception as e:
            logger.error(f"Failed to open file location: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"{t('open_file_location_failed')}: {e}")

    def _add_to_queue(self, track_ids: list):
        """Add tracks to the play queue."""
        self._queue_view.add_tracks(track_ids)

        # Show notification
        count = len(track_ids)
        self._status_bar = self.statusBar()
        s = "s" if count > 1 else ""
        msg = t("added_to_queue").replace("{count}", str(count)).replace("{s}", s)
        self._status_bar.showMessage(msg, 3000)

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

        # Restore playback state
        self._restore_playback_state()

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
            if source == "cloud":
                if hasattr(self, '_nav_cloud'):
                    self._nav_cloud.setChecked(True)
                if hasattr(self, '_nav_library'):
                    self._nav_library.setChecked(False)

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
                    if source == "cloud" and current_item.cloud_account_id:
                        account = self._db.get_cloud_account(current_item.cloud_account_id)
                        if account:
                            self._stacked_widget.setCurrentWidget(self._cloud_drive_view)

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
                        # Switch to cloud drive view
                        self._stacked_widget.setCurrentWidget(self._cloud_drive_view)

                        # Update sidebar selection
                        if hasattr(self, '_nav_cloud'):
                            self._nav_cloud.setChecked(True)
                        if hasattr(self, '_nav_library'):
                            self._nav_library.setChecked(False)
                        if hasattr(self, '_nav_playlists'):
                            self._nav_playlists.setChecked(False)
                        if hasattr(self, '_nav_queue'):
                            self._nav_queue.setChecked(False)
                        if hasattr(self, '_nav_favorites'):
                            self._nav_favorites.setChecked(False)
                        if hasattr(self, '_nav_history'):
                            self._nav_history.setChecked(False)

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
        print(f"[DEBUG] Local restore: track_id={current_track_id}, position={playback_position}, was_playing={was_playing}")

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

        # Check if playing cloud files BEFORE stopping
        is_playing_cloud = self._player.current_source == "cloud"
        is_playing = self._player.state == PlaybackState.PLAYING
        current_position = self._player.engine.position()
        current_index = self._player.engine.current_index
        current_volume = self._player.volume

        print(f"[DEBUG] closeEvent: index={current_index}, playing={is_playing}, position={current_position}, volume={current_volume}")

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

        if self._lyrics_download_thread and isValid(self._lyrics_download_thread) and self._lyrics_download_thread.isRunning():
            self._lyrics_download_thread.requestInterruption()
            self._lyrics_download_thread.quit()
            if not self._lyrics_download_thread.wait(1000):
                self._lyrics_download_thread.terminate()
                self._lyrics_download_thread.wait()

        if self._lyrics_search_thread and isValid(self._lyrics_search_thread) and self._lyrics_search_thread.isRunning():
            self._lyrics_search_thread.requestInterruption()
            self._lyrics_search_thread.quit()
            if not self._lyrics_search_thread.wait(1000):
                self._lyrics_search_thread.terminate()
                self._lyrics_search_thread.wait()

        # Close database
        self._db.close()

        event.accept()

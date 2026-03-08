"""
Main application window for the music player.
"""
import re
import logging

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

from PySide6.QtWebEngineWidgets import QWebEngineView
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

from database import DatabaseManager
from player import PlayerController
from player.engine import PlayerState
from services import LyricsService, MetadataService
from ui.library_view import LibraryView
from ui.lyrics_widget_pro import LyricsWidget
from ui.playlist_view import PlaylistView
from ui.player_controls import PlayerControls
from ui.mini_player import MiniPlayer
from ui.queue_view import QueueView
from ui.cloud_drive_view import CloudDriveView
from utils.global_hotkeys import GlobalHotkeys, setup_media_key_handler
from utils import t, set_language
from utils.config import ConfigManager


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

        # Initialize player controller
        self._player = PlayerController(self._db, self._config)

        # Mini player (hidden by default)
        self._mini_player: Optional[MiniPlayer] = None

        # Lyrics sync
        self._current_lyric_line: Optional[int] = None

        # Lyrics download thread (to prevent multiple downloads)
        self._lyrics_thread: Optional[QThread] = None
        self._lyrics_worker = None
        self._current_index = -1

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

        self._library_view = LibraryView(self._db, self._player)
        self._cloud_drive_view = CloudDriveView(self._db, self._player, self._config)
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

        # Set library as checked
        self._nav_library.setChecked(True)

        layout.addStretch()

        # Language selector
        from utils import get_language

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
        self._lyrics_view.seekRequested.connect(self._player.engine.seek)

        # Add music
        self._add_music_btn.clicked.connect(self._add_music)

        # Player connections
        self._player.engine.current_track_changed.connect(self._on_track_changed)
        self._player.engine.position_changed.connect(self._on_position_changed)

        # View connections
        self._library_view.track_double_clicked.connect(self._play_track)
        self._library_view.add_to_queue.connect(self._add_to_queue)
        self._playlist_view.track_double_clicked.connect(self._play_track)
        self._queue_view.play_track.connect(self._play_track)
        self._cloud_drive_view.track_double_clicked.connect(self._play_cloud_track)
        self._cloud_drive_view.play_cloud_files.connect(self._play_cloud_playlist)

        # lyrics
        # self.lyricsHtmlReady.connect(self._lyrics_view.setHtml)

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
        from threading import Thread

        def scan():
            self._library_view.refresh()

        # Run in thread to avoid blocking UI
        thread = Thread(target=scan)
        thread.start()

        QMessageBox.information(
            self,
            t("scanning"),
            t("added_music"),
        )

    def _toggle_language(self):
        """Toggle between English and Chinese."""
        from utils import get_language, set_language

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

        # Refresh views
        self._library_view.refresh()
        self._cloud_drive_view.refresh_ui()  # Refresh cloud drive view
        self._playlist_view._refresh_playlists()
        self._queue_view.refresh_queue()

    def _play_track(self, track_id: int):
        """Play a track."""
        # Set playback source to local when playing local tracks
        self._config.set_playback_source("local")
        self._config.clear_cloud_account_id()

        # Disconnect cloud playlist manager signals FIRST to prevent callbacks
        if hasattr(self, '_cloud_playlist_manager') and self._cloud_playlist_manager:
            try:
                self._player.engine.current_track_changed.disconnect(
                    self._cloud_playlist_manager.on_track_changed
                )
            except (TypeError, RuntimeError):
                pass
            self._cloud_playlist_manager = None

        # Stop current playback after disconnecting signals
        self._player.engine.stop()

        self._player.play_track(track_id)

    def _play_cloud_track(self, temp_path: str):
        """Play track from cloud (temp file)."""
        # Create track dict for cloud file
        track = {
            'path': temp_path,
            'title': 'Cloud Track',
            'artist': 'Cloud',
            'album': 'Cloud'
        }

        # Load directly into player engine (bypass controller which expects playlist_id)
        self._player.engine.load_playlist([track])
        self._player.engine.play()

    def _play_cloud_playlist(self, temp_path: str, index: int, cloud_files, start_position: float = 0.0):
        """Play multiple cloud files as a playlist."""
        from PySide6.QtCore import QTimer
        from database.models import CloudFile

        # Create a cloud playlist manager if needed
        if not hasattr(self, '_cloud_playlist_manager') or self._cloud_playlist_manager is None:
            self._cloud_playlist_manager = CloudPlaylistManager(
                self._cloud_drive_view,
                self._player.engine,
                self._db,
                self._config
            )

        # Load the playlist with start position
        self._cloud_playlist_manager.load_playlist(cloud_files, index, temp_path, start_position)



    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        # Reset lyric line tracking
        self._current_lyric_line = None

        # Sync selection in both library and queue views
        if track_dict:
            track_id = track_dict.get("id")
            if track_id:
                # Select in library view
                self._library_view._select_track_by_id(track_id)
                # Select in queue view (if it exists in queue)
                self._queue_view._select_track_by_id(track_id)

        self._lyrics_view.set_lyrics(t("no_lyrics"))
        if not track_dict:
            return

        # Load lyrics (fast, local only)
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        path = track_dict.get("path", "")

        # Skip loading lyrics for cloud files (empty path)
        if not path or path.strip() in ('', '.', '/'):
            return

        # Try to load lyrics
        lyrics = LyricsService.get_lyrics(path, title, artist)
        if lyrics:
            self._lyrics_view.set_lyrics(lyrics)
        else:
            # Check if .lrc file exists nearby
            from pathlib import Path
            if not path:
                return

            track_path = Path(path)
            lrc_path = track_path.with_suffix(".lrc")
            lyrics_dir = track_path.parent / "lyrics"
            lrc_alt = lyrics_dir / f"{track_path.stem}.lrc"

            if lrc_path.exists() or lrc_alt.exists():
                self._lyrics_view.set_lyrics(t("lyrics_found_parse_failed") + "\n" + t("ensure_lrc_valid"))

    def _download_lyrics(self):
        """Download lyrics for current track."""
        # Check if we're playing a track
        current_track = self._player.engine.current_track
        if not current_track:
            return

        # Check if this is a cloud file (no id or empty id)
        is_cloud_file = not current_track.get("id")

        if is_cloud_file:
            # For cloud files, use the current track info directly
            track_path = current_track.get("path", "")
            track_title = current_track.get("title", "")
            track_artist = current_track.get("artist", "")

            if not track_path:
                # Cannot download lyrics for cloud files without local path
                QMessageBox.warning(self, t("error"), t("cloud_lyrics_download_not_supported"))
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

        # Clean up existing thread if any
        if self._lyrics_thread and isValid(self._lyrics_thread) and self._lyrics_thread.isRunning():
            self._lyrics_thread.quit()
            self._lyrics_thread.wait()

        self._lyrics_view.set_lyrics(t("no_lyrics"))

        from PySide6.QtCore import QObject

        class LyricsDownloadWorker(QObject):
            finished = Signal(bool)
            lyrics_ready = Signal(str)
            error_ready = Signal(str)

            def __init__(self, track_path, title, artist):
                super().__init__()
                self._track_path = track_path
                self._title = title
                self._artist = artist

            def run(self):
                success = LyricsService.download_and_save_lyrics(
                    self._track_path, self._title, self._artist
                )

                if success:
                    lyrics = LyricsService.get_lyrics(self._track_path, self._title, self._artist)
                    if lyrics:
                        self.lyrics_ready.emit(lyrics)
                    else:
                        self.error_ready.emit("parse_failed")
                else:
                    self.error_ready.emit("not_found")

                self.finished.emit(True)

        # Create and start thread
        self._lyrics_thread = QThread()
        self._lyrics_worker = LyricsDownloadWorker(track_path, track_title, track_artist)
        self._lyrics_worker.moveToThread(self._lyrics_thread)

        self._lyrics_thread.started.connect(self._lyrics_worker.run)
        self._lyrics_worker.lyrics_ready.connect(self._on_lyrics_download_success)
        self._lyrics_worker.error_ready.connect(self._on_lyrics_download_error)
        self._lyrics_worker.finished.connect(self._lyrics_thread.quit)
        self._lyrics_worker.finished.connect(self._lyrics_worker.deleteLater)
        self._lyrics_thread.finished.connect(self._lyrics_thread.deleteLater)

        self._lyrics_thread.start()

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
        seconds = position_ms / 1000

        self._lyrics_view.update_position(seconds)

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._player.engine.state == PlayerState.PLAYING:
            self._player.engine.pause()
        else:
            self._player.engine.play()

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

        # Volume is restored by PlayerController, just update slider
        volume = self._config.get_volume()
        self._player_controls.set_volume(volume)

        # Restore playback state
        self._restore_playback_state()

    def _restore_playback_state(self):
        """Restore previous playback state."""
        from PySide6.QtCore import QTimer

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
        is_playing_cloud = (
            hasattr(self, '_cloud_playlist_manager') and
            self._cloud_playlist_manager is not None
        )
        is_playing = self._player.engine.state == PlayerState.PLAYING
        current_position = self._player.engine.position()

        try:
            if is_playing_cloud:
                # Save cloud playback state
                account_id = self._config.get_cloud_account_id()
                if account_id:
                    self._config.set_playback_source("cloud")
                    self._config.set_was_playing(is_playing)
                    # Clear local track info when playing cloud
                    self._config.set_current_track_id(0)
                    self._config.set_playback_position(0)

                    # Save playback position to cloud_accounts table
                    # Get current playing file from cloud playlist manager
                    if hasattr(self._cloud_playlist_manager, '_cloud_files'):
                        current_index = self._player.engine.current_index
                        cloud_files = self._cloud_playlist_manager._cloud_files
                        if 0 <= current_index < len(cloud_files):
                            current_file = cloud_files[current_index]
                            position_seconds = current_position / 1000.0
                            # Get local path if available
                            local_path = getattr(current_file, 'local_path', '') or ''
                            if not local_path and hasattr(self._cloud_playlist_manager, '_downloaded_files'):
                                local_path = self._cloud_playlist_manager._downloaded_files.get(current_file.file_id, '')
                            self._db.update_cloud_account_playing_state(
                                account_id=account_id,
                                playing_fid=current_file.file_id,
                                position=position_seconds,
                                local_path=local_path
                            )
            elif self._player.current_track_id:
                # Save local playback state
                self._config.set_playback_source("local")
                self._config.set_current_track_id(self._player.current_track_id)
                self._config.set_playback_position(current_position)
                self._config.set_was_playing(is_playing)
                # Clear cloud info when playing local
                self._config.clear_cloud_account_id()
            else:
                # No track playing
                source = self._config.get_playback_source()
                if source == "cloud":
                    self._config.set_was_playing(False)
                else:
                    self._config.set_playback_source("local")
                    self._config.set_current_track_id(0)
                    self._config.set_playback_position(0)
                    self._config.set_was_playing(False)
                    self._config.clear_cloud_account_id()
        except Exception as e:
            print(f"Error saving playback state: {e}")

        # Stop playback AFTER saving state
        self._player.engine.stop()

        # Close database
        self._db.close()

        event.accept()

class CloudPlaylistManager:
    """Manages playback of cloud files with on-demand downloading."""

    def __init__(self, cloud_drive_view, player_engine, db_manager, config_manager):
        self._cloud_view = cloud_drive_view
        self._player_engine = player_engine
        self._db = db_manager
        self._config_manager = config_manager
        self._cloud_files = []
        self._download_threads = []
        self._current_index = 0
        self._downloaded_files = {}  # Maps cloud_file_id to temp_path

    def load_playlist(self, cloud_files, start_index, first_file_path, start_position: float = 0.0):
        """Load cloud file playlist and start playback."""
        from PySide6.QtCore import QTimer

        self._cloud_files = cloud_files
        self._current_index = start_index
        self._start_position = start_position  # Save for later seek

        # Store first file path
        first_file = cloud_files[start_index]
        self._downloaded_files[first_file.file_id] = first_file_path

        # Extract metadata from first file
        first_title = first_file.name
        first_artist = ""
        first_album = ""
        metadata = MetadataService.extract_metadata(first_file_path)
        if metadata:
            if metadata.get("title"):
                first_title = metadata.get("title")
            if metadata.get("artist"):
                first_artist = metadata.get("artist")
            if metadata.get("album"):
                first_album = metadata.get("album")

        # Save playback state to config
        self._save_playback_state(first_file)

        # Build playlist dict with first file
        playlist = []
        for i, cloud_file in enumerate(cloud_files):
            if i == start_index:
                playlist.append({
                    'path': first_file_path,
                    'title': first_title,
                    'artist': first_artist,
                    'album': first_album
                })
            else:
                # Placeholder paths for other files
                playlist.append({
                    'path': '',  # Will be downloaded on demand
                    'title': cloud_file.name,
                    'artist': '',
                    'album': ''
                })

        # Load into player and start playing
        self._player_engine.load_playlist(playlist)

        # Use play_at_with_position to seek before playing if start_position is set
        if start_position > 0:
            position_ms = int(start_position * 1000)
            self._player_engine.play_at_with_position(start_index, position_ms)
        else:
            self._player_engine.play_at(start_index)

        # Connect signal AFTER playback has started using QTimer to ensure main thread
        QTimer.singleShot(0, self._connect_track_changed_signal)

    def _save_playback_state(self, cloud_file):
        """Save current cloud playback state to config and database."""
        if hasattr(self._cloud_view, '_config_manager') and self._cloud_view._config_manager:
            if hasattr(self._cloud_view, '_current_account') and self._cloud_view._current_account:
                account_id = self._cloud_view._current_account.id

                # Save cloud account ID to settings
                self._cloud_view._config_manager.set_cloud_account_id(account_id)
                self._cloud_view._config_manager.set_playback_source("cloud")

                # Save playing file and position to cloud_accounts table
                if hasattr(self._cloud_view, '_db'):
                    self._cloud_view._db.update_cloud_account_playing_state(
                        account_id=account_id,
                        playing_fid=cloud_file.file_id,
                        position=0.0
                    )

    def _connect_track_changed_signal(self):
        """Connect track changed signal in main thread."""
        # Disconnect first to avoid duplicates
        try:
            self._player_engine.current_track_changed.disconnect(
                self.on_track_changed
            )
        except (TypeError, RuntimeError):
            pass  # Signal wasn't connected, which is fine

        # Connect in main thread
        self._player_engine.current_track_changed.connect(
            self.on_track_changed
        )

    def _seek_to_start_position(self):
        """Seek to the saved start position after playback begins."""
        if hasattr(self, '_start_position') and self._start_position > 0:
            try:
                # Convert seconds to milliseconds
                position_ms = int(self._start_position * 1000)
                self._player_engine.seek(position_ms)
                print(f"Seeking to {self._start_position:.2f}s ({position_ms}ms)")
            except Exception as e:
                logger.error(f"Error seeking to position: {e}", exc_info=True)

    def on_track_changed(self, track_dict):
        """Handle track change to download files on demand."""
        if not track_dict:
            return

        # Only trigger download if path is empty AND we have cloud files
        if not track_dict.get('path') and self._cloud_files:
            current_index = self._player_engine.current_index

            # Check if this file needs downloading
            if 0 <= current_index < len(self._cloud_files):
                cloud_file = self._cloud_files[current_index]

                # Check if already downloaded
                if cloud_file.file_id not in self._downloaded_files:
                    self._download_and_play(current_index)
                else:
                    temp_path = self._downloaded_files[cloud_file.file_id]
                    self._update_track_path(current_index, temp_path)

    def _download_and_play(self, index: int):
        """Download cloud file and update player."""
        if index >= len(self._cloud_files):
            return

        cloud_file = self._cloud_files[index]

        # Check if already downloaded
        if cloud_file.file_id in self._downloaded_files:
            temp_path = self._downloaded_files[cloud_file.file_id]
            self._update_track_path(index, temp_path)
            return

        # Get current account
        account = self._cloud_view._current_account
        if not account:
            return

        # Download in background thread
        from ui.cloud_drive_view import CloudFileDownloadThread
        download_thread = CloudFileDownloadThread(
            account.access_token,
            cloud_file,
            index,
            self._cloud_files,
            self._config_manager
        )
        self._download_threads.append(download_thread)
        download_thread.finished.connect(lambda path: self._on_file_downloaded(index, path))
        download_thread.file_exists.connect(lambda path: self._on_file_exists(index, path))
        download_thread.token_updated.connect(self._cloud_view._on_token_updated)
        download_thread.start()

    def _on_file_exists(self, index: int, temp_path: str):
        """Handle when file already exists locally."""
        if temp_path:
            # Store path
            if index < len(self._cloud_files):
                cloud_file = self._cloud_files[index]
                self._downloaded_files[cloud_file.file_id] = temp_path

                # Update status label to show using cached file
                if hasattr(self._cloud_view, '_status_label'):
                    self._cloud_view._status_label.setText(f"{t('using_cached_file')} - {cloud_file.name}")

            # Update player if this is the current track
            self._update_track_path(index, temp_path)

    def _on_file_downloaded(self, index: int, temp_path: str):
        """Handle completed file download."""
        if temp_path:
            # Store path
            if index < len(self._cloud_files):
                cloud_file = self._cloud_files[index]
                self._downloaded_files[cloud_file.file_id] = temp_path

                # Update status label to show download complete
                if hasattr(self._cloud_view, '_status_label'):
                    import os
                    file_size = os.path.getsize(temp_path)
                    size_mb = file_size / (1024 * 1024)
                    self._cloud_view._status_label.setText(f"{t('download_complete')}: {cloud_file.name} ({size_mb:.1f} MB)")

            # Update player if this is the current track
            # This method is called in main thread via Qt signal/slot mechanism
            self._update_track_path(index, temp_path)

    def _update_track_path(self, index: int, temp_path: str):
        """Update track path in player and reload."""
        playlist = self._player_engine.playlist
        if 0 <= index < len(playlist):
            playlist[index]['path'] = temp_path

            # Reload and play if this is current track
            if index == self._player_engine.current_index:
                # Load metadata asynchronously
                from PySide6.QtCore import QThread, Signal, QObject

                class MetadataWorker(QObject):
                    finished = Signal(str, str)

                    def __init__(self, path):
                        super().__init__()
                        self._path = path

                    def run(self):
                        metadata = MetadataService.extract_metadata(self._path)
                        if metadata:
                            self.finished.emit(
                                metadata.get("title", ""),
                                metadata.get("artist", "")
                            )
                        else:
                            self.finished.emit("", "")

                def on_metadata_ready(title, artist):
                    if index < len(playlist):
                        if title:
                            playlist[index]['title'] = title
                        if artist:
                            playlist[index]['artist'] = artist

                # Start metadata extraction in background
                self._metadata_thread = QThread()
                self._metadata_worker = MetadataWorker(temp_path)
                self._metadata_worker.moveToThread(self._metadata_thread)
                self._metadata_thread.started.connect(self._metadata_worker.run)
                self._metadata_worker.finished.connect(on_metadata_ready)
                self._metadata_worker.finished.connect(self._metadata_thread.quit)
                self._metadata_worker.finished.connect(self._metadata_worker.deleteLater)
                self._metadata_thread.finished.connect(self._metadata_thread.deleteLater)
                self._metadata_thread.start()

                # Temporarily disconnect signal to prevent loop
                try:
                    self._player_engine.current_track_changed.disconnect(
                        self.on_track_changed
                    )
                except (TypeError, RuntimeError):
                    pass  # Signal might not be connected

                try:
                    # Reload the track
                    from PySide6.QtCore import QUrl
                    url = QUrl.fromLocalFile(temp_path)
                    self._player_engine._player.setSource(url)
                    self._player_engine._player.play()
                finally:
                    # Reconnect signal
                    self._player_engine.current_track_changed.connect(
                        self.on_track_changed
                    )

                # Emit signal after reconnecting so MainWindow._on_track_changed handles lyrics
                self._player_engine.current_track_changed.emit(playlist[index])

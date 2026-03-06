"""
Main application window for the music player.
"""
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
from PySide6.QtCore import Qt, Signal, QSettings, QThread
from typing import Optional

from database import DatabaseManager
from player import PlayerController
from player.engine import PlayerState
from services import LyricsService
from ui.library_view import LibraryView
from ui.playlist_view import PlaylistView
from ui.player_controls import PlayerControls
from ui.mini_player import MiniPlayer
from ui.queue_view import QueueView
from utils.global_hotkeys import GlobalHotkeys, setup_media_key_handler
from utils import t, set_language


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    play_track = Signal(int)  # Signal to play a track by ID
    lyricsHtmlReady = Signal(str)

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Settings (must be initialized first)
        self._settings = QSettings("HarmonyPlayer", "Harmony")

        # Initialize language from settings
        saved_lang = self._settings.value("language", "en")
        set_language(saved_lang)

        # Initialize database
        self._db = DatabaseManager()

        # Initialize player controller
        self._player = PlayerController(self._db)

        # Mini player (hidden by default)
        self._mini_player: Optional[MiniPlayer] = None

        # Lyrics sync
        self._current_lyric_line: Optional[int] = None

        # Lyrics download thread (to prevent multiple downloads)
        self._lyrics_thread: Optional[QThread] = None
        self._lyrics_worker = None

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
        self._playlist_view = PlaylistView(self._db, self._player)
        self._queue_view = QueueView(self._player, self._db)

        self._stacked_widget.addWidget(self._library_view)
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
        self._lyrics_view = QWebEngineView()
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
        self._nav_playlists.clicked.connect(lambda: self._show_page(1))
        self._nav_queue.clicked.connect(lambda: self._show_page(2))
        self._nav_favorites.clicked.connect(self._show_favorites)
        self._nav_history.clicked.connect(self._show_history)

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

        # lyrics
        self.lyricsHtmlReady.connect(self._lyrics_view.setHtml)

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
        self._nav_playlists.setChecked(index == 1)
        self._nav_queue.setChecked(index == 2)
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(False)

        # Switch view
        self._stacked_widget.setCurrentIndex(index)

        # Auto-select first playlist when showing playlists
        if index == 1:
            playlist_view = self._stacked_widget.widget(1)
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
        self._settings.setValue("language", new_lang)

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
        self._playlist_view._refresh_playlists()
        self._queue_view.refresh_queue()

    def _play_track(self, track_id: int):
        """Play a track."""
        self._player.play_track(track_id)

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

        if not track_dict:
            self._lyrics_view.setHtml(
                self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>{t("not_playing")}</div>')
            )
            return

        # Load lyrics (fast, local only)
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        path = track_dict.get("path", "")

        # Show loading message
        self._lyrics_view.setHtml(
            self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}</div>')
        )
        self._current_lyrics = []

        # Try to load lyrics
        lyrics = LyricsService.get_lyrics(path, title, artist)
        if lyrics:
            self._load_lyrics(lyrics)
        else:
            # Check if .lrc file exists nearby
            from pathlib import Path

            track_path = Path(path)
            lrc_path = track_path.with_suffix(".lrc")
            lyrics_dir = track_path.parent / "lyrics"
            lrc_alt = lyrics_dir / f"{track_path.stem}.lrc"

            if lrc_path.exists() or lrc_alt.exists():
                self._lyrics_view.setHtml(
                    self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>{t("lyrics_found_parse_failed")}<br><br>{t("ensure_lrc_valid")}</div>')
                )
            else:
                # No lyrics file exists, show no lyrics message
                self._lyrics_view.setHtml(
                    self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}<br><br>---<br><br>{t("no_lyrics")}<br><br>{t("click_download")}</div>')
                )

    def _download_lyrics(self):
        """Download lyrics for current track."""
        if not self._player.current_track_id:
            return

        track = self._db.get_track(self._player.current_track_id)
        if not track:
            return

        # Clean up existing thread if any
        if self._lyrics_thread and self._lyrics_thread.isRunning():
            self._lyrics_thread.quit()
            self._lyrics_thread.wait()

        self._lyrics_view.setHtml(
            self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">⏳<br><br>{t("searching_lyrics")}</div>')
        )

        from PySide6.QtCore import QObject

        class LyricsDownloadWorker(QObject):
            finished = Signal(bool)
            lyrics_ready = Signal(list)
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
        self._lyrics_worker = LyricsDownloadWorker(track.path, track.title, track.artist)
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
        self._current_lyrics = lyrics
        html = self._build_lyrics_html(lyrics)
        self._lyrics_view.setHtml(html)

    def _on_lyrics_download_error(self, error_type: str):
        """Handle lyrics download error."""
        if error_type == "parse_failed":
            html = self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">❌<br><br>{t("lyrics_downloaded_parsing_failed")}</div>')
        else:  # not_found
            html = self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">❌<br><br>{t("lyrics_not_found")}</div>')
        self._lyrics_view.setHtml(html)

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

        if not self._player.current_track_id:
            return

        track = self._db.get_track(self._player.current_track_id)
        if not track:
            return

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
        info_label = QLabel(f"{track.title} - {track.artist}")
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

        # Load existing lyrics if available
        lyrics = LyricsService.get_lyrics(track.path, track.title, track.artist)
        if lyrics:
            # Format as LRC
            lrc_lines = []
            for time, text in lyrics:
                minutes = int(time // 60)
                seconds = int(time % 60)
                milliseconds = int((time % 1) * 100)
                lrc_lines.append(f"[{minutes:02d}:{seconds:02d}.{milliseconds:02d}]{text}")
            text_edit.setPlainText('\n'.join(lrc_lines))

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
            if LyricsService.save_lyrics(track.path, parsed_lyrics):
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

        if not self._player.current_track_id:
            return

        track = self._db.get_track(self._player.current_track_id)
        if not track:
            return

        # Check if lyrics file exists
        if not LyricsService.lyrics_file_exists(track.path):
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
            if LyricsService.delete_lyrics(track.path):
                # Clear lyrics immediately and reset state
                self._current_lyrics = []
                self._current_lyric_line = None
                title = track.title or ""
                artist = track.artist or ""
                self._lyrics_view.setHtml(
                    self._build_html(f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}<br><br>---<br><br>{t("no_lyrics")}<br><br>{t("click_download")}</div>')
                )
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

        if not self._player.current_track_id:
            return

        track = self._db.get_track(self._player.current_track_id)
        if not track:
            return

        track_file = Path(track.path)

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
            QMessageBox.warning(self, "Error", f"{t('open_file_location_failed')}: {e}")

    def _add_to_queue(self, track_ids: list):
        """Add tracks to the play queue."""
        self._queue_view.add_tracks(track_ids)

        # Show notification
        count = len(track_ids)
        self._status_bar = self.statusBar()
        if not self._status_bar:
            self._status_bar = self.statusBar()
        s = "s" if count > 1 else ""
        msg = t("added_to_queue").replace("{count}", str(count)).replace("{s}", s)
        self._status_bar.showMessage(msg, 3000)

    def _load_lyrics(self, lyrics):
        """
        lyrics: List[(time_in_seconds, text)]
        """
        self._current_lyrics = lyrics
        self._current_index = -1

        html = self._build_lyrics_html(lyrics)
        self._lyrics_view.setHtml(html)

    def _on_position_changed(self, position_ms: int):
        if not self._current_lyrics:
            return

        seconds = position_ms / 1000.0
        index = self._find_line(seconds)

        if index != -1 and index != self._current_index:
            self._highlight_line(index)
            self._current_index = index

    def _find_line(self, seconds: float):
        """
        Binary search could be used here if lyrics are large.
        """
        for i in range(len(self._current_lyrics) - 1):
            if self._current_lyrics[i][0] <= seconds < self._current_lyrics[i + 1][0]:
                return i

        if self._current_lyrics and seconds >= self._current_lyrics[-1][0]:
            return len(self._current_lyrics) - 1

        return -1

    def _highlight_line(self, index: int):
        prev = self._current_index

        js = f"""
        if ({prev} >= 0) {{
            var prevEl = document.getElementById("line{prev}");
            if (prevEl) prevEl.classList.remove("active");
        }}

        var el = document.getElementById("line{index}");
        if (el) {{
            el.classList.add("active");
            el.scrollIntoView({{
                behavior: "smooth",
                block: "center"
            }});
        }}
        """

        self._lyrics_view.page().runJavaScript(js)

    def _build_lyrics_html(self, lyrics):
        html = ""
        for i, (_, text) in enumerate(lyrics):
            html += f'<div id="line{i}" class="line">{text}</div>'
        return self._build_html(html)

    def _build_html(self, content):
        html = """
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            html, body {
                background: #000000;
                margin: 0;
                padding: 0;
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                overflow-y: auto;
            }

            .container {
                padding: 16vh 20px;
                line-height: 2.4;
                font-size: 16px;
                color: #666666;
                text-align: center;
                scroll-behavior: smooth;
            }

            .line {
                margin: 10px 0;
                padding: 12px;
                border-radius: 10px;
                transition: all 0.25s ease;
                opacity: 0.4;
            }

            .line.active {
                color: #1db954;
                font-size: 22px;
                font-weight: bold;
                background-color: rgba(29,185,84,0.12);
                opacity: 1;
                transform: scale(1.10);
            }

            /* 上下渐隐遮罩 */
            body {
                mask-image: linear-gradient(
                    to bottom,
                    transparent,
                    black 15%,
                    black 85%,
                    transparent
                );
            }

            /* 滚动条隐藏（更干净） */
            ::-webkit-scrollbar {
                display: none;
            }

        </style>
        </head>
        <body>
        <div class="container">
        """

        html += content

        html += """
        </div>
        </body>
        </html>
        """

        return html

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
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = self._settings.value("splitter")
        if splitter_state:
            self._splitter.restoreState(splitter_state)

        # Restore volume
        volume = self._settings.value("volume", 70, type=int)
        self._player.engine.set_volume(volume)
        self._player_controls.set_volume(volume)  # Update slider too

        # Restore playback state
        self._restore_playback_state()

    def _restore_playback_state(self):
        """Restore previous playback state."""
        current_track_id = self._settings.value("current_track_id", 0, type=int)
        playback_position = self._settings.value("playback_position", 0, type=int)
        was_playing = self._settings.value("was_playing", False, type=bool)

        if current_track_id > 0:
            # Use QTimer to restore after UI is fully loaded
            from PySide6.QtCore import QTimer

            def restore_later():
                # Load the track
                track = self._db.get_track(current_track_id)
                if track:
                    # Don't check file existence on startup to avoid blocking
                    try:
                        self._player.play_track(current_track_id)

                        # Seek to previous position
                        if playback_position > 0:
                            self._player.engine.seek(playback_position)

                        # Resume playback if it was playing
                        if was_playing:
                            QTimer.singleShot(300, self._player.engine.play)
                    except Exception as e:
                        print(f"Could not restore playback: {e}")

            QTimer.singleShot(100, restore_later)

    def closeEvent(self, event):
        """Handle window close."""
        # Save window settings
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter", self._splitter.saveState())

        # Save volume
        self._settings.setValue("volume", self._player.engine.volume)

        # Save playback state
        if self._player.current_track_id:
            self._settings.setValue("current_track_id", self._player.current_track_id)

            # Get current position
            position = self._player.engine.position()
            self._settings.setValue("playback_position", position)

            # Save whether it was playing
            was_playing = self._player.engine.state == PlayerState.PLAYING
            self._settings.setValue("was_playing", was_playing)
        else:
            # Clear playback state if no track
            self._settings.setValue("current_track_id", 0)
            self._settings.setValue("playback_position", 0)
            self._settings.setValue("was_playing", False)

        # Close database
        self._db.close()

        event.accept()

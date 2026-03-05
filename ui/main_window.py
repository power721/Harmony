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
    QListWidget,
    QStackedWidget,
    QPushButton,
    QLineEdit,
    QFileDialog,
    QSlider,
    QLabel,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QStyle,
    QTextBrowser,
)
from PySide6.QtCore import Qt, Signal, QSettings, QSize
from PySide6.QtGui import QIcon, QCursor, QPixmap, QPainter, QColor
from typing import Optional
import sys
from pathlib import Path

from database import DatabaseManager
from player import PlayerController
from player.engine import PlayMode, PlayerState
from services import LyricsService, CoverService
from ui.library_view import LibraryView
from ui.playlist_view import PlaylistView
from ui.player_controls import PlayerControls
from ui.mini_player import MiniPlayer
from ui.queue_view import QueueView
from utils.global_hotkeys import GlobalHotkeys, setup_media_key_handler
from utils import t, set_language, get_language


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    play_track = Signal(int)  # Signal to play a track by ID

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

        title = QLabel(t("lyrics"))
        title.setObjectName("lyricsTitle")
        title.setAlignment(Qt.AlignLeft)
        title_layout.addWidget(title)

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
            count = self._player.scan_directory(
                folder, progress_callback=lambda current, total: None
            )
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
        # (labels will be refreshed when track changes)

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
                f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>{t("not_playing")}</div>'
            )
            return

        # Load lyrics (fast, local only)
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        path = track_dict.get("path", "")

        # Show loading message
        self._lyrics_view.setHtml(
            f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}</div>'
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
                    f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>{t("lyrics_found_parse_failed")}<br><br>{t("ensure_lrc_valid")}</div>'
                )
            else:
                self._lyrics_view.setHtml(
                    f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}<br><br>---<br><br>{t("no_lyrics")}<br><br>{t("click_download")}</div>'
                )

    def _download_lyrics(self):
        """Download lyrics for current track."""
        if not self._player.current_track_id:
            return

        track = self._db.get_track(self._player.current_track_id)
        if not track:
            return

        self._lyrics_view.setHtml(
            f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">⏳<br><br>{t("searching_lyrics")}</div>'
        )

        from threading import Thread
        from PySide6.QtCore import QMetaObject, Qt, Q_ARG

        def download():
            success = LyricsService.download_and_save_lyrics(
                track.path, track.title, track.artist
            )

            if success:
                lyrics = LyricsService.get_lyrics(track.path, track.title, track.artist)
                if lyrics:
                    self._current_lyrics = lyrics
                    html = (
                            '<div style="color: #b3b3b3; padding: 10px;">'
                            + "<br>".join(text for _, text in lyrics)
                            + "</div>"
                    )
                    QMetaObject.invokeMethod(
                        self._lyrics_view,
                        "setHtml",
                        Qt.QueuedConnection,
                        Q_ARG(str, html),
                    )
                else:
                    QMetaObject.invokeMethod(
                        self._lyrics_view,
                        "setHtml",
                        Qt.QueuedConnection,
                        Q_ARG(
                            str,
                            f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">❌<br><br>{t("lyrics_downloaded_parsing_failed")}</div>',
                        ),
                    )
            else:
                QMetaObject.invokeMethod(
                    self._lyrics_view,
                    "setHtml",
                    Qt.QueuedConnection,
                    Q_ARG(
                        str,
                        f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">❌<br><br>{t("lyrics_not_found")}</div>',
                    ),
                )

        thread = Thread(target=download)
        thread.daemon = True
        thread.start()

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

        download_action = menu.addAction(t("download_lyrics"))
        download_action.triggered.connect(self._download_lyrics)

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

        html = self._build_html(lyrics)
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

    def _build_html(self, lyrics):
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
                padding: 80px 20px;
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

        for i, (_, text) in enumerate(lyrics):
            html += f'<div id="line{i}" class="line">{text}</div>'

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

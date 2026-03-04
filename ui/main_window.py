"""
Main application window for the music player.
"""

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


class MainWindow(QMainWindow):
    """Main application window."""

    # Signals
    play_track = Signal(int)  # Signal to play a track by ID

    def __init__(self):
        """Initialize the main window."""
        super().__init__()

        # Initialize database
        self._db = DatabaseManager()

        # Initialize player controller
        self._player = PlayerController(self._db)

        # Settings
        self._settings = QSettings("HarmonyPlayer", "Harmony")

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
        self.setWindowTitle("Harmony - Music Player")
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
        self._queue_view = QueueView(self._player)

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
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 20, 10, 10)
        layout.setSpacing(5)

        # Logo
        logo_label = QLabel("🎵 Harmony")
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

        self._nav_library = QPushButton("🎼 Library")
        self._nav_library.setCheckable(True)
        self._nav_library.setChecked(True)
        self._nav_library.setStyleSheet(nav_style)
        layout.addWidget(self._nav_library)

        self._nav_playlists = QPushButton("📋 Playlists")
        self._nav_playlists.setCheckable(True)
        self._nav_playlists.setStyleSheet(nav_style)
        layout.addWidget(self._nav_playlists)

        self._nav_queue = QPushButton("🎶 Queue")
        self._nav_queue.setCheckable(True)
        self._nav_queue.setStyleSheet(nav_style)
        layout.addWidget(self._nav_queue)

        self._nav_favorites = QPushButton("⭐ Favorites")
        self._nav_favorites.setCheckable(True)
        self._nav_favorites.setStyleSheet(nav_style)
        layout.addWidget(self._nav_favorites)

        self._nav_history = QPushButton("🕐 History")
        self._nav_history.setCheckable(True)
        self._nav_history.setStyleSheet(nav_style)
        layout.addWidget(self._nav_history)

        layout.addStretch()

        # Add music button
        self._add_music_btn = QPushButton("+ Add Music")
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

        title = QLabel("Lyrics")
        title.setObjectName("lyricsTitle")
        title.setAlignment(Qt.AlignLeft)
        title_layout.addWidget(title)

        title_layout.addStretch()

        # Download lyrics button
        self._download_lyrics_btn = QPushButton("⬇ Download")
        self._download_lyrics_btn.setObjectName("downloadLyricsBtn")
        self._download_lyrics_btn.setFixedHeight(28)
        self._download_lyrics_btn.clicked.connect(self._download_lyrics)
        title_layout.addWidget(self._download_lyrics_btn)

        layout.addLayout(title_layout)

        # Lyrics text browser (has built-in scrolling)
        self._lyrics_browser = QTextBrowser()
        self._lyrics_browser.setObjectName("lyricsContent")
        self._lyrics_browser.setOpenExternalLinks(False)
        self._lyrics_browser.setContextMenuPolicy(Qt.CustomContextMenu)
        self._lyrics_browser.customContextMenuRequested.connect(
            self._show_lyrics_context_menu
        )
        self._lyrics_browser.setFocusPolicy(Qt.NoFocus)  # Prevent stealing focus

        # Store anchor positions for each line
        self._lyric_line_anchors = {}

        self._lyrics_browser.setStyleSheet("""
            QTextBrowser#lyricsContent {
                border: none;
                background-color: #1a1a1a;
                color: #c0c0c0;
                font-size: 14px;
                border-radius: 8px;
                padding: 10px;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar:horizontal {
                background-color: #1a1a1a;
                height: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal {
                background-color: #404040;
                border-radius: 6px;
                min-width: 40px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
            }
        """)

        layout.addWidget(self._lyrics_browser, 1)  # Give it stretch to fill space

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

        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)

        play_pause_action = tray_menu.addAction("Play/Pause")
        play_pause_action.triggered.connect(self._toggle_play_pause)

        next_action = tray_menu.addAction("Next")
        next_action.triggered.connect(self._player.engine.play_next)

        prev_action = tray_menu.addAction("Previous")
        prev_action.triggered.connect(self._player.engine.play_previous)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Quit")
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
        self._nav_favorites.setChecked(False)
        self._nav_history.setChecked(True)

        # Load history with delay to avoid blocking
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._library_view.show_history)

    def _add_music(self):
        """Add music to the library."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle("Select Music Folder")

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
            "Scanning",
            f"Added music from folder. Refresh the library to see new tracks.",
        )

    def _play_track(self, track_id: int):
        """Play a track."""
        self._player.play_track(track_id)

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        # Reset lyric line tracking
        self._current_lyric_line = None
        self._lyric_line_anchors = {}

        if not track_dict:
            self._lyrics_browser.setHtml(
                '<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>No track playing</div>'
            )
            return

        # Load lyrics (fast, local only)
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        path = track_dict.get("path", "")

        # Show loading message
        self._lyrics_browser.setHtml(
            f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}</div>'
        )
        self._current_lyrics = []

        # Try to load lyrics
        lyrics = LyricsService.get_lyrics(path, title, artist)
        if lyrics:
            self._current_lyrics = lyrics
            # Display first few lines as preview
            preview_lines = "<br>".join(text for _, text in lyrics[:3])
            if len(lyrics) > 3:
                preview_lines += "<br>..."
            self._lyrics_browser.setHtml(
                f'<div style="color: #b3b3b3; padding: 10px;">{preview_lines}</div>'
            )
        else:
            # Check if .lrc file exists nearby
            from pathlib import Path

            track_path = Path(path)
            lrc_path = track_path.with_suffix(".lrc")
            lyrics_dir = track_path.parent / "lyrics"
            lrc_alt = lyrics_dir / f"{track_path.stem}.lrc"

            if lrc_path.exists() or lrc_alt.exists():
                self._lyrics_browser.setHtml(
                    '<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>Lyrics file found but could not be parsed.<br><br>Make sure the .lrc file is valid.</div>'
                )
            else:
                self._lyrics_browser.setHtml(
                    f'<div style="color: #b3b3b3; text-align: center; padding: 40px;">🎵<br><br>♪ {title} ♪<br><br>by {artist}<br><br>---<br><br>No lyrics available<br><br>Click "⬇ Download" to search for lyrics online.</div>'
                )

    def _download_lyrics(self):
        """Download lyrics for current track."""
        if not self._player.current_track_id:
            return

        track = self._db.get_track(self._player.current_track_id)
        if not track:
            return

        self._lyrics_browser.setHtml(
            '<div style="color: #b3b3b3; text-align: center; padding: 40px;">⏳<br><br>Searching for lyrics...<br><br>Please wait...</div>'
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
                        self._lyrics_browser,
                        "setHtml",
                        Qt.QueuedConnection,
                        Q_ARG(str, html),
                    )
                else:
                    QMetaObject.invokeMethod(
                        self._lyrics_browser,
                        "setHtml",
                        Qt.QueuedConnection,
                        Q_ARG(
                            str,
                            '<div style="color: #b3b3b3; text-align: center; padding: 40px;">❌<br><br>Lyrics downloaded but could not be loaded.</div>',
                        ),
                    )
            else:
                QMetaObject.invokeMethod(
                    self._lyrics_browser,
                    "setHtml",
                    Qt.QueuedConnection,
                    Q_ARG(
                        str,
                        '<div style="color: #b3b3b3; text-align: center; padding: 40px;">❌<br><br>Could not find lyrics online.<br><br>Try searching manually and<br>adding the .lrc file.</div>',
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

        download_action = menu.addAction("⬇ Download Lyrics")
        download_action.triggered.connect(self._download_lyrics)

        refresh_action = menu.addAction("🔄 Refresh")
        refresh_action.triggered.connect(self._refresh_lyrics)

        menu.exec_(self._lyrics_browser.mapToGlobal(pos))

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
        self._status_bar.showMessage(
            f"Added {count} track{'s' if count > 1 else ''} to queue", 3000
        )

    def _on_position_changed(self, position_ms: int):
        """Handle position change for lyrics sync with highlight and auto-scroll."""
        if not hasattr(self, "_current_lyrics") or not self._current_lyrics:
            return

        position_s = position_ms / 1000.0

        from utils import find_lyric_line

        line_index = find_lyric_line(self._current_lyrics, position_s)

        if line_index is not None and line_index >= 0:
            # Only update if line changed (avoid unnecessary updates)
            if self._current_lyric_line != line_index:
                self._current_lyric_line = line_index

                # Build lyrics HTML with current line highlighted and anchors for scrolling
                lyrics_html = '<div style="line-height: 2.2; color: #b3b3b3; font-size: 14px; padding: 10px;">'

                for i, (time, text) in enumerate(self._current_lyrics):
                    anchor_name = f"line{i}"
                    if i == line_index:
                        # Highlight current line with different color, size, and weight
                        lyrics_html += (
                            f'<a id="{anchor_name}" name="{anchor_name}"></a>'
                        )
                        lyrics_html += f'<p style="color: #1db954; font-size: 17px; font-weight: bold; margin: 6px 0; padding: 10px; background-color: rgba(29, 185, 84, 0.15); border-radius: 6px;">{text}</p>'
                    else:
                        # Normal line with subtle opacity
                        lyrics_html += (
                            f'<a id="{anchor_name}" name="{anchor_name}"></a>'
                        )
                        lyrics_html += (
                            f'<p style="margin: 4px 0; opacity: 0.7;">{text}</p>'
                        )

                lyrics_html += "</div>"
                self._lyrics_browser.setHtml(lyrics_html)

                # Use QTimer to scroll after HTML is rendered
                from PySide6.QtCore import QTimer

                QTimer.singleShot(10, lambda: self._scroll_to_line(line_index))

    def _scroll_to_line(self, line_index: int):
        """Scroll lyrics to show the specified line using anchor-based scrolling."""
        anchor_name = f"line{line_index}"

        # Use QTextBrowser's built-in scrollToAnchor method
        # This is much more reliable than manual pixel calculations
        self._lyrics_browser.scrollToAnchor(anchor_name)

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

"""
Mini player mode - a small floating window.
"""
import logging
import threading

from pathlib import Path

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QKeySequence, QShortcut, QIcon, QPixmap, QPainter, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
)

from domain.playback import PlaybackState, PlayMode
from services.playback import PlaybackService
from system.i18n import t
from ui.widgets.mini_lyrics_widget import MiniLyricsWidget
from ui.widgets.player_controls import ClickableSlider
from utils import format_time

logger = logging.getLogger(__name__)

class MiniPlayer(QWidget):
    """
    Mini player - a compact floating window.

    Features:
    - Always on top
    - Compact size
    - Essential controls only
    - Draggable
    """

    closed = Signal()  # Signal when mini player is closed
    _cover_loaded = Signal(str)  # Signal for cover loaded in background thread
    _lyrics_loaded = Signal(str)  # Signal for lyrics loaded in background thread

    def __init__(self, player: PlaybackService, parent=None):
        """
        Initialize mini player.

        Args:
            player: Player controller instance
            parent: Parent widget
        """
        super().__init__(parent)
        self._player = player
        self._is_dragging = False
        self._drag_position = None
        self._is_seeking = False  # Track if user is seeking
        self._current_track_title = ""  # Current track title for window title

        self._setup_ui()
        self._setup_connections()
        self._setup_window_properties()

    def _setup_window_properties(self):
        """Setup window properties."""
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(350, 150)

    def _setup_ui(self):
        """Setup the user interface."""
        # Main container widget
        container = QWidget(self)
        container.setGeometry(0, 0, 350, 150)

        # Create rounded rectangle background
        container.setStyleSheet("""
            QWidget {
                background-color: #282828;
                border-radius: 12px;
            }
        """)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(8)

        # Top row - track info and close button
        top_layout = QHBoxLayout()

        # Cover art (small)
        self._cover_label = QLabel()
        self._cover_label.setFixedSize(50, 50)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setStyleSheet("""
            QLabel {
                background-color: #404040;
                border-radius: 6px;
            }
        """)
        self._set_default_cover()
        top_layout.addWidget(self._cover_label)

        # Track info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self._title_label = QLabel(t("not_playing"))
        self._title_label.setStyleSheet("""
            color: #ffffff;
            font-weight: bold;
            font-size: 13px;
        """)
        # self._title_label.setWordWrap(True)
        info_layout.addWidget(self._title_label)

        self._album_label = QLabel("")
        self._album_label.setStyleSheet("""
            color: #b3b3b3;
            font-size: 11px;
        """)
        # info_layout.addWidget(self._album_label)

        self._artist_label = QLabel("")
        self._artist_label.setStyleSheet("""
            color: #b3b3b3;
            font-size: 11px;
        """)
        # self._artist_label.setWordWrap(True)
        info_layout.addWidget(self._artist_label)

        top_layout.addLayout(info_layout)

        top_layout.addStretch()

        # Close button
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(26, 26)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #b3b3b3;
                font-size: 22px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #404040;
                border-radius: 14px;
            }
        """)
        top_layout.addWidget(self._close_btn)

        layout.addLayout(top_layout)

        self.lyrics = MiniLyricsWidget()
        self.lyrics.setMinimumHeight(40)
        self.lyrics.setMinimumWidth(140)
        layout.addWidget(self.lyrics)

        # Progress bar
        self._progress_slider = ClickableSlider(Qt.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setCursor(Qt.PointingHandCursor)
        self._progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 3px;
                background: #404040;
                border-radius: 1px;
            }
            QSlider::handle:horizontal {
                width: 10px;
                height: 10px;
                background: #1db954;
                border-radius: 5px;
                margin: -3px 0;
            }
            QSlider::handle:horizontal:hover {
                background: #1ed760;
            }
        """)
        layout.addWidget(self._progress_slider)

        # Bottom row - controls and time
        bottom_layout = QHBoxLayout()

        # Time labels
        self._current_time = QLabel("0:00")
        self._current_time.setStyleSheet("color: #b3b3b3; font-size: 10px; font-family: monospace;")
        bottom_layout.addWidget(self._current_time)

        bottom_layout.addStretch()

        # Controls
        self._prev_btn = self._create_control_button("previous.svg", 28)
        bottom_layout.addWidget(self._prev_btn)

        self._play_pause_btn = self._create_control_button("play.svg", 32)
        self._play_pause_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        bottom_layout.addWidget(self._play_pause_btn)

        self._next_btn = self._create_control_button("next.svg", 28)
        bottom_layout.addWidget(self._next_btn)

        bottom_layout.addStretch()

        self._total_time = QLabel("0:00")
        self._total_time.setStyleSheet("color: #b3b3b3; font-size: 10px; font-family: monospace;")
        bottom_layout.addWidget(self._total_time)

        layout.addLayout(bottom_layout)

    def _create_control_button(self, icon_name: str, size: int) -> QPushButton:
        """Create a control button with SVG icon."""
        btn = QPushButton()
        btn.setFixedSize(size, size)
        btn.setCursor(Qt.PointingHandCursor)

        # Load SVG icon
        icons_dir = Path(__file__).parent.parent.parent / "icons"
        icon_path = icons_dir / icon_name
        if icon_path.exists():
            icon = QIcon(str(icon_path))
            btn.setIcon(icon)
            btn.setIconSize(QSize(16, 16))

        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
            }
        """)
        return btn

    def _setup_connections(self):
        """Setup signal connections."""
        self._close_btn.clicked.connect(self.close)

        self._play_pause_btn.clicked.connect(self._toggle_play_pause)
        self._prev_btn.clicked.connect(self._play_previous)  # Custom handler
        self._next_btn.clicked.connect(self._player.engine.play_next)

        # Progress slider signals
        self._progress_slider.sliderPressed.connect(self._on_seek_start)
        self._progress_slider.sliderReleased.connect(self._on_seek_end)
        self._progress_slider.clicked_value.connect(self._on_slider_clicked)

        # Engine connections
        self._player.engine.state_changed.connect(self._on_state_changed)
        self._player.engine.position_changed.connect(self._on_position_changed)
        self._player.engine.duration_changed.connect(self._on_duration_changed)
        self._player.engine.current_track_changed.connect(self._on_track_changed)

        # Setup keyboard shortcuts for mini player
        self._setup_shortcuts()

        # Connect cover loaded signal
        self._cover_loaded.connect(self._show_cover)

        # Connect lyrics loaded signal
        self._lyrics_loaded.connect(self._show_lyrics)

        # Initialize with current track info
        self._initialize_current_track()

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._player.engine.state == PlaybackState.PLAYING:
            self._player.engine.pause()
        else:
            self._player.engine.play()

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts for mini player."""
        # Space - Play/Pause
        QShortcut(QKeySequence(Qt.Key_Space), self, self._toggle_play_pause)

        # Ctrl/Cmd + Left - Previous track
        QShortcut(QKeySequence("Ctrl+Left"), self, self._play_previous)

        # Ctrl/Cmd + Right - Next track
        QShortcut(QKeySequence("Ctrl+Right"), self, self._player.engine.play_next)

        # Ctrl/Cmd + Up - Volume up
        QShortcut(QKeySequence("Ctrl+Up"), self, self._volume_up)

        # Ctrl/Cmd + Down - Volume down
        QShortcut(QKeySequence("Ctrl+Down"), self, self._volume_down)

        # Ctrl/Cmd + M - Toggle mini mode (close mini player)
        QShortcut(QKeySequence("Ctrl+M"), self, self.close)

    def _volume_up(self):
        """Increase volume."""
        current_volume = self._player.engine.volume
        new_volume = min(100, current_volume + 5)
        self._player.engine.set_volume(new_volume)

    def _volume_down(self):
        """Decrease volume."""
        current_volume = self._player.engine.volume
        new_volume = max(0, current_volume - 5)
        self._player.engine.set_volume(new_volume)

    def _play_previous(self):
        """Play previous track - always switches to previous song in mini player."""
        current_index = self._player.engine.current_index
        playlist_size = len(self._player.engine.playlist_items)

        if playlist_size == 0:
            return

        # Always go to previous track (ignore the 3-second rule)
        new_index = current_index - 1

        # Handle wraparound based on play mode
        play_mode = self._player.engine.play_mode
        if new_index < 0:
            if play_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
                new_index = playlist_size - 1
            else:
                new_index = 0  # Stay at first track

        # Play the track
        self._player.engine.play_at(new_index)

    def _on_seek_start(self):
        """Handle seek start (slider pressed)."""
        self._is_seeking = True

    def _on_seek_end(self):
        """Handle seek end (slider released)."""
        if hasattr(self, "_current_duration"):
            # Calculate position in milliseconds
            position_ms = int(
                (self._progress_slider.value() / 1000) * self._current_duration * 1000
            )
            self._player.engine.seek(position_ms)
        self._is_seeking = False

    def _on_slider_clicked(self, value: int):
        """Handle click on progress slider - jump to position."""
        if hasattr(self, "_current_duration") and self._current_duration > 0:
            # Calculate position in milliseconds
            position_ms = int((value / 1000) * self._current_duration * 1000)
            self._player.engine.seek(position_ms)

    def _initialize_current_track(self):
        """Initialize with current track info if playing."""
        icons_dir = Path(__file__).parent.parent.parent / "icons"
        # Update play/pause button state
        if self._player.engine.state == PlaybackState.PLAYING:
            icon_path = icons_dir / "pause.svg"
        else:
            icon_path = icons_dir / "play.svg"
        if icon_path.exists():
            self._play_pause_btn.setIcon(QIcon(str(icon_path)))

        # Get current track info
        current_track = self._player.engine.current_track
        if current_track:
            self._on_track_changed(current_track)

            # Initialize position and duration
            position_ms = self._player.engine.position()
            self._on_position_changed(position_ms)

            # Get duration from player if available
            duration_ms = self._player.engine.duration()
            if duration_ms > 0:
                self._on_duration_changed(duration_ms)
        else:
            self._on_track_changed(None)

    def _on_state_changed(self, state: PlaybackState):
        """Handle player state change."""
        icons_dir = Path(__file__).parent.parent.parent / "icons"
        if state == PlaybackState.PLAYING:
            icon_path = icons_dir / "pause.svg"
            if icon_path.exists():
                self._play_pause_btn.setIcon(QIcon(str(icon_path)))
            # Update window title to show current track
            if self._current_track_title:
                self.setWindowTitle(self._current_track_title)
        else:
            icon_path = icons_dir / "play.svg"
            if icon_path.exists():
                self._play_pause_btn.setIcon(QIcon(str(icon_path)))
            # Paused or stopped - show original app title
            self.setWindowTitle(t("app_title"))

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        if hasattr(self, "_current_duration") and self._current_duration > 0:
            # Don't update slider while user is dragging it
            if not self._is_seeking:
                value = int((position_ms / (self._current_duration * 1000)) * 1000)
                self._progress_slider.setValue(value)
            # Always update time display
            self._current_time.setText(format_time(position_ms / 1000))
            self.lyrics.update_position(position_ms / 1000)

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self._current_duration = duration_ms / 1000
        self._total_time.setText(format_time(self._current_duration))

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        if track_dict:
            # Update UI immediately
            title = track_dict.get("title", t("unknown"))
            album = track_dict.get("album", "")
            artist = track_dict.get("artist", "")
            self._title_label.setText(title)
            self._artist_label.setText(artist)
            self._album_label.setText(album)

            # Save current track title and update window title if playing
            if artist:
                self._current_track_title = f"{title} - {artist}"
            else:
                self._current_track_title = title

            if self._player.engine.state == PlaybackState.PLAYING:
                self.setWindowTitle(self._current_track_title)

            # Load cover asynchronously to avoid blocking
            self._load_cover_async(track_dict)

            # Load lyrics asynchronously
            self._load_lyrics_async(track_dict)
        else:
            self._title_label.setText(t("not_playing"))
            self._artist_label.setText("")
            self._album_label.setText("")
            self._current_track_title = ""
            self.setWindowTitle(t("app_title"))
            self._set_default_cover()
            self.lyrics.set_lyrics("")

    def _load_cover_async(self, track_dict: dict):
        """Load cover art in background thread."""

        def load_cover():
            from pathlib import Path

            # First check if cover_path is already saved in database
            cover_path = track_dict.get("cover_path")
            if cover_path and Path(cover_path).exists():
                return cover_path

            # Fall back to extracting from file
            path = track_dict.get("path", "")
            title = track_dict.get("title", "")
            artist = track_dict.get("artist", "")
            album = track_dict.get("album", "")

            # Check if this is an online QQ Music track
            source_type = track_dict.get("source_type", "")
            cloud_file_id = track_dict.get("cloud_file_id", "")
            is_online = source_type == "online"

            if is_online and cloud_file_id:
                # For online QQ Music tracks, get cover directly by song_mid
                logger.debug(f"[MiniPlayer] Getting cover for online track: song_mid={cloud_file_id}")
                try:
                    cover_service = self._player.cover_service
                    if cover_service:
                        cover_path = cover_service.get_online_cover(
                            song_mid=cloud_file_id,
                            album_mid=None,  # We don't have album_mid in track_dict yet
                            artist=track_dict.get("artist", ""),
                            title=track_dict.get("title", "")
                        )
                        if cover_path:
                            logger.debug(f"[MiniPlayer] Got online cover: {cover_path}")
                            return cover_path
                except Exception as e:
                    logger.error(f"[MiniPlayer] Error getting online cover: {e}")

            # For cloud files that need download, skip online cover fetching
            # Online cover will be fetched after download completes in _save_cloud_track_to_library
            needs_download = track_dict.get("needs_download", False)
            is_cloud = track_dict.get("is_cloud", False)
            skip_online = needs_download or (is_cloud and not path)

            return self._player.get_track_cover(path, title, artist, album, skip_online=skip_online)

        def worker():
            cover_path = load_cover()
            # Use signal for thread-safe UI update
            self._cover_loaded.emit(cover_path or "")

        # Run in thread
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _show_cover(self, cover_path: str):
        """Show cover art (called via signal from background thread)."""
        if cover_path:
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    50, 50, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
                self._cover_label.setPixmap(scaled)
            else:
                self._set_default_cover()
        else:
            self._set_default_cover()

    def _set_default_cover(self):
        """Set default cover placeholder."""
        pixmap = QPixmap(50, 50)
        pixmap.fill(QColor("#404040"))
        self._cover_label.setPixmap(pixmap)

    def _load_lyrics_async(self, track_dict: dict):
        """Load lyrics in background thread."""

        def load_lyrics():
            from services.lyrics.lyrics_service import LyricsService

            path = track_dict.get("path", "")
            title = track_dict.get("title", "")
            artist = track_dict.get("artist", "")
            album = track_dict.get("album", "")

            # Check if this is an online QQ Music track with song_mid
            source_type = track_dict.get("source_type", "")
            cloud_file_id = track_dict.get("cloud_file_id", "")
            is_online = source_type == "online"

            if is_online and cloud_file_id:
                # For online QQ Music tracks, get lyrics by song_mid
                logger.debug(f"[MiniPlayer] Getting lyrics for online track: song_mid={cloud_file_id}")
                try:
                    lyrics = LyricsService.get_lyrics_by_qqmusic_mid(cloud_file_id)
                    if lyrics:
                        logger.debug(f"[MiniPlayer] Got online lyrics: {len(lyrics)} chars")
                        return lyrics
                except Exception as e:
                    logger.error(f"[MiniPlayer] Error getting online lyrics: {e}")

            # For local files or cloud files, use standard lyrics loading
            needs_download = track_dict.get("needs_download", False)
            is_cloud = track_dict.get("is_cloud", False)
            skip_online = needs_download or (is_cloud and not path)

            return LyricsService.get_lyrics(path, title, artist, album)

        def worker():
            lyrics = load_lyrics()
            # Use signal for thread-safe UI update
            self._lyrics_loaded.emit(lyrics or "")

        # Run in thread
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _show_lyrics(self, lyrics: str):
        """Show lyrics (called via signal from background thread)."""
        self.lyrics.set_lyrics(lyrics)

    def mousePressEvent(self, event):
        """Handle mouse press for dragging."""
        if event.button() == Qt.LeftButton:
            self._is_dragging = True
            self._drag_position = (
                    event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        """Handle mouse move for dragging."""
        if self._is_dragging and event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        if event.button() == Qt.LeftButton:
            self._is_dragging = False

    def closeEvent(self, event):
        """Handle close event."""
        self.closed.emit()
        event.accept()

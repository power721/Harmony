"""
Mini player mode - a small floating window.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtGui import QPixmap, QPainter, QColor, QKeySequence, QShortcut

from services.playback import PlaybackService
from domain.playback import PlaybackState, PlayMode
from utils import format_time
from system.i18n import t
import threading


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
        self.setFixedSize(350, 120)

    def _setup_ui(self):
        """Setup the user interface."""
        # Main container widget
        container = QWidget(self)
        container.setGeometry(0, 0, 350, 120)

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
        self._cover_label.setStyleSheet("""
            background-color: #404040;
            border-radius: 6px;
        """)
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
        self._title_label.setWordWrap(True)
        info_layout.addWidget(self._title_label)

        self._artist_label = QLabel("")
        self._artist_label.setStyleSheet("""
            color: #b3b3b3;
            font-size: 11px;
        """)
        self._artist_label.setWordWrap(True)
        info_layout.addWidget(self._artist_label)

        top_layout.addLayout(info_layout)

        top_layout.addStretch()

        # Close button
        self._close_btn = QPushButton("×")
        self._close_btn.setFixedSize(24, 24)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #b3b3b3;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton:hover {
                color: #ffffff;
                background-color: #404040;
                border-radius: 12px;
            }
        """)
        top_layout.addWidget(self._close_btn)

        layout.addLayout(top_layout)

        # Progress bar
        self._progress_slider = QSlider(Qt.Horizontal)
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
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
        self._current_time.setStyleSheet("color: #b3b3b3; font-size: 10px;")
        bottom_layout.addWidget(self._current_time)

        bottom_layout.addStretch()

        # Controls
        self._prev_btn = self._create_control_button("⏮", 28)
        bottom_layout.addWidget(self._prev_btn)

        self._play_pause_btn = self._create_control_button("▶️", 32)
        self._play_pause_btn.setStyleSheet("""
            QPushButton {
                background: #1db954;
                border: none;
                color: #000000;
                font-size: 16px;
                border-radius: 16px;
            }
            QPushButton:hover {
                background: #1ed760;
            }
        """)
        bottom_layout.addWidget(self._play_pause_btn)

        self._next_btn = self._create_control_button("⏭", 28)
        bottom_layout.addWidget(self._next_btn)

        bottom_layout.addStretch()

        self._total_time = QLabel("0:00")
        self._total_time.setStyleSheet("color: #b3b3b3; font-size: 10px;")
        bottom_layout.addWidget(self._total_time)

        layout.addLayout(bottom_layout)

    def _create_control_button(self, text: str, size: int) -> QPushButton:
        """Create a control button."""
        btn = QPushButton(text)
        btn.setFixedSize(size, size)
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #b3b3b3;
                font-size: 14px;
            }
            QPushButton:hover {
                color: #ffffff;
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

        # Engine connections
        self._player.engine.state_changed.connect(self._on_state_changed)
        self._player.engine.position_changed.connect(self._on_position_changed)
        self._player.engine.duration_changed.connect(self._on_duration_changed)
        self._player.engine.current_track_changed.connect(self._on_track_changed)

        # Setup keyboard shortcuts for mini player
        self._setup_shortcuts()

        # Connect cover loaded signal
        self._cover_loaded.connect(self._show_cover)

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

    def _initialize_current_track(self):
        """Initialize with current track info if playing."""
        # Update play/pause button state
        if self._player.engine.state == PlaybackState.PLAYING:
            self._play_pause_btn.setText("⏸")
        else:
            self._play_pause_btn.setText("▶️")

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
        if state == PlaybackState.PLAYING:
            self._play_pause_btn.setText("⏸")
            # Update window title to show current track
            if self._current_track_title:
                self.setWindowTitle(self._current_track_title)
        else:
            self._play_pause_btn.setText("▶️")
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

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self._current_duration = duration_ms / 1000
        self._total_time.setText(format_time(self._current_duration))

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        if track_dict:
            # Update UI immediately
            title = track_dict.get("title", t("unknown"))
            artist = track_dict.get("artist", "")
            self._title_label.setText(title)
            self._artist_label.setText(artist)

            # Save current track title and update window title if playing
            if artist:
                self._current_track_title = f"{title} - {artist}"
            else:
                self._current_track_title = title

            if self._player.engine.state == PlaybackState.PLAYING:
                self.setWindowTitle(self._current_track_title)

            # Load cover asynchronously to avoid blocking
            self._load_cover_async(track_dict)
        else:
            self._title_label.setText(t("not_playing"))
            self._artist_label.setText("")
            self._current_track_title = ""
            self.setWindowTitle(t("app_title"))
            self._cover_label.clear()

    def _load_cover_async(self, track_dict: dict):
        """Load cover art in background thread."""
        def load_cover():
            from services import CoverService
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

            return CoverService.get_cover(path, title, artist, album)

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
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(cover_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    50, 50, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
                )
                self._cover_label.setPixmap(scaled)
            else:
                self._cover_label.clear()
        else:
            self._cover_label.clear()

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

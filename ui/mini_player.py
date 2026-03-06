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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QPainter, QColor

from player import PlayerController
from player.engine import PlayerState
from utils import format_time, t


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

    def __init__(self, player: PlayerController, parent=None):
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
        self._prev_btn.clicked.connect(self._player.engine.play_previous)
        self._next_btn.clicked.connect(self._player.engine.play_next)

        self._progress_slider.sliderReleased.connect(self._on_seek)

        # Engine connections
        self._player.engine.state_changed.connect(self._on_state_changed)
        self._player.engine.position_changed.connect(self._on_position_changed)
        self._player.engine.duration_changed.connect(self._on_duration_changed)
        self._player.engine.current_track_changed.connect(self._on_track_changed)

        # Initialize with current track info
        self._initialize_current_track()

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._player.engine.state == PlayerState.PLAYING:
            self._player.engine.pause()
        else:
            self._player.engine.play()

    def _on_seek(self):
        """Handle seek."""
        if hasattr(self, "_current_duration"):
            # Calculate position in milliseconds
            position_ms = int(
                (self._progress_slider.value() / 1000) * self._current_duration * 1000
            )
            self._player.engine.seek(position_ms)

    def _initialize_current_track(self):
        """Initialize with current track info if playing."""
        # Update play/pause button state
        if self._player.engine.state == PlayerState.PLAYING:
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

    def _on_state_changed(self, state: PlayerState):
        """Handle player state change."""
        if state == PlayerState.PLAYING:
            self._play_pause_btn.setText("⏸")
        else:
            self._play_pause_btn.setText("▶️")

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        if hasattr(self, "_current_duration") and self._current_duration > 0:
            value = int((position_ms / (self._current_duration * 1000)) * 1000)
            self._progress_slider.setValue(value)
            self._current_time.setText(format_time(position_ms / 1000))

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self._current_duration = duration_ms / 1000
        self._total_time.setText(format_time(self._current_duration))

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        if track_dict:
            self._title_label.setText(track_dict.get("title", t("unknown")))
            self._artist_label.setText(track_dict.get("artist", ""))

            # Load cover
            self._load_cover(track_dict)
        else:
            self._title_label.setText(t("not_playing"))
            self._artist_label.setText("")
            self._cover_label.clear()

    def _load_cover(self, track_dict: dict):
        """Load cover art."""
        from PySide6.QtGui import QPixmap
        from services import CoverService

        path = track_dict.get("path", "")
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        album = track_dict.get("album", "")

        cover_path = CoverService.get_cover(path, title, artist, album)

        if cover_path:
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

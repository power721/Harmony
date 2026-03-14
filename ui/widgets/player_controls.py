"""
Player controls widget for playback control.
"""
import logging

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QPushButton,
    QSlider,
    QLabel,
    QDialog,
    QVBoxLayout,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QPixmap, QCursor, QMouseEvent, QScreen
import threading

from services.playback import PlaybackService
from domain.playback import PlaybackState, PlayMode
from utils import format_time
from system.i18n import t
from system.event_bus import EventBus

# Configure logging
logger = logging.getLogger(__name__)


class PlayerControls(QWidget):
    """Player controls widget at the bottom of the main window."""

    # Signal for cover loaded in background thread
    _cover_loaded = Signal(str)

    def __init__(self, player: PlaybackService, parent=None):
        """
        Initialize player controls.

        Args:
            player: Player controller instance
            parent: Parent widget
        """
        super().__init__(parent)
        self._player = player
        self._current_duration = 0
        self._is_seeking = False
        self._current_cover_path = None  # Store current cover path

        self._setup_ui()
        self._setup_connections()

        # Update position timer
        self._position_timer = QTimer(self)
        self._position_timer.timeout.connect(self._update_position_display)
        self._position_timer.start(100)

        # Initialize favorite button state if there's a current track
        QTimer.singleShot(0, self._initialize_favorite_button)

    def _initialize_favorite_button(self):
        """Initialize favorite button state based on current track."""
        current_track = self._player.engine.current_track
        if current_track:
            track_id = current_track.get("id")
            cloud_file_id = current_track.get("cloud_file_id")
            is_fav = self._player.is_favorite(track_id, cloud_file_id)
            self._update_favorite_button_style(is_fav)

    def _setup_ui(self):
        """Setup the user interface."""
        self.setObjectName("playerControls")
        self.setFixedHeight(90)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 10, 15, 10)
        layout.setSpacing(15)

        # Current track info (left side)
        info_widget = self._create_info_widget()
        layout.addWidget(info_widget, 2)

        # Playback controls (center)
        controls_widget = self._create_playback_controls()
        layout.addWidget(controls_widget, 3)

        # Volume and extra controls (right side)
        volume_widget = self._create_volume_widget()
        layout.addWidget(volume_widget, 1)

        # Apply styles
        self._apply_styles()

    def _create_info_widget(self) -> QWidget:
        """Create track info widget."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Cover art placeholder
        self._cover_label = ClickableLabel()
        self._cover_label.setFixedSize(60, 60)
        self._cover_label.setObjectName("coverArt")
        self._cover_label.setStyleSheet("""
            QLabel#coverArt {
                background-color: #282828;
                border-radius: 4px;
            }
        """)
        # Enable mouse tracking and click events
        self._cover_label.setMouseTracking(True)
        self._cover_label.setCursor(QCursor(Qt.PointingHandCursor))
        self._cover_label.clicked.connect(self._on_cover_clicked)
        layout.addWidget(self._cover_label)

        layout.addSpacing(10)

        # Track info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        self._title_label = QLabel(t("not_playing"))
        self._title_label.setObjectName("trackTitle")
        self._title_label.setStyleSheet("color: #ffffff; font-weight: bold;")

        self._artist_label = QLabel("")
        self._artist_label.setObjectName("trackArtist")
        self._artist_label.setStyleSheet("color: #b3b3b3;")

        info_layout.addWidget(self._title_label)
        info_layout.addWidget(self._artist_label)
        info_layout.addStretch()

        layout.addLayout(info_layout)
        layout.addStretch()

        # Favorite button
        self._favorite_btn = QPushButton("☆")
        self._favorite_btn.setObjectName("favoriteBtn")
        self._favorite_btn.setFixedSize(40, 40)
        self._favorite_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._favorite_btn)

        return widget

    def _create_playback_controls(self) -> QWidget:
        """Create playback controls widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Progress bar
        progress_layout = QHBoxLayout()
        progress_layout.setSpacing(10)

        self._current_time_label = QLabel("0:00")
        self._current_time_label.setObjectName("timeLabel")
        self._current_time_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        self._current_time_label.setFixedWidth(40)

        self._progress_slider = QSlider(Qt.Horizontal)
        self._progress_slider.setObjectName("progressSlider")
        self._progress_slider.setRange(0, 1000)
        self._progress_slider.setValue(0)
        self._progress_slider.setCursor(Qt.PointingHandCursor)

        self._total_time_label = QLabel("0:00")
        self._total_time_label.setObjectName("timeLabel")
        self._total_time_label.setStyleSheet("color: #b3b3b3; font-size: 11px;")
        self._total_time_label.setFixedWidth(40)

        progress_layout.addWidget(self._current_time_label)
        progress_layout.addWidget(self._progress_slider)
        progress_layout.addWidget(self._total_time_label)

        layout.addLayout(progress_layout)

        # Control buttons
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        # Shuffle button
        self._shuffle_btn = self._create_control_button("🔀")
        self._shuffle_btn.setCheckable(True)
        self._shuffle_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self._shuffle_btn)

        controls_layout.addStretch()

        # Previous button
        self._prev_btn = self._create_control_button("⏮")
        self._prev_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self._prev_btn)

        # Play/Pause button
        self._play_pause_btn = self._create_control_button("▶️")
        self._play_pause_btn.setFixedSize(45, 45)
        self._play_pause_btn.setObjectName("playPauseBtn")
        controls_layout.addWidget(self._play_pause_btn)

        # Next button
        self._next_btn = self._create_control_button("⏭")
        self._next_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self._next_btn)

        controls_layout.addStretch()

        # Repeat button
        self._repeat_btn = self._create_control_button("🔁")
        self._repeat_btn.setCheckable(True)
        self._repeat_btn.setFixedSize(40, 40)
        controls_layout.addWidget(self._repeat_btn)

        layout.addLayout(controls_layout)

        return widget

    def _create_volume_widget(self) -> QWidget:
        """Create volume control widget."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()

        # Volume button (mute/unmute)
        self._volume_btn = QPushButton("🔊")
        self._volume_btn.setObjectName("volumeBtn")
        self._volume_btn.setFixedSize(35, 35)
        self._volume_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._volume_btn)

        # Volume slider
        self._volume_slider = QSlider(Qt.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setValue(70)
        self._volume_slider.setFixedWidth(100)
        self._volume_slider.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._volume_slider)

        # Queue button (placeholder)
        # self._queue_btn = QPushButton('📋')
        # self._queue_btn.setObjectName('queueBtn')
        # self._queue_btn.setFixedSize(35, 35)
        # self._queue_btn.setCursor(Qt.PointingHandCursor)
        # layout.addWidget(self._queue_btn)

        return widget

    def _create_control_button(self, text: str) -> QPushButton:
        """Create a control button with emoji support."""
        btn = QPushButton(text)
        btn.setObjectName("controlBtn")
        btn.setCursor(Qt.PointingHandCursor)
        # Use a font that supports emoji
        from PySide6.QtGui import QFontDatabase, QFont

        font = QFont()
        # Try common emoji-supporting fonts in order
        emoji_fonts = [
            "Segoe UI Emoji",
            "Apple Color Emoji",
            "Noto Color Emoji",
            "Symbola",
            "Arial Unicode MS",
            "DejaVu Sans",
        ]
        # Get available font families
        available_families = QFontDatabase.families()
        # Find first available emoji font
        for emoji_font in emoji_fonts:
            if any(emoji_font.lower() in f.lower() for f in available_families):
                font.setFamily(emoji_font)
                break
        else:
            # Fallback to system default
            font = btn.font()
        font.setPointSize(18)
        btn.setFont(font)
        return btn

    def _apply_styles(self):
        """Apply widget styles."""
        self.setStyleSheet("""
            QWidget#playerControls {
                background-color: #181818;
                border-top: 1px solid #282828;
            }
            QPushButton#controlBtn {
                background: transparent;
                border: none;
                color: #b3b3b3;
            }
            QPushButton#controlBtn:hover {
                color: #ffffff;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 6px;
            }
            QPushButton#controlBtn[active="true"] {
                color: #1db954;
            }
            QPushButton#controlBtn[active="true"]:hover {
                color: #1ed760;
            }
            QPushButton#playPauseBtn {
                background: #ffffff;
                border-radius: 22px;
                color: #000000;
                font-size: 22px;
            }
            QPushButton#playPauseBtn:hover {
                background: #1db954;
                color: #000000;
            }
            QPushButton#favoriteBtn {
                background: transparent;
                border: 2px solid #b3b3b3;
                color: #b3b3b3;
                border-radius: 20px;
                font-size: 28px;
            }
            QPushButton#favoriteBtn:hover {
                border-color: #ff4444;
                color: #ff4444;
            }
            QPushButton#favoriteBtn:checked {
                background-color: #ff4444;
                border-color: #ff4444;
                color: #ffffff;
            }
            QPushButton#favoriteBtn:checked:hover {
                background-color: #ff6666;
            }
            QSlider#progressSlider::groove:horizontal {
                height: 4px;
                background: #4d4d4d;
                border-radius: 2px;
            }
            QSlider#progressSlider::handle:horizontal {
                width: 12px;
                height: 12px;
                background: #ffffff;
                border-radius: 6px;
                margin: -4px 0;
            }
            QSlider#progressSlider::handle:horizontal:hover {
                background: #1db954;
            }
            QPushButton#volumeBtn, QPushButton#queueBtn {
                background: transparent;
                border: none;
                color: #b3b3b3;
                font-size: 16px;
            }
            QPushButton#volumeBtn:hover, QPushButton#queueBtn:hover {
                color: #ffffff;
            }
        """)

    def _setup_connections(self):
        """Setup signal connections."""
        # Playback controls
        self._play_pause_btn.clicked.connect(self._toggle_play_pause)
        self._prev_btn.clicked.connect(self._player.engine.play_previous)
        self._next_btn.clicked.connect(self._player.engine.play_next)

        # Progress slider
        self._progress_slider.sliderPressed.connect(self._on_seek_start)
        self._progress_slider.sliderReleased.connect(self._on_seek_end)
        self._progress_slider.valueChanged.connect(self._on_seek)

        # Volume controls
        self._volume_slider.valueChanged.connect(self._on_volume_changed)
        self._volume_btn.clicked.connect(self._toggle_mute)

        # Favorite button
        self._favorite_btn.clicked.connect(self._toggle_favorite)

        # Shuffle and repeat
        self._shuffle_btn.clicked.connect(self._toggle_shuffle)
        self._repeat_btn.clicked.connect(self._toggle_repeat)

        # Engine connections
        self._player.engine.state_changed.connect(self._on_state_changed)
        self._player.engine.position_changed.connect(self._on_position_changed)
        self._player.engine.duration_changed.connect(self._on_duration_changed)
        self._player.engine.current_track_changed.connect(self._on_track_changed)
        self._player.engine.play_mode_changed.connect(self._on_play_mode_changed)
        self._player.engine.volume_changed.connect(self._on_volume_changed_from_engine)

        # EventBus connections
        bus = EventBus.instance()
        bus.favorite_changed.connect(self._on_favorite_changed)
        bus.metadata_updated.connect(self._on_metadata_updated)
        bus.cover_updated.connect(self._on_cover_updated)

        # Cover loaded signal (for thread-safe UI update)
        self._cover_loaded.connect(self._show_cover)

        # Sync button states with current player mode
        self._sync_button_states()

    def _sync_button_states(self):
        """Sync button states with current player mode."""
        current_mode = self._player.engine.play_mode

        # Sync shuffle button
        if current_mode in (
            PlayMode.RANDOM,
            PlayMode.RANDOM_LOOP,
            PlayMode.RANDOM_TRACK_LOOP,
        ):
            self._shuffle_btn.setChecked(True)
            self._shuffle_btn.setText("🔀")
            self._update_button_style(self._shuffle_btn, active=True)
        else:
            self._shuffle_btn.setChecked(False)
            self._shuffle_btn.setText("🔀")
            self._update_button_style(self._shuffle_btn, active=False)

        # Sync repeat button
        if current_mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP):
            self._repeat_btn.setChecked(True)
            self._repeat_btn.setText("🔁")
            self._update_button_style(self._repeat_btn, active=True)
        elif current_mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            self._repeat_btn.setChecked(True)
            self._repeat_btn.setText("🔂")
            self._update_button_style(self._repeat_btn, active=True)
        else:
            self._repeat_btn.setChecked(False)
            self._repeat_btn.setText("🔁")
            self._update_button_style(self._repeat_btn, active=False)

    def _toggle_play_pause(self):
        """Toggle play/pause."""
        if self._player.engine.state == PlaybackState.PLAYING:
            self._player.engine.pause()
        else:
            self._player.engine.play()

    def _on_seek_start(self):
        """Handle seek start."""
        self._is_seeking = True

    def _on_seek_end(self):
        """Handle seek end."""
        self._is_seeking = False
        # Calculate position in milliseconds
        position_ms = int(
            (self._progress_slider.value() / 1000) * self._current_duration * 1000
        )
        self._player.engine.seek(position_ms)

    def _on_seek(self, value: int):
        """Handle seek (update time label while dragging)."""
        if self._current_duration > 0:
            # Calculate position in seconds for display
            position_s = (value / 1000) * self._current_duration
            self._current_time_label.setText(format_time(position_s))

    def _on_volume_changed(self, value: int):
        """Handle volume change from slider."""
        self._player.engine.set_volume(value)
        self._update_volume_button(value)

    def _on_volume_changed_from_engine(self, value: int):
        """Handle volume change from engine (e.g., hotkeys)."""
        self._volume_slider.blockSignals(True)  # Prevent feedback loop
        self._volume_slider.setValue(value)
        self._volume_slider.blockSignals(False)
        self._update_volume_button(value)

    def set_volume(self, volume: int):
        """
        Set volume and update slider.

        Args:
            volume: Volume level (0-100)
        """
        volume = max(0, min(100, volume))
        self._volume_slider.blockSignals(True)  # Prevent feedback loop
        self._volume_slider.setValue(volume)
        self._volume_slider.blockSignals(False)
        self._player.engine.set_volume(volume)
        self._update_volume_button(volume)

    def _update_volume_button(self, value: int):
        """Update volume button icon based on value."""
        if value == 0:
            self._volume_btn.setText("🔇")
        elif value < 50:
            self._volume_btn.setText("🔉")
        else:
            self._volume_btn.setText("🔊")

    def _toggle_mute(self):
        """Toggle mute."""
        if self._volume_slider.value() > 0:
            self._previous_volume = self._volume_slider.value()
            self._volume_slider.setValue(0)
        else:
            volume = getattr(self, "_previous_volume", 70)
            self._volume_slider.setValue(volume)

    def _toggle_favorite(self):
        """Toggle favorite status."""
        self._player.toggle_favorite()
        # UI update is handled by _on_favorite_changed via EventBus

    def _on_favorite_changed(self, item_id, is_favorite: bool, is_cloud: bool = False):
        """Handle favorite status change from EventBus."""
        # Only update if this is the current track
        current_track = self._player.engine.current_track
        if current_track:
            current_id = current_track.get("id")
            current_cloud_file_id = current_track.get("cloud_file_id")

            # Match by track_id or cloud_file_id
            if current_id and current_id == item_id:
                self._update_favorite_button_style(is_favorite)
            elif is_cloud and current_cloud_file_id and current_cloud_file_id == item_id:
                self._update_favorite_button_style(is_favorite)

    def _on_metadata_updated(self, track_id: int):
        """Handle metadata update (e.g., cover path) from EventBus."""
        # Only update if this is the current track
        current_track = self._player.engine.current_track
        if not current_track:
            return

        current_id = current_track.get("id")
        current_path = current_track.get("path")

        # Check if this is the current track by ID or by checking database
        should_reload = False

        if current_id and current_id == track_id:
            # Direct ID match
            should_reload = True
        elif current_path:
            # Try to find track by path and check if it matches
            try:
                # Get database from player if available
                if hasattr(self._player, 'db'):
                    track = self._player.db.get_track_by_path(current_path)
                    if track and track.id == track_id:
                        should_reload = True
                        logger.info(f"[PlayerControls] Found track by path: {track_id}, reloading cover")
            except Exception as e:
                logger.error(f"[PlayerControls] Error checking track by path: {e}")

        if should_reload:
            # Reload from database to get latest cover_path
            if current_path and hasattr(self._player, 'db'):
                try:
                    track = self._player.db.get_track_by_path(current_path)
                    if track:
                        # Create updated track dict
                        updated_track = {
                            "id": track.id,
                            "path": track.path,
                            "title": track.title,
                            "artist": track.artist,
                            "album": track.album,
                            "duration": track.duration,
                            "cover_path": track.cover_path,
                            "source_type": "local",
                        }
                        logger.info(f"[PlayerControls] Metadata updated for current track {track_id}, reloading cover with cover_path={track.cover_path}")
                        QTimer.singleShot(100, lambda: self._load_cover_art_async(updated_track))
                except Exception as e:
                    logger.error(f"[PlayerControls] Error loading updated track: {e}")
            else:
                # Fallback: reload with current track
                logger.info(f"[PlayerControls] Metadata updated for current track {track_id}, reloading cover")
                QTimer.singleShot(100, lambda: self._load_cover_art_async(current_track))

    def _on_cover_updated(self, item_id, is_cloud: bool = False):
        """Handle cover update from EventBus."""
        # Only update if this is the current track
        current_track = self._player.engine.current_track
        if not current_track:
            return

        should_reload = False

        if is_cloud:
            # For cloud files, match by cloud_file_id
            current_cloud_file_id = current_track.get("cloud_file_id")
            logger.debug(f"[PlayerControls] _on_cover_updated: is_cloud=True, item_id={item_id}, current_cloud_file_id={current_cloud_file_id}")
            if current_cloud_file_id and current_cloud_file_id == item_id:
                should_reload = True
        else:
            # For local tracks, match by track_id
            current_id = current_track.get("id")
            logger.debug(f"[PlayerControls] _on_cover_updated: is_cloud=False, item_id={item_id}, current_id={current_id}")
            if current_id and current_id == item_id:
                should_reload = True

        if should_reload:
            logger.info(f"[PlayerControls] Cover updated for current track, reloading")
            # For local tracks, reload from database to get updated cover_path
            if not is_cloud and hasattr(self._player, 'db'):
                try:
                    track = self._player.db.get_track(item_id)
                    if track:
                        updated_track = {
                            "id": track.id,
                            "path": track.path,
                            "title": track.title,
                            "artist": track.artist,
                            "album": track.album,
                            "duration": track.duration,
                            "cover_path": track.cover_path,
                            "source_type": "local",
                        }
                        QTimer.singleShot(100, lambda t=updated_track: self._load_cover_art_async(t))
                        return
                except Exception as e:
                    logger.error(f"[PlayerControls] Error loading updated track: {e}")

            # For cloud files or fallback: clear current cover and reload
            # This ensures the cached cover (just saved) will be loaded
            self._cover_label.clear()
            self._current_cover_path = None
            # Use a copy of current_track to avoid closure issues
            track_copy = dict(current_track)
            QTimer.singleShot(100, lambda t=track_copy: self._load_cover_art_async(t))

    def _update_favorite_button_style(self, is_favorite: bool):
        """Update favorite button style based on favorite status."""
        if is_favorite:
            # Red style for favorited tracks
            self._favorite_btn.setStyleSheet("""
                QPushButton {
                    background-color: #ff4444;
                    border: 2px solid #ff4444;
                    color: #ffffff;
                    border-radius: 20px;
                    font-size: 28px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #ff6666;
                    border-color: #ff6666;
                }
            """)
        else:
            # Default style (clear to use stylesheet)
            self._favorite_btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    border: 2px solid #b3b3b3;
                    color: #b3b3b3;
                    border-radius: 20px;
                    font-size: 28px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    border-color: #ff4444;
                    color: #ff4444;
                }
            """)

    def _toggle_shuffle(self):
        """Toggle shuffle mode."""
        current_mode = self._player.engine.play_mode

        if self._shuffle_btn.isChecked():
            # Enable shuffle - preserve current loop state
            if current_mode == PlayMode.PLAYLIST_LOOP:
                # Switch to random + playlist loop
                self._player.engine.set_play_mode(PlayMode.RANDOM_LOOP)
            elif current_mode == PlayMode.LOOP:
                # Switch to random + track loop
                self._player.engine.set_play_mode(PlayMode.RANDOM_TRACK_LOOP)
            elif current_mode == PlayMode.SEQUENTIAL:
                # Switch to random
                self._player.engine.set_play_mode(PlayMode.RANDOM)
            # Already in a random mode, no change needed
            self._shuffle_btn.setText("🔀")
            self._update_button_style(self._shuffle_btn, active=True)
        else:
            # Disable shuffle - preserve loop state
            if current_mode == PlayMode.RANDOM_LOOP:
                self._player.engine.set_play_mode(PlayMode.PLAYLIST_LOOP)
            elif current_mode == PlayMode.RANDOM_TRACK_LOOP:
                self._player.engine.set_play_mode(PlayMode.LOOP)
            elif current_mode == PlayMode.RANDOM:
                self._player.engine.set_play_mode(PlayMode.SEQUENTIAL)
            self._shuffle_btn.setText("🔀")
            self._update_button_style(self._shuffle_btn, active=False)

    def _update_button_style(self, button: QPushButton, active: bool):
        """Update button style based on active state."""
        from PySide6.QtGui import QPalette

        if active:
            # Set white background and green color for active state
            button.setStyleSheet("""
                QPushButton {
                    background: #ffffff;
                    border: none;
                    color: #1db954;
                    border-radius: 6px;
                    padding: 0px;
                }
                QPushButton:hover {
                    color: #1ed760;
                    background: #ffffff;
                }
            """)
        else:
            # Clear inline style to use default from stylesheet
            button.setStyleSheet("")

    def _toggle_repeat(self):
        """Toggle repeat mode."""
        current_mode = self._player.engine.play_mode

        if current_mode == PlayMode.SEQUENTIAL:
            # Sequential -> Playlist Loop
            self._player.engine.set_play_mode(PlayMode.PLAYLIST_LOOP)
            self._repeat_btn.setText("🔁")
            self._repeat_btn.setChecked(True)
            self._update_button_style(self._repeat_btn, active=True)
        elif current_mode == PlayMode.PLAYLIST_LOOP:
            # Playlist Loop -> Track Loop
            self._player.engine.set_play_mode(PlayMode.LOOP)
            self._repeat_btn.setText("🔂")
        elif current_mode == PlayMode.LOOP:
            # Track Loop -> Sequential
            self._player.engine.set_play_mode(PlayMode.SEQUENTIAL)
            self._repeat_btn.setText("🔁")
            self._repeat_btn.setChecked(False)
            self._update_button_style(self._repeat_btn, active=False)
        elif current_mode == PlayMode.RANDOM:
            # Random -> Random + Playlist Loop
            self._player.engine.set_play_mode(PlayMode.RANDOM_LOOP)
            self._repeat_btn.setText("🔁")
            self._repeat_btn.setChecked(True)
            self._update_button_style(self._repeat_btn, active=True)
        elif current_mode == PlayMode.RANDOM_LOOP:
            # Random Loop -> Random + Track Loop
            self._player.engine.set_play_mode(PlayMode.RANDOM_TRACK_LOOP)
            self._repeat_btn.setText("🔂")
        elif current_mode == PlayMode.RANDOM_TRACK_LOOP:
            # Random Track Loop -> Random
            self._player.engine.set_play_mode(PlayMode.RANDOM)
            self._repeat_btn.setText("🔁")
            self._repeat_btn.setChecked(False)
            self._update_button_style(self._repeat_btn, active=False)

    def _on_play_mode_changed(self, mode: PlayMode):
        """Handle play mode change - sync button states."""
        self._sync_button_states()

    def _on_state_changed(self, state: PlaybackState):
        """Handle player state change."""
        if state == PlaybackState.PLAYING:
            self._play_pause_btn.setText("⏸")
        else:
            self._play_pause_btn.setText("▶")

    def _on_position_changed(self, position_ms: int):
        """Handle position change."""
        if not self._is_seeking and self._current_duration > 0:
            # Convert position to seconds for display
            position_s = position_ms / 1000
            self._current_time_label.setText(format_time(position_s))

            # Update progress slider (0-1000 range)
            value = int((position_ms / (self._current_duration * 1000)) * 1000)
            self._progress_slider.setValue(value)

    def _on_duration_changed(self, duration_ms: int):
        """Handle duration change."""
        self._current_duration = duration_ms / 1000  # Store in seconds
        self._total_time_label.setText(format_time(self._current_duration))

    def _on_track_changed(self, track_dict: dict):
        """Handle track change."""
        if track_dict:
            title = track_dict.get("title", t("unknown"))
            artist = track_dict.get("artist", t("unknown"))
            self._title_label.setText(title)
            self._artist_label.setText(artist)

            # Update favorite button
            track_id = track_dict.get("id")
            cloud_file_id = track_dict.get("cloud_file_id")
            is_fav = self._player.is_favorite(track_id, cloud_file_id)
            self._update_favorite_button_style(is_fav)

            # Clear cover immediately, load in background
            self._cover_label.clear()
            # Use QTimer to delay cover loading so UI doesn't block
            QTimer.singleShot(100, lambda: self._load_cover_art_async(track_dict))
        else:
            self._title_label.setText(t("not_playing"))
            self._artist_label.setText("")
            self._cover_label.clear()
            # Reset favorite button style
            self._update_favorite_button_style(False)
            self._update_favorite_button_style(False)

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        current_track = self._player.engine.current_track
        if not current_track:
            self._title_label.setText(t("not_playing"))

    def _load_cover_art_async(self, track_dict: dict):
        """Load cover art in background thread."""
        def load_cover():
            from pathlib import Path

            # First check if cover_path is already saved in database
            cover_path = track_dict.get("cover_path")
            if cover_path:
                if Path(cover_path).exists():
                    logger.debug(f"[PlayerControls] Found cover_path in track_dict: {cover_path}")
                    return cover_path

            # Fall back to getting cover (embedded, cached, or online)
            path = track_dict.get("path", "")
            title = track_dict.get("title", "")
            artist = track_dict.get("artist", "")
            album = track_dict.get("album", "")

            logger.debug(f"[PlayerControls] Loading cover for: path={path}, title={title}, artist={artist}, album={album}")

            try:
                cover_path = self._player.get_track_cover(path, title, artist, album)
                logger.debug(f"[PlayerControls] get_track_cover returned: {cover_path}")
                if cover_path:
                    return cover_path
            except Exception as e:
                logger.error(f"Cover load error for track {track_dict.get('title', 'Unknown')}: {e}", exc_info=True)
            return None

        def worker():
            cover_path = load_cover()
            logger.info(f"[PlayerControls] Worker emitting cover_path: {cover_path}")
            # Use signal for thread-safe UI update
            self._cover_loaded.emit(cover_path or "")

        # Run in thread
        thread = threading.Thread(target=worker)
        thread.daemon = True
        thread.start()

    def _show_cover(self, cover_path: str):
        """Show cover art (called via signal from background thread)."""
        logger.info(f"[PlayerControls] _show_cover called with: {cover_path}")
        if cover_path:
            try:
                pixmap = QPixmap(cover_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(
                        60,
                        60,
                        Qt.KeepAspectRatioByExpanding,
                        Qt.SmoothTransformation,
                    )
                    self._cover_label.setPixmap(scaled_pixmap)
                    self._current_cover_path = cover_path  # Store cover path
            except Exception as e:
                logger.error(f"Error showing cover: {e}")
        else:
            self._current_cover_path = None

    def _on_cover_clicked(self):
        """Handle cover art click - show large image dialog."""
        if self._current_cover_path:
            try:
                dialog = CoverDialog(self._current_cover_path, self)
                dialog.exec_()
            except Exception as e:
                logger.error(f"Error showing cover dialog: {e}")

    def _update_position_display(self):
        """Update position display continuously."""
        if self._player.engine.state == PlaybackState.PLAYING and not self._is_seeking:
            position_ms = (
                self._player.engine.position()
                if hasattr(self._player.engine, "position")
                else 0
            )
            # Update handled by _on_position_changed signal


class ClickableLabel(QLabel):
    """A QLabel that emits a signal when clicked."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press event."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CoverDialog(QDialog):
    """Dialog to display large cover art."""

    def __init__(self, cover_path: str, parent=None):
        """
        Initialize cover dialog.

        Args:
            cover_path: Path to the cover image
            parent: Parent widget
        """
        super().__init__(parent)
        self._cover_path = cover_path
        self._setup_ui()

    def _setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle(t("album_art"))
        self.setModal(True)

        # Get screen size
        screen = QScreen.availableGeometry(self.screen())
        screen_width = screen.width()
        screen_height = screen.height()

        # Set dialog size to 80% of screen, max 800x800
        dialog_width = min(int(screen_width * 0.8), 800)
        dialog_height = min(int(screen_height * 0.8), 800)
        self.setFixedSize(dialog_width, dialog_height)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Image label (no scroll area needed now)
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setStyleSheet("background-color: #1e1e1e;")

        # Load and scale image to fit dialog
        pixmap = QPixmap(self._cover_path)
        if not pixmap.isNull():
            # Scale image to fit within dialog while maintaining aspect ratio
            scaled = pixmap.scaled(
                dialog_width - 20,  # Leave some margin
                dialog_height - 20,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            image_label.setPixmap(scaled)
        else:
            image_label.setText(t("cover_load_failed"))

        layout.addWidget(image_label)

        # Apply dialog style
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
            }
        """)

    def keyPressEvent(self, event):
        """Handle key press - close on Escape."""
        if event.key() == Qt.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)

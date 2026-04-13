"""
Now playing window with large cover and synchronized lyrics.
"""
import logging
import threading
from contextlib import suppress
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, QSize, QTimer, QEvent
from PySide6.QtGui import QColor, QPixmap, QShortcut, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QApplication,
    QSizeGrip,
    QSizePolicy,
    QDialog,
    QListWidget,
    QListWidgetItem,
)
from shiboken6 import isValid

from domain.playback import PlaybackState, PlayMode
from services.lyrics.lyrics_loader import LyricsLoader
from services.playback import PlaybackService
from system.event_bus import EventBus
from system.i18n import t
from ui.icons import IconName, get_icon
from ui.widgets.cover_loader import CoverLoader
from ui.widgets.player_controls import PlayerControls
from ui.widgets.lyrics_widget_pro import LyricsWidget
from utils import format_time
from PySide6.QtGui import QKeySequence

logger = logging.getLogger(__name__)


class NowPlayingWindow(QWidget):
    """Standalone now-playing window."""

    closed = Signal()
    _cover_loaded = Signal(str, int)

    _STYLE_WINDOW = """
        QWidget#nowPlayingRoot {
            background-color: %background%;
        }
        QLabel#nowPlayingTitle {
            color: %text%;
            font-size: 24px;
            font-weight: bold;
        }
        QLabel#nowPlayingArtist {
            color: %text_secondary%;
            font-size: 14px;
        }
        QLabel#nowPlayingAlbum {
            color: %text_secondary%;
            font-size: 13px;
        }
        QPushButton#nowPlayingClose {
            background: transparent;
            border: none;
            color: %text_secondary%;
            padding: 6px;
            border-radius: 14px;
        }
        QPushButton#nowPlayingMaximize {
            background: transparent;
            border: none;
            color: %text_secondary%;
            padding: 6px;
            border-radius: 14px;
        }
        QPushButton#nowPlayingMaximize:hover {
            background-color: %selection%;
            color: %text%;
        }
        QPushButton#nowPlayingClose:hover {
            background-color: %selection%;
            color: %text%;
        }
        QLabel#nowPlayingCover {
            background-color: %background_alt%;
            border: 1px solid %border%;
            border-radius: 12px;
        }
        QLabel#nowPlayingCover[circleMode="true"] {
            background-color: transparent;
            border: none;
            border-radius: 0px;
        }
        QPushButton#nowPlayingControl {
            background: transparent;
            border: none;
            color: %text_secondary%;
            border-radius: 6px;
            padding: 0px;
        }
        QPushButton#nowPlayingControl:hover {
            background: rgba(255, 255, 255, 0.1);
            color: %text%;
        }
        QPushButton#nowPlayingControl[active="true"] {
            color: %highlight%;
            background-color: %text%;
            border-radius: 6px;
        }
        QPushButton#nowPlayingControl[active="true"]:hover {
            color: %highlight_hover%;
            background-color: %text%;
        }
        QPushButton#nowPlayingPrimaryBtn {
            background-color: %highlight%;
            border: none;
            color: %background%;
            border-radius: 24px;
            padding: 0px;
            min-width: 48px;
            min-height: 48px;
            max-width: 48px;
            max-height: 48px;
        }
        QPushButton#nowPlayingPrimaryBtn:hover {
            background-color: %highlight_hover%;
        }
        QSlider#nowPlayingProgress::groove:horizontal {
            height: 4px;
            background: %border%;
            border-radius: 2px;
        }
        QSlider#nowPlayingProgress::handle:horizontal {
            width: 12px;
            height: 12px;
            background: %text%;
            border-radius: 6px;
            margin: -4px 0;
        }
        QSlider#nowPlayingProgress::handle:horizontal:hover {
            background: %highlight%;
        }
        QSlider#nowPlayingVolume::groove:horizontal {
            height: 4px;
            background: %border%;
            border-radius: 2px;
        }
        QSlider#nowPlayingVolume::handle:horizontal {
            width: 10px;
            height: 10px;
            background: %text_secondary%;
            border-radius: 5px;
            margin: -3px 0;
        }
        QLabel#nowPlayingTime {
            color: %text_secondary%;
            font-size: 12px;
            font-family: monospace;
        }
    """

    _STYLE_QUEUE_DIALOG = """
        QDialog {
            background-color: %background%;
            border: 1px solid %border%;
            border-radius: 10px;
        }
        QPushButton#queueDialogClose {
            background: transparent;
            border: none;
            color: %text_secondary%;
            border-radius: 12px;
            padding: 4px;
        }
        QPushButton#queueDialogClose:hover {
            background-color: %selection%;
            color: %text%;
        }
        QListWidget {
            background-color: %background%;
            border: none;
            color: %text%;
            outline: none;
        }
        QListWidget::item {
            padding: 10px 12px;
            border-bottom: 1px dashed %border%;
        }
        QListWidget::item:selected {
            background-color: %selection%;
            color: %text%;
        }
    """

    def __init__(self, playback: PlaybackService, parent=None):
        super().__init__(parent)
        from app import Bootstrap

        self._playback = playback
        self._config = Bootstrap.instance().config
        self._cover_load_version = 0
        self._current_cover_path = ""
        self._lyrics_thread: Optional[LyricsLoader] = None
        self._cover_thread: Optional[threading.Thread] = None
        self._current_duration = 0.0
        self._is_seeking = False
        self._previous_volume = 70
        self._dragging = False
        self._drag_start_pos = None
        self._drag_window_pos = None
        self._shortcuts: list[QShortcut] = []
        self._cover_mode = "square"  # square | circle_rotate
        self._cover_angle = 0.0
        self._cover_source_pixmap: Optional[QPixmap] = None
        self._runtime_signals_connected = False
        self._cover_anim_timer = QTimer(self)
        self._cover_anim_timer.setInterval(33)
        self._cover_anim_timer.timeout.connect(self._update_cover_rotation)

        self._setup_ui()
        self._restore_window_settings()
        self._setup_connections()

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        self._cover_loaded.connect(self._on_cover_loaded)
        self._initialize_from_current_track()

        self._resize_grip = QSizeGrip(self)
        self._resize_grip.setFixedSize(16, 16)
        self._resize_grip.setStyleSheet("background: transparent;")
        self._resize_grip.raise_()

    def _setup_ui(self):
        """Build now playing layout."""
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        self.setObjectName("nowPlayingRoot")
        self.setWindowTitle(t("app_title"))
        self.setMinimumSize(1000, 650)
        self.resize(1300, 820)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(12)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)

        self._track_title = QLabel(t("not_playing"))
        self._track_title.setObjectName("nowPlayingTitle")
        header.addWidget(self._track_title, 1)

        self._max_btn = QPushButton()
        self._max_btn.setObjectName("nowPlayingMaximize")
        self._max_btn.setFixedSize(34, 34)
        self._max_btn.setIcon(get_icon(IconName.MAXIMIZE, None))
        self._max_btn.setIconSize(QSize(16, 16))
        self._max_btn.setCursor(Qt.PointingHandCursor)
        header.addWidget(self._max_btn)

        self._close_btn = QPushButton()
        self._close_btn.setObjectName("nowPlayingClose")
        self._close_btn.setFixedSize(34, 34)
        self._close_btn.setIcon(get_icon(IconName.TIMES, None))
        self._close_btn.setIconSize(QSize(18, 18))
        self._close_btn.setCursor(Qt.PointingHandCursor)
        header.addWidget(self._close_btn)
        root.addLayout(header)

        self._track_album = QLabel("")
        self._track_album.setObjectName("nowPlayingAlbum")
        root.addWidget(self._track_album)

        self._track_artist = QLabel("")
        self._track_artist.setObjectName("nowPlayingArtist")
        root.addWidget(self._track_artist)

        body = QHBoxLayout()
        body.setContentsMargins(0, 6, 0, 0)
        body.setSpacing(6)
        body.addStretch(1)

        self._cover_label = QLabel()
        self._cover_label.setObjectName("nowPlayingCover")
        self._cover_label.setMinimumSize(420, 420)
        self._cover_label.setMaximumSize(560, 560)
        self._cover_label.setAlignment(Qt.AlignCenter)
        self._cover_label.setCursor(Qt.PointingHandCursor)
        self._cover_label.installEventFilter(self)
        self._cover_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        body.addWidget(self._cover_label, 0, Qt.AlignVCenter)
        self._apply_cover_mode_style()

        self._lyrics_widget = LyricsWidget()
        self._lyrics_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        body.addWidget(self._lyrics_widget, 3)
        body.addStretch(0)

        root.addLayout(body, 1)

        # Reuse main PlayerControls and hide the left info/cover section.
        self._player_controls = PlayerControls(self._playback, self, instance_name="now-playing")
        self._player_controls.setFixedHeight(116)
        self._player_controls.set_info_placeholder_width(180)
        self._player_controls.set_sleep_timer_visible(False)
        self._player_controls.set_queue_placement("progress")
        self._player_controls.set_queue_visible(True)
        root.addWidget(self._player_controls)

        # Keep backward-compatible attribute references used by existing logic.
        self._progress_slider = self._player_controls._progress_slider
        self._current_time = self._player_controls._current_time_label
        self._total_time = self._player_controls._total_time_label
        self._favorite_btn = self._player_controls._favorite_btn
        self._shuffle_btn = self._player_controls._shuffle_btn
        self._play_pause_btn = self._player_controls._play_pause_btn
        self._prev_btn = self._player_controls._prev_btn
        self._next_btn = self._player_controls._next_btn
        self._repeat_btn = self._player_controls._repeat_btn
        self._queue_btn = self._player_controls._queue_btn
        self._volume_btn = self._player_controls._volume_btn
        self._volume_slider = self._player_controls._volume_slider

        # Emphasize play/pause in now-playing mode.
        self._play_pause_btn.setObjectName("nowPlayingPrimaryBtn")
        self._play_pause_btn.setFixedSize(48, 48)
        self._play_pause_btn.setIconSize(QSize(32, 32))

        self._set_default_cover()
        self.refresh_theme()

    def _setup_connections(self):
        """Connect playback and widget signals."""
        self._close_btn.clicked.connect(self.close)
        self._max_btn.clicked.connect(self._toggle_maximized)
        self._lyrics_widget.seekRequested.connect(self._playback.seek)
        self._setup_shortcuts()
        self._player_controls.queue_requested.connect(self._show_playlist_dialog)
        self._connect_runtime_signals()

    def _add_shortcut(self, key: str | int, callback):
        shortcut = QShortcut(QKeySequence(key), self)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _setup_shortcuts(self):
        """Now playing shortcuts (aligned with mini player behavior)."""
        self._add_shortcut(Qt.Key_Space, self._toggle_play_pause)
        self._add_shortcut("Ctrl+Left", self._playback.engine.play_previous)
        self._add_shortcut("Ctrl+Right", self._playback.engine.play_next)
        self._add_shortcut("Ctrl+Up", self._volume_up)
        self._add_shortcut("Ctrl+Down", self._volume_down)
        self._add_shortcut("Ctrl+F", self._toggle_favorite)
        self._add_shortcut("Ctrl+M", self._switch_to_mini_player)
        self._add_shortcut("Ctrl+P", self.close)
        self._add_shortcut("Ctrl+Q", self._quit_application)

    def _quit_application(self):
        parent = self.parent()
        if parent and hasattr(parent, "request_quit"):
            parent.request_quit()
            return
        if parent and hasattr(parent, "_quit_from_now_playing"):
            parent._quit_from_now_playing()
            return
        app = QApplication.instance()
        if app:
            app.quit()

    def _switch_to_mini_player(self):
        parent = self.parent()
        if parent and hasattr(parent, "_switch_now_playing_to_mini"):
            parent._switch_now_playing_to_mini()
            return
        self.close()

    def _initialize_from_current_track(self):
        """Sync initial state from playback engine."""
        current_track = self._playback.engine.current_track
        self._on_track_changed(current_track if current_track else None)
        if current_track:
            self._on_position_changed(self._playback.engine.position())
        duration_ms = self._playback.engine.duration()
        if duration_ms > 0:
            self._on_duration_changed(duration_ms)
        self._on_state_changed(self._playback.engine.state)
        self._sync_play_mode_buttons()
        self._on_volume_changed_from_engine(self._playback.engine.volume)

    def _on_track_changed(self, track_dict: dict):
        """Update cover/lyrics when track changes."""
        self._apply_track_info(track_dict, load_cover=True, load_lyrics=True)

    def _on_pending_track_changed(self, track_dict: dict):
        """Update lightweight track info while download is pending."""
        self._apply_track_info(track_dict, load_cover=False, load_lyrics=False)

    def _apply_track_info(self, track_dict: dict, load_cover: bool, load_lyrics: bool):
        """Apply track metadata and optionally trigger heavy loaders."""
        if not track_dict:
            self._current_duration = 0.0
            self._progress_slider.setValue(0)
            self._current_time.setText("0:00")
            self._total_time.setText("0:00")
            self._track_title.setText(t("not_playing"))
            self._track_artist.setText("")
            self._track_album.setText("")
            self._lyrics_widget.set_lyrics("")
            self._current_cover_path = ""
            self._set_default_cover()
            self.setWindowTitle(t("app_title"))
            return

        self._current_duration = 0.0
        self._progress_slider.setValue(0)
        self._current_time.setText("0:00")
        self._total_time.setText("0:00")

        title = track_dict.get("title", t("unknown"))
        artist = track_dict.get("artist", "")
        album = track_dict.get("album", "")
        self._track_title.setText(title)
        self._track_artist.setText(artist)
        self._track_album.setText(album if album else "")

        window_title = f"{title} - {artist}" if artist else title
        self._current_track_title = window_title
        self.setWindowTitle(window_title)

        if load_cover:
            self._load_cover_async(track_dict)
        else:
            self._current_cover_path = ""
            self._set_default_cover()

        if load_lyrics:
            self._load_lyrics_async(track_dict)
        else:
            self._lyrics_widget.set_lyrics("")

        self._update_favorite_state()

    def _on_position_changed(self, position_ms: int):
        """Sync lyric highlight position."""
        controls_seeking = bool(getattr(self._player_controls, "_is_seeking", False))
        if self._current_duration > 0 and not self._is_seeking and not controls_seeking:
            value = int((position_ms / (self._current_duration * 1000)) * 1000)
            self._progress_slider.setValue(value)
            self._current_time.setText(format_time(position_ms / 1000))
        self._lyrics_widget.update_position(position_ms / 1000)

    def _on_duration_changed(self, duration_ms: int):
        self._current_duration = duration_ms / 1000
        self._total_time.setText(format_time(self._current_duration))

    def _on_state_changed(self, state: PlaybackState):
        if state == PlaybackState.PLAYING:
            self._play_pause_btn.setIcon(get_icon(IconName.PAUSE, None, 32))
            self._update_cover_animation_state()
            if self._current_track_title:
                self.setWindowTitle(self._current_track_title)
        else:
            self._play_pause_btn.setIcon(get_icon(IconName.PLAY, None, 32))
            self._update_cover_animation_state()
            self.setWindowTitle(t("app_title"))

    def _toggle_play_pause(self):
        if self._playback.engine.state == PlaybackState.PLAYING:
            self._playback.engine.pause()
        else:
            self._playback.engine.play()

    def _on_seek_start(self):
        self._is_seeking = True

    def _on_seek_end(self):
        if self._current_duration > 0:
            position_ms = int((self._progress_slider.value() / 1000) * self._current_duration * 1000)
            self._playback.engine.seek(position_ms)
        self._is_seeking = False

    def _on_seek_value_changed(self, value: int):
        if self._is_seeking and self._current_duration > 0:
            position_s = (value / 1000) * self._current_duration
            self._current_time.setText(format_time(position_s))

    def _on_slider_clicked(self, value: int):
        if self._current_duration > 0:
            position_ms = int((value / 1000) * self._current_duration * 1000)
            self._playback.engine.seek(position_ms)

    def _on_volume_changed(self, value: int):
        self._playback.engine.set_volume(value)
        self._update_volume_button(value)

    def _on_volume_changed_from_engine(self, value: int):
        self._volume_slider.blockSignals(True)
        self._volume_slider.setValue(value)
        self._volume_slider.blockSignals(False)
        self._update_volume_button(value)

    def _update_volume_button(self, value: int):
        if value == 0:
            icon = IconName.VOLUME_OFF
        elif value < 50:
            icon = IconName.VOLUME_LOW
        else:
            icon = IconName.VOLUME_HIGH
        self._volume_btn.setIcon(get_icon(icon, None, 20))

    def _toggle_mute(self):
        current = self._volume_slider.value()
        if current > 0:
            self._previous_volume = current
            self._volume_slider.setValue(0)
        else:
            self._volume_slider.setValue(self._previous_volume or 70)

    def _volume_up(self):
        current = self._playback.engine.volume
        self._playback.engine.set_volume(min(100, current + 5))

    def _volume_down(self):
        current = self._playback.engine.volume
        self._playback.engine.set_volume(max(0, current - 5))

    def _toggle_favorite(self):
        self._playback.toggle_favorite()

    def _update_favorite_state(self):
        track = self._playback.engine.current_track
        if not track:
            self._set_favorite_icon(False)
            return
        is_fav = self._playback.is_favorite(track.get("id"), track.get("cloud_file_id"))
        self._set_favorite_icon(is_fav)

    def _on_favorite_changed(self, item_id, is_favorite: bool, is_cloud: bool = False):
        track = self._playback.engine.current_track
        if not track:
            return
        if track.get("id") == item_id or (is_cloud and track.get("cloud_file_id") == item_id):
            self._set_favorite_icon(is_favorite)

    def _set_favorite_icon(self, is_favorite: bool):
        """Set favorite icon style consistent with player controls."""
        if is_favorite:
            self._favorite_btn.setIcon(get_icon(IconName.STAR_FILLED, "#ff4444", 20))
        else:
            from system.theme import ThemeManager
            outline_color = ThemeManager.instance().current_theme.text_secondary
            self._favorite_btn.setIcon(get_icon(IconName.STAR_OUTLINE, outline_color, 20))

    def _on_play_mode_changed(self, mode: PlayMode):
        self._sync_play_mode_buttons()

    def _sync_play_mode_buttons(self):
        mode = self._playback.engine.play_mode

        shuffle_on = mode in (PlayMode.RANDOM, PlayMode.RANDOM_LOOP, PlayMode.RANDOM_TRACK_LOOP)
        self._shuffle_btn.setChecked(shuffle_on)
        self._shuffle_btn.setProperty("active", shuffle_on)
        self._shuffle_btn.style().unpolish(self._shuffle_btn)
        self._shuffle_btn.style().polish(self._shuffle_btn)

        repeat_on = mode in (PlayMode.PLAYLIST_LOOP, PlayMode.RANDOM_LOOP, PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP)
        self._repeat_btn.setChecked(repeat_on)
        self._repeat_btn.setProperty("active", repeat_on)
        self._repeat_btn.style().unpolish(self._repeat_btn)
        self._repeat_btn.style().polish(self._repeat_btn)

        if mode in (PlayMode.LOOP, PlayMode.RANDOM_TRACK_LOOP):
            self._repeat_btn.setIcon(get_icon(IconName.REPEAT_ONCE, None, 26))
        else:
            self._repeat_btn.setIcon(get_icon(IconName.REPEAT, None, 26))

    def _toggle_shuffle(self):
        mode = self._playback.engine.play_mode
        if self._shuffle_btn.isChecked():
            if mode == PlayMode.PLAYLIST_LOOP:
                self._playback.engine.set_play_mode(PlayMode.RANDOM_LOOP)
            elif mode == PlayMode.LOOP:
                self._playback.engine.set_play_mode(PlayMode.RANDOM_TRACK_LOOP)
            elif mode == PlayMode.SEQUENTIAL:
                self._playback.engine.set_play_mode(PlayMode.RANDOM)
        else:
            if mode == PlayMode.RANDOM_LOOP:
                self._playback.engine.set_play_mode(PlayMode.PLAYLIST_LOOP)
            elif mode == PlayMode.RANDOM_TRACK_LOOP:
                self._playback.engine.set_play_mode(PlayMode.LOOP)
            elif mode == PlayMode.RANDOM:
                self._playback.engine.set_play_mode(PlayMode.SEQUENTIAL)

    def _toggle_repeat(self):
        mode = self._playback.engine.play_mode
        if mode == PlayMode.SEQUENTIAL:
            self._playback.engine.set_play_mode(PlayMode.PLAYLIST_LOOP)
        elif mode == PlayMode.PLAYLIST_LOOP:
            self._playback.engine.set_play_mode(PlayMode.LOOP)
        elif mode == PlayMode.LOOP:
            self._playback.engine.set_play_mode(PlayMode.SEQUENTIAL)
        elif mode == PlayMode.RANDOM:
            self._playback.engine.set_play_mode(PlayMode.RANDOM_LOOP)
        elif mode == PlayMode.RANDOM_LOOP:
            self._playback.engine.set_play_mode(PlayMode.RANDOM_TRACK_LOOP)
        elif mode == PlayMode.RANDOM_TRACK_LOOP:
            self._playback.engine.set_play_mode(PlayMode.RANDOM)

    def _show_playlist_dialog(self):
        """Show current play queue."""
        dialog = QDialog(self)
        dialog.setWindowTitle("")
        dialog.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        dialog.resize(520, 620)
        from system.theme import ThemeManager
        dialog.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_QUEUE_DIALOG))

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)

        header = QHBoxLayout()
        header.addStretch()
        close_btn = QPushButton()
        close_btn.setObjectName("queueDialogClose")
        close_btn.setFixedSize(28, 28)
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setIcon(get_icon(IconName.TIMES, None, 16))
        close_btn.setIconSize(QSize(16, 16))
        close_btn.clicked.connect(dialog.reject)
        header.addWidget(close_btn)
        layout.addLayout(header)

        queue_list = QListWidget(dialog)
        queue_list.setCursor(Qt.PointingHandCursor)
        layout.addWidget(queue_list)

        items = self._playback.engine.playlist_items
        current_index = self._playback.engine.current_index

        for i, item in enumerate(items):
            title = item.title or t("unknown")
            artist = item.artist or ""
            text = f"{i + 1}. {title} - {artist}" if artist else f"{i + 1}. {title}"
            row = QListWidgetItem(text)
            row.setData(Qt.UserRole, i)
            row.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            queue_list.addItem(row)

        if 0 <= current_index < queue_list.count():
            queue_list.setCurrentRow(current_index)
            current_item = queue_list.item(current_index)
            if current_item:
                from system.theme import ThemeManager
                tm = ThemeManager.instance().current_theme
                current_item.setForeground(QColor(tm.highlight))
                font = current_item.font()
                font.setBold(True)
                current_item.setFont(font)
                # Defer scrolling until popup is visible; otherwise Qt may reset to top.
                QTimer.singleShot(
                    0,
                    lambda item=current_item: queue_list.scrollToItem(
                        item, QListWidget.PositionAtCenter
                    ),
                )

        def _play_selected(selected_item: QListWidgetItem):
            index = selected_item.data(Qt.UserRole)
            if isinstance(index, int):
                self._playback.engine.play_at(index)
            dialog.accept()

        queue_list.itemDoubleClicked.connect(_play_selected)
        dialog.exec()
        dialog.deleteLater()

    def _load_cover_async(self, track_dict: dict):
        """Load current track cover in worker thread."""
        self._cover_load_version += 1
        version = self._cover_load_version

        def load_cover() -> str:
            return CoverLoader.resolve_track_cover_path(
                track_dict,
                getattr(self._playback, "cover_service", None),
                self._playback.get_track_cover,
                logger,
            )

        def worker():
            self._cover_loaded.emit(load_cover(), version)

        self._cover_thread = threading.Thread(target=worker, daemon=True)
        self._cover_thread.start()

    def _on_cover_loaded(self, cover_path: str, version: int):
        """Apply cover if result is still current."""
        if version != self._cover_load_version:
            return
        self._cover_thread = None
        self._current_cover_path = cover_path
        if not cover_path:
            self._set_default_cover()
            return
        pixmap = CoverLoader.load_pixmap(cover_path)
        if pixmap is None:
            self._set_default_cover()
            return
        self._cover_source_pixmap = pixmap
        self._cover_angle = 0.0
        self._render_cover()

    def _invalidate_cover_load(self):
        """Invalidate pending cover worker results and clear thread reference."""
        self._cover_load_version += 1
        self._cover_thread = None

    def _connect_runtime_signals(self):
        """Connect engine and event-bus signals owned by this window once."""
        if getattr(self, "_runtime_signals_connected", False):
            return

        engine = getattr(self._playback, "engine", None)
        if engine is None:
            return

        engine.current_track_changed.connect(self._on_track_changed)
        engine.current_track_pending.connect(self._on_pending_track_changed)
        engine.position_changed.connect(self._on_position_changed)
        engine.duration_changed.connect(self._on_duration_changed)
        engine.state_changed.connect(self._on_state_changed)
        engine.play_mode_changed.connect(self._on_play_mode_changed)
        engine.volume_changed.connect(self._on_volume_changed_from_engine)

        EventBus.instance().favorite_changed.connect(self._on_favorite_changed)
        self._runtime_signals_connected = True

    def _disconnect_runtime_signals(self):
        """Disconnect engine and event-bus signals owned by this window."""
        if not getattr(self, "_runtime_signals_connected", False):
            return

        engine = getattr(self._playback, "engine", None)
        if engine is not None:
            with suppress(Exception):
                engine.current_track_changed.disconnect(self._on_track_changed)
            with suppress(Exception):
                engine.current_track_pending.disconnect(self._on_pending_track_changed)
            with suppress(Exception):
                engine.position_changed.disconnect(self._on_position_changed)
            with suppress(Exception):
                engine.duration_changed.disconnect(self._on_duration_changed)
            with suppress(Exception):
                engine.state_changed.disconnect(self._on_state_changed)
            with suppress(Exception):
                engine.play_mode_changed.disconnect(self._on_play_mode_changed)
            with suppress(Exception):
                engine.volume_changed.disconnect(self._on_volume_changed_from_engine)

        with suppress(Exception):
            EventBus.instance().favorite_changed.disconnect(self._on_favorite_changed)
        self._runtime_signals_connected = False

    def _set_default_cover(self):
        """Set fallback cover when missing."""
        width = max(420, self._cover_label.width() or 420)
        height = max(420, self._cover_label.height() or 420)
        pixmap = QPixmap(width, height)
        pixmap.fill(QColor("#303030"))
        self._cover_source_pixmap = pixmap
        self._render_cover()

    def _render_cover(self):
        """Render current cover according to display mode."""
        if not self._cover_source_pixmap or self._cover_source_pixmap.isNull():
            return

        target_size = self._cover_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        if self._cover_mode == "square":
            rendered = self._cover_source_pixmap.scaled(
                target_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._cover_label.setPixmap(rendered)
            return

        # circle_rotate mode
        diameter = min(target_size.width(), target_size.height())
        square = self._cover_source_pixmap.scaled(
            diameter,
            diameter,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation,
        )

        circle_pm = QPixmap(diameter, diameter)
        circle_pm.fill(Qt.transparent)
        painter = QPainter(circle_pm)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        path = QPainterPath()
        path.addEllipse(0, 0, diameter, diameter)
        painter.setClipPath(path)
        painter.translate(diameter / 2, diameter / 2)
        painter.rotate(self._cover_angle)
        painter.drawPixmap(-diameter / 2, -diameter / 2, square)
        painter.end()

        self._cover_label.setPixmap(circle_pm)

    def _update_cover_animation_state(self):
        """Start/stop cover animation based on mode and playback state."""
        should_rotate = self._cover_mode == "circle_rotate" and self._playback.engine.state == PlaybackState.PLAYING
        if should_rotate and not self._cover_anim_timer.isActive():
            self._cover_anim_timer.start()
        elif not should_rotate and self._cover_anim_timer.isActive():
            self._cover_anim_timer.stop()

    def _update_cover_rotation(self):
        """Advance rotation animation frame."""
        self._cover_angle = (self._cover_angle + 1.0) % 360.0
        self._render_cover()

    def _toggle_cover_mode(self):
        """Switch between square static and circular rotating cover."""
        if self._cover_mode == "square":
            self._cover_mode = "circle_rotate"
        else:
            self._cover_mode = "square"
        self._apply_cover_mode_style()
        self._update_cover_animation_state()
        self._render_cover()

    def _apply_cover_mode_style(self):
        """Update cover container style based on current mode."""
        is_circle = self._cover_mode == "circle_rotate"
        self._cover_label.setProperty("circleMode", is_circle)
        self._cover_label.style().unpolish(self._cover_label)
        self._cover_label.style().polish(self._cover_label)

    def _stop_lyrics_thread(self, wait_ms: int = 1000, cleanup_signals: bool = False):
        """Stop current lyrics loader thread cooperatively."""
        thread = getattr(self, "_lyrics_thread", None)
        if not thread or not isValid(thread):
            self._lyrics_thread = None
            return

        if isValid(thread) and thread.isRunning():
            thread.requestInterruption()
            thread.quit()
            if not thread.wait(wait_ms):
                logger.warning("[NowPlayingWindow] Lyrics thread did not stop in time")

        if cleanup_signals:
            for signal_name in ("finished", "lyrics_ready"):
                signal = getattr(thread, signal_name, None)
                if signal is not None:
                    with suppress(RuntimeError):
                        signal.disconnect()
            thread.deleteLater()
            self._lyrics_thread = None

    def _load_lyrics_async(self, track_dict: dict):
        """Load lyrics using existing LyricsLoader."""
        self._stop_lyrics_thread(wait_ms=500, cleanup_signals=True)

        path = track_dict.get("path", "")
        title = track_dict.get("title", "")
        artist = track_dict.get("artist", "")
        source = track_dict.get("source", "") or track_dict.get("source_type", "")
        cloud_file_id = track_dict.get("cloud_file_id", "")
        provider_id = track_dict.get("online_provider_id")
        is_online = source in ("online", "ONLINE")

        self._lyrics_thread = LyricsLoader(
            path,
            title,
            artist,
            song_mid=cloud_file_id,
            is_online=is_online,
            provider_id=provider_id,
        )
        self._lyrics_thread.lyrics_ready.connect(self._on_lyrics_ready)
        self._lyrics_thread.finished.connect(self._on_lyrics_thread_finished)
        self._lyrics_thread.start()

    def _on_lyrics_ready(self, lyrics: str):
        """Apply loaded lyrics to widget."""
        self._lyrics_widget.set_lyrics(lyrics or "")

    def _on_lyrics_thread_finished(self):
        sender = self.sender()
        if sender and sender == self._lyrics_thread:
            self._lyrics_thread = None

    def keyPressEvent(self, event):
        """Esc closes now playing view."""
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 72 and not self.isMaximized():
            self._dragging = True
            self._drag_start_pos = event.globalPosition().toPoint()
            self._drag_window_pos = self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging and self._drag_start_pos is not None and self._drag_window_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_start_pos
            self.move(self._drag_window_pos + delta)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
            self._drag_start_pos = None
            self._drag_window_pos = None
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and event.position().y() <= 72:
            self._toggle_maximized()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, obj, event):
        if (
            obj == self._cover_label
            and event.type() == QEvent.MouseButtonPress
            and event.button() == Qt.LeftButton
        ):
            self._toggle_cover_mode()
            return True
        return super().eventFilter(obj, event)

    def _toggle_maximized(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._sync_maximize_button_icon()

    def _sync_maximize_button_icon(self):
        icon = IconName.MINIMIZE if self.isMaximized() else IconName.MAXIMIZE
        self._max_btn.setIcon(get_icon(icon, None))

    def _restore_window_settings(self):
        geometry = self._config.get_now_playing_geometry()
        if geometry:
            self.restoreGeometry(geometry)

        if self._config.get_now_playing_maximized():
            self.showMaximized()

        self._sync_maximize_button_icon()

    def _save_window_settings(self):
        self._config.set_now_playing_geometry(bytes(self.saveGeometry()))
        self._config.set_now_playing_maximized(self.isMaximized())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_resize_grip") and self._resize_grip:
            self._resize_grip.move(self.width() - 16, self.height() - 16)
        self._render_cover()

    def showEvent(self, event):
        """Reconnect runtime subscriptions when the hidden window is shown again."""
        was_connected = getattr(self, "_runtime_signals_connected", False)
        self._connect_runtime_signals()
        if not was_connected:
            self._initialize_from_current_track()
        super().showEvent(event)

    def closeEvent(self, event):
        """Cleanup and notify main window to restore."""
        self._save_window_settings()
        self._invalidate_cover_load()
        self._disconnect_runtime_signals()

        self._stop_lyrics_thread(wait_ms=800, cleanup_signals=True)

        self.closed.emit()
        event.accept()

    def refresh_theme(self):
        """Apply theme tokens."""
        from system.theme import ThemeManager
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_WINDOW))
        self._apply_cover_mode_style()

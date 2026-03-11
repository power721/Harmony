"""
Queue view for managing the current playback queue.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QMenu,
    QAbstractItemView,
    QInputDialog,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QAction, QColor, QBrush
from typing import List

from player import PlayerController
from player.engine import PlayerState
from utils import format_duration, t


class QueueView(QWidget):
    """View for managing the current playback queue."""

    play_track = Signal(int)

    def __init__(self, player: PlayerController, db_manager=None, parent=None):
        """
        Initialize queue view.

        Args:
            player: Player controller
            db_manager: Database manager
            parent: Parent widget
        """
        super().__init__(parent)
        self._player = player
        self._db = db_manager if db_manager else player._db
        self._setup_ui()
        self._setup_connections()

        # Load initial queue content and update indicators
        from PySide6.QtCore import QTimer

        QTimer.singleShot(0, self._initialize_view)

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(10)

        # Header
        header = QWidget()
        header.setObjectName("queueHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 10, 0, 10)
        header_layout.setSpacing(10)

        self._title_label = QLabel(t("play_queue"))
        self._title_label.setObjectName("queueTitle")
        self._title_label.setStyleSheet("""
            QLabel#queueTitle {
                color: #1db954;
                font-size: 28px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Clear button
        self._clear_btn = QPushButton(t("clear_queue"))
        self._clear_btn.setObjectName("queueActionBtn")
        self._clear_btn.setCursor(Qt.PointingHandCursor)
        self._clear_btn.clicked.connect(self._clear_queue)
        header_layout.addWidget(self._clear_btn)

        layout.addWidget(header)

        # Queue list
        self._queue_list = QListWidget()
        self._queue_list.setObjectName("queueList")
        self._queue_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._queue_list.setAlternatingRowColors(True)
        self._queue_list.setDragDropMode(QAbstractItemView.InternalMove)
        self._queue_list.model().rowsMoved.connect(self._on_rows_moved)
        self._queue_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._queue_list.customContextMenuRequested.connect(self._show_context_menu)
        self._queue_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self._queue_list)

        # Status bar
        self._status_label = QLabel(f"0 {t('tracks_in_queue')}")
        self._status_label.setStyleSheet("color: #808080; font-size: 13px;")
        layout.addWidget(self._status_label)

        # Add track hint
        self._hint_label = QLabel(t("tip_right_click"))
        self._hint_label.setStyleSheet("color: #606060; font-size: 11px;")
        layout.addWidget(self._hint_label)

        # Apply modern styles
        self.setStyleSheet("""
            QWidget#queueHeader {
                background-color: #141414;
            }
            QPushButton#queueActionBtn {
                background: transparent;
                border: 2px solid #404040;
                color: #c0c0c0;
                padding: 6px 14px;
                border-radius: 6px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#queueActionBtn:hover {
                border-color: #1db954;
                color: #1db954;
                background-color: rgba(29, 185, 84, 0.1);
            }
            QListWidget#queueList {
                background-color: #1e1e1e;
                border: none;
                outline: none;
                border-radius: 8px;
            }
            QListWidget#queueList::item {
                padding: 14px 18px;
                color: #e0e0e0;
                border-bottom: 1px solid #2a2a2a;
                margin: 1px 0px;
                background-color: #1e1e1e;
            }
            /* Alternating row colors */
            QListWidget#queueList::item:alternate {
                background-color: #252525;
            }
            QListWidget#queueList::item:!alternate {
                background-color: #1e1e1e;
            }
            QListWidget#queueList::item:selected {
                background-color: #1db954;
                color: #000000;
                font-weight: bold;
            }
            QListWidget#queueList::item:selected:!alternate {
                background-color: #1db954;
            }
            QListWidget#queueList::item:selected:alternate {
                background-color: #1ed760;
            }
            QListWidget#queueList::item:hover {
                background-color: #2d2d2d;
                color: #1db954;
            }
            QListWidget#queueList::item:selected:hover {
                background-color: #1ed760;
            }
            QListWidget#queueList::item[current] {
                background-color: #1db954;
                color: #000000;
                font-weight: bold;
                border-left: 4px solid #000000;
            }
            QListWidget QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
            }
            QListWidget QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QListWidget QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
        """)

    def _setup_connections(self):
        """Setup signal connections."""
        # Connect to engine signals to update current track indicator
        self._player.engine.current_track_changed.connect(
            self._on_current_track_changed
        )
        self._player.engine.state_changed.connect(self._on_player_state_changed)
        self._player.engine.playlist_changed.connect(self._refresh_queue)

        # Track playlist size to detect playlist changes
        self._last_playlist_size = 0

    def _initialize_view(self):
        """Initialize the queue view with current content and indicators."""
        # Get current playlist from engine
        playlist = self._player.engine.playlist
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlayerState.PLAYING

        # Update last known playlist size
        self._last_playlist_size = len(playlist)

        # Save current selection
        selected_items = self._queue_list.selectedItems()
        selected_indices = [self._queue_list.row(item) for item in selected_items]

        # Block signals to prevent feedback
        self._queue_list.blockSignals(True)

        # Clear and repopulate
        self._queue_list.clear()

        for i, track in enumerate(playlist):
            title = track.get("title", t("unknown"))
            artist = track.get("artist", t("unknown"))

            # Add play/pause icon for current track
            if i == current_index:
                icon = "▶️ " if is_playing else "⏸️ "
                item_text = f"{i + 1}. {icon}{title} - {artist}"
            else:
                item_text = f"{i + 1}. {title} - {artist}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, track)

            # Set default text color
            item.setForeground(QBrush(QColor("#e0e0e0")))

            # Highlight current track
            if i == current_index:
                item.setData(Qt.UserRole + 1, True)  # Mark as current
                item.setBackground(QColor("#1db954"))
                item.setForeground(QBrush(QColor("#000000")))

            self._queue_list.addItem(item)

        # Restore selection
        for row in selected_indices:
            if row < self._queue_list.count():
                self._queue_list.item(row).setSelected(True)

        self._queue_list.blockSignals(False)

        # Update status
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

        # Scroll to current track after a delay
        QTimer.singleShot(100, self._scroll_to_current_track)

    def refresh_queue(self):
        """Refresh the queue display (can be called externally)."""
        self._refresh_queue()

    def _refresh_queue(self):
        """Refresh the queue display."""
        # Update UI texts
        self._update_ui_texts()

        # Get current playlist from engine
        playlist = self._player.engine.playlist
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlayerState.PLAYING

        # Save current selection
        selected_items = self._queue_list.selectedItems()
        selected_indices = [self._queue_list.row(item) for item in selected_items]

        # Block signals to prevent feedback
        self._queue_list.blockSignals(True)

        # Clear and repopulate
        self._queue_list.clear()

        for i, track in enumerate(playlist):
            title = track.get("title", t("unknown"))
            artist = track.get("artist", t("unknown"))

            # Add play/pause icon for current track
            if i == current_index:
                icon = "▶️ " if is_playing else "⏸️ "
                item_text = f"{i + 1}. {icon}{title} - {artist}"
            else:
                item_text = f"{i + 1}. {title} - {artist}"

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, track)

            # Set default text color
            item.setForeground(QBrush(QColor("#e0e0e0")))

            # Highlight current track
            if i == current_index:
                item.setData(Qt.UserRole + 1, True)  # Mark as current
                item.setBackground(QColor("#1db954"))
                item.setForeground(QBrush(QColor("#000000")))

            self._queue_list.addItem(item)

        # Restore selection
        for row in selected_indices:
            if row < self._queue_list.count():
                self._queue_list.item(row).setSelected(True)

        self._queue_list.blockSignals(False)

        # Update current track styling
        self._update_current_track_indicator()

        # Scroll to current track after a short delay
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._scroll_to_current_track)

        # Update status
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

    def _update_ui_texts(self):
        """Update UI texts after language change."""
        # Update title
        self._title_label.setText(t("play_queue"))

        # Update clear button
        self._clear_btn.setText(t("clear_queue"))

        # Update status
        playlist = self._player.engine.playlist
        self._status_label.setText(f"{len(playlist)} {t('tracks_in_queue')}")

        # Update hint
        self._hint_label.setText(t("tip_right_click"))

    def _update_current_track_indicator(self):
        """Update the visual indicator for current track."""
        current_index = self._player.engine.current_index
        is_playing = self._player.engine.state == PlayerState.PLAYING

        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            track = item.data(Qt.UserRole)

            if i == current_index:
                item.setBackground(QColor("#1db954"))
                item.setForeground(QColor("#000000"))

                # Update the text with play/pause icon
                if track and isinstance(track, dict):
                    title = track.get("title", "Unknown")
                    artist = track.get("artist", "Unknown")
                    icon = "▶️ " if is_playing else "⏸️ "
                    item_text = f"{i + 1}. {icon}{title} - {artist}"
                    item.setText(item_text)
            else:
                item.setBackground(Qt.transparent)
                item.setForeground(QColor("#e0e0e0"))

                # Remove icon if it was previously added
                if track and isinstance(track, dict):
                    title = track.get("title", "Unknown")
                    artist = track.get("artist", "Unknown")
                    # Check if text has icon and remove it
                    current_text = item.text()
                    if "▶️ " in current_text or "⏸️ " in current_text:
                        item_text = f"{i + 1}. {title} - {artist}"
                        item.setText(item_text)

    def _on_current_track_changed(self, track_dict):
        """Handle current track change."""
        # Check if playlist size changed (indicates new playlist loaded)
        current_size = len(self._player.engine.playlist)
        if current_size != self._last_playlist_size:
            self._last_playlist_size = current_size
            self._refresh_queue()
        else:
            self._update_current_track_indicator()

        # Scroll to current track with delay to ensure UI is updated
        from PySide6.QtCore import QTimer

        QTimer.singleShot(100, self._scroll_to_current_track)

    def _scroll_to_current_track(self):
        """Scroll to the current playing track."""
        current_index = self._player.engine.current_index
        if 0 <= current_index < self._queue_list.count():
            item = self._queue_list.item(current_index)
            if item:
                self._queue_list.scrollToItem(item, QListWidget.PositionAtCenter)

    def _select_track_by_id(self, track_id: int):
        """
        Select a track by its ID.

        Args:
            track_id: Track ID to select
        """
        # Find the item with the track
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            if item:
                track = item.data(Qt.UserRole)
                if track and isinstance(track, dict):
                    item_track_id = track.get("id")
                    if item_track_id == track_id:
                        # Clear previous selection
                        self._queue_list.clearSelection()
                        # Select the item
                        item.setSelected(True)
                        break

    def _on_player_state_changed(self, state: PlayerState):
        """Handle player state change (play/pause)."""
        # Update the play/pause icon
        self._update_current_track_indicator()

    def _on_rows_moved(self):
        """Handle row move (drag and drop reorder)."""
        # Build new playlist from current list order
        new_playlist = []
        for i in range(self._queue_list.count()):
            item = self._queue_list.item(i)
            track = item.data(Qt.UserRole)
            if track:
                new_playlist.append(track)

        # Update engine playlist
        self._player.engine.load_playlist(new_playlist)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Handle item double click."""
        track = item.data(Qt.UserRole)
        if track:
            track_id = track.get("id")
            if track_id:
                self.play_track.emit(track_id)

    def _clear_queue(self):
        """Clear the queue."""
        reply = QMessageBox.question(
            self,
            t("clear_queue"),
            t("clear_queue_confirm"),
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._player.engine.clear_playlist()

    def _remove_selected(self):
        """Remove selected tracks from queue."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        # Get indices in reverse order to remove from back to front
        rows_to_remove = sorted(
            [self._queue_list.row(item) for item in selected_items], reverse=True
        )

        # Block list widget signals during removal to prevent feedback
        self._queue_list.blockSignals(True)

        # Remove from engine playlist
        for row in rows_to_remove:
            self._player.engine.remove_track(row)

        # Unblock signals
        self._queue_list.blockSignals(False)

        # Refresh the queue display (will be called automatically by playlist_changed signal,
        # but we also call it here to ensure immediate update)
        self._refresh_queue()

    def _play_selected(self):
        """Play the selected track."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        # Play the first selected track
        item = selected_items[0]
        track = item.data(Qt.UserRole)
        if track:
            row = self._queue_list.row(item)
            self._player.engine.play_at(row)

    def _toggle_favorite_selected(self):
        """Toggle favorite status for selected tracks."""
        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            track = item.data(Qt.UserRole)
            if track and isinstance(track, dict):
                track_id = track.get("id")
                if track_id:
                    track_ids.append(track_id)

        if not track_ids:
            return

        added_count = 0
        removed_count = 0
        for track_id in track_ids:
            if self._db.is_favorite(track_id):
                self._db.remove_favorite(track_id)
                removed_count += 1
            else:
                self._db.add_favorite(track_id)
                added_count += 1

        if added_count > 0 and removed_count == 0:
            from utils import format_count_message
            message = format_count_message("added_x_tracks_to_favorites", added_count)
            QMessageBox.information(
                self,
                t("added_to_favorites"),
                message,
            )
        elif removed_count > 0 and added_count == 0:
            from utils import format_count_message
            message = format_count_message("removed_x_tracks_from_favorites", removed_count)
            QMessageBox.information(
                self,
                t("removed_from_favorites"),
                message,
            )
        else:
            message = t("added_x_removed_y").format(added=added_count, removed=removed_count)
            QMessageBox.information(
                self,
                t("updated_favorites"),
                message,
            )

    def _show_context_menu(self, pos):
        """Show context menu."""
        item = self._queue_list.itemAt(pos)
        if not item:
            return

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

        # Play action
        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(self._play_selected)

        menu.addSeparator()

        remove_action = menu.addAction(t("remove_from_queue"))
        remove_action.triggered.connect(self._remove_selected)

        menu.exec_(self._queue_list.mapToGlobal(pos))

    def add_tracks(self, track_ids: List[int]):
        """
        Add tracks to the queue.

        Args:
            track_ids: List of track IDs to add
        """
        from database import DatabaseManager, Track

        db = DatabaseManager()

        for track_id in track_ids:
            track = db.get_track(track_id)
            if track:
                from pathlib import Path

                if Path(track.path).exists():
                    track_dict = {
                        "id": track.id,
                        "path": track.path,
                        "title": track.title,
                        "artist": track.artist,
                        "album": track.album,
                        "duration": track.duration,
                    }
                    self._player.engine.add_track(track_dict)

        db.close()

    def closeEvent(self, event):
        """Handle close event."""
        event.accept()

    def showEvent(self, event):
        """Handle show event - refresh queue when view becomes visible."""
        super().showEvent(event)
        # Refresh queue content and update indicators when the view becomes visible
        from PySide6.QtCore import QTimer

        QTimer.singleShot(50, self._initialize_view)

    def _edit_media_info(self):
        """Edit media information for selected track."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QFormLayout,
            QLabel,
            QLineEdit,
            QDialogButtonBox,
        )
        from services import MetadataService

        selected_items = self._queue_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        track = item.data(Qt.UserRole)

        if not track or not isinstance(track, dict):
            return

        track_id = track.get("id")
        if not track_id:
            return

        track = self._db.get_track(track_id)
        if not track:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(t("edit_media_info_title"))
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet("""
            QDialog { background-color: #282828; color: #ffffff; }
            QLabel { color: #ffffff; font-size: 13px; }
            QLineEdit {
                background-color: #181818;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #1db954; }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1ed760; }
            QPushButton[role="cancel"] { background-color: #404040; color: #ffffff; }
            QPushButton[role="cancel"]:hover { background-color: #505050; }
        """)

        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        title_input = QLineEdit(track.title or "")
        title_input.setPlaceholderText(t("enter_title"))
        artist_input = QLineEdit(track.artist or "")
        artist_input.setPlaceholderText(t("enter_artist"))
        album_input = QLineEdit(track.album or "")
        album_input.setPlaceholderText(t("enter_album"))

        path_label = QLabel(track.path)
        path_label.setStyleSheet("color: #808080; font-size: 11px;")
        path_label.setWordWrap(True)

        form_layout.addRow(t("title") + ":", title_input)
        form_layout.addRow(t("artist") + ":", artist_input)
        form_layout.addRow(t("album") + ":", album_input)
        form_layout.addRow(t("file") + ":", path_label)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox()
        ok_button = QPushButton(t("save"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(buttons)

        def save_changes():
            new_title = title_input.text().strip() or track.title
            new_artist = artist_input.text().strip() or track.artist
            new_album = album_input.text().strip() or track.album

            success = MetadataService.save_metadata(
                track.path, title=new_title, artist=new_artist, album=new_album
            )

            if success:
                self._db.update_track(
                    track_id, title=new_title, artist=new_artist, album=new_album
                )
                QMessageBox.information(self, t("success"), t("media_saved"))
                self.refresh()
            else:
                QMessageBox.warning(self, "Error", t("media_save_failed"))

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

    def refresh(self):
        """Refresh the queue display."""
        self._refresh_queue()

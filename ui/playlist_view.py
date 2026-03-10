"""
Playlist view widget for managing playlists.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QInputDialog,
    QMessageBox,
    QSplitter,
    QLabel,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QAction, QBrush, QColor
from typing import List, Optional

from database import DatabaseManager, Track, Playlist
from player import PlayerController
from utils import format_duration, t


class PlaylistView(QWidget):
    """Playlist view for managing playlists."""

    track_double_clicked = Signal(int)  # Signal when track is double-clicked (from library view, plays all)
    playlist_track_double_clicked = Signal(int, int)  # Signal when playlist track is double-clicked (playlist_id, track_id)

    def __init__(
        self, db_manager: DatabaseManager, player: PlayerController, parent=None
    ):
        """
        Initialize playlist view.

        Args:
            db_manager: Database manager
            player: Player controller
            parent: Parent widget
        """
        super().__init__(parent)
        self._db = db_manager
        self._player = player
        self._current_playlist_id: Optional[int] = None

        self._setup_ui()
        self._setup_connections()
        self._refresh_playlists()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for playlist list and playlist content
        splitter = QSplitter(Qt.Horizontal)

        # Left side - playlist list
        playlist_list_widget = self._create_playlist_list()
        splitter.addWidget(playlist_list_widget)

        # Right side - playlist content
        playlist_content = self._create_playlist_content()
        splitter.addWidget(playlist_content)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        # Apply styles
        self._apply_styles()

    def _create_playlist_list(self) -> QWidget:
        """Create the playlist list widget."""
        widget = QWidget()
        widget.setObjectName("playlistListPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 20, 15, 10)
        layout.setSpacing(10)

        # Title
        self._playlist_list_title = QLabel("📋 " + t("playlists"))
        self._playlist_list_title.setStyleSheet("""
            color: #1db954;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        """)
        layout.addWidget(self._playlist_list_title)

        # New playlist button
        self._new_playlist_btn = QPushButton(t("new_playlist"))
        self._new_playlist_btn.setObjectName("newPlaylistBtn")
        self._new_playlist_btn.setCursor(Qt.PointingHandCursor)
        layout.addWidget(self._new_playlist_btn)

        # Playlist list
        self._playlist_list = QListWidget()
        self._playlist_list.setObjectName("playlistList")
        self._playlist_list.setFocusPolicy(Qt.NoFocus)
        layout.addWidget(self._playlist_list)

        return widget

    def _create_playlist_content(self) -> QWidget:
        """Create the playlist content widget."""
        widget = QWidget()
        widget.setObjectName("playlistContentPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        self._playlist_title = QLabel(t("select_playlist_placeholder"))
        self._playlist_title.setStyleSheet("""
            color: #1db954;
            font-size: 24px;
            font-weight: bold;
        """)
        header_layout.addWidget(self._playlist_title)

        header_layout.addStretch()

        # Playlist actions
        self._play_playlist_btn = QPushButton(t("play"))
        self._play_playlist_btn.setObjectName("playlistActionBtn")
        self._play_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._play_playlist_btn.setEnabled(False)
        self._play_playlist_btn.clicked.connect(self._play_current_playlist)
        header_layout.addWidget(self._play_playlist_btn)

        self._delete_playlist_btn = QPushButton("🗑️ " + t("delete_playlist"))
        self._delete_playlist_btn.setObjectName("playlistActionBtn")
        self._delete_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._delete_playlist_btn.setEnabled(False)
        header_layout.addWidget(self._delete_playlist_btn)

        layout.addLayout(header_layout)

        # Tracks table
        self._tracks_table = QTableWidget()
        self._tracks_table.setColumnCount(4)
        self._tracks_table.setHorizontalHeaderLabels(
            [t("title"), t("artist"), t("album"), t("duration")]
        )

        # Configure table
        self._tracks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tracks_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._tracks_table.setAlternatingRowColors(True)
        self._tracks_table.verticalHeader().setVisible(False)
        self._tracks_table.horizontalHeader().setStretchLastSection(True)
        # Disable editing
        self._tracks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Remove focus outline
        self._tracks_table.setFocusPolicy(Qt.NoFocus)

        # Set column widths
        header = self._tracks_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        self._tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tracks_table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self._tracks_table)

        # Status
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #808080; font-size: 13px; padding: 8px 0px;"
        )
        layout.addWidget(self._status_label)

        return widget

    def _apply_styles(self):
        """Apply modern widget styles."""
        self.setStyleSheet("""
            QWidget#playlistListPanel {
                background-color: #141414;
                border-right: 1px solid #2a2a2a;
            }
            QWidget#playlistContentPanel {
                background-color: #141414;
            }
            QPushButton#newPlaylistBtn {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 10px 15px;
                border-radius: 20px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#newPlaylistBtn:hover {
                background-color: #1ed760;
            }
            QPushButton#playlistActionBtn {
                background: transparent;
                border: 2px solid #404040;
                color: #c0c0c0;
                padding: 8px 15px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton#playlistActionBtn:hover {
                border-color: #1db954;
                color: #1db954;
                background-color: rgba(29, 185, 84, 0.1);
            }
            QPushButton#playlistActionBtn:disabled {
                border-color: #2a2a2a;
                color: #404040;
            }
            QListWidget#playlistList {
                background: transparent;
                border: none;
            }
            QListWidget#playlistList::item {
                padding: 12px;
                color: #c0c0c0;
                border-radius: 8px;
                margin: 2px 0px;
            }
            QListWidget#playlistList::item:selected {
                background-color: #1db954;
                color: #000000;
                font-weight: bold;
            }
            QListWidget#playlistList::item:hover {
                background-color: #2a2a2a;
                color: #1db954;
            }
            QListWidget#playlistList::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            /* Alternating row colors */
            QTableWidget::item:alternate {
                background-color: #252525;
            }
            QTableWidget::item:!alternate {
                background-color: #1e1e1e;
            }
            QTableWidget::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget::item:selected:alternate {
                background-color: #1ed760;
            }
            QTableWidget::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget QHeaderView::section {
                background-color: #2a2a2a;
                color: #1db954;
                padding: 14px 12px;
                border: none;
                border-bottom: 2px solid #1db954;
                font-weight: bold;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            QTableWidget QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
            }
            QTableWidget QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
        """)

    def _setup_connections(self):
        """Setup signal connections."""
        self._new_playlist_btn.clicked.connect(self._create_playlist)
        self._delete_playlist_btn.clicked.connect(self._delete_playlist)
        self._playlist_list.itemClicked.connect(self._on_playlist_selected)
        self._playlist_list.itemDoubleClicked.connect(self._on_playlist_double_clicked)
        self._tracks_table.itemDoubleClicked.connect(self._on_track_double_clicked)

    def _refresh_playlists(self):
        """Refresh the playlist list."""
        self._playlist_list.clear()

        playlists = self._db.get_all_playlists()
        for playlist in playlists:
            item = QListWidgetItem(playlist.name)
            item.setData(Qt.UserRole, playlist.id)
            self._playlist_list.addItem(item)

        # Update UI texts
        self._update_ui_texts()

    def _update_ui_texts(self):
        """Update UI texts after language change."""
        # Update playlist list title
        self._playlist_list_title.setText("📋 " + t("playlists"))

        # Update playlist title label in content panel
        if not self._current_playlist_id:
            self._playlist_title.setText(t("select_playlist_placeholder"))

        # Update button texts
        self._new_playlist_btn.setText(t("new_playlist"))
        self._play_playlist_btn.setText(t("play"))
        self._delete_playlist_btn.setText("🗑️ " + t("delete_playlist"))

        # Update table headers
        self._tracks_table.setHorizontalHeaderLabels(
            [t("title"), t("artist"), t("album"), t("duration")]
        )

    def _create_playlist(self):
        """Create a new playlist."""
        name, ok = QInputDialog.getText(
            self, t("create_playlist"), t("enter_playlist_name")
        )

        if ok and name:
            playlist_id = self._db.create_playlist(name)
            self._refresh_playlists()

            # Select the new playlist
            for i in range(self._playlist_list.count()):
                item = self._playlist_list.item(i)
                if item.data(Qt.UserRole) == playlist_id:
                    self._playlist_list.setCurrentItem(item)
                    self._load_playlist(playlist_id)
                    break

    def _delete_playlist(self):
        """Delete the current playlist."""
        if self._current_playlist_id is None:
            return

        reply = QMessageBox.question(
            self,
            t("delete_playlist"),
            t("delete_playlist_confirm"),
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._db.delete_playlist(self._current_playlist_id)
            self._current_playlist_id = None
            self._refresh_playlists()
            self._clear_playlist_content()

    def _on_playlist_selected(self, item: QListWidgetItem):
        """Handle playlist selection."""
        playlist_id = item.data(Qt.UserRole)
        self._load_playlist(playlist_id)

    def _on_playlist_double_clicked(self, item: QListWidgetItem):
        """Handle playlist double click - load and play."""
        playlist_id = item.data(Qt.UserRole)
        self._load_playlist(playlist_id)
        self._player.load_playlist(playlist_id)

        # Start playing if there are tracks
        if self._player.engine.playlist:
            self._player.engine.play()

    def _load_playlist(self, playlist_id: int):
        """Load a playlist's content."""
        self._current_playlist_id = playlist_id

        # Get playlist info
        playlist = self._db.get_playlist(playlist_id)
        if playlist:
            self._playlist_title.setText(playlist.name)

        # Enable buttons
        self._delete_playlist_btn.setEnabled(True)
        tracks = self._db.get_playlist_tracks(playlist_id)
        self._play_playlist_btn.setEnabled(len(tracks) > 0)

        # Load tracks
        self._populate_table(tracks)
        self._status_label.setText(f"{len(tracks)} {t('tracks')}")

    def _play_current_playlist(self):
        """Play the current playlist."""
        if self._current_playlist_id is None:
            return
        self._player.load_playlist(self._current_playlist_id)
        if self._player.engine.playlist:
            self._player.engine.play()

    def _clear_playlist_content(self):
        """Clear the playlist content view."""
        self._playlist_title.setText(t("select_playlist_placeholder"))
        self._tracks_table.setRowCount(0)
        self._status_label.setText("")
        self._delete_playlist_btn.setEnabled(False)
        self._play_playlist_btn.setEnabled(False)

    def _populate_table(self, tracks: List[Track]):
        """Populate the table with tracks."""
        self._tracks_table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            # Title
            title_item = QTableWidgetItem(track.title or track.path.split("/")[-1])
            title_item.setData(Qt.UserRole, track.id)
            title_item.setForeground(QBrush(QColor("#e0e0e0")))
            self._tracks_table.setItem(row, 0, title_item)

            # Artist
            artist_item = QTableWidgetItem(track.artist or t("unknown"))
            artist_item.setForeground(QBrush(QColor("#b0b0b0")))
            self._tracks_table.setItem(row, 1, artist_item)

            # Album
            album_item = QTableWidgetItem(track.album or t("unknown"))
            album_item.setForeground(QBrush(QColor("#b0b0b0")))
            self._tracks_table.setItem(row, 2, album_item)

            # Duration
            duration_item = QTableWidgetItem(format_duration(track.duration))
            duration_item.setForeground(QBrush(QColor("#909090")))
            self._tracks_table.setItem(row, 3, duration_item)

    def _on_track_double_clicked(self, item: QTableWidgetItem):
        """Handle track double click."""
        row = item.row()
        title_item = self._tracks_table.item(row, 0)
        if title_item:
            track_id = title_item.data(Qt.UserRole)
            if track_id and self._current_playlist_id:
                # Emit playlist-specific signal
                self.playlist_track_double_clicked.emit(self._current_playlist_id, track_id)

    def _show_context_menu(self, pos):
        """Show context menu for tracks."""
        item = self._tracks_table.itemAt(pos)
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

        remove_action = QAction(t("remove_from_playlist"), self)
        remove_action.triggered.connect(lambda: self._remove_track(item))
        menu.addAction(remove_action)

        favorite_action = QAction(t("add_to_favorites"), self)
        favorite_action.triggered.connect(lambda: self._toggle_favorite_selected())
        menu.addAction(favorite_action)

        menu.addSeparator()

        edit_action = QAction(t("edit_media_info"), self)
        edit_action.triggered.connect(lambda: self._edit_media_info())
        menu.addAction(edit_action)

        menu.exec_(self._tracks_table.mapToGlobal(pos))

    def _remove_track(self, item: QTableWidgetItem):
        """Remove a track from the playlist."""
        if self._current_playlist_id is None:
            return

        row = item.row()
        title_item = self._tracks_table.item(row, 0)
        if title_item:
            track_id = title_item.data(Qt.UserRole)
            self._db.remove_track_from_playlist(self._current_playlist_id, track_id)
            self._load_playlist(self._current_playlist_id)

    def _toggle_favorite_selected(self):
        """Toggle favorite status for selected tracks."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            if item.column() == 0:
                track_id = item.data(Qt.UserRole)
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

        if self._current_playlist_id:
            self._load_playlist(self._current_playlist_id)

    def add_track_to_playlist(self, track_id: int):
        """Add a track to the current playlist."""
        if self._current_playlist_id is None:
            QMessageBox.warning(
                self, t("no_playlist_selected"), t("select_playlist_first")
            )
            return

        success = self._db.add_track_to_playlist(self._current_playlist_id, track_id)
        if success:
            self._load_playlist(self._current_playlist_id)
        else:
            QMessageBox.warning(self, "Error", t("track_already_in_playlist"))

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

        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_id = None
        for item in selected_items:
            if item.column() == 0:
                track_id = item.data(Qt.UserRole)
                break

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
                if self._current_playlist_id:
                    self._load_playlist(self._current_playlist_id)
            else:
                QMessageBox.warning(self, "Error", t("media_save_failed"))

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

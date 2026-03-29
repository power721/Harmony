"""
Playlist view widget for managing playlists.
"""

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QBrush, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLineEdit,
    QDialog,
    QDialogButtonBox,
    QSplitter,
    QLabel,
    QAbstractItemView,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
)

from ui.dialogs.message_dialog import MessageDialog, Yes, No
from domain.track import Track
from domain.playlist import Playlist
from services.playback import PlaybackService
from system.i18n import t
from system.event_bus import EventBus
from utils import format_duration


class DarkInputDialog(QDialog):
    """Custom input dialog with dark theme styling."""

    _STYLE_TEMPLATE = """
        QDialog {
            background-color: %background_alt%;
            color: %text%;
        }
        QLabel {
            color: %text%;
        }
        QLineEdit {
            background-color: %border%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px;
        }
        QLineEdit:focus {
            border: 1px solid %highlight%;
        }
        QPushButton {
            background-color: %border%;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px 20px;
            min-width: 80px;
        }
        QPushButton:hover {
            background-color: %background_hover%;
        }
        QPushButton:pressed {
            background-color: %background_hover%;
        }
        QDialogButtonBox {
            button-layout: 2;
        }
    """

    def __init__(self, title: str, label: str, text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(350)

        # Apply themed styling
        from system.theme import ThemeManager
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Label
        label_widget = QLabel(label)
        layout.addWidget(label_widget)

        # Input field
        self._input = QLineEdit()
        self._input.setText(text)
        self._input.selectAll()
        layout.addWidget(self._input)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        # Set button texts for internationalization
        button_box.button(QDialogButtonBox.Ok).setText(t("ok"))
        button_box.button(QDialogButtonBox.Cancel).setText(t("cancel"))
        layout.addWidget(button_box)

    def get_text(self) -> str:
        """Get the input text."""
        return self._input.text().strip()

    @staticmethod
    def getText(parent, title: str, label: str, text: str = "") -> tuple:
        """
        Static method to get text from user.
        Returns (text, accepted) tuple similar to QInputDialog.getText.
        """
        dialog = DarkInputDialog(title, label, text, parent)
        result = dialog.exec_()
        return dialog.get_text(), result == QDialog.Accepted


class PlaylistView(QWidget):
    """Playlist view for managing playlists."""

    # QSS template with theme tokens
    _STYLE_TEMPLATE = """
        QWidget#playlistListPanel {
            background-color: %background%;
            border-right: 1px solid %background_hover%;
        }
        QWidget#playlistContentPanel {
            background-color: %background%;
        }
        QPushButton#newPlaylistBtn {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 10px 15px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 13px;
        }
        QPushButton#newPlaylistBtn:hover {
            background-color: %highlight_hover%;
        }
        QPushButton#playlistActionBtn {
            background: transparent;
            border: 2px solid %border%;
            color: %text_secondary%;
            padding: 8px 15px;
            border-radius: 6px;
            font-weight: 500;
        }
        QPushButton#playlistActionBtn:hover {
            border-color: %highlight%;
            color: %highlight%;
            background-color: %selection%;
        }
        QPushButton#playlistActionBtn:disabled {
            border-color: %background_hover%;
            color: %border%;
        }
        QListWidget#playlistList {
            background: transparent;
            border: none;
        }
        QListWidget#playlistList::item {
            padding: 12px;
            color: %text_secondary%;
            border-radius: 8px;
            margin: 2px 0px;
        }
        QListWidget#playlistList::item:selected {
            background-color: %highlight%;
            color: %background%;
            font-weight: bold;
        }
        QListWidget#playlistList::item:hover {
            background-color: %background_hover%;
            color: %highlight%;
        }
        QListWidget#playlistList::item:selected:hover {
            background-color: %highlight_hover%;
            color: %background%;
        }
        QTableWidget {
            background-color: %background%;
            border: none;
            border-radius: 8px;
            gridline-color: %background_hover%;
        }
        QTableWidget::item {
            padding: 12px 8px;
            color: %text%;
            border: none;
            border-bottom: 1px solid %background_hover%;
        }
        QTableWidget::item:alternate {
            background-color: %background_alt%;
        }
        QTableWidget::item:!alternate {
            background-color: %background%;
        }
        QTableWidget::item:selected {
            background-color: %highlight%;
            color: %background%;
            font-weight: 500;
        }
        QTableWidget::item:selected:!alternate {
            background-color: %highlight%;
        }
        QTableWidget::item:selected:alternate {
            background-color: %highlight_hover%;
        }
        QTableWidget::item:hover {
            background-color: %background_hover%;
        }
        QTableWidget::item:selected:hover {
            background-color: %highlight_hover%;
        }
        QTableWidget QHeaderView::section {
            background-color: %background_hover%;
            color: %highlight%;
            padding: 14px 12px;
            border: none;
            border-bottom: 2px solid %highlight%;
            font-weight: bold;
            font-size: 13px;
            letter-spacing: 0.5px;
        }
        QTableWidget QScrollBar:vertical {
            background-color: %background%;
            width: 12px;
            border-radius: 6px;
        }
        QTableWidget QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 40px;
        }
        QTableWidget QScrollBar::handle:vertical:hover {
            background-color: %background_hover%;
        }
    """
    _CONTEXT_MENU_STYLE = """
        QMenu {
            background-color: %background_alt%;
            color: %text%;
            border: 1px solid %border%;
        }
        QMenu::item {
            padding: 8px 20px;
        }
        QMenu::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
    """
    _EDIT_DIALOG_STYLE = """
        QDialog { background-color: %background_alt%; color: %text%; }
        QLabel { color: %text%; font-size: 13px; }
        QLineEdit {
            background-color: #181818;
            color: %text%;
            border: 1px solid %border%;
            border-radius: 4px;
            padding: 8px;
            font-size: 13px;
        }
        QLineEdit:focus { border: 1px solid %highlight%; }
        QPushButton {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 8px 20px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover { background-color: %highlight_hover%; }
        QPushButton[role="cancel"] { background-color: %border%; color: %text%; }
        QPushButton[role="cancel"]:hover { background-color: %background_hover%; }
    """

    track_double_clicked = Signal(int)  # Signal when track is double-clicked (from library view, plays all)
    playlist_track_double_clicked = Signal(int,
                                           int)  # Signal when playlist track is double-clicked (playlist_id, track_id)

    def __init__(
            self,
            playlist_service: 'PlaylistService',
            favorite_service: 'FavoritesService',
            library_service: 'LibraryService',
            player: PlaybackService,
            parent=None
    ):
        """
        Initialize playlist view.

        Args:
            playlist_service: Playlist service for playlist operations
            favorite_service: Favorites service for favorite operations
            library_service: Library service for track operations
            player: Player controller
            parent: Parent widget
        """
        super().__init__(parent)
        self._playlist_service = playlist_service
        self._favorite_service = favorite_service
        self._library_service = library_service
        self._player = player
        self._current_playlist_id: Optional[int] = None

        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

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

        # Apply themed styles
        self.refresh_theme()

    def refresh_theme(self):
        """Apply themed styles from ThemeManager."""
        from system.theme import ThemeManager
        theme_manager = ThemeManager.instance()
        theme = theme_manager.current_theme

        self.setStyleSheet(theme_manager.get_qss(self._STYLE_TEMPLATE))

        # Update title labels with theme colors
        self._playlist_list_title.setStyleSheet(f"""
            color: {theme.highlight};
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        """)
        self._playlist_title.setStyleSheet(f"""
            color: {theme.highlight};
            font-size: 24px;
            font-weight: bold;
        """)
        self._status_label.setStyleSheet(
            f"color: {theme.text_secondary}; font-size: 13px; padding: 8px 0px;"
        )

    def _create_playlist_list(self) -> QWidget:
        """Create the playlist list widget."""
        widget = QWidget()
        widget.setObjectName("playlistListPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 20, 15, 10)
        layout.setSpacing(10)

        # Title
        self._playlist_list_title = QLabel(t("playlists"))
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
        self._playlist_list.setCursor(Qt.PointingHandCursor)
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
        header_layout.addWidget(self._playlist_title)

        header_layout.addStretch()

        # Playlist actions
        self._play_playlist_btn = QPushButton(t("play"))
        self._play_playlist_btn.setObjectName("playlistActionBtn")
        self._play_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._play_playlist_btn.setEnabled(False)
        self._play_playlist_btn.clicked.connect(self._play_current_playlist)
        header_layout.addWidget(self._play_playlist_btn)

        self._rename_playlist_btn = QPushButton(t("rename"))
        self._rename_playlist_btn.setObjectName("playlistActionBtn")
        self._rename_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._rename_playlist_btn.setEnabled(False)
        self._rename_playlist_btn.clicked.connect(self._rename_playlist)
        header_layout.addWidget(self._rename_playlist_btn)

        self._delete_playlist_btn = QPushButton("🗑️ " + t("delete_playlist"))
        self._delete_playlist_btn.setObjectName("playlistActionBtn")
        self._delete_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._delete_playlist_btn.setEnabled(False)
        header_layout.addWidget(self._delete_playlist_btn)

        layout.addLayout(header_layout)

        # Tracks table
        self._tracks_table = QTableWidget()
        self._tracks_table.setColumnCount(5)
        self._tracks_table.setHorizontalHeaderLabels(
            [t("source"), t("title"), t("artist"), t("album"), t("duration")]
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
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        self._tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tracks_table.customContextMenuRequested.connect(self._show_context_menu)

        layout.addWidget(self._tracks_table)

        # Status
        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        return widget

    def _setup_connections(self):
        """Setup signal connections."""
        self._new_playlist_btn.clicked.connect(self._create_playlist)
        self._delete_playlist_btn.clicked.connect(self._delete_playlist)
        # _rename_playlist_btn already connected in _create_playlist_content
        self._playlist_list.itemClicked.connect(self._on_playlist_selected)
        self._playlist_list.itemDoubleClicked.connect(self._on_playlist_double_clicked)
        self._tracks_table.itemDoubleClicked.connect(self._on_track_double_clicked)

        # Listen for playlist events from other views
        EventBus.instance().playlist_created.connect(self._on_playlist_created)
        EventBus.instance().playlist_modified.connect(self._on_playlist_modified)

    def _refresh_playlists(self):
        """Refresh the playlist list."""
        self._playlist_list.clear()

        playlists = self._playlist_service.get_all_playlists()
        for playlist in playlists:
            item = QListWidgetItem(playlist.name)
            item.setData(Qt.UserRole, playlist.id)
            self._playlist_list.addItem(item)

        # Update UI texts
        self._update_ui_texts()

    def _update_ui_texts(self):
        """Update UI texts after language change."""
        # Update playlist list title
        self._playlist_list_title.setText(t("playlists"))

        # Update playlist title label in content panel
        if not self._current_playlist_id:
            self._playlist_title.setText(t("select_playlist_placeholder"))

        # Update button texts
        self._new_playlist_btn.setText(t("new_playlist"))
        self._play_playlist_btn.setText(t("play"))
        self._rename_playlist_btn.setText(t("rename"))
        self._delete_playlist_btn.setText("🗑️ " + t("delete_playlist"))

        # Update table headers
        self._tracks_table.setHorizontalHeaderLabels(
            [t("source"), t("title"), t("artist"), t("album"), t("duration")]
        )

    def _create_playlist(self):
        """Create a new playlist."""
        name, ok = DarkInputDialog.getText(
            self, t("create_playlist"), t("enter_playlist_name")
        )

        if ok and name:
            playlist = Playlist(name=name)
            playlist_id = self._playlist_service.create_playlist(playlist)
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

        reply = MessageDialog.question(
            self,
            t("delete_playlist"),
            t("delete_playlist_confirm"),
            MessageDialog.Yes | MessageDialog.No,
        )

        if reply == MessageDialog.Yes:
            self._playlist_service.delete_playlist(self._current_playlist_id)
            self._current_playlist_id = None
            self._refresh_playlists()
            self._clear_playlist_content()

    def _rename_playlist(self):
        """Rename the current playlist."""
        if self._current_playlist_id is None:
            return

        playlist = self._playlist_service.get_playlist(self._current_playlist_id)
        if not playlist:
            return

        new_name, ok = DarkInputDialog.getText(
            self,
            t("rename_playlist"),
            t("enter_playlist_name"),
            text=playlist.name
        )

        if ok and new_name:
            playlist.name = new_name
            self._playlist_service.update_playlist(playlist)
            self._playlist_title.setText(new_name)
            self._refresh_playlists()

    def _on_playlist_selected(self, item: QListWidgetItem):
        """Handle playlist selection."""
        playlist_id = item.data(Qt.UserRole)
        self._load_playlist(playlist_id)

    def _on_playlist_created(self, playlist_id: int):
        """Handle playlist created event from other views."""
        self._refresh_playlists()
        # Select and load the new playlist
        for i in range(self._playlist_list.count()):
            item = self._playlist_list.item(i)
            if item and item.data(Qt.UserRole) == playlist_id:
                self._playlist_list.setCurrentItem(item)
                self._load_playlist(playlist_id)
                break

    def _on_playlist_modified(self, playlist_id: int):
        """Handle playlist modified event from other views."""
        # Refresh current playlist if it's the one being modified
        if self._current_playlist_id == playlist_id:
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
        playlist = self._playlist_service.get_playlist(playlist_id)
        if playlist:
            self._playlist_title.setText(playlist.name)

        # Enable buttons
        self._delete_playlist_btn.setEnabled(True)
        self._rename_playlist_btn.setEnabled(True)
        tracks = self._playlist_service.get_playlist_tracks(playlist_id)
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
        self._rename_playlist_btn.setEnabled(False)
        self._play_playlist_btn.setEnabled(False)

    def _populate_table(self, tracks: List[Track]):
        """Populate the table with tracks."""
        from domain.track import TrackSource
        from system.theme import ThemeManager

        # Get theme colors
        theme = ThemeManager.instance().current_theme
        text_secondary_color = QColor(theme.text_secondary)
        text_color = QColor(theme.text)

        self._tracks_table.setRowCount(len(tracks))

        for row, track in enumerate(tracks):
            # Source
            source_text = self._get_source_display_name(track.source)
            source_item = QTableWidgetItem(source_text)
            source_item.setData(Qt.UserRole, track.id)
            source_item.setForeground(QBrush(text_secondary_color))
            self._tracks_table.setItem(row, 0, source_item)

            # Title
            title_item = QTableWidgetItem(track.title or track.path.split("/")[-1])
            title_item.setForeground(QBrush(text_color))
            self._tracks_table.setItem(row, 1, title_item)

            # Artist
            artist_item = QTableWidgetItem(track.artist or t("unknown"))
            artist_item.setForeground(QBrush(text_secondary_color))
            self._tracks_table.setItem(row, 2, artist_item)

            # Album
            album_item = QTableWidgetItem(track.album or t("unknown"))
            album_item.setForeground(QBrush(text_secondary_color))
            self._tracks_table.setItem(row, 3, album_item)

            # Duration
            duration_item = QTableWidgetItem(format_duration(track.duration))
            duration_item.setForeground(QBrush(text_secondary_color))
            self._tracks_table.setItem(row, 4, duration_item)

    def _get_source_display_name(self, source) -> str:
        """Get display name for track source."""
        from domain.track import TrackSource

        source_map = {
            TrackSource.LOCAL: t("source_local"),
            TrackSource.QUARK: t("source_quark"),
            TrackSource.BAIDU: t("source_baidu"),
            TrackSource.QQ: t("source_qq"),
        }
        return source_map.get(source, t("source_local"))

    def _on_track_double_clicked(self, item: QTableWidgetItem):
        """Handle track double click."""
        row = item.row()
        source_item = self._tracks_table.item(row, 0)
        if source_item:
            track_id = source_item.data(Qt.UserRole)
            if track_id and self._current_playlist_id:
                # Emit playlist-specific signal
                self.playlist_track_double_clicked.emit(self._current_playlist_id, track_id)

    def _show_context_menu(self, pos):
        """Show context menu for tracks."""
        item = self._tracks_table.itemAt(pos)
        if not item:
            return

        menu = QMenu(self)
        from system.theme import ThemeManager
        menu.setStyleSheet(ThemeManager.instance().get_qss(self._CONTEXT_MENU_STYLE))

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
        source_item = self._tracks_table.item(row, 0)
        if source_item:
            track_id = source_item.data(Qt.UserRole)
            self._playlist_service.remove_track_from_playlist(self._current_playlist_id, track_id)
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
            if self._favorite_service.is_favorite(track_id=track_id):
                self._favorite_service.remove_favorite(track_id=track_id)
                removed_count += 1
            else:
                self._favorite_service.add_favorite(track_id=track_id)
                added_count += 1

        if added_count > 0 and removed_count == 0:
            from utils import format_count_message
            message = format_count_message("added_x_tracks_to_favorites", added_count)
            MessageDialog.information(
                self,
                t("added_to_favorites"),
                message,
            )
        elif removed_count > 0 and added_count == 0:
            from utils import format_count_message
            message = format_count_message("removed_x_tracks_from_favorites", removed_count)
            MessageDialog.information(
                self,
                t("removed_from_favorites"),
                message,
            )
        else:
            message = t("added_x_removed_y").format(added=added_count, removed=removed_count)
            MessageDialog.information(
                self,
                t("updated_favorites"),
                message,
            )

        if self._current_playlist_id:
            self._load_playlist(self._current_playlist_id)

    def add_track_to_playlist(self, track_id: int):
        """Add a track to the current playlist."""
        if self._current_playlist_id is None:
            MessageDialog.warning(
                self, t("no_playlist_selected"), t("select_playlist_first")
            )
            return

        success = self._playlist_service.add_track_to_playlist(self._current_playlist_id, track_id)
        if success:
            self._load_playlist(self._current_playlist_id)
            # Get playlist name for message
            playlist = self._playlist_service.get_playlist(self._current_playlist_id)
            playlist_name = playlist.name if playlist else ""
            MessageDialog.information(
                self, t("success"), t("added_tracks_to_playlist").format(count=1, name=playlist_name)
            )
        else:
            MessageDialog.warning(self, "Error", t("track_already_in_playlist"))

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

        track = self._library_service.get_track(track_id)
        if not track:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(t("edit_media_info_title"))
        dialog.setMinimumWidth(450)
        from system.theme import ThemeManager
        dialog.setStyleSheet(ThemeManager.instance().get_qss(self._EDIT_DIALOG_STYLE))

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
        theme = ThemeManager.instance().current_theme
        path_label.setStyleSheet(f"color: {theme.text_secondary}; font-size: 11px;")
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
                track.title = new_title
                track.artist = new_artist
                track.album = new_album
                self._library_service.update_track(track)
                # Emit metadata_updated signal to update play_queue
                EventBus.instance().metadata_updated.emit(track_id)
                MessageDialog.information(self, t("success"), t("media_saved"))
                if self._current_playlist_id:
                    self._load_playlist(self._current_playlist_id)
            else:
                MessageDialog.warning(self, "Error", t("media_save_failed"))

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

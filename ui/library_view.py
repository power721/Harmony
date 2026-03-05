"""
Library view widget for browsing the music library.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QPushButton,
    QLabel,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMenu,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QIcon
from typing import List, Optional
from pathlib import Path

from database import DatabaseManager, Track
from player import PlayerController
from player.engine import PlayerState


class LibraryView(QWidget):
    """Library view for browsing music."""

    track_double_clicked = Signal(int)  # Signal when track is double-clicked
    add_to_queue = Signal(list)  # Signal when tracks should be added to queue
    add_to_playlist_signal = Signal(
        list
    )  # Signal when tracks should be added to a playlist

    def __init__(
        self, db_manager: DatabaseManager, player: PlayerController, parent=None
    ):
        """
        Initialize library view.

        Args:
            db_manager: Database manager
            player: Player controller
            parent: Parent widget
        """
        super().__init__(parent)
        self._db = db_manager
        self._player = player
        self._current_view = "all"  # all, favorites, history
        self._current_sub_view = "all"  # all, artists, albums (for library view)
        self._current_playing_track_id = None  # Track currently playing
        self._current_playing_row = -1  # Row of currently playing track

        self._setup_ui()
        self._setup_connections()
        self.refresh()

    def _setup_ui(self):
        """Setup the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(15)

        # Header with title and search
        header_layout = QHBoxLayout()

        self._title_label = QLabel("Your Library")
        self._title_label.setObjectName("libraryTitle")
        self._title_label.setStyleSheet("""
            QLabel#libraryTitle {
                color: #1db954;
                font-size: 28px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        header_layout.addWidget(self._title_label)

        header_layout.addStretch()

        # Search box
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 Search tracks, artists, albums...")
        self._search_input.setFixedWidth(300)
        self._search_input.setStyleSheet("""
            QLineEdit {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 2px solid #3a3a3a;
                border-radius: 20px;
                padding: 10px 15px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 2px solid #1db954;
                background-color: #2d2d2d;
            }
            QLineEdit::placeholder {
                color: #808080;
            }
        """)
        header_layout.addWidget(self._search_input)

        layout.addLayout(header_layout)

        # View type selector
        view_selector = QHBoxLayout()
        view_selector.setSpacing(10)

        # Get emoji-supporting font
        from PySide6.QtGui import QFontDatabase, QFont
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

        # Create view buttons with emoji font
        self._btn_all = QPushButton("🎵 All Tracks")
        self._btn_all.setCheckable(True)
        self._btn_all.setChecked(True)
        self._btn_all.setObjectName("viewBtn")
        self._btn_all.setCursor(Qt.PointingHandCursor)
        self._btn_all.setMinimumWidth(120)  # Ensure enough width for text
        if emoji_font:
            btn_font = QFont()
            btn_font.setFamily(emoji_font)
            btn_font.setPointSize(13)
            self._btn_all.setFont(btn_font)
        view_selector.addWidget(self._btn_all)

        self._btn_artists = QPushButton("🎤 Artists")
        self._btn_artists.setCheckable(True)
        self._btn_artists.setObjectName("viewBtn")
        self._btn_artists.setCursor(Qt.PointingHandCursor)
        self._btn_artists.setMinimumWidth(110)  # Ensure enough width for text
        if emoji_font:
            btn_font = QFont()
            btn_font.setFamily(emoji_font)
            btn_font.setPointSize(13)
            self._btn_artists.setFont(btn_font)
        view_selector.addWidget(self._btn_artists)

        self._btn_albums = QPushButton("💿 Albums")
        self._btn_albums.setCheckable(True)
        self._btn_albums.setObjectName("viewBtn")
        self._btn_albums.setCursor(Qt.PointingHandCursor)
        self._btn_albums.setMinimumWidth(100)  # Ensure enough width for text
        if emoji_font:
            btn_font = QFont()
            btn_font.setFamily(emoji_font)
            btn_font.setPointSize(13)
            self._btn_albums.setFont(btn_font)
        view_selector.addWidget(self._btn_albums)

        # Style the view buttons
        view_button_style = """
            QPushButton#viewBtn {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 2px solid #3a3a3a;
                border-radius: 20px;
                padding: 8px 20px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton#viewBtn:hover {
                background-color: #3a3a3a;
                border: 2px solid #1db954;
                color: #1db954;
            }
            QPushButton#viewBtn:checked {
                background-color: #1db954;
                color: #000000;
                border: 2px solid #1db954;
                font-weight: bold;
            }
            QPushButton#viewBtn:checked:hover {
                background-color: #1ed760;
            }
        """

        # Apply styles to all buttons
        self._btn_all.setStyleSheet(view_button_style)
        self._btn_artists.setStyleSheet(view_button_style)
        self._btn_albums.setStyleSheet(view_button_style)
        self._btn_all.setStyleSheet(view_button_style)
        self._btn_artists.setStyleSheet(view_button_style)
        self._btn_albums.setStyleSheet(view_button_style)

        view_selector.addStretch()

        layout.addLayout(view_selector)

        # Tracks table
        self._tracks_table = QTableWidget()
        self._tracks_table.setObjectName("tracksTable")
        self._tracks_table.setColumnCount(5)
        self._tracks_table.setHorizontalHeaderLabels(
            ["Title", "Artist", "Album", "Duration", ""]
        )

        # Configure table
        self._tracks_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._tracks_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._tracks_table.setAlternatingRowColors(True)
        self._tracks_table.verticalHeader().setVisible(False)
        self._tracks_table.horizontalHeader().setStretchLastSection(True)
        self._tracks_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tracks_table.customContextMenuRequested.connect(self._show_context_menu)
        # Disable editing
        self._tracks_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # Remove focus outline
        self._tracks_table.setFocusPolicy(Qt.NoFocus)

        # Set column widths - Title gets all remaining space
        header = self._tracks_table.horizontalHeader()
        header.setStretchLastSection(False)

        # Set resize modes - Title stretches to fill remaining space
        # Title: stretch to fill all remaining space
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        # Artist: fixed width
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(1, 120)
        # Album: fixed width
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(2, 150)
        # Duration: fit content
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        # Favorites: fixed small width
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self._tracks_table.setColumnWidth(4, 40)

        # Styling - Modern, eye-friendly design
        self._tracks_table.setStyleSheet("""
            QTableWidget#tracksTable {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget#tracksTable::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            /* Alternating row colors for better readability */
            QTableWidget#tracksTable::item:alternate {
                background-color: #252525;
            }
            QTableWidget#tracksTable::item:!alternate {
                background-color: #1e1e1e;
            }
            /* Selected state with vibrant accent */
            QTableWidget#tracksTable::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget#tracksTable::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget#tracksTable::item:selected:alternate {
                background-color: #1ed760;
            }
            /* Hover effect for interactivity */
            QTableWidget#tracksTable::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget#tracksTable::item:selected:hover {
                background-color: #1ed760;
            }
            /* Remove focus outline */
            QTableWidget#tracksTable::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget#tracksTable:focus {
                outline: none;
                border: none;
            }
            /* Header styling */
            QTableWidget#tracksTable QHeaderView::section {
                background-color: #2a2a2a;
                color: #1db954;
                padding: 14px 12px;
                border: none;
                border-bottom: 2px solid #1db954;
                border-radius: 0px;
                font-weight: bold;
                font-size: 13px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            /* First header (top-left corner) */
            QTableWidget#tracksTable QTableCornerButton::section {
                background-color: #2a2a2a;
                border: none;
                border-right: 1px solid #3a3a3a;
                border-bottom: 2px solid #1db954;
            }
            /* Scrollbar styling */
            QTableWidget#tracksTable QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QTableWidget#tracksTable QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget#tracksTable QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QTableWidget#tracksTable QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border-radius: 6px;
            }
            QTableWidget#tracksTable QScrollBar::handle:horizontal {
                background-color: #404040;
                border-radius: 6px;
                min-width: 40px;
            }
            QTableWidget#tracksTable QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            QTableWidget#tracksTable QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
                width: 0px;
            }
        """)

        # Loading indicator
        self._loading_label = QLabel("⏳ Loading...")
        self._loading_label.setAlignment(Qt.AlignCenter)
        self._loading_label.setStyleSheet(
            "color: #1db954; font-size: 16px; padding: 40px; background-color: #1e1e1e; border-radius: 8px;"
        )
        self._loading_label.setVisible(False)
        layout.addWidget(self._loading_label)

        layout.addWidget(self._tracks_table)

        # Status bar
        self._status_label = QLabel("📚 No tracks in library")
        self._status_label.setStyleSheet(
            "color: #808080; font-size: 13px; padding: 8px 0px;"
        )
        layout.addWidget(self._status_label)

    def _setup_connections(self):
        """Setup signal connections."""
        self._search_input.textChanged.connect(self._on_search)
        self._tracks_table.itemDoubleClicked.connect(self._on_item_double_clicked)

        self._btn_all.clicked.connect(lambda: self._change_view("all"))
        self._btn_artists.clicked.connect(lambda: self._change_view("artists"))
        self._btn_albums.clicked.connect(lambda: self._change_view("albums"))

        # Connect to player engine signals
        self._player.engine.current_track_changed.connect(self._on_current_track_changed)
        self._player.engine.state_changed.connect(self._on_player_state_changed)

    def refresh(self):
        """Refresh the library view."""
        if self._current_view == "all":
            if self._current_sub_view == "artists":
                self._load_artists()
            elif self._current_sub_view == "albums":
                self._load_albums()
            else:
                self._load_all_tracks()
        elif self._current_view == "favorites":
            self._load_favorites()
        elif self._current_view == "history":
            self._load_history()

    def show_all(self):
        """Show all tracks."""
        self._current_view = "all"
        self._title_label.setText("Your Library")
        self._load_all_tracks()
        # Show view buttons
        self._btn_all.setVisible(True)
        self._btn_artists.setVisible(True)
        self._btn_albums.setVisible(True)
        # Restore the sub-view button state
        self._btn_all.setChecked(self._current_sub_view == "all")
        self._btn_artists.setChecked(self._current_sub_view == "artists")
        self._btn_albums.setChecked(self._current_sub_view == "albums")
        # Load the appropriate sub-view content
        if self._current_sub_view == "artists":
            self._load_artists()
        elif self._current_sub_view == "albums":
            self._load_albums()

        # Select and scroll to current playing track after UI updates
        from PySide6.QtCore import QTimer
        QTimer.singleShot(150, self._select_and_scroll_to_current)

    def show_favorites(self):
        """Show favorite tracks."""
        self._current_view = "favorites"
        self._title_label.setText("⭐ Favorites")
        self._load_favorites()
        # Hide view buttons
        self._btn_all.setVisible(False)
        self._btn_artists.setVisible(False)
        self._btn_albums.setVisible(False)

    def show_history(self):
        """Show play history."""
        self._current_view = "history"
        self._title_label.setText("🕐 Recently Played")
        self._load_history()
        # Hide view buttons
        self._btn_all.setVisible(False)
        self._btn_artists.setVisible(False)
        self._btn_albums.setVisible(False)

    def _change_view(self, view_type: str):
        """Change the view type."""
        # Save the sub-view state
        self._current_sub_view = view_type

        # Update button states
        self._btn_all.setChecked(view_type == "all")
        self._btn_artists.setChecked(view_type == "artists")
        self._btn_albums.setChecked(view_type == "albums")

        if view_type == "all":
            self._load_all_tracks()
        elif view_type == "artists":
            self._load_artists()
        elif view_type == "albums":
            self._load_albums()

    def _load_all_tracks(self):
        """Load all tracks into the table."""
        self._loading_label.setVisible(True)
        self._tracks_table.setVisible(False)

        tracks = self._db.get_all_tracks()
        self._populate_table(tracks)
        self._status_label.setText(f"{len(tracks)} tracks")

        self._loading_label.setVisible(False)
        self._tracks_table.setVisible(True)

    def _load_favorites(self):
        """Load favorite tracks."""
        self._loading_label.setVisible(True)
        self._tracks_table.setVisible(False)

        tracks = self._db.get_favorites()
        self._populate_table(tracks)
        self._status_label.setText(f"{len(tracks)} favorites")

        self._loading_label.setVisible(False)
        self._tracks_table.setVisible(True)

    def _load_history(self):
        """Load play history."""
        self._loading_label.setVisible(True)
        self._tracks_table.setVisible(False)

        history = self._db.get_play_history(limit=50)

        tracks = []
        for entry in history:
            track = self._db.get_track(entry.track_id)
            if track:
                tracks.append((track, entry.played_at))

        self._populate_table([t[0] for t in tracks])
        self._status_label.setText(f"{len(tracks)} recently played")

        self._loading_label.setVisible(False)
        self._tracks_table.setVisible(True)

    def _load_artists(self):
        """Load artists view."""
        # Get all unique artists
        tracks = self._db.get_all_tracks()
        artists = {}
        for track in tracks:
            if track.artist not in artists:
                artists[track.artist] = []
            artists[track.artist].append(track)

        # For now, show first track per artist
        # In a full implementation, this would show artist cards
        artist_tracks = []
        for artist, track_list in sorted(artists.items()):
            if track_list:
                artist_tracks.append(track_list[0])

        self._populate_table(artist_tracks)
        self._status_label.setText(f"{len(artists)} artists")

    def _load_albums(self):
        """Load albums view."""
        # Get all unique albums
        tracks = self._db.get_all_tracks()
        albums = {}
        for track in tracks:
            key = f"{track.artist} - {track.album}"
            if key not in albums:
                albums[key] = []
            albums[key].append(track)

        # For now, show first track per album
        album_tracks = []
        for album, track_list in sorted(albums.items()):
            if track_list:
                album_tracks.append(track_list[0])

        self._populate_table(album_tracks)
        self._status_label.setText(f"{len(albums)} albums")

    def _populate_table(self, tracks: List[Track]):
        """Populate the table with tracks."""
        from utils import format_duration
        from PySide6.QtGui import QBrush, QColor

        # Block UI updates during population
        self._tracks_table.setUpdatesEnabled(False)
        self._tracks_table.setRowCount(len(tracks))

        try:
            # Batch size for UI updates (process in chunks to avoid blocking)
            batch_size = 50
            total_tracks = len(tracks)
            playing_row = -1  # Track which row has the playing song

            for row, track in enumerate(tracks):
                # Title - add play icon if currently playing
                is_currently_playing = (track.id == self._current_playing_track_id)
                if is_currently_playing:
                    playing_row = row

                # Determine icon based on player state
                icon_prefix = ""
                if is_currently_playing:
                    if self._player.engine.state == PlayerState.PLAYING:
                        icon_prefix = "▶️ "
                    else:
                        icon_prefix = "⏸️ "

                title_text = f"{icon_prefix}{track.title or track.path.split('/')[-1]}"
                title_item = QTableWidgetItem(title_text)
                title_item.setData(Qt.UserRole, track.id)
                title_item.setForeground(QBrush(QColor("#e0e0e0")))

                # Make currently playing row bold and green
                if is_currently_playing:
                    from PySide6.QtGui import QFont
                    font = title_item.font()
                    font.setBold(True)
                    title_item.setFont(font)
                    title_item.setForeground(QBrush(QColor("#1db954")))

                self._tracks_table.setItem(row, 0, title_item)

                # Artist
                artist_item = QTableWidgetItem(track.artist or "Unknown")
                artist_item.setForeground(QBrush(QColor("#b0b0b0")))
                self._tracks_table.setItem(row, 1, artist_item)

                # Album
                album_item = QTableWidgetItem(track.album or "Unknown")
                album_item.setForeground(QBrush(QColor("#b0b0b0")))
                self._tracks_table.setItem(row, 2, album_item)

                # Duration
                duration_item = QTableWidgetItem(format_duration(track.duration))
                duration_item.setForeground(QBrush(QColor("#909090")))
                self._tracks_table.setItem(row, 3, duration_item)

                # Favorite indicator (check if actually favorited)
                is_fav = self._db.is_favorite(track.id)
                fav_text = "⭐" if is_fav else ""
                fav_item = QTableWidgetItem(fav_text)
                fav_item.setForeground(
                    QBrush(QColor("#ffd700" if is_fav else "#505050"))
                )
                self._tracks_table.setItem(row, 4, fav_item)

                # Process events periodically to keep UI responsive
                if (row + 1) % batch_size == 0:
                    from PySide6.QtWidgets import QApplication

                    QApplication.processEvents()

        finally:
            # Re-enable updates
            self._tracks_table.setUpdatesEnabled(True)

    def _on_search(self, query: str):
        """Handle search."""
        if not query:
            self.refresh()
            return

        tracks = self._db.search_tracks(query)
        self._populate_table(tracks)
        self._status_label.setText(f'{len(tracks)} results for "{query}"')

    def _on_current_track_changed(self, track_dict: dict):
        """Handle current track change from player."""
        if track_dict:
            new_track_id = track_dict.get('id')
            old_track_id = self._current_playing_track_id
            self._current_playing_track_id = new_track_id

            # Update the playing indicator in the table without reloading
            self._update_playing_indicator_in_table(old_track_id, new_track_id)

            # Scroll to the playing track
            self._scroll_to_playing_track()

    def _on_player_state_changed(self, state: PlayerState):
        """Handle player state change (play/pause)."""
        # Update the icon when playing/paused without reloading
        self._update_playing_icon_state()

    def _update_playing_indicator_in_table(self, old_track_id: Optional[int], new_track_id: Optional[int]):
        """Update playing indicator by modifying existing items instead of reloading."""
        from PySide6.QtGui import QFont, QBrush, QColor

        # Remove playing indicator from old track
        if old_track_id is not None:
            self._set_track_playing_status(old_track_id, False)

        # Add playing indicator to new track
        if new_track_id is not None:
            self._set_track_playing_status(new_track_id, True)

    def _update_playing_icon_state(self):
        """Update the playing/paused icon for current track."""
        if self._current_playing_track_id is not None:
            self._set_track_playing_status(self._current_playing_track_id, True, update_icon_only=True)

    def _set_track_playing_status(self, track_id: int, is_playing: bool, update_icon_only: bool = False):
        """Set the playing status for a specific track in the table."""
        from PySide6.QtGui import QFont, QBrush, QColor

        # Find the row with this track
        for row in range(self._tracks_table.rowCount()):
            title_item = self._tracks_table.item(row, 0)
            if title_item:
                item_track_id = title_item.data(Qt.UserRole)
                if item_track_id == track_id:
                    # Get the original title without icon
                    current_text = title_item.text()
                    # Remove any existing icons
                    original_title = current_text.replace("▶️ ", "").replace("⏸️ ", "")

                    if is_playing:
                        # Determine which icon to show
                        if self._player.engine.state == PlayerState.PLAYING:
                            icon = "▶️ "
                        else:
                            icon = "⏸️ "

                        new_text = f"{icon}{original_title}"

                        # Update text
                        title_item.setText(new_text)

                        # Update font and color
                        if not update_icon_only:
                            font = title_item.font()
                            font.setBold(True)
                            title_item.setFont(font)
                            title_item.setForeground(QBrush(QColor("#1db954")))
                    else:
                        # Remove playing indicator
                        title_item.setText(original_title)

                        # Reset font and color
                        if not update_icon_only:
                            font = title_item.font()
                            font.setBold(False)
                            title_item.setFont(font)
                            title_item.setForeground(QBrush(QColor("#e0e0e0")))
                    break

    def _scroll_to_playing_track(self):
        """Scroll to the currently playing track."""
        if self._current_playing_track_id is None:
            return

        # Find the row with the current playing track
        for row in range(self._tracks_table.rowCount()):
            title_item = self._tracks_table.item(row, 0)
            if title_item:
                track_id = title_item.data(Qt.UserRole)
                if track_id == self._current_playing_track_id:
                    # Select the row
                    self._tracks_table.selectRow(row)
                    # Scroll to the item
                    self._tracks_table.scrollToItem(title_item)
                    break

    def _select_track_by_id(self, track_id: int):
        """
        Select a track by its ID.

        Args:
            track_id: Track ID to select
        """
        # Find the row with the track
        for row in range(self._tracks_table.rowCount()):
            title_item = self._tracks_table.item(row, 0)
            if title_item:
                item_track_id = title_item.data(Qt.UserRole)
                if item_track_id == track_id:
                    # Clear previous selection
                    self._tracks_table.clearSelection()
                    # Select the row
                    self._tracks_table.selectRow(row)
                    break

    def _select_and_scroll_to_current(self):
        """Select and scroll to the currently playing track."""
        if self._current_playing_track_id is not None:
            # Find the row with the current playing track
            for row in range(self._tracks_table.rowCount()):
                title_item = self._tracks_table.item(row, 0)
                if title_item:
                    track_id = title_item.data(Qt.UserRole)
                    if track_id == self._current_playing_track_id:
                        # Clear previous selection and select this row
                        self._tracks_table.clearSelection()
                        self._tracks_table.selectRow(row)
                        # Scroll to the item with center positioning
                        self._tracks_table.scrollToItem(title_item)
                        break

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """Handle item double click."""
        # Get track ID from the first column
        row = item.row()
        title_item = self._tracks_table.item(row, 0)
        if title_item:
            track_id = title_item.data(Qt.UserRole)
            if track_id:
                self.track_double_clicked.emit(track_id)

    def _show_context_menu(self, pos):
        """Show context menu for tracks."""
        item = self._tracks_table.itemAt(pos)
        if not item:
            return

        # Get selected items and check if already favorited
        selected_items = self._tracks_table.selectedItems()
        track_id = None
        for it in selected_items:
            if it.column() == 0:
                track_id = it.data(Qt.UserRole)
                break

        is_favorited = False
        if track_id:
            is_favorited = self._db.is_favorite(track_id)

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

        # Add to queue action
        add_action = menu.addAction("➕ Add to Queue")
        add_action.triggered.connect(lambda: self._add_selected_to_queue())

        # Play action
        play_action = menu.addAction("▶️ Play")
        play_action.triggered.connect(lambda: self._play_selected_track())

        menu.addSeparator()

        # Add to playlist action
        add_to_playlist_action = menu.addAction("📋 Add to Playlist")
        add_to_playlist_action.triggered.connect(lambda: self._add_to_playlist())

        # Favorite action - check if already favorited
        if self._current_view == "favorites" or is_favorited:
            favorite_action = menu.addAction("❌ Remove from Favorites")
        else:
            favorite_action = menu.addAction("⭐ Add to Favorites")
        favorite_action.triggered.connect(lambda: self._toggle_favorite_selected())

        menu.addSeparator()

        # Edit media info action
        edit_action = menu.addAction("✏️ Edit Media Info")
        edit_action.triggered.connect(lambda: self._edit_media_info())

        menu.exec_(self._tracks_table.mapToGlobal(pos))

    def _add_selected_to_queue(self):
        """Add selected tracks to queue."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        track_ids = []
        for item in selected_items:
            # Only process items from the first column to avoid duplicates
            if item.column() == 0:
                track_id = item.data(Qt.UserRole)
                if track_id:
                    track_ids.append(track_id)

        if track_ids:
            self.add_to_queue.emit(track_ids)

    def _play_selected_track(self):
        """Play the first selected track."""
        selected_items = self._tracks_table.selectedItems()
        if not selected_items:
            return

        # Find first item from first column
        for item in selected_items:
            if item.column() == 0:
                track_id = item.data(Qt.UserRole)
                if track_id:
                    self.track_double_clicked.emit(track_id)
                    break

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
            QMessageBox.information(
                self,
                "Added to Favorites",
                f"Added {added_count} track{'s' if added_count > 1 else ''} to favorites",
            )
        elif removed_count > 0 and added_count == 0:
            QMessageBox.information(
                self,
                "Removed from Favorites",
                f"Removed {removed_count} track{'s' if removed_count > 1 else ''} from favorites",
            )
        else:
            QMessageBox.information(
                self,
                "Updated Favorites",
                f"Added {added_count}, removed {removed_count}",
            )

        self.refresh()

    def _add_to_playlist(self):
        """Add selected tracks to a playlist."""
        # Get selected track IDs
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

        # Get all playlists
        playlists = self._db.get_all_playlists()

        if not playlists:
            reply = QMessageBox.question(
                self,
                "No Playlists",
                "You don't have any playlists yet.\nWould you like to create one?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                if hasattr(self, "window()") and self.window():
                    self.window()._nav_playlists.click()
            return

        # If only one playlist, add directly
        if len(playlists) == 1:
            playlist = playlists[0]
            added_count = 0
            duplicate_count = 0
            for track_id in track_ids:
                if self._db.add_track_to_playlist(playlist.id, track_id):
                    added_count += 1
                else:
                    duplicate_count += 1

            if duplicate_count == 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f'Added {added_count} track{"s" if added_count > 1 else ""} to "{playlist.name}"',
                )
            elif added_count == 0:
                QMessageBox.warning(
                    self,
                    "Duplicate",
                    f'All {duplicate_count} track{"s" if duplicate_count > 1 else ""} already in "{playlist.name}"',
                )
            else:
                QMessageBox.information(
                    self,
                    "Partially Added",
                    f"Added {added_count}, skipped {duplicate_count} duplicate{'s' if duplicate_count > 1 else ''}",
                )
            return

        # Create dialog to select playlist
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QListWidget,
            QDialogButtonBox,
        )

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Playlist")
        dialog.setMinimumWidth(400)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #282828;
                color: #ffffff;
            }
            QListWidget {
                background-color: #181818;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                color: #ffffff;
            }
            QListWidget::item:selected {
                background-color: #1db954;
                color: #000000;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)

        layout = QVBoxLayout(dialog)

        label = QLabel(
            f"Add {len(track_ids)} track{'s' if len(track_ids) > 1 else ''} to playlist:"
        )
        layout.addWidget(label)

        playlist_list = QListWidget()
        for playlist in playlists:
            playlist_list.addItem(playlist.name)
        playlist_list.setCurrentRow(0)
        layout.addWidget(playlist_list)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            selected_items = playlist_list.selectedItems()
            if selected_items:
                playlist_name = selected_items[0].text()
                playlist = next((p for p in playlists if p.name == playlist_name), None)
                if playlist:
                    added_count = 0
                    duplicate_count = 0
                    for track_id in track_ids:
                        if self._db.add_track_to_playlist(playlist.id, track_id):
                            added_count += 1
                        else:
                            duplicate_count += 1

                    if duplicate_count == 0:
                        QMessageBox.information(
                            self,
                            "Success",
                            f'Added {added_count} track{"s" if added_count > 1 else ""} to "{playlist_name}"',
                        )
                    elif added_count == 0:
                        QMessageBox.warning(
                            self,
                            "Duplicate",
                            f'All {duplicate_count} track{"s" if duplicate_count > 1 else ""} already in "{playlist_name}"',
                        )
                    else:
                        QMessageBox.information(
                            self,
                            "Partially Added",
                            f"Added {added_count}, skipped {duplicate_count} duplicate{'s' if duplicate_count > 1 else ''}",
                        )

    def _edit_media_info(self):
        """Edit media information for selected track."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QDialogButtonBox,
            QFormLayout,
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
        dialog.setWindowTitle("Edit Media Info")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #282828;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #181818;
                color: #ffffff;
                border: 1px solid #404040;
                border-radius: 4px;
                padding: 8px;
                font-size: 13px;
            }
            QLineEdit:focus {
                border: 1px solid #1db954;
            }
            QPushButton {
                background-color: #1db954;
                color: #000000;
                border: none;
                padding: 8px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton[role="cancel"] {
                background-color: #404040;
                color: #ffffff;
            }
            QPushButton[role="cancel"]:hover {
                background-color: #505050;
            }
        """)

        layout = QVBoxLayout(dialog)

        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        title_input = QLineEdit(track.title or "")
        title_input.setPlaceholderText("Enter title")
        artist_input = QLineEdit(track.artist or "")
        artist_input.setPlaceholderText("Enter artist")
        album_input = QLineEdit(track.album or "")
        album_input.setPlaceholderText("Enter album")

        path_label = QLabel(track.path)
        path_label.setStyleSheet("color: #808080; font-size: 11px;")
        path_label.setWordWrap(True)

        form_layout.addRow("Title:", title_input)
        form_layout.addRow("Artist:", artist_input)
        form_layout.addRow("Album:", album_input)
        form_layout.addRow("File:", path_label)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox()
        ok_button = QPushButton("Save")
        ok_button.setObjectName("saveBtn")
        cancel_button = QPushButton("Cancel")
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
                QMessageBox.information(
                    self, "Success", "Media information saved successfully."
                )
                self.refresh()
            else:
                QMessageBox.warning(self, "Error", "Failed to save media information.")

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

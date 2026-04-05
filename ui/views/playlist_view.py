"""
Playlist view widget for managing playlists.
"""

from typing import TYPE_CHECKING, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QLabel,
    QFileDialog,
)

from domain.playlist import Playlist
from domain.track import Track
from services.playback import PlaybackService
from system.event_bus import EventBus
from system.i18n import t
from ui.dialogs.edit_media_info_dialog import EditMediaInfoDialog
from ui.dialogs.input_dialog import InputDialog
from ui.dialogs.message_dialog import MessageDialog, Yes
from ui.views.playlist_tracks_list_view import PlaylistTracksListView

if TYPE_CHECKING:
    from services.favorites import FavoritesService
    from services.library import LibraryService
    from services.playlist import PlaylistService


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
    """

    track_double_clicked = Signal(int)  # Signal when track is double-clicked (from library view, plays all)
    playlist_track_double_clicked = Signal(int,
                                           int)  # Signal when playlist track is double-clicked (playlist_id, track_id)
    insert_to_queue = Signal(list)  # track IDs
    add_to_queue = Signal(list)  # track IDs
    download_cover_requested = Signal(object)  # Track
    redownload_requested = Signal(object)  # Track

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

        self._export_playlist_btn = QPushButton(t("export_playlist"))
        self._export_playlist_btn.setObjectName("playlistActionBtn")
        self._export_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._export_playlist_btn.setEnabled(False)
        self._export_playlist_btn.clicked.connect(self._export_playlist)
        header_layout.addWidget(self._export_playlist_btn)

        self._import_playlist_btn = QPushButton(t("import_playlist"))
        self._import_playlist_btn.setObjectName("playlistActionBtn")
        self._import_playlist_btn.setCursor(Qt.PointingHandCursor)
        self._import_playlist_btn.clicked.connect(self._import_playlist)
        header_layout.addWidget(self._import_playlist_btn)

        layout.addLayout(header_layout)

        # Tracks list view
        self._tracks_list_view = PlaylistTracksListView()
        layout.addWidget(self._tracks_list_view)

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
        self._tracks_list_view.track_activated.connect(self._on_track_activated)
        self._tracks_list_view.play_requested.connect(self._on_ctx_play)
        self._tracks_list_view.insert_to_queue_requested.connect(self._on_ctx_insert_to_queue)
        self._tracks_list_view.add_to_queue_requested.connect(self._on_ctx_add_to_queue)
        self._tracks_list_view.add_to_playlist_requested.connect(self._on_ctx_add_to_playlist)
        self._tracks_list_view.favorites_toggle_requested.connect(self._on_ctx_favorite_toggle)
        self._tracks_list_view.edit_info_requested.connect(self._on_ctx_edit_info)
        self._tracks_list_view.download_cover_requested.connect(self._on_ctx_download_cover)
        self._tracks_list_view.open_file_location_requested.connect(self._on_ctx_open_file_location)
        self._tracks_list_view.remove_from_library_requested.connect(self._on_ctx_remove_from_library)
        self._tracks_list_view.delete_file_requested.connect(self._on_ctx_delete_file)
        self._tracks_list_view.redownload_requested.connect(self._on_ctx_redownload)
        self._tracks_list_view.remove_from_playlist_requested.connect(self._on_ctx_remove_from_playlist)

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

    def refresh_playlists(self):
        """Public wrapper for refreshing playlist list data."""
        self._refresh_playlists()

    def ensure_default_playlist_selected(self):
        """Select and load the first playlist if none is currently selected."""
        if self._current_playlist_id is not None:
            return
        if self._playlist_list.count() <= 0:
            return
        self._playlist_list.setCurrentRow(0)
        first_item = self._playlist_list.item(0)
        if first_item:
            self._load_playlist(first_item.data(Qt.UserRole))

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
        self._export_playlist_btn.setText(t("export_playlist"))
        self._import_playlist_btn.setText(t("import_playlist"))

    def _create_playlist(self):
        """Create a new playlist."""
        name, ok = InputDialog.getText(
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
        )

        if reply == Yes:
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

        new_name, ok = InputDialog.getText(
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
        self._export_playlist_btn.setEnabled(True)
        tracks = self._playlist_service.get_playlist_tracks(playlist_id)
        self._play_playlist_btn.setEnabled(len(tracks) > 0)

        favorite_ids = self._favorite_service.get_all_favorite_track_ids()
        self._tracks_list_view.load_tracks(tracks, favorite_ids)
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
        self._tracks_list_view.clear()
        self._status_label.setText("")
        self._delete_playlist_btn.setEnabled(False)
        self._rename_playlist_btn.setEnabled(False)
        self._play_playlist_btn.setEnabled(False)
        self._export_playlist_btn.setEnabled(False)

    def _on_track_activated(self, track: Track):
        """Handle track activation from list view."""
        if track and track.id and self._current_playlist_id:
            self.playlist_track_double_clicked.emit(self._current_playlist_id, track.id)

    def _on_ctx_play(self, tracks: list):
        from domain import PlaylistItem
        items = [PlaylistItem.from_track(track) for track in tracks if track.id]
        if items:
            self._player.engine.load_playlist_items(items)
            self._player.engine.play()

    def _on_ctx_insert_to_queue(self, tracks: list):
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self.insert_to_queue.emit(track_ids)

    def _on_ctx_add_to_queue(self, tracks: list):
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            self.add_to_queue.emit(track_ids)

    def _on_ctx_add_to_playlist(self, tracks: list):
        from utils.playlist_utils import add_tracks_to_playlist
        track_ids = [t.id for t in tracks if t.id]
        if track_ids:
            add_tracks_to_playlist(self, self._library_service, track_ids, "[PlaylistView]")

    def _on_ctx_favorite_toggle(self, tracks: list, all_favorited: bool):
        bus = EventBus.instance()
        for track in tracks:
            if not track.id:
                continue
            if all_favorited:
                self._favorite_service.remove_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, False, is_cloud=False)
            else:
                self._favorite_service.add_favorite(track_id=track.id)
                bus.emit_favorite_change(track.id, True, is_cloud=False)

    def _on_ctx_edit_info(self, track):
        if not track or not track.id:
            return
        dialog = EditMediaInfoDialog([track.id], self._library_service, self)
        dialog.tracks_updated.connect(self._on_tracks_updated)
        dialog.exec()

    def _on_ctx_download_cover(self, track):
        if not track or not track.id:
            return
        self.download_cover_requested.emit(track)

    def _on_ctx_open_file_location(self, track):
        if not track or not track.path or not track.path.strip():
            MessageDialog.warning(self, "Error", t("no_local_file"))
            return
        from pathlib import Path
        import subprocess
        import sys
        file_path = Path(track.path)
        if not file_path.exists():
            MessageDialog.warning(self, "Error", t("file_not_found"))
            return
        if sys.platform == 'darwin':
            subprocess.Popen(['open', '-R', str(file_path)])
        elif sys.platform == 'win32':
            subprocess.Popen(f'explorer /select,"{file_path}"')
        else:
            subprocess.Popen(['xdg-open', str(file_path.parent)])

    def _on_ctx_remove_from_library(self, tracks: list):
        from utils import format_count_message
        track_ids = [t.id for t in tracks if t.id]
        if not track_ids:
            return
        confirm_message = format_count_message("remove_from_library_confirm", len(track_ids))
        reply = MessageDialog.question(self, t("remove_from_library"), confirm_message)
        if reply == Yes:
            removed_count = 0
            for track_id in track_ids:
                if self._library_service.remove_track(track_id):
                    removed_count += 1
            if removed_count > 0:
                success_message = format_count_message("remove_from_library_success", removed_count)
                MessageDialog.information(self, t("remove_from_library"), success_message)
                self._load_playlist(self._current_playlist_id)

    def _on_ctx_delete_file(self, tracks: list):
        from utils import format_count_message
        from pathlib import Path
        confirm_message = format_count_message("delete_file_confirm", len(tracks))
        reply = MessageDialog.question(self, t("delete_file"), confirm_message)
        if reply == Yes:
            for track in tracks:
                if track.path and Path(track.path).exists():
                    try:
                        Path(track.path).unlink()
                        if track.id:
                            self._library_service.remove_track(track.id)
                    except OSError as e:
                        MessageDialog.warning(self, "Error", str(e))
            self._load_playlist(self._current_playlist_id)

    def _on_ctx_redownload(self, track):
        if not track or not track.id:
            return
        self.redownload_requested.emit(track)

    def _on_ctx_remove_from_playlist(self, tracks: list):
        if self._current_playlist_id is None:
            return
        for track in tracks:
            if track.id:
                self._playlist_service.remove_track_from_playlist(self._current_playlist_id, track.id)
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
            playlist = self._playlist_service.get_playlist(self._current_playlist_id)
            playlist_name = playlist.name if playlist else ""
            MessageDialog.information(
                self, t("success"), t("added_tracks_to_playlist").format(count=1, name=playlist_name)
            )
        else:
            MessageDialog.warning(self, "Error", t("track_already_in_playlist"))

    def _on_tracks_updated(self, track_ids: List[int]):
        """Handle tracks updated event from EditMediaInfoDialog."""
        del track_ids
        if self._current_playlist_id:
            self._load_playlist(self._current_playlist_id)

    def _import_playlist(self):
        """Import playlist from an M3U file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, t("import_playlist"), "", "M3U Files (*.m3u);;All Files (*)"
        )
        if not file_path:
            return

        playlist_name, ok = InputDialog.getText(
            self, t("import_playlist"), t("enter_playlist_name")
        )
        if not ok or not playlist_name:
            return

        try:
            imported = self._playlist_service.import_m3u(file_path, playlist_name)
            if imported > 0:
                self._refresh_playlists()
                # Select the new playlist
                playlists = self._playlist_service.get_all_playlists()
                for p in playlists:
                    if p.name == playlist_name:
                        for i in range(self._playlist_list.count()):
                            item = self._playlist_list.item(i)
                            if item.data(Qt.UserRole) == p.id:
                                self._playlist_list.setCurrentItem(item)
                                self._load_playlist(p.id)
                                break
                        break
                MessageDialog.information(
                    self, t("import_playlist"),
                    t("playlist_imported").format(count=imported, name=playlist_name)
                )
            else:
                MessageDialog.warning(
                    self, t("import_playlist"), t("no_valid_tracks_found")
                )
        except FileNotFoundError:
            MessageDialog.warning(self, t("error"), t("file_not_found"))
        except Exception as e:
            MessageDialog.warning(self, t("error"), str(e))

    def _export_playlist(self):
        """Export the current playlist to an M3U file."""
        if self._current_playlist_id is None:
            return

        playlist = self._playlist_service.get_playlist(self._current_playlist_id)
        if not playlist:
            return

        default_name = f"{playlist.name}.m3u"
        file_path, _ = QFileDialog.getSaveFileName(
            self, t("export_playlist"), default_name, "M3U Files (*.m3u);;All Files (*)"
        )
        if not file_path:
            return

        if not file_path.endswith('.m3u'):
            file_path += '.m3u'

        try:
            exported = self._playlist_service.export_m3u(self._current_playlist_id, file_path)
            MessageDialog.information(
                self, t("export_playlist"),
                t("playlist_exported").format(count=exported, name=playlist.name)
            )
        except Exception as e:
            MessageDialog.warning(self, t("error"), str(e))

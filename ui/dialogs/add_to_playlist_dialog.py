"""
Dialog for adding tracks to a playlist.
"""
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QDialogButtonBox,
    QPushButton,
)

from ui.dialogs.message_dialog import MessageDialog, Yes, No
from PySide6.QtCore import Qt

from system.i18n import t
from system.theme import ThemeManager


class AddToPlaylistDialog(QDialog):
    """Dialog for selecting a playlist to add tracks to."""

    _STYLE_TEMPLATE = """
        QDialog {
            background-color: %background_alt%;
            color: %text%;
        }
        QLabel {
            color: %text%;
            font-size: 13px;
        }
        QListWidget {
            background-color: %background%;
            border: 1px solid %border%;
            border-radius: 4px;
        }
        QListWidget::item {
            color: %text%;
        }
        QListWidget::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
        QPushButton {
            background-color: %highlight%;
            color: %background%;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: %highlight_hover%;
        }
    """

    def __init__(self, library_service, parent=None):
        """
        Initialize the dialog.

        Args:
            library_service: Library service for database access
            parent: Parent widget
        """
        super().__init__(parent)
        self._library_service = library_service
        self._track_ids = []

        self._setup_ui()
        ThemeManager.instance().register_widget(self)

    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle(t("select_playlist"))
        self.setMinimumWidth(400)
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        layout = QVBoxLayout(self)

        # Message label
        self._label = QLabel(t("select_playlist"))
        layout.addWidget(self._label)

        # Playlist list
        self._playlist_list = QListWidget()
        self._playlist_list.setSpacing(4)
        self._playlist_list.setCurrentRow(0)
        layout.addWidget(self._playlist_list)

        # Buttons
        self._buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        layout.addWidget(self._buttons)

        # Load playlists
        self._load_playlists()

    def _load_playlists(self):
        """Load playlists from database."""
        self.playlists = self._library_service.get_all_playlists()
        for playlist in self.playlists:
            self._playlist_list.addItem(playlist.name)
        if self._playlist_list.count() > 0:
            self._playlist_list.setCurrentRow(0)

    def set_track_ids(self, track_ids: list):
        """
        Set the track IDs to add.

        Args:
            track_ids: List of track IDs
        """
        self._track_ids = track_ids
        s = "s" if len(track_ids) > 1 else ""
        self._label.setText(
            t("add_to_playlist_message")
            .replace("{count}", str(len(track_ids)))
            .replace("{s}", s)
        )

    def set_tracks(self, tracks: list):
        """
        Set the tracks to add.

        Args:
            tracks: List of Track objects
        """
        track_ids = [t.id for t in tracks if t.id]
        self.set_track_ids(track_ids)

    def get_selected_playlist(self):
        """Get the selected playlist name."""
        selected_items = self._playlist_list.selectedItems()
        if selected_items:
            playlist_name = selected_items[0].text()
            return next((p for p in self.playlists if p.name == playlist_name), None)
        return None

    def get_track_ids(self):
        """Get the track IDs to add."""
        return self._track_ids

    def has_playlists(self):
        """Check if there are any playlists."""
        return self._playlist_list.count() > 0

    def has_single_playlist(self):
        """Check if there is exactly one playlist."""
        return self._playlist_list.count() == 1

    def get_single_playlist(self):
        """Get the single playlist name if there's only one."""
        if self._playlist_list.count() == 1:
            playlist_name = self._playlist_list.item(0).text()
            return next((p for p in self.playlists if p.name == playlist_name), None)
        return None

    def show_no_playlists_prompt(self):
        """Show prompt when no playlists exist."""
        reply = MessageDialog.question(
            self,
            t("no_playlists"),
            t("no_playlists_message"),
            MessageDialog.Yes | MessageDialog.No,
        )
        return reply == MessageDialog.Yes

    def refresh_theme(self):
        """Refresh theme when changed."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

"""
Dialog for adding tracks to a playlist.
"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath, QRegion
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QGraphicsDropShadowEffect,
    QWidget,
    QHBoxLayout,
)

from system.i18n import t
from system.theme import ThemeManager
from ui.dialogs.draggable_dialog_mixin import DraggableDialogMixin
from ui.dialogs.dialog_title_bar import setup_equalizer_title_layout
from ui.dialogs.message_dialog import MessageDialog, Yes, No


class AddToPlaylistDialog(DraggableDialogMixin, QDialog):
    """Dialog for selecting a playlist to add tracks to."""

    _STYLE_TEMPLATE = """
        QListWidget {
            background-color: %background%;
            border: 1px solid %border%;
            border-radius: 6px;
            padding: 4px;
        }
        QListWidget::item {
            color: %text%;
            padding: 8px;
            border-radius: 4px;
        }
        QListWidget::item:selected {
            background-color: %highlight%;
            color: %background%;
        }
        QListWidget::item:hover {
            background-color: %background_hover%;
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
        self._drag_pos = None

        self.setWindowFlags(Qt.WindowType.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(420, 320)
        self.setMaximumWidth(520)
        self.setWindowTitle(t("select_playlist"))

        self._setup_shadow()
        self._setup_ui()
        self._apply_style()
        ThemeManager.instance().register_widget(self)

    def _setup_shadow(self):
        """Setup drop shadow effect."""
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(30)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _setup_ui(self):
        """Setup the user interface."""
        # Outer layout with 0 margins — container fills the dialog
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        container = QWidget()
        container.setObjectName("dialogContainer")
        outer.addWidget(container)

        container_layout = QVBoxLayout(container)
        layout, self._title_bar_controller = setup_equalizer_title_layout(
            self,
            container_layout,
            t("select_playlist"),
        )

        # Message label
        self._label = QLabel(t("select_playlist"))
        self._label.setObjectName("dialogLabel")
        layout.addWidget(self._label)

        # Playlist list
        self._playlist_list = QListWidget()
        self._playlist_list.setSpacing(4)
        self._playlist_list.setCurrentRow(0)
        layout.addWidget(self._playlist_list)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton(t("cancel"))
        cancel_btn.setProperty("role", "cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton(t("ok"))
        ok_btn.setProperty("role", "primary")
        ok_btn.clicked.connect(self.accept)
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

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
            Yes | No,
        )
        return reply == Yes

    def _apply_style(self):
        """Apply themed stylesheet."""
        self.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

    def refresh_theme(self):
        """Refresh theme when changed."""
        self._apply_style()
        self._title_bar_controller.refresh_theme()

    def resizeEvent(self, event):
        """Handle resize to apply rounded mask."""
        path = QPainterPath()
        path.addRoundedRect(self.rect(), 12, 12)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))
        super().resizeEvent(event)

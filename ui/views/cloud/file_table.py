"""
Cloud file table widget for displaying files from cloud storage.
"""

from typing import List, Optional, TYPE_CHECKING

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from domain.cloud import CloudFile
from utils import format_duration
from system.i18n import t

if TYPE_CHECKING:
    from domain.playback import PlaybackState
    from services.playback import PlaybackService


class CloudFileTable(QWidget):
    """
    Table widget for displaying cloud files.

    Features:
    - Display folders and audio files
    - Show playing status indicator
    - Double-click handling for navigation and playback
    """

    _STYLE_TEMPLATE = """
        QTableWidget#cloudFileTable {
            background-color: %background%;
            border: none;
            border-radius: 8px;
            gridline-color: %background_hover%;
        }
        QTableWidget#cloudFileTable::item {
            padding: 12px 8px;
            color: %text%;
            border: none;
            border-bottom: 1px solid %background_hover%;
        }
        /* Alternating row colors for better readability */
        QTableWidget#cloudFileTable::item:alternate {
            background-color: %background_alt%;
        }
        QTableWidget#cloudFileTable::item:!alternate {
            background-color: %background%;
        }
        /* Selected state with vibrant accent */
        QTableWidget#cloudFileTable::item:selected {
            background-color: %highlight%;
            color: #ffffff;
            font-weight: 500;
        }
        QTableWidget#cloudFileTable::item:selected:!alternate {
            background-color: %highlight%;
        }
        QTableWidget#cloudFileTable::item:selected:alternate {
            background-color: %highlight_hover%;
        }
        /* Hover effect for interactivity */
        QTableWidget#cloudFileTable::item:hover {
            background-color: %background_hover%;
        }
        QTableWidget#cloudFileTable::item:selected:hover {
            background-color: %highlight_hover%;
        }
        /* Remove focus outline */
        QTableWidget#cloudFileTable::item:focus {
            outline: none;
            border: none;
        }
        QTableWidget#cloudFileTable:focus {
            outline: none;
            border: none;
        }
        /* Header styling */
        QTableWidget#cloudFileTable QHeaderView::section {
            background-color: %background_hover%;
            color: %highlight%;
            padding: 14px 12px;
            border: none;
            border-bottom: 2px solid %highlight%;
            border-radius: 0px;
            font-weight: bold;
            font-size: 13px;
            letter-spacing: 0.5px;
        }
        /* First header (top-left corner) */
        QTableWidget#cloudFileTable QTableCornerButton::section {
            background-color: %background_hover%;
            border: none;
            border-right: 1px solid %border%;
            border-bottom: 2px solid %highlight%;
        }
        /* Scrollbar styling */
        QTableWidget#cloudFileTable QScrollBar:vertical {
            background-color: %background%;
            width: 12px;
            border-radius: 6px;
            margin: 0px;
        }
        QTableWidget#cloudFileTable QScrollBar::handle:vertical {
            background-color: %border%;
            border-radius: 6px;
            min-height: 40px;
        }
        QTableWidget#cloudFileTable QScrollBar::handle:vertical:hover {
            background-color: %background_hover%;
        }
        QTableWidget#cloudFileTable QScrollBar:horizontal {
            background-color: %background%;
            height: 12px;
            border-radius: 6px;
        }
        QTableWidget#cloudFileTable QScrollBar::handle:horizontal {
            background-color: %border%;
            border-radius: 6px;
            min-width: 40px;
        }
        QTableWidget#cloudFileTable QScrollBar::handle:horizontal:hover {
            background-color: %background_hover%;
        }
        QTableWidget#cloudFileTable QScrollBar::add-line, QScrollBar::sub-line {
            height: 0px;
            width: 0px;
        }
    """

    # Signals
    folder_double_clicked = Signal(CloudFile)  # User double-clicked a folder
    audio_double_clicked = Signal(CloudFile)  # User double-clicked an audio file
    context_menu_requested = Signal(object, CloudFile)  # (position, file)

    def __init__(self, parent=None):
        """Initialize the file table widget."""
        super().__init__(parent)
        self._current_playing_file_id: Optional[str] = None
        self._player: Optional["PlaybackService"] = None

        # Register for theme change notifications
        from system.theme import ThemeManager
        ThemeManager.instance().register_widget(self)

        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create table
        self._table = QTableWidget()
        self._table.setObjectName("cloudFileTable")
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels([
            t("title"), t("type"), t("size"), t("duration"), "⬇"
        ])

        # Configure table
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setFocusPolicy(Qt.NoFocus)
        self._table.cellDoubleClicked.connect(self._on_double_click)

        # Apply style matching library table
        from system.theme import ThemeManager
        self._table.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

        # Set column widths
        header = self._table.horizontalHeader()
        # Name: stretch to fill
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        # Type: fixed
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        self._table.setColumnWidth(1, 80)
        # Size: fixed
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self._table.setColumnWidth(2, 100)
        # Duration: fixed
        header.setSectionResizeMode(3, QHeaderView.Fixed)
        self._table.setColumnWidth(3, 80)
        # Status: fixed
        header.setSectionResizeMode(4, QHeaderView.Fixed)
        self._table.setColumnWidth(4, 50)

        layout.addWidget(self._table)

    def set_player(self, player: "PlaybackService"):
        """Set the player service for playback state queries."""
        self._player = player

    def populate(self, files: List[CloudFile], current_playing_file_id: str = None):
        """
        Populate the table with files.

        Args:
            files: List of CloudFile objects
            current_playing_file_id: Currently playing file ID for indicator
        """
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        self._current_playing_file_id = current_playing_file_id
        self._table.setRowCount(0)
        self._table.setUpdatesEnabled(False)

        try:
            for row, file in enumerate(files):
                self._table.insertRow(row)

                # Check if this file is currently playing
                is_currently_playing = (
                    current_playing_file_id and
                    file.file_id == current_playing_file_id and
                    file.file_type == "audio"
                )

                # Name column
                name_item = QTableWidgetItem(file.name)
                name_item.setData(Qt.UserRole, file)
                name_item.setForeground(QBrush(QColor(theme.text)))

                if file.file_type == "folder":
                    name_item.setText(f"📁 {file.name}")
                elif is_currently_playing:
                    name_item = self._add_playing_indicator(name_item, file.name)

                self._table.setItem(row, 0, name_item)

                # Type column
                type_item = QTableWidgetItem(self._get_file_type_label(file.file_type))
                type_item.setForeground(QBrush(QColor(theme.text_secondary)))
                self._table.setItem(row, 1, type_item)

                # Size column
                size_text = ""
                if file.size:
                    size_mb = file.size / (1024 * 1024)
                    size_text = f"{size_mb:.1f} MB"
                size_item = QTableWidgetItem(size_text)
                size_item.setForeground(QBrush(QColor(theme.text_secondary)))
                self._table.setItem(row, 2, size_item)

                # Duration column
                duration_text = ""
                if file.file_type == "audio" and file.duration:
                    duration_text = format_duration(file.duration)
                duration_item = QTableWidgetItem(duration_text)
                duration_item.setForeground(QBrush(QColor(theme.text_secondary)))
                self._table.setItem(row, 3, duration_item)

                # Status column (downloaded indicator)
                status_text = "✓" if file.local_path else ""
                status_item = QTableWidgetItem(status_text)
                status_item.setForeground(QBrush(QColor(theme.highlight)))
                status_item.setTextAlignment(Qt.AlignCenter)
                self._table.setItem(row, 4, status_item)

        finally:
            self._table.setUpdatesEnabled(True)

    def _add_playing_indicator(self, item: QTableWidgetItem, name: str) -> QTableWidgetItem:
        """Add playing indicator to the name item."""
        from domain.playback import PlaybackState
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        if self._player and hasattr(self._player, 'engine'):
            if self._player.engine.state == PlaybackState.PLAYING:
                item.setText(f"▶ {name}")
            else:
                item.setText(f"⏸ {name}")
        else:
            item.setText(f"▶ {name}")

        # Set bold and green color
        font = item.font()
        font.setBold(True)
        item.setFont(font)
        item.setForeground(QBrush(QColor(theme.highlight)))

        return item

    def _get_file_type_label(self, file_type: str) -> str:
        """Get display label for file type."""
        labels = {"folder": t("folder"), "audio": t("audio"), "other": t("file")}
        return labels.get(file_type, t("file"))

    def _on_double_click(self, row: int, column: int):
        """Handle double-click on table item."""
        item = self._table.item(row, 0)
        if not item:
            return

        file = item.data(Qt.UserRole)
        if not file:
            return

        if file.file_type == "folder":
            self.folder_double_clicked.emit(file)
        elif file.file_type == "audio":
            self.audio_double_clicked.emit(file)

    def _on_context_menu(self, pos):
        """Handle context menu request."""
        item = self._table.itemAt(pos)
        if not item:
            return

        file = item.data(Qt.UserRole)
        if file:
            self.context_menu_requested.emit(pos, file)

    def update_playing_status(self, file_id: str, is_playing: bool):
        """
        Update the playing status indicator for a file.

        Args:
            file_id: File ID to update
            is_playing: Whether the file is currently playing
        """
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        self._current_playing_file_id = file_id if is_playing else None

        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if not item:
                continue

            file = item.data(Qt.UserRole)
            if not file:
                continue

            # Reset all items first
            if file.file_type == "audio":
                if file.file_id == file_id and is_playing:
                    # Set playing indicator
                    self._add_playing_indicator(item, file.name)
                else:
                    # Reset to normal
                    item.setText(file.name)
                    item.setForeground(QBrush(QColor(theme.text)))
                    font = item.font()
                    font.setBold(False)
                    item.setFont(font)

    def update_file_local_path(self, file_id: str, local_path: str):
        """
        Update the local path for a file and show download indicator.

        Args:
            file_id: File ID to update
            local_path: New local path
        """
        from system.theme import ThemeManager
        theme = ThemeManager.instance().current_theme

        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if not item:
                continue

            file = item.data(Qt.UserRole)
            if file and file.file_id == file_id:
                # Update the file object
                file.local_path = local_path

                # Update status column
                status_item = self._table.item(row, 4)
                if status_item:
                    status_item.setText("✓")
                    status_item.setForeground(QBrush(QColor(theme.highlight)))
                break

    def get_current_files(self) -> List[CloudFile]:
        """Get all files currently displayed in the table."""
        files = []
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                file = item.data(Qt.UserRole)
                if file:
                    files.append(file)
        return files

    def select_and_scroll_to_file(self, file_id: str):
        """Select and scroll to a file in the table."""
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item:
                file = item.data(Qt.UserRole)
                if file and file.file_id == file_id:
                    self._table.selectRow(row)
                    self._table.scrollToItem(item)
                    break

    def clear(self):
        """Clear the table."""
        self._table.setRowCount(0)
        self._current_playing_file_id = None

    def refresh_ui(self):
        """Refresh UI texts for language change."""
        # Update header labels
        self._table.setHorizontalHeaderLabels([
            t("title"), t("type"), t("size"), t("duration"), "⬇"
        ])

    def refresh_theme(self):
        """Apply themed styles using ThemeManager tokens."""
        from system.theme import ThemeManager
        self._table.setStyleSheet(ThemeManager.instance().get_qss(self._STYLE_TEMPLATE))

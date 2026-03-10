"""
Cloud drive view for browsing and playing cloud files.
"""

import logging

# Configure logging
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('[%(levelname)s] %(name)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QStackedWidget,
    QMessageBox,
    QMenu,
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QSplitter,
    QApplication,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QCursor, QColor, QBrush
from typing import List, Optional
import tempfile
import os
from database.models import CloudAccount, CloudFile
from services.quark_drive_service import QuarkDriveService
from ui.cloud_login_dialog import CloudLoginDialog
from utils import t, format_duration
from utils.event_bus import EventBus


class CloudDriveView(QWidget):
    """View for browsing and playing cloud drive files"""

    track_double_clicked = Signal(str)  # Signal for playing track (temp file path)
    play_cloud_files = Signal(
        str, int, list, float
    )  # Signal for playing multiple cloud files (temp_path, index, cloud_files, start_position)

    def __init__(self, db_manager, player, config_manager=None, parent=None):
        super().__init__(parent)
        self._db = db_manager
        self._player = player
        self._config_manager = config_manager
        self._current_account: Optional[CloudAccount] = None
        self._current_parent_id = "0"  # Root folder
        self._parent_dir_id = None  # Parent directory ID for back navigation
        self._navigation_history = []  # Navigation stack for multi-level back: [(parent_id, path), ...]
        self._current_audio_files = []  # Track audio files in current folder
        self._last_playing_fid = ""  # Last playing file ID from database
        self._last_position = 0.0  # Last playback position from database
        self._fid_path = []  # List of folder IDs in current path (e.g., ["0", "fid1", "fid2"])
        self._current_playing_file_id = ""  # Currently playing file ID

        self._setup_ui()
        self._load_accounts()

        # Connect to EventBus for download completion (for auto-play next track)
        self._event_bus = EventBus.instance()
        self._event_bus.download_started.connect(self._on_event_bus_download_started)
        self._event_bus.download_completed.connect(self._on_event_bus_download_completed)

        # Connect to EventBus for track changes (to highlight current playing)
        self._event_bus.track_changed.connect(self._on_track_changed)
        self._event_bus.playback_state_changed.connect(self._on_playback_state_changed)

    def _setup_ui(self):
        """Setup UI components"""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for account list and file list
        splitter = QSplitter(Qt.Horizontal)

        # Left side - account list
        account_list_widget = self._create_account_list()
        splitter.addWidget(account_list_widget)

        # Right side - file list content
        file_content = self._create_file_content()
        splitter.addWidget(file_content)

        splitter.setStretchFactor(0, 1)  # Account list gets 1/4
        splitter.setStretchFactor(1, 3)  # File list gets 3/4

        layout.addWidget(splitter)

        # Apply styles
        self._apply_styles()

    def _create_account_list(self) -> QWidget:
        """Create the account list widget."""
        widget = QWidget()
        widget.setObjectName("accountListPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(15, 20, 15, 10)
        layout.setSpacing(10)

        # Title
        self._account_list_title = QLabel("☁️ " + t("accounts"))
        self._account_list_title.setStyleSheet("""
            color: #1db954;
            font-size: 20px;
            font-weight: bold;
            margin-bottom: 10px;
        """)
        layout.addWidget(self._account_list_title)

        # Add account button
        self._add_account_btn = QPushButton(t("add_account"))
        self._add_account_btn.setObjectName("addAccountBtn")
        self._add_account_btn.setCursor(Qt.PointingHandCursor)
        self._add_account_btn.clicked.connect(self._add_account)
        layout.addWidget(self._add_account_btn)

        # Account list
        self._account_list = QListWidget()
        self._account_list.setObjectName("accountList")
        self._account_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._account_list.setAlternatingRowColors(True)
        self._account_list.itemClicked.connect(self._on_account_selected)
        self._account_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self._account_list.customContextMenuRequested.connect(
            self._show_account_context_menu
        )
        layout.addWidget(self._account_list)

        return widget

    def _create_file_content(self) -> QWidget:
        """Create the file content widget."""
        widget = QWidget()
        widget.setObjectName("fileContentPanel")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(20, 20, 20, 10)
        layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        self._account_title = QLabel(t("select_account"))
        self._account_title.setStyleSheet("""
            color: #1db954;
            font-size: 24px;
            font-weight: bold;
        """)
        header_layout.addWidget(self._account_title)

        header_layout.addStretch()

        # Navigation button
        self._back_btn = QPushButton("← " + t("back"))
        self._back_btn.setObjectName("backBtn")
        self._back_btn.setCursor(Qt.PointingHandCursor)
        self._back_btn.setEnabled(False)
        self._back_btn.clicked.connect(self._navigate_back)
        header_layout.addWidget(self._back_btn)

        # Path label
        self._path_label = QLabel("/")
        self._path_label.setStyleSheet("""
            color: #c0c0c0;
            font-size: 14px;
            padding: 0 10px;
        """)
        header_layout.addWidget(self._path_label)

        layout.addLayout(header_layout)

        # Stacked widget for different states
        self._stack = QStackedWidget()

        # Empty state page
        empty_page = QWidget()
        empty_layout = QVBoxLayout()
        empty_label = QLabel(t("add_cloud_account"))
        empty_label.setObjectName("emptyLabel")
        empty_label.setAlignment(Qt.AlignCenter)
        empty_label.setStyleSheet("color: #808080; font-size: 14px;")
        empty_layout.addWidget(empty_label)
        empty_page.setLayout(empty_layout)
        self._stack.addWidget(empty_page)

        # File browser page
        browser_page = QWidget()
        browser_layout = QVBoxLayout()

        # File table with same styling as LibraryView
        self._file_table = QTableWidget()
        self._file_table.setObjectName("cloudFilesTable")
        self._file_table.setColumnCount(4)
        self._file_table.setHorizontalHeaderLabels([t("title"), t("type"), t("size"), t("duration")])

        # Configure table to match LibraryView
        self._file_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._file_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self._file_table.setAlternatingRowColors(True)
        self._file_table.verticalHeader().setVisible(False)

        # Set column resize modes - Title gets all remaining space
        header = self._file_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Title column stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Type auto-size
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Size auto-size
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Duration auto-size

        self._file_table.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._file_table.setContextMenuPolicy(Qt.CustomContextMenu)
        self._file_table.customContextMenuRequested.connect(self._show_context_menu)
        self._file_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._file_table.setFocusPolicy(Qt.NoFocus)

        browser_layout.addWidget(self._file_table)

        browser_page.setLayout(browser_layout)
        self._stack.addWidget(browser_page)

        layout.addWidget(self._stack)

        # Status bar
        self._status_label = QLabel("")
        self._status_label.setStyleSheet(
            "color: #808080; font-size: 13px; padding: 8px 0px;"
        )
        layout.addWidget(self._status_label)

        return widget

    def _apply_styles(self):
        """Apply modern widget styles."""
        self.setStyleSheet("""
            QWidget#accountListPanel {
                background-color: #141414;
                border-right: 1px solid #2a2a2a;
            }
            QWidget#fileContentPanel {
                background-color: #141414;
            }
            QPushButton#addAccountBtn {
                background: #1db954;
                color: #000000;
                border: none;
                padding: 10px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
            }
            QPushButton#addAccountBtn:hover {
                background: #1ed760;
            }
            QPushButton#backBtn {
                background: transparent;
                border: 2px solid #404040;
                color: #c0c0c0;
                padding: 8px 15px;
                border-radius: 6px;
                font-weight: 500;
            }
            QPushButton#backBtn:hover {
                border-color: #1db954;
                color: #1db954;
                background-color: rgba(29, 185, 84, 0.1);
            }
            QPushButton#backBtn:disabled {
                border-color: #2a2a2a;
                color: #404040;
            }
            QListWidget#accountList {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget#accountList::item {
                padding: 12px 16px;
                color: #e0e0e0;
                border-radius: 4px;
                margin: 2px 0;
            }
            QListWidget#accountList::item:selected {
                background-color: #1db954;
                color: #000000;
                font-weight: 600;
            }
            QListWidget#accountList::item:hover {
                background-color: #2a2a2a;
            }
            QListWidget#accountList::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#cloudFilesTable {
                background-color: #1e1e1e;
                border: none;
                border-radius: 8px;
                gridline-color: #2a2a2a;
            }
            QTableWidget#cloudFilesTable::item {
                padding: 12px 8px;
                color: #e0e0e0;
                border: none;
                border-bottom: 1px solid #2a2a2a;
            }
            QTableWidget#cloudFilesTable::item:alternate {
                background-color: #252525;
            }
            QTableWidget#cloudFilesTable::item:!alternate {
                background-color: #1e1e1e;
            }
            QTableWidget#cloudFilesTable::item:selected {
                background-color: #1db954;
                color: #ffffff;
                font-weight: 500;
            }
            QTableWidget#cloudFilesTable::item:selected:!alternate {
                background-color: #1db954;
            }
            QTableWidget#cloudFilesTable::item:selected:alternate {
                background-color: #1ed760;
            }
            QTableWidget#cloudFilesTable::item:hover {
                background-color: #2d2d2d;
            }
            QTableWidget#cloudFilesTable::item:selected:hover {
                background-color: #1ed760;
            }
            QTableWidget#cloudFilesTable::item:focus {
                outline: none;
                border: none;
            }
            QTableWidget#cloudFilesTable:focus {
                outline: none;
                border: none;
            }
            QTableWidget#cloudFilesTable QHeaderView::section {
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
            QTableWidget#cloudFilesTable QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:vertical {
                background-color: #404040;
                border-radius: 6px;
                min-height: 40px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:vertical:hover {
                background-color: #505050;
            }
            QTableWidget#cloudFilesTable QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                border-radius: 6px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:horizontal {
                background-color: #404040;
                border-radius: 6px;
                min-width: 40px;
            }
            QTableWidget#cloudFilesTable QScrollBar::handle:horizontal:hover {
                background-color: #505050;
            }
            QTableWidget#cloudFilesTable QScrollBar::add-line, QScrollBar::sub-line {
                height: 0px;
                width: 0px;
            }
        """)

    def _load_accounts(self):
        """Load available cloud accounts and auto-select the last used account."""
        accounts = self._db.get_cloud_accounts(provider="quark")
        self._populate_account_list(accounts)

        # Auto-select the first account to restore last session
        if accounts and not self._current_account:
            # Select the first account in the list
            first_item = self._account_list.item(0)
            if first_item:
                account = first_item.data(Qt.UserRole)
                if account:
                    self._account_list.setCurrentItem(first_item)
                    self._current_account = account

                    # Restore last saved folder path
                    saved_path = account.last_folder_path if account.last_folder_path else "/"
                    self._path_label.setText(saved_path)

                    # Restore fid_path
                    if account.last_fid_path and account.last_fid_path != "0":
                        # Parse fid_path string like "/fid1/fid2/fid3" into list
                        self._fid_path = account.last_fid_path.strip("/").split("/")
                        if self._fid_path == [""]:
                            self._fid_path = []
                    else:
                        self._fid_path = []

                    # Current folder ID is the last item in fid_path, or "0" if empty
                    if self._fid_path:
                        self._current_parent_id = self._fid_path[-1]
                    else:
                        self._current_parent_id = "0"

                    # Clear navigation history
                    self._navigation_history.clear()

                    # Enable back button if not at root
                    can_go_back = len(self._fid_path) > 0
                    self._back_btn.setEnabled(can_go_back)

                    # Store last playing state for later restoration (but don't auto-restore)
                    self._last_playing_fid = account.last_playing_fid
                    self._last_position = account.last_position

                    # Load files for the restored folder
                    self._update_file_view()

                    # NOTE: Playback restoration is handled by MainWindow._restore_playback_state()
                    # Do not auto-restore here to avoid conflicts

    def _populate_account_list(self, accounts: List[CloudAccount]):
        """Populate the account list widget."""
        self._account_list.clear()

        for account in accounts:
            item = QListWidgetItem(account.account_name)
            item.setData(Qt.UserRole, account)

            # Set as selected if it's the current account
            if self._current_account and account.id == self._current_account.id:
                self._account_list.setCurrentItem(item)

            self._account_list.addItem(item)

        # Update status
        if not accounts:
            self._stack.setCurrentIndex(0)  # Show empty
        else:
            self._stack.setCurrentIndex(1)  # Show browser

    def _on_account_selected(self, item: QListWidgetItem):
        """Handle account selection."""
        account = item.data(Qt.UserRole)
        if account:
            self._current_account = account

            # Restore last saved folder path
            saved_path = account.last_folder_path if account.last_folder_path else "/"
            self._path_label.setText(saved_path)

            # Restore fid_path
            if account.last_fid_path and account.last_fid_path != "0":
                # Parse fid_path string like "/fid1/fid2/fid3" into list
                self._fid_path = account.last_fid_path.strip("/").split("/")
                if self._fid_path == [""]:
                    self._fid_path = []
            else:
                self._fid_path = []

            # Current folder ID is the last item in fid_path, or "0" if empty
            if self._fid_path:
                self._current_parent_id = self._fid_path[-1]
            else:
                self._current_parent_id = "0"

            # Clear navigation history when switching accounts
            self._navigation_history.clear()

            # Enable back button if not at root
            can_go_back = len(self._fid_path) > 0
            self._back_btn.setEnabled(can_go_back)

            # Store last playing state for later restoration
            self._last_playing_fid = account.last_playing_fid
            self._last_position = account.last_position

            self._update_file_view()

            # Try to restore playback after files are loaded
            if account.last_playing_fid:
                QTimer.singleShot(1000, self._restore_playback)

    def _update_file_view(self):
        """Update the file view based on current account."""
        if not self._current_account:
            self._account_title.setText(t("select_account"))
            self._stack.setCurrentIndex(0)
            return

        # Update title
        self._account_title.setText(self._current_account.account_name)
        self._stack.setCurrentIndex(1)

        # Load files
        self._load_files()

    def _add_account(self):
        """Add a new cloud account."""
        dialog = CloudLoginDialog(self)
        dialog.login_success.connect(self._on_login_success)
        dialog.exec()

    def _on_login_success(self, account_info: dict):
        """Handle successful login."""
        account_id = self._db.create_cloud_account(
            provider="quark",
            account_name=account_info.get("account_email", "Quark Account"),
            account_email=account_info.get("account_email", ""),
            access_token=account_info.get("access_token", ""),
        )

        # Reload accounts
        accounts = self._db.get_cloud_accounts(provider="quark")
        self._populate_account_list(accounts)

        # Select the new account
        if accounts:
            for i in range(self._account_list.count()):
                item = self._account_list.item(i)
                account = item.data(Qt.UserRole)
                if account.id == account_id:
                    self._account_list.setCurrentItem(item)
                    self._current_account = account
                    self._update_file_view()
                    break

    def _load_files(self):
        """Load files for current directory."""
        if not self._current_account:
            return

        self._status_label.setText(t("loading_files"))

        # Get files from service (returns tuple: files, updated_token)
        result = QuarkDriveService.get_file_list(
            self._current_account.access_token, self._current_parent_id
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            files, updated_token = result
        else:
            files, updated_token = result, None

        # Update token if changed
        if updated_token:
            self._db.update_cloud_account_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

        # Cache files in database
        if files and len(files) > 0:
            self._current_parent_id = files[0].parent_id
            can_go_back = self._current_parent_id != "0"
            self._back_btn.setEnabled(can_go_back)
            self._db.cache_cloud_files(self._current_account.id, files)

            # Reload files from database to get local_path information
        files = self._db.get_cloud_files(self._current_account.id, self._current_parent_id)

        # Save the first file's parent_id (current folder's parent) for back navigation
        # If we have files and we're not at root, the first file's parent_id can help us
        # But actually, we save the parent when navigating INTO a folder

        # Save audio files for playlist playback
        self._current_audio_files = [f for f in files if f.file_type == "audio"]

        # Update table
        self._populate_table(files)
        self._status_label.setText(f"{len(files)} " + t("items"))

    def _populate_table(self, files: List[CloudFile]):
        """Populate table with files."""
        from player.engine import PlayerState
        from PySide6.QtGui import QFont

        self._file_table.setRowCount(0)
        self._file_table.setUpdatesEnabled(False)

        try:
            for row, file in enumerate(files):
                self._file_table.insertRow(row)

                # Check if this file is currently playing
                is_currently_playing = (
                    self._current_playing_file_id and
                    file.file_id == self._current_playing_file_id and
                    file.file_type == "audio"
                )

                # Name
                name_item = QTableWidgetItem(file.name)
                name_item.setData(Qt.UserRole, file)
                name_item.setForeground(QBrush(QColor("#e0e0e0")))

                if file.file_type == "folder":
                    name_item.setText("📁 " + file.name)
                elif is_currently_playing:
                    # Add play/pause icon for currently playing audio
                    if self._player and hasattr(self._player, 'engine'):
                        if self._player.engine.state == PlayerState.PLAYING:
                            name_item.setText("▶ " + file.name)
                        else:
                            name_item.setText("⏸ " + file.name)
                    else:
                        name_item.setText("▶ " + file.name)

                    # Set bold and green color for playing file
                    font = name_item.font()
                    font.setBold(True)
                    name_item.setFont(font)
                    name_item.setForeground(QBrush(QColor("#1db954")))

                self._file_table.setItem(row, 0, name_item)

                # Type
                type_item = QTableWidgetItem(self._get_file_type_label(file.file_type))
                type_item.setForeground(QBrush(QColor("#b0b0b0")))
                self._file_table.setItem(row, 1, type_item)

                # Size
                size_text = ""
                if file.size:
                    size_mb = file.size / (1024 * 1024)
                    size_text = f"{size_mb:.1f} MB"
                size_item = QTableWidgetItem(size_text)
                size_item.setForeground(QBrush(QColor("#909090")))
                self._file_table.setItem(row, 2, size_item)

                # Duration (only for audio files)
                duration_text = ""
                if file.file_type == "audio" and file.duration:
                    duration_text = format_duration(file.duration)
                duration_item = QTableWidgetItem(duration_text)
                duration_item.setForeground(QBrush(QColor("#909090")))
                self._file_table.setItem(row, 3, duration_item)

        finally:
            self._file_table.setUpdatesEnabled(True)

    def _get_file_type_label(self, file_type: str) -> str:
        """Get display label for file type."""
        labels = {"folder": t("folder"), "audio": t("audio"), "other": t("file")}
        return labels.get(file_type, t("file"))

    def _on_item_double_clicked(self, item: QTableWidgetItem):
        """Handle double-click on item."""
        file = item.data(Qt.UserRole)
        if not file:
            return

        if file.file_type == "folder":
            # Navigate into folder
            self._navigate_to_folder(file.file_id, file.name)
        elif file.file_type == "audio":
            # Play audio file
            self._play_audio_file(file)

    def _navigate_to_folder(self, folder_id: str, folder_name: str):
        """Navigate to a folder."""
        # Save current parent_id for history
        parent_id = self._current_parent_id
        current_path = self._path_label.text()

        # Save to navigation history
        self._navigation_history.append((parent_id, current_path))

        # Build fid_path: append current folder ID to the path
        self._fid_path.append(folder_id)
        fid_path_str = "/" + "/".join(self._fid_path)

        self._current_parent_id = folder_id

        # Update path label
        if current_path == "/":
            new_path = f"/{folder_name}"
        else:
            new_path = f"{current_path}/{folder_name}"
        self._path_label.setText(new_path)

        self._back_btn.setEnabled(True)

        # Don't save to database - only save when playing a file
        self._load_files()

    def _navigate_back(self):
        """Navigate to previous folder in history."""
        if self._navigation_history:
            # Pop the previous state from navigation history
            parent_id, path = self._navigation_history.pop()

            # Update fid_path: remove the last folder ID
            if self._fid_path:
                self._fid_path.pop()

            # Navigate to previous folder
            self._current_parent_id = parent_id
            self._path_label.setText(path)

            # Update back button state
            self._back_btn.setEnabled(len(self._navigation_history) > 0 or len(self._fid_path) > 0)

            # Don't save to database - only save when playing a file
            self._load_files()

        elif len(self._fid_path) > 0:
            # History is empty but we have fid_path - use it to go back

            # Remove the last folder from fid_path
            self._fid_path.pop()

            # Determine parent folder ID from fid_path
            if len(self._fid_path) > 0:
                # Get the parent folder ID (last item in fid_path)
                parent_folder_id = self._fid_path[-1]
            else:
                # Back to root
                parent_folder_id = "0"

            # Calculate parent path
            current_path = self._path_label.text()
            if current_path != "/":
                path_parts = current_path.rstrip("/").split("/")
                if len(path_parts) > 1:
                    parent_path = "/".join(path_parts[:-1])
                    if not parent_path:
                        parent_path = "/"
                else:
                    parent_path = "/"
            else:
                parent_path = "/"

            # Navigate to parent folder
            self._current_parent_id = parent_folder_id
            self._path_label.setText(parent_path)
            self._back_btn.setEnabled(len(self._fid_path) > 0)

            # Don't save to database - only save when playing a file
            self._load_files()

        else:
            # Navigate to root
            self._current_parent_id = "0"
            self._path_label.setText("/")
            self._fid_path = []
            self._back_btn.setEnabled(False)

            # Don't save to database
            self._load_files()

    def _restore_playback(self):
        """Restore last playback state if available."""
        if not self._last_playing_fid:
            return

        # Find the file in current folder's audio list
        file_to_play = None
        file_index = 0
        for i, audio_file in enumerate(self._current_audio_files):
            if audio_file.file_id == self._last_playing_fid:
                file_to_play = audio_file
                file_index = i
                break

        if file_to_play:
            self._status_label.setText(f"🎵 恢复播放: {file_to_play.name}")

            # Play the file (will start from saved position)
            self._play_audio_file(file_to_play)

            # Note: Position restoration would require seeking after playback starts
            # This depends on PlayerController/PlayerEngine implementation
        else:
            self._status_label.setText(f"⚠️ 上次播放的文件不在当前文件夹")

        # Clear the restoration state
        self._last_playing_fid = ""
        self._last_position = 0.0

    def _save_playback_position(self):
        """Save current playback position periodically."""
        if not self._current_account or not self._player:
            return

        # Get current position from player engine
        try:
            # Get position from player engine (returns milliseconds)
            if hasattr(self._player, 'engine'):
                player_engine = self._player.engine
                if hasattr(player_engine, 'position'):
                    current_position_ms = player_engine.position()
                else:
                    return
            else:
                return

            # Convert milliseconds to seconds for storage
            current_position = current_position_ms / 1000.0

            # Get currently playing file ID
            if not hasattr(self, '_current_playing_file_id') or not self._current_playing_file_id:
                return

            # Save position to database (in seconds)
            self._db.update_cloud_account_playing_state(
                self._current_account.id,
                position=current_position
            )

        except Exception as e:
            logger.error(f"Error saving playback position: {e}", exc_info=True)

    def _play_audio_file(self, file: CloudFile, start_position: float = None):
        """Play an audio file from cloud.

        Args:
            file: CloudFile to play
            start_position: Optional position to start from (in seconds). If None, uses saved position.
        """
        # Track the currently playing file
        self._current_playing_file_id = file.file_id

        # Save current path and playing state to database when starting playback
        if self._current_account:
            # Build fid_path string
            fid_path_str = "/" + "/".join(self._fid_path) if self._fid_path else "0"
            current_path = self._path_label.text()

            # Save folder path and fid_path
            self._db.update_cloud_account_folder(
                self._current_account.id,
                self._current_parent_id,
                current_path,
                "0",
                fid_path_str
            )

            # Determine start position
            if start_position is not None:
                # Use provided start_position (from restore)
                actual_start_position = start_position
            elif self._last_playing_fid == file.file_id:
                # This is the same file that was playing before
                actual_start_position = self._last_position
            else:
                actual_start_position = 0.0

            if actual_start_position > 0:
                self._status_label.setText(
                    f"🎵 恢复播放: {file.name} (从 {int(actual_start_position // 60)}:{int(actual_start_position % 60):02d} 开始)")

            self._db.update_cloud_account_playing_state(
                self._current_account.id,
                playing_fid=file.file_id,
                position=actual_start_position
            )

        # Find index of this file in current folder's audio list
        try:
            file_index = next(
                i
                for i, f in enumerate(self._current_audio_files)
                if f.file_id == file.file_id
            )
        except StopIteration:
            file_index = 0

        # Check if file already exists locally
        from pathlib import Path
        from utils.helpers import sanitize_filename

        if self._config_manager:
            download_dir = Path(self._config_manager.get_cloud_download_dir())
        else:
            download_dir = Path("data/cloud_downloads")

        # Convert to absolute path
        if not download_dir.is_absolute():
            download_dir = Path.cwd() / download_dir

        safe_filename = sanitize_filename(file.name)
        local_file_path = download_dir / safe_filename

        # Check file status
        if local_file_path.exists() and file.size:
            actual_size = local_file_path.stat().st_size
            size_diff = abs(actual_size - file.size)
            tolerance = file.size * 0.01  # 1% tolerance

            if size_diff > tolerance:
                # File size mismatch
                size_mb = file.size / (1024 * 1024)
                self._status_label.setText(f"{t('file_size_mismatch')}: {file.name} ({size_mb:.1f} MB)")
            else:
                # File exists and size matches
                if actual_start_position == 0:
                    self._status_label.setText(f"{t('using_cached_file')}: {file.name}")
                # else: already set message above about resuming

        else:
            # File doesn't exist or no size info
            size_info = ""
            if file.size:
                size_mb = file.size / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)"
            self._status_label.setText(f"{t('downloading')} {file.name}{size_info}...")

        # Create download thread with context info
        download_thread = CloudFileDownloadThread(
            self._current_account.access_token,
            file,
            file_index,
            self._current_audio_files,
            self._config_manager,
            self,
        )
        download_thread.finished.connect(
            lambda path: self._on_file_downloaded(
                path, file_index, self._current_audio_files, file.name, actual_start_position
            )
        )
        download_thread.file_exists.connect(
            lambda path: self._on_file_exists(
                path, file_index, self._current_audio_files, file.name, actual_start_position
            )
        )
        download_thread.token_updated.connect(self._on_token_updated)
        download_thread.start()

    def _on_file_exists(self, temp_path: str, file_index: int, audio_files: list, file_name: str,
                        start_position: float = 0.0):
        """Handle when file already exists locally."""
        import os

        if temp_path and os.path.exists(temp_path):
            if start_position == 0:
                self._status_label.setText(f"{t('using_cached_file')} - {file_name}")
            # else: message already set in _play_audio_file

            # Save local path to database
            if file_index < len(audio_files):
                cloud_file = audio_files[file_index]
                if self._current_account:
                    self._db.update_cloud_file_local_path(
                        cloud_file.file_id,
                        self._current_account.id,
                        temp_path
                    )

            # Emit signal with playlist info and start position
            self.play_cloud_files.emit(temp_path, file_index, audio_files, start_position)

            # Update current audio files list with local path
            if file_index < len(self._current_audio_files):
                # Update the CloudFile object in current list
                for i, f in enumerate(self._current_audio_files):
                    if f.file_id == self._current_audio_files[file_index].file_id:
                        # Create updated CloudFile with local_path
                        from database.models import CloudFile as CloudFileModel
                        updated_file = CloudFileModel(
                            id=f.id,
                            account_id=f.account_id,
                            file_id=f.file_id,
                            parent_id=f.parent_id,
                            name=f.name,
                            file_type=f.file_type,
                            size=f.size,
                            mime_type=f.mime_type,
                            duration=f.duration,
                            metadata=f.metadata,
                            local_path=temp_path,
                            created_at=f.created_at,
                            updated_at=f.updated_at
                        )
                        self._current_audio_files[i] = updated_file
                        break
        else:
            self._status_label.setText(t("download_failed"))

    def _on_token_updated(self, updated_token: str):
        """Handle updated access token from API calls."""
        if self._current_account and updated_token:
            self._db.update_cloud_account_token(self._current_account.id, updated_token)
            self._current_account.access_token = updated_token

    def _on_file_downloaded(self, temp_path: str, file_index: int, audio_files: list, file_name: str = None,
                            start_position: float = 0.0):
        """Handle completed file download."""
        if temp_path:
            import os

            if os.path.exists(temp_path):
                # Get file name from parameter or audio_files list
                if not file_name and file_index < len(audio_files):
                    file_name = audio_files[file_index].name
                elif not file_name:
                    file_name = "Unknown"

                # Get file size for display
                file_size = os.path.getsize(temp_path)
                size_mb = file_size / (1024 * 1024)

                if start_position == 0:
                    self._status_label.setText(f"{t('download_complete')}: {file_name} ({size_mb:.1f} MB)")

                # Save local path to database
                if file_index < len(audio_files):
                    cloud_file = audio_files[file_index]
                    if self._current_account:
                        self._db.update_cloud_file_local_path(
                            cloud_file.file_id,
                            self._current_account.id,
                            temp_path
                        )

                # Emit signal with playlist info and start position
                self.play_cloud_files.emit(temp_path, file_index, audio_files, start_position)

                # Update current audio files list with local path
                if file_index < len(self._current_audio_files):
                    # Update the CloudFile object in current list
                    for i, f in enumerate(self._current_audio_files):
                        if f.file_id == self._current_audio_files[file_index].file_id:
                            # Create updated CloudFile with local_path
                            from database.models import CloudFile as CloudFileModel
                            updated_file = CloudFileModel(
                                id=f.id,
                                account_id=f.account_id,
                                file_id=f.file_id,
                                parent_id=f.parent_id,
                                name=f.name,
                                file_type=f.file_type,
                                size=f.size,
                                mime_type=f.mime_type,
                                duration=f.duration,
                                metadata=f.metadata,
                                local_path=temp_path,
                                created_at=f.created_at,
                                updated_at=f.updated_at
                            )
                            self._current_audio_files[i] = updated_file

                            # Update table item data
                            for row in range(self._file_table.rowCount()):
                                item = self._file_table.item(row, 0)
                                if item:
                                    table_file = item.data(Qt.UserRole)
                                    if table_file and table_file.file_id == f.file_id:
                                        item.setData(Qt.UserRole, updated_file)
                                        break

                            break
            else:
                self._status_label.setText(t("download_failed"))
        else:
            self._status_label.setText(t("download_failed"))

    def _on_event_bus_download_started(self, file_id: str):
        """Handle download start from EventBus (for auto-play next track).

        This is called when a cloud file download starts during auto-play,
        which uses CloudDownloadService instead of CloudDriveView's own download thread.
        """
        logger.debug(f"[CloudDriveView] _on_event_bus_download_started: {file_id}")

        # Only update status if this file is in our current audio files list
        file_name = None
        file_size = None
        for f in self._current_audio_files:
            if f.file_id == file_id:
                file_name = f.name
                file_size = f.size
                break

        if file_name:
            size_info = ""
            if file_size:
                size_mb = file_size / (1024 * 1024)
                size_info = f" ({size_mb:.1f} MB)"
            self._status_label.setText(f"{t('downloading')} {file_name}{size_info}...")
            logger.debug(f"[CloudDriveView] Updated status for auto-play download start: {file_name}")

    def _on_event_bus_download_completed(self, file_id: str, local_path: str):
        """Handle download completion from EventBus (for auto-play next track).

        This is called when a cloud file download completes during auto-play,
        which uses CloudDownloadService instead of CloudDriveView's own download thread.
        """
        import os

        logger.debug(f"[CloudDriveView] _on_event_bus_download_completed: {file_id}")

        # Update CloudFile's local_path and refresh table
        for f in self._current_audio_files:
            if f.file_id == file_id:
                f.local_path = local_path
                file_name = f.name

                # Update the corresponding row in the table
                for row in range(self._file_table.rowCount()):
                    item = self._file_table.item(row, 0)
                    if item:
                        row_file = item.data(Qt.UserRole)
                        if row_file and row_file.file_id == file_id:
                            # Update the file's local_path
                            row_file.local_path = local_path
                            # Update status column to show downloaded
                            status_item = self._file_table.item(row, 4)
                            if status_item:
                                status_item.setText("✓")
                            break
                break
        else:
            file_name = None

        if file_name and local_path and os.path.exists(local_path):
            file_size = os.path.getsize(local_path)
            size_mb = file_size / (1024 * 1024)
            self._status_label.setText(f"{t('download_complete')}: {file_name} ({size_mb:.1f} MB)")
            logger.debug(f"[CloudDriveView] Updated status for auto-play download: {file_name}")

    def _show_context_menu(self, pos):
        """Show context menu for file."""
        item = self._file_table.itemAt(pos)
        if not item:
            return

        file = item.data(Qt.UserRole)
        if not file or file.file_type != "audio":
            return

        # Check if file has been downloaded
        has_local_path = file.local_path

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1db954;
                color: #000000;
            }
            QMenu::item:disabled {
                color: #808080;
            }
        """)

        play_action = menu.addAction(t("play"))
        play_action.triggered.connect(lambda: self._play_audio_file(file))

        menu.addSeparator()

        # Add file info action
        info_text = f"ℹ️ {t('file_info')}"
        if file.size:
            size_mb = file.size / (1024 * 1024)
            info_text += f" ({size_mb:.1f} MB)"
        if file.duration:
            from utils import format_duration
            info_text += f" - {format_duration(file.duration)}"

        info_action = menu.addAction(info_text)
        info_action.setEnabled(False)  # Just for display, not clickable

        menu.addSeparator()

        queue_action = menu.addAction(t("add_to_queue"))
        queue_action.triggered.connect(lambda: self._add_to_queue(file))

        menu.addSeparator()

        # Edit media info action - only available if file is downloaded
        edit_action = menu.addAction(t("edit_media_info"))
        if has_local_path:
            edit_action.triggered.connect(lambda: self._edit_media_info(file))
        else:
            edit_action.setEnabled(False)
            edit_action.setText(f"{t('edit_media_info')} ({t('download_first')})")

        # Open file location action - only available if file is downloaded
        open_action = menu.addAction(t("open_file_location"))
        if has_local_path:
            open_action.triggered.connect(lambda: self._open_file_location(file))
        else:
            open_action.setEnabled(False)
            open_action.setText(f"{t('open_file_location')} ({t('download_first')})")

        menu.exec_(QCursor.pos())

    def _show_account_context_menu(self, pos):
        """Show context menu for account."""
        item = self._account_list.itemAt(pos)
        if not item:
            return

        account = item.data(Qt.UserRole)
        if not account:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #404040;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #1db954;
                color: #000000;
            }
        """)

        # Add account info action
        info_action = menu.addAction("ℹ️ " + t("get_account_info"))
        info_action.triggered.connect(lambda: self._get_account_info(account))

        menu.addSeparator()

        # Add change download directory action
        change_dir_action = menu.addAction("📁 " + t("change_download_dir"))
        change_dir_action.triggered.connect(lambda: self._change_download_dir())

        menu.addSeparator()

        # Add delete action
        delete_action = menu.addAction("🗑️ " + t("delete_account"))
        delete_action.triggered.connect(lambda: self._delete_account(account))

        menu.exec_(QCursor.pos())

    def _get_account_info(self, account: CloudAccount):
        """Get and display account information."""
        self._status_label.setText(f"{t('loading')} {t('account_info')}...")

        # Get account info from service (returns tuple: info, updated_token)
        result = QuarkDriveService.get_account_info(
            account.access_token, account.account_email
        )

        # Handle tuple return value
        if isinstance(result, tuple):
            account_info, updated_token = result
        else:
            account_info, updated_token = result, None

        # Update token if changed
        if updated_token:
            self._db.update_cloud_account_token(account.id, updated_token)
            account.access_token = updated_token
            # Also update current account if it's the same
            if self._current_account and self._current_account.id == account.id:
                self._current_account.access_token = updated_token

        if account_info:
            # Show account info dialog
            self._show_account_info_dialog(account, account_info)
            self._status_label.setText("")
        else:
            self._status_label.setText(t("failed_to_get_account_info"))
            QMessageBox.warning(self, t("error"), t("failed_to_get_account_info"))

    def _show_account_info_dialog(self, account: CloudAccount, account_info: dict):
        """Show account information dialog."""
        dialog = QMessageBox(self)
        dialog.setWindowTitle(t("account_info"))

        # Format timestamps
        created_at_str = self._format_timestamp(account_info.get("created_at"))
        exp_at_str = self._format_timestamp(account_info.get("exp_at"))

        # Format capacity
        total_capacity_str = self._format_capacity(
            account_info.get("total_capacity", 0)
        )
        used_capacity_str = self._format_capacity(account_info.get("use_capacity", 0))

        # Calculate usage percentage
        total_cap = account_info.get("total_capacity", 0)
        used_cap = account_info.get("use_capacity", 0)
        if total_cap > 0:
            usage_percent = (used_cap / total_cap) * 100
            usage_str = f"{usage_percent:.1f}%"
        else:
            usage_str = "N/A"

        # Build info text
        info_text = f"""
{t("account_name")}: {account_info.get("nickname", account.account_name)}
{t("member_type")}: {account_info.get("member_type", "unknown")}
{t("account_created")}: {created_at_str}
{t("vip_expires")}: {exp_at_str}
{t("storage_used")}: {used_capacity_str} / {total_capacity_str} ({usage_str})
"""

        dialog.setText(info_text)
        dialog.setIcon(QMessageBox.Information)
        dialog.setStandardButtons(QMessageBox.Ok)

        # Style the dialog
        dialog.setStyleSheet("""
            QMessageBox {
                background-color: #1e1e1e;
            }
            QMessageBox QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
        """)

        dialog.exec()

    def _format_timestamp(self, timestamp_ms: int) -> str:
        """Format millisecond timestamp to readable date string."""
        if not timestamp_ms:
            return "N/A"

        try:
            from datetime import datetime

            # Convert milliseconds to seconds
            timestamp_sec = timestamp_ms / 1000
            dt = datetime.fromtimestamp(timestamp_sec)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logger.error(f"Error formatting timestamp: {e}", exc_info=True)
            return "N/A"

    def _format_capacity(self, bytes_size: int) -> str:
        """Format bytes to readable size string (TB/GB/MB)."""
        if not bytes_size or bytes_size == 0:
            return "0 GB"

        try:
            tb = bytes_size / (1024 ** 4)
            gb = bytes_size / (1024 ** 3)
            mb = bytes_size / (1024 ** 2)

            if tb >= 1:
                return f"{tb:.2f} TB"
            elif gb >= 1:
                return f"{gb:.2f} GB"
            else:
                return f"{mb:.2f} MB"
        except Exception as e:
            logger.error(f"Error formatting capacity: {e}", exc_info=True)
            return "N/A"

    def _delete_account(self, account: CloudAccount):
        """Delete a cloud account."""
        reply = QMessageBox.question(
            self,
            t("delete_account"),
            f"{t('delete_account_confirm')}\n\n{account.account_name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self._db.delete_cloud_account(account.id)

            # Reload accounts
            accounts = self._db.get_cloud_accounts(provider="quark")
            self._populate_account_list(accounts)

            # Reset current account if needed
            if self._current_account and self._current_account.id == account.id:
                self._current_account = None
                self._update_file_view()

    def _add_to_queue(self, file: CloudFile):
        """Add file to play queue."""
        from player.playlist_item import PlaylistItem, CloudProvider

        if file.file_type != 'audio':
            return

        # Check if file is already downloaded
        local_path = ""
        if file.local_path:
            local_path = file.local_path
        else:
            # Check download cache
            from pathlib import Path
            from utils.helpers import sanitize_filename

            if self._config_manager:
                download_dir = Path(self._config_manager.get_cloud_download_dir())
            else:
                download_dir = Path("data/cloud_downloads")

            if not download_dir.is_absolute():
                download_dir = Path.cwd() / download_dir

            safe_filename = sanitize_filename(file.name)
            local_file_path = download_dir / safe_filename

            if local_file_path.exists():
                local_path = str(local_file_path)

        # Create playlist item
        account_id = self._current_account.id if self._current_account else 0
        item = PlaylistItem.from_cloud_file(file, account_id, local_path)

        # Add to engine playlist
        self._player.engine.add_track(item)

        # Update status
        self._status_label.setText(f"✓ {t('add_to_queue')}: {file.name}")

    def _edit_media_info(self, file: CloudFile):
        """Edit media info for downloaded cloud file."""
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QDialogButtonBox,
            QPushButton,
            QFormLayout,
            QMessageBox,
        )
        from services import MetadataService
        from pathlib import Path

        if not file.local_path:
            QMessageBox.warning(self, "Error", "File not downloaded")
            return

        # Extract current metadata from file
        current_metadata = MetadataService.extract_metadata(file.local_path)

        # Create dialog
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{t('edit_media_info_title')} - {file.name}")
        dialog.setMinimumWidth(450)
        dialog.setStyleSheet("""
            QDialog {
                background-color: #2a2a2a;
                color: #e0e0e0;
            }
            QLabel {
                color: #e0e0e0;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
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
                color: #e0e0e0;
            }
            QPushButton[role="cancel"]:hover {
                background-color: #505050;
            }
        """)

        layout = QVBoxLayout(dialog)
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        form_layout.setLabelAlignment(Qt.AlignRight)

        # Title field
        title_input = QLineEdit(current_metadata.get("title") or file.name)
        title_input.setPlaceholderText(t("enter_title"))
        form_layout.addRow(t("title") + ":", title_input)

        # Artist field
        artist_input = QLineEdit(current_metadata.get("artist") or "")
        artist_input.setPlaceholderText(t("enter_artist"))
        form_layout.addRow(t("artist") + ":", artist_input)

        # Album field
        album_input = QLineEdit(current_metadata.get("album") or "")
        album_input.setPlaceholderText(t("enter_album"))
        form_layout.addRow(t("album") + ":", album_input)

        # Show file information
        try:
            track_file = Path(file.local_path)
            file_size = track_file.stat().st_size
            file_size_str = self._format_file_size(file_size)

            # Get audio codec info using mutagen
            import mutagen

            audio_info = mutagen.File(file.local_path)
            media_info = []

            if audio_info and hasattr(audio_info, "info"):
                info = audio_info.info
                # Bitrate
                if hasattr(info, "bitrate") and info.bitrate:
                    media_info.append(f"{info.bitrate // 1000} kbps")

                # Sample rate
                if hasattr(info, "sample_rate") and info.sample_rate:
                    media_info.append(f"{info.sample_rate // 1000} kHz")

                # Length/Duration
                if hasattr(info, "length") and info.length:
                    minutes = int(info.length // 60)
                    seconds = int(info.length % 60)
                    media_info.append(f"{minutes}:{seconds:02d}")

            # Format (codec)
            if audio_info:
                mime_type = audio_info.mime if hasattr(audio_info, "mime") else []
                if mime_type:
                    format_str = mime_type[0].split("/")[-1].upper()
                    media_info.append(format_str)
                else:
                    # Try to get format from type
                    if hasattr(audio_info, "type"):
                        media_info.append(audio_info.type)

            # Create info text
            file_info_text = f"{file_size_str}"
            if media_info:
                file_info_text += f" | {' | '.join(media_info)}"

            info_label = QLabel(file_info_text)
            info_label.setStyleSheet("color: #808080; font-size: 11px;")

            # File path
            path_label = QLabel(file.local_path)
            path_label.setStyleSheet("color: #606060; font-size: 10px;")
            path_label.setWordWrap(True)

            # Add both labels in a vertical layout
            info_container = QWidget()
            info_layout = QVBoxLayout(info_container)
            info_layout.setContentsMargins(0, 0, 0, 0)
            info_layout.setSpacing(2)
            info_layout.addWidget(info_label)
            info_layout.addWidget(path_label)

            form_layout.addRow(t("file") + ":", info_container)

        except Exception as e:
            logger.error(f"Error showing file info dialog for {file.name}: {e}", exc_info=True)
            # Fallback to just show path if there's an error
            path_label = QLabel(file.local_path)
            path_label.setStyleSheet("color: #808080; font-size: 11px;")
            path_label.setWordWrap(True)
            form_layout.addRow(t("file") + ":", path_label)

        layout.addLayout(form_layout)

        # Buttons
        buttons = QDialogButtonBox()
        ok_button = QPushButton(t("save"))
        cancel_button = QPushButton(t("cancel"))
        cancel_button.setProperty("role", "cancel")

        buttons.addButton(ok_button, QDialogButtonBox.AcceptRole)
        buttons.addButton(cancel_button, QDialogButtonBox.RejectRole)

        layout.addWidget(buttons)

        def save_changes():
            new_title = title_input.text().strip() or file.name
            new_artist = artist_input.text().strip()
            new_album = album_input.text().strip()

            # Save to file
            success = MetadataService.save_metadata(
                file.local_path,
                title=new_title,
                artist=new_artist,
                album=new_album,
            )

            if success:
                # Update tracks table in database
                track = self._db.get_track_by_cloud_file_id(file.file_id)
                if track:
                    # Update existing track
                    conn = self._db._get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE tracks SET title = ?, artist = ?, album = ? WHERE id = ?",
                        (new_title, new_artist, new_album, track.id)
                    )
                    conn.commit()
                    logger.debug(f"[CloudDriveView] Updated track {track.id} metadata in database")
                else:
                    # Check if track exists by path
                    track = self._db.get_track_by_path(file.local_path)
                    if track:
                        conn = self._db._get_connection()
                        cursor = conn.cursor()
                        cursor.execute(
                            "UPDATE tracks SET title = ?, artist = ?, album = ?, cloud_file_id = ? WHERE id = ?",
                            (new_title, new_artist, new_album, file.file_id, track.id)
                        )
                        conn.commit()
                        logger.debug(f"[CloudDriveView] Updated track {track.id} metadata and cloud_file_id in database")

                # Update CloudFile display name
                file.name = new_title

                QMessageBox.information(self, t("success"), t("media_saved"))

                # Refresh the file list to show updated metadata
                self._load_files()
            else:
                QMessageBox.warning(self, "Error", t("media_save_failed"))

            dialog.accept()

        ok_button.clicked.connect(save_changes)
        cancel_button.clicked.connect(dialog.reject)

        dialog.exec_()

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def _open_file_location(self, file: CloudFile):
        """Open the file location in system file manager."""
        if not file.local_path:
            return

        import platform
        import subprocess
        import shutil
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox

        file_path = Path(file.local_path)
        if not file_path.exists():
            QMessageBox.warning(self, "Error", t("file_not_found"))
            return

        try:
            system = platform.system()

            if system == "Windows":
                subprocess.Popen(["explorer", "/select," + str(file_path)])

            elif system == "Darwin":
                subprocess.Popen(["open", "-R", str(file_path)])

            else:
                # Linux
                # Try to select file in supported file managers
                file_managers = {
                    "nautilus": ["nautilus", "--select", str(file_path)],
                    "dolphin": ["dolphin", "--select", str(file_path)],
                    "caja": ["caja", "--select", str(file_path)],
                    "nemo": ["nemo", str(file_path)],
                }

                for fm, cmd in file_managers.items():
                    if shutil.which(fm):
                        subprocess.Popen(cmd)
                        return

                # fallback - open directory only
                subprocess.Popen(["xdg-open", str(file_path.parent)])

        except Exception as e:
            logger.error(f"Failed to open file location for {file_path}: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to open file location: {e}")

    def _change_download_dir(self):
        """Change the cloud download directory."""
        if not self._config_manager:
            return

        current_dir = self._config_manager.get_cloud_download_dir()

        # Open directory selection dialog
        from PySide6.QtWidgets import QFileDialog

        new_dir = QFileDialog.getExistingDirectory(
            self,
            t("select_download_dir"),
            current_dir,
        )

        if new_dir:
            self._config_manager.set_cloud_download_dir(new_dir)
            self._status_label.setText(f"{t('cloud_download_dir')}: {new_dir}")

    def refresh_ui(self):
        """Refresh UI texts after language change."""
        # Update account list title
        self._account_list_title.setText("☁️ " + t("accounts"))

        # Update button texts
        self._add_account_btn.setText(t("add_account"))
        if hasattr(self, "_back_btn"):
            self._back_btn.setText("← " + t("back"))

        # Update table headers
        if hasattr(self, "_file_table"):
            self._file_table.setHorizontalHeaderLabels(
                [t("title"), t("type"), t("size"), t("duration")]
            )

        # Update title based on state
        if self._current_account:
            self._account_title.setText(self._current_account.account_name)
        else:
            self._account_title.setText(t("select_account"))

        # Update empty state label
        if self._stack.count() > 0:
            empty_page = self._stack.widget(0)
            if empty_page:
                empty_label = empty_page.findChild(QLabel, "emptyLabel")
                if empty_label:
                    empty_label.setText(t("add_cloud_account"))

    def restore_playback_state(self, account_id: int, file_path: str, file_fid: str, auto_play: bool = False, start_position: float = 0.0, local_path: str = ""):
        """
        Restore previous cloud playback state.

        Args:
            account_id: Account ID to select
            file_path: Parent folder ID to load
            file_fid: File ID to highlight (optional)
            auto_play: Whether to auto-play the file (default: False)
            start_position: Position to start playback from (in seconds, default: 0.0)
            local_path: Local path of the file for faster restore (optional)
        """
        # Store file_fid, auto_play, start_position and local_path for later use
        self._restore_file_fid = file_fid
        self._restore_auto_play = auto_play
        self._restore_start_position = start_position
        self._restore_local_path = local_path

        # If we have a local path and it exists, use fast restore path
        if local_path and auto_play:
            import os
            if os.path.exists(local_path):
                print(f"[DEBUG] Fast restore using local path: {local_path}")
                # Use fast restore directly
                self._fast_restore_playback(account_id, file_fid, local_path, start_position)
                return True

        # Select the account
        accounts = self._db.get_cloud_accounts()
        target_account = None

        for account in accounts:
            if account.id == account_id:
                target_account = account
                break

        if not target_account:
            return False
        # Set current account
        self._current_account = target_account
        self._current_parent_id = file_path

        # Restore _fid_path from account's last_fid_path
        if target_account.last_fid_path and target_account.last_fid_path != "0":
            self._fid_path = target_account.last_fid_path.strip("/").split("/")
            if self._fid_path == [""]:
                self._fid_path = []
        else:
            self._fid_path = []

        # Update path label
        self._path_label.setText(target_account.last_folder_path or "/")

        # Update back button state
        can_go_back = len(self._fid_path) > 0
        self._back_btn.setEnabled(can_go_back)

        # Update UI to show selected account
        for i in range(self._account_list.count()):
            item = self._account_list.item(i)
            account = item.data(Qt.UserRole)
            if account.id == account_id:
                self._account_list.setCurrentItem(item)
                break

        # Update account title
        self._account_title.setText(target_account.account_name)

        # Load files for the folder
        self._load_files()

        # If file_fid is provided, try to select/highlight and optionally play the file
        if file_fid and hasattr(self, '_file_table'):
            # Use QTimer to wait for table to populate, then select/play the file
            # Capture variables to avoid late binding issues
            captured_fid = file_fid
            captured_auto_play = auto_play
            print(f"[DEBUG] restore_playback_state: file_fid={file_fid}, auto_play={auto_play}")
            QTimer.singleShot(500, lambda: self._select_and_play_file_by_fid(captured_fid, captured_auto_play))
        elif file_fid:
            print(f"[DEBUG] restore_playback_state: file_fid={file_fid}, but _file_table not ready")
            # Wait for table to be ready
            captured_fid = file_fid
            captured_auto_play = auto_play
            QTimer.singleShot(1000, lambda: self._select_and_play_file_by_fid(captured_fid, captured_auto_play))

        return True

    def _fast_restore_playback(self, account_id: int, file_fid: str, local_path: str, start_position: float):
        """Fast restore playback using known local path without loading folder."""
        from pathlib import Path
        from database.models import CloudFile

        # Select the account in UI
        accounts = self._db.get_cloud_accounts()
        target_account = None
        for account in accounts:
            if account.id == account_id:
                target_account = account
                break

        if not target_account:
            return False

        # Set current account
        self._current_account = target_account

        # Update UI to show selected account
        for i in range(self._account_list.count()):
            item = self._account_list.item(i)
            account = item.data(Qt.UserRole)
            if account.id == account_id:
                self._account_list.setCurrentItem(item)
                break

        # Update account title
        self._account_title.setText(target_account.account_name)

        # Create a minimal CloudFile for playback
        file_name = Path(local_path).name
        cloud_file = CloudFile(
            file_id=file_fid,
            name=file_name,
            file_type='audio',
            local_path=local_path
        )

        # Start playback directly
        print(f"[DEBUG] Fast restore: playing {file_name} from {local_path}")
        self._play_audio_file(cloud_file, start_position=start_position)
        return True

    def _select_and_play_file_by_fid(self, file_fid: str, auto_play: bool = False):
        """Select and optionally play a file in the table by its file ID."""
        start_pos = getattr(self, '_restore_start_position', 0.0)
        print(f"[DEBUG] _select_and_play_file_by_fid: file_fid={file_fid}, auto_play={auto_play}, start_position={start_pos}")
        if not hasattr(self, '_file_table'):
            print("[DEBUG] _file_table not found")
            return

        for row in range(self._file_table.rowCount()):
            item = self._file_table.item(row, 0)
            if item and item.data(Qt.UserRole):
                cloud_file = item.data(Qt.UserRole)
                if hasattr(cloud_file, 'file_id') and cloud_file.file_id == file_fid:
                    # Select the file
                    self._file_table.selectRow(row)
                    self._file_table.scrollToItem(item)
                    print(f"[DEBUG] Found file: {cloud_file.name}, file_type={cloud_file.file_type}")

                    # Auto-play the file if requested and it's an audio file
                    if auto_play and cloud_file.file_type == 'audio':
                        # Use a small delay to ensure UI is ready
                        # Capture cloud_file and start_position in a closure to avoid late binding
                        captured_file = cloud_file
                        captured_position = getattr(self, '_restore_start_position', 0.0)
                        print(f"[DEBUG] Restoring with start_position: {captured_position}s")
                        QTimer.singleShot(300, lambda f=captured_file, p=captured_position: self._play_audio_file(f, start_position=p))
                    break

    def _select_file_by_fid(self, file_fid: str):
        """Select a file in the table by its file ID (without playing)."""
        if not hasattr(self, '_file_table'):
            return

        for row in range(self._file_table.rowCount()):
            item = self._file_table.item(row, 0)
            if item and item.data(Qt.UserRole):
                cloud_file = item.data(Qt.UserRole)
                if hasattr(cloud_file, 'file_id') and cloud_file.file_id == file_fid:
                    self._file_table.selectRow(row)
                    self._file_table.scrollToItem(item)
                    break

    def _on_track_changed(self, track_item):
        """Handle track change event from EventBus."""
        from player.engine import PlayerState
        from PySide6.QtGui import QBrush, QColor

        # Get cloud_file_id from track_item
        new_file_id = None
        if hasattr(track_item, 'cloud_file_id'):
            new_file_id = track_item.cloud_file_id
        elif isinstance(track_item, dict):
            new_file_id = track_item.get('cloud_file_id')

        old_file_id = self._current_playing_file_id

        # Only process if this is a cloud file
        if not new_file_id:
            # Clear highlight if switching to local track
            if old_file_id:
                self._set_file_playing_status(old_file_id, False)
                self._current_playing_file_id = ""
            return

        # Update current playing file ID
        self._current_playing_file_id = new_file_id

        # Update playing indicators in table
        if old_file_id != new_file_id:
            # Remove indicator from old file
            if old_file_id:
                self._set_file_playing_status(old_file_id, False)
            # Add indicator to new file
            self._set_file_playing_status(new_file_id, True)
            # Scroll to the playing file
            self._scroll_to_playing_file()

    def _on_playback_state_changed(self, state: str):
        """Handle playback state change from EventBus."""
        # Update the icon for the currently playing file
        if self._current_playing_file_id:
            # Determine if playing or paused
            is_playing = state == "playing"
            self._set_file_playing_status(self._current_playing_file_id, is_playing, update_icon_only=True)

    def _set_file_playing_status(self, file_id: str, is_playing: bool, update_icon_only: bool = False):
        """Set the playing status for a specific file in the table."""
        from PySide6.QtGui import QBrush, QColor, QFont
        from player.engine import PlayerState

        if not hasattr(self, '_file_table'):
            return

        # Find the row with this file
        for row in range(self._file_table.rowCount()):
            name_item = self._file_table.item(row, 0)
            if name_item:
                cloud_file = name_item.data(Qt.UserRole)
                if cloud_file and hasattr(cloud_file, 'file_id') and cloud_file.file_id == file_id:
                    # Get the original name without icon
                    current_text = name_item.text()
                    # Remove any existing icons
                    original_name = current_text.replace("▶ ", "").replace("⏸ ", "").replace("🎵 ", "").replace("📁 ", "")

                    # Add folder icon back if it's a folder
                    if cloud_file.file_type == "folder":
                        original_name = "📁 " + original_name

                    if is_playing:
                        # Determine which icon to show based on playback state
                        if self._player and hasattr(self._player, 'engine'):
                            if self._player.engine.state == PlayerState.PLAYING:
                                icon = "▶ "
                            else:
                                icon = "⏸ "
                        else:
                            icon = "▶ "

                        new_text = f"{icon}{original_name}"

                        # Update text
                        name_item.setText(new_text)

                        # Update font and color
                        if not update_icon_only:
                            font = name_item.font()
                            font.setBold(True)
                            name_item.setFont(font)
                            name_item.setForeground(QBrush(QColor("#1db954")))
                    else:
                        # Remove playing indicator
                        name_item.setText(original_name)

                        # Reset font and color
                        if not update_icon_only:
                            font = name_item.font()
                            font.setBold(False)
                            name_item.setFont(font)
                            name_item.setForeground(QBrush(QColor("#e0e0e0")))
                    break

    def _scroll_to_playing_file(self):
        """Scroll to the currently playing file in the table."""
        if not self._current_playing_file_id or not hasattr(self, '_file_table'):
            return

        # Find the row with the current playing file
        for row in range(self._file_table.rowCount()):
            name_item = self._file_table.item(row, 0)
            if name_item:
                cloud_file = name_item.data(Qt.UserRole)
                if cloud_file and hasattr(cloud_file, 'file_id') and cloud_file.file_id == self._current_playing_file_id:
                    # Select the row
                    self._file_table.selectRow(row)
                    # Scroll to the item
                    self._file_table.scrollToItem(name_item)
                    break


class CloudFileDownloadThread(QThread):
    """Thread for downloading cloud files."""

    finished = Signal(str)  # Emits local file path
    token_updated = Signal(str)  # Emits updated access token
    file_exists = Signal(str)  # Emits local file path when file already exists

    def __init__(
            self,
            access_token: str,
            file: CloudFile,
            file_index: int = 0,
            audio_files: list = None,
            config_manager=None,
            parent=None,
    ):
        super().__init__(parent)
        self._access_token = access_token
        self._file = file
        self._file_index = file_index
        self._audio_files = audio_files or []
        self._config_manager = config_manager
        logger.debug(f"[CloudFileDownloadThread] __init__ called for file: {file.name}")
        pass  # Thread created

    def run(self):
        """Download file in background thread."""
        import os
        from pathlib import Path
        import time

        start_time = time.time()
        logger.debug(f"[CloudFileDownloadThread] run() started for: {self._file.name}")

        # Get download directory from config
        if self._config_manager:
            download_dir = self._config_manager.get_cloud_download_dir()
        else:
            download_dir = "data/cloud_downloads"

        # Create download directory if it doesn't exist
        download_path = Path(download_dir)
        # Convert to absolute path
        if not download_path.is_absolute():
            download_path = Path.cwd() / download_path
        download_path.mkdir(parents=True, exist_ok=True)

        # Use original filename
        from utils.helpers import sanitize_filename
        safe_filename = sanitize_filename(self._file.name)
        local_file_path = download_path / safe_filename

        # Check if file already exists and has correct size
        if local_file_path.exists():
            logger.debug(f"[CloudFileDownloadThread] File exists: {local_file_path}")
            file_size = local_file_path.stat().st_size
            expected_size = self._file.size if self._file.size else 0

            # If we have expected size, verify it matches
            if expected_size > 0:
                # Allow 1% tolerance for file size differences (metadata, etc.)
                size_diff = abs(file_size - expected_size)
                tolerance = expected_size * 0.01  # 1% tolerance

                if size_diff <= tolerance:
                    # File size matches, use existing file
                    logger.debug(f"[CloudFileDownloadThread] File size matches, using cached file. Took: {time.time() - start_time:.3f}s")
                    self.file_exists.emit(str(local_file_path))
                    return
                else:
                    # File size mismatch, need to re-download
                    logger.debug(f"[CloudFileDownloadThread] File size mismatch, re-downloading")
                    pass
            else:
                # No size info available, use existing file
                logger.debug(f"[CloudFileDownloadThread] No size info, using cached file. Took: {time.time() - start_time:.3f}s")
                self.file_exists.emit(str(local_file_path))
                return

        # Get download URL
        logger.debug(f"[CloudFileDownloadThread] Getting download URL for file_id: {self._file.file_id}")
        url_start = time.time()
        result = QuarkDriveService.get_download_url(
            self._access_token, self._file.file_id
        )
        logger.debug(f"[CloudFileDownloadThread] get_download_url took: {time.time() - url_start:.3f}s")

        # Handle tuple return value
        if isinstance(result, tuple):
            url, updated_token = result
        else:
            url, updated_token = result, None

        # Emit token update signal if changed
        if updated_token:
            self.token_updated.emit(updated_token)

        if url:
            # If file exists and size mismatch, delete it first
            if local_file_path.exists():
                expected_size = self._file.size if self._file.size else 0
                if expected_size > 0:
                    actual_size = local_file_path.stat().st_size
                    size_diff = abs(actual_size - expected_size)
                    tolerance = expected_size * 0.01

                    if size_diff > tolerance:
                        local_file_path.unlink()

            # Download to persistent location
            logger.debug(f"[CloudFileDownloadThread] Starting download from URL to: {local_file_path}")
            download_start = time.time()
            success = QuarkDriveService.download_file(
                url, str(local_file_path), self._access_token
            )
            logger.debug(f"[CloudFileDownloadThread] download_file took: {time.time() - download_start:.3f}s, success={success}")

            if success:
                # Verify downloaded file size
                if local_file_path.exists():
                    downloaded_size = local_file_path.stat().st_size
                    expected_size = self._file.size if self._file.size else 0

                    if expected_size > 0:
                        size_diff = abs(downloaded_size - expected_size)
                        tolerance = expected_size * 0.01  # 1% tolerance

                        if size_diff <= tolerance:
                            logger.debug(f"[CloudFileDownloadThread] Download complete, emitting finished signal. Total time: {time.time() - start_time:.3f}s")
                            self.finished.emit(str(local_file_path))
                            return
                        else:
                            # Delete incomplete file
                            local_file_path.unlink()
                            logger.error(f"[CloudFileDownloadThread] Download size mismatch, expected {expected_size}, got {downloaded_size}")
                            self.finished.emit("")
                    else:
                        # No size info, assume download was successful
                        logger.debug(f"[CloudFileDownloadThread] Download complete (no size check), emitting finished signal. Total time: {time.time() - start_time:.3f}s")
                        self.finished.emit(str(local_file_path))
                        return
                else:
                    logger.error("[CloudFileDownloadThread] File does not exist after download")
                    self.finished.emit("")
            else:
                logger.error("[CloudFileDownloadThread] Download failed")
                self.finished.emit("")
        else:
            logger.error(f"[CloudFileDownloadThread] Failed to get download URL")
            self.finished.emit("")
            self.finished.emit("")
